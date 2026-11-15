"""Physical inventory, selection and unmount-contract tests, without USB writes."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'stage3/01-install-packages/files/mixpi-media-inventory.py'
SPEC = importlib.util.spec_from_file_location('media_inventory', HELPER)
MEDIA = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MEDIA)


def disk(name, device, size, transport, children):
    return dict(name=name, **{'maj:min': device}, type='disk', size=size,
                tran=transport, children=children, mountpoints=[])


def partition(name, device, label='Guest'):
    return dict(name=name, **{'maj:min': device}, type='part', size=4000000000,
                label=label, uuid='CLONED-UUID', mountpoints=[])


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.path_validation = mock.patch.object(MEDIA, 'validate_mount_path')
        self.path_validation.start()
        self.addCleanup(self.path_validation.stop)
        self.blocks = [
            disk('bootdisk', '179:0', 64000000000, 'mmc', [partition('root', '179:2')]),
            disk('arbitrary-a', '8:32', 64000000000, 'usb', [partition('vol-a', '8:33'), partition('vol-b', '8:34')]),
            disk('arbitrary-b', '8:80', 4000000000, 'usb', [partition('vol-c', '8:81')]),
        ]
        self.mounts = MEDIA.parse_mounts(
            '1 0 179:2 / / rw - ext4 /dev/root rw\n'
            '20 1 8:33 / /media/pi/Guest rw - exfat /dev/vol-a rw\n'
            '21 1 8:34 / /mnt/second ro - vfat /dev/vol-b ro\n'
            '22 1 8:81 / /media/pi/Guest2 rw - vfat /dev/vol-c rw\n')
        self.identities = {'8:32': dict(sysfs='/sys/devices/usb/disk-a', diskseq='50'),
                           '8:80': dict(sysfs='/sys/devices/usb/disk-b', diskseq='51')}

    def snapshot(self):
        return MEDIA.inventory(self.blocks, self.mounts, self.identities, 'boot', 'mnt:[1]')

    def test_two_physical_drives_and_all_partitions(self):
        result = self.snapshot()['drives']
        self.assertEqual(len(result), 2)
        self.assertEqual([len(drive['volumes']) for drive in result], [2, 1])
        self.assertEqual([len(drive['partitions']) for drive in result], [3, 2])

    def test_duplicate_labels_and_cloned_uuids_never_identify_selection(self):
        volumes = [volume for drive in self.snapshot()['drives'] for volume in drive['volumes']]
        self.assertEqual({volume['label'] for volume in volumes}, {'Guest'})
        self.assertEqual(len({volume['token'] for volume in volumes}), 3)
        self.assertEqual(len({volume['discriminator'] for volume in volumes}), 3)
        for volume in volumes:
            self.assertEqual(MEDIA.selected(self.snapshot(), volume['token'], 'load'), volume)
            self.assertGreater(volume['size'], 0)

    def test_excludes_entire_usb_boot_disk_including_other_partitions(self):
        self.blocks[0]['tran'] = 'usb'
        self.blocks[0]['children'].append(partition('music', '179:3'))
        self.mounts.append(dict(self.mounts[1], id=25, device='179:3', path='/media/bootmusic'))
        self.assertEqual(len(self.snapshot()['drives']), 2)

    def test_system_bind_mount_excludes_entire_disk(self):
        self.mounts.append(dict(self.mounts[1], id=25, root='/system', path='/var/lib/music'))
        self.assertEqual([drive['device'] for drive in self.snapshot()['drives']], ['8:80'])

    def test_internal_copied_export_not_a_volume(self):
        self.mounts.append(dict(self.mounts[1], id=25, device='179:2', root='/exports', path='/media/pi/Copy'))
        self.assertEqual(len(self.snapshot()['drives']), 2)

    def test_swap_excludes_whole_drive(self):
        result = MEDIA.inventory(self.blocks, self.mounts, self.identities, 'boot', 'mnt:[1]', ['8:34'])
        self.assertEqual([drive['device'] for drive in result['drives']], ['8:80'])

    def test_no_partition_table_whole_disk_volume(self):
        self.blocks[2]['children'] = []
        self.blocks[2]['label'] = 'Whole disk'
        self.mounts[-1]['device'] = '8:80'
        self.assertEqual(self.snapshot()['drives'][-1]['volumes'][0]['label'], 'Whole disk')

    def test_bind_mount_accounted_for_eject_not_load(self):
        self.mounts.append(dict(self.mounts[1], id=25, root='/Music', path='/mnt/alias'))
        drive = self.snapshot()['drives'][0]
        self.assertEqual(len(drive['volumes']), 2)
        self.assertEqual(sum(len(part['mounts']) for part in drive['partitions']), 3)

    def test_other_drive_hotplug_does_not_retarget_or_invalidate_selection(self):
        token = self.snapshot()['drives'][0]['volumes'][0]['token']
        self.identities['8:80']['diskseq'] = '99'
        self.assertEqual(MEDIA.selected(self.snapshot(), token, 'load')['mount']['device'], '8:33')

    def test_target_replacement_reusing_mount_id_label_and_uuid_invalidates(self):
        previous = self.snapshot()['drives'][0]
        self.identities['8:32']['diskseq'] = '99'
        for mode, token in [('eject', previous['token']), ('load', previous['volumes'][0]['token'])]:
            with self.assertRaises(MEDIA.ObservationError):
                MEDIA.selected(self.snapshot(), token, mode)

    def test_target_remount_or_sibling_partition_change_invalidates(self):
        token = self.snapshot()['drives'][0]['volumes'][0]['token']
        self.mounts[2]['id'] = 100
        with self.assertRaises(MEDIA.ObservationError):
            MEDIA.selected(self.snapshot(), token, 'load')

    def test_target_disappearance_never_selects_remaining_drive(self):
        token = self.snapshot()['drives'][0]['token']
        self.blocks.pop(1)
        self.mounts = [mount for mount in self.mounts if mount['device'] not in ('8:33', '8:34')]
        with self.assertRaises(MEDIA.ObservationError):
            MEDIA.selected(self.snapshot(), token, 'eject')

    def test_missing_generation_fails_closed(self):
        self.identities['8:32'].pop('diskseq')
        with self.assertRaises(MEDIA.ObservationError):
            self.snapshot()

    def test_unknown_root_ancestry_fails_closed(self):
        self.mounts[0]['device'] = '0:99'
        with self.assertRaisesRegex(MEDIA.ObservationError, 'System disk'):
            self.snapshot()

    def test_stacked_usb_fails_closed(self):
        self.blocks[1]['children'][0]['type'] = 'crypt'
        with self.assertRaisesRegex(MEDIA.ObservationError, 'Stacked'):
            self.snapshot()

    def test_overmounted_path_fails_closed(self):
        self.mounts[-1]['path'] = self.mounts[1]['path']
        with self.assertRaisesRegex(MEDIA.ObservationError, 'Overmounted'):
            self.snapshot()

    def test_covered_ancestor_cannot_publish_load_volume(self):
        self.mounts.append(dict(self.mounts[-1], id=99, path='/media/pi'))
        MEDIA.validate_mount_path.side_effect = MEDIA.ObservationError('Resolved directory differs from selected mount')
        with self.assertRaisesRegex(MEDIA.ObservationError, 'Resolved directory'):
            self.snapshot()

    def test_production_eject_reports_unfinished_gate_without_mutation(self):
        before = self.snapshot()
        for drive in before['drives']:
            result = MEDIA.EjectCoordinator(self.snapshot).eject(drive['token'])
            self.assertEqual(result['state'], 'blocked')
            self.assertIn('No unmount was attempted', result['reason'])
            self.assertIn('Cached playback is not proof', result['reason'])
        self.assertEqual(before, self.snapshot())

    def test_mount_escaping_and_malformed_input(self):
        mounts = MEDIA.parse_mounts('1 0 179:2 / / rw - ext4 root rw\n' +
            r'2 1 8:33 / /media/Guest\040Mix\134040 rw - exfat disk rw' + '\n')
        self.assertEqual(mounts[1]['path'], '/media/Guest Mix\\040')
        for text in ('', 'bad mount', '1 0 x / / rw - ext4 root rw',
                     '1 0 1:1 / / rw - ext4 root rw\n1 0 1:2 / /foo rw - vfat disk rw'):
            with self.subTest(text=text), self.assertRaises(MEDIA.ObservationError):
                MEDIA.parse_mounts(text)


class ModelLease:
    def __init__(self, state):
        self.state = state
        self.coverage = set(MEDIA.GATES)
        self.exclusive = True
        self.users = {}
        self.calls = []
        self.fail_mount = None
        self.complete = True
        self.released = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.released = True

    def busy(self, identity):
        return self.users.get(identity, [])

    def unmount(self, mount, *, force, lazy):
        self.calls.append((mount['id'], force, lazy))
        if mount['id'] == self.fail_mount:
            return False
        for drive in self.state['drives']:
            for part in drive['partitions']:
                part['mounts'] = [current for current in part['mounts'] if current['id'] != mount['id']]
        return True

    def verified_complete(self, drive):
        return self.complete


class EjectContractTests(unittest.TestCase):
    def setUp(self):
        fixture = InventoryTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.state = fixture.snapshot()
        self.target = self.state['drives'][0]
        self.lease = ModelLease(self.state)
        self.coordinator = MEDIA.EjectCoordinator(lambda: copy.deepcopy(self.state), lambda drive: self.lease)

    def eject(self):
        return self.coordinator.eject(self.target['token'])

    def test_each_missing_native_ownership_gate_prevents_any_unmount(self):
        for gate in MEDIA.GATES:
            with self.subTest(gate=gate):
                self.lease.coverage = MEDIA.GATES - {gate}
                self.assertEqual(self.eject()['state'], 'blocked')
                self.assertEqual(self.lease.calls, [])

    def test_queued_load_analysis_metadata_recording_copy_and_fallback_block_target(self):
        for user in ('pending-load', 'analyzer', 'metadata', 'recording', 'queued-copy', 'decoder', 'cache-fallback'):
            with self.subTest(user=user):
                self.lease.users[self.target['identity']] = [user]
                self.assertEqual(self.eject()['state'], 'blocked')
                self.assertEqual(self.lease.calls, [])

    def test_busy_other_drive_is_not_stopped_or_unmounted(self):
        other = self.state['drives'][1]
        before = copy.deepcopy(other)
        self.lease.users[other['identity']] = ['playing', 'copying']
        self.assertEqual(self.eject()['state'], 'safe')
        self.assertEqual(other, before)
        self.assertEqual(self.lease.calls, [(20, False, False), (21, False, False)])
        self.assertTrue(self.lease.released)

    def test_unknown_usage_or_nonexclusive_observation_blocks(self):
        self.lease.users[self.target['identity']] = None
        self.assertEqual(self.eject()['state'], 'blocked')
        self.lease.users.clear()
        self.lease.exclusive = False
        self.assertEqual(self.eject()['state'], 'blocked')
        self.assertEqual(self.lease.calls, [])

    def test_failed_second_unmount_never_signals_safe(self):
        self.lease.fail_mount = 21
        self.assertEqual(self.eject()['state'], 'failed')
        self.assertTrue(self.target['partitions'][-1]['mounts'])
        self.assertTrue(self.lease.released)

    def test_success_exit_without_verified_completion_is_not_safe(self):
        self.lease.complete = False
        self.assertEqual(self.eject()['state'], 'failed')

    def test_success_exit_while_mounts_remain_is_not_safe(self):
        self.lease.unmount = lambda mount, **flags: True
        self.assertNotEqual(self.eject()['state'], 'safe')

    def test_replacement_during_confirmation_blocks_before_unmount(self):
        original = self.coordinator.acquire
        def replace(drive):
            lease = original(drive)
            self.target['token'] = 'replacement'
            return lease
        self.coordinator.acquire = replace
        with self.assertRaises(MEDIA.ObservationError):
            self.coordinator.eject(self.target['token'])
        self.assertEqual(self.lease.calls, [])

    def test_new_mount_during_transaction_blocks_remaining_unmounts(self):
        original = self.lease.unmount
        def add_mount(mount, **flags):
            result = original(mount, **flags)
            self.target['partitions'][0]['mounts'].append(dict(mount, id=999))
            return result
        self.lease.unmount = add_mount
        self.assertEqual(self.eject()['state'], 'blocked')
        self.assertEqual(len(self.lease.calls), 1)

    def test_observation_failure_does_not_attempt_unmount(self):
        self.coordinator.snapshot = mock.Mock(side_effect=MEDIA.ObservationError('unreadable'))
        with self.assertRaises(MEDIA.ObservationError):
            self.eject()
        self.assertEqual(self.lease.calls, [])


class IntegrationGuards(unittest.TestCase):
    def test_cli_rejects_eject_arguments(self):
        result = subprocess.run(['python3', str(HELPER), 'eject', '/dev/example'],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)['drives'], [])
        self.assertIn('read-only', json.loads(result.stdout)['error'])

    def test_helper_has_no_operational_unmount_or_fd_scan_shortcut(self):
        source = HELPER.read_text()
        for forbidden in ('udisksctl', 'os.umount', 'files_in_use', 'lsof', 'fuser'):
            self.assertNotIn(forbidden, source)

    def test_recipe_installs_read_only_inventory_helper(self):
        self.assertIn('files/mixpi-media-inventory.py', (HELPER.parent.parent / '02-run.sh').read_text())


class ObservationTests(unittest.TestCase):
    def setUp(self):
        fixture = InventoryTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.blocks = fixture.blocks
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.proc = self.root / 'proc'
        self.sysfs = self.root / 'sys'
        (self.proc / 'self').mkdir(parents=True)
        (self.proc / 'self/ns').mkdir()
        (self.proc / 'self/ns/mnt').symlink_to('mnt:[1]')
        (self.proc / 'sys/kernel/random').mkdir(parents=True)
        (self.proc / 'sys/kernel/random/boot_id').write_text('boot')
        (self.proc / 'swaps').write_text('Filename Type Size Used Priority\n')
        (self.proc / 'self/mountinfo').write_text(
            '1 0 179:2 / / rw - ext4 /dev/root rw\n'
            '20 1 8:33 / /media/pi/Guest rw - exfat /dev/vol-a rw\n'
            '21 1 8:34 / /mnt/second ro - vfat /dev/vol-b ro\n'
            '22 1 8:81 / /media/pi/Guest2 rw - vfat /dev/vol-c rw\n')
        (self.sysfs / 'dev/block').mkdir(parents=True)
        for block in self.blocks:
            target = self.sysfs / 'devices' / block['name']
            target.mkdir(parents=True)
            (target / 'diskseq').write_text('50')
            (self.sysfs / 'dev/block' / block['maj:min']).symlink_to(target, target_is_directory=True)
        self.calls = 0
        self.mutate = lambda: None

    def run_lsblk(self, command, **kwargs):
        self.calls += 1
        self.assertEqual(command[0], '/usr/bin/lsblk')
        self.assertTrue(kwargs['check'])
        self.assertEqual(kwargs['timeout'], 4)
        if self.calls == 2:
            self.mutate()
        return subprocess.CompletedProcess(command, 0, json.dumps(dict(blockdevices=self.blocks)))

    def observe(self):
        return MEDIA.observe(self.proc, self.sysfs, self.run_lsblk)

    def test_stable_snapshot_includes_physical_generations(self):
        result = self.observe()
        self.assertEqual(self.calls, 2)
        self.assertEqual(len(result['drives']), 2)
        for drive in result['drives']:
            for volume in drive['volumes']:
                self.assertEqual(volume['physical']['diskseq'], '50')

    def test_replacement_between_observations_fails_closed(self):
        self.mutate = lambda: (self.sysfs / 'devices/arbitrary-a/diskseq').write_text('51')
        with self.assertRaisesRegex(MEDIA.ObservationError, 'replaced'):
            self.observe()

    def test_unmounted_partition_added_between_observations_fails_closed(self):
        self.mutate = lambda: self.blocks[1]['children'].append(partition('new-part', '8:35'))
        with self.assertRaisesRegex(MEDIA.ObservationError, 'topology changed'):
            self.observe()

    def test_mount_changed_between_observations_fails_closed(self):
        path = self.proc / 'self/mountinfo'
        self.mutate = lambda: path.write_text(path.read_text().replace('20 1', '30 1'))
        with self.assertRaisesRegex(MEDIA.ObservationError, 'Mounts changed'):
            self.observe()

    def test_unreadable_mountinfo_cannot_return_partial_inventory(self):
        (self.proc / 'self/mountinfo').unlink()
        with self.assertRaises(OSError):
            self.observe()

    def test_timeout_cannot_return_partial_inventory(self):
        self.run_lsblk = mock.Mock(side_effect=subprocess.TimeoutExpired('lsblk', 4))
        with self.assertRaises(subprocess.TimeoutExpired):
            self.observe()

    def test_namespace_change_invalidates_snapshot(self):
        def change():
            (self.proc / 'self/ns/mnt').unlink()
            (self.proc / 'self/ns/mnt').symlink_to('mnt:[2]')
        self.mutate = change
        with self.assertRaisesRegex(MEDIA.ObservationError, 'Mounts changed'):
            self.observe()


class ResolvedMountTests(unittest.TestCase):
    def setUp(self):
        self.mount = dict(id=20, device='8:33', path='/media/pi/Guest')
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.proc = Path(self.directory.name)
        (self.proc / 'self/fdinfo').mkdir(parents=True)
        self.info = self.proc / 'self/fdinfo/73'
        self.info.write_text('pos: 0\nmnt_id:\t20\n')

    def validate(self, device=(8, 33)):
        with mock.patch.object(os, 'O_PATH', 0x200000, create=True), \
                mock.patch.object(os, 'open', return_value=73) as opened, \
                mock.patch.object(os, 'fstat', return_value=SimpleNamespace(st_dev=os.makedev(*device))), \
                mock.patch.object(os, 'close') as closed:
            try:
                MEDIA.validate_mount_path(self.mount, self.proc)
            finally:
                opened.assert_called_once_with(self.mount['path'], os.O_PATH | os.O_DIRECTORY | os.O_CLOEXEC)
                closed.assert_called_once_with(73)

    def test_matching_open_directory_device_and_mount(self):
        self.validate()

    def test_covered_ancestor_resolves_other_mount(self):
        self.info.write_text('mnt_id: 21\n')
        with self.assertRaises(MEDIA.ObservationError):
            self.validate((8, 81))

    def test_same_device_different_mount_id(self):
        self.info.write_text('mnt_id: 21\n')
        with self.assertRaises(MEDIA.ObservationError):
            self.validate()

    def test_other_device_even_if_mount_id_reused(self):
        with self.assertRaises(MEDIA.ObservationError):
            self.validate((8, 81))

    def test_missing_or_duplicate_mount_id_fails_closed(self):
        for content in ('pos: 0\n', 'mnt_id: 20\nmnt_id: 20\n'):
            with self.subTest(content=content), self.assertRaises(MEDIA.ObservationError):
                self.info.write_text(content)
                self.validate()

    def test_unreadable_fdinfo_fails_closed_and_closes(self):
        self.info.unlink()
        with self.assertRaises(OSError):
            self.validate()


if __name__ == '__main__':
    unittest.main()
