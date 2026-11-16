"""Native WNumberPos tap check (owner decision 4.1); not full application acceptance."""
import importlib.util
from pathlib import Path
import unittest

from native.library_interface_runner import qt_available

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / 'stage3/01-install-packages/files/mixxx-position-display.patch'


def runner():
    spec = importlib.util.spec_from_file_location(
        'position_display_runner', ROOT / 'tests/native/position_display_runner.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PositionDisplayPatchTests(unittest.TestCase):
    def test_tap_never_selects_both(self):
        text = PATCH.read_text()
        added = [line[1:] for line in text.splitlines()
                 if line.startswith('+') and not line.startswith('+++')]
        self.assertNotIn('m_displayMode = TrackTime::DisplayMode::ELAPSED_AND_REMAINING;', '\n'.join(added))
        self.assertEqual(text.count('diff --git '), 1)
        self.assertIn('diff --git a/src/widget/wnumberpos.cpp b/src/widget/wnumberpos.cpp', text)


@unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
class NativePositionDisplayTests(unittest.TestCase):
    def test_shipping_widget_toggles_elapsed_and_remaining(self):
        result = runner().run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('FAILURES 0', result.stdout)

    def test_saved_both_checks_fail_without_council_fixes(self):
        # F-5 (council round 1): with build 2 a saved PositionDisplay 2 still
        # showed elapsed and remaining; the checks must say so.
        result = runner().run(without_council=True)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('FAIL saved 2 shows elapsed only, never both', result.stderr)
        self.assertIn('FAIL new widget with saved 2 shows elapsed only', result.stderr)
        self.assertNotIn('FAIL stored sequence 0 -> 1 -> 0, never 2', result.stderr)

    def test_pinned_widget_fails_the_same_check(self):
        # Holdout: the fixture must catch the upstream three-mode cycle.
        result = runner().run(baseline=True)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('stored sequence 0 -> 1 -> 0, never 2', result.stderr)


if __name__ == '__main__':
    unittest.main()
