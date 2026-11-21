"""Spec 2e, as 2g applies it (build J, wave J10): an eject also clears a drive's Folders view.

Owner, 2026-11-20: "Let just land on the top menu instead". Found on the card
after council round 5 (acceptance J, shots 201-203): a drive opened through
Folders (Sources › Folders › Removable Devices › DRIVE › ...) and then
ejected kept its file rows in the table, and ☰ opened in Folders.

The cause: J4 (mixxx-eject-top-menu.patch) empties the table and lands the
menu only when a rekordbox drive's row goes (RekordboxFeature discovery). A
Folders view is BrowseFeature's: the eject's releaseViews
(refreshMediaLifecycle) removes the rows below Removable Devices, / and the
Quick Links, but BrowseTableModel keeps its folder and its rows (and
setPath({}) would not clear them: BrowseThread skips an empty path before it
clears the model), nothing tells Browse when the unmount is done or a drive
is pulled out, and the menu, whose place was below Removable Devices, went
back to its tile (Folders), still inside.

mixxx-eject-folders-view.patch: BrowseFeature::activateChild notes the mount
that holds the folder it shows (from the mount table); when the mount table
changes (MixpiMedia::tick, and ejectFinished after a clean eject),
Library::releaseGoneFolder asks BrowseFeature::releaseGoneFolder, which
empties the table (BrowseTableModel::releasePath) when that mount went, and
drops the drives no longer mounted from Removable Devices. When the folder is
the place Tracks shows, the menu lands on its top level with nothing current
(WLibrarySidebar::releaseShownSource, as J4). Only the mount table is read.

The native checks are in tests/native/eject_folders_view_test.cpp (built by
tests/native/eject_folders_view_runner.py).
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
PATCH = RUNNER.PATCH_DIR / 'mixxx-eject-folders-view.patch'
TEST = ROOT / 'tests/native/eject_folders_view_test.cpp'
FEATURE = 'src/library/browse/browsefeature.cpp'
FILES = [FEATURE, 'src/library/browse/browsefeature.h', 'src/library/browse/browsetablemodel.h',
         'src/library/library.cpp', 'src/library/library.h', 'src/library/mixpimedia.h',
         'src/widget/wlibrarysidebar.cpp', 'src/widget/wlibrarysidebar.h']


def added(path):
    text = PATCH.read_text()
    start = text.index('diff --git a/' + path + ' ')
    end = text.find('\ndiff --git', start + 1)
    return '\n'.join(line[1:] for line in text[start:end if end > 0 else None].splitlines()
                     if line.startswith('+') and not line.startswith('+++'))


class EjectFoldersViewPatchTests(unittest.TestCase):
    def test_patch_changes_only_its_files_and_only_adds(self):
        text = PATCH.read_text()
        self.assertEqual(sorted(re.findall(r'^diff --git a/(\S+) b/\S+$', text, re.MULTILINE)), sorted(FILES))
        self.assertEqual([line for line in text.splitlines() if line.startswith('-') and not line.startswith('---')],
                         [])

    def test_patch_is_registered_last_after_j4_j5_and_zoom(self):
        names = subprocess.check_output(['bash', str(ROOT / 'stage3/01-install-packages/01-run.sh'),
                                         '--mixxx-print-patches'], text=True).split()
        if PATCH.name not in names:
            self.skipTest(PATCH.name + ' is not registered yet')
        self.assertEqual(names[-1], PATCH.name)
        self.assertLess(names.index('mixxx-media-open-inside.patch'), names.index(PATCH.name))
        self.assertLess(names.index('mixxx-zoom-setting.patch'), names.index(PATCH.name))

    def test_the_table_goes_only_when_the_folders_mount_went(self):
        feature = added(FEATURE)
        # The mount of the folder shown, noted while it is there.
        self.assertIn('m_shownMount = mountOf(path);', feature)
        self.assertIn('const QString kMountTable = QStringLiteral("/proc/self/mountinfo");', feature)
        # Released only when that mount left the table; / never goes.
        self.assertIn('if (!m_shownMount.isEmpty() && m_shownMount != QDir::rootPath() &&', feature)
        self.assertIn('!points.isEmpty() && !points.contains(m_shownMount)) {', feature)
        self.assertIn('m_browseModel.releasePath();', feature)
        table = added('src/library/browse/browsetablemodel.h')
        self.assertIn('removeRows(0, rowCount());', table)
        # Read only: the mount table, nothing on a drive; no settings (★ stays).
        for writer in ('QIODevice::WriteOnly', '.write(', 'setValue', 'SidebarDefaultSource', 'QDir(path)',
                       'QFileInfo(', 'entryInfoList', 'ofstream'):
            self.assertNotIn(writer, feature + table)

    def test_the_mount_change_reaches_browse_and_the_menu(self):
        media = added('src/library/mixpimedia.h')
        self.assertIn('std::function<void()> mountsChanged;', media)
        self.assertEqual(media.count('mountsChanged();'), 2)
        library = added('src/library/library.cpp')
        self.assertIn('m_pMixpiMedia->mountsChanged = [this] {', library)
        self.assertIn('const QString folder = m_pBrowseFeature->releaseGoneFolder();', library)
        self.assertIn('m_pSidebarWidget->releaseShownSource();', library)
        sidebar = added('src/widget/wlibrarysidebar.cpp')
        self.assertIn('void WLibrarySidebar::releaseShownSource() {', sidebar)
        for line in ('m_shownSourceGone = true;', 'selectionModel()->clear();', 'm_menuInside = false;',
                     'm_touchNavigation->setFloor({});', 'm_touchNavigation->home();'):
            self.assertIn(line, sidebar)
        for writer in ('setValue', 'SidebarDefaultSource', 'set(0)'):
            self.assertNotIn(writer, sidebar + library + media)


@unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
class EjectFoldersViewNativeTests(unittest.TestCase):
    def run_fixture(self, *arguments):
        return subprocess.run([sys.executable, '-B', str(ROOT / 'tests/native/eject_folders_view_runner.py'),
                               *arguments], cwd=ROOT, capture_output=True, text=True, timeout=300)

    def test_native_eject_folders_view(self):
        result = self.run_fixture()
        print(result.stdout[-4000:], result.stderr[-2000:], flush=True)
        self.assertEqual(result.returncode, 0, result.stdout[-6000:] + result.stderr[-3000:])
        for check in checks(TEST):
            self.assertIn('PASS ' + check, result.stdout)
        self.assertNotIn('FAIL ', result.stdout)
        self.assertIn('OK 0', result.stdout)
        self.assertGreaterEqual(len(checks(TEST)), 15)

    def test_checks_fail_without_the_patch(self):
        result = self.run_fixture('--baseline')
        print(result.stdout[-4000:], result.stderr[-2000:], flush=True)
        self.assertNotEqual(result.returncode, 0)
        for check in ('J10 eject with GANDER1\'s folder in Tracks (Removable Devices): the table has 0 rows',
                      'J10 eject (Removable Devices): ☰ opens at the top level, no row has the edge, '
                      'nothing current',
                      'J10 pulled out with GANDER1\'s folder in Tracks (Quick Link): the table has 0 rows',
                      'J10 pulled out (Quick Link): ☰ opens at the top level, no edge, nothing current',
                      'J10 pulled out with DJ STICK\'s folder in Tracks (/): the table has 0 rows',
                      'after the pull, Removable Devices drops GANDER1 and keeps the drives still in'):
            self.assertIn('FAIL ' + check, result.stdout)
        # The checks that hold without the patch still hold.
        for check in ('J10: ejecting another drive (GANDER1) leaves the table alone',
                      'J10: with a folder of the Pi in Tracks an eject leaves the table alone',
                      'nothing on the drives was written'):
            self.assertIn('PASS ' + check, result.stdout)


if __name__ == '__main__':
    unittest.main()
