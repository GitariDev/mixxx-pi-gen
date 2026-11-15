import os
from pathlib import Path
import subprocess
import sys
import unittest

from native.library_interface_runner import qt_available

from test_media_ownership import production_file

ROOT = Path(__file__).resolve().parents[1]


class RekordboxAnalysisTests(unittest.TestCase):
    @unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
    def test_real_parser_rejects_failed_optional_analysis(self):
        subprocess.run([sys.executable, str(ROOT / 'tests/native/rekordbox_analysis_runner.py')],
                       check=True, timeout=150)

    @unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
    def test_reserved_truncated_section_and_recovery(self):
        subprocess.run([sys.executable, str(ROOT / 'tests/native/rekordbox_analysis_runner.py'),
                        '--holdout'], check=True, timeout=150)

    def test_complete_parse_precedes_track_mutation(self):
        source = production_file('src/library/rekordbox/rekordboxfeature.cpp')
        start = source.index('void readAnalyze(')
        end = source.index('\n} // anonymous namespace', start)
        function = source[start:end]
        self.assertIn('QFileInfo(anlzPath).isFile()', function)
        self.assertIn('ifs.is_open()', function)
        self.assertIn('catch (const std::runtime_error&', function)
        self.assertIn('catch (const std::length_error&', function)
        self.assertNotIn('catch (const std::exception&', function)
        self.assertLess(function.index('auto& anlz = *parsed'), function.index('track->trySetBeats'))
        self.assertLess(function.rindex('catch ('), function.index('setHotCue('))


if __name__ == '__main__':
    unittest.main()
