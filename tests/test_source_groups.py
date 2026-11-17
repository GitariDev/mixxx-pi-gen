"""R-9 step 3: grouped Sources.

On the Sources screen the rail's tiles are views onto the sources: one tile
per open drive (first, in plug-in order), This Pi (Tracks, Playlists, Crates,
Auto DJ), Recordings, History, Folders (Computer), Samples, and More (the
other sources, only while one is on). Sources edit orders and hides tiles;
the owner's per-source choices are mapped once (a tile whose sources are all
hidden starts hidden).

The native checks are in tests/native/source_groups_test.cpp.
"""
from pathlib import Path
import re
import subprocess
import unittest

from native.library_interface_runner import qt_available
from native import library_interface_runner as RUNNER
from test_sample_browser import checks

ROOT = Path(__file__).resolve().parents[1]
PATCH = RUNNER.PATCH_DIR / 'mixxx-source-groups.patch'
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
        result = subprocess.run(['python3', str(ROOT / 'tests/native/sample_browser_runner.py'),
                                 '--source-groups'], capture_output=True, text=True, timeout=300)
        self.assertEqual(result.returncode, 0, result.stdout[-6000:] + result.stderr[-3000:])
        for check in checks(TEST):
            self.assertIn('PASS ' + check, result.stdout)
        self.assertNotIn('FAIL ', result.stdout)
        self.assertIn('OK 0', result.stdout)
        self.assertGreaterEqual(len(checks(TEST)), 30)


if __name__ == '__main__':
    unittest.main()
