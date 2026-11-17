"""R-12: the scan bar shows the file name only, has Hide and Cancel, keeps a
saved Hide, sits above the transport row and reports a percent.

The strip itself is checked natively by tests/native/library_scanner_strip_test.cpp
(run from tests/test_quiet_scan.py). This module checks the patch scope and
that the repaint check catches the old label.
"""
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
PATCH = RUNNER.PATCH_DIR / 'mixxx-scan-progress.patch'
SCANNER = 'src/library/scanner/'


def patch_names():
    return subprocess.check_output(['bash', str(ROOT / 'stage3/01-install-packages/01-run.sh'),
                                    '--mixxx-print-patches'], text=True).split()


class ScanProgressPatchTests(unittest.TestCase):
    def test_patch_changes_only_the_scanner_and_its_strip(self):
        self.assertEqual(re.findall(r'^diff --git a/(\S+) b/\S+$', PATCH.read_text(), re.MULTILINE),
                         [SCANNER + name for name in ('libraryscanner.h', 'libraryscanner.cpp',
                                                      'libraryscannerdlg.h', 'libraryscannerdlg.cpp')])

    def test_patch_follows_the_strip_and_the_scanner_media_lease(self):
        names = patch_names()
        self.assertIn('mixxx-scan-progress.patch', names)
        for earlier in ('mixxx-quiet-scan.patch', 'mixxx-media-selection.patch'):
            self.assertLess(names.index(earlier), names.index('mixxx-scan-progress.patch'), earlier)

    def test_patched_strip_names_size_controls_and_saved_hide(self):
        with tempfile.TemporaryDirectory(prefix='mixpi-scan-progress-') as temporary:
            target = Path(temporary)
            RUNNER.reconstruct(target)
            header = (target / SCANNER / 'libraryscannerdlg.h').read_text()
            dialog = (target / SCANNER / 'libraryscannerdlg.cpp').read_text()
            scanner = (target / SCANNER / 'libraryscanner.cpp').read_text()
        self.assertIn('kStripHeight = 48', header)
        self.assertIn('kTransportHeight = 56', header)
        for text in ('"ScanBarHidden"', '"scan_active"', '"scan_percent"', '"scan_bar_hidden"',
                     'QStringLiteral("screen")', 'tr("Scanning · %1")', 'tr("Hide")', 'tr("Cancel")',
                     'Qt::ElideRight', 'painter.fillRect(rect(), kStripBackground);',
                     'pHost->height() - kTransportHeight - kStripHeight',
                     'mixxx::Duration::fromSeconds(2)'):
            self.assertIn(text, dialog)
        self.assertNotIn('Qt::ElideMiddle', dialog)
        self.assertNotIn('setRange(0, 0)', dialog)
        # The count runs once on the scanner thread, before work is queued.
        start = scanner.index('void LibraryScanner::slotStartScan()')
        self.assertLess(scanner.index('mixpi::countScanFolders(roots)', start),
                        scanner.index('queueTask(new RecursiveScanDirectoryTask(', start))
        self.assertEqual(scanner.count('if (m_scanPercent.folderDone())'), 2)
        self.assertIn('new LibraryScannerDlg(pConfig)', scanner)

    @unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
    def test_repaint_check_fails_for_a_label_without_its_own_background(self):
        # The plan's "overdrawn text" step: the label as it was (no background
        # of its own) leaves pixels of the previous name; the fixture sees it.
        result = subprocess.run([sys.executable, '-B',
                                 str(ROOT / 'tests/native/library_scanner_strip_runner.py'),
                                 '--label-without-background'],
                                cwd=ROOT, capture_output=True, text=True, timeout=240)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn('FAIL repaintLeavesNoOldPixels(', result.stderr)
        self.assertNotIn('LIBRARY_SCANNER_STRIP_OK', result.stdout)


if __name__ == '__main__':
    unittest.main()
