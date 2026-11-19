"""Spec 2d (m-sources-sub.png): a "Tracks" row inside a rekordbox drive.

mixxx-drive-tracks-row.patch (build I): inside "DRIVE › rekordbox" in the
Sources menu the first row is "Tracks", with the music-note icon of This Pi's
Tracks row and no ›. It lists every track in the drive's export, in or out of
a playlist: Mixxx's import already fills the device's own playlist (named by
the drive's path) with every track row of export.pdb, and the row opens it the
way a playlist row opens its own. The row is added on the GUI thread through
the sidebar model after an import finishes; when the drive's whole list is in
Tracks (OPEN, ★, a tap on the drive) the feature selects the row, so the
menu's current-row edge sits on it. Nothing is written to the drive.

The native checks are in tests/native/drive_tracks_row_test.cpp.in, built by
tests/native/drive_tracks_row_runner.py on the actual import with a fake
export.pdb; the sidebar's side (the row first in the menu, the edge drawn on
it, an eject with it in view) is in tests/native/source_groups_test.cpp.
"""
from pathlib import Path
import os
import re
import subprocess
import sys
import unittest

from native.library_interface_runner import qt_available
from native import library_interface_runner as RUNNER
from test_sample_browser import checks

ROOT = Path(__file__).resolve().parents[1]
PATCH = RUNNER.PATCH_DIR / 'mixxx-drive-tracks-row.patch'
TEST = ROOT / 'tests/native/drive_tracks_row_test.cpp.in'
FEATURE = 'src/library/rekordbox/rekordboxfeature.cpp'


def added(path):
    text = PATCH.read_text()
    start = text.index('diff --git a/' + path + ' ')
    end = text.find('\ndiff --git', start + 1)
    return '\n'.join(line[1:] for line in text[start:end if end > 0 else None].splitlines()
                     if line.startswith('+') and not line.startswith('+++'))


def feature_sources():
    """rekordboxfeature.cpp with every registered patch, without and with this one."""
    import tempfile
    with tempfile.TemporaryDirectory(prefix='mixpi-drive-tracks-src-') as temporary:
        target = Path(temporary)
        RUNNER.reconstruct(target, exclude=(PATCH.name,))
        base = (target / FEATURE).read_text()
        subprocess.run(['git', 'apply', str(PATCH)], cwd=target, check=True)
        return base, (target / FEATURE).read_text()


class DriveTracksRowPatchTests(unittest.TestCase):
    def test_patch_changes_only_the_rekordbox_feature(self):
        self.assertEqual(sorted(re.findall(r'^diff --git a/(\S+) b/\S+$', PATCH.read_text(), re.MULTILINE)),
                         [FEATURE, 'src/library/rekordbox/rekordboxfeature.h'])

    def test_patch_is_registered_after_the_shared_columns(self):
        names = subprocess.check_output(['bash', str(ROOT / 'stage3/01-install-packages/01-run.sh'),
                                         '--mixxx-print-patches'], text=True).split()
        if PATCH.name not in names:
            self.skipTest(PATCH.name + ' is not registered yet')
        self.assertLess(names.index('mixxx-shared-columns-stretch.patch'), names.index(PATCH.name))

    def test_row_words_icon_and_list(self):
        feature = added(FEATURE)
        # Exact copy from the mockup, and This Pi's Tracks icon
        # (MixxxLibraryFeature's "tracks", at LibraryFeature's icon path).
        self.assertIn('QObject::tr("Tracks")', feature)
        self.assertIn('QIcon(QStringLiteral(":/images/library/ic_library_tracks.svg"))', feature)
        # The row opens the device's own list: the drive's path.
        self.assertIn('QList<QString>{device.getData().toList().value(0).toString(),', feature)
        # Added through the sidebar model, first; selected when its list shows.
        self.assertIn('m_pSidebarModel->insertTreeItemRows(std::move(rows), 0, m_pSidebarModel->index(row, 0));',
                      feature)
        self.assertIn('emit featureSelect(this, m_pSidebarModel->index(0, 0, m_pSidebarModel->index(row, 0)));',
                      feature)
        # Read only: the patch writes nothing (no SQL, no files).
        for writer in ('INSERT', 'UPDATE', 'DELETE', 'ofstream', 'QIODevice::WriteOnly', '.write('):
            self.assertNotIn(writer, feature)

    @unittest.skipUnless(os.environ.get('MIXXX_TEST_SOURCE'), 'set MIXXX_TEST_SOURCE to the pinned Mixxx source')
    def test_other_fixtures_extracts_are_unchanged(self):
        # The import's checkpoints (import_cancellation_runner.py counts 14)
        # and the methods other fixtures extract stay as they were; the new
        # helpers sit after the parser.
        base, source = feature_sources()

        def parser(text):
            return text[text.index('template<typename Base, typename T>'):text.index('void setHotCue(')]

        def function(text, signature):
            start = text.index(signature)
            return text[start:text.index('\n}\n', start) + 3]

        self.assertEqual(parser(source), parser(base))
        self.assertEqual(parser(source).count('operation->checkpoint();'), 14)
        self.assertGreater(source.index('bool isDriveTracksRow('), source.index('void readAnalyze('))
        for method in ('activateChild(', 'onTracksFound(', 'onRekordboxDevicesFound(', 'openRemovableDevice(',
                       'openRemovableDeviceAsync(', '~RekordboxFeature(', 'requestDeviceRefresh(',
                       'finishDeviceRefresh('):
            signature = 'RekordboxFeature::' + method
            self.assertEqual(function(source, signature), function(base, signature), method)


@unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
class DriveTracksRowNativeTests(unittest.TestCase):
    def run_fixture(self, *arguments):
        return subprocess.run([sys.executable, '-B', str(ROOT / 'tests/native/drive_tracks_row_runner.py'),
                               *arguments], cwd=ROOT, capture_output=True, text=True, timeout=300)

    def test_native_drive_tracks_row(self):
        result = self.run_fixture()
        print(result.stdout[-4000:], result.stderr[-2000:], flush=True)
        self.assertEqual(result.returncode, 0, result.stdout[-6000:] + result.stderr[-3000:])
        for check in checks(TEST):
            self.assertIn('PASS ' + check, result.stdout)
        self.assertNotIn('FAIL ', result.stdout)
        self.assertIn('OK 0', result.stdout)
        self.assertGreaterEqual(len(checks(TEST)), 12)

    def test_checks_fail_without_the_patch(self):
        result = self.run_fixture('--baseline')
        print(result.stdout[-4000:], result.stderr[-2000:], flush=True)
        self.assertNotEqual(result.returncode, 0)
        for check in ('inside the drive the first row is Tracks, then the export\'s playlists and folders as before',
                      'picking Tracks lists all 7 tracks of the export, tracks 5-7 (in no playlist) too',
                      'with Tracks picked, the edge sits on the Tracks row'):
            self.assertIn('FAIL ' + check, result.stdout)


if __name__ == '__main__':
    unittest.main()
