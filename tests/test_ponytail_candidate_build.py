"""Small source/DEB fixtures; never compile, install, or execute Mixxx."""

import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools/performance/mixxx-candidate.py'
SPEC = importlib.util.spec_from_file_location('ponytail_candidate', TOOL)
candidate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(candidate)


def executable(machine=183, interpreter=b'/lib/ld-linux-aarch64.so.1\0'):
    header = struct.pack('<16sHHIQQQIHHHHHH', b'\x7fELF\x02\x01\x01' + bytes(9),
                         3, machine, 1, 0, 64, 0, 0, 64, 56, 1, 0, 0, 0)
    segment = struct.pack('<IIQQQQQQ', 3, 4, 120, 0, 0, len(interpreter), len(interpreter), 1)
    return header + segment + interpreter


def payload(binary=None, name='./usr/bin/mixxx', duplicate=False, symlink=False):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w') as archive:
        member = tarfile.TarInfo(name)
        member.mode = 0o755
        if symlink:
            member.type = tarfile.SYMTYPE
            member.linkname = 'elsewhere'
            archive.addfile(member)
        else:
            data = executable() if binary is None else binary
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
            if duplicate:
                archive.addfile(member, io.BytesIO(data))
    return output.getvalue()


class CandidateResourceTests(unittest.TestCase):
    def test_defaults_are_small_compressed_and_not_cpu_derived(self):
        settings = candidate.resource_settings({})
        self.assertEqual(settings['CMAKE_BUILD_PARALLEL_LEVEL'], '2')
        self.assertEqual(settings['CTEST_PARALLEL_LEVEL'], '2')
        self.assertEqual(settings['CCACHE_MAXSIZE'], '1G')
        self.assertEqual(settings['CCACHE_COMPRESS'], 'true')

    def test_explicit_limits_and_compression_survive(self):
        settings = candidate.resource_settings({'CMAKE_BUILD_PARALLEL_LEVEL': '1',
            'CTEST_PARALLEL_LEVEL': '3', 'CCACHE_MAXSIZE': '256M', 'CCACHE_COMPRESS': 'false'})
        self.assertEqual(settings['CMAKE_BUILD_PARALLEL_LEVEL'], '1')
        self.assertEqual(settings['CTEST_PARALLEL_LEVEL'], '3')
        self.assertEqual(settings['CCACHE_MAXSIZE'], '256M')
        self.assertEqual(settings['CCACHE_COMPRESS'], 'false')

    def test_invalid_or_unbounded_settings_fail_closed(self):
        for key, values in {
            'CMAKE_BUILD_PARALLEL_LEVEL': ['', '0', '-1', '65', 'auto', '1;exit 0'],
            'CTEST_PARALLEL_LEVEL': ['', '0', '999999'],
            'CCACHE_MAXSIZE': ['', '0', '10G', '5G', '-1G', 'unlimited'],
            'CCACHE_COMPRESS': ['', 'yes', 'FALSE'],
            'CCACHE_COMPRESSLEVEL': ['', '20', '-6', 'abc'],
        }.items():
            for value in values:
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    candidate.resource_settings({key: value})

    def test_legacy_nocompress_is_normalized_and_conflicts_refused(self):
        self.assertEqual(candidate.resource_settings({'CCACHE_NOCOMPRESS': 'true'})[
            'CCACHE_COMPRESS'], 'false')
        with self.assertRaises(ValueError):
            candidate.resource_settings({'CCACHE_NOCOMPRESS': 'true', 'CCACHE_COMPRESS': 'true'})

    def test_shell_exports_use_ccache_boolean_semantics(self):
        for compression in ('true', 'false'):
            environment = {**os.environ, 'CCACHE_COMPRESS': compression}
            for key in ('MIXXX_CCACHE_COMPRESSION', 'CCACHE_NOCOMPRESS'):
                environment.pop(key, None)
            exports = subprocess.check_output(['python3', str(TOOL), 'resources'],
                                              env=environment, text=True)
            result = subprocess.check_output(['bash', '-c', exports + '\n'
                'printf "%s|%s|%s|%s" "${CCACHE_COMPRESS-unset}" "${CCACHE_NOCOMPRESS-unset}" '
                '"$MIXXX_CCACHE_COMPRESSION" "$CMAKE_BUILD_PARALLEL_LEVEL"'], env=environment, text=True)
            self.assertEqual(result, ('true|unset|true|2' if compression == 'true'
                                      else 'unset|true|false|2'))


class CandidateSourceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'user.name', 'Fixture')
        (self.source / 'original.cpp').write_text('original\n')
        (self.source / '.gitignore').write_text('build/\nnew.cpp\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'fixture')
        self.commit = self.git('rev-parse', 'HEAD').strip()
        self.patch_file = self.root / 'new.patch'
        self.patch_file.write_text('diff --git a/new.cpp b/new.cpp\nnew file mode 100644\n'
            '--- /dev/null\n+++ b/new.cpp\n@@ -0,0 +1 @@\n+patched\n')
        self.git('apply', str(self.patch_file))

    def git(self, *arguments):
        return subprocess.check_output(['git', '-C', str(self.source), *arguments], text=True)

    def identity(self):
        return candidate.source_identity(self.source, self.commit, [self.patch_file])

    def test_ignored_new_patch_files_are_bound_and_build_is_excluded(self):
        before = self.identity()
        self.assertIn('new.cpp', [entry['path'] for entry in before['files']])
        (self.source / 'build').mkdir()
        (self.source / 'build/generated').write_text('not source')
        self.assertEqual(before, self.identity())
        (self.source / 'new.cpp').write_text('changed\n')
        self.assertNotEqual(before['sha256'], self.identity()['sha256'])

    def test_deleted_tracked_file_changes_identity(self):
        before = self.identity()
        (self.source / 'original.cpp').unlink()
        self.assertNotEqual(before['sha256'], self.identity()['sha256'])

    def test_pin_mismatch_and_escaping_symlink_fail(self):
        with self.assertRaises(ValueError):
            candidate.source_identity(self.source, '0' * 40, [self.patch_file])
        (self.source / 'escape').symlink_to('../outside')
        with self.assertRaises(ValueError):
            self.identity()

    def prepare(self):
        recipe = self.root / 'recipe.sh'
        recipe.write_text('fixture recipe\n')
        versions = self.root / 'source-versions'
        versions.write_text('fixture source pins\n')
        args = SimpleNamespace(source=self.source, recipe=recipe, source_versions=versions,
            ref='fixture-ref', commit=self.commit, patch=[self.patch_file],
            cmake_flag=['-DCMAKE_BUILD_TYPE=Release', '-DBUILD_TESTING=OFF'])
        original_command = candidate.command

        def commands(arguments):
            if arguments == ['dpkg', '--print-architecture']:
                return 'arm64'
            return original_command(arguments)

        with patch.object(candidate, 'command', side_effect=commands):
            candidate.prepare(args)
        return args

    def configured_package(self):
        self.prepare()
        build = self.source / 'build'
        (build / 'CMakeCache.txt').write_text('CMAKE_C_COMPILER:FILEPATH=/fixture/cc\n'
                                          'CMAKE_CXX_COMPILER:FILEPATH=/fixture/c++\n')
        (build / 'CPackConfig.cmake').write_text('fixture cpack settings\n')
        candidate.configured(SimpleNamespace(output_dir=build))
        package = build / 'mixxx.deb'
        package.write_bytes(b'fixture DEB')
        return build, package

    def fake_package_identity(self, package, architecture):
        return {'name': package.name, **candidate.file_record(package),
                'metadata': {'Package': 'mixxx', 'Version': 'fixture', 'Architecture': architecture},
                'binary': {'sha256': hashlib.sha256(executable()).hexdigest(),
                           'size': len(executable()), 'mode': 0o755}}

    def test_prepare_emit_verify_bind_exact_candidate(self):
        with patch.dict(os.environ, {}, clear=True), \
                patch.object(candidate, 'tool_identity', side_effect=lambda name: {'fixture': name}), \
                patch.object(candidate, 'packaged_identity', side_effect=self.fake_package_identity):
            build, package = self.configured_package()
            candidate.emit(SimpleNamespace(output_dir=build))
            manifest = json.loads(package.with_name(package.name + '.candidate.json').read_text())
            self.assertFalse(manifest['approval'])
            self.assertEqual(manifest['source'], self.identity())
            self.assertEqual(manifest['upstream']['commit'], self.commit)
            self.assertEqual(manifest['patches'][0]['sha256'], candidate.file_record(self.patch_file)['sha256'])
            self.assertEqual(manifest['cmake_flags'], ['-DCMAKE_BUILD_TYPE=Release', '-DBUILD_TESTING=OFF'])
            candidate.verify(SimpleNamespace(output_dir=build, installed=None))
            package.write_bytes(b'changed DEB')
            with self.assertRaisesRegex(ValueError, 'DEB/manifest'):
                candidate.verify(SimpleNamespace(output_dir=build, installed=None))

    def test_emission_refuses_changed_composed_source_and_recipe(self):
        with patch.dict(os.environ, {}, clear=True), \
                patch.object(candidate, 'tool_identity', side_effect=lambda name: {'fixture': name}):
            build, package = self.configured_package()
            (self.source / 'new.cpp').write_text('changed source\n')
            with self.assertRaisesRegex(ValueError, 'composed source changed'):
                candidate.emit(SimpleNamespace(output_dir=build))
            (self.source / 'new.cpp').write_text('patched\n')
            (self.root / 'recipe.sh').write_text('changed recipe\n')
            with self.assertRaisesRegex(ValueError, 'build input changed'):
                candidate.emit(SimpleNamespace(output_dir=build))
            self.assertFalse(package.with_name(package.name + '.candidate.json').exists())

    def test_emission_refuses_changed_patch_settings_and_tools(self):
        with patch.dict(os.environ, {}, clear=True), \
                patch.object(candidate, 'tool_identity', side_effect=lambda name: {'fixture': name}):
            build, package = self.configured_package()
            original = self.patch_file.read_bytes()
            self.patch_file.write_bytes(original + b'\n')
            with self.assertRaisesRegex(ValueError, 'build input changed'):
                candidate.emit(SimpleNamespace(output_dir=build))
            self.patch_file.write_bytes(original)
            with patch.dict(os.environ, {'CTEST_PARALLEL_LEVEL': '1'}):
                with self.assertRaisesRegex(ValueError, 'settings changed'):
                    candidate.emit(SimpleNamespace(output_dir=build))
            with patch.object(candidate, 'tool_identity', return_value={'fixture': 'changed tool'}):
                with self.assertRaisesRegex(ValueError, 'tool changed'):
                    candidate.emit(SimpleNamespace(output_dir=build))

    def test_emission_refuses_configuration_changed_after_configure(self):
        with patch.dict(os.environ, {}, clear=True), \
                patch.object(candidate, 'tool_identity', side_effect=lambda name: {'fixture': name}):
            build, package = self.configured_package()
            (build / 'CPackConfig.cmake').write_text('stale or replaced configuration\n')
            with self.assertRaisesRegex(ValueError, 'configured build inputs changed'):
                candidate.emit(SimpleNamespace(output_dir=build))

    def test_manifest_tamper_and_installed_copy_mismatch_are_refused(self):
        with patch.dict(os.environ, {}, clear=True), \
                patch.object(candidate, 'tool_identity', side_effect=lambda name: {'fixture': name}), \
                patch.object(candidate, 'packaged_identity', side_effect=self.fake_package_identity):
            build, package = self.configured_package()
            candidate.emit(SimpleNamespace(output_dir=build))
            installed = self.root / 'installed-mixxx'
            installed.write_bytes(b'wrong installed bytes')
            with self.assertRaisesRegex(ValueError, 'installed /usr/bin/mixxx'):
                candidate.verify(SimpleNamespace(output_dir=build, installed=installed))
            installed.write_bytes(executable())
            installed.chmod(0o755)
            metadata = {
                'dpkg': 'arm64',
                '-W': 'install ok installed mixxx arm64 fixture',
                '-S': 'mixxx: /usr/bin/mixxx',
            }
            with patch.object(candidate, 'command', side_effect=lambda args: metadata[
                    args[0] if args[0] == 'dpkg' else args[1]]):
                candidate.verify(SimpleNamespace(output_dir=build, installed=installed))
                metadata['-S'] = 'other-package: /usr/bin/mixxx'
                with self.assertRaisesRegex(ValueError, 'ownership mismatch'):
                    candidate.verify(SimpleNamespace(output_dir=build, installed=installed))
            sidecar = package.with_name(package.name + '.candidate.json')
            manifest = json.loads(sidecar.read_text())
            manifest['settings']['CMAKE_BUILD_PARALLEL_LEVEL'] = '9'
            sidecar.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'manifest digest mismatch'):
                candidate.verify(SimpleNamespace(output_dir=build, installed=None))
            manifest['approval'] = True
            sidecar.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'not a candidate manifest'):
                candidate.verify(SimpleNamespace(output_dir=build, installed=None))

    def test_prepare_refuses_stale_build(self):
        (self.source / 'build').mkdir()
        with self.assertRaisesRegex(ValueError, 'stale build'):
            self.prepare()


class CandidatePackageTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.deb = self.root / 'mixxx.deb'
        self.deb.write_bytes(b'fixture-deb-not-the-payload')

    def inspect(self, data=None, architecture='arm64'):
        archive_data = payload() if data is None else data
        process = unittest.mock.MagicMock()
        process.stdout = io.BytesIO(archive_data)
        process.wait.return_value = 0
        process.__enter__.return_value = process
        with patch.object(candidate, 'command', side_effect=lambda args: {
                'Package': 'mixxx', 'Version': '2.5.6+rmodified-1',
                'Architecture': 'arm64'}[args[-1]]), \
                patch.object(candidate.subprocess, 'Popen', return_value=process):
            return candidate.packaged_identity(self.deb, architecture)

    def test_deb_and_independently_extracted_binary_hashes_differ(self):
        result = self.inspect()
        self.assertEqual(result['sha256'], hashlib.sha256(self.deb.read_bytes()).hexdigest())
        self.assertEqual(result['binary']['sha256'], hashlib.sha256(executable()).hexdigest())
        self.assertNotEqual(result['sha256'], result['binary']['sha256'])
        self.assertEqual(result['binary']['elf']['machine'], 183)
        self.assertEqual(result['binary']['elf']['interpreter'], '/lib/ld-linux-aarch64.so.1')

    def test_absent_duplicate_unsafe_linked_or_wrong_arch_binary_refused(self):
        for data in (payload(name='./other'), payload(duplicate=True), payload(symlink=True),
                     payload(name='../usr/bin/mixxx'), payload(binary=executable(machine=62)),
                     payload(binary=b'not ELF')):
            with self.subTest(data=data[:32]), self.assertRaises(ValueError):
                self.inspect(data)
        with self.assertRaises(ValueError):
            self.inspect(architecture='amd64')

    def test_extraction_failure_and_binary_alias_are_refused(self):
        with self.assertRaises(ValueError):
            self.inspect(payload(name='usr//bin/./mixxx', duplicate=True))
        with patch.object(candidate.subprocess, 'Popen') as constructor, \
                patch.object(candidate, 'command', side_effect=lambda args: {
                    'Package': 'mixxx', 'Version': 'fixture', 'Architecture': 'arm64'}[args[-1]]):
            process = constructor.return_value.__enter__.return_value
            process.stdout = io.BytesIO(payload())
            process.wait.return_value = 7
            with self.assertRaisesRegex(ValueError, 'extraction failed'):
                candidate.packaged_identity(self.deb, 'arm64')

    def test_output_set_refuses_absent_extra_stale_or_symlink(self):
        self.assertEqual(candidate.package_output(self.root), self.deb)
        extra = self.root / 'extra.deb'
        extra.write_bytes(b'extra')
        with self.assertRaises(ValueError):
            candidate.package_output(self.root)
        extra.unlink()
        self.deb.with_name('old.deb.candidate.json').write_text('{}')
        with self.assertRaises(ValueError):
            candidate.package_output(self.root)
        self.deb.with_name('old.deb.candidate.json').unlink()
        self.deb.unlink()
        with self.assertRaises(ValueError):
            candidate.package_output(self.root)
        outside = self.root / 'outside'
        outside.write_bytes(b'do not follow')
        self.deb.symlink_to(outside)
        with self.assertRaises(ValueError):
            candidate.package_output(self.root)

    @unittest.skipUnless(shutil.which('dpkg-deb'), 'dpkg-deb unavailable on this host')
    def test_real_minimal_deb_extraction(self):
        package_root = self.root / 'pkg'
        (package_root / 'DEBIAN').mkdir(parents=True)
        (package_root / 'DEBIAN/control').write_text('Package: mixxx\nVersion: 2.5.6+rmodified-1\n'
            'Architecture: arm64\nMaintainer: Fixture <fixture@example.invalid>\nDescription: fixture\n')
        (package_root / 'usr/bin').mkdir(parents=True)
        binary = package_root / 'usr/bin/mixxx'
        binary.write_bytes(executable())
        binary.chmod(0o755)
        subprocess.run(['dpkg-deb', '--build', str(package_root), str(self.deb)], check=True,
                       stdout=subprocess.DEVNULL)
        result = candidate.packaged_identity(self.deb, 'arm64')
        self.assertEqual(result['binary']['sha256'], hashlib.sha256(executable()).hexdigest())


class CandidateRecipeTests(unittest.TestCase):
    def test_package_mode_honors_limits_with_mocked_build_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            recipe = root / 'stage3/01-install-packages/01-run.sh'
            recipe.parent.mkdir(parents=True)
            opt = root / 'opt'
            opt.mkdir()
            original = (ROOT / 'stage3/01-install-packages/01-run.sh').read_text()
            recipe.write_text(original.replace('/opt/mixxx.version', str(opt / 'mixxx.version'))
                              .replace('/opt/mixxx.tag', str(opt / 'mixxx.tag')))
            helper = root / 'tools/performance/mixxx-candidate.py'
            helper.parent.mkdir(parents=True)
            shutil.copyfile(TOOL, helper)
            shutil.copyfile(ROOT / 'source-versions', root / 'source-versions')
            patch_directory = root / 'patch files'
            patch_directory.mkdir()
            names = subprocess.check_output(['bash', str(recipe), '--mixxx-print-patches'], text=True).splitlines()
            for name in names:
                (patch_directory / name).write_bytes(b'fixture patch')
            environment = {**os.environ, 'FIXTURE_ROOT': str(root), 'MIXXX_REF': 'fixture',
                'MIXXX_COMMIT': '0' * 40, 'CMAKE_BUILD_PARALLEL_LEVEL': '1',
                'CTEST_PARALLEL_LEVEL': '3', 'CCACHE_MAXSIZE': '256M', 'CCACHE_COMPRESS': 'true'}
            for key in ('CCACHE_NOCOMPRESS', 'MIXXX_CCACHE_COMPRESSION',
                        'MIXXX_TOUCH_SMOKE_SCRIPT', 'MIXXX_CACHE_SMOKE_SCRIPT'):
                environment.pop(key, None)
            script = r'''
set -eu
python3() {
    case "${2:-}" in
        prepare|configured|emit|verify) printf '%s\n' "$2" >> "$FIXTURE_ROOT/helper-calls" ;;
        *) command python3 "$@" ;;
    esac
}
git() {
    case "$1" in
        clone)
            for destination in "$@"; do :; done
            mkdir -p "$destination/tools"
            printf '#!/bin/bash\nexit 0\n' > "$destination/tools/debian_buildenv.sh"
            chmod 755 "$destination/tools/debian_buildenv.sh"
            ;;
        rev-parse) printf '%s\n' "$MIXXX_COMMIT" ;;
        describe) printf fixture ;;
        apply) : ;;
        *) return 97 ;;
    esac
}
ccache() { printf '%s\n' "$*" >> "$FIXTURE_ROOT/ccache-calls"; }
nproc() { printf 24; }
cmake() {
    printf 'jobs=%s tests=%s compression=%s nocompress=%s cache=%s\n' \
        "$CMAKE_BUILD_PARALLEL_LEVEL" "$CTEST_PARALLEL_LEVEL" "${CCACHE_COMPRESS-unset}" \
        "${CCACHE_NOCOMPRESS-unset}" "$CCACHE_MAXSIZE" >> "$FIXTURE_ROOT/cmake-environment"
    mkdir -p "$FIXTURE_ROOT/source/build"
}
cpack() { :; }
export -f python3 git ccache nproc cmake cpack
bash "$FIXTURE_ROOT/stage3/01-install-packages/01-run.sh" --mixxx-package \
    "$FIXTURE_ROOT/patch files" "$FIXTURE_ROOT/source" "$FIXTURE_ROOT/cache"
'''
            result = subprocess.run(['bash', '-c', script], env=environment, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((root / 'cmake-environment').read_text().splitlines(),
                ['jobs=1 tests=3 compression=true nocompress=unset cache=256M'] * 2)
            self.assertIn('-M 256M', (root / 'ccache-calls').read_text())
            self.assertNotIn('10G', (root / 'ccache-calls').read_text())
            self.assertEqual((root / 'helper-calls').read_text().splitlines(),
                             ['prepare', 'configured', 'emit', 'verify'])

    def test_missing_helper_fails_before_clone(self):
        with tempfile.TemporaryDirectory() as directory:
            recipe = Path(directory) / 'stage3/01-install-packages/01-run.sh'
            recipe.parent.mkdir(parents=True)
            shutil.copyfile(ROOT / 'stage3/01-install-packages/01-run.sh', recipe)
            env = {**os.environ, 'MIXXX_REF': 'fixture', 'MIXXX_COMMIT': '0' * 40}
            result = subprocess.run(['bash', str(recipe), '--mixxx-package', directory,
                str(Path(directory) / 'must-not-be-cloned')], env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('candidate helper', result.stderr)
            self.assertFalse((Path(directory) / 'must-not-be-cloned').exists())

    def test_disposable_root_copies_helpers_resources_and_sidecars_without_building(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            runtime = root / 'runtime'
            runtime.mkdir()
            work = root / 'work'
            work.mkdir()
            deploy = root / 'deploy'
            deploy.mkdir()
            environment = {**os.environ, 'ROOTFS_DIR': str(runtime), 'STAGE_WORK_DIR': str(work),
                'BASE_DIR': str(root / 'base'), 'DEPLOY_DIR': str(deploy),
                'MIXXX_REF': 'fixture-ref', 'MIXXX_COMMIT': '0' * 40,
                'CMAKE_BUILD_PARALLEL_LEVEL': '1', 'CTEST_PARALLEL_LEVEL': '3',
                'CCACHE_MAXSIZE': '256M', 'CCACHE_COMPRESS': 'true', 'FIXTURE_ROOT': str(root)}
            for key in ('MIXXX_CCACHE_COMPRESSION', 'CCACHE_NOCOMPRESS'):
                environment.pop(key, None)
            script = r'''
set -eu
rsync() { :; }
mount() { :; }
unmount() { :; }
python3() {
    if [ "${2:-}" = verify ]; then
        printf '%s\n' "$*" >> "$FIXTURE_ROOT/verify-calls"
    else
        command python3 "$@"
    fi
}
on_chroot() {
    if [ -e "$FIXTURE_ROOT/build-commands" ]; then
        cat > "$FIXTURE_ROOT/install-commands"
    else
        cat > "$FIXTURE_ROOT/build-commands"
        inputs="$ROOTFS_DIR/opt/mixpi-build-inputs"
        test -f "$inputs/stage3/01-install-packages/01-run.sh"
        test -f "$inputs/tools/performance/mixxx-candidate.py"
        test -f "$inputs/source-versions"
        cmp "$inputs/tools/performance/mixxx-candidate.py" "$REAL_CANDIDATE_HELPER"
        mkdir -p "$ROOTFS_DIR/code/build"
        printf fixture > "$ROOTFS_DIR/code/build/mixxx.deb"
        printf fixture > "$ROOTFS_DIR/code/build/mixxx.deb.candidate.json"
        printf commit > "$ROOTFS_DIR/opt/mixxx.version"
        printf tag > "$ROOTFS_DIR/opt/mixxx.tag"
    fi
}
export -f rsync mount unmount python3 on_chroot
bash ./01-run.sh
'''
            environment['REAL_CANDIDATE_HELPER'] = str(TOOL)
            result = subprocess.run(['bash', '-c', script], env=environment,
                cwd=ROOT / 'stage3/01-install-packages', capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            commands = (root / 'build-commands').read_text()
            for expected in ('export CMAKE_BUILD_PARALLEL_LEVEL=1', 'export CTEST_PARALLEL_LEVEL=3',
                             'export CCACHE_MAXSIZE=256M', 'export CCACHE_COMPRESS=true',
                             '/opt/mixpi-build-inputs/stage3/01-install-packages/01-run.sh'):
                self.assertIn(expected, commands)
            self.assertTrue((deploy / 'mixxx.deb.candidate.json').is_file())
            self.assertTrue((runtime / 'opt/mixxx-package/mixxx.deb.candidate.json').is_file())
            commands = (root / 'install-commands').read_text()
            self.assertLess(commands.index(' verify '), commands.index('apt-get update'))
            self.assertIn('--installed /usr/bin/mixxx', commands)
            self.assertIn('/opt/mixxx.candidate.json', commands)
            self.assertFalse(list(work.iterdir()))

    def test_invalid_resource_fails_before_clone(self):
        environment = {**os.environ, 'CMAKE_BUILD_PARALLEL_LEVEL': '0'}
        result = subprocess.run(['bash', str(ROOT / 'stage3/01-install-packages/01-run.sh'),
            '--mixxx-package', '/unused'], env=environment, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('must be an integer', result.stderr)


if __name__ == '__main__':
    unittest.main()
