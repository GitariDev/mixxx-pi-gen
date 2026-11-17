"""R-8 native part: the Load sample screen keeps its own place.

[MixPi],sample_load 1 remembers Tracks' source, search and scroll, and shows
the sample browser's own last place (first: the Samples folder); 0 restores
Tracks. [MixPi],sample_source picks 1 Samples, 2 the track collection, 3 the
first open drive (none: Samples), 4 Recordings; [MixPi],sample_source_available
says the buttons work. The Actions menu gains "Load to a sampler pad…", which
writes [MixPi],screen 4 (Choose pad).

The native checks are in tests/native/sample_browser_test.cpp.
"""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

from native.library_interface_runner import qt_available
from native import library_interface_runner as RUNNER

ROOT = Path(__file__).resolve().parents[1]
PATCH = RUNNER.PATCH_DIR / 'mixxx-sample-browser.patch'
TEST = ROOT / 'tests/native/sample_browser_test.cpp'


def checks(path=TEST):
    """The name of every require(condition, "name") in a fixture."""
    source = path.read_text()
    names = []
    for start in [match.end() for match in re.finditer(r'\brequire\(', source)][1:]:
        names.append(re.findall(r'"([^"\n]*)"', source[start:source.index(');', start)])[-1])
    return names


class SampleBrowserPatchTests(unittest.TestCase):
    def test_patch_changes_only_its_files(self):
        self.assertEqual(sorted(re.findall(r'^diff --git a/(\S+) b/\S+$', PATCH.read_text(), re.MULTILINE)),
                         ['src/library/browse/browsefeature.cpp', 'src/library/browse/browsefeature.h',
                          'src/library/library.cpp', 'src/library/library.h',
                          'src/widget/libraryinterface.h', 'src/widget/wtracktableview.cpp'])

    def test_patch_follows_the_sources_screen(self):
        names = subprocess.check_output(['bash', str(ROOT / 'stage3/01-install-packages/01-run.sh'),
                                         '--mixxx-print-patches'], text=True).split()
        if 'mixxx-sample-browser.patch' not in names:
            self.skipTest('mixxx-sample-browser.patch is not registered yet')
        self.assertLess(names.index('mixxx-sources-screen.patch'), names.index('mixxx-sample-browser.patch'))

    def test_controls_and_writes(self):
        text = PATCH.read_text()
        added = '\n'.join(line[1:] for line in text.splitlines() if line.startswith('+'))
        for key in ('ConfigKey("[MixPi]", "sample_load")', 'ConfigKey("[MixPi]", "sample_source")',
                    'ConfigKey("[MixPi]", "sample_source_available")'):
            self.assertIn(key, added)
        # The skin's buttons write these values.
        for value in ('kSamples = 1', 'kCollection = 2', 'kDrive = 3', 'kRecordings = 4'):
            self.assertIn(value, added)
        # Choose pad is screen 4; the entry needs the MixPi skin's screen control.
        self.assertIn('ControlObject::set(ConfigKey("[MixPi]", "screen"), 4);', added)
        self.assertIn('ControlFlag::NoWarnIfMissing', added)
        self.assertIn('Load to a sampler pad\\u2026', added)
        # A drive opened from the media screen no longer writes sample_load 0
        # around the sample browser: it ends sample mode where it is.
        self.assertNotIn('ControlObject::set(ConfigKey("[MixPi]", "sample_load"), 0);', added)
        self.assertIn('leaveSampleMode(false);', added)
        # The Samples folder under the Pi's music folder.
        self.assertIn('QStandardPaths::MusicLocation', added)
        self.assertIn('QStringLiteral("Samples")', added)

    def test_skin_names_match(self):
        skin = (RUNNER.PATCH_DIR / 'mixpi-performance.py').read_text()
        for name in ("'[MixPi],sample_source'", "'[MixPi],sample_source_available'", "'[MixPi],sample_load'"):
            self.assertIn(name, skin)
        self.assertIn("('SAMPLES', 1), ('THIS PI', 2), ('RECORDINGS', 4)", skin)
        self.assertIn('SCREEN_NONE, SCREEN_SOURCES, SCREEN_MEDIA, SCREEN_LOAD_SAMPLE, SCREEN_CHOOSE_PAD', skin)

    @unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
    def test_native_sample_browser(self):
        result = subprocess.run(['python3', str(ROOT / 'tests/native/sample_browser_runner.py')],
                                capture_output=True, text=True, timeout=300)
        self.assertEqual(result.returncode, 0, result.stdout[-6000:] + result.stderr[-3000:])
        for check in checks():
            self.assertIn('PASS ' + check, result.stdout)
        self.assertNotIn('FAIL ', result.stdout)
        self.assertIn('OK 0', result.stdout)
        self.assertGreaterEqual(len(checks()), 30)


if __name__ == '__main__':
    unittest.main()
