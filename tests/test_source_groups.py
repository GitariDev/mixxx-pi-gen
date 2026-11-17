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
                          'src/library/mixpistartdrive.h', 'src/library/rekordbox/rekordboxfeature.cpp'])

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


if __name__ == '__main__':
    unittest.main()
