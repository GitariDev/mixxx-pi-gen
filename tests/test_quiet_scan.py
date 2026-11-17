import importlib.util
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from native.library_interface_runner import qt_available

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'library_interface_runner', ROOT / 'tests/native/library_interface_runner.py')
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)
PATCH = RUNNER.PATCH_DIR / 'mixxx-quiet-scan.patch'


class QuietScanPatchTests(unittest.TestCase):
    def test_patch_is_twentieth_and_only_changes_the_scanner_dialog(self):
        names = subprocess.check_output(
            ['bash', str(ROOT / 'stage3/01-install-packages/01-run.sh'),
             '--mixxx-print-patches'], text=True).split()
        self.assertEqual(names.index('mixxx-quiet-scan.patch'), 19)
        # Later patches leave the scanner dialog to this patch, except
        # mixxx-scan-progress.patch (R-12) and mixxx-scan-strip-fixes.patch,
        # which build on it.
        patch_dir = PATCH.parent
        for later in names[20:]:
            if later not in ('mixxx-scan-progress.patch', 'mixxx-scan-strip-fixes.patch'):
                self.assertNotIn('libraryscannerdlg', (patch_dir / later).read_text(), later)
        # The scan itself (LibraryScanner, tasks, DAO) is left untouched.
        self.assertEqual(re.findall(r'^diff --git a/(\S+) b/\S+$', PATCH.read_text(), re.MULTILINE),
                         ['src/library/scanner/libraryscannerdlg.cpp',
                          'src/library/scanner/libraryscannerdlg.h'])

    def test_full_stack_applies_and_reverses_on_pinned_source(self):
        with tempfile.TemporaryDirectory(prefix='mixpi-quiet-scan-stack-') as temporary:
            target = Path(temporary)
            names, baseline = RUNNER.reconstruct(target)
            self.assertIn('mixxx-quiet-scan.patch', names)
            # R-12 (mixxx-scan-progress.patch) makes the strip 48 px.
            self.assertIn('kStripHeight = 48',
                          (target / 'src/library/scanner/libraryscannerdlg.h').read_text())
            for name in reversed(names):
                for options in (['--check'], []):
                    subprocess.run(['git', 'apply', '--reverse', *options,
                                    str(RUNNER.PATCH_DIR / name)], cwd=target, check=True)
            restored = {str(path.relative_to(target)): path.read_bytes()
                        for path in target.rglob('*') if path.is_file()}
            self.assertEqual(baseline, restored)

    @unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
    def test_native_strip_above_transport_with_hide_cancel_and_percent(self):
        result = subprocess.run([sys.executable, '-B',
                                 str(ROOT / 'tests/native/library_scanner_strip_runner.py')],
                                cwd=ROOT, capture_output=True, text=True, timeout=240)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('LIBRARY_SCANNER_STRIP_OK height=48', result.stdout)


if __name__ == '__main__':
    unittest.main()
