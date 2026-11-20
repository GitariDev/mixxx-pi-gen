"""Spec 2e (build J, wave J4): after an eject, the menu and the table.

Owner, 2026-11-20: "Let just land on the top menu instead". When the drive
whose list is in the Tracks table is ejected (from the Media page) or pulled
out:
- the table stops showing its rows (RekordboxFeature::releaseRemovedDrives
  points RekordboxPlaylistModel at no list: releasePlaylist), also after the
  drive comes back and its lists take the old ids;
- the Sources menu lands on its top level, so the next ☰ opens there, and no
  row has the current-row edge (WLibrarySidebar::rowsAboutToBeRemoved).
Another drive going, or a list of This Pi in Tracks, changes nothing. The
saved ★ start is not touched, the eject's own release of the drive's views
(refreshMediaLifecycle) is unchanged, and nothing is written to the drive.

mixxx-eject-top-menu.patch. The table's checks are in
tests/native/eject_top_menu_test.cpp.in (built by
tests/native/eject_top_menu_runner.py); the menu's are in
tests/native/source_groups_test.cpp (test_source_groups.py).
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
PATCH = RUNNER.PATCH_DIR / 'mixxx-eject-top-menu.patch'
TEST = ROOT / 'tests/native/eject_top_menu_test.cpp.in'
FEATURE = 'src/library/rekordbox/rekordboxfeature.cpp'


def added(path):
    text = PATCH.read_text()
    start = text.index('diff --git a/' + path + ' ')
    end = text.find('\ndiff --git', start + 1)
    return '\n'.join(line[1:] for line in text[start:end if end > 0 else None].splitlines()
                     if line.startswith('+') and not line.startswith('+++'))


class EjectTopMenuPatchTests(unittest.TestCase):
    def test_patch_changes_only_its_files_and_only_adds(self):
        text = PATCH.read_text()
        self.assertEqual(sorted(re.findall(r'^diff --git a/(\S+) b/\S+$', text, re.MULTILINE)),
                         [FEATURE, 'src/library/rekordbox/rekordboxfeature.h',
                          'src/widget/wlibrarysidebar.cpp', 'src/widget/wlibrarysidebar.h'])
        self.assertEqual([line for line in text.splitlines() if line.startswith('-') and not line.startswith('---')],
                         [])

    def test_patch_is_registered_after_the_quit_fix(self):
        names = subprocess.check_output(['bash', str(ROOT / 'stage3/01-install-packages/01-run.sh'),
                                         '--mixxx-print-patches'], text=True).split()
        if PATCH.name not in names:
            self.skipTest(PATCH.name + ' is not registered yet')
        self.assertLess(names.index('mixxx-quit-library-widget.patch'), names.index(PATCH.name))

    def test_table_is_released_only_for_the_drive_shown(self):
        feature = added(FEATURE)
        # Wired to the feature's own model: the drive rows discovery removes
        # (onRekordboxDevicesFound itself is unchanged, other fixtures extract it).
        self.assertIn('&QAbstractItemModel::rowsAboutToBeRemoved,', feature)
        self.assertIn('&RekordboxFeature::releaseRemovedDrives);', feature)
        self.assertIn('(shown == path || shown.startsWith(path + kPLaylistPathDelimiter))', feature)
        header = added('src/library/rekordbox/rekordboxfeature.h')
        self.assertIn('setPlaylistById(0);', header)
        # Read only: no SQL, no files, no settings (the ★ start stays).
        for writer in ('INSERT', 'UPDATE', 'DELETE', 'ofstream', 'QIODevice::WriteOnly', '.write(', 'setValue',
                       'SidebarDefaultSource'):
            self.assertNotIn(writer, feature + header)

    def test_menu_lands_on_the_top_level_with_no_edge(self):
        sidebar = added('src/widget/wlibrarysidebar.cpp')
        self.assertIn('void WLibrarySidebar::rowsAboutToBeRemoved(', sidebar)
        # Only a drive's own row (refreshMediaLifecycle removes rows below a
        # drive, which must leave the menu alone).
        self.assertIn('if (!tile.id.startsWith(QStringLiteral("drive:")) || !tile.node.isValid() ||', sidebar)
        self.assertIn('selectionModel()->clear();', sidebar)
        self.assertIn('m_menuInside = false;', sidebar)
        self.assertIn('if (shown.isEmpty() && m_shownSourceGone) {', sidebar)
        for writer in ('setValue', 'SidebarDefaultSource', 'set(0)'):
            self.assertNotIn(writer, sidebar)


@unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
class EjectTopMenuNativeTests(unittest.TestCase):
    def run_fixture(self, *arguments):
        return subprocess.run([sys.executable, '-B', str(ROOT / 'tests/native/eject_top_menu_runner.py'),
                               *arguments], cwd=ROOT, capture_output=True, text=True, timeout=300)

    def test_native_eject_top_menu(self):
        result = self.run_fixture()
        print(result.stdout[-4000:], result.stderr[-2000:], flush=True)
        self.assertEqual(result.returncode, 0, result.stdout[-6000:] + result.stderr[-3000:])
        for check in checks(TEST):
            self.assertIn('PASS ' + check, result.stdout)
        self.assertNotIn('FAIL ', result.stdout)
        self.assertIn('OK 0', result.stdout)
        self.assertGreaterEqual(len(checks(TEST)), 8)

    def test_checks_fail_without_the_patch(self):
        result = self.run_fixture('--baseline')
        print(result.stdout[-4000:], result.stderr[-2000:], flush=True)
        self.assertNotEqual(result.returncode, 0)
        for check in ('J4 eject with GANDER1\'s list in Tracks: the table has 0 rows and no list',
                      'J4: after a re-plug and a new import, the table still shows no rows (no list id is reused)',
                      'J4 pulled out (the only drive) with its playlist in Tracks: the table has 0 rows'):
            self.assertIn('FAIL ' + check, result.stdout)
        # The checks that hold without the patch still hold.
        self.assertIn('PASS J4: ejecting another drive (MANTACORE) leaves the table alone', result.stdout)


if __name__ == '__main__':
    unittest.main()
