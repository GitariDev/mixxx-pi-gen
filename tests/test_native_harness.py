"""Portable regression checks for the required Linux gate and reconstruction."""
import importlib.util
import io
import os
import re
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from native import library_interface_runner as native

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('required_native', ROOT / 'tools/performance/required-native.py')
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class NativeHarnessTests(unittest.TestCase):
    def test_required_gate_includes_ram_cache_smoke_and_identity_holdouts(self):
        self.assertIn('test_ram_cache_identity', GATE.REQUIRED_TESTS)

    def test_reconstruction_follows_entire_live_recipe_without_inventing_patches(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            patches = root / 'patches'
            patches.mkdir()
            target = root / 'source'
            target.mkdir()
            (patches / 'first.patch').write_text(
                'diff --git a/current.h b/current.h\nnew file mode 100644\n'
                '--- /dev/null\n+++ b/current.h\n@@ -0,0 +1 @@\n+first\n')
            (patches / 'latest.patch').write_text(
                'diff --git a/current.h b/current.h\n--- a/current.h\n+++ b/current.h\n'
                '@@ -1 +1 @@\n-first\n+latest-recipe\n')
            def git_output(command, **options):
                if command[0] == 'bash':
                    return 'first.patch\nlatest.patch\n'
                if 'ls-tree' in command:
                    return ''
                self.fail('unexpected reconstruction input: ' + repr(command))
            with patch.object(native, 'source_reference', return_value=root), \
                    patch.object(native, 'PATCH_DIR', patches), \
                    patch.object(native.subprocess, 'check_output', side_effect=git_output):
                names, baseline = native.reconstruct(target)
            self.assertEqual(names, ['first.patch', 'latest.patch'])
            self.assertEqual(baseline, {})
            self.assertEqual((target / 'current.h').read_text(), 'latest-recipe\n')

    def test_publication_builds_and_release_need_composed_native_gate(self):
        for filename, jobs in (('main.yml', ('build', 'release')),
                               ('mixxx-deb.yml', ('package',)),
                               ('touchscreen-build.yml', ('image',))):
            workflow = (ROOT / '.github/workflows' / filename).read_text()
            self.assertIn('uses: ./.github/workflows/required-native.yml', workflow)
            for job in jobs:
                block = re.search(r'^  ' + job + r':\n(.*?)(?=^  [a-zA-Z][\w-]*:|\Z)',
                                  workflow, re.MULTILINE | re.DOTALL)[1]
                self.assertRegex(block, r'needs:.*required-native')
        required = (ROOT / '.github/workflows/required-native.yml').read_text()
        self.assertIn('runs-on: ubuntu-24.04', required)
        self.assertIn('tools/performance/required-native.py', required)
        self.assertIn('qt6-base-dev', required)
        self.assertIn('MIXXX_TEST_SOURCE=', required)
        self.assertNotIn('continue-on-error:', required)

    def test_linux_uses_pkg_config_not_apple_frameworks_even_on_arm64(self):
        with patch.object(native.platform, 'system', return_value='Linux'), \
                patch.object(native.platform, 'machine', return_value='arm64'), \
                patch.object(native.subprocess, 'check_output', return_value='-I/qt/include -lQt6Core') as query:
            flags = native.qt_flags(('QtCore',))
        query.assert_called_once_with(['pkg-config', '--cflags', '--libs', 'Qt6Core'],
                                      text=True, timeout=15)
        self.assertEqual(flags, ['-DQT_USE_QSTRINGBUILDER', '-fPIC', '-I/qt/include', '-lQt6Core'])
        self.assertNotIn('-framework', flags)
        self.assertNotIn('arm_acle.h', flags)

    def test_mac_frameworks_require_explicit_existing_sdk(self):
        with patch.object(native.platform, 'system', return_value='Darwin'), \
                patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, 'QT_SDK_PATH'):
                native.qt_flags()
        with tempfile.TemporaryDirectory() as directory:
            sdk = Path(directory)
            (sdk / 'lib/QtCore.framework/Headers').mkdir(parents=True)
            with patch.object(native.platform, 'system', return_value='Darwin'), \
                    patch.object(native.platform, 'machine', return_value='arm64'), \
                    patch.dict(os.environ, {'QT_SDK_PATH': directory}):
                flags = native.qt_flags(('QtCore',))
            self.assertIn('-framework', flags)
            self.assertIn('-DQT_USE_QSTRINGBUILDER', flags)
            self.assertIn('arm_acle.h', flags)

    def test_source_is_explicit_and_validated_at_recipe_pin_not_head(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, 'MIXXX_TEST_SOURCE'):
                native.source_reference()
        with tempfile.TemporaryDirectory() as directory, \
                patch.dict(os.environ, {'MIXXX_TEST_SOURCE': directory}), \
                patch.object(native.subprocess, 'run') as command:
            self.assertEqual(native.source_reference(), Path(directory).resolve())
        self.assertEqual(command.call_args.args[0][-1], native.source_pin() + '^{commit}')
        self.assertTrue(command.call_args.kwargs['check'])

    def test_missing_source_commit_is_an_error_not_skip(self):
        with patch.dict(os.environ, {'MIXXX_TEST_SOURCE': '/missing-source'}), \
                patch.object(native.subprocess, 'run', side_effect=subprocess.CalledProcessError(128, 'git')):
            with self.assertRaises(subprocess.CalledProcessError):
                native.source_reference()

    def test_missing_required_tool_fails(self):
        with patch.object(GATE.platform, 'system', return_value='Linux'), \
                patch.object(GATE.shutil, 'which', return_value=None):
            with self.assertRaisesRegex(RuntimeError, 'tool missing'):
                GATE.prerequisites()

    def test_non_linux_gate_refuses_instead_of_claiming_ipc(self):
        with patch.object(GATE.platform, 'system', return_value='Darwin'):
            with self.assertRaisesRegex(RuntimeError, 'cannot run on Darwin'):
                GATE.prerequisites()

    def test_required_missing_source_qt_moc_and_sndfile_fail(self):
        for dependency in ('source_reference', 'qt_flags', 'moc_path', 'sndfile_flags'):
            with self.subTest(dependency=dependency), \
                    patch.object(GATE.platform, 'system', return_value='Linux'), \
                    patch.object(GATE.shutil, 'which', return_value='/tool'), \
                    patch.dict(os.environ, {}, clear=True), \
                    patch.object(GATE.os, 'pidfd_open', return_value=123, create=True), \
                    patch.object(GATE.os, 'close'), \
                    patch.object(GATE, 'source_reference', return_value=Path('/source')), \
                    patch.object(GATE, 'qt_flags'), patch.object(GATE, 'moc_path'), \
                    patch.object(GATE, 'sndfile_flags'), \
                    patch.object(GATE, dependency, side_effect=RuntimeError('missing ' + dependency)):
                with self.assertRaisesRegex(RuntimeError, 'missing ' + dependency):
                    GATE.prerequisites()

    def test_required_checks_refuse_skips_and_expected_failures(self):
        def skipped():
            raise unittest.SkipTest('missing native prerequisite')
        cases = [unittest.FunctionTestCase(skipped)]
        class ExpectedFailure(unittest.TestCase):
            @unittest.expectedFailure
            def runTest(self):
                self.fail('not accepted evidence')
        cases.append(ExpectedFailure())
        for case in cases:
            with self.subTest(case=type(case).__name__), patch('sys.stderr', io.StringIO()):
                self.assertFalse(GATE.run_required(unittest.TestSuite([case]), io.StringIO()))

    def test_required_green_and_empty_suite(self):
        self.assertTrue(GATE.run_required(unittest.TestSuite([
            unittest.FunctionTestCase(lambda: None)]), io.StringIO()))
        with self.assertRaisesRegex(RuntimeError, 'empty'):
            GATE.run_required(unittest.TestSuite(), io.StringIO())

    def test_every_named_required_check_must_contain_tests(self):
        loader = Mock()
        loader.loadTestsFromName.return_value = unittest.TestSuite()
        with self.assertRaisesRegex(RuntimeError, 'check is empty'):
            GATE.required_suite(loader)

    def test_required_gate_refuses_baseline_and_candidate_overrides(self):
        for name in GATE.FORBIDDEN_OVERRIDES:
            with self.subTest(name=name), patch.object(GATE.platform, 'system', return_value='Linux'), \
                    patch.object(GATE.shutil, 'which', return_value='/tool'), \
                    patch.dict(os.environ, {name: '1'}):
                with self.assertRaisesRegex(RuntimeError, 'refuses override'):
                    GATE.prerequisites()


if __name__ == '__main__':
    unittest.main()
