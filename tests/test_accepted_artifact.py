"""Synthetic artifacts and chroot hooks; no root installs or application runs."""

import gzip
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('accepted_artifact', ROOT / 'tools/performance/accepted-artifact.py')
ingest = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ingest)
PACKAGE_DIRECTORIES = ('usr/share/mixxx', 'usr/share/mixxx/udev', 'usr/share/mixxx/udev/rules.d')


def archive(entries, overlay=False):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w', format=tarfile.USTAR_FORMAT) as stream:
        for name, data, mode, kind in entries:
            member = tarfile.TarInfo(name)
            member.uid = member.gid = 1000 if overlay else 0
            member.mode = mode
            member.type = kind
            if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE):
                member.linkname = '/outside'
            member.size = len(data) if kind == tarfile.REGTYPE else 0
            stream.addfile(member, io.BytesIO(data) if member.isfile() else None)
    return gzip.compress(output.getvalue(), mtime=0)


def deb(data, architecture='arm64'):
    control = ('Package: mixxx\nVersion: 2.5.6+rmodified-1\nArchitecture: ' + architecture +
               '\nDepends: libc6\n').encode()
    result = b'!<arch>\n'
    for name, content in (
            ('debian-binary', b'2.0\n'),
            ('control.tar.gz', archive([('./control', control, 0o644, tarfile.REGTYPE),
                                       ('./md5sums', b'fixture\n', 0o644, tarfile.REGTYPE)])),
            ('data.tar.gz', data)):
        header = f'{name:<16}{0:<12}{0:<6}{0:<6}{100644:<8}{len(content):<10}`\n'.encode()
        result += header + content + (b'\n' if len(content) % 2 else b'')
    return result


class AcceptedArtifactTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.repo = self.base / 'repo'
        self.repo.mkdir()
        for stage in ('stage0', 'stage1', 'stage2', 'stage3'):
            (self.repo / stage).mkdir()
        for name in ('build.sh', 'stage3/01-install-packages/01-run.sh',
                     'stage3/01-install-packages/02-run.sh', 'stage3/02-desktop/06-run.sh',
                     'stage3/02-desktop/files/49-mixpi-controlled-media.rules',
                     'tools/performance/accepted-artifact.py', *ingest.DESKTOP.values()):
            destination = self.repo / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, destination)
        self.approval_path = self.repo / 'tools/performance/accepted-artifact-20261110.json'
        self.artifacts = self.base / 'artifacts'
        self.artifacts.mkdir()
        self.work = self.base / 'work'
        self.rootfs = self.work / 'stage3/rootfs'
        self.deb_entries = [('./usr/bin/mixxx', b'fixture binary', 0o755, tarfile.REGTYPE),
                            *[('./' + name, b'', 0o775, tarfile.DIRTYPE) for name in PACKAGE_DIRECTORIES],
                            ('./usr/share/mixxx/upstream.xml', b'upstream', 0o644, tarfile.REGTYPE)]
        self.overlay_entries = [('./usr/share/mixxx/skins/Pioneered/skin.xml', b'skin', 0o644, tarfile.REGTYPE),
                                ('./opt/mixpi-skin-tools/tool.py', b'tool', 0o644, tarfile.REGTYPE),
                                ('./opt/pioneered.version', b'pinned-skin\n', 0o664, tarfile.REGTYPE)]
        self.manifest = {'schema': 1, 'mode': ingest.MODE, 'binary_sha256': ingest.digest(b'fixture binary'),
                         'refs': {'MIXXX_REF': '2.5.6', 'MIXXX_COMMIT': 'pinned-mixxx',
                                  'PIONEERED_COMMIT': 'pinned-skin', 'PI_DJ_COMMIT': 'pinned-pi-dj'},
                         'sources': {}, 'patch_order': subprocess.check_output(
                             ['bash', str(ROOT / 'stage3/01-install-packages/01-run.sh'), '--mixxx-print-patches'],
                             text=True).split()}
        for name in self.manifest['patch_order']:
            relative = 'stage3/01-install-packages/files/' + name
            destination = self.repo / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text('fixture patch ' + name)
            self.manifest['sources'][relative] = ingest.digest(destination.read_bytes())
        self.set_artifact('deb', deb(archive(self.deb_entries)))
        self.set_artifact('overlay', archive(self.overlay_entries, overlay=True))
        environment = {key: value for key, value in os.environ.items() if not key.startswith('MIXPI_ARTIFACT_')}
        environment.update(self.manifest['refs'])
        environment.update(MIXPI_ARTIFACT_MODE=ingest.MODE, MIXPI_ARTIFACT_DIR=str(self.artifacts),
                           MIXPI_CONTROLLED_MEDIA='0', ARCH='arm64', BASE_DIR=str(self.repo),
                           WORK_DIR=str(self.work), ROOTFS_DIR=str(self.rootfs), USE_QCOW2='0', CLEAN='', STAGE_LIST='')
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, environment, clear=True).start()
        patch.object(ingest, 'REPO', self.repo).start()
        patch.object(ingest, 'MANIFEST', self.approval_path).start()
        self.approve_fixture()

    def set_artifact(self, key, data):
        name = 'candidate.deb' if key == 'deb' else 'overlay.tar.gz'
        (self.artifacts / name).write_bytes(data)
        item = {'name': name, 'size': len(data), 'sha256': ingest.digest(data)}
        if key == 'deb':
            inventory, _ = ingest.deb_inventory(data)
            item.update(inventory)
        else:
            item['payload'], _ = ingest.tar_inventory(data, overlay=True)
        self.manifest[key] = item

    def approve_fixture(self):
        raw = ingest.encoded(self.manifest)
        self.approval_path.write_bytes(raw)
        os.environ['MIXPI_ARTIFACT_MANIFEST_SHA256'] = ingest.digest(raw)

    def initialize(self):
        ingest.initialize()
        self.rootfs.mkdir(parents=True)

    def write(self, name, data=b'stale', mode=0o644):
        target = self.rootfs / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        target.chmod(mode)
        return target

    def install_fixture(self):
        self.initialize()
        ingest.prepare()
        for name, data, mode, kind in self.deb_entries:
            if kind == tarfile.DIRTYPE:
                directory = self.rootfs / name[2:]
                directory.mkdir(parents=True, exist_ok=True)
                directory.chmod(mode)
            else:
                self.write(name[2:], data, mode)
        ingest.installed()

    def test_package_directory_modes_harden_before_payload_verification(self):
        shared = self.rootfs / 'usr/share'
        self.install_fixture()
        for name in PACKAGE_DIRECTORIES:
            self.assertEqual(stat.S_IMODE((self.rootfs / name).stat().st_mode), 0o755)
            self.assertEqual(self.manifest['deb']['payload'][name]['mode'], 0o775)
        self.assertEqual(stat.S_IMODE(shared.stat().st_mode), 0o755)
        self.assertEqual((self.rootfs / 'usr/bin/mixxx').read_bytes(), b'fixture binary')
        ingest.verify_payload(self.rootfs, self.manifest['deb']['payload'])

    def hardening_fixture(self):
        self.rootfs.mkdir(parents=True)
        for name in PACKAGE_DIRECTORIES:
            directory = self.rootfs / name
            directory.mkdir(parents=True, exist_ok=True)
            directory.chmod(0o775)
        return self.manifest['deb']['payload']

    def test_hardening_prevalidates_all_directories_before_changes(self):
        payload = self.hardening_fixture()
        leaf = self.rootfs / PACKAGE_DIRECTORIES[-1]
        for mode in (0o777, 0o770, 0o700, 0o2775):
            with self.subTest(mode=oct(mode)):
                leaf.chmod(mode)
                with self.assertRaisesRegex(ValueError, 'package directory'):
                    ingest.normalize_package_directories(self.rootfs, payload)
                self.assertEqual(stat.S_IMODE((self.rootfs / PACKAGE_DIRECTORIES[0]).stat().st_mode), 0o775)
                self.assertEqual(stat.S_IMODE(leaf.stat().st_mode), mode)

    def test_hardening_rejects_links_and_wrong_types_without_following(self):
        payload = self.hardening_fixture()
        leaf = self.rootfs / PACKAGE_DIRECTORIES[-1]
        outside = self.base / 'outside'
        outside.mkdir(mode=0o775)
        outside.chmod(0o775)
        leaf.rmdir()
        leaf.symlink_to(outside)
        with self.assertRaises(OSError):
            ingest.normalize_package_directories(self.rootfs, payload)
        self.assertEqual(stat.S_IMODE(outside.stat().st_mode), 0o775)
        self.assertEqual(stat.S_IMODE((self.rootfs / PACKAGE_DIRECTORIES[0]).stat().st_mode), 0o775)
        leaf.unlink()
        leaf.write_text('not a directory')
        with self.assertRaises(OSError):
            ingest.normalize_package_directories(self.rootfs, payload)

    def test_hardening_requires_exact_manifest_and_existing_directories(self):
        payload = self.hardening_fixture()
        payload[PACKAGE_DIRECTORIES[-1]]['mode'] = 0o777
        with self.assertRaisesRegex(ValueError, 'package directory manifest'):
            ingest.normalize_package_directories(self.rootfs, payload)
        self.assertEqual(stat.S_IMODE((self.rootfs / PACKAGE_DIRECTORIES[0]).stat().st_mode), 0o775)
        payload[PACKAGE_DIRECTORIES[-1]]['mode'] = 0o775
        (self.rootfs / PACKAGE_DIRECTORIES[-1]).rmdir()
        with self.assertRaises(FileNotFoundError):
            ingest.normalize_package_directories(self.rootfs, payload)

    def test_hardening_rejects_unexpected_ownership_before_changes(self):
        payload = self.hardening_fixture()
        observations = [(self.rootfs / name).stat() for name in PACKAGE_DIRECTORIES]
        for field in (4, 5):
            with self.subTest(field=field):
                changed = list(observations[-1])
                changed[field] += 1
                with patch.object(ingest.os, 'fstat', side_effect=[*observations[:-1], os.stat_result(changed)]):
                    with self.assertRaisesRegex(ValueError, 'package directory owner/mode'):
                        ingest.normalize_package_directories(self.rootfs, payload)
                for name in PACKAGE_DIRECTORIES:
                    self.assertEqual(stat.S_IMODE((self.rootfs / name).stat().st_mode), 0o775)

    def test_hardening_failure_does_not_record_installed_completion(self):
        original = ingest.os.fchmod
        calls = []

        def fail_second(descriptor, mode):
            calls.append(descriptor)
            if len(calls) == 2:
                raise PermissionError('injected chmod failure')
            original(descriptor, mode)

        with patch.object(ingest.os, 'fchmod', side_effect=fail_second):
            with self.assertRaisesRegex(PermissionError, 'injected chmod failure'):
                self.install_fixture()
        self.assertFalse((self.work / ingest.STATE / 'installed').exists())

    def test_hardening_is_idempotent_and_does_not_relax_safe_path(self):
        payload = self.hardening_fixture()
        with self.assertRaisesRegex(ValueError, 'unsafe owner/mode'):
            ingest.safe_path(self.rootfs, 'usr/share/mixxx/upstream.xml')
        ingest.normalize_package_directories(self.rootfs, payload)
        ingest.normalize_package_directories(self.rootfs, payload)
        self.assertEqual(ingest.safe_path(self.rootfs, 'usr/share/mixxx/upstream.xml'),
                         self.rootfs / 'usr/share/mixxx/upstream.xml')
        (self.rootfs / 'usr/share').chmod(0o775)
        with self.assertRaisesRegex(ValueError, 'unsafe owner/mode'):
            ingest.normalize_package_directories(self.rootfs, payload)

    @unittest.skipUnless(sys.platform == 'linux' and os.geteuid() == 0 and
                         os.environ.get('MIXPI_TEST_REAL_DEB') == '1',
                         'requires explicitly authorized Linux root and exact accepted DEB')
    def test_real_deb_extraction_normalizes_only_three_directories(self):
        package = Path(os.environ['MIXPI_TEST_DEB_PATH'])
        self.assertEqual(ingest.digest(package.read_bytes()),
                         '40fb4a74485a67c3ea0b33a3a01f661d4d2d6b19dc929d9441e7a50a878749c1')
        manifest = json.loads((ROOT / 'tools/performance/accepted-artifact-20261110.json').read_bytes())
        self.rootfs.mkdir(parents=True)
        subprocess.run(['dpkg-deb', '--extract', str(package), str(self.rootfs)], check=True)
        files = {str(path.relative_to(self.rootfs)): ingest.digest(path.read_bytes())
                 for path in self.rootfs.rglob('*') if path.is_file()}
        directories = {str(path.relative_to(self.rootfs)): stat.S_IMODE(path.stat().st_mode)
                       for path in self.rootfs.rglob('*') if path.is_dir()}
        for name in PACKAGE_DIRECTORIES:
            self.assertEqual(directories[name], 0o775)
        ingest.normalize_package_directories(self.rootfs, manifest['deb']['payload'])
        for name, mode in directories.items():
            self.assertEqual(stat.S_IMODE((self.rootfs / name).stat().st_mode),
                             0o755 if name in PACKAGE_DIRECTORIES else mode)
        for name, checksum in files.items():
            self.assertEqual(ingest.digest((self.rootfs / name).read_bytes()), checksum)

    def skin_fixture(self):
        self.install_fixture()
        source = self.base / 'pi-dj'
        source.mkdir()
        (source / 'pi-dj.xml').write_text('pinned fixture')
        ingest.copy_pi_dj(source)
        ingest.overlay()

    def test_happy_path_sealed_inputs_lineage_and_final_off(self):
        self.skin_fixture()
        source = self.repo / ingest.DESKTOP['usr/local/bin/mixpi-mount-control']
        self.write('usr/local/bin/mixpi-mount-control', source.read_bytes(), 0o755)
        ingest.verify()
        for destination, source in ingest.DESKTOP.items():
            self.write(destination, (self.repo / source).read_bytes(), 0o755 if destination.endswith('control') else 0o644)
        ingest.verify(final=True)
        receipt = json.loads((self.rootfs / 'opt/mixpi-accepted-artifact/integration.json').read_bytes())
        self.assertFalse(receipt['eject_reviewed'])
        self.assertEqual(receipt['media_eject'], 'OFF')
        self.assertEqual(receipt['controlled_media'], 'OFF')
        self.assertEqual((self.rootfs / 'opt/pioneered.version').stat().st_mode & 0o777, 0o644)
        self.assertTrue((self.rootfs / 'opt/mixxx-package/candidate.deb').exists())

    def test_configuration_failures_precede_work_creation(self):
        failures = [('ARCH', 'amd64'), ('MIXXX_REF', 'other'), ('MIXXX_COMMIT', 'other'),
                    ('PIONEERED_COMMIT', 'other'), ('PI_DJ_COMMIT', 'other'),
                    ('MIXPI_ARTIFACT_MODE', 'unknown'), ('MIXPI_CONTROLLED_MEDIA', '1'),
                    ('MIXPI_ARTIFACT_MANIFEST_SHA256', '0' * 64), ('MIXPI_ARTIFACT_OTHER', 'unexpected')]
        for key, value in failures:
            with self.subTest(key=key), patch.dict(os.environ, {key: value}):
                with self.assertRaises(ValueError):
                    ingest.initialize()
                self.assertFalse(self.work.exists())
        for key in ingest.CONFIG | {'MIXPI_CONTROLLED_MEDIA'}:
            with self.subTest(missing=key), patch.dict(os.environ):
                del os.environ[key]
                with self.assertRaises(ValueError):
                    ingest.initialize()

    def test_digest_and_patch_mismatch_fail_before_mutations(self):
        artifact = self.artifacts / self.manifest['deb']['name']
        original = artifact.read_bytes()
        artifact.write_bytes(original + b'corrupt')
        with self.assertRaisesRegex(ValueError, 'digest/size'):
            ingest.initialize()
        artifact.write_bytes(original)
        source = self.repo / next(iter(self.manifest['sources']))
        source.write_text('different patch')
        with self.assertRaisesRegex(ValueError, 'source input'):
            ingest.initialize()
        self.assertFalse(self.work.exists())

    def test_wrong_deb_arch_even_with_fresh_hash_is_not_approved(self):
        self.set_artifact('deb', deb(archive(self.deb_entries), architecture='amd64'))
        self.approve_fixture()
        with self.assertRaisesRegex(ValueError, 'architecture'):
            ingest.initialize()

    def test_archive_unsafe_shapes(self):
        for name, mode, kind in (
                ('../escape', 0o644, tarfile.REGTYPE), ('/absolute', 0o644, tarfile.REGTYPE),
                ('./usr//bad', 0o644, tarfile.REGTYPE), ('./etc/passwd', 0o644, tarfile.REGTYPE),
                ('./opt/mixpi-skin-tools/link', 0o644, tarfile.SYMTYPE),
                ('./opt/mixpi-skin-tools/link', 0o644, tarfile.LNKTYPE),
                ('./opt/mixpi-skin-tools/fifo', 0o644, tarfile.FIFOTYPE),
                ('./opt/mixpi-skin-tools/file', 0o4755, tarfile.REGTYPE),
                ('./opt/mixpi-skin-tools/file', 0o666, tarfile.REGTYPE)):
            with self.subTest(name=name, mode=mode, kind=kind), self.assertRaises(ValueError):
                ingest.tar_inventory(archive([(name, b'x', mode, kind)], overlay=True), overlay=True)
        duplicate = [self.overlay_entries[0], self.overlay_entries[0]]
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            ingest.tar_inventory(archive(duplicate, overlay=True), overlay=True)
        entries = [('./opt/mixpi-skin-tools', b'parent', 0o644, tarfile.REGTYPE), self.overlay_entries[1]]
        with self.assertRaisesRegex(ValueError, 'parent'):
            ingest.tar_inventory(archive(entries, overlay=True), overlay=True)
        with self.assertRaises(ValueError):
            ingest.tar_inventory(archive(self.overlay_entries), overlay=True)

    def test_archive_and_file_bounds_do_not_open_special_inputs(self):
        oversized = [('./opt/mixpi-skin-tools/large', b'x' * (1024 * 1024 + 1), 0o644, tarfile.REGTYPE)]
        with self.assertRaisesRegex(ValueError, 'oversized'):
            ingest.tar_inventory(archive(oversized, overlay=True), overlay=True)
        many = [(f'./opt/mixpi-skin-tools/{number}', b'x', 0o644, tarfile.REGTYPE) for number in range(81)]
        with self.assertRaisesRegex(ValueError, 'too many'):
            ingest.tar_inventory(archive(many, overlay=True), overlay=True)
        fifo = self.base / 'fifo'
        os.mkfifo(fifo)
        with self.assertRaisesRegex(ValueError, 'regular file'):
            ingest.regular(fifo)
        original = self.artifacts / 'candidate.deb'
        alias = self.base / 'linked'
        os.link(original, alias)
        with self.assertRaisesRegex(ValueError, 'regular file'):
            ingest.initialize()

    def test_same_content_source_reordering_is_not_accepted(self):
        stage = self.repo / 'stage3/01-install-packages/01-run.sh'
        names = self.manifest['patch_order']
        stage.write_text(stage.read_text().replace(names[0], 'TEMPORARY').replace(names[1], names[0]).replace('TEMPORARY', names[1]))
        with self.assertRaisesRegex(ValueError, 'patch order'):
            ingest.initialize()

    def test_valid_but_unexpected_payload_is_rejected(self):
        entries = self.overlay_entries + [('./opt/mixpi-skin-tools/extra', b'x', 0o644, tarfile.REGTYPE)]
        data = archive(entries, overlay=True)
        (self.artifacts / 'overlay.tar.gz').write_bytes(data)
        self.manifest['overlay']['sha256'] = ingest.digest(data)
        self.manifest['overlay']['size'] = len(data)
        self.approve_fixture()
        with self.assertRaisesRegex(ValueError, 'overlay payload'):
            ingest.initialize()

    def test_existing_work_and_root_aliases_refused(self):
        self.work.mkdir()
        with self.assertRaisesRegex(ValueError, 'fresh dedicated'):
            ingest.initialize()
        self.work.rmdir()
        self.initialize()
        self.rootfs.rmdir()
        elsewhere = self.base / 'elsewhere'
        elsewhere.mkdir()
        self.rootfs.symlink_to(elsewhere, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'aliased rootfs'):
            ingest.prepare()

    def test_stale_paths_and_profile_gates_refused_without_deletion(self):
        self.initialize()
        for name in ('usr/bin/mixxx', 'opt/mixxx.version', 'opt/mixxx-package',
                     'etc/mixpi/controlled-media', 'etc/mixpi/eject-reviewed',
                     'etc/polkit-1/rules.d/renamed.rules',
                     'etc/systemd/system/multi-user.target.wants/mixpi-mount-broker.service',
                     'var/lib/dpkg/info/mixxx.list'):
            with self.subTest(name=name):
                target = self.write(name, b'controlled-media')
                with self.assertRaises(ValueError):
                    ingest.prepare()
                self.assertEqual(target.read_bytes(), b'controlled-media')
                target.unlink()
        status = self.write('var/lib/dpkg/status', b'Package: mixxx\nStatus: deinstall ok config-files\n')
        with self.assertRaisesRegex(ValueError, 'dpkg state'):
            ingest.prepare()
        status.unlink()
        gate = self.rootfs / 'etc/mixpi/eject-reviewed'
        gate.symlink_to('missing')
        with self.assertRaisesRegex(ValueError, 'aliased'):
            ingest.prepare()
        gate.unlink()
        parent = self.rootfs / 'etc/mixpi'
        parent.rmdir()
        parent.symlink_to(self.base, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'aliased'):
            ingest.prepare()

    def test_inaccessible_policy_parent_is_not_absence(self):
        self.initialize()
        directory = self.rootfs / 'etc/mixpi'
        directory.mkdir(parents=True)
        directory.chmod(0o111)
        try:
            with self.assertRaisesRegex(ValueError, 'inaccessible'):
                ingest.prepare()
        finally:
            directory.chmod(0o755)

    def test_aliased_and_inherited_profile_enablement_are_refused(self):
        self.initialize()
        policy = self.write('etc/sysctl.d/renamed.conf', b'user.max_user_namespaces=0\n# controlled-media\n')
        with self.assertRaisesRegex(ValueError, 'inherited profile'):
            ingest.prepare()
        policy.unlink()
        mask = self.rootfs / 'etc/systemd/system/udisks2.service'
        mask.parent.mkdir(parents=True)
        mask.symlink_to('/dev/null')
        with self.assertRaisesRegex(ValueError, 'authority/mask'):
            ingest.prepare()
        mask.unlink()
        enablement = mask.parent / 'multi-user.target.wants/renamed.service'
        enablement.parent.mkdir()
        enablement.symlink_to('../mixpi-mount-broker.service')
        with self.assertRaisesRegex(ValueError, 'authority/mask'):
            ingest.prepare()

    def test_stock_unit_alias_is_allowed_but_hidden_policy_is_not(self):
        self.initialize()
        target = self.write('usr/lib/systemd/system/normal.service', b'[Service]\nExecStart=/usr/bin/true\n')
        alias = self.rootfs / 'etc/systemd/system/multi-user.target.wants/renamed.service'
        alias.parent.mkdir(parents=True)
        alias.symlink_to('/usr/lib/systemd/system/normal.service')
        ingest.profile_off(self.rootfs)
        target.write_bytes(b'[Service]\nExecStart=/usr/local/bin/mixpi-mount-control\n')
        with self.assertRaisesRegex(ValueError, 'inherited profile policy'):
            ingest.profile_off(self.rootfs)
        target.unlink()
        with self.assertRaises(FileNotFoundError):
            ingest.profile_off(self.rootfs)

    def test_media_eject_gate_must_be_absent_in_artifact_mode(self):
        # R-6: the eject gate file and the build switch are both refused.
        self.initialize()
        ingest.profile_off(self.rootfs)
        gate = self.write('etc/mixpi/media-eject', b'v1\n')
        with self.assertRaisesRegex(ValueError, 'media-eject|stale|exist'):
            ingest.profile_off(self.rootfs)
        self.assertEqual(gate.read_bytes(), b'v1\n')
        gate.unlink()
        with patch.dict(os.environ, {'MIXPI_MEDIA_EJECT': '1'}):
            with self.assertRaisesRegex(ValueError, 'media eject OFF'):
                ingest.profile_off(self.rootfs)
        ingest.profile_off(self.rootfs)

    def test_default_ssh_key_service_is_not_controlled_mount_authority(self):
        self.initialize()
        self.write('etc/systemd/system/mixpi-install-ssh-key.service', b'[Service]\nExecStart=/usr/local/bin/mixpi-install-ssh-key\n')
        alias = self.rootfs / 'etc/systemd/system/multi-user.target.wants/mixpi-install-ssh-key.service'
        alias.parent.mkdir()
        alias.symlink_to('../mixpi-install-ssh-key.service')
        ingest.profile_off(self.rootfs)

    def test_renamed_profile_hardening_is_not_silently_inherited(self):
        self.initialize()
        for name, data in (
                ('etc/sysctl.d/arbitrary.conf', b'user.max_user_namespaces = 0\n'),
                ('etc/sysctl.conf', b'user.max_user_namespaces=0\n'),
                ('etc/sudoers.d/renamed', b'pi ALL=(root) NOPASSWD: /usr/sbin/shutdown\n'),
                ('var/lib/dpkg/statoverride', b'root root 0755 /usr/bin/udevil\n')):
            with self.subTest(name=name):
                path = self.write(name, data)
                with self.assertRaisesRegex(ValueError, 'inherited profile'):
                    ingest.prepare()
                path.unlink()

    def test_final_rejects_renamed_shipped_polkit_policy(self):
        self.skin_fixture()
        for destination, source in ingest.DESKTOP.items():
            self.write(destination, (self.repo / source).read_bytes(), 0o755 if destination.endswith('control') else 0o644)
        policy = (self.repo / 'stage3/02-desktop/files/49-mixpi-controlled-media.rules').read_bytes()
        for content in (policy, policy.replace(b'    ', b'\t'), b'// retained policy\n' + policy):
            with self.subTest(content=content):
                target = self.write('etc/polkit-1/rules.d/77-renamed.rules', content)
                with self.assertRaisesRegex(ValueError, 'inherited profile'):
                    ingest.verify(final=True)
                self.assertFalse((self.rootfs / 'opt/mixpi-accepted-artifact/integration.json').exists())
                self.assertEqual(target.read_bytes(), content)
                target.unlink()
        self.write('usr/share/polkit-1/rules.d/50-stock.rules',
                   b'polkit.addRule(function(action, subject) { return polkit.Result.NOT_HANDLED; });\n')
        ingest.verify(final=True)

    def test_final_rejects_sysctl_search_paths_and_spellings(self):
        self.skin_fixture()
        for folder in ('etc', 'etc/sysctl.d', 'usr/lib/sysctl.d', 'usr/local/lib/sysctl.d', 'run/sysctl.d', 'lib/sysctl.d'):
            for setting in (b'user.max_user_namespaces=0\n', b'user/max_user_namespaces = 0\n',
                            b'-user/max_user_namespaces = 0 # restricted\n'):
                with self.subTest(folder=folder, setting=setting):
                    target = self.write(folder + ('/sysctl.conf' if folder == 'etc' else '/80-renamed.conf'), setting)
                    with self.assertRaisesRegex(ValueError, 'inherited profile namespace'):
                        ingest.verify(final=True)
                    target.unlink()

    def test_sysctl_merged_usr_alias_stays_root_local(self):
        self.initialize()
        target = self.write('usr/lib/sysctl.d/80-renamed.conf', b'user/max_user_namespaces=0\n')
        alias = self.rootfs / 'lib'
        for destination in ('usr/lib', '/usr/lib'):
            with self.subTest(destination=destination):
                alias.symlink_to(destination)
                with self.assertRaisesRegex(ValueError, 'inherited profile namespace'):
                    ingest.profile_off(self.rootfs)
                alias.unlink()
        target.write_bytes(b'user/max_user_namespaces=1024\n')
        alias.symlink_to('usr/lib')
        ingest.profile_off(self.rootfs)
        alias.unlink()
        alias.symlink_to(self.base)
        with self.assertRaisesRegex(ValueError, 'alias'):
            ingest.profile_off(self.rootfs)

    def test_final_rejects_merged_and_unmerged_statoverrides(self):
        self.skin_fixture()
        for executable in ('/bin/mount', '/bin/umount', '/usr/bin/mount', '/usr/bin/umount',
                           '/bin/udevil', '/bin/fusermount', '/bin/fusermount3', '/bin/ntfs-3g',
                           '/sbin/mount.cifs', '/usr/sbin/mount.cifs'):
            with self.subTest(executable=executable):
                target = self.write('var/lib/dpkg/statoverride', ('root root 0755 ' + executable + '\n').encode())
                with self.assertRaisesRegex(ValueError, 'inherited profile dpkg'):
                    ingest.verify(final=True)
                target.unlink()

    def test_all_required_stages_reject_nested_skips_before_work(self):
        for stage in ('stage0', 'stage1', 'stage2', 'stage3'):
            with self.subTest(stage=stage):
                marker = self.repo / stage / '00-recipe/deeper/SKIP'
                marker.parent.mkdir(parents=True, exist_ok=True)
                marker.touch()
                with self.assertRaisesRegex(ValueError, 'cannot skip'):
                    ingest.initialize()
                self.assertFalse(self.work.exists())
                marker.unlink()

    def test_all_required_stages_recheck_nested_skip_drift(self):
        self.initialize()
        for stage in ('stage0', 'stage1', 'stage2', 'stage3'):
            with self.subTest(stage=stage):
                marker = self.repo / stage / '00-recipe/deeper/SKIP'
                marker.parent.mkdir(parents=True, exist_ok=True)
                marker.symlink_to('missing-marker-target')
                with self.assertRaisesRegex(ValueError, 'cannot skip'):
                    ingest.load()
                marker.unlink()

    def test_required_stage_topology_errors_fail_before_work(self):
        directory = self.repo / 'stage1'
        directory.rmdir()
        with self.assertRaises(OSError):
            ingest.initialize()
        self.assertFalse(self.work.exists())
        directory.symlink_to(self.repo / 'stage0', target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'aliased required stage'):
            ingest.initialize()
        directory.unlink()
        directory.mkdir(mode=0o300)
        with self.assertRaises((ValueError, PermissionError)):
            ingest.initialize()
        directory.chmod(0o755)
        (directory / 'aliased-recipe').symlink_to(self.repo / 'stage0', target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'aliased stage directory'):
            ingest.initialize()
        self.assertFalse(self.work.exists())

    def test_existing_overlay_and_package_parents_cannot_be_aliased(self):
        self.initialize()
        directory = self.rootfs / 'usr'
        directory.symlink_to(self.base, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'aliased'):
            ingest.prepare()
        directory.unlink()
        target = self.write(ingest.SKIN + '/existing', b'preserved')
        with self.assertRaisesRegex(ValueError, 'existing destination'):
            ingest.prepare()
        self.assertEqual(target.read_bytes(), b'preserved')

    def test_stable_copy_ignores_replaced_original_but_seal_detects_changes(self):
        self.initialize()
        (self.artifacts / 'candidate.deb').write_bytes(b'changed external input')
        ingest.prepare()
        self.assertEqual(ingest.digest((self.rootfs / 'opt/mixxx-package/candidate.deb').read_bytes()),
                         self.manifest['deb']['sha256'])
        (self.repo / 'stage3/02-desktop/06-run.sh').write_text('changed integration')
        with self.assertRaisesRegex(ValueError, 'changed after preflight'):
            ingest.load()

    def test_pi_dj_cannot_overlap_or_alias_overlay(self):
        self.install_fixture()
        source = self.base / 'pi-dj'
        source.mkdir()
        (source / 'Pioneered').mkdir()
        with self.assertRaisesRegex(ValueError, 'overlaps'):
            ingest.copy_pi_dj(source)
        (source / 'Pioneered').rmdir()
        (source / 'alias').symlink_to(self.base)
        with self.assertRaisesRegex(ValueError, 'link'):
            ingest.copy_pi_dj(source)

    def test_final_detects_late_overlay_change(self):
        self.skin_fixture()
        self.write(ingest.SKIN + '/skin.xml', b'late mutation')
        with self.assertRaisesRegex(ValueError, 'payload mismatch'):
            ingest.verify()

    def test_final_detects_extra_overlay_and_lineage_changes(self):
        self.skin_fixture()
        source = self.repo / ingest.DESKTOP['usr/local/bin/mixpi-mount-control']
        self.write('usr/local/bin/mixpi-mount-control', source.read_bytes(), 0o755)
        extra = self.write(ingest.TOOLS + '/extra.py')
        with self.assertRaisesRegex(ValueError, 'unexpected overlay'):
            ingest.verify()
        extra.unlink()
        self.write('opt/mixxx.version', b'other')
        with self.assertRaisesRegex(ValueError, 'lineage ref changed'):
            ingest.verify()

    def test_failed_install_retains_evidence_without_completion(self):
        self.initialize()
        script = 'on_chroot() { cat > "$WORK_DIR/failed-commands"; return 23; }; export -f on_chroot; bash ./01-run.sh'
        result = subprocess.run(['bash', '-c', script], cwd=self.repo / 'stage3/01-install-packages', capture_output=True)
        self.assertEqual(result.returncode, 23, result.stderr)
        self.assertTrue((self.rootfs / 'opt/mixxx-package/candidate.deb').exists())
        self.assertFalse((self.work / ingest.STATE / 'installed').exists())
        with self.assertRaisesRegex(ValueError, 'existing destination'):
            ingest.prepare()

    def test_real_package_stage_uses_only_normal_apt_and_ownership_hooks(self):
        self.initialize()
        script = r'''
set -eu
on_chroot() {
    cat > "$WORK_DIR/install-commands"
    mkdir -p "$ROOTFS_DIR/usr/bin" "$ROOTFS_DIR/usr/share/mixxx"
    mkdir -p "$ROOTFS_DIR/usr/share/mixxx/udev/rules.d"
    chmod 775 "$ROOTFS_DIR/usr/share/mixxx" "$ROOTFS_DIR/usr/share/mixxx/udev" "$ROOTFS_DIR/usr/share/mixxx/udev/rules.d"
    printf 'fixture binary' > "$ROOTFS_DIR/usr/bin/mixxx"
    chmod 755 "$ROOTFS_DIR/usr/bin/mixxx"
    printf upstream > "$ROOTFS_DIR/usr/share/mixxx/upstream.xml"
}
mount() { exit 90; }
rsync() { exit 91; }
cmake() { exit 92; }
export -f on_chroot mount rsync cmake
bash ./01-run.sh
'''
        result = subprocess.run(['bash', '-c', script], cwd=self.repo / 'stage3/01-install-packages',
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        commands = (self.work / 'install-commands').read_text()
        for expected in ('apt-get update', 'apt-get install -y --no-install-recommends /opt/mixxx-package/candidate.deb',
                         'dpkg-query -S /usr/bin/mixxx', 'dpkg --audit', 'apt-get check', 'dpkg --print-architecture'):
            self.assertIn(expected, commands)
        for forbidden in ('--force', '--allow-unauthenticated', 'cmake', 'ccache'):
            self.assertNotIn(forbidden, commands)
        self.assertFalse(list(self.work.glob('mixxx-build.*')))
        self.assertFalse((self.repo / '.ccache').exists())

    def test_real_skin_stage_never_fetches_or_regenerates_pioneered(self):
        self.install_fixture()
        script = r'''
set -eu
git() {
    printf '%s\n' "$*" >> "$WORK_DIR/git-calls"
    case "$*" in *Pioneered*) exit 93;; esac
    if [ "$1" = init ]; then
        mkdir -p "$3/mixxx/skin"
        printf pi-dj > "$3/mixxx/skin/pi-dj.xml"
    elif [ "$3" = rev-parse ]; then
        printf '%s\n' "$PI_DJ_COMMIT"
    fi
}
on_chroot() { exit 94; }
export -f git on_chroot
bash ./02-run.sh
'''
        result = subprocess.run(['bash', '-c', script], cwd=self.repo / 'stage3/01-install-packages',
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('pinned-pi-dj', (self.work / 'git-calls').read_text())
        self.assertNotIn('Pioneered', (self.work / 'git-calls').read_text())
        ingest.verify_payload(self.rootfs, self.manifest['overlay']['payload'])

    def test_real_desktop_stage_import_stays_off(self):
        self.skin_fixture()
        source = self.repo / ingest.DESKTOP['usr/local/bin/mixpi-mount-control']
        self.write('usr/local/bin/mixpi-mount-control', source.read_bytes(), 0o755)
        for name in ('usr/local/bin', 'etc/systemd/system'):
            (self.rootfs / name).mkdir(parents=True, exist_ok=True)
        script = 'on_chroot() { exit 95; }; export -f on_chroot; bash ./06-run.sh'
        result = subprocess.run(['bash', '-c', script], cwd=self.repo / 'stage3/02-desktop', capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        ingest.verify(final=True)
        self.assertFalse((self.rootfs / 'etc/mixpi').exists())

    def test_actual_desktop_04_then_06_stays_off(self):
        for name in ('04-run.sh', 'files/bin/mixpi_ui.py', 'files/ssh/mixpi-import-ssh-key',
                     'files/ssh/20-mixpi-key-only.conf', 'files/ssh/mixpi-ssh-key.service',
                     'files/sbin/mixpi-maintenance', 'files/sudoers/020_mixpi-maintenance'):
            target = self.repo / 'stage3/02-desktop' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / 'stage3/02-desktop' / name, target)
        self.skin_fixture()
        (self.rootfs / 'etc/systemd/system').mkdir(parents=True)
        script = 'set -eu; on_chroot() { cat >/dev/null; }; export -f on_chroot; bash ./04-run.sh; bash ./06-run.sh'
        result = subprocess.run(['bash', '-c', script], cwd=self.repo / 'stage3/02-desktop',
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        ingest.verify(final=True)
        self.assertFalse((self.rootfs / 'etc/mixpi').exists())

    def test_desktop_phase_requires_exact_cli_and_absent_other_helpers(self):
        self.skin_fixture()
        name = 'usr/local/bin/mixpi-mount-control'
        expected = (self.repo / ingest.DESKTOP[name]).read_bytes()
        with self.assertRaises(FileNotFoundError):
            ingest.verify()
        target = self.write(name, b'changed', 0o755)
        with self.assertRaisesRegex(ValueError, 'helper mismatch'):
            ingest.verify()
        target.write_bytes(expected)
        target.chmod(0o644)
        with self.assertRaisesRegex(ValueError, 'helper mode'):
            ingest.verify()
        target.unlink()
        original = self.base / 'original-cli'
        original.write_bytes(expected)
        original.chmod(0o755)
        target.symlink_to(original)
        with self.assertRaisesRegex(ValueError, 'aliased'):
            ingest.verify()
        target.unlink()
        os.link(original, target)
        with self.assertRaisesRegex(ValueError, 'single regular'):
            ingest.verify()
        target.unlink()
        self.write(name, expected, 0o755)
        ingest.verify()
        for destination, source in ingest.DESKTOP.items():
            if destination == name:
                continue
            extra = self.write(destination, (self.repo / source).read_bytes())
            with self.assertRaises(ValueError):
                ingest.verify()
            extra.unlink()

    def test_partial_mode_never_falls_back_to_compilation(self):
        for key in ingest.CONFIG:
            with self.subTest(missing=key), patch.dict(os.environ):
                del os.environ[key]
                script = 'mktemp() { exit 96; }; export -f mktemp; bash ./01-run.sh'
                result = subprocess.run(['bash', '-c', script], cwd=self.repo / 'stage3/01-install-packages',
                                        capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotEqual(result.returncode, 96)
                self.assertIn('partial or unknown', result.stderr)

    def test_package_cli_rejects_mixed_mode_without_clone(self):
        result = subprocess.run(['bash', './01-run.sh', '--mixxx-package', '/unused'],
                                cwd=self.repo / 'stage3/01-install-packages', capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('cannot build a package', result.stderr)

    def test_build_config_exports_and_preflight_precede_image_work(self):
        build = (ROOT / 'build.sh').read_text()
        start = build.index('if [[ -n "${!MIXPI_ARTIFACT_*}" ]]')
        stop = build.index('\nterm() {', start)
        block = build[start:stop].replace('python3 "${BASE_DIR}/tools/performance/accepted-artifact.py" initialize',
                                        'env > "$EXPORTED"')
        config = '\n'.join(f'{name}={json.dumps(os.environ[name])}' for name in ingest.CONFIG | {'MIXPI_CONTROLLED_MEDIA', 'ARCH', 'WORK_DIR'})
        result = subprocess.run(['bash', '-eu', '-c', config + '\n' + block],
                                env={'PATH': os.environ['PATH'], 'EXPORTED': str(self.base / 'exported')},
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        exported = (self.base / 'exported').read_text()
        for name in ingest.CONFIG | {'MIXPI_CONTROLLED_MEDIA', 'ARCH', 'WORK_DIR'}:
            self.assertIn(name + '=' + os.environ[name], exported)
        self.assertLess(start, build.index('dependencies_check "${BASE_DIR}/depends"'))
        self.assertIn('accepted-artifact.py" final', build)

    def test_actual_build_startup_reads_unexported_config_then_seals(self):
        shutil.copyfile(ROOT / 'source-versions', self.repo / 'source-versions')
        names = ingest.CONFIG | {'MIXPI_CONTROLLED_MEDIA', 'ARCH', 'WORK_DIR'} | set(self.manifest['refs'])
        (self.repo / 'config').write_text('\n'.join(f'{name}={json.dumps(os.environ[name])}' for name in names) + '\n')
        environment = {name: value for name, value in os.environ.items() if name not in names}
        script = 'id() { printf "0\\n"; }; python3() { command python3 "$@" || return $?; return 77; }; source ./build.sh'
        result = subprocess.run(['bash', '-e', '-c', script], cwd=self.repo, env=environment,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 77, result.stderr)
        self.assertIn('initialize PASS', result.stdout)
        self.assertTrue((self.work / ingest.STATE / 'seal.json').exists())
        self.assertFalse((self.work / 'stage0').exists())


if __name__ == '__main__':
    unittest.main()
