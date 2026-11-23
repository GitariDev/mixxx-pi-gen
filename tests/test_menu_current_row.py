"""Council round 9 (Opus), wave J17: the menu's edge stays on the list in view.

AGREED-UI-SPEC 2a: "the Sources menu's current-row edge follows the source in
view"; m-sources-sub.png draws the edge on the playlist in view (Afro house),
not on Tracks. Confirmed on the card (build P, acceptance-P shots o9-1..o9-5):
with A - MAIN PLAYLIST in view,

1. a tap on the empty part of the open menu left no row edged: that press is
   the sidebar's focus-in, and upstream's focusInEvent clears the current
   row (kept by mixxx-source-tap.patch);
2. the next ☰ put the edge on TRACKS: J16's edgeShownDriveTracks picked the
   Tracks row whenever the current row was gone, whatever the table showed.

mixxx-menu-current-row.patch: in the touch Sources menu a focus-in keeps the
current row (the desktop sidebar is unchanged), and J16's show-time restore
edges the row of the drive's level whose list the table shows (its path, the
last row made current, as RekordboxFeature::selectShownDriveTracks matches
the drive); TRACKS only while the Tracks list is in view; none at that level:
the current row stays as it is. The native checks are in
tests/native/menu_current_row_test.cpp (built by
tests/native/menu_current_row_runner.py).
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
PATCH = RUNNER.PATCH_DIR / 'mixxx-menu-current-row.patch'
TEST = ROOT / 'tests/native/menu_current_row_test.cpp'
SIDEBAR = 'src/widget/wlibrarysidebar.cpp'
HEADER = 'src/widget/wlibrarysidebar.h'


def changed(path, sign):
    text = PATCH.read_text()
    start = text.index('diff --git a/' + path + ' ')
    end = text.find('\ndiff --git', start + 1)
    return [line[1:] for line in text[start:end if end > 0 else None].splitlines()
            if line.startswith(sign) and not line.startswith(sign * 3)]


class MenuCurrentRowPatchTests(unittest.TestCase):
    def test_patch_changes_only_the_sidebar(self):
        self.assertEqual(sorted(re.findall(r'^diff --git a/(\S+) b/\S+$', PATCH.read_text(), re.MULTILINE)),
                         [SIDEBAR, HEADER])
        # Only two lines go: the Tracks match and the unconditional clear.
        self.assertEqual(changed(HEADER, '-'), [])
        self.assertEqual([line.strip() for line in changed(SIDEBAR, '-')],
                         ['if (!isRowHidden(row, node) && pathOf(child) == path) {',
                          '// Clear the current index, i.e. remove the focus indicator',
                          'selectionModel()->clearCurrentIndex();'])

    def test_patch_is_registered_last(self):
        names = subprocess.check_output(['bash', str(ROOT / 'stage3/01-install-packages/01-run.sh'),
                                         '--mixxx-print-patches'], text=True).split()
        if PATCH.name not in names:
            self.skipTest(PATCH.name + ' is not registered yet')
        # Only the three-band waveform patch (test_waveform_three_band.py) comes after it.
        self.assertEqual(names[names.index(PATCH.name) + 1:], ['mixxx-waveform-three-band.patch'])
        self.assertLess(names.index('mixxx-menu-place-fix.patch'), names.index(PATCH.name))

    def test_focus_in_keeps_the_current_row_only_in_the_touch_menu(self):
        added = '\n'.join(changed(SIDEBAR, '+'))
        self.assertIn('if (!(m_touchNavigation && m_sourceScreen)) {', added)
        self.assertIn('        selectionModel()->clearCurrentIndex();', added)

    def test_restore_edges_the_row_whose_list_is_in_view(self):
        added = '\n'.join(changed(SIDEBAR, '+'))
        self.assertIn('QString m_shownList;', '\n'.join(changed(HEADER, '+')))
        # Remembered from every row made current, by its path ...
        self.assertIn('const QVariant data = current.data(SidebarModel::DataRole);', added)
        self.assertIn('m_shownList = data.userType() == QMetaType::QString', added)
        # ... matched by path at the drive's level, none: unchanged ...
        self.assertIn('if (m_shownList.isEmpty()) {', added)
        self.assertIn('if (!isRowHidden(row, node) && pathOf(child) == m_shownList) {', added)
        # ... and forgotten with the drive (J4).
        self.assertEqual(added.count('m_shownList.clear();'), 2)
        # Nothing is activated or written: the table does not change.
        for activation in ('emit clicked(', 'emit pressed(', 'activateTouchIndex(', 'closeSources()',
                           'setValue', 'SidebarDefaultSource', 'set(0)', 'set(1)'):
            self.assertNotIn(activation, added)


@unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
class MenuCurrentRowNativeTests(unittest.TestCase):
    def run_fixture(self, *arguments):
        return subprocess.run([sys.executable, '-B', str(ROOT / 'tests/native/menu_current_row_runner.py'),
                               *arguments], cwd=ROOT, capture_output=True, text=True, timeout=300)

    def test_native_menu_current_row(self):
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
                'J17 (a) Afro house in view, a focus-in, then ☰: current = Afro house, not TRACKS',
                'J17 (a) Afro house in view, clearCurrentIndex(), then ☰: current = Afro house, not TRACKS',
                'J17 (a) Afro house in view, a sidebar model reset, then ☰: current = Afro house, not TRACKS',
                'J17 (a) the folder current (BACK), a model reset, then ☰: current = the folder, not TRACKS',
                'J17 a list of another level (Deep cuts), a model reset, then ☰: the current row stays as it is '
                '(none), not TRACKS',
                'J17 (b) a tap on the empty part of the open menu (its focus-in): the edge stays on Afro house',
                'J17 (b) then ✕ and ☰: the edge on Afro house, not TRACKS (o9-5)',
                'J17 (b) a drag from the empty part of the open menu: the edge stays on Afro house',
                'J17 (b) a drag of the menu\'s rows (from Warm-up): the edge stays on Afro house, nothing opens',
                'J17 (c) TRACKS in view, a focus-in keeps it current, then ☰: the edge on TRACKS'):
            self.assertIn('FAIL ' + check, result.stdout)
        # What J17 keeps holds without it too.
        for check in (
                'start: OPEN, inside GANDER1 › rekordbox, the edge on TRACKS',
                '(a) Afro house picked: ☰ has the edge on it (o9-3)',
                'J17 (c) TRACKS in view, clearCurrentIndex(), then ☰: TRACKS (J16 unchanged)',
                'J17 (c) TRACKS in view, a model reset, then ☰: TRACKS (J16 unchanged)',
                'J17 (d) OPEN before ☰ was ever shown: the first ☰ opens inside IXIAN › rekordbox, the edge on '
                'TRACKS (J16 unchanged)',
                'J17 (d) J4: Afro house in view, then the eject: ☰ at the top level, no edge, nothing current',
                'J17 (d) the drive back and OPEN: inside GANDER1 › rekordbox, the edge on TRACKS (J5 unchanged)',
                'J17 (d) then BACK: the top level, the edge on GANDER1 only (build E)',
                'J17 does not change the saved start (★)',
                'desktop sidebar: a focus-in still clears the current row (unchanged)',
                'J17 (a) focus-in: the table is not changed',
                'J17 (b) the empty tap: the table is not changed',
                'J17 (b) the drag: the table is not changed',
                'J17 (b) the row drag: the table is not changed'):
            self.assertIn('PASS ' + check, result.stdout)


if __name__ == '__main__':
    unittest.main()
