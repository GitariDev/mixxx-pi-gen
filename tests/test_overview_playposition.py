"""Build G1: the DECKS overview strip froze after about 6 h 46 min without a seek.

The owner (build F session, 19 Nov 2026): "Good catch on the strip. Please Fix".
mixxx-overview-playposition.patch backports upstream Mixxx bef0af3172
(mixxxdj/mixxx#16245, fixes #9751). Native fixture:
tests/native/overview_playposition_runner.py.
"""
import importlib.util
from pathlib import Path
import unittest

from native.library_interface_runner import qt_available

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / 'stage3/01-install-packages/files/mixxx-overview-playposition.patch'

NATIVE_CHECKS = (
    'a new EngineBuffer starts its indicator counter at 0',
    *[size + ' frames: ' + check for size in ('256', '512', '1024') for check in (
        'playposition updates at about 15 per second (140-151 in 10 s)',
        'CueControl::updateIndicators runs with every playposition update',
        'the counter never passes the threshold by more than one buffer',
        'the counter never goes negative after INT_MAX',
        'playposition keeps updating past the old overflow point',
        'the overview is within 0.1 s of the play position past the old overflow point',
    )],
    '7 h paused without a seek: the counter never goes negative',
    'after 7 h without a seek, playposition updates while playing',
    'after 7 h without a seek, the overview moves 10 s in 10 s of play',
    'a seek shows in playposition on the next callback',
)
# Stock 2.5.6 (no patch): the overflow and rate checks fail, a seek still works.
BASELINE_FAILS = (
    'a new EngineBuffer starts its indicator counter at 0',
    '1024 frames: playposition updates at about 15 per second (140-151 in 10 s)',
    '1024 frames: the counter never goes negative after INT_MAX',
    '1024 frames: playposition keeps updating past the old overflow point',
    '7 h paused without a seek: the counter never goes negative',
    'after 7 h without a seek, playposition updates while playing',
    'after 7 h without a seek, the overview moves 10 s in 10 s of play',
)


def runner():
    spec = importlib.util.spec_from_file_location(
        'overview_playposition_runner', ROOT / 'tests/native/overview_playposition_runner.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OverviewPlaypositionPatchTests(unittest.TestCase):
    def setUp(self):
        self.patch = PATCH.read_text()

    def test_patch_is_the_upstream_commit(self):
        touched = [line.split()[2][2:] for line in self.patch.splitlines()
                   if line.startswith('diff --git ')]
        self.assertEqual(touched, ['src/engine/enginebuffer.cpp'])
        added = [line[1:] for line in self.patch.splitlines()
                 if line.startswith('+') and not line.startswith('+++')]
        self.assertEqual(added, ['          m_iSamplesSinceLastIndicatorUpdate(0),',
                                 '        m_iSamplesSinceLastIndicatorUpdate = 0;'])
        self.assertFalse([line for line in self.patch.splitlines()
                          if line.startswith('-') and not line.startswith('---')])

    def test_header_names_the_source(self):
        self.assertIn('bef0af317269dba735b06352f775d698c26f7406', self.patch)
        self.assertIn('https://github.com/mixxxdj/mixxx/pull/16245', self.patch)
        self.assertIn('https://github.com/mixxxdj/mixxx/issues/9751', self.patch)

    def test_reset_follows_both_indicator_updates(self):
        hunk = self.patch[self.patch.index('m_playposSlider->set(fFractionalPlaypos);'):]
        self.assertLess(hunk.index('m_pCueControl->updateIndicators();'),
                        hunk.index('+        m_iSamplesSinceLastIndicatorUpdate = 0;'))


@unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
class NativeOverviewPlaypositionTests(unittest.TestCase):
    def test_playposition_keeps_updating_past_the_overflow(self):
        result = runner().run()
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output[-6000:])
        self.assertIn('FAILURES 0', result.stdout)
        self.assertNotIn('FAIL ', result.stdout)
        for check in NATIVE_CHECKS:
            self.assertIn('PASS ' + check, result.stdout)

    def test_stock_engine_buffer_fails_the_same_checks(self):
        # Holdout: without the patch the fixture must see the freeze.
        result = runner().run(baseline=True)
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, output[-6000:])
        for check in BASELINE_FAILS:
            self.assertIn('FAIL ' + check, result.stdout)
        self.assertIn('PASS a seek shows in playposition on the next callback', result.stdout)


if __name__ == '__main__':
    unittest.main()
