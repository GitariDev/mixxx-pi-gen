"""Offline fixtures only: synthetic ownership/chroot, never a qualified image."""

import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('controlled_profile', ROOT / 'tools/performance/check-controlled-media.py')
profile = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(profile)


class ControlledProfileTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'rootfs'
        for directory in ('opt/mixpi-skin-tools', 'usr/local/bin', 'etc/systemd/system',
                          'etc/sysctl.d', 'etc/sudoers.d', 'media/pi', 'run', 'usr/bin'):
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        command = 'on_chroot() { cat > "$ROOTFS_DIR/fixture-chroot-commands"; }; export -f on_chroot; ./06-run.sh'
        subprocess.run(['bash', '-eu', '-c', command], cwd=ROOT / 'stage3/02-desktop',
                       env=dict(os.environ, ROOTFS_DIR=str(self.root), MIXPI_CONTROLLED_MEDIA='1'), check=True)
        self.write('/opt/mixpi-skin-tools/mixpi-media-inventory.py', (ROOT / profile.INSTALLED['/opt/mixpi-skin-tools/mixpi-media-inventory.py']).read_text())
        self.write('/etc/passwd', 'root:x:0:0:root:/root:/bin/bash\npi:x:1000:1000:pi:/home/pi:/bin/bash\n')
        self.write('/etc/group', 'root:x:0:\npi:x:1000:\nsudo:x:27:\ndisk:x:6:\n')
        self.write('/etc/sudoers', 'root ALL=(ALL:ALL) ALL\n@includedir /etc/sudoers.d\n')
        self.write('/etc/fstab', 'PARTUUID=fixture / ext4 defaults 0 1\n')
        self.write('/usr/bin/mount', 'fixture binary, never executed\n', 0o755)
        self.write('/var/lib/dpkg/statoverride', 'root root 0755 /bin/mount\n')
        self.write('/var/lib/dpkg/info/mount.list', '/bin/mount\n')
        (self.root / 'bin').symlink_to('usr/bin')
        (self.root / 'etc/systemd/system/udisks2.service').symlink_to('/dev/null')
        enabled = self.root / 'etc/systemd/system/multi-user.target.wants'
        enabled.mkdir()
        (enabled / 'mixpi-mount-broker.service').symlink_to('../mixpi-mount-broker.service')
        self.real_lstat = Path.lstat
        self.nonroot = set()

        def synthetic_ownership(path, *args, **kwargs):
            info = self.real_lstat(path, *args, **kwargs)
            if path == self.root or self.root in path.parents:
                fields = list(info)
                fields[4] = 1000 if path in self.nonroot else 0
                fields[5] = 0
                return os.stat_result(fields)
            return info

        self.addCleanup(patch.stopall)
        patch.object(Path, 'lstat', synthetic_ownership).start()

    def write(self, name, text, mode=0o644):
        path = self.root / name.lstrip('/')
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            path.chmod(0o644)
        path.write_text(text)
        path.chmod(mode)
        return path

    def check(self, receipt=None):
        return profile.Checker(self.root).run(receipt)

    def finding(self, report, path, status):
        return any(item['path'] == path and item['status'] == status for item in report['findings'])

    def test_known_recipe_fixture_is_not_actual_image_acceptance(self):
        result = self.check()
        self.assertFalse(any(item['status'] == 'FAIL' for item in result['findings']), result)
        self.assertEqual(result['actual_image_qualification'], 'UNVERIFIED')
        self.assertFalse(result['safe_to_eject'])
        self.assertEqual(result['candidate'], 'UNVERIFIED')
        self.assertTrue(self.finding(result, '/etc/mixpi/eject-reviewed', 'PASS'))

    def test_missing_and_stale_installed_policy(self):
        path = self.root / 'etc/polkit-1/rules.d/49-mixpi-controlled-media.rules'
        path.unlink()
        self.assertTrue(self.finding(self.check(), '/' + str(path.relative_to(self.root)), 'UNVERIFIED'))
        path.write_text('polkit.addRule(function() { return polkit.Result.YES; });')
        self.assertTrue(self.finding(self.check(), '/' + str(path.relative_to(self.root)), 'FAIL'))

    def test_relative_escape_absolute_link_and_cycle_never_read_host(self):
        sentinel = Path(self.temporary.name) / 'secret'
        sentinel.write_text('DO-NOT-OUTPUT-SECRET')
        gate = self.root / 'etc/mixpi/controlled-media'
        for target in ('../../../secret', str(sentinel), 'controlled-media'):
            with self.subTest(target=target):
                gate.unlink()
                gate.symlink_to(target)
                result = self.check()
                self.assertTrue(self.finding(result, '/etc/mixpi/controlled-media', 'UNVERIFIED'))
                self.assertNotIn('DO-NOT-OUTPUT-SECRET', json.dumps(result))

    def test_unreadable_and_special_required_evidence(self):
        gate = self.root / 'etc/mixpi/controlled-media'
        gate.chmod(0)
        self.assertTrue(self.finding(self.check(), '/etc/mixpi/controlled-media', 'UNVERIFIED'))
        gate.unlink()
        os.mkfifo(gate)
        self.assertTrue(self.finding(self.check(), '/etc/mixpi/controlled-media', 'UNVERIFIED'))

    def test_merged_usr_and_package_spelling_both_checked(self):
        self.write('/var/lib/dpkg/statoverride', 'root root 0755 /usr/bin/mount\n')
        report = self.check()
        self.assertFalse(self.finding(report, '/bin/mount', 'FAIL'))
        self.assertTrue(self.finding(report, '/var/lib/dpkg/info/mount.list', 'UNVERIFIED'))
        self.write('/var/lib/dpkg/statoverride', 'root root 0755 /bin/mount\nroot root 4755 /usr/bin/mount\n')
        self.assertTrue(self.finding(self.check(), '/bin/mount', 'FAIL'))

    def test_privileged_helper_capability_and_xattr_failure(self):
        self.write('/usr/bin/mount', 'fixture', 0o4755)
        self.write('/usr/bin/unknown-helper', 'fixture', 0o2755)
        with patch.object(profile.sys, 'platform', 'linux'), patch.object(profile.os, 'listxattr', return_value=['security.capability'], create=True):
            result = self.check()
        self.assertTrue(self.finding(result, '/bin/mount', 'FAIL'))
        self.assertTrue(self.finding(result, '/usr/bin/unknown-helper', 'UNVERIFIED'))
        with patch.object(profile.sys, 'platform', 'linux'), patch.object(profile.os, 'listxattr', side_effect=PermissionError, create=True):
            self.assertTrue(self.finding(self.check(), '/usr/bin/mount', 'UNVERIFIED'))

    def test_primary_privileged_group_and_broad_sudo(self):
        self.write('/etc/passwd', 'root:x:0:0:root:/root:/bin/bash\npi:x:1000:6:pi:/home/pi:/bin/bash\n')
        self.write('/etc/sudoers.d/010_pi-nopasswd', 'pi ALL=(ALL) NOPASSWD: ALL\n')
        result = self.check()
        self.assertTrue(self.finding(result, '/etc/group', 'FAIL'))
        self.assertTrue(self.finding(result, '/etc/sudoers.d/010_pi-nopasswd', 'FAIL'))

    def test_alias_dropin_polkit_order_and_custom_mount(self):
        self.write('/usr/lib/systemd/system/other-owner.service', '[Service]\nExecStart=/usr/bin/udisksd\n')
        self.write('/etc/systemd/system/mixpi-mount-broker.service.d/override.conf', '[Service]\nPrivateMounts=yes\n')
        self.write('/etc/polkit-1/rules.d/00-grant.rules', 'return YES;')
        self.write('/usr/share/polkit-1/rules.d/00-grant.rules', 'return YES;')
        self.write('/etc/sysctl.d/99-userns.conf', 'user.max_user_namespaces=100\n')
        self.write('/etc/fstab', '/dev/sda1 /media/music vfat defaults 0 0\n')
        result = self.check()
        for path in ('/usr/lib/systemd/system/other-owner.service', '/etc/systemd/system/mixpi-mount-broker.service.d/override.conf', '/etc/sysctl.d/99-userns.conf', '/etc/fstab:1'):
            self.assertTrue(self.finding(result, path, 'UNVERIFIED'))
        self.assertEqual(result['polkit_order'][:2], ['/etc/polkit-1/rules.d/00-grant.rules', '/usr/share/polkit-1/rules.d/00-grant.rules'])

    def test_writable_parent_and_nonroot_code(self):
        (self.root / 'opt/mixpi-skin-tools').chmod(0o777)
        self.nonroot.add(self.root / 'usr/local/bin/mixpi-mount-control')
        result = self.check()
        self.assertTrue(self.finding(result, '/opt/mixpi-skin-tools', 'FAIL'))
        self.assertTrue(self.finding(result, '/usr/local/bin/mixpi-mount-control', 'FAIL'))

    def test_candidate_missing_stale_and_matching_attestation(self):
        receipt = Path(self.temporary.name) / 'receipt.json'
        self.assertEqual(self.check(receipt)['candidate'], 'UNVERIFIED')
        original = self.check()
        value = {key: original[key] for key in ('source_sha256', 'rootfs_evidence_sha256')}
        value.update(build_id='synthetic-only', image_sha256='a' * 64)
        receipt.write_text(json.dumps(value))
        matched = self.check(receipt)
        self.assertEqual(matched['candidate'], 'MATCHED_ATTESTATION_ONLY')
        self.assertEqual(matched['actual_image_qualification'], 'UNVERIFIED')
        self.write('/etc/mixpi/controlled-media', 'v2\n')
        self.assertEqual(self.check(receipt)['candidate'], 'STALE_OR_MISMATCHED')

    def test_missing_root_and_live_root_refused(self):
        for root in ('/', '/tmp/..', self.root / 'missing'):
            result = profile.Checker(root).run()
            self.assertEqual(result['actual_image_qualification'], 'UNVERIFIED')
            self.assertFalse(result['safe_to_eject'])

    def test_holdout_alternate_service_alias_and_enabled_target(self):
        alias = self.root / 'etc/systemd/system/alternate.service'
        alias.symlink_to('mixpi-mount-broker.service')
        enabled = self.root / 'etc/systemd/system/multi-user.target.wants/mixpi-mount-broker.service'
        enabled.unlink()
        enabled.symlink_to('../udisks2.service')
        result = self.check()
        self.assertTrue(self.finding(result, '/etc/systemd/system/alternate.service', 'UNVERIFIED'))
        self.assertTrue(self.finding(result, '/' + str(enabled.relative_to(self.root)), 'UNVERIFIED'))

    def test_shadow_and_private_key_contents_never_read(self):
        self.write('/etc/shadow', 'SENSITIVE-SHADOW')
        self.write('/root/.ssh/id_ed25519', 'SENSITIVE-PRIVATE-KEY')
        real_read = Path.read_bytes

        def guarded_read(path):
            self.assertNotIn(path.name, ('shadow', 'id_ed25519'))
            return real_read(path)

        with patch.object(Path, 'read_bytes', guarded_read):
            report = self.check()
        self.assertNotIn('SENSITIVE-', json.dumps(report))

    def test_in_root_capability_alias_cannot_satisfy_broker_lstat_gate(self):
        gate = self.root / 'etc/mixpi/controlled-media'
        gate.rename(gate.with_name('saved-capability'))
        gate.symlink_to('saved-capability')
        self.assertTrue(self.finding(self.check(), '/etc/mixpi/controlled-media', 'FAIL'))

    def test_gate_under_aliased_parent_is_not_reported_absent(self):
        self.write('/etc/mixpi/eject-reviewed', 'v1\n')
        directory = self.root / 'etc/mixpi'
        directory.rename(directory.with_name('mixpi-saved'))
        directory.symlink_to('mixpi-saved')
        report = self.check()
        self.assertFalse(self.finding(report, '/etc/mixpi/eject-reviewed', 'PASS'))
        self.assertTrue(self.finding(report, '/etc/mixpi/eject-reviewed', 'UNVERIFIED'))

    def test_named_gate_probe_does_not_depend_on_directory_inventory(self):
        self.write('/etc/mixpi/eject-reviewed', 'v1\n')
        (self.root / 'etc/mixpi').chmod(0o111)
        self.addCleanup((self.root / 'etc/mixpi').chmod, 0o755)
        checker = profile.Checker(self.root)
        with patch.object(checker, 'inventory'):
            report = checker.run()
        gates = [item for item in report['findings'] if item['path'] == '/etc/mixpi/eject-reviewed']
        self.assertFalse(any('gate absent' in item['impact'] for item in gates))
        self.assertTrue(any('gate present' in item['impact'] for item in gates))

    def test_inaccessible_gate_parent_cannot_confirm_absence(self):
        checker = profile.Checker(self.root)
        original = Path.lstat
        def denied(path, *args, **kwargs):
            if path == self.root / 'etc/mixpi':
                raise PermissionError('synthetic denial')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'lstat', denied):
            report = checker.run()
        self.assertFalse(self.finding(report, '/etc/mixpi/eject-reviewed', 'PASS'))
        self.assertTrue(self.finding(report, '/etc/mixpi/eject-reviewed', 'UNVERIFIED'))

    def test_policy_aliases_never_read_or_hash_sensitive_targets(self):
        sensitive = ['/etc/shadow', '/root/.ssh/id_ed25519', '/run/private-token']
        original = Path.read_bytes
        for index, target in enumerate(sensitive):
            self.write(target, 'SENSITIVE-SENTINEL')
            (self.root / f'etc/sysctl.d/{index}-alias.conf').symlink_to(target)
        def guarded(path):
            if self.root in path.parents:
                self.assertNotIn('/' + str(path.relative_to(self.root)), sensitive)
            return original(path)
        checker = profile.Checker(self.root)
        with patch.object(Path, 'read_bytes', guarded):
            report = checker.run()
        for index in range(len(sensitive)):
            name = f'/etc/sysctl.d/{index}-alias.conf'
            self.assertNotIn(name, checker.read_hashes)
            self.assertTrue(self.finding(report, name, 'UNVERIFIED'))

    def test_read_failure_reasons_remain_distinct(self):
        name = '/etc/mixpi/controlled-media'
        path = self.root / name.lstrip('/')
        reasons = []
        for condition in ('missing', 'unreadable', 'oversized', 'encoding', 'special'):
            if path.exists():
                path.unlink()
            if condition == 'unreadable':
                self.write(name, 'v1\n', 0o000)
            elif condition == 'oversized':
                self.write(name, 'x' * (1024 * 1024 + 1))
            elif condition == 'encoding':
                path.write_bytes(b'\xff')
            elif condition == 'special':
                path.mkdir()
            checker = profile.Checker(self.root)
            self.assertIsNone(checker.read(name))
            reasons.append(checker.findings[-1]['impact'])
        self.assertEqual(len(set(reasons)), len(reasons), reasons)

    def test_dangling_gate_alias_and_missing_parent_cannot_confirm_absence(self):
        gate = self.root / 'etc/mixpi/eject-reviewed'
        gate.symlink_to('missing-target')
        checker = profile.Checker(self.root)
        checker.capability('/etc/mixpi/eject-reviewed', optional=True)
        self.assertFalse(any(item['status'] == 'PASS' for item in checker.findings))
        gate.unlink()
        (gate.parent / 'controlled-media').unlink()
        gate.parent.rmdir()
        checker = profile.Checker(self.root)
        checker.capability('/etc/mixpi/eject-reviewed', optional=True)
        self.assertFalse(any(item['status'] == 'PASS' for item in checker.findings))

    def test_hardlinked_policy_content_is_not_read_or_hashed(self):
        secret = self.write('/etc/shadow', 'SENSITIVE-SENTINEL')
        alias = self.root / 'etc/sysctl.d/91-alias.conf'
        os.link(secret, alias)
        checker = profile.Checker(self.root)
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('content must not be read')):
            self.assertIsNone(checker.read('/etc/sysctl.d/91-alias.conf'))
        self.assertEqual(checker.read_hashes, {})
        self.assertIn('multiply linked', checker.findings[-1]['impact'])


class MediaEjectGateRecipeTests(unittest.TestCase):
    """R-6: 06-run.sh writes /etc/mixpi/media-eject only for MIXPI_MEDIA_EJECT=1."""

    def run_recipe(self, **settings):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name) / 'rootfs'
        for directory in ('opt/mixpi-skin-tools', 'usr/local/bin', 'etc/systemd/system',
                          'etc/sysctl.d', 'etc/sudoers.d', 'media/pi'):
            (root / directory).mkdir(parents=True, exist_ok=True)
        command = 'on_chroot() { cat > "$ROOTFS_DIR/fixture-chroot-commands"; }; export -f on_chroot; ./06-run.sh'
        environment = {name: value for name, value in os.environ.items()
                       if not name.startswith(('MIXPI_ARTIFACT_', 'MIXPI_MEDIA_EJECT', 'MIXPI_CONTROLLED_MEDIA'))}
        environment.update(ROOTFS_DIR=str(root), **settings)
        result = subprocess.run(['bash', '-eu', '-c', command], cwd=ROOT / 'stage3/02-desktop',
                                env=environment, check=True, capture_output=True, text=True)
        return root, result.stdout

    def test_default_build_writes_no_gate_and_says_off(self):
        root, output = self.run_recipe()
        self.assertFalse((root / 'etc/mixpi/media-eject').exists())
        self.assertIn('media eject OFF', output)
        root, output = self.run_recipe(MIXPI_MEDIA_EJECT='0', MIXPI_CONTROLLED_MEDIA='1')
        self.assertFalse((root / 'etc/mixpi/media-eject').exists())
        self.assertIn('media eject OFF', output)

    def test_explicit_switch_writes_v1_mode_644(self):
        root, output = self.run_recipe(MIXPI_MEDIA_EJECT='1')
        gate = root / 'etc/mixpi/media-eject'
        self.assertEqual(gate.read_bytes(), b'v1\n')
        self.assertEqual(stat.S_IMODE(gate.stat().st_mode), 0o644)
        self.assertIn('media eject ON', output)
        # The recipe sets root ownership when it runs as root (as pi-gen does).
        recipe = (ROOT / 'stage3/02-desktop/06-run.sh').read_text()
        self.assertIn('chown root:root "${ROOTFS_DIR}/etc/mixpi/media-eject"', recipe)
        # The controlled profile alone never writes the eject gate.
        self.assertNotIn('media-eject', recipe.split('if [ "${MIXPI_MEDIA_EJECT:-0}" = 1 ]', 1)[0])


if __name__ == '__main__':
    unittest.main()
