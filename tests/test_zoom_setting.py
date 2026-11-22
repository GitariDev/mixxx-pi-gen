"""Wave J9: Settings › Interface, Zoom + and − (spec 2f).

How Mixxx 2.5.6 holds the zoom:
- Each deck has [ChannelN],waveform_zoom (BaseTrackPlayerImpl): a control
  that takes 1-10 (WaveformWidgetRenderer's min and max; a smaller number is
  a closer view). It is not saved. waveform_zoom_up adds 1 and
  waveform_zoom_down takes 1 off; the Loop panel's − and + write those.
- Every waveform viewer of a deck follows that control, and the waveform
  factory starts each new viewer at [Waveform],DefaultZoom from mixxx.cfg
  (3). Mixxx's Preferences dialog is the only stock writer of DefaultZoom.
- [Waveform],ZoomSynchronization 0 (stage3/02-desktop/files/mixxx.cfg) keeps
  the decks apart: the Loop panel zooms only its deck.

So the skin alone cannot do it: a skin button can only write a control, and
nothing stock steps DefaultZoom or keeps a zoom over a restart.
mixxx-zoom-setting.patch adds [MixPi],waveform_zoom_in and
[MixPi],waveform_zoom_out (util/mixpizoomsetting.h, owned by CoreServices):
a press steps DefaultZoom by one between 1 and 10, sets both decks'
waveform_zoom to it and hands it to WaveformWidgetFactory::setDefaultZoom.
The save on change writes DefaultZoom within a second; at the next start
the factory starts both decks at it.

The native checks are in tests/native/zoom_setting_test.cpp, built by
tests/native/zoom_setting_runner.py.
"""
from pathlib import Path
import re
import subprocess
import sys
import unittest

from native.library_interface_runner import qt_available, pinned_bytes
from native import zoom_setting_runner as RUNNER

ROOT = Path(__file__).resolve().parents[1]
PATCH = RUNNER.PATCH_DIR / RUNNER.PATCH
HEADER = 'src/util/mixpizoomsetting.h'
CONFIG = ROOT / 'stage3/02-desktop/files/mixxx.cfg'
TEST = ROOT / 'tests/native/zoom_setting_test.cpp'


def added(path):
    text = PATCH.read_text()
    start = text.index('diff --git a/' + path + ' ')
    end = text.find('\ndiff --git', start + 1)
    return '\n'.join(line[1:] for line in text[start:end if end > 0 else None].splitlines()
                     if line.startswith('+') and not line.startswith('+++'))


def checks():
    """Every check("name") in the fixture, as printed (QStringLiteral text)."""
    source = TEST.read_text()
    names = []
    # The name is the last QStringLiteral of a check(...) call (calls whose
    # condition holds a lambda body, with its own ";", are left out).
    for call in re.findall(r'\bcheck\(([^;]*)\);', source, re.DOTALL):
        literals = re.findall(r'QStringLiteral\("([^"]*)"\)', call)
        if literals and literals[-1] and "%1" not in literals[-1]:
            names.append(literals[-1])
    return names


class ZoomPatchTests(unittest.TestCase):
    def test_patch_adds_the_header_and_wires_it_in_core_services(self):
        self.assertEqual(sorted(re.findall(r'^diff --git a/(\S+) b/\S+$', PATCH.read_text(), re.MULTILINE)),
                         ['src/coreservices.cpp', 'src/coreservices.h', HEADER])
        self.assertIn('--- /dev/null\n+++ b/' + HEADER, PATCH.read_text())
        removed = [line for line in PATCH.read_text().splitlines()
                   if line.startswith('-') and not line.startswith('---')]
        self.assertEqual(removed, [])

    def test_patch_is_registered_last(self):
        names = subprocess.check_output(['bash', str(ROOT / 'stage3/01-install-packages/01-run.sh'),
                                         '--mixxx-print-patches'], text=True).split()
        if PATCH.name not in names:
            self.skipTest(PATCH.name + ' is not registered yet')
        index = names.index(PATCH.name)
        self.assertEqual(names[index:index + 3], [PATCH.name, 'mixxx-eject-folders-view.patch',
                                                  'mixxx-removable-rows-fix.patch'])
        self.assertLess(names.index('mixxx-agreed-controls.patch'), names.index(PATCH.name))

    def test_header_steps_the_saved_zoom_and_both_decks(self):
        header = added(HEADER)
        for text in ('ConfigKey(QStringLiteral("[MixPi]"), QString::fromLatin1(item))',
                     'button("waveform_zoom_in")', 'button("waveform_zoom_out")',
                     'setZoom(zoom() - kStep);', 'setZoom(zoom() + kStep);', 'if (value > 0) {',
                     'QStringLiteral("[Waveform]"), QStringLiteral("DefaultZoom")',
                     'std::clamp(value, kMinZoom, kMaxZoom)',
                     'control("waveform_zoom_percent")',
                     'std::lround(kDefaultZoom / zoom * 100.0)',
                     'm_pSettings->setValue(kDefaultZoomKey, zoom);',
                     'for (const auto* group : {"[Channel1]", "[Channel2]"})',
                     'QStringLiteral("waveform_zoom")',
                     'static constexpr double kMinZoom = 1.0;', 'static constexpr double kMaxZoom = 10.0;',
                     'static constexpr double kDefaultZoom = 3.0;', 'static constexpr double kStep = 1.0;'):
            self.assertIn(text, header)
        # Nothing of the Loop panel's controls is touched.
        self.assertNotIn('waveform_zoom_up', header.replace('waveform_zoom_up/_down', ''))
        self.assertNotIn('ZoomSynchronization', header)

    def test_core_services_hands_the_zoom_to_the_waveform_factory(self):
        services = added('src/coreservices.cpp')
        self.assertIn('#include "util/mixpizoomsetting.h"', services)
        self.assertIn('#include "waveform/waveformwidgetfactory.h"', services)
        self.assertIn('m_pZoomSetting = std::make_unique<MixpiZoomSetting>(pConfig, [](double zoom) {', services)
        self.assertIn('pFactory->setDefaultZoom(zoom);', services)
        self.assertIn('m_pZoomSetting.reset();', services)
        self.assertIn('std::unique_ptr<MixpiZoomSetting> m_pZoomSetting;', added('src/coreservices.h'))


class MixxxZoomTests(unittest.TestCase):
    """The stock Mixxx 2.5.6 code the setting and the fixture rely on."""

    def source(self, path):
        return pinned_bytes(path).decode()

    def test_limits_and_default_are_the_renderers(self):
        renderer = self.source('src/waveform/renderers/waveformwidgetrenderer.cpp')
        for text in ('s_waveformMinZoom = 1.0;', 's_waveformMaxZoom = 10.0;', 's_waveformDefaultZoom = 3.0;'):
            self.assertIn(text, renderer)

    def test_loop_panel_controls_step_by_one_within_the_limits(self):
        player = self.source('src/mixer/basetrackplayer.cpp')
        self.assertIn('ConfigKey(getGroup(), "waveform_zoom")', player)
        self.assertIn('m_pWaveformZoom->set(1.0);', player)
        self.assertIn('m_pWaveformZoom->set(m_pWaveformZoom->get() + 1.0);', player)
        self.assertIn('m_pWaveformZoom->set(m_pWaveformZoom->get() - 1.0);', player)
        self.assertRegex(player, r'v <= WaveformWidgetRenderer::s_waveformMaxZoom\s*'
                                 r'&& v >= WaveformWidgetRenderer::s_waveformMinZoom\)\s*\{\s*'
                                 r'm_pWaveformZoom->setAndConfirm\(v\);')
        # Not a persist control: stock Mixxx forgets a deck's zoom.
        self.assertNotIn('"waveform_zoom"), true', player)

    def test_factory_starts_every_waveform_at_the_saved_default(self):
        factory = self.source('src/waveform/waveformwidgetfactory.cpp')
        self.assertIn('m_config->getValueString(ConfigKey("[Waveform]","DefaultZoom")).toDouble(&ok);', factory)
        self.assertIn('viewer->setZoom(m_defaultZoom);', factory)
        start = factory.index('void WaveformWidgetFactory::setDefaultZoom(double zoom) {')
        body = factory[start:factory.index('\n}\n', start)]
        self.assertIn('m_config->set(ConfigKey("[Waveform]","DefaultZoom"), ConfigValue(m_defaultZoom));', body)
        self.assertIn('holder.m_waveformViewer->setZoom(m_defaultZoom);', body)
        viewer = self.source('src/widget/wwaveformviewer.cpp')
        self.assertIn('m_pZoom = new ControlProxy(group, "waveform_zoom", this, ControlFlag::NoAssertIfMissing);',
                      viewer)

    def test_card_config_keeps_the_decks_apart_and_starts_at_three(self):
        section = CONFIG.read_text().split('\n[Waveform]\n', 1)[1].split('\n[', 1)[0]
        self.assertIn('\nDefaultZoom 3\n', '\n' + section + '\n')
        self.assertIn('\nZoomSynchronization 0\n', '\n' + section + '\n')


@unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
class ZoomNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patched = RUNNER.run()
        cls.baseline = RUNNER.run(baseline=True)

    def output(self, results):
        return ''.join(result.stdout for result in results)

    def test_every_check_passes_with_the_patch(self):
        for mode, result in zip(RUNNER.MODES, self.patched):
            self.assertEqual(result.returncode, 0, mode + result.stdout[-4000:] + result.stderr[-3000:])
        output = self.output(self.patched)
        names = checks()
        self.assertGreaterEqual(len(names), 20)
        for name in names:
            self.assertRegex(output, r'(?m)^PASS ' + re.escape(name))
        self.assertNotIn('FAIL ', output)
        self.assertIn('STEPS 2 1 1 1 2 3 4 5 6 7 8 9 10 10 10', output)
        self.assertIn('PERCENTS 300 150 100 75 60 50 43 38 33 30', output)
        saves = re.findall(r'MEASURE .* in mixxx.cfg on disk ms: (-?\d+)', output)
        self.assertEqual(len(saves), 2)
        for measured in saves:
            self.assertTrue(0 <= int(measured) < 1000, measured)

    def test_the_checks_fail_without_the_patch(self):
        for mode, result in zip(RUNNER.MODES, self.baseline):
            self.assertNotEqual(result.returncode, 0, mode)
        output = self.output(self.baseline)
        for name in ('[MixPi],waveform_zoom_in (+) and [MixPi],waveform_zoom_out (−) exist',
                     '+ zooms both decks in by one step (3 to 2)',
                     '− again: both decks at 4',
                     'the zoom is saved in mixxx.cfg in under 1 s',
                     '+ stops at 1, step for step as the Loop panel\'s + (2 1 1 1)',
                     'after SIGKILL 1 s after + mixxx.cfg holds DefaultZoom 2',
                     'after the restart both decks start at the saved zoom 2',
                     'the readout starts at 100 for the saved zoom 3',
                     'the readout is 300 150 100 75 60 50 43 38 33 30 for zoom 1 to 10'):
            self.assertRegex(output, r'(?m)^FAIL ' + re.escape(name))
        # What stock Mixxx already does still holds without the patch.
        self.assertRegex(output, r'(?m)^PASS both decks start at the saved zoom 3')
        self.assertRegex(output, r'(?m)^PASS the Loop panel\'s \+ zooms only its deck, as before')


if __name__ == '__main__':
    unittest.main()
