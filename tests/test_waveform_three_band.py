"""Three-band main waveforms (R&D thread, owner 2026-11-23).

The owner's choices (docs/ideas/rnd-waveform-three-band-20261122/OWNER-DECISIONS.md):
- Direction A Overlay: Mixxx's all-shader Filtered waveform (type 19) draws
  bass, mids and highs over each other, in Pioneered's own colours (low
  #004ee4, mid #c95a00, high #f6e9d3).
- A setting in Settings › Advanced, "Waveform colours", RGB or 3-BAND, the
  row under Read ahead; three-band by default after the next build; the Loop
  panel's waveform follows the setting (Mixxx's waveform type covers every
  scrolling waveform); the overview strips stay as they are.
- J13/J15's height: the main waveforms draw at pregain x kMainWaveformGain
  (0.90), so the loudest tracks stop 10 % from the edge.

How Mixxx 2.5.6 draws it:
- WaveformWidgetRenderer::getGain(applyCompensation) doubles m_gain for the
  renderers that ask for it: allshader Filtered (and the textured ones) do,
  allshader RGB does not. Doubled at 0.90, a band would sit on the edge in
  about a quarter of a typical track's columns (tools/performance/
  waveform-three-band-heights.py on the card's library). So
  mixxx-waveform-three-band.patch has the main waveforms skip the doubling
  (mixpi::heightCompensation); every other waveform keeps it.
- [MixPi],waveform_colours (util/mixpiwaveformcolours.h, owned by
  CoreServices) switches [Waveform],WaveformType between 17 and 19 through
  WaveformWidgetFactory::setWidgetTypeFromHandle, which re-creates every
  scrolling waveform through createWaveformWidget, where J13 marks the main
  rows again.
- mixpi-touch-defaults sets WaveformType 19 once ([MixPi] ThreeBandDefault 1
  records it), so the card opens in 3-BAND after the update and a later RGB
  choice is kept.
- mixpi-performance.py sets the three colours on the waveform template, so the
  main rows and the Loop panel's waveform carry them.

The native checks are in tests/native/waveform_three_band_test.cpp, built by
tests/native/waveform_three_band_runner.py.
"""
import importlib.machinery
import importlib.util
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

from native.library_interface_runner import qt_available, pinned_bytes
from native import waveform_three_band_runner as RUNNER
from native import waveform_height_runner as HEIGHT_RUNNER

ROOT = Path(__file__).resolve().parents[1]
PATCH = RUNNER.PATCH_DIR / RUNNER.PATCH
HEADER = 'src/util/mixpiwaveformcolours.h'
GAIN_HEADER = 'src/waveform/mixpiwaveformgain.h'
RENDERER = 'src/waveform/renderers/waveformwidgetrenderer.h'
SEEDER = ROOT / 'stage3/02-desktop/files/bin/mixpi-touch-defaults'
TEST = ROOT / 'tests/native/waveform_three_band_test.cpp'
COLOURS = {'SignalLowColor': '#004ee4', 'SignalMidColor': '#c95a00', 'SignalHighColor': '#f6e9d3'}


def added(path):
    text = PATCH.read_text()
    start = text.index('diff --git a/' + path + ' ')
    end = text.find('\ndiff --git', start + 1)
    return '\n'.join(line[1:] for line in text[start:end if end > 0 else None].splitlines()
                     if line.startswith('+') and not line.startswith('+++'))


def checks():
    """Every check("name") in the fixture, as printed (QStringLiteral text)."""
    names = []
    for call in re.findall(r'\bcheck\(([^;]*)\);', TEST.read_text(), re.DOTALL):
        literals = re.findall(r'QStringLiteral\("([^"]*)"\)', call)
        if literals and literals[-1] and '%1' not in literals[-1]:
            names.append(literals[-1])
    return names


def waveform_types():
    """WaveformWidgetType::Type values, counted as the compiler does (the
    enum gives no explicit values; its comments are not all right)."""
    source = pinned_bytes('src/waveform/widgets/waveformwidgettype.h').decode()
    body = source[source.index('enum Type {') + len('enum Type {'):source.index('};')]
    names = [re.match(r'\s*(\w+)', line).group(1) for line in body.splitlines()
             if re.match(r'\s*\w+\s*(=\s*0\s*)?,', line)]
    return {name: index for index, name in enumerate(names)}


def seeder():
    loader = importlib.machinery.SourceFileLoader('mixpi_touch_defaults', str(SEEDER))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class ThreeBandPatchTests(unittest.TestCase):
    def test_patch_files_and_only_one_changed_line(self):
        text = PATCH.read_text()
        self.assertEqual(sorted(re.findall(r'^diff --git a/(\S+) b/\S+$', text, re.MULTILINE)),
                         ['src/coreservices.cpp', 'src/coreservices.h', HEADER, GAIN_HEADER, RENDERER])
        self.assertIn('--- /dev/null\n+++ b/' + HEADER, text)
        removed = [line for line in text.splitlines() if line.startswith('-') and not line.startswith('---')]
        self.assertEqual(removed, ['-        return applyCompensation ? m_gain * 2.f : m_gain;'])

    def test_patch_is_registered_last_after_its_prerequisites(self):
        names = subprocess.check_output(['bash', str(ROOT / 'stage3/01-install-packages/01-run.sh'),
                                         '--mixxx-print-patches'], text=True).split()
        self.assertEqual(names[-1], PATCH.name)
        for prerequisite in ('mixxx-waveform-height.patch', 'mixxx-waveform-height-gain.patch',
                             'mixxx-zoom-setting.patch'):
            self.assertLess(names.index(prerequisite), names.index(PATCH.name))

    def test_types_are_mixxx_rgb_and_filtered(self):
        types = waveform_types()
        self.assertEqual(types['AllShaderRGBWaveform'], 17)
        self.assertEqual(types['AllShaderFilteredWaveform'], 19)
        header = added(HEADER)
        self.assertIn('static constexpr int kRgbType = 17;', header)
        self.assertIn('static constexpr int kThreeBandType = 19;', header)
        self.assertIn('QStringLiteral("waveform_colours")', header)
        self.assertIn('ConfigKey(QStringLiteral("[Waveform]"), QStringLiteral("WaveformType"))', header)
        # Confirmed only after the factory switched; anything but 0 and 1 refused.
        self.assertRegex(header, r'if \(!m_applyType \|\| !m_applyType\(type\)\) \{\s*return;')
        self.assertIn('if (value != kRgb && value != kThreeBand) {', header)

    def test_main_waveforms_skip_the_doubled_height(self):
        gain = added(GAIN_HEADER)
        self.assertIn('return applyCompensation && !mainWaveform ? 2.0 : 1.0;', gain)
        self.assertIn('return m_gain * mixpi::heightCompensation(m_mixpiMainWaveform, applyCompensation);',
                      added(RENDERER))
        self.assertIn('#include "waveform/mixpiwaveformgain.h"', added(RENDERER))
        # Stock: Filtered asks for the doubled gain and RGB does not.
        filtered = pinned_bytes('src/waveform/renderers/allshader/waveformrendererfiltered.cpp').decode()
        rgb = pinned_bytes('src/waveform/renderers/allshader/waveformrendererrgb.cpp').decode()
        self.assertIn('getGains(&allGain, true, &bandGain[0], &bandGain[1], &bandGain[2]);', filtered)
        self.assertIn('getGains(&allGain, false, &lowGain, &midGain, &highGain);', rgb)
        base = pinned_bytes('src/waveform/renderers/waveformrenderersignalbase.cpp').decode()
        self.assertIn('m_waveformRenderer->getGain(applyCompensation)', base)

    def test_core_services_switches_every_waveform_through_the_factory(self):
        core = added('src/coreservices.cpp')
        self.assertIn('std::make_unique<MixpiWaveformColours>(pConfig, [](int type) {', core)
        self.assertIn('pFactory->findHandleIndexFromType(', core)
        self.assertIn('return handle >= 0 && pFactory->setWidgetTypeFromHandle(handle);', core)
        self.assertIn('m_pWaveformColours.reset();', core)
        factory = pinned_bytes('src/waveform/waveformwidgetfactory.cpp').decode()
        switch = factory[factory.index('bool WaveformWidgetFactory::setWidgetTypeFromHandle'):]
        switch = switch[:switch.index('\n}\n')]
        # The switch re-creates each waveform with its track, zoom and play marker ...
        for line in ('createWaveformWidget(m_type, holder.m_waveformViewer);', 'widget->setTrack(pTrack);',
                     'viewer->setZoom(previousZoom);', 'setWidgetType(handle.m_type);'):
            self.assertIn(line, switch)
        # ... and createWaveformWidget marks the main rows again (J13).
        j13 = (RUNNER.PATCH_DIR / 'mixxx-waveform-height.patch').read_text()
        self.assertIn('+            widget->setMixpiMainWaveform(mixpi::isMainWaveform(viewer));', j13)
        # setWidgetType writes [Waveform],WaveformType to mixxx.cfg.
        self.assertIn('ConfigKey("[Waveform]", "WaveformType"), *pCurrentType);', factory)

    def test_the_overview_strips_have_their_own_type(self):
        factory = pinned_bytes('src/waveform/waveformwidgetfactory.cpp').decode()
        self.assertNotIn('Overview', factory[factory.index('bool WaveformWidgetFactory::setWidgetTypeFromHandle'):
                                             factory.index('void WaveformWidgetFactory::setDefaultZoom')])


class ThreeBandSkinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roots = {}
        for loop_display in ('focus', 'overlay'):
            with tempfile.TemporaryDirectory() as folder:
                cls.roots[loop_display] = ET.parse(HEIGHT_RUNNER.generate_skin(folder, loop_display)).getroot()

    def test_every_scrolling_waveform_has_the_owners_colours(self):
        for loop_display, root in self.roots.items():
            visuals = list(root.iter('Visual'))
            # Two main rows; the card's "focus" Loop panel adds a waveform per deck.
            self.assertEqual(len(visuals), 4 if loop_display == 'focus' else 2, loop_display)
            for visual in visuals:
                for tag, colour in COLOURS.items():
                    with self.subTest(loop_display=loop_display, tag=tag):
                        self.assertEqual([e.text for e in visual.findall(tag)], [colour])

    def test_colours_replace_whatever_the_base_skin_says(self):
        module = HEIGHT_RUNNER.load('mixpi-performance')
        visual = ET.fromstring('<Visual><SignalLowColor>#ff0000</SignalLowColor><BgColor>#000</BgColor></Visual>')
        module.three_band_colours(visual)
        self.assertEqual({tag: [e.text for e in visual.findall(tag)] for tag in COLOURS},
                         {tag: [colour] for tag, colour in COLOURS.items()})
        self.assertEqual(visual.findtext('BgColor'), '#000')

    def advanced_rows(self, root):
        pane = next(e for e in root.iter('WidgetGroup') if e.findtext('ObjectName') == 'MixpiAdvancedSettings')
        rows = []
        for row in pane.find('Children'):
            if row.findtext('ObjectName') != 'MixpiSetting':
                continue
            title = next(e.findtext('Text') for e in row.iter('Label')
                         if e.findtext('ObjectName') == 'MixpiSettingTitle')
            buttons = [(b.findtext('State/Text'), [c.findtext('ConfigKey') for c in b.findall('Connection')],
                        [ET.tostring(t).decode() for t in b.iter('Transform')])
                       for b in row.iter('PushButton')]
            rows.append((title, buttons))
        return rows

    def test_advanced_has_the_row_under_read_ahead(self):
        for loop_display, root in self.roots.items():
            rows = self.advanced_rows(root)
            self.assertEqual([title for title, _ in rows],
                             ['Waveform FPS', 'Read ahead', 'Waveform colours', 'Mixxx preferences'], loop_display)
            buttons = dict(rows)['Waveform colours']
            self.assertEqual([text for text, _, _ in buttons], ['RGB', '3-BAND'])
            for _, keys, _ in buttons:
                self.assertEqual(keys, ['[MixPi],waveform_colours', '[MixPi],waveform_colours'])
            # Each lights when the setting is its value, like the page's other choices.
            self.assertIn('<IsEqual>0</IsEqual>', ''.join(buttons[0][2]))
            self.assertIn('<IsEqual>1</IsEqual>', ''.join(buttons[1][2]))


class ThreeBandDefaultTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = Path(self.temp.name) / '.mixxx/mixxx.cfg'
        self.seeder = seeder()

    def test_a_new_card_starts_in_three_band(self):
        self.seeder.seed(self.config)
        text = self.config.read_text()
        self.assertIn('[Waveform]\nWaveformType 19\n', text)
        self.assertIn('[MixPi]\nThreeBandDefault 1\n', text)

    def test_the_update_switches_a_saved_rgb_once_and_keeps_the_rest(self):
        self.config.parent.mkdir()
        source = ('[Config]\nResizableSkin Pioneered\n\n[Library]\nRowHeight 34\n'
                  'Font Sans Serif,-1,17,5,50,0,0,0,0,0\n\n[MixPi]\nRamCacheMB 1024\n\n'
                  '[Waveform]\nDefaultZoom 3\nWaveformType 17\nZoomSynchronization 0\n')
        self.config.write_text(source)
        self.seeder.seed(self.config)
        expected = source.replace('WaveformType 17', 'WaveformType 19').replace(
            '[MixPi]\nRamCacheMB 1024\n', '[MixPi]\nThreeBandDefault 1\nRamCacheMB 1024\n')
        self.assertEqual(self.config.read_text(), expected)

    def test_a_later_rgb_choice_is_kept(self):
        self.seeder.seed(self.config)
        chosen = self.config.read_text().replace('WaveformType 19', 'WaveformType 17')
        self.config.write_text(chosen)
        before = self.config.stat().st_mtime_ns
        self.seeder.seed(self.config)
        self.seeder.seed(self.config)
        self.assertEqual(self.config.read_text(), chosen)
        self.assertEqual(self.config.stat().st_mtime_ns, before)

    def test_a_config_without_a_waveform_type_gets_one(self):
        self.config.parent.mkdir()
        self.config.write_text('[Waveform]\nDefaultZoom 3\n')
        self.seeder.seed(self.config)
        self.assertIn('[Waveform]\nWaveformType 19\nDefaultZoom 3\n', self.config.read_text())


@unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
class ThreeBandNativeTests(unittest.TestCase):
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
        self.assertGreaterEqual(len(names), 17)
        for name in names:
            self.assertRegex(output, r'(?m)^PASS ' + re.escape(name))
        self.assertNotIn('FAIL ', output)
        self.assertIn('HEIGHTS main-filtered 0.900 main-rgb 0.900 loop-filtered 0.760 loop-rgb 0.380', output)
        saves = re.findall(r'MEASURE .* in mixxx.cfg on disk ms: (-?\d+)', output)
        self.assertEqual(len(saves), 2)
        for measured in saves:
            self.assertTrue(0 <= int(measured) < 1000, measured)

    def test_the_checks_fail_without_the_patch(self):
        for mode, result in zip(RUNNER.MODES, self.baseline):
            self.assertNotEqual(result.returncode, 0, mode)
        output = self.output(self.baseline)
        for name in ('[MixPi],waveform_colours exists',
                     'RGB asks the waveform factory for type 17 (all-shader RGB)',
                     '3-BAND is saved in mixxx.cfg in under 1 s',
                     'values other than 0 and 1 are refused and change nothing',
                     'a saved WaveformType 17 shows as RGB (0)',
                     'a main waveform\'s loudest band stops at kMainWaveformGain (0.90) of the edge in 3-BAND',
                     'the pregain knob still scales the 3-BAND height (0.5 to 0.45)'):
            self.assertRegex(output, r'(?m)^FAIL ' + re.escape(name))
        # What stock Mixxx already does still holds without the patch.
        self.assertRegex(output, r'(?m)^PASS the Loop panel\'s waveform keeps Mixxx\'s doubled Filtered height')
        self.assertRegex(output, r'(?m)^PASS the Loop panel\'s RGB waveform keeps total_gain, as before')


if __name__ == '__main__':
    unittest.main()
