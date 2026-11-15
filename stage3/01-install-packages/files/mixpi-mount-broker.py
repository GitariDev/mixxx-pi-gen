#!/usr/bin/env python3
"""Opt-in appliance lifecycle authority. Never adopts existing mounts."""
import ctypes
import array
import errno
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import select
import socket
import stat
import struct
import sys
import tempfile


class Refused(RuntimeError):
    pass


def load_inventory():
    path = Path(__file__).with_name('mixpi-media-inventory.py')
    spec = importlib.util.spec_from_file_location('broker_inventory', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def generation(physical):
    fields = [physical[key] for key in ('boot_id', 'namespace', 'sysfs', 'device', 'diskseq')]
    return ''.join(f'{len(field.encode())}:{field}' for field in fields)


def alive(descriptor):
    poller = select.poll()
    poller.register(descriptor, select.POLLIN)
    return not poller.poll(0)


def authenticate(connection, uid):
    process, peer_uid, _ = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
    descriptor = connection.getsockopt(socket.SOL_SOCKET, 77)
    try:
        if peer_uid != uid or not alive(descriptor):
            raise Refused('Peer identity/lifetime unavailable')
        own = os.stat('/proc/self/ns/mnt')
        peer = os.stat(f'/proc/{process}/ns/mnt')
        if (own.st_dev, own.st_ino) != (peer.st_dev, peer.st_ino):
            raise Refused('Other mount namespace')
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


class NativeDrain:
    def __init__(self, uid, key, *, endpoint=None):
        self.connection = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC)
        self.process = -1
        try:
            self.connection.settimeout(2)
            self.connection.connect(endpoint or f'/run/user/{uid}/mixpi-copy/control')
            self.process = authenticate(self.connection, uid)
            namespace = os.open('/proc/self/ns/mnt', os.O_RDONLY | os.O_CLOEXEC)
            try:
                self.connection.sendmsg([b'NAMESPACE'], [(socket.SOL_SOCKET, socket.SCM_RIGHTS,
                                                          array.array('i', [namespace]))])
                if self.connection.recv(64) != b'OK' or not alive(self.process):
                    raise Refused('Native namespace proof denied')
            finally:
                os.close(namespace)
            if self.request('DRAIN\n' + key) not in ('IDLE', 'BUSY'):
                raise Refused('Native drain denied or restart quarantine')
        except BaseException:
            self.close()
            raise

    def request(self, message):
        if not alive(self.process):
            raise Refused('Native owner exited; protection quarantined')
        self.connection.sendall(message.encode())
        response = self.connection.recv(64).decode()
        if not alive(self.process):
            raise Refused('Native owner exited')
        return response

    def idle(self):
        response = self.request('DRAIN_STATUS')
        if response not in ('IDLE', 'BUSY'):
            raise Refused('Native protocol failure')
        return response == 'IDLE'

    def cancel(self):
        if self.request('DRAIN_CANCEL') != 'OK':
            raise Refused('Drain cancellation not acknowledged')
        self.close()

    def complete(self):
        if self.request('DRAIN_COMMIT') != 'OK':
            raise Refused('Native retirement not acknowledged')
        self.close()

    def close(self):
        self.connection.close()
        if self.process >= 0:
            os.close(self.process)
            self.process = -1


class Owner:
    def __init__(self, connection, process):
        self.connection = connection
        self.process = process
        self.connected = True

    def alive(self):
        if not self.connected or not alive(self.process):
            return False
        poller = select.poll()
        poller.register(self.connection, select.POLLHUP | select.POLLERR | select.POLLRDHUP)
        return not poller.poll(0)

    def disconnect(self):
        self.connected = False
        self.connection.close()
        os.close(self.process)


class LinuxOS:
    def __init__(self, uid):
        self.uid = uid
        self.inventory = load_inventory()
        self.base = Path('/media') / pwd.getpwuid(uid).pw_name
        self.libc = ctypes.CDLL(None, use_errno=True)
        self.libc.mount.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_char_p]
        self.libc.umount2.argtypes = [ctypes.c_char_p, ctypes.c_int]

    def snapshot(self):
        if os.readlink('/proc/self/ns/mnt') != os.readlink('/proc/1/ns/mnt'):
            raise Refused('Broker is not in the host mount namespace')
        first = Path('/proc/self/mountinfo').read_text()
        mounts = self.inventory.parse_mounts(first)
        if any(mount['path'] != '/' and (str(self.base) == mount['path'] or
               str(self.base).startswith(mount['path'] + '/')) for mount in mounts):
            raise Refused('Media parent must be on the system root, not an alias mount')
        observed = self.inventory.observe()
        if Path('/proc/self/mountinfo').read_text() != first:
            raise Refused('Concurrent topology transition')
        drives = {}
        for drive in observed['drives']:
            sysfs = Path('/sys/dev/block', drive['device']).resolve(strict=True)
            members = {part['device'] for part in drive['partitions']}
            for device in members:
                node = Path('/sys/dev/block', device).resolve(strict=True)
                if '/virtual/' in str(node):
                    raise Refused('Virtual block device')
                if any(list((node / folder).iterdir()) for folder in ('holders', 'slaves') if (node / folder).exists()):
                    raise Refused('Stacked block device')
            physical = dict(boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                            namespace=os.readlink('/proc/self/ns/mnt'), sysfs=str(sysfs),
                            device=drive['device'], diskseq=drive['diskseq'])
            drives[drive['token']] = dict(drive, generation=generation(physical), members=members)
        relevant = set().union(*(drive['members'] for drive in drives.values())) if drives else set()
        host_namespace = os.readlink('/proc/self/ns/mnt')
        host_user_namespace = os.readlink('/proc/1/ns/user')
        seen = {host_namespace}
        for process in Path('/proc').iterdir():
            if not process.name.isdecimal():
                continue
            try:
                if os.readlink(process / 'ns/user') != host_user_namespace:
                    raise Refused('Existing user namespaces are outside the controlled appliance profile')
                namespace = os.readlink(process / 'ns/mnt')
                if namespace in seen:
                    continue
                other_mounts = self.inventory.parse_mounts((process / 'mountinfo').read_text())
                if any(mount['device'] in relevant for mount in other_mounts):
                    raise Refused('USB device mounted in another namespace')
                seen.add(namespace)
            except FileNotFoundError:
                continue
        if Path('/proc/self/mountinfo').read_text() != first:
            raise Refused('Topology changed during namespace validation')
        return drives, mounts

    def verify(self, mount):
        self.inventory.validate_mount_path(mount)
        if Path(mount['path']).resolve(strict=True) != Path(mount['path']):
            raise Refused('Mount target alias')

    def create_target(self, device, key):
        self.base.mkdir(mode=0o755, exist_ok=True)
        status = self.base.lstat()
        if not stat.S_ISDIR(status.st_mode) or status.st_uid != 0 or status.st_mode & 0o022:
            raise Refused('Untrusted media parent')
        digest = hashlib.sha256(key.encode()).hexdigest()
        prefix = 'mixpi-' + device.replace(':', '-') + '-' + digest + '-'
        return Path(tempfile.mkdtemp(prefix=prefix, dir=self.base))

    def mount(self, device, key):
        node = Path('/sys/dev/block', device).resolve(strict=True)
        disk = node.parent if (node / 'partition').exists() else node
        physical = dict(boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                        namespace=os.readlink('/proc/self/ns/mnt'), sysfs=str(disk),
                        device=(disk / 'dev').read_text().strip(), diskseq=(disk / 'diskseq').read_text().strip())
        if generation(physical) != key:
            raise Refused('Physical generation changed before device open')
        properties = dict(line.split('=', 1) for line in (node / 'uevent').read_text().splitlines() if '=' in line)
        name = properties.get('DEVNAME', '')
        if not name or '/' in name or name in ('.', '..'):
            raise Refused('Invalid kernel device name')
        source = Path('/dev') / name
        status = source.lstat()
        if not stat.S_ISBLK(status.st_mode) or f'{os.major(status.st_rdev)}:{os.minor(status.st_rdev)}' != device:
            raise Refused('Device node changed')
        target = self.create_target(device, key)
        descriptor = os.open(source, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
        try:
            if os.fstat(descriptor).st_rdev != status_device(device):
                raise Refused('Changed opened device')
            sequence = struct.unpack('Q', fcntl.ioctl(descriptor, 0x80081280, bytes(8)))[0]
            if sequence != int(physical['diskseq']):
                raise Refused('Opened block descriptor belongs to another generation')
            pinned = f'/proc/self/fd/{descriptor}'.encode()
            for filesystem in (b'vfat', b'exfat'):
                options = f'uid={self.uid},gid={pwd.getpwuid(self.uid).pw_gid},fmask=0133,dmask=0022'.encode()
                if self.libc.mount(pinned, os.fsencode(target), filesystem, 2 | 4 | 8, options) == 0:
                    return str(target)
                error = ctypes.get_errno()
                if error not in (errno.EINVAL, errno.ENODEV):
                    raise OSError(error, os.strerror(error))
            raise Refused('Only kernel vfat/exfat filesystems are supported')
        finally:
            os.close(descriptor)

    def unmount(self, mount):
        self.verify(mount)
        if self.libc.umount2(os.fsencode(mount['path']), 0) != 0:
            error = ctypes.get_errno()
            raise OSError(error, os.strerror(error))


def status_device(device):
    major, minor = device.split(':')
    return os.makedev(int(major), int(minor))


class Broker:
    def __init__(self, adapter, drain_factory):
        self.os = adapter
        self.drain_factory = drain_factory
        self.owned = {}
        self.transactions = {}
        self.retired = set()
        self.quarantine = None
        self.os.snapshot()

    def selected(self, token):
        if self.quarantine:
            raise Refused(self.quarantine)
        drives, mounts = self.os.snapshot()
        if token not in drives:
            raise Refused('Stale physical selection; refresh and select again')
        drive = drives[token]
        if drive['generation'] in self.retired:
            raise Refused('Generation retired; physically reconnect before reuse')
        relevant = [mount for mount in mounts if mount['device'] in drive['members']]
        for mount in relevant:
            if mount['root'] != '/' or self.owned.get(mount['id']) != (drive['generation'], mount):
                raise Refused('Unmanaged mount or alias; no adoption permitted')
            if sum(other['device'] == mount['device'] for other in mounts) != 1:
                raise Refused('Aliased partition')
            if any(other['id'] != mount['id'] and (other['path'] == mount['path'] or
                   other['path'].startswith(mount['path'] + '/')) for other in mounts):
                raise Refused('Overmount or nested mount')
            self.os.verify(mount)
        expected = {ident for ident, (key, _) in self.owned.items() if key == drive['generation']}
        if expected != {mount['id'] for mount in relevant}:
            raise Refused('Owned mount disappeared or changed')
        return drive, relevant

    def mount(self, token):
        drive, mounts = self.selected(token)
        if mounts or self.transactions:
            raise Refused('Already mounted or lifecycle transaction active')
        drain = self.drain_factory(drive['generation'])
        try:
            if not drain.idle():
                drain.cancel()
                return dict(status='busy', safe=False)
            candidates = [part for part in drive['partitions'] if part['device'] != drive['device']]
            if not candidates:
                raise Refused('Partitioned USB disk required')
            current_token = token
            for part in candidates:
                current, _ = self.selected(current_token)
                if current['generation'] != drive['generation'] or not drain.idle():
                    raise Refused('Identity or native protection changed')
                target = self.os.mount(part['device'], drive['generation'])
                latest, all_mounts = self.os.snapshot()
                refreshed = [item for item in latest.values() if item['generation'] == drive['generation']]
                exact = [item for item in all_mounts if item['path'] == target and item['device'] == part['device'] and item['root'] == '/']
                if len(refreshed) != 1 or len(exact) != 1:
                    raise Refused('Mount completion cannot be verified')
                self.os.verify(exact[0])
                self.owned[exact[0]['id']] = (drive['generation'], exact[0])
                current_token = refreshed[0]['token']
                self.selected(current_token)
            drain.cancel()
            return dict(status='mounted', safe=False, token=current_token)
        except BaseException:
            self.quarantine = 'Mount lifecycle failed; restart recovery requires administrator review'
            self.transactions[token] = dict(drain=drain, generation=drive['generation'], mounts=mounts, changed=True, owner=None)
            raise

    def begin(self, token, owner):
        if len(self.transactions) >= 16:
            raise Refused('Drain capacity reached; review quarantined transactions')
        drive, mounts = self.selected(token)
        if not owner.alive():
            raise Refused('Requesting peer exited/disconnected')
        if token in self.transactions or not mounts:
            raise Refused('No controlled mounts or drain already active')
        drain = self.drain_factory(drive['generation'])
        self.transactions[token] = dict(drain=drain, generation=drive['generation'], mounts=mounts,
                                        changed=False, owner=owner, cutoff=False, ready=False)
        return dict(status='draining', safe=False)

    def cancel(self, token, owner):
        transaction = self.transaction(token, owner)
        if transaction['cutoff']:
            return dict(status='too-late', safe=False, cancellable=False)
        if transaction['changed']:
            raise Refused('Partial operation quarantined; cannot reopen admission')
        self.selected(token)
        transaction['drain'].cancel()
        del self.transactions[token]
        return dict(status='cancelled', safe=False)

    def commit(self, token, owner):
        transaction = self.transaction(token, owner)
        if not transaction['ready'] or transaction['cutoff']:
            raise Refused('Poll for readiness before accepting the irreversible cutoff')
        transaction['cutoff'] = True
        return dict(status='committing', safe=False, cancellable=False)

    def transaction(self, token, owner):
        transaction = self.transactions.get(token)
        if not transaction or transaction['owner'] != owner:
            raise Refused('Transaction belongs to another authenticated connection')
        if not owner.alive():
            raise Refused('Requesting peer exited/disconnected; drain retained')
        return transaction

    def poll(self, token, owner):
        transaction = self.transaction(token, owner)
        if transaction['changed']:
            raise Refused('Partial operation quarantined; keep connected')
        drive, mounts = self.selected(token)
        if drive['generation'] != transaction['generation'] or mounts != transaction['mounts']:
            raise Refused('Selected generation/topology changed')
        if not transaction['drain'].idle():
            return dict(status='busy', safe=False)
        if not transaction['cutoff']:
            transaction['ready'] = True
            return dict(status='ready', safe=False, cancellable=True)
        removed = []
        try:
            for mount in mounts:
                current_drives, current_mounts = self.os.snapshot()
                matching = [item for item in current_drives.values() if item['generation'] == drive['generation']]
                remaining = [item for item in current_mounts if item['device'] in drive['members']]
                if len(matching) != 1 or remaining != [item for item in mounts if item['id'] not in removed]:
                    raise Refused('Topology changed while draining')
                self.selected(matching[0]['token'])
                if not owner.alive() or not transaction['drain'].idle():
                    raise Refused('Native protection lost')
                transaction['changed'] = True
                self.os.unmount(mount)
                _, verified = self.os.snapshot()
                if any(item['id'] == mount['id'] or item['path'] == mount['path'] for item in verified):
                    raise Refused('Unmount completion not verified')
                removed.append(mount['id'])
                del self.owned[mount['id']]
            final_drives, final_mounts = self.os.snapshot()
            if not any(item['generation'] == drive['generation'] for item in final_drives.values()) or any(
                    item['device'] in drive['members'] for item in final_mounts) or not owner.alive() or not transaction['drain'].idle():
                raise Refused('Final generation/idle verification failed')
            self.retired.add(drive['generation'])
            transaction['drain'].complete()
            del self.transactions[token]
            return dict(status='unmounted', safe=True, removed=removed, token=None)
        except (OSError, Refused, RuntimeError) as error:
            return dict(status='quarantined', safe=False, removed=removed, error=str(error))


def checked_profile(uid):
    for path, expected in (('/etc/mixpi/controlled-media', 'v1\n'),
                           ('/etc/mixpi/eject-reviewed', 'v1\n')):
        status = os.lstat(path)
        if not stat.S_ISREG(status.st_mode) or status.st_uid != 0 or status.st_mode & 0o022 or Path(path).read_text() != expected:
            raise Refused('Missing root-owned reviewed appliance capability')
    if uid == 0 or os.geteuid() != 0:
        raise Refused('Root broker and non-root appliance account required')
    if os.path.realpath('/etc/systemd/system/udisks2.service') != '/dev/null':
        raise Refused('udisks2 must be masked')
    if Path('/proc/sys/user/max_user_namespaces').read_text().strip() != '0':
        raise Refused('User namespace creation must be disabled in this appliance profile')
    for path in ('/usr/bin/udevil', '/bin/mount', '/bin/umount', '/usr/bin/fusermount', '/usr/bin/fusermount3',
                 '/usr/bin/ntfs-3g', '/usr/sbin/mount.cifs'):
        if Path(path).exists() and os.stat(path).st_mode & (stat.S_ISUID | stat.S_ISGID):
            raise Refused('Competing privileged lifecycle binary')


def serve():
    uid = pwd.getpwnam('pi').pw_uid
    checked_profile(uid)
    directory = Path('/run/mixpi-mount')
    directory.mkdir(mode=0o755, exist_ok=True)
    status = directory.lstat()
    if not stat.S_ISDIR(status.st_mode) or status.st_uid != 0 or status.st_mode & 0o022:
        raise Refused('Untrusted runtime directory')
    lock = os.open(directory / 'owner.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    broker = Broker(LinuxOS(uid), lambda key: NativeDrain(uid, key))
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC)
    endpoint = directory / 'control'
    endpoint.unlink(missing_ok=True)
    listener.bind(str(endpoint))
    os.chown(endpoint, uid, pwd.getpwuid(uid).pw_gid)
    os.chmod(endpoint, 0o600)
    listener.listen(8)
    listener.setblocking(False)
    clients = {}
    while True:
        readable, _, _ = select.select([listener, *clients], [], [], 0.25)
        for connection, owner in list(clients.items()):
            if not owner.alive():
                clients.pop(connection)
                owner.disconnect()
        for connection in readable:
            if connection is listener:
                client, _ = listener.accept()
                try:
                    if len(clients) >= 16:
                        raise Refused('Connection limit')
                    process = authenticate(client, uid)
                    client.settimeout(2)
                    clients[client] = Owner(client, process)
                except (OSError, Refused):
                    client.close()
                continue
            if connection not in clients:
                continue
            try:
                data, _, flags, _ = connection.recvmsg(8192)
                if not data or flags & socket.MSG_TRUNC:
                    raise ConnectionError('Closed or oversized request')
                request = json.loads(data)
                if not isinstance(request, dict) or set(request) - {'op', 'token'}:
                    raise Refused('Invalid narrow request')
                operation, token = request.get('op'), request.get('token')
                owner = clients[connection]
                if operation == 'list':
                    drives, _ = broker.os.snapshot()
                    answer = dict(status='inventory', safe=False, drives=[dict(token=key, device=value['device'],
                                  diskseq=value['diskseq'], volumes=value['volumes']) for key, value in drives.items()])
                elif not isinstance(token, str) or len(token) != 64:
                    raise Refused('Exact physical token required')
                elif operation == 'mount':
                    answer = broker.mount(token)
                elif operation == 'eject':
                    answer = broker.begin(token, owner)
                elif operation == 'poll':
                    answer = broker.poll(token, owner)
                elif operation == 'commit':
                    answer = broker.commit(token, owner)
                elif operation == 'cancel':
                    answer = broker.cancel(token, owner)
                else:
                    raise Refused('Unknown operation')
                connection.sendall(json.dumps(answer).encode())
            except (Refused, OSError, ValueError, RuntimeError) as error:
                try:
                    connection.sendall(json.dumps(dict(status='blocked', safe=False, error=str(error))).encode())
                except OSError:
                    pass
                clients.pop(connection).disconnect()


if __name__ == '__main__':
    serve()
