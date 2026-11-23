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

How Mixxx 2.5.6 draws it, and what mixxx-waveform-three-band.patch changes:
- WaveformWidgetRenderer::getGain(applyCompensation) doubles m_gain for the
  renderers that ask for it: allshader Filtered (and the textured and
  software ones) do, allshader RGB does not. Doubled at 0.90, a band would
  sit on the edge in about a quarter of a typical track's columns
  (tools/performance/waveform-three-band-heights.py on the card's library).
  So the all-shader Filtered renderer alone does not ask for the doubling on
  a main row (mixpi::filteredHeightCompensation); getGain and every other
  renderer are as in Mixxx.
- [MixPi],waveform_colours (util/mixpiwaveformcolours.h) is owned by the main
  window, made after the waveform factory and deleted before it. A request
  from any thread is applied on the GUI thread, through
  WaveformWidgetFactory::mixpiSwitchTo; the control shows the type the factory
  runs (mixpiAppliedType) and follows mixpiWidgetTypeChanged.
- Three-band by default, once: CoreServices calls
  MixpiWaveformColours::defaultOnce when mixxx.cfg has been read, before the
  factory reads the type; [MixPi],ThreeBandDefault records it once the factory
  has taken type 19. mixpi-touch-defaults has no part in it, so the default
  holds however Mixxx is started and an old binary never gets it.
- mixpi-performance.py sets the three colours (and a SignalColor when the base
  has none) on the waveform template, so the main rows and the Loop panel's
  waveform carry them.

The native checks are in tests/native/waveform_three_band_test.cpp, built by
tests/native/waveform_three_band_runner.py.
"""
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
FILTERED = 'src/waveform/renderers/allshader/waveformrendererfiltered.cpp'
FACTORY = 'src/waveform/waveformwidgetfactory.cpp'
MAIN_WINDOW = 'src/mixxxmainwindow.cpp'
VIEWER = 'src/widget/wwaveformviewer.cpp'
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


class ThreeBandPatchTests(unittest.TestCase):
    def test_patch_files_and_removed_lines(self):
        text = PATCH.read_text()
        self.assertEqual(sorted(re.findall(r'^diff --git a/(\S+) b/\S+$', text, re.MULTILINE)),
                         ['src/coreservices.cpp', MAIN_WINDOW, 'src/mixxxmainwindow.h', HEADER, GAIN_HEADER,
                          FILTERED, FACTORY, 'src/waveform/waveformwidgetfactory.h', VIEWER])
        self.assertIn('--- /dev/null\n+++ b/' + HEADER, text)
        removed = [line for line in text.splitlines() if line.startswith('-') and not line.startswith('---')]
        self.assertEqual(removed, [
            '-    getGains(&allGain, true, &bandGain[0], &bandGain[1], &bandGain[2]);',
            '-                this,'])

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
        self.assertEqual(types['EmptyWaveform'], 0)
        header = added(HEADER)
        self.assertIn('static constexpr int kRgbType = 17;', header)
        self.assertIn('static constexpr int kThreeBandType = 19;', header)
        self.assertIn('QStringLiteral("waveform_colours")', header)
        self.assertIn('if (value != kRgb && value != kThreeBand) {', header)

    def test_a_request_is_applied_on_the_gui_thread_only(self):
        header = added(HEADER)
        # Not a direct connection: Qt queues a request from another thread to
        # the setting's own thread (review: Sol 1, Fable M1).
        self.assertNotIn('DirectConnection', header)
        self.assertRegex(header, r'connectValueChangeRequest\(\s*this, \[this\]\(double value\) '
                                 r'\{ request\(value\); \}\);')
        self.assertIn('if (QThread::currentThread() != thread()) {', header)
        # The factory is reached through the two calls the main window hands
        # over, never through Singleton::instance().
        self.assertNotIn('instance()', header)
        self.assertNotIn('WaveformWidgetFactory', added('src/coreservices.cpp'))

    def test_the_setting_lives_only_while_the_factory_does(self):
        text = PATCH.read_text()
        window = text[text.index('diff --git a/' + MAIN_WINDOW + ' '):text.index('diff --git a/src/mixxxmainwindow.h ')]
        # Made after the factory has its config, on the GUI thread ...
        made = window.index('+        m_pMixpiWaveformColours = new MixpiWaveformColours(')
        self.assertLess(window.index(' WaveformWidgetFactory::instance()->setConfig(m_pCoreServices->getSettings());'), made)
        # ... and deleted before the factory.
        deleted = window.index('+    delete m_pMixpiWaveformColours;')
        self.assertLess(made, deleted)
        self.assertLess(deleted, window.index('\n     WaveformWidgetFactory::destroy();'))
        added_window = added(MAIN_WINDOW)
        self.assertIn('return static_cast<int>(pFactory->mixpiAppliedType());', added_window)
        self.assertIn('return pFactory->mixpiSwitchTo(static_cast<WaveformWidgetType::Type>(type));', added_window)
        # The row follows every change of the type (the skin has loaded,
        # Mixxx's own Preferences).
        self.assertIn('&WaveformWidgetFactory::mixpiWidgetTypeChanged,', added_window)
        self.assertIn('[this] { m_pMixpiWaveformColours->sync(); });', added_window)
        # Stock: the factory is made in the main window's initialize and
        # destroyed in its destructor; the skin is parsed after both lines.
        stock = pinned_bytes(MAIN_WINDOW).decode()
        self.assertLess(stock.index('WaveformWidgetFactory::instance()->setConfig('),
                        stock.index('emit skinLoaded();'))

    def test_the_row_shows_what_the_factory_runs(self):
        header = added(HEADER)
        self.assertIn('m_pColours->setAndConfirm(valueForType(appliedType()));', header)
        self.assertEqual(header.count('setAndConfirm('), 1)
        # The factory is the only writer of the type after the default.
        self.assertEqual(header.count('setValue(typeKey()'), 1)
        factory = added(FACTORY)
        self.assertIn('if (!holder.m_waveformWidget || holder.m_waveformWidget->getType() != m_configType) {',
                      factory)
        self.assertIn('return mixpiAppliedType() == type;', factory)
        self.assertEqual(factory.count('emit mixpiWidgetTypeChanged();'), 2)
        # Stock: a widget that cannot start falls back to the empty one, and
        # the switch re-creates each waveform with its track, zoom and marker.
        stock = pinned_bytes(FACTORY).decode()
        self.assertIn('widget = new EmptyWaveformWidget(viewer->getGroup(), viewer);', stock)
        switch = stock[stock.index('bool WaveformWidgetFactory::setWidgetTypeFromHandle'):]
        switch = switch[:switch.index('\n}\n')]
        for line in ('createWaveformWidget(m_type, holder.m_waveformViewer);', 'widget->setTrack(pTrack);',
                     'viewer->setZoom(previousZoom);', 'setWidgetType(handle.m_type);'):
            self.assertIn(line, switch)
        # ... and createWaveformWidget marks the main rows again (J13).
        j13 = (RUNNER.PATCH_DIR / 'mixxx-waveform-height.patch').read_text()
        self.assertIn('+            widget->setMixpiMainWaveform(mixpi::isMainWaveform(viewer));', j13)
        # setWidgetType writes [Waveform],WaveformType to mixxx.cfg.
        self.assertIn('ConfigKey("[Waveform]", "WaveformType"), *pCurrentType);', stock)

    def test_the_default_is_set_in_mixxx_before_the_factory_reads_the_type(self):
        text = PATCH.read_text()
        core = text[text.index('diff --git a/src/coreservices.cpp '):text.index('diff --git a/' + MAIN_WINDOW + ' ')]
        self.assertLess(core.index(' UserSettingsPointer pConfig = m_pSettingsManager->settings();'),
                        core.index('+    MixpiWaveformColours::defaultOnce(pConfig);'))
        header = added(HEADER)
        self.assertRegex(header, r'if \(!pSettings->exists\(defaultDoneKey\(\)\)\) \{\s*'
                                 r'pSettings->setValue\(typeKey\(\), kThreeBandType\);')
        self.assertIn('ConfigKey(QStringLiteral("[MixPi]"), QStringLiteral("ThreeBandDefault"))', header)
        self.assertIn('ConfigKey(QStringLiteral("[Waveform]"), QStringLiteral("WaveformType"))', header)
        # The seeder has no part in it: an old binary never gets the default,
        # and a config the seeder cannot parse cannot lose it.
        seeder = SEEDER.read_text()
        for word in ('WaveformType', 'ThreeBandDefault', 'Waveform'):
            self.assertNotIn(word, seeder)

    def test_only_the_filtered_renderer_skips_the_doubled_height_on_main_rows(self):
        self.assertIn('return rgbStacked || !mainWaveform;', added(GAIN_HEADER))
        filtered = added(FILTERED)
        self.assertIn('#include "waveform/mixpiwaveformgain.h"', filtered)
        self.assertEqual(RUNNER.filtered_choice(filtered),
                         'mixpi::filteredHeightCompensation( m_waveformRenderer->isMixpiMainWaveform(), m_bRgbStacked)')
        # getGain is Mixxx's own, and so is what every other renderer asks it.
        self.assertNotIn('diff --git a/' + RENDERER + ' ', PATCH.read_text())
        self.assertIn('return applyCompensation ? m_gain * 2.f : m_gain;', pinned_bytes(RENDERER).decode())
        self.assertEqual(RUNNER.filtered_choice(pinned_bytes(FILTERED).decode()), 'true')
        for path, line in (
                ('src/waveform/renderers/allshader/waveformrendererrgb.cpp',
                 'getGains(&allGain, false, &lowGain, &midGain, &highGain);'),
                ('src/waveform/renderers/waveformrendererrgb.cpp',
                 'getGains(&allGain, true, &lowGain, &midGain, &highGain);'),
                ('src/waveform/renderers/allshader/waveformrenderertextured.cpp',
                 'getGains(&allGain, true, &lowGain, &midGain, &highGain);'),
                ('src/waveform/renderers/waveformrenderersignalbase.cpp',
                 'm_waveformRenderer->getGain(applyCompensation)')):
            self.assertIn(line, pinned_bytes(path).decode(), path)

    def test_a_passthrough_connection_ends_with_its_waveform_widget(self):
        # Review, Sol 8: with the viewer as context, each switch left one more.
        viewer = PATCH.read_text()
        viewer = viewer[viewer.index('diff --git a/' + VIEWER + ' '):]
        self.assertRegex(viewer, r' +&WWaveformViewer::passthroughChanged,\n-\s+this,\n\+\s+pWidget,\n')

    def test_the_overview_strips_have_their_own_type(self):
        factory = pinned_bytes(FACTORY).decode()
        self.assertNotIn('Overview', factory[factory.index('bool WaveformWidgetFactory::setWidgetTypeFromHandle'):
                                             factory.index('void WaveformWidgetFactory::setDefaultZoom')])
        self.assertNotIn('Overview', added(FACTORY))


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
                # Mixxx keeps them only beside a valid SignalColor; the test base
                # skin has none (review, Fable m5).
                self.assertEqual([e.text for e in visual.findall('SignalColor')], ['#32323c'], loop_display)

    def test_colours_replace_whatever_the_base_skin_says(self):
        module = HEIGHT_RUNNER.load('mixpi-performance')
        visual = ET.fromstring('<Visual><SignalLowColor>#ff0000</SignalLowColor><BgColor>#000</BgColor></Visual>')
        module.three_band_colours(visual)
        self.assertEqual({tag: [e.text for e in visual.findall(tag)] for tag in COLOURS},
                         {tag: [colour] for tag, colour in COLOURS.items()})
        self.assertEqual(visual.findtext('BgColor'), '#000')
        self.assertEqual([e.text for e in visual.findall('SignalColor')], ['#32323c'])

    def test_a_signal_colour_of_the_base_skin_is_kept(self):
        module = HEIGHT_RUNNER.load('mixpi-performance')
        visual = ET.fromstring('<Visual><SignalColor>#123456</SignalColor></Visual>')
        module.three_band_colours(visual)
        self.assertEqual([e.text for e in visual.findall('SignalColor')], ['#123456'])
        # Mixxx: the band colours are replaced unless SignalColor is valid too.
        colours = pinned_bytes('src/waveform/renderers/waveformsignalcolors.cpp').decode()
        self.assertIn('if (m_signalColor.isValid() && filteredColorValid) {\n        return true;', colours)
        blank = ET.fromstring('<Visual><SignalColor> </SignalColor></Visual>')
        module.three_band_colours(blank)
        self.assertEqual([e.text for e in blank.findall('SignalColor')], ['#32323c'])

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
        self.assertGreaterEqual(len(names), 30)
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
                     'and the setting shows what the waveforms run, 3-BAND, not what was asked',
                     'waveforms running type 17 show as RGB (0)',
                     'a saved 19 the factory could not apply does not show as 3-BAND',
                     'a repeated WaveformType key ends as one line with 19',
                     'the update switches a saved RGB to 3-BAND',
                     'the RGB choice is kept at restart 2',
                     'it reaches the waveform factory on the GUI thread',
                     'rapid opposing writes from a worker thread run in the order written and end in the last value',
                     'a main waveform\'s loudest band stops at kMainWaveformGain (0.90) of the edge in 3-BAND',
                     'the pregain knob still scales the 3-BAND height (0.5 to 0.45)'):
            self.assertRegex(output, r'(?m)^FAIL ' + re.escape(name))
        # Stock Mixxx's own getGain, asked what stock Filtered asks: doubled.
        self.assertIn('HEIGHTS main-filtered 1.800 main-rgb 0.900 loop-filtered 0.760 loop-rgb 0.380', output)
        # What stock Mixxx already does still holds without the patch.
        self.assertRegex(output, r'(?m)^PASS the Loop panel\'s waveform keeps Mixxx\'s doubled Filtered height')
        self.assertRegex(output, r'(?m)^PASS the Loop panel\'s RGB waveform keeps total_gain, as before')


if __name__ == '__main__':
    unittest.main()
