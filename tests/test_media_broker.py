"""Synthetic unmount coverage: no test in this file mounts or unmounts a device."""
import copy
import array
import json
import hashlib
import importlib.util
import importlib.machinery
import os
import pwd
import signal
from pathlib import Path
import socket
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import test_media_copy_ipc as copy_ipc


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'stage3/01-install-packages/files/mixpi-mount-broker.py'
spec = importlib.util.spec_from_file_location('mount_broker', PATH)
broker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(broker)


class FakeOwner:
    connected = True

    def alive(self):
        return self.connected


class FakeDrain:
    ready = True
    cancelled = False
    crashed = False
    completed = False

    def idle(self):
        if self.crashed:
            raise broker.Refused('Native owner died')
        return self.ready

    def cancel(self):
        if self.crashed:
            raise broker.Refused('Native owner died')
        self.cancelled = True

    def complete(self):
        if self.crashed:
            raise broker.Refused('Native owner died')
        self.completed = True


class FakeOS:
    def __init__(self):
        self.disks = {'A': ['8:1', '8:2'], 'B': ['8:17']}
        self.mounts = []
        self.operations = []
        self.sequence = 100
        self.failure = None
        self.bad_path = False
        self.failed_verification = False
        self.on_unmount = lambda: None

    def snapshot(self):
        drives = {}
        for key, members in self.disks.items():
            mounted = [item for item in self.mounts if item['device'] in members]
            token = hashlib.sha256(repr((key, members, mounted)).encode()).hexdigest()
            drives[token] = dict(token=token, generation=key, members=set(members), device='disk-' + key,
                                 partitions=[dict(device=device) for device in members], volumes=[dict(label='DUPLICATE')])
        return copy.deepcopy(drives), copy.deepcopy(self.mounts)

    def token(self, key):
        return next(token for token, drive in self.snapshot()[0].items() if drive['generation'] == key)

    def verify(self, mount):
        if self.bad_path:
            raise broker.Refused('Different resolved mount')

    def mount(self, device, key):
        self.sequence += 1
        path = '/media/pi/' + device.replace(':', '-')
        self.mounts.append(dict(id=self.sequence, device=device, root='/', path=path))
        self.operations.append(('mount', device))
        return path

    def unmount(self, mount):
        self.operations.append(('unmount', mount['id']))
        if self.failure == mount['device']:
            raise OSError('EBUSY synthetic')
        if not self.failed_verification:
            self.mounts.remove(mount)
        self.on_unmount()


class BrokerBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.os = FakeOS()
        self.drains = []
        def factory(key):
            drain = FakeDrain()
            self.drains.append(drain)
            return drain
        self.service = broker.Broker(self.os, factory)
        self.owner = FakeOwner()

    def mounted(self, key='A'):
        answer = self.service.mount(self.os.token(key))
        self.assertEqual(answer['status'], 'mounted')
        return answer['token']

    def pending(self, cutoff=True):
        token = self.mounted()
        self.service.begin(token, self.owner)
        if cutoff:
            self.assertEqual(self.service.poll(token, self.owner)['status'], 'ready')
            self.assertEqual(self.service.commit(token, self.owner)['status'], 'committing')
        return token

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Real Linux socketpair and pidfd')
    def test_cancel_queued_during_initial_idle_has_no_irreversible_work(self):
        client, server = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        owner = broker.Owner(server, os.pidfd_open(os.getpid()))
        self.addCleanup(client.close)
        self.addCleanup(owner.disconnect)
        token = self.mounted()
        self.service.begin(token, owner)
        def idle():
            client.send(json.dumps(dict(op='cancel', token=token)).encode())
            return True
        self.drains[-1].idle = idle
        answer = self.service.poll(token, owner)
        self.assertEqual(len(self.os.mounts), 2)
        self.assertEqual(answer['status'], 'ready')
        request = json.loads(server.recv(8192))
        answer = self.service.cancel(request['token'], owner)
        server.send(json.dumps(answer).encode())
        self.assertEqual(json.loads(client.recv(8192))['status'], 'cancelled')
        self.assertEqual(len(self.os.mounts), 2)

    def test_normal_synthetic_multipartition_success_retains_drain(self):
        token = self.pending()
        answer = self.service.poll(token, self.owner)
        self.assertEqual(answer['status'], 'unmounted')
        self.assertTrue(answer['safe'])
        self.assertEqual(len(answer['removed']), 2)
        self.assertFalse(self.drains[-1].cancelled)
        self.assertTrue(self.drains[-1].completed)
        self.assertIsNone(answer['token'])
        with self.assertRaises(broker.Refused):
            self.service.mount(self.os.token('A'))

    def test_busy_or_unknown_native_owners_do_not_unmount(self):
        token = self.pending()
        self.drains[-1].ready = False
        self.assertEqual(self.service.poll(token, self.owner)['status'], 'busy')
        self.assertEqual(len(self.os.mounts), 2)
        self.assertFalse(any(item[0] == 'unmount' for item in self.os.operations))

    def test_success_removes_active_transaction_but_preserves_retirement(self):
        token = self.pending()
        self.assertTrue(self.service.poll(token, self.owner)['safe'])
        self.assertNotIn(token, self.service.transactions)
        self.assertIn('A', self.service.retired)
        self.mounted('B')
        with self.assertRaises(broker.Refused):
            self.service.mount(self.os.token('A'))

    def test_target_names_include_boot_identity_and_never_reuse_directories(self):
        adapter = broker.LinuxOS.__new__(broker.LinuxOS)
        physical = dict(boot_id='first-boot', namespace='mnt:[1]', sysfs='/sys/usb/disk',
                        device='8:0', diskseq='9')
        with tempfile.TemporaryDirectory(prefix='broker-target-') as temporary:
            adapter.base = Path(temporary)
            trusted = Mock(st_mode=0o40755, st_uid=0)
            with patch.object(Path, 'lstat', return_value=trusted):
                first = adapter.create_target('8:1', broker.generation(physical))
                marker = first / 'must-not-adopt'
                marker.write_text('retained')
                repeat = adapter.create_target('8:1', broker.generation(physical))
                physical['boot_id'] = 'second-boot'
                second = adapter.create_target('8:1', broker.generation(physical))
            self.assertEqual(len({first, repeat, second}), 3)
            self.assertNotEqual(first.name.rsplit('-', 1)[0], second.name.rsplit('-', 1)[0])
            self.assertEqual(marker.read_text(), 'retained')
            self.assertEqual(list(repeat.iterdir()), [])
            self.assertEqual(list(second.iterdir()), [])
            self.assertEqual(second.stat().st_mode & 0o777, 0o700)

    def test_target_creation_rejects_untrusted_parent_without_reusing_it(self):
        adapter = broker.LinuxOS.__new__(broker.LinuxOS)
        with tempfile.TemporaryDirectory(prefix='broker-target-') as temporary:
            adapter.base = Path(temporary)
            for mode, uid in ((0o120755, 0), (0o40777, 0), (0o40755, 1000)):
                with self.subTest(mode=mode, uid=uid), patch.object(
                        Path, 'lstat', return_value=Mock(st_mode=mode, st_uid=uid)):
                    with self.assertRaisesRegex(broker.Refused, 'Untrusted media parent'):
                        adapter.create_target('8:1', 'generation')
            self.assertEqual(list(adapter.base.iterdir()), [])

    def test_two_disks_duplicate_labels_do_not_cross_eject(self):
        first = self.mounted('A')
        second = self.mounted('B')
        self.assertNotEqual(first, second)
        self.service.begin(first, self.owner)
        self.service.poll(first, self.owner)
        self.service.commit(first, self.owner)
        self.assertTrue(self.service.poll(first, self.owner)['safe'])
        self.assertEqual([item['device'] for item in self.os.mounts], ['8:17'])

    def test_stale_generation_and_system_or_arbitrary_targets_rejected(self):
        token = self.mounted()
        self.os.disks['REPLACEMENT'] = self.os.disks.pop('A')
        for target in (token, '/', '/dev/sda', 'disk-system', ''):
            with self.subTest(target=target), self.assertRaises(broker.Refused):
                self.service.begin(target, self.owner)

    def test_unmanaged_mount_never_adopted_even_after_restart(self):
        token = self.mounted()
        restarted = broker.Broker(self.os, lambda key: FakeDrain())
        with self.assertRaises(broker.Refused):
            restarted.begin(token, self.owner)
        self.assertFalse(restarted.owned)

    def test_alias_overmount_nested_and_changed_resolved_path_rejected(self):
        self.mounted()
        baseline = copy.deepcopy(self.os.mounts)
        variants = [dict(baseline[0], id=999, path='/media/alias'),
                    dict(baseline[0], id=999, device='0:9'),
                    dict(baseline[0], id=999, device='0:9', path=baseline[0]['path'] + '/nested')]
        for alias in variants:
            self.os.mounts = copy.deepcopy(baseline) + [alias]
            with self.subTest(alias=alias), self.assertRaises(broker.Refused):
                self.service.begin(self.os.token('A'), self.owner)
        self.os.mounts = baseline
        self.os.bad_path = True
        with self.assertRaises(broker.Refused):
            self.service.begin(self.os.token('A'), self.owner)

    def test_cancel_releases_only_unchanged_selected_drain(self):
        token = self.pending(cutoff=False)
        with self.assertRaises(broker.Refused):
            self.service.cancel(token, FakeOwner())
        self.assertEqual(self.service.cancel(token, self.owner)['status'], 'cancelled')
        self.assertTrue(self.drains[-1].cancelled)
        self.assertEqual(len(self.os.mounts), 2)

    def test_cutoff_requires_ready_owner_and_token_and_is_not_an_unmount(self):
        token = self.pending(cutoff=False)
        with self.assertRaises(broker.Refused):
            self.service.commit(token, self.owner)
        self.assertEqual(self.service.poll(token, self.owner)['status'], 'ready')
        for wrong_token, wrong_owner in ((token, FakeOwner()), ('f' * 64, self.owner)):
            with self.assertRaises(broker.Refused):
                self.service.cancel(wrong_token, wrong_owner)
            with self.assertRaises(broker.Refused):
                self.service.commit(wrong_token, wrong_owner)
        self.assertEqual(self.service.commit(token, self.owner)['status'], 'committing')
        self.assertEqual(len(self.os.mounts), 2)
        self.assertEqual(self.service.cancel(token, self.owner)['status'], 'too-late')
        self.assertFalse(self.drains[-1].cancelled)
        self.assertTrue(self.service.poll(token, self.owner)['safe'])

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Real Linux socketpair and pidfd')
    def test_disconnect_after_cutoff_ack_retains_drain_without_unmount(self):
        client, server = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        owner = broker.Owner(server, os.pidfd_open(os.getpid()))
        self.addCleanup(owner.disconnect)
        self.addCleanup(client.close)
        token = self.mounted()
        self.service.begin(token, owner)
        self.service.poll(token, owner)
        server.send(json.dumps(self.service.commit(token, owner)).encode())
        self.assertEqual(json.loads(client.recv(8192))['status'], 'committing')
        client.close()
        with self.assertRaises(broker.Refused):
            self.service.poll(token, owner)
        self.assertEqual(len(self.os.mounts), 2)
        self.assertFalse(self.drains[-1].cancelled)

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Real Linux socketpair and pidfd')
    def test_queued_cancel_after_cutoff_is_explicitly_too_late(self):
        client, server = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        owner = broker.Owner(server, os.pidfd_open(os.getpid()))
        self.addCleanup(owner.disconnect)
        self.addCleanup(client.close)
        token = self.mounted()
        self.service.begin(token, owner)
        self.service.poll(token, owner)
        server.send(json.dumps(self.service.commit(token, owner)).encode())
        self.assertEqual(json.loads(client.recv(8192))['status'], 'committing')
        client.send(json.dumps(dict(op='cancel', token=token)).encode())
        request = json.loads(server.recv(8192))
        server.send(json.dumps(self.service.cancel(request['token'], owner)).encode())
        self.assertEqual(json.loads(client.recv(8192))['status'], 'too-late')
        self.assertEqual(len(self.os.mounts), 2)
        self.assertTrue(self.service.poll(token, owner)['safe'])

    def test_partial_failure_retains_admission_and_reports_removed_subset(self):
        token = self.pending()
        self.os.failure = '8:2'
        answer = self.service.poll(token, self.owner)
        self.assertFalse(answer['safe'])
        self.assertEqual(answer['status'], 'quarantined')
        self.assertEqual(len(answer['removed']), 1)
        self.assertFalse(self.drains[-1].cancelled)
        self.assertEqual(self.service.cancel(token, self.owner)['status'], 'too-late')

    def test_failed_kernel_completion_never_claims_removal(self):
        token = self.pending()
        self.os.failed_verification = True
        answer = self.service.poll(token, self.owner)
        self.assertFalse(answer['safe'])
        self.assertEqual(answer['removed'], [])
        self.assertEqual(len(self.os.mounts), 2)

    def test_peer_death_before_and_during_unmount_preserves_drain(self):
        token = self.pending()
        self.owner.connected = False
        with self.assertRaises(broker.Refused):
            self.service.poll(token, self.owner)
        self.owner.connected = True
        self.os.on_unmount = lambda: setattr(self.owner, 'connected', False)
        answer = self.service.poll(token, self.owner)
        self.assertFalse(answer['safe'])
        self.assertFalse(self.drains[-1].cancelled)
        self.assertEqual(len(answer['removed']), 1)

    def test_native_crash_and_hotplug_fail_closed(self):
        token = self.pending()
        self.drains[-1].crashed = True
        with self.assertRaises(broker.Refused):
            self.service.poll(token, self.owner)
        self.drains[-1].crashed = False
        self.os.disks.pop('A')
        with self.assertRaises(broker.Refused):
            self.service.poll(token, self.owner)

    def test_unmount_backend_uses_only_zero_flags_and_verified_target(self):
        adapter = broker.LinuxOS.__new__(broker.LinuxOS)
        adapter.libc = Mock()
        adapter.libc.umount2.return_value = 0
        adapter.verify = Mock()
        mount = dict(path='/media/pi/synthetic-only')
        adapter.unmount(mount)
        adapter.verify.assert_called_once_with(mount)
        adapter.libc.umount2.assert_called_once_with(b'/media/pi/synthetic-only', 0)
        adapter.verify.side_effect = broker.Refused('Wrong mount')
        with self.assertRaises(broker.Refused):
            adapter.unmount(mount)
        self.assertEqual(adapter.libc.umount2.call_count, 1)

    def test_capability_absent_fails_before_any_backend(self):
        with patch.object(broker.os, 'lstat', side_effect=FileNotFoundError), patch.object(broker, 'LinuxOS') as adapter:
            with self.assertRaises(FileNotFoundError):
                broker.checked_profile(1000)
            adapter.assert_not_called()

    def test_production_adapter_rejects_other_namespace_before_discovery(self):
        adapter = broker.LinuxOS.__new__(broker.LinuxOS)
        with patch.object(broker.os, 'readlink', side_effect=['mnt:[2]', 'mnt:[1]']):
            with self.assertRaisesRegex(broker.Refused, 'host mount namespace'):
                adapter.snapshot()

    def test_image_profile_not_enabled_by_default_or_self_approved(self):
        recipe = (ROOT / 'stage3/02-desktop/06-run.sh').read_text()
        self.assertIn('${MIXPI_CONTROLLED_MEDIA:-0}', recipe)
        self.assertNotIn('eject-reviewed', recipe)
        self.assertIn('systemctl mask udisks2.service', recipe)
        self.assertIn('gpasswd -d pi sudo', recipe)
        self.assertIn('chown root:root /media/pi', recipe)
        self.assertTrue(os.access(ROOT / 'stage3/02-desktop/06-run.sh', os.X_OK))
        subprocess.run(['bash', '-n', str(ROOT / 'stage3/02-desktop/06-run.sh')], check=True)

    def test_actual_image_recipe_in_synthetic_rootfs_never_creates_review_gate(self):
        for profile in ('0', '1'):
            with self.subTest(profile=profile), tempfile.TemporaryDirectory(prefix='broker-image-') as temporary:
                root = Path(temporary)
                for directory in ('opt/mixpi-skin-tools', 'usr/local/bin', 'etc/systemd/system',
                                  'etc/sysctl.d', 'etc/sudoers.d'):
                    (root / directory).mkdir(parents=True, exist_ok=True)
                environment = dict(os.environ, ROOTFS_DIR=str(root), MIXPI_CONTROLLED_MEDIA=profile)
                command = 'on_chroot() { cat > "$ROOTFS_DIR/synthetic-chroot-commands"; }; export -f on_chroot; ./06-run.sh'
                subprocess.run(['bash', '-eu', '-c', command], cwd=ROOT / 'stage3/02-desktop', env=environment, check=True)
                self.assertTrue((root / 'opt/mixpi-skin-tools/mixpi-mount-broker.py').is_file())
                self.assertTrue((root / 'usr/local/bin/mixpi-mount-control').stat().st_mode & 0o111)
                self.assertFalse((root / 'etc/mixpi/eject-reviewed').exists())
                self.assertEqual((root / 'etc/mixpi/controlled-media').exists(), profile == '1')
                if profile == '1':
                    self.assertNotIn('NOPASSWD: ALL', (root / 'etc/sudoers.d/010_pi-nopasswd').read_text())

    @unittest.skipUnless(shutil.which('c++'), 'C++ compiler required')
    def test_actual_registry_retirement_preserves_other_and_unknown_admission(self):
        source = '''#include "registry.h"
#include <cassert>
int main() {
    using namespace mixxx::media;
    MediaUseRegistry registry;
    auto lease = registry.acquire({"A", "source", {}}, Producer::Copy);
    auto drain = registry.beginDrain("A");
    assert(!drain.retire());
    assert(!registry.acquire({}, Producer::Browser));
    lease.reset();
    assert(drain.retire());
    assert(!registry.acquire({"A", "source", {}}, Producer::Load));
    assert(!registry.beginDrain("A"));
    assert(registry.acquire({"B", "source", {}}, Producer::Load));
    assert(registry.acquire({}, Producer::Browser));
}
'''
        with tempfile.TemporaryDirectory(prefix='broker-registry-') as temporary:
            root = Path(temporary)
            (root / 'registry.h').write_text(copy_ipc.added_header(copy_ipc.PATCH, 'src/library/media/mediauseregistry.h'))
            (root / 'test.cpp').write_text(source)
            subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror', str(root / 'test.cpp'), '-o', str(root / 'test')], check=True)
            subprocess.run([str(root / 'test')], check=True)


@unittest.skipUnless(sys.platform.startswith('linux'), 'Linux credential/pidfd transport required')
class NativeDrainTransportTests(unittest.TestCase):
    setUpClass = classmethod(copy_ipc.NativeCopyIPC.setUpClass.__func__)
    tearDownClass = classmethod(copy_ipc.NativeCopyIPC.tearDownClass.__func__)
    setUp = copy_ipc.NativeCopyIPC.setUp
    tearDown = copy_ipc.NativeCopyIPC.tearDown
    def connect(self):
        client = copy_ipc.NativeCopyIPC.connect(self)
        if os.getuid() == 0:
            descriptor = os.open('/proc/self/ns/mnt', os.O_RDONLY)
            try:
                client.sendmsg([b'NAMESPACE'], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', [descriptor]))])
                self.assertEqual(client.recv(64), b'OK')
            finally:
                os.close(descriptor)
        return client
    request = copy_ipc.NativeCopyIPC.request
    begin = copy_ipc.NativeCopyIPC.begin

    @unittest.skipIf(os.getuid() == 0, 'Non-root authentication case')
    def test_unprivileged_drain_cannot_close_admission(self):
        self.assertEqual(self.request(self.connect(), 'DRAIN\nA'), 'DENIED')
        self.assertTrue(self.begin(self.connect()).startswith('OK'))

    @unittest.skipUnless(os.getuid() == 0, 'Run explicitly as root in Linux scratch for real root credentials')
    def test_root_busy_finish_cancel_and_other_generation(self):
        producer = self.connect()
        self.assertTrue(self.begin(producer).startswith('OK'))
        drain = self.connect()
        self.assertEqual(self.request(drain, 'DRAIN\nA'), 'BUSY')
        self.assertEqual(self.request(self.connect(), f'BEGIN\nR{self.root}/source'), 'DENIED')
        other = self.connect()
        self.assertTrue(self.request(other, f'BEGIN\nR{self.root}/other').startswith('OK'))
        self.assertEqual(self.request(producer, 'FINISH'), 'OK')
        self.assertEqual(self.request(drain, 'DRAIN_STATUS'), 'IDLE')
        self.assertEqual(self.request(drain, 'DRAIN_CANCEL'), 'OK')
        self.assertTrue(self.begin(self.connect()).startswith('OK'))

    @unittest.skipUnless(os.getuid() == 0, 'Run explicitly as root in Linux scratch for real root credentials')
    def test_broker_process_death_retains_generation_drain(self):
        code = 'import os,sys; from test_media_broker import broker; drain=broker.NativeDrain(os.getuid(), "A", endpoint=sys.argv[1]); assert drain.idle()'
        subprocess.run([sys.executable, '-c', code, str(self.root / 'ipc/control')], check=True)
        self.assertEqual(self.request(self.connect(), f'BEGIN\nR{self.root}/source'), 'DENIED')

    @unittest.skipUnless(os.getuid() == 0, 'Explicit Linux scratch root-credential integration')
    def test_python_broker_with_actual_native_drain_and_synthetic_unmount(self):
        adapter = FakeOS()
        service = broker.Broker(adapter, lambda key: broker.NativeDrain(os.getuid(), key, endpoint=str(self.root / 'ipc/control')))
        token = service.mount(adapter.token('A'))['token']
        producer = self.connect()
        self.assertTrue(self.begin(producer).startswith('OK'))
        owner = FakeOwner()
        service.begin(token, owner)
        self.assertEqual(service.poll(token, owner)['status'], 'busy')
        self.assertEqual(self.request(producer, 'FINISH'), 'OK')
        self.assertEqual(service.poll(token, owner)['status'], 'ready')
        self.assertEqual(service.commit(token, owner)['status'], 'committing')
        answer = service.poll(token, owner)
        self.assertTrue(answer['safe'])
        self.assertEqual(len(answer['removed']), 2)
        self.assertEqual(self.request(self.connect(), f'BEGIN\nR{self.root}/source'), 'DENIED')
        for transaction in service.transactions.values():
            transaction['drain'].close()


@unittest.skipUnless(sys.platform.startswith('linux') and os.getuid() == 0,
                     'Explicit root client and non-root pi scratch server')
class CrossUIDDrainTests(unittest.TestCase):
    setUpClass = classmethod(copy_ipc.NativeCopyIPC.setUpClass.__func__)
    tearDownClass = classmethod(copy_ipc.NativeCopyIPC.tearDownClass.__func__)
    tearDown = copy_ipc.NativeCopyIPC.tearDown

    def setUp(self):
        account = pwd.getpwnam('pi')
        self.uid = account.pw_uid
        self.assertNotEqual(self.uid, 0)
        os.chmod(self.build.name, 0o755)
        self.temporary = tempfile.TemporaryDirectory(prefix='cross-uid-', dir='/home/pi')
        self.root = Path(self.temporary.name)
        os.chown(self.root, self.uid, account.pw_gid)
        for name in ('source', 'destination', 'other'):
            (self.root / name).mkdir()
            os.chown(self.root / name, self.uid, account.pw_gid)
        self.server = subprocess.Popen([str(self.executable), str(self.root)],
                user=self.uid, group=account.pw_gid, extra_groups=[],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        self.assertEqual(self.server.stdout.readline().strip(), 'READY')

    def test_actual_root_broker_nonroot_native(self):
        self.assertEqual((self.root / 'ipc').stat().st_uid, self.uid)
        drain = broker.NativeDrain(self.uid, 'A', endpoint=str(self.root / 'ipc/control'))
        self.addCleanup(drain.close)
        self.assertTrue(drain.idle())
        drain.cancel()

    def connection(self):
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        connection.settimeout(3)
        connection.connect(str(self.root / 'ipc/control'))
        self.addCleanup(connection.close)
        return connection

    def proof(self, connection, descriptors, message=b'NAMESPACE'):
        rights = [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', descriptors))] if descriptors else []
        connection.sendmsg([message], rights)
        return connection.recv(64)

    def test_namespace_descriptor_denials_and_cleanup(self):
        baseline = len(list(Path(f'/proc/{self.server.pid}/fd').iterdir()))
        namespace = os.open('/proc/self/ns/mnt', os.O_RDONLY)
        regular = os.open(self.root / 'source', os.O_RDONLY)
        user_namespace = os.open('/proc/self/ns/user', os.O_RDONLY)
        try:
            for descriptors, message in (([], b'NAMESPACE'), ([regular], b'NAMESPACE'),
                    ([user_namespace], b'NAMESPACE'), ([namespace] * 2, b'NAMESPACE'),
                    ([namespace] * 32, b'NAMESPACE'), ([namespace], b'x' * 17000),
                    ([namespace], b'DRAIN\nA')):
                with self.subTest(count=len(descriptors), message=message[:12]):
                    connection = self.connection()
                    response = self.proof(connection, descriptors, message)
                    self.assertIn(response, (b'DENIED', b''))
                    connection.close()
            connection = self.connection()
            self.assertEqual(self.proof(connection, [namespace]), b'OK')
            self.assertEqual(self.proof(connection, [namespace], b'DRAIN\nA'), b'DENIED')
            connection.close()
        finally:
            for descriptor in (namespace, regular, user_namespace):
                os.close(descriptor)
        deadline = copy_ipc.time.monotonic() + 3
        while len(list(Path(f'/proc/{self.server.pid}/fd').iterdir())) != baseline:
            self.assertLess(copy_ipc.time.monotonic(), deadline)
            copy_ipc.time.sleep(0.01)

    def test_root_cannot_use_helper_begin_even_with_valid_namespace(self):
        connection = self.connection()
        namespace = os.open('/proc/self/ns/mnt', os.O_RDONLY)
        try:
            self.assertEqual(self.proof(connection, [namespace]), b'OK')
        finally:
            os.close(namespace)
        connection.sendall(f'BEGIN\nR{self.root}/source'.encode())
        self.assertEqual(connection.recv(64), b'DENIED')

    def test_disconnect_quarantines_native_drain(self):
        drain = broker.NativeDrain(self.uid, 'A', endpoint=str(self.root / 'ipc/control'))
        drain.close()
        with self.assertRaises(broker.Refused):
            broker.NativeDrain(self.uid, 'A', endpoint=str(self.root / 'ipc/control'))

    def test_different_mount_namespace_proof_is_denied(self):
        code = ('import ctypes,sys; libc=ctypes.CDLL(None,use_errno=True); '
                'result=libc.unshare(0x20000); print(result,flush=True); sys.stdin.read()')
        child = subprocess.Popen([sys.executable, '-c', code], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(), '0')
            descriptor = os.open(f'/proc/{child.pid}/ns/mnt', os.O_RDONLY)
            try:
                self.assertEqual(self.proof(self.connection(), [descriptor]), b'DENIED')
            finally:
                os.close(descriptor)
        finally:
            child.stdin.close()
            child.wait(timeout=3)
            child.stdout.close()

    def test_failed_native_drain_closes_client_descriptors(self):
        drain = broker.NativeDrain(self.uid, 'A', endpoint=str(self.root / 'ipc/control'))
        self.addCleanup(drain.close)
        baseline = len(list(Path('/proc/self/fd').iterdir()))
        for attempt in range(5):
            with self.assertRaises(broker.Refused):
                broker.NativeDrain(self.uid, 'A', endpoint=str(self.root / 'ipc/control'))
        self.assertEqual(len(list(Path('/proc/self/fd').iterdir())), baseline)
        drain.cancel()

    def test_restart_with_live_session_guard_denies_cross_uid_drain(self):
        import fcntl
        guard = os.open(self.root / 'ipc/sessions.lock', os.O_RDWR)
        try:
            fcntl.flock(guard, fcntl.LOCK_SH)
            self.server.stdin.close()
            self.server.wait(timeout=3)
            self.server.stdout.close()
            account = pwd.getpwnam('pi')
            self.server = subprocess.Popen([str(self.executable), str(self.root)],
                    user=self.uid, group=account.pw_gid, extra_groups=[],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
            self.assertEqual(self.server.stdout.readline().strip(), 'READY')
            with self.assertRaises(broker.Refused):
                broker.NativeDrain(self.uid, 'A', endpoint=str(self.root / 'ipc/control'))
        finally:
            os.close(guard)
        deadline = copy_ipc.time.monotonic() + 3
        while True:
            try:
                drain = broker.NativeDrain(self.uid, 'A', endpoint=str(self.root / 'ipc/control'))
                drain.cancel()
                break
            except broker.Refused:
                self.assertLess(copy_ipc.time.monotonic(), deadline)
                copy_ipc.time.sleep(0.01)

    def test_cross_uid_broker_synthetic_partition_completion(self):
        adapter = FakeOS()
        service = broker.Broker(adapter, lambda key: broker.NativeDrain(self.uid, key,
                                endpoint=str(self.root / 'ipc/control')))
        token = service.mount(adapter.token('A'))['token']
        owner = FakeOwner()
        service.begin(token, owner)
        self.assertEqual(service.poll(token, owner)['status'], 'ready')
        self.assertEqual(len(adapter.mounts), 2)
        self.assertEqual(service.commit(token, owner)['status'], 'committing')
        answer = service.poll(token, owner)
        self.assertTrue(answer['safe'])
        self.assertEqual(len(answer['removed']), 2)
        self.assertNotIn(token, service.transactions)


class BrokerCLITests(unittest.TestCase):
    def exercise(self, interrupt_status=None, timeout=False):
        loader = importlib.machinery.SourceFileLoader('broker_cli_test',
                        str(ROOT / 'stage3/02-desktop/files/bin/mixpi-mount-control'))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        cli = importlib.util.module_from_spec(spec)
        loader.exec_module(cli)
        connection = Mock()
        operations = []
        handler = None
        def install(signum, callback):
            nonlocal handler
            handler = callback
            return signal.SIG_DFL
        def send(payload):
            operations.append(json.loads(payload)['op'])
        def receive(size):
            operation = operations[-1]
            status = {'eject': 'draining', 'cancel': 'cancelled', 'commit': 'committing',
                      'poll': 'unmounted' if 'commit' in operations else 'ready'}[operation]
            if timeout and operation == 'poll':
                raise TimeoutError('synthetic blocked response')
            if status == interrupt_status:
                handler(signal.SIGINT, None)
            return json.dumps(dict(status=status, safe=status == 'unmounted')).encode()
        connection.sendall.side_effect = send
        connection.recv.side_effect = receive
        with patch.object(cli.socket, 'socket', return_value=connection), \
                patch.object(cli.signal, 'signal', side_effect=install), \
                patch.object(sys, 'argv', ['mixpi-mount-control', 'eject', 'a' * 64]), \
                patch('builtins.print'):
            result = cli.main()
        return result, operations

    def test_interrupt_during_prepare_waits_for_cancel_ack(self):
        self.assertEqual(self.exercise('ready'), (0, ['eject', 'poll', 'cancel']))

    def test_interrupt_after_commit_does_not_promise_cancellation(self):
        self.assertEqual(self.exercise('committing'), (0, ['eject', 'poll', 'commit', 'poll']))

    def test_timeout_is_unknown_not_cancellation(self):
        self.assertEqual(self.exercise(timeout=True), (1, ['eject', 'poll']))


if __name__ == '__main__':
    unittest.main()
