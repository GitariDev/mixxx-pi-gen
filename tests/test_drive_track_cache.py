"""Wave J7: a drive's lists show that drive's tracks.

mixxx-drive-track-cache.patch: a rekordbox row draws its columns (title,
artist, location, ...) from the feature's BaseTrackCache by the row's id, and
LOAD reads its file from there too. With no drive left, stock Mixxx drops and
re-creates the rekordbox tables, so their AUTOINCREMENT ids start at 1 again;
the cache, built once, kept the ejected drive's rows under those ids, so the
next drive's lists showed the ejected drive's songs and paths (the owner,
2026-11-20: IXIAN's playlists showed GANDER1's Drake tracks). The patch builds
the cache again from the tables whenever a drive's export has been read
(before the list is shown) and whenever drives leave the menu (after their
tables are cleared), and a list in view whose playlist left is selected again
(empty), so no row cached for one drive is ever drawn for another.

The native checks are in tests/native/drive_track_cache_test.cpp.in, built by
tests/native/drive_track_cache_runner.py on the actual import with fake
exports of two drives.
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
PATCH = RUNNER.PATCH_DIR / 'mixxx-drive-track-cache.patch'
TEST = ROOT / 'tests/native/drive_track_cache_test.cpp.in'
FEATURE = 'src/library/rekordbox/rekordboxfeature.cpp'


def added(path):
    text = PATCH.read_text()
    start = text.index('diff --git a/' + path + ' ')
    end = text.find('\ndiff --git', start + 1)
    return '\n'.join(line[1:] for line in text[start:end if end > 0 else None].splitlines()
                     if line.startswith('+') and not line.startswith('+++'))


class DriveTrackCachePatchTests(unittest.TestCase):
    def test_patch_changes_only_the_rekordbox_feature(self):
        self.assertEqual(sorted(re.findall(r'^diff --git a/(\S+) b/\S+$', PATCH.read_text(), re.MULTILINE)),
                         [FEATURE, 'src/library/rekordbox/rekordboxfeature.h'])

    def test_patch_is_registered_after_the_drive_tracks_row(self):
        names = subprocess.check_output(['bash', str(ROOT / 'stage3/01-install-packages/01-run.sh'),
                                         '--mixxx-print-patches'], text=True).split()
        if PATCH.name not in names:
            self.skipTest(PATCH.name + ' is not registered yet')
        self.assertLess(names.index('mixxx-drive-tracks-row.patch'), names.index(PATCH.name))

    def test_cache_is_rebuilt_before_the_list_shows(self):
        feature = added(FEATURE)
        self.assertIn('m_trackSource->buildIndex();', feature)
        # Connected before onTracksFound, which shows the drive's list.
        self.assertRegex(feature, r'connect\(&m_tracksFutureWatcher,\s+&QFutureWatcher<QString>::finished,'
                                  r'\s+this,\s+&RekordboxFeature::resetTrackCache\);')
        # Drives leaving the menu (top-level rows removed after their tables
        # are cleared or dropped).
        self.assertIn('&QAbstractItemModel::rowsRemoved', feature)
        self.assertIn('m_pRekordboxPlaylistModel->select();', feature)

    def test_read_only(self):
        # Nothing written to a drive or to the tables: no SQL writes, no files.
        feature = added(FEATURE)
        for writer in ('INSERT', 'UPDATE', 'DELETE', 'DROP', 'ofstream', 'QIODevice::WriteOnly', '.write('):
            self.assertNotIn(writer, feature)

    @unittest.skipUnless(os.environ.get('MIXXX_TEST_SOURCE'), 'set MIXXX_TEST_SOURCE to the pinned Mixxx source')
    def test_other_fixtures_extracts_are_unchanged(self):
        # Fixtures that extract RekordboxFeature methods (drive_tracks_row,
        # import_cancellation, media_completion) and the parser stay as they
        # were: the patch adds constructor lines and two new methods only.
        import tempfile
        with tempfile.TemporaryDirectory(prefix='mixpi-drive-cache-src-') as temporary:
            target = Path(temporary)
            RUNNER.reconstruct(target, exclude=(PATCH.name,))
            base = (target / FEATURE).read_text()
            subprocess.run(['git', 'apply', str(PATCH)], cwd=target, check=True)
            source = (target / FEATURE).read_text()

        def function(text, signature):
            start = text.index(signature)
            return text[start:text.index('\n}\n', start) + 3]

        def parser(text):
            return text[text.index('template<typename Base, typename T>'):text.index('void setHotCue(')]

        self.assertEqual(parser(source), parser(base))
        for method in ('activateChild(', 'onTracksFound(', 'onRekordboxDevicesFound(', 'openRemovableDevice(',
                       'openRemovableDeviceAsync(', '~RekordboxFeature(', 'requestDeviceRefresh(',
                       'finishDeviceRefresh(', 'addDriveTracksRows(', 'selectShownDriveTracks('):
            signature = 'RekordboxFeature::' + method
            self.assertEqual(function(source, signature), function(base, signature), method)


@unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
class DriveTrackCacheNativeTests(unittest.TestCase):
    def run_fixture(self, *arguments):
        return subprocess.run([sys.executable, '-B', str(ROOT / 'tests/native/drive_track_cache_runner.py'),
                               *arguments], cwd=ROOT, capture_output=True, text=True, timeout=400)

    def test_native_drive_track_cache(self):
        result = self.run_fixture()
        print(result.stdout[-5000:], result.stderr[-2000:], flush=True)
        self.assertEqual(result.returncode, 0, result.stdout[-6000:] + result.stderr[-3000:])
        for check in checks(TEST):
            self.assertIn('PASS ' + check, result.stdout)
        self.assertNotIn('FAIL ', result.stdout)
        self.assertIn('OK 0', result.stdout)
        self.assertGreaterEqual(len(checks(TEST)), 20)

    def test_checks_fail_without_the_patch(self):
        result = self.run_fixture('--baseline')
        print(result.stdout[-5000:], result.stderr[-2000:], flush=True)
        self.assertNotEqual(result.returncode, 0)
        for check in ('after the eject the track cache holds no row of GANDER1',
                      'after the eject the list in view shows no row of GANDER1',
                      "IXIAN's Tracks lists its 7 tracks, not GANDER1's songs",
                      "each IXIAN row loads IXIAN's file, never a GANDER1 path",
                      "IXIAN's playlist Sunny shows its own 3 tracks and paths",
                      "after both drives left, IXIAN's Tracks shows only IXIAN's tracks"):
            self.assertIn('FAIL ' + check, result.stdout)


if __name__ == '__main__':
    unittest.main()
