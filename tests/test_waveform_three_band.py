"""Three-band main waveforms (R&D thread, owner 2026-11-23).

The owner's choices (docs/ideas/rnd-waveform-three-band-20261122/OWNER-DECISIONS.md):
- Direction A Overlay: Mixxx's all-shader Filtered waveform (type 19) draws
  bass, mids and highs over each other, in Pioneered's own colours (low
  #004ee4, mid #c95a00, high #f6e9d3).
- A setting in Settings › Advanced, "Waveform colours", RGB or 3-BAND, the
  row under Read ahead; three-band by default after the next build; the Loop
  panel's waveform follows the setting (Mixxx's waveform type covers every
  scrolling waveform).
- 2026-11-24, owner: the overview strips follow the setting too (Mixxx's
  Filtered overview in the same three colours with 3-BAND, the RGB overview
  with RGB). Leader, the same day, while the owner was away: the overview's
  status text keeps its colour (MixpiStatusTextColor).
- After the reviews: the Loop panel's three-band waveform draws at the same
  height as RGB there ("Same height as RGB"); a start that cannot draw 3-BAND
  shows the choice disabled ("Show it unavailable"); a third waveform type
  keeps lighting RGB.
- J13/J15's height: the main waveforms draw at pregain x kMainWaveformGain
  (0.90), so the loudest tracks stop 10 % from the edge.

How Mixxx 2.5.6 draws it, and what mixxx-waveform-three-band.patch changes:
- WaveformWidgetRenderer::getGain(applyCompensation) doubles m_gain for the
  renderers that ask for it: allshader Filtered (and the textured and
  software ones) do, allshader RGB does not. Doubled at 0.90, a band would
  sit on the edge in about a quarter of a typical track's columns
  (tools/performance/waveform-three-band-heights.py on the card's library).
  So the all-shader Filtered renderer alone does not ask for the doubling
  (mixpi::filteredHeightCompensation), on a main row or in the Loop panel:
  3-BAND draws at RGB's height in both. getGain, the Stacked type and every
  other renderer are as in Mixxx.
- [MixPi],waveform_colours (util/mixpiwaveformcolours.h) is owned by the main
  window, made after the waveform factory and deleted before it. A request
  from any thread is applied on the GUI thread, through
  WaveformWidgetFactory::mixpiSwitchTo; the control shows the type the factory
  runs (mixpiAppliedType) and follows mixpiWidgetTypeChanged.
- [MixPi],waveform_three_band_available is read-only, 1 when the factory has
  a handle for type 19. Only the 3-BAND button binds its enabled state to it,
  as the Audio buffer buttons do with [MixPi],buffer_available; the page's
  #MixpiButton:disabled rule draws it.
- Three-band by default, once: CoreServices calls
  MixpiWaveformColours::defaultOnce when mixxx.cfg has been read, before the
  factory reads the type; [MixPi],ThreeBandDefault records it once the factory
  has taken type 19. mixpi-touch-defaults has no part in it, so the default
  holds however Mixxx is started and an old binary never gets it.
- mixpi-performance.py sets the three colours (and a SignalColor when the base
  has none) on the waveform template, so the main rows and the Loop panel's
  waveform carry them, and on the overview template, so every overview strip
  does, with MixpiStatusTextColor #007de1 (Pioneered's overview colour).
- The overview type follows the row: MixpiWaveformColours::sync writes
  [Waveform],WaveformOverviewType (0 Filtered with type 19, otherwise 2 RGB)
  to mixxx.cfg and forces it onto Mixxx's read-only control of that name when
  it exists; nothing is written when the value is already right. Mixxx's
  Preferences makes that control after the first sync, from mixxx.cfg, and
  every WOverview follows it live. The RGB overview draws with
  SignalRGB*Color only; its status text is the one use of SignalLowColor, so
  WOverview reads MixpiStatusTextColor first (falling back to SignalLowColor).

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
OVERVIEW = 'src/widget/woverview.cpp'
OVERVIEW_HEADER = 'src/widget/woverview.h'
GAIN_HEADER = 'src/waveform/mixpiwaveformgain.h'
RENDERER = 'src/waveform/renderers/waveformwidgetrenderer.h'
FILTERED = 'src/waveform/renderers/allshader/waveformrendererfiltered.cpp'
FACTORY = 'src/waveform/waveformwidgetfactory.cpp'
MAIN_WINDOW = 'src/mixxxmainwindow.cpp'
VIEWER = 'src/widget/wwaveformviewer.cpp'
SEEDER = ROOT / 'stage3/02-desktop/files/bin/mixpi-touch-defaults'
QSS = ROOT / 'stage3/01-install-packages/files/mixpi-performance.qss'
AVAILABLE = '[MixPi],waveform_three_band_available'
TEST = ROOT / 'tests/native/waveform_three_band_test.cpp'
COLOURS = {'SignalLowColor': '#004ee4', 'SignalMidColor': '#c95a00', 'SignalHighColor': '#f6e9d3'}
STATUS_TEXT = '#007de1'


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
                          FILTERED, FACTORY, 'src/waveform/waveformwidgetfactory.h',
                          OVERVIEW, OVERVIEW_HEADER, VIEWER])
        self.assertIn('--- /dev/null\n+++ b/' + HEADER, text)
        removed = [line for line in text.splitlines() if line.startswith('-') and not line.startswith('---')]
        self.assertEqual(removed, [
            '-    getGains(&allGain, true, &bandGain[0], &bandGain[1], &bandGain[2]);',
            '-    m_lowColor.setAlphaF(0.5f);',
            '-            QBrush(m_lowColor), 1.25 * m_scaleFactor, Qt::SolidLine, Qt::RoundCap);',
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
        # 3-BAND is available when the factory has a handle for the type.
        self.assertRegex(added_window, r'waveforms\.canDraw = \[pFactory\]\(int type\) \{\s*'
                                       r'return pFactory->findHandleIndexFromType\(\s*'
                                       r'static_cast<WaveformWidgetType::Type>\(type\)\) >= 0;')
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
        self.assertIn('const int type = appliedType();\n        m_pColours->setAndConfirm(valueForType(type));', header)
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

    def test_three_band_availability_is_a_read_only_control_from_the_factory(self):
        # Owner, 2026-11-23: "Show it unavailable".
        header = added(HEADER)
        self.assertIn('QStringLiteral("waveform_three_band_available")', header)
        self.assertIn('m_pThreeBandAvailable->setReadOnly();', header)
        self.assertIn('m_pThreeBandAvailable->setParent(this);', header)
        # Written with every sync, from the factory's answer for type 19 only.
        self.assertRegex(header, r'void sync\(\) \{\s*m_pThreeBandAvailable->forceSet\(\s*'
                                 r'm_waveforms\.canDraw && m_waveforms\.canDraw\(kThreeBandType\) \? 1 : 0\);')
        self.assertEqual(header.count('m_pThreeBandAvailable->forceSet('), 1)
        # Stock: a read-only control ignores set(); the handles are found once,
        # when the factory is made, and a handle index below 0 means no handle.
        self.assertIn('qWarning() << m_key << "is read-only. Ignoring set of value:" << v;',
                      pinned_bytes('src/control/controlobject.cpp').decode())
        stock = pinned_bytes(FACTORY).decode()
        self.assertEqual(stock.count('    evaluateWidgets();'), 1)
        self.assertIn('int index = -1;\n    for (int i = 0; i < m_waveformWidgetHandles.size(); i++) {', stock)

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

    def test_only_the_filtered_renderer_skips_the_doubled_height(self):
        # On a main row and in the Loop panel alike (owner, 2026-11-23: "Same
        # height as RGB"); the Stacked type keeps Mixxx's height.
        gain = added(GAIN_HEADER)
        self.assertIn('inline bool filteredHeightCompensation(bool rgbStacked) {\n    return rgbStacked;\n}', gain)
        self.assertNotIn('mainWaveform', gain)
        filtered = added(FILTERED)
        self.assertIn('#include "waveform/mixpiwaveformgain.h"', filtered)
        self.assertEqual(RUNNER.filtered_choice(filtered), 'mixpi::filteredHeightCompensation(m_bRgbStacked)')
        self.assertNotIn('isMixpiMainWaveform', filtered)
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

    def test_the_factory_does_not_switch_the_overviews_the_setting_does(self):
        factory = pinned_bytes(FACTORY).decode()
        self.assertNotIn('Overview', factory[factory.index('bool WaveformWidgetFactory::setWidgetTypeFromHandle'):
                                             factory.index('void WaveformWidgetFactory::setDefaultZoom')])
        self.assertNotIn('Overview', added(FACTORY))

    def test_the_overview_type_follows_the_row(self):
        # Owner, 2026-11-24: "the smaller bottom bar currently isn't 3 band".
        header = added(HEADER)
        self.assertIn('static constexpr int kOverviewFiltered = 0;', header)
        self.assertIn('static constexpr int kOverviewRgb = 2;', header)
        self.assertIn('return type == kThreeBandType ? kOverviewFiltered : kOverviewRgb;', header)
        self.assertIn('ConfigKey(QStringLiteral("[Waveform]"), QStringLiteral("WaveformOverviewType"))', header)
        # At every sync, from the type the factory runs.
        self.assertRegex(header, r'const int type = appliedType\(\);\s*'
                                 r'm_pColours->setAndConfirm\(valueForType\(type\)\);\s*'
                                 r'syncOverview\(overviewTypeFor\(type\)\);')
        self.assertEqual(header.count('syncOverview('), 2)
        # mixxx.cfg always, only when the value differs ...
        self.assertRegex(header, r'if \(m_pSettings->getValue<int>\(overviewTypeKey\(\), -1\) != overviewType\) \{\s*'
                                 r'm_pSettings->setValue\(overviewTypeKey\(\), overviewType\);')
        # ... and Mixxx's read-only control, forced, when it exists.
        self.assertRegex(header, r'ControlObject::getControl\(overviewTypeKey\(\), ControlFlag::NoWarnIfMissing\);\s*'
                                 r'if \(pOverviewType && pOverviewType->get\(\) != overviewType\) \{\s*'
                                 r'pOverviewType->forceSet\(overviewType\);')
        self.assertIn("An\n///   overview type picked in Mixxx's Preferences is replaced at the next sync.", header)

    def test_mixxx_makes_the_overview_control_after_the_first_sync(self):
        # Stock: WOverview::Type is Filtered 0, HSV 1, RGB 2; the overviews
        # follow [Waveform],WaveformOverviewType live.
        woverview = pinned_bytes(OVERVIEW).decode()
        types = pinned_bytes(OVERVIEW_HEADER).decode()
        self.assertRegex(types, r'enum class Type \{\s*Filtered,\s*HSV,\s*RGB,\s*\};')
        self.assertIn('m_pTypeControl->connectValueChanged(this, &WOverview::slotTypeControlChanged);', woverview)
        # The control is Mixxx's Preferences' own: read-only, from mixxx.cfg.
        dialog = pinned_bytes('src/preferences/dialog/dlgprefwaveform.cpp').decode()
        made = dialog[dialog.index('DlgPrefWaveform::DlgPrefWaveform('):dialog.index('// Populate waveform options.')]
        for line in ('m_pTypeControl = std::make_unique<ControlPushButton>(kOverviewTypeCfgKey);',
                     'm_pTypeControl->setReadOnly();',
                     'm_pConfig->getValue<WOverview::Type>(kOverviewTypeCfgKey, WOverview::Type::RGB);',
                     'm_pTypeControl->forceSet(cfgTypeIndex);'):
            self.assertIn(line, made)
        self.assertIn('new DlgPrefWaveform(this, m_pConfig, pLibrary)',
                      pinned_bytes('src/preferences/dialog/dlgpreferences.cpp').decode())
        # forceSet skips the read-only handler.
        control = pinned_bytes('src/control/controlobject.h').decode()
        self.assertRegex(control, r'inline void forceSet\(double value\) \{\s*setAndConfirm\(value\);')
        # The main window: the setting (and its first sync) is made before
        # Mixxx's Preferences, which is made before the skin.
        text = PATCH.read_text()
        window = text[text.index('diff --git a/' + MAIN_WINDOW + ' '):text.index('diff --git a/src/mixxxmainwindow.h ')]
        self.assertIn('+        m_pMixpiWaveformColours = new MixpiWaveformColours(', window)
        self.assertLess(window.index('+        m_pMixpiWaveformColours = new MixpiWaveformColours('),
                        window.index('     connect(this,\n             &MixxxMainWindow::skinLoaded,'))
        stock = pinned_bytes(MAIN_WINDOW).decode()
        initialize = stock[stock.index('void MixxxMainWindow::initialize() {'):]
        self.assertLess(initialize.index('            &MixxxMainWindow::skinLoaded,'),
                        initialize.index('m_pPrefDlg = new DlgPreferences('))
        self.assertLess(initialize.index('WaveformWidgetFactory::instance()->startVSync('),
                        initialize.index('m_pPrefDlg = new DlgPreferences('))
        self.assertLess(initialize.index('m_pPrefDlg = new DlgPreferences('),
                        initialize.index('if (!loadConfiguredSkin()) {'))

    def test_the_rgb_overview_keeps_its_look(self):
        # Stock: the RGB overview draws with SignalRGB*Color only; the band
        # colours are the Filtered (and HSV) overview's, and SignalLowColor is
        # also the status text's.
        woverview = pinned_bytes(OVERVIEW).decode()
        rgb = woverview[woverview.index('void WOverview::drawNextPixmapPartRGB('):
                        woverview.index('void WOverview::paintText(')]
        self.assertNotRegex(rgb, r'get(Low|Mid|High)Color\(\)|m_lowColor')
        self.assertEqual(re.findall(r'getRgb(?:Low|Mid|High)Color', rgb),
                         ['getRgbLowColor', 'getRgbMidColor', 'getRgbHighColor'])
        self.assertEqual(woverview.count('m_lowColor'), 3)
        self.assertIn('m_lowColor = m_signalColors.getLowColor();', woverview)
        self.assertIn('    m_lowColor.setAlphaF(0.5f);', woverview[woverview.index('void WOverview::paintText('):])

    def test_the_status_text_colour_is_read_with_a_fallback(self):
        # Leader, 2026-11-24: the status text keeps its colour.
        overview = added(OVERVIEW)
        self.assertRegex(overview, r'm_mixpiStatusTextColor = context\.selectColor\(node, '
                                   r'QStringLiteral\("MixpiStatusTextColor"\)\);\s*'
                                   r'm_mixpiStatusTextColor = m_mixpiStatusTextColor\.isValid\(\)\s*'
                                   r'\? WSkinColor::getCorrectColor\(m_mixpiStatusTextColor\)\.toRgb\(\)\s*'
                                   r': m_lowColor;')
        self.assertIn('    m_mixpiStatusTextColor.setAlphaF(0.5f);', overview)
        self.assertIn('QBrush(m_mixpiStatusTextColor), 1.25 * m_scaleFactor', overview)
        self.assertIn('QColor m_mixpiStatusTextColor;', added(OVERVIEW_HEADER))
        # The fallback, m_lowColor, is still SignalLowColor (stock line kept).
        text = PATCH.read_text()
        section = text[text.index('diff --git a/' + OVERVIEW + ' '):text.index('diff --git a/' + OVERVIEW_HEADER + ' ')]
        self.assertIn('\n     m_lowColor = m_signalColors.getLowColor();\n+', section)


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

    def test_every_overview_strip_has_the_owners_colours_and_the_status_text_colour(self):
        for loop_display, root in self.roots.items():
            overviews = list(root.iter('Overview'))
            # The Decks page's two strips and the browse page's two.
            self.assertEqual(len(overviews), 4, loop_display)
            self.assertEqual(sorted(o.findtext('Channel') for o in overviews), ['1', '1', '2', '2'])
            for overview in overviews:
                with self.subTest(loop_display=loop_display, channel=overview.findtext('Channel')):
                    for tag, colour in COLOURS.items():
                        self.assertEqual([e.text for e in overview.findall(tag)], [colour])
                    self.assertEqual([e.text for e in overview.findall('MixpiStatusTextColor')], [STATUS_TEXT])
                    self.assertEqual([e.text for e in overview.findall('SignalColor')], ['#32323c'])

    def test_the_overview_template_keeps_a_base_signal_colour_and_one_status_colour(self):
        module = HEIGHT_RUNNER.load('mixpi-performance')
        overview = ET.fromstring('<Overview><SignalColor>#222</SignalColor><SignalLowColor>#007de1</SignalLowColor>'
                                 '<MixpiStatusTextColor>#fff</MixpiStatusTextColor></Overview>')
        module.three_band_overview(overview)
        self.assertEqual([e.text for e in overview.findall('SignalColor')], ['#222'])
        self.assertEqual([e.text for e in overview.findall('MixpiStatusTextColor')], [STATUS_TEXT])
        self.assertEqual({tag: [e.text for e in overview.findall(tag)] for tag in COLOURS},
                         {tag: [colour] for tag, colour in COLOURS.items()})

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
            buttons = [(b.findtext('State/Text'),
                        [c.findtext('ConfigKey') for c in b.findall('Connection') if c.find('BindProperty') is None],
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

    def bound(self, button):
        """A button's property bindings: (property, control, transform)."""
        return [(c.findtext('BindProperty'), c.findtext('ConfigKey'), c.find('Transform'))
                for c in button.findall('Connection') if c.find('BindProperty') is not None]

    def test_only_the_three_band_button_is_enabled_by_its_availability(self):
        # Owner, 2026-11-23: "Show it unavailable".
        for loop_display, root in self.roots.items():
            with self.subTest(loop_display=loop_display):
                guarded = [b for b in root.iter('PushButton')
                           if AVAILABLE in [c.findtext('ConfigKey') for c in b.findall('Connection')]]
                self.assertEqual([b.findtext('State/Text') for b in guarded], ['3-BAND'])
                # No transform: enabled is the control's value, 1 or 0.
                self.assertEqual(self.bound(guarded[0]), [('enabled', AVAILABLE, None)])
                pane = next(e for e in root.iter('WidgetGroup')
                            if e.findtext('ObjectName') == 'MixpiAdvancedSettings')
                rgb = next(b for b in pane.iter('PushButton') if b.findtext('State/Text') == 'RGB')
                self.assertEqual(self.bound(rgb), [])
                # Nothing else in the skin reads or writes the control.
                self.assertEqual(sum(e.text == AVAILABLE for e in root.iter('ConfigKey')), 1)
                # The page's own disabled look covers the button; no new rule.
                self.assertEqual(guarded[0].findtext('ObjectName'), rgb.findtext('ObjectName'))
                self.assertEqual(guarded[0].findtext('ObjectName'), 'MixpiButton')
        qss = QSS.read_text()
        self.assertRegex(qss, r'#MixpiButton:disabled,[^{]*\{\s*'
                              r'color: #7f8896; background: #13161b; border: 1px dashed #2c333d;')
        self.assertNotIn('waveform', qss.lower())

    def test_the_audio_buffer_buttons_disable_the_same_way(self):
        # The pattern the 3-BAND button follows.
        root = self.roots['focus']
        buffers = [b for b in root.iter('PushButton')
                   if b.findtext('Connection/ConfigKey') == '[MixPi],buffer_frames']
        self.assertEqual(len(buffers), 3)
        for b in buffers:
            self.assertEqual(self.bound(b), [('enabled', '[MixPi],buffer_available', None)])
            self.assertEqual(b.findtext('ObjectName'), 'MixpiButton')


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
        self.assertIn('HEIGHTS main-filtered 0.900 main-rgb 0.900 loop-filtered 0.380 loop-rgb 0.380', output)
        saves = re.findall(r'MEASURE .* in mixxx.cfg on disk ms: (-?\d+)', output)
        self.assertEqual(len(saves), 3)
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
                     'the pregain knob still scales the 3-BAND height (0.5 to 0.45)',
                     '[MixPi],waveform_three_band_available is 1 when the factory has a handle for type 19',
                     '[MixPi],waveform_three_band_available is 0 when the factory has no handle for type 19',
                     'the availability follows the factory\'s handle for type 19 (sync)',
                     'a write to [MixPi],waveform_three_band_available is ignored (read-only)',
                     'the Loop panel\'s 3-BAND waveform draws at total_gain (0.38), not Mixxx\'s doubled 0.76',
                     'the Loop panel\'s 3-BAND and RGB waveforms reach the same height',
                     'at the first sync, before the overview control exists, 3-BAND writes overview type 0 '
                     '(Filtered) to mixxx.cfg',
                     'RGB (type 17) sets the overview control and mixxx.cfg to 2 (RGB)',
                     '3-BAND (type 19) sets the overview control and mixxx.cfg to 0 (Filtered)',
                     'a third waveform type sets the overview control and mixxx.cfg to 2 (RGB)',
                     'an overview type picked in Mixxx\'s Preferences is replaced at the next sync',
                     'a sync with the overview type already right writes nothing to mixxx.cfg or the control',
                     'a write from a worker thread changes the overview type on the GUI thread only'):
            self.assertRegex(output, r'(?m)^FAIL ' + re.escape(name))
        # Stock Mixxx's own getGain, asked what stock Filtered asks: doubled.
        self.assertIn('HEIGHTS main-filtered 1.800 main-rgb 0.900 loop-filtered 0.760 loop-rgb 0.380', output)
        # What stock Mixxx already does still holds without the patch.
        self.assertRegex(output, r'(?m)^PASS the Stacked type \(the same renderer class\) keeps Mixxx\'s doubled height')
        self.assertRegex(output, r'(?m)^PASS the Loop panel\'s RGB waveform keeps total_gain, as before')


if __name__ == '__main__':
    unittest.main()
