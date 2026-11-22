"""Spec 2e (wave J16): ☰ after OPEN always opens inside the drive, edge on TRACKS.

Spec 2e: "☰ after OPEN opens inside the drive, with the current-row edge on
Tracks, as m-sources-sub.png draws it". Council round 8 (Opus) found it
broken on the card; the investigation (investigation-R8-edge) found two
causes:

1. After a Mixxx start, the first OPEN, BROWSE or LOAD before ☰ was ever
   shown: openShownSource returned early, because the hidden sidebar has no
   width and so is not the Sources menu yet (m_sourceScreen false). ☰ then
   opened at the top level. mixxx-menu-place-fix.patch remembers that OPEN
   (m_pendingOpen) and applies it when the menu turns on, while Tracks still
   shows a list of the same drive.
2. Acceptance M 38-menu: inside "GANDER1 › rekordbox" with no row edged. The
   place and the current row are kept apart, and a focus-in
   (clearCurrentIndex) or a sidebar model reset clears the current row while
   the place stays. On every ☰ at a drive's own level with no row of it
   current, the patch makes the drive's Tracks row current
   (edgeShownDriveTracks). Nothing is activated: the table does not change.

J4, J5, the ★ start, BACK, the crumb and taps on rows are kept. The native
checks are in tests/native/menu_place_fix_test.cpp (built by
tests/native/menu_place_fix_runner.py).
"""
from pathlib import Path
import re
import subprocess
import sys
import unittest

from native.library_interface_runner import qt_available
from native import library_interface_runner as RUNNER
from test_sample_browser import checks

ROOT = Path(__file__).resolve().parents[1]
PATCH = RUNNER.PATCH_DIR / 'mixxx-menu-place-fix.patch'
TEST = ROOT / 'tests/native/menu_place_fix_test.cpp'
SIDEBAR = 'src/widget/wlibrarysidebar.cpp'
HEADER = 'src/widget/wlibrarysidebar.h'


def changed(path, sign):
    text = PATCH.read_text()
    start = text.index('diff --git a/' + path + ' ')
    end = text.find('\ndiff --git', start + 1)
    return [line[1:] for line in text[start:end if end > 0 else None].splitlines()
            if line.startswith(sign) and not line.startswith(sign * 3)]


class MenuPlaceFixPatchTests(unittest.TestCase):
    def test_patch_changes_only_the_sidebar_and_only_adds(self):
        self.assertEqual(sorted(re.findall(r'^diff --git a/(\S+) b/\S+$', PATCH.read_text(), re.MULTILINE)),
                         [SIDEBAR, HEADER])
        self.assertEqual(changed(SIDEBAR, '-') + changed(HEADER, '-'), [])

    def test_patch_is_registered_last(self):
        names = subprocess.check_output(['bash', str(ROOT / 'stage3/01-install-packages/01-run.sh'),
                                         '--mixxx-print-patches'], text=True).split()
        if PATCH.name not in names:
            self.skipTest(PATCH.name + ' is not registered yet')
        self.assertEqual(names[-1], PATCH.name)
        for prerequisite in ('mixxx-sources-open-edge.patch', 'mixxx-media-open-inside.patch',
                             'mixxx-eject-folders-view.patch'):
            self.assertLess(names.index(prerequisite), names.index(PATCH.name))

    def test_open_before_the_menu_is_remembered(self):
        added = '\n'.join(changed(SIDEBAR, '+'))
        self.assertIn('QPersistentModelIndex m_pendingOpen;', '\n'.join(changed(HEADER, '+')))
        # Set by openShownSource while the sidebar is not the menu yet ...
        self.assertIn('if (!m_sourceScreen && groupedTiles && m_touchNavigation && !m_sourcesEditing) {', added)
        self.assertIn('m_pendingOpen = QPersistentModelIndex(currentIndex());', added)
        # ... applied when it turns on, only for the same source ...
        self.assertIn('if (!pending.isEmpty() && pending == tileOf(currentIndex())) {', added)
        # ... and dropped by the ★ start and by a folder that went with its drive.
        self.assertGreaterEqual(added.count('m_pendingOpen = QPersistentModelIndex();'), 4)

    def test_menu_shown_inside_a_drive_puts_the_edge_on_tracks(self):
        added = '\n'.join(changed(SIDEBAR, '+'))
        self.assertIn('void WLibrarySidebar::showEvent(QShowEvent* pEvent) {', added)
        self.assertIn('void WLibrarySidebar::edgeShownDriveTracks() {', added)
        # Only at the drive's own level, only with no row of it current.
        self.assertIn('rootIndex() != pTile->node) {', added)
        self.assertIn('if (current.isValid() && tileOf(current) != pTile->id) {', added)
        # The Tracks row is the drive's child with its own path first in its
        # data list (driveTracksRow); a plain string (a folder drive) is none.
        self.assertIn("return data.userType() == QMetaType::QString ? QString() : "
                      "data.toList().value(0).toString();", added)
        self.assertIn('if (!isRowHidden(row, node) && pathOf(child) == path) {', added)
        # Current only: nothing is activated, so the table does not change.
        self.assertIn('selectionModel()->setCurrentIndex(child,', added)
        for activation in ('emit clicked(', 'emit pressed(', 'activateTouchIndex(', 'closeSources()'):
            self.assertNotIn(activation, added)
        for writer in ('setValue', 'SidebarDefaultSource', 'set(0)', 'set(1)'):
            self.assertNotIn(writer, added)


@unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
class MenuPlaceFixNativeTests(unittest.TestCase):
    def run_fixture(self, *arguments):
        return subprocess.run([sys.executable, '-B', str(ROOT / 'tests/native/menu_place_fix_runner.py'),
                               *arguments], cwd=ROOT, capture_output=True, text=True, timeout=300)

    def test_native_menu_place_fix(self):
        result = self.run_fixture()
        print(result.stdout[-4000:], result.stderr[-2000:], flush=True)
        self.assertEqual(result.returncode, 0, result.stdout[-6000:] + result.stderr[-3000:])
        for check in checks(TEST):
            self.assertIn('PASS ' + check, result.stdout)
        self.assertNotIn('FAIL ', result.stdout)
        self.assertIn('OK 0', result.stdout)
        self.assertGreaterEqual(len(checks(TEST)), 25)

    def test_checks_fail_without_the_patch(self):
        result = self.run_fixture('--baseline')
        print(result.stdout[-4000:], result.stderr[-2000:], flush=True)
        self.assertNotEqual(result.returncode, 0)
        for check in (
                'J16 (a) OPEN before ☰ was ever shown: the first ☰ opens inside GANDER1 › rekordbox, '
                'the edge on TRACKS',
                'J16 (a) BROWSE or LOAD before ☰ was ever shown: the first ☰ opens inside IXIAN › rekordbox, '
                'the edge on TRACKS',
                'J16 (a) folder drive opened before ☰ was ever shown: the first ☰ lands as J5 does (STICK)',
                'J16 (b) clearCurrentIndex(), then ☰: inside GANDER1 › rekordbox, current = TRACKS',
                'J16 (b) a focus-in (clearCurrentIndex at :1429), then ☰: inside GANDER1 › rekordbox, '
                'current = TRACKS',
                'J16 (b) a sidebar model reset, then ☰: inside GANDER1 › rekordbox, current = TRACKS'):
            self.assertIn('FAIL ' + check, result.stdout)
        # What J16 keeps holds without it too.
        for check in (
                'J5 kept: OPEN after ☰ was shown once: inside GANDER1 › rekordbox, the edge on TRACKS',
                '★ start before ☰ was ever shown: the top level, the edge on the drive (kept)',
                'J16 (c) J4: OPEN, then an eject before ☰ was ever shown: ☰ at the top level, nothing current',
                'J16 (c) J4: the eject with the drive\'s list in Tracks: ☰ at the top level, no edge, nothing current',
                'J4 kept: another drive ejected: inside GANDER1 › rekordbox, the edge on TRACKS',
                'a playlist picked inside the drive: ☰ keeps the edge on it, not TRACKS',
                'inside a folder of the drive: ☰ keeps the folder current (build B)',
                'J16 (b) clearCurrentIndex: the table is not changed',
                'J16 (b) focus-in: the table is not changed',
                'J16 (b) model reset: the table is not changed'):
            self.assertIn('PASS ' + check, result.stdout)


if __name__ == '__main__':
    unittest.main()
