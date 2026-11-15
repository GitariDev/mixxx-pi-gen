#!/usr/bin/env python3
"""Read-only physical USB inventory and fail-closed eject transaction policy.

The CLI only observes. It cannot unmount, stop a player or authorize an eject.
Native worker ownership and an identity-bound unmount lease are not available
in the current Mixxx binary; every production eject therefore stays blocked.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys


GATES = frozenset({
    'pending_loads', 'analyzers', 'decoder_cache_fallback', 'metadata_queue',
    'recording_writers', 'copy_writers', 'hotplug_admission',
    'mount_namespaces', 'identity_bound_unmount',
})
UNFINISHED = (
    'EJECT BLOCKED: no per-drive exclusive media-use lease. Pending loads, '
    'analyzers, original-file decoder/cache fallback, queued metadata, '
    'recording/copy writers, mount namespaces and hotplug admission are not '
    'proven quiescent. Cached playback is not proof of independence. '
    'No unmount was attempted. Keep this drive connected.'
)


class ObservationError(RuntimeError):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def decode_mount(value):
    return re.sub(r'\\(040|011|012|134)',
                  lambda match: chr(int(match[1], 8)), value)


def parse_mounts(text):
    mounts = []
    seen = set()
    for line in text.splitlines():
        fields = line.split()
        try:
            separator = fields.index('-')
            if separator < 6 or len(fields) != separator + 4:
                raise ValueError('incomplete mount record')
            mount_id = int(fields[0])
            int(fields[1])
            if mount_id in seen or not re.fullmatch(r'\d+:\d+', fields[2]):
                raise ValueError('ambiguous mount identity')
            seen.add(mount_id)
            mounts.append(dict(id=mount_id, device=fields[2],
                               root=decode_mount(fields[3]),
                               path=decode_mount(fields[4]),
                               options=fields[5], filesystem=fields[separator + 1],
                               source=decode_mount(fields[separator + 2])))
        except (ValueError, IndexError) as error:
            raise ObservationError('Cannot parse mountinfo') from error
    if not mounts or not any(mount['path'] == '/' for mount in mounts):
        raise ObservationError('System root mount is unknown')
    return sorted(mounts, key=lambda mount: mount['id'])


def protected(path):
    return path == '/' or any(path == root or path.startswith(root + '/')
                             for root in ('/boot', '/usr', '/var', '/home',
                                          '/etc', '/opt', '/srv'))


def validate_mount_path(mount, proc=Path('/proc')):
    if not hasattr(os, 'O_PATH'):
        raise ObservationError('Kernel path identity unavailable')
    descriptor = os.open(mount['path'], os.O_PATH | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        status = os.fstat(descriptor)
        fields = (proc / 'self/fdinfo' / str(descriptor)).read_text().splitlines()
        identities = [line.split(':', 1)[1].strip() for line in fields
                      if line.startswith('mnt_id:')]
        device = f'{os.major(status.st_dev)}:{os.minor(status.st_dev)}'
        if identities != [str(mount['id'])] or device != mount['device']:
            raise ObservationError('Resolved directory differs from selected mount')
    finally:
        os.close(descriptor)


def inventory(blocks, mounts, identities, boot_id, namespace, swap_devices=(),
              validate_path=None):
    validate_path = validate_path or validate_mount_path
    nodes = {}
    owners = {}

    def visit(node, ancestors=()):
        device = node.get('maj:min')
        if not isinstance(device, str) or not re.fullmatch(r'\d+:\d+', device):
            raise ObservationError('Unknown block device identity')
        if device in nodes and nodes[device].get('name') != node.get('name'):
            raise ObservationError('Conflicting block topology')
        nodes[device] = node
        disks = ancestors + ((device,) if node.get('type') == 'disk' else ())
        owners.setdefault(device, set()).update(disks)
        for child in node.get('children', []):
            visit(child, disks)

    for block in blocks:
        visit(block)
    excluded = set()
    for mount in mounts:
        if protected(mount['path']):
            if mount['device'].startswith('0:') and mount['path'] != '/':
                continue
            if not owners.get(mount['device']):
                raise ObservationError('System disk ancestry cannot be proven')
            excluded.update(owners[mount['device']])
    for device, node in nodes.items():
        if '[SWAP]' in (node.get('mountpoints') or []) or device in swap_devices:
            if not owners.get(device):
                raise ObservationError('Swap disk ancestry cannot be proven')
            excluded.update(owners[device])
    if not boot_id or not namespace:
        raise ObservationError('Boot or mount namespace identity unavailable')
    drives = []
    for device, node in sorted(nodes.items()):
        if node.get('type') != 'disk' or node.get('tran') != 'usb' or device in excluded:
            continue
        identity = identities.get(device)
        if not identity or not identity.get('sysfs') or not identity.get('diskseq'):
            raise ObservationError('USB generation identity unavailable')
        members = sorted(member for member, disks in owners.items() if device in disks)
        if any(nodes[member].get('type') not in ('disk', 'part') or
               len(owners[member]) != 1 for member in members):
            raise ObservationError('Stacked USB topology is not supported safely')
        partitions = [dict(device=member, size=int(nodes[member]['size']),
                           mounts=[mount for mount in mounts if mount['device'] == member])
                      for member in members]
        drive_key = digest([boot_id, namespace, device, identity])
        fingerprint = digest([drive_key, partitions])
        volumes = []
        for partition in partitions:
            for mount in partition['mounts']:
                if mount['root'] != '/':
                    continue
                if sum(other['path'] == mount['path'] for other in mounts) != 1:
                    raise ObservationError('Overmounted source is ambiguous')
                validate_path(mount)
                label = nodes[partition['device']].get('label') or 'Unlabelled'
                volumes.append(dict(label=label, size=partition['size'],
                                    mount=mount, drive=drive_key,
                                    physical=dict(identity, device=device, boot_id=boot_id,
                                                  namespace=namespace),
                                    token=digest([fingerprint, mount]),
                                    discriminator=f"{mount['path']} · {partition['device']} · mount {mount['id']}",
                                    state='observed; use unknown'))
        drives.append(dict(identity=drive_key, token=fingerprint, device=device,
                           diskseq=identity['diskseq'], size=int(node['size']),
                           partitions=partitions, volumes=volumes,
                           state='blocked', reason=UNFINISHED))
    return dict(version=1, drives=drives)


def observe(proc=Path('/proc'), sysfs=Path('/sys'), run=subprocess.run):
    first = (proc / 'self/mountinfo').read_text()
    mounts = parse_mounts(first)
    namespace = os.readlink(proc / 'self/ns/mnt')
    command = ['/usr/bin/lsblk', '--json', '--bytes', '--output',
               'NAME,TYPE,TRAN,SIZE,LABEL,MAJ:MIN,MOUNTPOINTS']
    result = run(command,
                 capture_output=True, text=True, check=True, timeout=4)
    blocks = json.loads(result.stdout)['blockdevices']
    identities = {}
    for block in blocks:
        if block.get('type') == 'disk':
            target = (sysfs / 'dev/block' / block['maj:min']).resolve(strict=True)
            sequence = (target / 'diskseq').read_text().strip()
            if not sequence.isdecimal() or int(sequence) <= 0:
                raise ObservationError('Invalid kernel disk sequence')
            identities[block['maj:min']] = dict(sysfs=str(target), diskseq=sequence)
    swaps = []
    for line in (proc / 'swaps').read_text().splitlines()[1:]:
        path = decode_mount(line.split()[0])
        stat = os.stat(path)
        number = stat.st_rdev or stat.st_dev
        swaps.append(f'{os.major(number)}:{os.minor(number)}')
    answer = inventory(blocks, mounts, identities,
                       (proc / 'sys/kernel/random/boot_id').read_text().strip(),
                       namespace, swaps, lambda mount: validate_mount_path(mount, proc))
    after = run(command, capture_output=True, text=True, check=True, timeout=4)
    if blocks != json.loads(after.stdout)['blockdevices']:
        raise ObservationError('Block topology changed during observation; retry')
    for device, identity in identities.items():
        target = (sysfs / 'dev/block' / device).resolve(strict=True)
        if str(target) != identity['sysfs'] or (target / 'diskseq').read_text().strip() != identity['diskseq']:
            raise ObservationError('Device replaced during observation')
    if first != (proc / 'self/mountinfo').read_text() or namespace != os.readlink(proc / 'self/ns/mnt'):
        raise ObservationError('Mounts changed during observation; retry')
    return answer


def selected(snapshot, token, mode):
    entries = snapshot['drives'] if mode == 'eject' else [
        volume for drive in snapshot['drives'] for volume in drive['volumes']]
    matches = [entry for entry in entries if entry['token'] == token]
    if len(matches) != 1:
        raise ObservationError('Selection disappeared or changed; choose again')
    return matches[0]


class EjectCoordinator:
    """Transaction contract for a future native, identity-bound exclusive lease.

    No production lease provider is shipped. Tests supply model leases only.
    A lease must block admission before inspecting users, cover all GATES,
    and keep ownership until verified completion or failure. Its unmount must
    atomically bind kernel mount identity, not resolve a reused device name.
    """
    def __init__(self, snapshot, acquire=None):
        self.snapshot = snapshot
        self.acquire = acquire

    def eject(self, token):
        drive = selected(self.snapshot(), token, 'eject')
        if self.acquire is None:
            return dict(state='blocked', reason=UNFINISHED)
        with self.acquire(drive) as lease:
            if not GATES.issubset(lease.coverage) or not lease.exclusive:
                return dict(state='blocked', reason='Incomplete exclusive media-use coverage')
            busy = lease.busy(drive['identity'])
            if busy is None or busy:
                return dict(state='blocked', reason='Target users unknown or busy')
            drive = selected(self.snapshot(), token, 'eject')
            remaining = {mount['id']: mount for part in drive['partitions'] for mount in part['mounts']}
            for mount in sorted(remaining.values(), key=lambda item: len(item['path']), reverse=True):
                current = self._same_device(drive)
                actual = {item['id']: item for part in current['partitions'] for item in part['mounts']}
                if actual != remaining or lease.busy(drive['identity']) != []:
                    return dict(state='blocked', reason='Target changed while ejecting; keep connected')
                if not lease.unmount(mount, force=False, lazy=False):
                    return dict(state='failed', reason='Unmount failed; keep connected')
                remaining.pop(mount['id'])
            current = self._same_device(drive)
            if any(part['mounts'] for part in current['partitions']) or not lease.verified_complete(drive):
                return dict(state='failed', reason='Unmount completion unproven; keep connected')
            return dict(state='safe', identity=drive['identity'])

    def _same_device(self, drive):
        matches = [item for item in self.snapshot()['drives'] if item['identity'] == drive['identity']]
        if len(matches) != 1:
            raise ObservationError('Physical device disappeared or was replaced')
        current = matches[0]
        if [(part['device'], part['size']) for part in current['partitions']] != [
                (part['device'], part['size']) for part in drive['partitions']]:
            raise ObservationError('Partition topology changed')
        return current


def main():
    try:
        if len(sys.argv) != 1:
            raise ObservationError('This helper only supports read-only inventory')
        answer = observe()
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError,
            ObservationError) as error:
        answer = dict(version=1, drives=[], error=str(error))
    print(json.dumps(answer))
    return 1 if 'error' in answer else 0


if __name__ == '__main__':
    sys.exit(main())
