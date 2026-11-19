"""R-9 step 3 and agreed UI s5: grouped Sources in the side menu.

The menu's top-level rows are views onto the sources: one row per open drive
(first, in plug-in order), This Pi (Tracks, Playlists, Crates, Auto DJ),
Recordings, History, Folders (Computer), Samples, and More (the other
sources, only while one is on). The full-screen edit list orders and hides
those rows; the owner's per-source choices are mapped once (a row whose
sources are all hidden starts hidden).

The native checks are in tests/native/source_groups_test.cpp, built by
tests/native/source_groups_runner.py. They run with the skin's style sheets
(MIXPI_QSS_DIR); set MIXPI_SOURCES_GRAB_DIR to keep the 800x480 renders of
the menu and the edit list.

mixxx-sources-menu-fixes.patch (wave C2): rekordbox lists carry their track
counts (m-sources-sub.png), and ★ works on the drive row and on Samples
(m-sources-edit.png): Tracks starts at the drive that is in (opened as OPEN
on the Media page opens it), else This Pi; or at the Samples folder.

mixxx-sources-start-rows.patch (build D, spec 2a and U-4): every start value
build B could save shows ★ on its row (the owner's RekordboxFeature on the
drive row) and Tracks starts there, without rewriting the value; the menu's
current-row edge follows the source Tracks shows; This Pi's and More's own
lists come back in Sources edit as indented rows with only ON/OFF; the menu
rows' title is drawn in the sidebar's own (build B) font.

mixxx-sources-open-edge.patch (build E, spec 2b "do 2"; acceptance D repro
1): a drive opened from the Media page (OPEN or BROWSE) becomes the menu's
current source and place: ☰ reopens inside the drive, and the top level has
the accent edge on the drive row. The saved start (★) is not touched.

mixxx-drive-tracks-row.patch (build I, spec 2d): the drive's rows start with
the feature's own Tracks row (driveTracksRow, no ›); with the drive's whole
list in Tracks the edge sits on it, a tap opens it like any list, and an
eject with it in view leaves nothing dangling. The import side is in
tests/test_drive_tracks_row.py.
"""
import os
from pathlib import Path
import re
import subprocess
import unittest

from native.library_interface_runner import qt_available
from native import library_interface_runner as RUNNER
from test_sample_browser import checks

ROOT = Path(__file__).resolve().parents[1]
PATCH = RUNNER.PATCH_DIR / 'mixxx-source-groups.patch'
FIXES = RUNNER.PATCH_DIR / 'mixxx-sources-menu-fixes.patch'
START_ROWS = RUNNER.PATCH_DIR / 'mixxx-sources-start-rows.patch'
OPEN_EDGE = RUNNER.PATCH_DIR / 'mixxx-sources-open-edge.patch'
TEST = ROOT / 'tests/native/source_groups_test.cpp'


class SourceGroupsPatchTests(unittest.TestCase):
    def test_patch_changes_only_its_files(self):
        self.assertEqual(sorted(re.findall(r'^diff --git a/(\S+) b/\S+$', PATCH.read_text(), re.MULTILINE)),
                         ['src/library/library.cpp', 'src/library/library.h',
                          'src/widget/libraryinterface.h', 'src/widget/touchsourcenavigation.h',
                          'src/widget/wlibrarysidebar.cpp', 'src/widget/wlibrarysidebar.h'])

    def test_patch_follows_the_sample_browser(self):
        names = subprocess.check_output(['bash', str(ROOT / 'stage3/01-install-packages/01-run.sh'),
                                         '--mixxx-print-patches'], text=True).split()
        if 'mixxx-source-groups.patch' not in names:
            self.skipTest('mixxx-source-groups.patch is not registered yet')
        self.assertLess(names.index('mixxx-sample-browser.patch'), names.index('mixxx-source-groups.patch'))

    def test_groups_and_settings(self):
        added = '\n'.join(line[1:] for line in PATCH.read_text().splitlines() if line.startswith('+'))
        # The tiles in the plan's order; drives first.
        self.assertIn('return {kDrives, kThisPi, kRecordings, kHistory, kFolders, kSamples, kMore};', added)
        for source in ('"MixxxLibraryFeature"', '"PlaylistFeature"', '"CrateFeature"', '"AutoDJFeature"'):
            self.assertIn(source, added)
        for key in ('SourceGroupDrives', 'SourceGroupThisPi', 'SourceGroupSamples', 'SourceGroupMore',
                    'SourceGroupOrder', 'SourceGroupsMapped'):
            self.assertIn(key, added)
        # The Library hides sources through the sidebar's own layer, so a
        # set tile (This Pi) never looks like a hidden source.
        library = '\n'.join(line[1:] for line in PATCH.read_text().split('diff --git')[1].splitlines()
                            if line.startswith('+'))
        self.assertIn('setSourceRowHidden(row, !visible)', library)
        self.assertIn('isSourceRowHidden', library)
        # Back stops at a drive's row.
        self.assertIn('if (m_root == m_floor) {', added)

    def test_owner_words_on_tiles(self):
        added = '\n'.join(line[1:] for line in PATCH.read_text().splitlines() if line.startswith('+'))
        for words in ('tr("This Pi")', 'tr("More")', 'tr("Folders")', 'tr("History")', 'tr("Recordings")',
                      'tr("Samples")', 'tr("USB drives (each drive)")'):
            self.assertIn(words, added)
        for jargon in ('broker', 'generation', 'token'):
            self.assertNotIn(jargon, added.lower())

    @unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
    def test_native_source_groups(self):
        environment = dict(os.environ, MIXPI_QSS_DIR=str(RUNNER.PATCH_DIR))
        result = subprocess.run(['python3', str(ROOT / 'tests/native/source_groups_runner.py')],
                                capture_output=True, text=True, timeout=300, env=environment)
        self.assertEqual(result.returncode, 0, result.stdout[-6000:] + result.stderr[-3000:])
        for check in checks(TEST):
            self.assertIn('PASS ' + check, result.stdout)
        self.assertNotIn('FAIL ', result.stdout)
        self.assertIn('OK 0', result.stdout)
        self.assertGreaterEqual(len(checks(TEST)), 55)


def added_lines(path):
    """The lines mixxx-sources-menu-fixes.patch adds to one file."""
    text = FIXES.read_text()
    start = text.index('diff --git a/' + path + ' ')
    end = text.find('\ndiff --git', start + 1)
    return '\n'.join(line[1:] for line in text[start:end if end > 0 else None].splitlines()
                     if line.startswith('+') and not line.startswith('+++'))


class SourcesMenuFixesPatchTests(unittest.TestCase):
    def names(self):
        return subprocess.check_output(['bash', str(ROOT / 'stage3/01-install-packages/01-run.sh'),
                                        '--mixxx-print-patches'], text=True).split()

    def test_patch_changes_only_its_files(self):
        self.assertEqual(sorted(re.findall(r'^diff --git a/(\S+) b/\S+$', FIXES.read_text(), re.MULTILINE)),
                         ['src/library/library.cpp', 'src/library/library.h', 'src/library/mixpimedia.h',
                          'src/library/mixpistartdrive.h', 'src/library/rekordbox/rekordboxfeature.cpp',
                          'src/widget/wlibrarysidebar.cpp'])

    def test_place_inside_a_drive_names_the_part_shown(self):
        sidebar = added_lines('src/widget/wlibrarysidebar.cpp')
        # m-sources-sub.png: "MANTACORE › rekordbox"; a drive without an
        # export: its folder view.
        self.assertIn('QStringLiteral("rekordbox")', sidebar)
        self.assertIn('Groups::title(Groups::kFolders)', sidebar)

    def test_patch_comes_after_the_menu_and_the_media_page(self):
        names = self.names()
        if 'mixxx-sources-menu-fixes.patch' not in names:
            self.skipTest('mixxx-sources-menu-fixes.patch is not registered yet')
        for earlier in ('mixxx-sources-menu.patch', 'mixxx-media-agreed.patch'):
            self.assertLess(names.index(earlier), names.index('mixxx-sources-menu-fixes.patch'))

    def test_rekordbox_counts_come_from_what_the_import_reads(self):
        feature = added_lines('src/library/rekordbox/rekordboxfeature.cpp')
        # The count is the size of the entries already in memory: no query.
        self.assertIn('playlistTrackMap.value(childID).size()', feature)
        self.assertIn('QStringLiteral("%1 (%2)")', feature)
        self.assertIn('playlistIsFolderMap.value(childID)', feature)
        self.assertNotIn('QSqlQuery', feature)

    def test_start_at_the_drive_and_at_samples(self):
        library = added_lines('src/library/library.cpp')
        media = added_lines('src/library/mixpimedia.h')
        # ★ is on for the drive row and for Samples.
        self.assertIn('entry.available = true;', library)
        self.assertIn('SampleBrowser::kSamples', library)
        # At the start: the drive opens through the Media page's open path,
        # without switching to Tracks; Tracks shows the drive, This Pi or
        # Samples.
        self.assertIn('m_pMixpiMedia->openStartDrive();', library)
        self.assertIn('if (showStartTile(start)) {', library)
        self.assertIn('volume.value(QStringLiteral("mixpiStart")).toBool()', library)
        self.assertIn('openVolume(start.identity, start.token, true);', media)
        self.assertIn('volume.insert(QStringLiteral("mixpiStart"), true);', media)
        # Nothing is written to a drive.
        for word in ('QFile::remove', 'QFile::copy', 'O_WRONLY', 'WriteOnly', 'ReadWrite'):
            self.assertNotIn(word, library + media)


def start_rows_added(path):
    """The lines mixxx-sources-start-rows.patch adds to one file."""
    text = START_ROWS.read_text()
    start = text.index('diff --git a/' + path + ' ')
    end = text.find('\ndiff --git', start + 1)
    return '\n'.join(line[1:] for line in text[start:end if end > 0 else None].splitlines()
                     if line.startswith('+') and not line.startswith('+++'))


class SourcesStartRowsPatchTests(unittest.TestCase):
    def test_patch_changes_only_its_files(self):
        self.assertEqual(sorted(re.findall(r'^diff --git a/(\S+) b/\S+$', START_ROWS.read_text(), re.MULTILINE)),
                         ['src/library/library.cpp', 'src/widget/libraryinterface.h',
                          'src/widget/wlibrarysidebar.cpp', 'src/widget/wlibrarysidebar.h'])

    def test_patch_comes_after_the_menu_fixes(self):
        names = subprocess.check_output(['bash', str(ROOT / 'stage3/01-install-packages/01-run.sh'),
                                         '--mixxx-print-patches'], text=True).split()
        if 'mixxx-sources-start-rows.patch' not in names:
            self.skipTest('mixxx-sources-start-rows.patch is not registered yet')
        self.assertLess(names.index('mixxx-sources-menu-fixes.patch'), names.index('mixxx-sources-start-rows.patch'))

    def test_saved_start_maps_to_its_row_and_is_not_rewritten(self):
        interface = start_rows_added('src/widget/libraryinterface.h')
        library = start_rows_added('src/library/library.cpp')
        # Rekordbox (the owner's saved start) is the drive row's start.
        self.assertIn('if (start == QStringLiteral("RekordboxFeature")) {\n        return kDrives;', interface)
        self.assertIn('return startTile(start) == row;', interface)
        self.assertIn('const QString start = Groups::startTile(saved);', library)
        self.assertIn('if (groupedSources() && Groups::startTile(start) == Groups::kDrives) {', library)
        # The start only reads the saved value: no write of SidebarDefaultSource.
        start = library.index('// A drive\'s source saved by build B (Rekordbox) is the drive row\'s')
        self.assertNotIn('setValue', library[start:])

    def test_child_rows_switch_their_source_only(self):
        interface = start_rows_added('src/widget/libraryinterface.h')
        library = start_rows_added('src/library/library.cpp')
        # A child row: member, its source's own key; ★, icon, UP, DOWN hidden.
        self.assertIn('members.append({source.id, source.title, m_pConfig->getValue(source.preference, true),', library)
        self.assertIn('source.feature != nullptr, true});', library)
        self.assertIn('entries.append(members);', library)
        self.assertIn('static_cast<QWidget*>(icon),', interface)

    def test_current_row_follows_tracks_and_row_font_is_the_sidebars(self):
        sidebar = start_rows_added('src/widget/wlibrarysidebar.cpp')
        self.assertIn('const QString shown = tileOf(currentIndex());', sidebar)
        self.assertIn('m_groupedTiles.at(tile).id == shown);', sidebar)
        # Build B's font for a list row: no weight forced in C++.
        self.assertNotIn('setWeight', sidebar)
        self.assertIn('const QFont title = option.font;', sidebar)


def open_edge_added(path):
    """The lines mixxx-sources-open-edge.patch adds to one file."""
    text = OPEN_EDGE.read_text()
    start = text.index('diff --git a/' + path + ' ')
    end = text.find('\ndiff --git', start + 1)
    return '\n'.join(line[1:] for line in text[start:end if end > 0 else None].splitlines()
                     if line.startswith('+') and not line.startswith('+++'))


class SourcesOpenEdgePatchTests(unittest.TestCase):
    def test_patch_changes_only_its_files_and_only_adds(self):
        text = OPEN_EDGE.read_text()
        self.assertEqual(sorted(re.findall(r'^diff --git a/(\S+) b/\S+$', text, re.MULTILINE)),
                         ['src/library/library.cpp', 'src/widget/wlibrarysidebar.cpp',
                          'src/widget/wlibrarysidebar.h'])
        self.assertEqual([line for line in text.splitlines() if line.startswith('-') and not line.startswith('---')],
                         [])

    def test_patch_is_registered_after_the_start_rows(self):
        names = subprocess.check_output(['bash', str(ROOT / 'stage3/01-install-packages/01-run.sh'),
                                         '--mixxx-print-patches'], text=True).split()
        self.assertIn('mixxx-sources-open-edge.patch', names)
        self.assertLess(names.index('mixxx-sources-start-rows.patch'), names.index('mixxx-sources-open-edge.patch'))

    def test_both_open_paths_follow_the_drive_and_keep_the_start(self):
        library = open_edge_added('src/library/library.cpp')
        # The sync path (folders, or a rekordbox drive already read) and the
        # async one (rekordbox).
        self.assertIn('        m_pSidebarWidget->followShownSource();', library)
        self.assertIn('                        owner->m_pSidebarWidget->followShownSource();', library)
        sidebar = open_edge_added('src/widget/wlibrarysidebar.cpp')
        self.assertIn('const QString id = tileOf(shown);', sidebar)
        self.assertIn('openGroupedTile(id, false);', sidebar)
        # Nothing writes a setting: the saved start (★) stays.
        for added in (library, sidebar):
            self.assertNotIn('setValue', added)
            self.assertNotIn('SidebarDefaultSource', added)
        # The native repro (acceptance D repro 1) is in the fixture.
        test = TEST.read_text()
        self.assertIn('after OPEN, BACK: the top level has the accent edge on the drive only', test)
        self.assertIn('sidebar.followShownSource();', test)


if __name__ == '__main__':
    unittest.main()
