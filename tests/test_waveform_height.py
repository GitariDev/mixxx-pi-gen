"""Wave J13: bigger main waveforms on the Decks page (spec 2h).

What Mixxx 2.5.6 does:
- The card draws its waveforms with [Waveform] WaveformType 17, the
  all-shader RGB renderer. The image does not install
  stage3/02-desktop/files/mixxx.cfg (its install in 02-desktop/03-run.sh is
  commented out; test_no_audio_routing_seed.py keeps it so), so a new card
  has no WaveformType and WaveformWidgetFactory::autoChooseWidgetType picks
  AllShaderRGBWaveform (17) on a GL build with shaders, and saves it.
- A waveform's height is total_gain x VisualGain_0 x halfBreadth / 255 x
  filtered.all (allshader/waveformrendererrgb.cpp, getGains in
  waveformrenderersignalbase.cpp, m_gain in waveformwidgetrenderer.cpp).
  total_gain is the pregain knob times the ReplayGain correction
  (enginepregain.cpp), so a loudly mastered track (the smallest ReplayGain)
  is drawn smallest: on the card's library a typical track's peaks reach
  about 37 % of the half height (tools/performance/waveform-height.py).
- VisualGain_0 also sets the overview strips' scale (woverview.cpp), so a
  larger VisualGain_0 would change them too, and would make the quietly
  mastered tracks clip, not the loud ones.

mixxx-waveform-height.patch (option A, agreed 2026-11-22): a viewer inside
the skin group MixpiWaveRow (the Decks page's main waveform rows) takes the
pregain knob only for its height; every other waveform (the Loop panel's,
in the bottom strip) keeps total_gain. The sound is unchanged.

mixxx-waveform-height-gain.patch (wave J15, owner 2026-11-22: "Let's set
the gain to around .80"): the main waveforms draw at kMainWaveformGain = 0.80
x that height, so the loudest peaks (levels are capped at 255) stop at 80 % of
the half height. The Loop panel's waveform and the overview strips are
unchanged.

The native checks are in tests/native/waveform_height_test.cpp, built by
tests/native/waveform_height_runner.py.
"""
import importlib.util
from pathlib import Path
import re
import sqlite3
import struct
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zlib

from native.library_interface_runner import qt_available, pinned_bytes
from native import waveform_height_runner as RUNNER

ROOT = Path(__file__).resolve().parents[1]
PATCH = RUNNER.PATCH_DIR / RUNNER.PATCH
GAIN_PATCH = RUNNER.PATCH_DIR / RUNNER.GAIN_PATCH
HEADER = 'src/waveform/mixpiwaveformgain.h'
RENDERER = 'src/waveform/renderers/waveformwidgetrenderer.cpp'
RENDERER_H = 'src/waveform/renderers/waveformwidgetrenderer.h'
FACTORY = 'src/waveform/waveformwidgetfactory.cpp'


def load_script():
    spec = importlib.util.spec_from_file_location(
        'waveform_height', ROOT / 'tools/performance/waveform-height.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def changed(path, sign, patch=PATCH):
    text = patch.read_text()
    start = text.index('diff --git a/' + path + ' ')
    end = text.find('\ndiff --git', start + 1)
    return [line[1:] for line in text[start:end if end > 0 else None].splitlines()
            if line.startswith(sign) and not line.startswith(sign * 3)]


def added(path, patch=PATCH):
    return '\n'.join(changed(path, '+', patch))


def main_group():
    return re.search(r'static const QString kGroup = QStringLiteral\("([^"]+)"\);', added(HEADER))[1]


class WaveformHeightPatchTests(unittest.TestCase):
    def test_patch_changes_only_its_files(self):
        text = PATCH.read_text()
        self.assertEqual(sorted(re.findall(r'^diff --git a/(\S+) b/\S+$', text, re.MULTILINE)),
                         sorted([HEADER, RENDERER, RENDERER_H, FACTORY]))
        self.assertIn('--- /dev/null\n+++ b/' + HEADER, text)
        removed = [line for path in (RENDERER, RENDERER_H, FACTORY) for line in changed(path, '-')]
        self.assertEqual(removed, ['    m_gain = m_pGainControlObject->get();'])

    def test_patch_is_registered_last(self):
        names = subprocess.check_output(['bash', str(ROOT / 'stage3/01-install-packages/01-run.sh'),
                                         '--mixxx-print-patches'], text=True).split()
        if PATCH.name not in names:
            self.skipTest(PATCH.name + ' is not registered yet')
        if GAIN_PATCH.name in names:
            # Wave J15: the gain patch comes right after it, last.
            self.assertEqual(names[-2:], [PATCH.name, GAIN_PATCH.name])
        else:
            self.assertEqual(names[-1], PATCH.name)

    def test_header_tells_main_waveforms_apart_and_picks_their_gain(self):
        header = added(HEADER)
        for text in ('static const QString kGroup = QStringLiteral("MixpiWaveRow");',
                     'for (const QWidget* pWidget = pViewer; pWidget != nullptr;',
                     'pWidget = pWidget->parentWidget()) {',
                     'if (pWidget->objectName() == mainWaveformGroup()) {',
                     'inline double waveformHeightGain(bool mainWaveform, double pregain, double totalGain) {',
                     'return mainWaveform ? pregain : totalGain;'):
            self.assertIn(text, header)

    def test_renderer_takes_the_pregain_for_a_main_waveform(self):
        renderer = added(RENDERER)
        self.assertIn('#include "waveform/mixpiwaveformgain.h"', renderer)
        self.assertIn('m_pPregainControlObject = new ControlProxy(\n            m_group, "pregain");', renderer)
        self.assertIn('delete m_pPregainControlObject;', renderer)
        self.assertIn('m_gain = mixpi::waveformHeightGain(m_mixpiMainWaveform,\n'
                      '            m_pPregainControlObject->get(),\n'
                      '            m_pGainControlObject->get());', renderer)
        self.assertIn('m_mixpiMainWaveform(false),', renderer)
        header = added(RENDERER_H)
        self.assertIn('void setMixpiMainWaveform(bool mainWaveform) {', header)
        self.assertIn('ControlProxy* m_pPregainControlObject;', header)

    def test_factory_marks_every_widget_it_makes(self):
        factory = added(FACTORY)
        self.assertIn('#include "waveform/mixpiwaveformgain.h"', factory)
        self.assertIn('widget->setMixpiMainWaveform(mixpi::isMainWaveform(viewer));', factory)
        # Both places that make a widget (a new viewer, a type change) go
        # through createWaveformWidget, where the mark is set.
        stock = pinned_bytes(FACTORY).decode()
        self.assertEqual(len(re.findall(r'= createWaveformWidget\(m_type, ', stock)), 2)


class WaveformHeightGainPatchTests(unittest.TestCase):
    """Wave J15: the main waveforms at 0.80 x the J13 height."""

    def test_gain_patch_changes_only_the_header(self):
        text = GAIN_PATCH.read_text()
        self.assertEqual(re.findall(r'^diff --git a/(\S+) b/\S+$', text, re.MULTILINE), [HEADER])
        self.assertNotIn('--- /dev/null', text)
        self.assertEqual(changed(HEADER, '-', GAIN_PATCH), [
            '/// The gain a waveform\'s height follows: the pregain knob for a main',
            '/// waveform, total_gain for every other waveform.',
            '    return mainWaveform ? pregain : totalGain;'])

    def test_main_waveforms_take_the_owners_gain(self):
        header = added(HEADER, GAIN_PATCH)
        self.assertIn('constexpr double kMainWaveformGain = 0.80;', header)
        self.assertIn('return mainWaveform ? pregain * kMainWaveformGain : totalGain;', header)
        self.assertEqual(float(re.search(r'kMainWaveformGain = ([0-9.]+);', header)[1]), RUNNER.MAIN_GAIN)

    def test_gain_patch_applies_after_the_height_patch(self):
        # Its context is the J13 header, so the J13 patch must come first.
        context = [line[1:] for line in GAIN_PATCH.read_text().splitlines() if line.startswith(' ')]
        j13 = added(HEADER).splitlines()
        for line in context:
            self.assertIn(line, j13)


class MainWaveformGroupTests(unittest.TestCase):
    """The skin's main waveform rows carry the name the patch looks for."""

    def build(self, loop_display):
        with tempfile.TemporaryDirectory() as folder:
            root = ET.parse(RUNNER.generate_skin(folder, loop_display)).getroot()
        parents = {child: parent for parent in root.iter() for child in parent}

        def groups(element):
            names = []
            while element in parents:
                element = parents[element]
                if element.tag in ('WidgetGroup', 'WidgetStack'):
                    names.append(element.findtext('ObjectName'))
            return names

        return [(visual.findtext('Channel'), groups(visual)) for visual in root.iter('Visual')]

    def test_each_deck_main_waveform_is_in_the_group_the_patch_names(self):
        group = main_group()
        for loop_display in ('focus', 'overlay'):
            with self.subTest(loop_display=loop_display):
                visuals = self.build(loop_display)
                main = [(channel, names) for channel, names in visuals if group in names]
                self.assertEqual([channel for channel, _ in main], ['1', '2'])
                for _, names in main:
                    # Directly in the row, in the Decks page's waveform area.
                    self.assertEqual(names[0], group)
                    self.assertIn('MixpiWaveforms', names)

    def test_the_loop_panel_waveforms_are_not_in_it(self):
        group = main_group()
        loop = [(channel, names) for channel, names in self.build('focus')
                if 'MixpiFocusedOverview' in names]
        self.assertEqual([channel for channel, _ in loop], ['1', '2'])
        for _, names in loop:
            self.assertNotIn(group, names)
        # Only the main rows and the Loop panel's strips have a waveform.
        self.assertEqual(len(self.build('focus')), 4)
        self.assertEqual(len(self.build('overlay')), 2)


class MixxxWaveformTests(unittest.TestCase):
    """The stock Mixxx code the patch and the measurement rely on."""

    def source(self, path):
        return pinned_bytes(path).decode()

    def test_card_renderer_is_the_auto_choice(self):
        factory = self.source(FACTORY)
        self.assertRegex(factory, r'if \(isOpenGlShaderAvailable\(\)\) \{\s*#ifndef MIXXX_USE_QOPENGL\s*'
                                  r'return WaveformWidgetType::GLSLRGBWaveform;\s*#else\s*'
                                  r'return WaveformWidgetType::AllShaderRGBWaveform;')
        self.assertIn('if (!ok || !setWidgetType(type, &m_configType)) {\n'
                      '        setWidgetType(autoChooseWidgetType(), &m_configType);', factory)
        self.assertIn('AllShaderRGBWaveform,        // 17 RGB (all-shaders)',
                      self.source('src/waveform/widgets/waveformwidgettype.h'))
        recipe = (ROOT / 'stage3/02-desktop/03-run.sh').read_text()
        self.assertIn('# install -m 755 files/mixxx.cfg ${ROOTFS_DIR}/home/pi/.mixxx/mixxx.cfg', recipe)

    def test_height_follows_the_widget_gain_and_visual_gain(self):
        rgb = self.source('src/waveform/renderers/allshader/waveformrendererrgb.cpp')
        self.assertIn('getGains(&allGain, false, &lowGain, &midGain, &highGain);', rgb)
        self.assertIn('const float heightFactor = allGain * halfBreadth / m_maxValue;', rgb)
        self.assertIn('halfBreadth - heightFactor * maxAllChn[0],', rgb)
        base = self.source('src/waveform/renderers/waveformrenderersignalbase.cpp')
        self.assertIn('*pAllGain = static_cast<CSAMPLE_GAIN>(m_waveformRenderer->getGain(applyCompensation)) *\n'
                      '                static_cast<CSAMPLE_GAIN>(factory->getVisualGain(WaveformWidgetFactory::All));',
                      base)
        renderer = self.source(RENDERER)
        self.assertIn('m_pGainControlObject = new ControlProxy(\n            m_group, "total_gain");', renderer)
        self.assertEqual(renderer.count('m_gain = m_pGainControlObject->get();'), 1)

    def test_total_gain_is_pregain_times_replaygain(self):
        pregain = self.source('src/engine/enginepregain.cpp')
        self.assertIn('auto totalGain = static_cast<CSAMPLE_GAIN>(m_pPotmeterPregain->get()) *\n'
                      '            math_clamp(fReplayGainCorrection, 0.0f, 10.0f);\n\n'
                      '    m_pTotalGain->set(totalGain);', pregain)
        self.assertIn('m_pPotmeterPregain = new ControlAudioTaperPot(ConfigKey(group, "pregain")', pregain)
        self.assertIn('fReplayGainCorrection = static_cast<CSAMPLE_GAIN>(s_pDefaultBoost->get());', pregain)

    def test_overview_strips_do_not_use_the_widget_gain(self):
        overview = self.source('src/widget/woverview.cpp')
        self.assertNotIn('getGain(', overview)
        self.assertNotIn('WaveformWidgetRenderer', overview)

    def test_skin_parser_parents_a_viewer_to_its_named_group(self):
        parser = self.source('src/skin/legacy/legacyskinparser.cpp')
        self.assertIn('WWaveformViewer* viewer = new WWaveformViewer(group, m_pConfig, m_pParent);\n'
                      '    viewer->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);\n'
                      '    WaveformWidgetFactory* pFactory = WaveformWidgetFactory::instance();\n'
                      '    pFactory->setWaveformWidget(viewer, node, *m_pContext);', parser)
        self.assertRegex(parser, r'setupWidget\(node, pGroup->toQWidget\(\)\);[\s\S]{0,400}'
                                 r'parseChildren\(node, pGroup\);')
        self.assertIn('m_pParent = pGroup;', parser)

    def test_analyser_clamps_levels_at_255(self):
        analyser = self.source('src/analyzer/analyzerwaveform.h')
        self.assertIn('datum.filtered.all = static_cast<unsigned char>(math_min(255.0,', analyser)
        self.assertIn('return std::pow(invalue, 2.0f * 0.316f);', analyser)


def varint(value):
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def waveform_file(levels, packed=False):
    """A Waveform-5.0 analysis file (qCompress of protobuf) with these
    interleaved left/right filtered.all levels."""
    if packed:
        body = b''.join(varint(level) for level in levels)
        signal = b'\x0a' + varint(len(body)) + body
    else:
        signal = b''.join(b'\x08' + varint(level) for level in levels)
    message = b'\x09' + struct.pack('<d', 441.0) + b'\x1a' + varint(len(signal)) + signal
    return struct.pack('>I', len(message)) + zlib.compress(message)


class MeasurementScriptTests(unittest.TestCase):
    def setUp(self):
        self.script = load_script()
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        root = Path(self.folder.name)
        self.db = root / 'mixxxdb.sqlite'
        (root / 'analysis').mkdir()
        connection = sqlite3.connect(self.db)
        connection.execute('CREATE TABLE library (id INTEGER PRIMARY KEY, artist TEXT, title TEXT, replaygain FLOAT)')
        connection.execute('CREATE TABLE track_analysis (id INTEGER PRIMARY KEY, track_id INTEGER, type INTEGER)')
        # Track 1: loud master (ReplayGain 0.25), every level 255 on the left
        # and 204 on the right.  Track 2: no ReplayGain yet, all 102.
        connection.execute("INSERT INTO library VALUES (1, 'A', 'Loud', 0.25), (2, 'B', 'New', 0)")
        connection.execute('INSERT INTO track_analysis VALUES (10, 1, 1), (11, 1, 2), (12, 2, 1)')
        connection.commit()
        connection.close()
        (root / 'analysis/10').write_bytes(waveform_file([255, 204] * 300))
        (root / 'analysis/11').write_bytes(b'summary is not read')
        (root / 'analysis/12').write_bytes(waveform_file([102, 102] * 300, packed=True))
        self.analysis = root / 'analysis'

    def test_reads_the_main_waveform_levels(self):
        self.assertEqual(self.script.signal_all(waveform_file([1, 2, 300, 4])), [1, 2, 300, 4])
        self.assertEqual(self.script.signal_all(waveform_file([7, 8], packed=True)), [7, 8])
        self.assertEqual(self.script.pixel_peaks([1, 9, 5, 2, 3, 4, 8, 1, 2, 1, 0, 0]), [5, 9, 8, 1])

    def test_option_a_at_the_owners_gain(self):
        # Wave J15: --a-gain 0.8 is the build; a level of 255 stops at 0.8.
        rows = {row['track_id']: row for row in self.script.measure(self.db, self.analysis, 0.8, 2.0)}
        self.assertAlmostEqual(rows[1]['A']['max'], 0.8)
        self.assertEqual(rows[1]['A']['edge_pct'], 0.0)
        self.assertAlmostEqual(rows[2]['A']['max'], 0.8 * 0.4)

    def test_today_option_a_and_option_b_heights(self):
        rows = {row['track_id']: row for row in self.script.measure(self.db, self.analysis, 1.0, 2.0)}
        self.assertEqual(sorted(rows), [1, 2])
        loud, new = rows[1], rows[2]
        self.assertAlmostEqual(loud['today']['max'], 0.25)
        self.assertAlmostEqual(loud['today']['p50'], 0.25 * 204 / 255)
        self.assertEqual(loud['today']['edge_pct'], 0.0)
        self.assertAlmostEqual(loud['A']['max'], 1.0)
        self.assertAlmostEqual(loud['A']['edge_pct'], 50.0)
        self.assertEqual(loud['A']['clip_pct'], 0.0)
        self.assertAlmostEqual(loud['B']['max'], 0.5)
        self.assertAlmostEqual(new['today']['max'], 10 ** (-6 / 20) * 102 / 255)
        self.assertAlmostEqual(new['A']['max'], 0.4)
        self.assertAlmostEqual(new['B']['max'], 2 * 10 ** (-6 / 20) * 0.4)

    def test_prints_a_summary(self):
        output = subprocess.run(['python3', '-I', str(ROOT / 'tools/performance/waveform-height.py'),
                                 str(self.db), str(self.analysis)],
                                capture_output=True, text=True, check=True, timeout=60).stdout
        self.assertIn('2 analysed tracks, 1 with a ReplayGain', output)
        self.assertIn('A (VisualGain 1, no ReplayGain)', output)


@unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
class WaveformHeightNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patched = RUNNER.run()
        cls.baseline = RUNNER.run(baseline=True)
        cls.without_gain = RUNNER.run(gain=False)

    def output(self, results):
        return ''.join(result.stdout for result in results)

    def test_every_check_passes_with_the_patch(self):
        for mode, result in zip(RUNNER.MODES, self.patched):
            self.assertEqual(result.returncode, 0, mode + result.stdout[-4000:] + result.stderr[-3000:])
        output = self.output(self.patched)
        self.assertNotIn('FAIL ', output)
        self.assertEqual(len(re.findall(r'(?m)^PASS ', output)), 34)  # focus 4 + 2 x 8, overlay 4 + 2 x 5
        self.assertIn('RESULT focus PASS', output)
        self.assertIn('RESULT overlay PASS', output)
        # Levels 64 128 200 255 in a 128 px row: the main waveform at 0.80
        # of the stored level (wave J15), the Loop panel's at ReplayGain
        # 0.377 of it.
        self.assertIn('HEIGHTS focus deck 1 rg 0.377 pregain 1 main: 12.85 25.70 40.16 51.20', output)
        self.assertIn('HEIGHTS focus deck 1 rg 0.377 pregain 1 loop panel: 6.06 12.11 18.92 24.13', output)
        self.assertIn('HEIGHTS focus deck 2 rg 0.377 pregain 2 main: 25.70 51.40 80.31 102.40', output)
        self.assertRegex(output, r'(?m)^VIEWER focus channel 1 main 1 in .*/MixpiWaveforms/MixpiWaveRow$')
        self.assertRegex(output, r'(?m)^VIEWER focus channel 1 main 0 in .*/MixpiFocusedOverview$')

    def test_the_checks_fail_without_the_patch(self):
        for mode, result in zip(RUNNER.MODES, self.baseline):
            self.assertNotEqual(result.returncode, 0, mode)
        output = self.output(self.baseline)
        for mode in RUNNER.MODES:
            for name in ('%s: both main waveforms are told apart as main' % mode,
                         '%s deck 1: the main waveform\'s height is pregain x VisualGain_0 x 0.80 x '
                         'halfBreadth / 255 x level (ReplayGain left out)' % mode,
                         '%s deck 2: a level of 255 stops at 0.80 of the half height, '
                         'short of the edge' % mode,
                         '%s deck 1: the pregain knob still scales the main waveform (x2)' % mode,
                         '%s deck 2: a track with no ReplayGain is drawn at 0.80 of its '
                         'stored level' % mode):
                self.assertRegex(output, r'(?m)^FAIL ' + re.escape(name))
        # What stock Mixxx already does still holds without the patch.
        for name in ('focus: the Loop panel\'s waveforms are not main',
                     'focus deck 1: the Loop panel\'s waveform still follows total_gain',
                     'focus deck 2: the pregain knob still scales the Loop panel\'s waveform (x2)',
                     'focus: the Decks page has one main waveform per deck'):
            self.assertRegex(output, r'(?m)^PASS ' + re.escape(name))

    def test_the_gain_checks_fail_without_the_gain_patch(self):
        # Wave J15: the stack with mixxx-waveform-height.patch but without
        # mixxx-waveform-height-gain.patch draws the main waveforms at the
        # full J13 height.
        for mode, result in zip(RUNNER.MODES, self.without_gain):
            self.assertNotEqual(result.returncode, 0, mode)
        output = self.output(self.without_gain)
        self.assertIn('HEIGHTS focus deck 1 rg 0.377 pregain 1 main: 16.06 32.13 50.20 64.00', output)
        for mode in RUNNER.MODES:
            for channel in (1, 2):
                for name in ('the main waveform\'s height is pregain x VisualGain_0 x 0.80 x '
                             'halfBreadth / 255 x level (ReplayGain left out)',
                             'a level of 255 stops at 0.80 of the half height, short of the edge',
                             'the pregain knob still scales the main waveform (x2)',
                             'the pregain knob still scales the main waveform (x0.5)',
                             'a track with no ReplayGain is drawn at 0.80 of its stored level'):
                    self.assertRegex(output, r'(?m)^FAIL ' + re.escape(
                        '%s deck %d: %s' % (mode, channel, name)))
            # J13's choice of viewers holds without the gain patch.
            self.assertRegex(output, r'(?m)^PASS ' + re.escape(
                '%s: both main waveforms are told apart as main' % mode))
        # The Loop panel's waveforms are the same with and without it.
        for channel in (1, 2):
            for name in ('the Loop panel\'s waveform still follows total_gain',
                         'the pregain knob still scales the Loop panel\'s waveform (x2)',
                         'the Loop panel\'s waveform keeps the default boost'):
                self.assertRegex(output, r'(?m)^PASS ' + re.escape(
                    'focus deck %d: %s' % (channel, name)))
        loop = r'(?m)^HEIGHTS focus deck \d rg 0\.377 pregain 1 loop panel: .*$'
        self.assertEqual(re.findall(loop, output), re.findall(loop, self.output(self.patched)))


if __name__ == '__main__':
    unittest.main()
