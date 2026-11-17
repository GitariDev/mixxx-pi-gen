"""Validate real control semantics and pinned waveform reuse in the owned pages.

Qt rendering/audio still require the separate Pi trial. These checks detect
misrouted controls, missing release events, and unsafe loop-toggle semantics.
They also run the skin's screen model (UI-REDESIGN-PLAN R-1, R-7, R-8, R-9,
R-11) on paper: which widgets are visible for each [MixPi],screen value, and
what each button writes on press and release.
"""
import copy
import importlib.util
import os
from pathlib import Path
import re
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
FILES=ROOT/'stage3/01-install-packages/files'

def load(name):
    spec=importlib.util.spec_from_file_location(name,FILES/(name+'.py'))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

SKIN=load('mixpi-performance')
TOUCH=load('pioneered-touch')
SCREEN='[MixPi],screen'


def transform(connection, value):
    """Mixxx ValueTransformer::transform for the nodes the skin uses."""
    steps = connection.find('Transform')
    for step in steps if steps is not None else ():
        if step.tag == 'IsEqual':
            value = float(value == float(step.text))
        elif step.tag == 'Not':
            value = float(not value)
        elif step.tag == 'Add':
            value = value + float(step.text)
        elif step.tag == 'Invert':
            value = -value
        else:
            raise AssertionError(step.tag)
    return value


def inverse(connection, value):
    """Mixxx ValueTransformer::transformInverse (last node first)."""
    steps = connection.find('Transform')
    for step in reversed(list(steps) if steps is not None else []):
        if step.tag == 'IsEqual':
            value = float(step.text) if value > 0 else 0.0
        elif step.tag == 'Not':
            value = float(not value)
        elif step.tag == 'Add':
            value = value - float(step.text)
        elif step.tag == 'Invert':
            value = -value
        else:
            raise AssertionError(step.tag)
    return value


def size(element):
    """(width, height, width policy, height policy) from a Size like '48f,48f'."""
    def part(text):
        match = re.fullmatch(r'(\d+)(me|min|max|f|e|i|p)?', text)
        return int(match.group(1)), match.group(2) or ''
    (w, wp), (h, hp) = (part(p) for p in element.findtext('Size').split(','))
    return w, h, wp, hp


class Model:
    """Visibility and button writes of a generated skin, as Mixxx evaluates them."""

    def __init__(self, root):
        self.root = root
        self.parent = {child: parent for parent in root.iter() for child in parent}

    def by_name(self, name):
        return [e for e in self.root.iter() if e.findtext('ObjectName') == name]

    def one(self, name):
        found = self.by_name(name)
        assert len(found) == 1, (name, len(found))
        return found[0]

    @staticmethod
    def state(screen=0, **values):
        state = {SCREEN: screen, '[MixPi],sample_load': 1 if screen in (3, 4) else 0,
                 '[Sidebar],sidebar_visible': 1 if screen == 1 else 0,
                 '[MixPi],sample_pad': 0, '[MixPi],loop_deck': 0,
                 '[Tab],library': 1 if screen in (1, 3, 4) else 0}
        state.update({key.replace('__', ','): value for key, value in values.items()})
        return state

    def visible(self, element, state):
        while element is not None:
            for c in element.findall('Connection'):
                if c.findtext('BindProperty') == 'visible':
                    if not transform(c, float(state.get(c.findtext('ConfigKey'), 0))) > 0:
                        return False
            trigger = element.get('trigger')
            if trigger and not state.get(trigger, 0):
                return False
            element = self.parent.get(element)
        return True

    @staticmethod
    def writes(button, phase='press', state=None):
        """Ordered (key, value) a button writes on press or release."""
        push = button.findtext('LeftClickIsPushButton') == 'true'
        connections = [c for c in button.findall('Connection') if c.find('BindProperty') is None
                       and c.findtext('ConnectValueFromWidget', 'true') == 'true']
        if push:
            emitted = 1.0 if phase == 'press' else 0.0
        else:
            states = int(button.findtext('NumberStates'))
            first = connections[0]
            emitted = float((int((state or {}).get(first.findtext('ConfigKey'), 0)) + 1) % states)
        result = []
        for c in connections:
            if c.findtext('EmitOnPressAndRelease') == 'true':
                phases = ('press', 'release')
            elif c.findtext('EmitOnDownPress') == 'false':
                phases = ('release',)
            elif c.findtext('EmitOnDownPress') == 'true' or not push:
                phases = ('press',)
            else:
                phases = ('press', 'release')
            if phase in phases:
                result.append((c.findtext('ConfigKey'), inverse(c, emitted)))
        return result

    def final(self, button, state=None):
        values = dict(self.writes(button, 'press', state))
        values.update(self.writes(button, 'release', state))
        return values


class PerformanceSkinTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.skin=Path(self.temp.name)/'Pioneered'
        self.skin.mkdir()
        (self.skin/'skin.xml').write_text('<skin><manifest><title>Pioneered</title>'
            '<description>original</description><attributes>'
            '<attribute config_key="[Master],num_samplers">16</attribute>'
            '</attributes></manifest></skin>')
        (self.skin/'style.qss').write_text('/* upstream */\n')
        (self.skin/'waveform.xml').write_text('<Template><Visual><ObjectName>Waveform</ObjectName>'
            '<Channel><Variable name="channel"/></Channel><BeatColor>#40ffffff</BeatColor>'
            '<Mark><Control>hotcue_1_position</Control></Mark></Visual></Template>')
        (self.skin/'deck.xml').write_text('<Template><Overview><ObjectName>DeckOverview</ObjectName>'
            '<Channel><Variable name="channel"/></Channel><MarkRange>'
            '<StartControl>loop_start_position</StartControl><EndControl>loop_end_position</EndControl>'
            '</MarkRange></Overview></Template>')
        (self.skin/'library.xml').write_text(TOUCH.patch_library(
            (ROOT/'tests/fixtures/pioneered-library.xml').read_text()))
        SKIN.build(self.skin)
        self.root=ET.parse(self.skin/'skin.xml').getroot()
        self.model=Model(self.root)

    def button_by_key(self, key, name=None):
        found = [b for b in self.root.iter('PushButton')
                 if b.findtext('Connection/ConfigKey') == key
                 and (name is None or b.findtext('ObjectName') == name)]
        self.assertEqual(len(found), 1, key)
        return found[0]

    def button_by_text(self, text):
        found = [b for b in self.root.iter('PushButton') if b.findtext('State/Text') == text]
        self.assertEqual(len(found), 1, text)
        return found[0]

    # ---------- R-1 shell: top bar and the screen control ----------

    def test_topbar_is_48_px_in_prototype_order_and_fits_800(self):
        top = self.model.one('MixpiTopbar')
        self.assertEqual(top.findtext('Size'), '0me,48f')
        items = list(top.find('Children'))
        names = [e.findtext('ObjectName') for e in items]
        self.assertEqual(names, ['MixpiTabPair', 'MixpiTabPair', 'MixpiTab', 'MixpiTabPair',
                                 'MixpiTopSpacer', 'MixpiUsbChip', 'MixpiGap', 'MixpiRecord',
                                 'MixpiGap', 'MixpiIconButton', 'MixpiGap', 'MixpiCpuBox'])
        widths = [size(e)[0] for e in items if e.findtext('ObjectName') != 'MixpiTopSpacer']
        self.assertEqual(widths, [84, 84, 72, 96, 150, 11, 72, 8, 48, 3, 56])
        self.assertLessEqual(sum(widths), 800)
        for e in items:
            if e.findtext('ObjectName') != 'MixpiTopSpacer':
                self.assertEqual(size(e)[1:4:2], (48, 'f'), e.findtext('ObjectName'))
        # Tap points of plan 5.3 (y 24): chip 527, REC 649, gear 717.
        x, centres = 800, {}
        for e in reversed(items):
            if e.findtext('ObjectName') == 'MixpiTopSpacer':
                break
            x -= size(e)[0]
            centres[e.findtext('ObjectName')] = x + size(e)[0] / 2
        self.assertEqual((centres['MixpiUsbChip'], centres['MixpiRecord'],
                          centres['MixpiIconButton']), (527, 649, 717))
        x, tabs = 0, []
        for e in items[:4]:
            tabs.append(x + size(e)[0] / 2)
            x += size(e)[0]
        self.assertEqual(tabs, [42, 126, 204, 288])

    def test_screen_is_a_skin_only_unsaved_control(self):
        attributes = {a.get('config_key'): a for a in self.root.findall('manifest/attributes/attribute')}
        for key in (SCREEN, '[MixPi],sample_pad', '[Sidebar],sidebar_visible'):
            self.assertEqual(attributes[key].text, '0')
            self.assertIsNone(attributes[key].get('persist'))

    def test_bottom_rows_show_only_without_a_full_screen_view(self):
        bottom = self.model.one('MixpiBottom')
        self.assertEqual([c.findtext('ObjectName') for c in bottom.find('Children')],
                         ['MixpiSummaries', 'MixpiTransport'])
        self.assertEqual(size(bottom)[1], 48 + 56)
        self.assertEqual(self.model.one('MixpiSummaries').findtext('Size'), '0me,48f')
        self.assertEqual(self.model.one('MixpiTransport').findtext('Size'), '0me,56f')
        for screen in range(6):
            self.assertEqual(self.model.visible(bottom, {SCREEN: screen}), screen == 0, screen)
        # Nothing under the overviews and transport carries its own screen binding.
        for e in bottom.iter():
            self.assertNotIn(SCREEN, [c.findtext('ConfigKey') for c in e.findall('Connection')
                                      if e is not bottom])

    def tabs(self):
        return [b for b in self.root.iter('PushButton') if b.findtext('ObjectName') == 'MixpiTab']

    def test_every_tab_writes_screen_zero_and_closes_every_view(self):
        tabs = self.tabs()
        self.assertEqual([b.findtext('State/Text') for b in tabs],
                         ['DECKS', 'DECKS', 'TRACKS', 'TRACKS', 'FX', 'SAMPLER', 'SAMPLER'])
        pages = {'DECKS': 'overview', 'TRACKS': 'library', 'FX': 'fx', 'SAMPLER': 'sampler'}
        for tab in tabs:
            self.assertEqual(tab.findtext('LeftClickIsPushButton'), 'true')
            writes = self.model.writes(tab)
            self.assertEqual(writes[0], (f"[Tab],{pages[tab.findtext('State/Text')]}", 1.0))
            self.assertEqual(dict(writes[1:]), {SCREEN: 0, '[MixPi],loop_deck': 0,
                                                '[MixPi],sample_load': 0, '[MixPi],sample_pad': 0,
                                                '[Sidebar],sidebar_visible': 0})
            self.assertEqual(self.model.writes(tab, 'release'), [])

    def test_active_tab_is_lit_and_sampler_stays_lit_in_sample_screens(self):
        def lit(text, state):
            shown = [b for b in self.tabs() if b.findtext('State/Text') == text
                     and self.model.visible(b, state)]
            self.assertEqual(len(shown), 1, (text, state))
            display = [c for c in shown[0].findall('Connection')
                       if c.find('BindProperty') is None and c.findtext('ConnectValueToWidget') == 'true']
            return bool(display) and transform(display[-1], float(state.get(display[-1].findtext('ConfigKey'), 0))) == 1
        tracks = Model.state(0, **{'[Tab]__library': 1})
        self.assertEqual([lit(t, tracks) for t in ('DECKS', 'TRACKS', 'FX', 'SAMPLER')],
                         [False, True, False, False])
        sources = Model.state(1)
        self.assertEqual([lit(t, sources) for t in ('TRACKS', 'SAMPLER')], [True, False])
        for screen in (3, 4):
            state = Model.state(screen)
            self.assertEqual([lit(t, state) for t in ('DECKS', 'TRACKS', 'SAMPLER')],
                             [False, False, True], screen)
        from_sample = Model.state(1, **{'[MixPi]__sample_load': 1})
        self.assertEqual([lit(t, from_sample) for t in ('TRACKS', 'SAMPLER')], [False, True])
        settings = Model.state(0, **{'[Tab]__overview': 1, '[MixPi]__loop_deck': 3})
        self.assertFalse(lit('DECKS', settings))

    def test_active_tab_style_is_filled_with_a_three_pixel_underline(self):
        style = (self.skin/'style.qss').read_text()
        rule = style.split('#MixpiTab[value="1"] {', 1)[1].split('}', 1)[0]
        self.assertIn('border-bottom: 3px solid #b5e15c;', rule)
        self.assertIn('background:', rule)

    def test_settings_highlights_only_settings_not_decks(self):
        pair = next(g for g in self.root.findall('.//WidgetGroup')
                    if g.findtext('ObjectName') == 'MixpiTabPair')
        self.assertEqual((pair.findtext('Layout'), pair.findtext('Size')), ('stacked', '84f,48f'))
        normal, twin = pair.findall('Children/PushButton')
        for b in (normal, twin):
            self.assertEqual(b.findtext('ObjectName'), 'MixpiTab')
            self.assertEqual(b.findtext('Size'), '84f,48f')
            self.assertEqual(b.findtext('State/Text'), 'DECKS')
            self.assertEqual(b.findtext('LeftClickIsPushButton'), 'true')
        self.assertEqual(self.model.writes(normal), self.model.writes(twin))
        self.assertEqual(self.model.writes(twin)[0][0], '[Tab],overview')
        # The twin never shows the tab state; the normal tab does.
        self.assertFalse(any(c.findtext('ConnectValueToWidget') == 'true' for c in twin.findall('Connection')))
        self.assertEqual(normal.findtext('Connection/ConnectValueToWidget'), 'true')
        for loop_deck in (0, 1, 2, 3):
            shown = [b for b in (normal, twin)
                     if self.model.visible(b, {'[MixPi],loop_deck': loop_deck})]
            self.assertEqual(shown, [twin] if loop_deck == 3 else [normal])

    def gear(self):
        return self.button_by_key('[MixPi],loop_deck', 'MixpiIconButton')

    def test_gear_keeps_settings_inside_decks_and_closes_full_screen_views(self):
        gear = self.gear()
        self.assertEqual(gear.findtext('Size'), '48f,48f')
        self.assertEqual(gear.findtext('Connection/Transform/IsEqual'), '3')
        self.assertEqual(gear.findtext('Connection/ConnectValueToWidget'), 'true')
        self.assertEqual(self.model.writes(gear), [
            ('[MixPi],loop_deck', 3), ('[Tab],overview', 1), ('[MixPi],sample_load', 0),
            (SCREEN, 0), ('[MixPi],sample_pad', 0), ('[Sidebar],sidebar_visible', 0)])
        guard = next(c for c in gear.findall('Connection') if c.findtext('BindProperty') == 'enabled')
        self.assertEqual(guard.findtext('ConfigKey'), '[MixPi],settings_available')
        self.assertEqual([s.findtext('Unpressed') for s in gear.findall('State')],
                         ['mixpi-icon-gear.svg'] * 2)

    def test_media_actions_are_native_gated_and_separate_from_sampler(self):
        buttons = self.root.findall('.//PushButton')
        action = self.button_by_key('[MixPi],media_load')
        gate = action.findall('Connection')[-1]
        self.assertEqual(gate.findtext('ConfigKey'), '[MixPi],media_available')
        self.assertEqual(gate.findtext('BindProperty'), 'enabled')
        self.assertFalse(any(button.findtext('Connection/ConfigKey') == '[MixPi],media_eject'
                             for button in buttons))
        self.assertTrue(any('[MixPi],sample_load' in [k.text for k in button.findall('Connection/ConfigKey')]
                            for button in buttons))

    def test_usb_chip_replaces_load_eject_and_opens_todays_dialog(self):
        chip = self.button_by_key('[MixPi],media_load')
        self.assertEqual((chip.findtext('ObjectName'), chip.findtext('Size')), ('MixpiUsbChip', '150f,48f'))
        self.assertEqual(self.model.writes(chip), [('[MixPi],media_load', 1)])
        self.assertEqual({s.findtext('Text').strip() for s in chip.findall('State')}, {'USB'})
        self.assertEqual({s.findtext('Unpressed') for s in chip.findall('State')}, {'mixpi-icon-usb.svg'})
        texts = [t.text for t in self.root.iter('Text')]
        self.assertNotIn('LOAD / EJECT', texts)

    PUSH_GUARD_EXEMPT = ()

    def small_buttons(self, root):
        small = []
        for b in root.iter('PushButton'):
            if not any(c.find('BindProperty') is None and c.findtext('ConnectValueFromWidget', 'true') == 'true'
                       for c in b.findall('Connection')):
                continue  # display-only chip
            w, h, wp, hp = size(b)
            if h < 48 or (wp == 'f' and w < 48) or (wp != 'f' and w != 0 and w < 48):
                small.append((b.findtext('ObjectName'), b.findtext('Size')))
        return small

    def test_every_generated_push_button_is_at_least_48_by_48(self):
        self.assertEqual(self.small_buttons(self.root), [])

    def test_touch_guard_catches_a_small_button(self):
        self.root.find('.//Children').append(SKIN.button('X', '[Channel1],play', size='40f,48f'))
        self.assertEqual(self.small_buttons(self.root), [('MixpiButton', '40f,48f')])

    def page(self, name):
        return self.model.one(name)

    def test_page_heights_fill_480(self):
        # Top 48 + bottom 104 on screen 0; the page fills the rest (328).
        sampler = self.page('MixpiSampler')
        heights = [size(c)[1] for c in sampler.find('Children')]
        self.assertEqual(heights[:2], [48, 2 * 104])
        self.assertEqual(sampler.find('Children')[2].findtext('Size'), '0me,0i')
        self.assertEqual(48 + sum(heights[:2]) + SKIN.SAMPLER_INFO + 48 + 56, 480)
        # At 800x444 (desktop bar shown) every page's minimum fits 444 - 48 - 104.
        self.assertLessEqual(sum(heights[:2]), 444 - 48 - 104)
        info = sampler.find('Children')[2]
        for deck in info.findall('Children/WidgetGroup'):
            self.assertEqual(sum(size(c)[1] for c in deck.find('Children')), SKIN.SAMPLER_INFO)

    def test_two_state_buttons_without_push_mode_target_real_toggles(self):
        self.assertEqual(self.toggle_offenders(self.root), [])

    # ---------- the browse page: Tracks, Sources, Load sample, Choose pad ----------

    VIEWS = ['SidebarButton', 'MixpiTracksCrumb', 'MixpiSourcesHead', 'MixpiLoadHead', 'SearchBox',
             'LibraryActionsButton', 'LibraryBackButton', 'LibrarySourcesButton', 'MixpiSourcesBody',
             'MixpiSampleSources', 'MixpiLibraryMain', 'MixpiTrackTitles', 'MixpiSampleFooter',
             'MixpiChooseScrim']

    def shown(self, state):
        return [name for name in self.VIEWS if self.model.visible(self.model.one(name), state)]

    def test_tracks_toolbar_is_menu_crumb_search_pen(self):
        self.assertEqual(self.shown(Model.state(0, **{'[Tab]__library': 1})),
                         ['SidebarButton', 'MixpiTracksCrumb', 'SearchBox', 'LibraryActionsButton',
                          'MixpiLibraryMain', 'MixpiTrackTitles'])
        header = self.model.one('MixpiBrowseHeader')
        self.assertEqual(header.findtext('Size'), '0me,48f')
        self.assertEqual(self.model.one('MixpiTracksCrumb').findtext('Size'), '220f,48f')
        order = [e.findtext('ObjectName') for e in header.iter() if e.findtext('ObjectName') in self.VIEWS]
        self.assertLess(order.index('SidebarButton'), order.index('MixpiTracksCrumb'))
        self.assertLess(order.index('MixpiTracksCrumb'), order.index('SearchBox'))
        self.assertLess(order.index('SearchBox'), order.index('LibraryActionsButton'))

    def test_sources_is_a_full_screen_with_the_sidebar_under_its_header(self):
        self.assertEqual(self.shown(Model.state(1)),
                         ['SidebarButton', 'MixpiSourcesHead', 'LibraryBackButton',
                          'LibrarySourcesButton', 'MixpiSourcesBody'])
        body = self.model.one('MixpiSourcesBody')
        sidebar = self.model.one('SidebarWrapper')
        self.assertIn(sidebar, list(body.iter()))
        self.assertEqual(sidebar.findtext('Size'), '0me,0me')
        self.assertNotIn('290f', ET.tostring(self.model.one('MixpiBrowse'), encoding='unicode'))
        self.assertEqual([c.findtext('ObjectName') for c in sidebar.find('Children')], ['LibrarySidebar'])
        self.assertEqual(sidebar.findtext('Connection/ConfigKey'), '[Sidebar],sidebar_visible')
        wrapper = self.model.one('LibraryWrapper')
        self.assertEqual([c.findtext('ObjectName') for c in wrapper.find('Children')][:2],
                         ['MixpiBrowseHeader', 'MixpiSourcesBody'])
        # The library table is not shown under Sources.
        self.assertFalse(self.model.visible(self.model.one('Library'), Model.state(1)))

    def test_edit_list_and_back_keep_their_native_controls(self):
        library = ET.parse(self.skin/'library.xml').getroot()
        original = next(button for button in library.findall('.//PushButton')
                        if button.findtext('ObjectName') == 'LibrarySourcesButton')
        edit = self.model.one('LibrarySourcesButton')
        self.assertEqual(edit.findtext('Size'), '128f,48f')
        self.assertEqual(edit.findtext('State/Text'), 'EDIT LIST')
        self.assertEqual([[(item.tag, item.text) for item in c] for c in edit.findall('Connection')
                          if c.find('BindProperty') is None],
                         [[(item.tag, item.text) for item in c] for c in original.findall('Connection')])
        self.assertEqual(self.model.writes(edit), [('[Library],show_sidebar_sources_menu', 1)])
        back = self.model.one('LibraryBackButton')
        self.assertEqual(back.findtext('Size'), '96f,48f')
        self.assertEqual(back.findtext('Connection/ConfigKey'), '[Library],sidebar_back')
        self.assertEqual(back.findall('Connection')[1].findtext('ConfigKey'), '[Library],sidebar_can_go_back')

    def test_menu_opens_sources_and_its_x_closes_it(self):
        menu = self.model.one('SidebarButton')
        self.assertIsNone(menu.find('LeftClickIsPushButton'))
        self.assertEqual(menu.findtext('Connection/ConfigKey'), '[Sidebar],sidebar_visible')
        closed, opened = Model.state(0, **{'[Tab]__library': 1}), Model.state(1)
        self.assertEqual(self.model.writes(menu, state=closed),
                         [('[Sidebar],sidebar_visible', 1), (SCREEN, 1)])
        self.assertEqual(self.model.writes(menu, state=opened),
                         [('[Sidebar],sidebar_visible', 0), (SCREEN, 0)])
        # The ✕ is the same button in the same place (x 0-48, the header's first slot).
        for state in (closed, opened):
            self.assertTrue(self.model.visible(menu, state))
        slot = self.model.one('MixpiHeaderSlot')
        self.assertEqual(list(self.model.one('MixpiBrowseHeader').find('Children'))[0], slot)

    def test_load_sample_is_a_second_layout_around_the_one_library(self):
        for screen in (3, 4):
            self.assertEqual(self.shown(Model.state(screen))[:6],
                             ['MixpiLoadHead', 'SearchBox', 'MixpiSampleSources', 'MixpiLibraryMain',
                              'MixpiSampleFooter'] + (['MixpiChooseScrim'] if screen == 4 else []))
        self.assertEqual(len(self.root.findall('.//Library')), 1)
        self.assertEqual(len(self.root.findall('.//SearchBox')), 1)
        self.assertEqual(self.model.by_name('MixpiSamplerDestinations'), [])
        self.assertFalse(any('LoadSelectedTrackAndPlay' in (k.text or '') for k in self.root.iter('ConfigKey')))
        # Header 48, sources 56, list y 152-416, footer 64 (plan R-8).
        self.assertEqual(size(self.model.one('MixpiSampleSources'))[1], 56)
        self.assertEqual(size(self.model.one('MixpiSampleFooter'))[1], 64)
        self.assertEqual(48 + 48 + 56, 152)
        self.assertEqual(480 - 64, 416)

    def test_load_sample_close_returns_to_the_sampler(self):
        close = [b for b in self.root.iter('PushButton')
                 if b.findtext('Connection/ConfigKey') == '[Tab],sampler'
                 and b.findtext('ObjectName') == 'MixpiIconButton']
        self.assertEqual(len(close), 1)
        self.assertTrue(self.model.visible(close[0], Model.state(3)))
        self.assertFalse(self.model.visible(close[0], Model.state(1)))
        self.assertEqual(self.model.final(close[0])[SCREEN], 0)
        self.assertEqual(self.model.final(close[0])['[Tab],sampler'], 1)
        self.assertEqual(self.model.final(close[0])['[MixPi],sample_load'], 0)

    def test_sources_opened_from_load_sample_returns_there(self):
        open_sources = self.button_by_text('SOURCES…')
        self.assertEqual(self.model.final(open_sources), {'[Sidebar],sidebar_visible': 1, SCREEN: 1})
        state = Model.state(1, **{'[MixPi]__sample_load': 1})
        menu = self.model.one('SidebarButton')
        self.assertFalse(self.model.visible(menu, state))
        close = next(b for b in self.root.iter('PushButton')
                     if b.findtext('Connection/ConfigKey') == '[Sidebar],sidebar_visible'
                     and self.model.visible(b, state) and b.findtext('ObjectName') == 'MixpiIconButton')
        self.assertEqual(self.model.final(close), {'[Sidebar],sidebar_visible': 0, SCREEN: 3})
        self.assertFalse(self.model.visible(close, Model.state(1)))

    def test_sample_source_buttons_wait_for_the_native_browser(self):
        for text, value in (('SAMPLES', 1), ('THIS PI', 2), ('RECORDINGS', 4)):
            b = self.button_by_text(text)
            self.assertEqual(self.model.final(b), {'[MixPi],sample_source': value})
            self.assertFalse(self.model.visible(b, Model.state(3)))
            self.assertTrue(self.model.visible(b, Model.state(3, **{'[MixPi]__sample_source_available': 1})))

    def load_targets(self):
        return list(self.model.one('MixpiLoadTarget').find('Children'))

    def test_load_to_pad_footer_shows_one_button_per_sample_pad(self):
        targets = self.load_targets()
        self.assertEqual(len(targets), 9)
        for pad in range(9):
            state = Model.state(3, **{'[MixPi]__sample_pad': pad})
            shown = [t for t in targets if self.model.visible(t, state)]
            self.assertEqual(len(shown), 1)
            self.assertEqual(shown[0].findtext('Size'), '250f,56f')
            if pad == 0:
                self.assertEqual(shown[0].findtext('State/Text'), 'LOAD TO PAD…')
                self.assertEqual(self.model.final(shown[0]), {SCREEN: 4})
            else:
                self.assertEqual(shown[0].findtext('State/Text'), f'LOAD TO PAD {pad}')
                self.assert_loads_then_closes(shown[0], pad)

    def assert_loads_then_closes(self, button, sampler):
        key = f'[Sampler{sampler}]'
        self.assertEqual(self.model.writes(button), [(f'{key},LoadSelectedTrack', 1)])
        release = self.model.writes(button, 'release')
        self.assertEqual(release[0], (f'{key},LoadSelectedTrack', 0))
        self.assertEqual(dict(release[1:]), {'[Tab],sampler': 1, SCREEN: 0, '[MixPi],sample_load': 0,
                                             '[MixPi],sample_pad': 0, '[MixPi],loop_deck': 0,
                                             '[Sidebar],sidebar_visible': 0})
        guard = next(c for c in button.findall('Connection') if c.findtext('BindProperty') == 'enabled')
        self.assertEqual(guard.findtext('ConfigKey'), f'{key},play')
        self.assertEqual(transform(guard, 1.0), 0)

    def tiles(self):
        return [b for b in self.root.iter('PushButton') if b.findtext('ObjectName') == 'MixpiChooseTile']

    def test_choose_pad_has_eight_tiles_in_pad_order(self):
        tiles = self.tiles()
        self.assertEqual(len(tiles), 8)
        for sampler, tile in enumerate(tiles, 1):
            self.assertEqual(tile.findtext('Size'), '165f,96f')
            self.assert_loads_then_closes(tile, sampler)
            cell = self.model.parent[self.model.parent[tile]]
            names = [t.text for t in cell.iter('Text')]
            self.assertIn(f"{'A' if sampler <= 4 else 'B'}{(sampler - 1) % 4 + 1}", names)
            self.assertTrue(any(e.findtext('Group') == f'[Sampler{sampler}]' for e in cell.iter('TrackProperty')))
        cancel = self.button_by_text('CANCEL')
        self.assertEqual(self.model.final(cancel), {SCREEN: 3})
        scrim = self.model.one('MixpiChooseScrim')
        # A hidden sheet must not raise the page minimum (stacked layouts count hidden pages).
        self.assertEqual(scrim.findtext('Size'), '0me,0i')
        self.assertEqual(self.model.one('MixpiBrowse').findtext('Layout'), 'stacked')

    def test_choose_pad_geometry_matches_the_plan_hit_map(self):
        sheet = self.model.one('MixpiChooseSheet')
        self.assertEqual(sheet.findtext('Size'), '720f,340f')
        top = 48 + 4
        rows, y = {}, top
        for child in sheet.find('Children'):
            rows[child.findtext('ObjectName') + str(y)] = y
            if child.findtext('ObjectName') == 'MixpiChooseTitleRow':
                cancel_y = y + 24
            if child.findtext('ObjectName') == 'MixpiChooseRow':
                rows.setdefault('tiles', []).append(y + 48)
            y += size(child)[1]
        self.assertEqual(cancel_y, 92)
        self.assertEqual(rows['tiles'], [176, 280])
        title_row = next(c for c in sheet.find('Children') if c.findtext('ObjectName') == 'MixpiChooseTitleRow')
        widths = [size(c)[0] for c in title_row.find('Children')]
        self.assertEqual(40 + 720 - widths[-1] - widths[-2] / 2, 682)
        row = next(c for c in sheet.find('Children') if c.findtext('ObjectName') == 'MixpiChooseRow')
        x, centres = 40, []
        for cell in row.find('Children'):
            w = size(cell)[0]
            if cell.findtext('ObjectName') == 'MixpiChooseCell':
                centres.append(x + w / 2)
            x += w
        self.assertEqual(x, 760)
        for got, plan in zip(centres, (144, 315, 485, 656)):
            self.assertLessEqual(abs(got - plan), 4)

    # ---------- R-7 sampler ----------

    def pads(self):
        return [g for g in self.root.iter('WidgetGroup') if g.findtext('ObjectName') in ('MixpiPadA', 'MixpiPadB')]

    def test_eight_pads_match_the_starlight(self):
        attributes = {a.get('config_key'): a.text for a in self.root.findall('manifest/attributes/attribute')}
        self.assertEqual(attributes['[Master],num_samplers'], '8')
        self.assertEqual(attributes['[MixPi],sample_load'], '0')
        pads = self.pads()
        self.assertEqual(len(pads), 8)
        rows = [g for g in self.root.iter('WidgetGroup') if g.findtext('ObjectName') == 'MixpiPadRow']
        self.assertEqual([[p.findtext('ObjectName') for p in r.find('Children')] for r in rows],
                         [['MixpiPadA'] * 4, ['MixpiPadB'] * 4])
        for sampler, pad in enumerate(pads, 1):
            key = f'[Sampler{sampler}]'
            deck = 'A' if sampler <= 4 else 'B'
            self.assertEqual(pad.findtext('Size'), '200f,104f')
            badges = [l for l in pad.iter('Label') if l.findtext('ObjectName') == f'MixpiPadBadge{deck}']
            self.assertEqual({l.findtext('Text') for l in badges}, {str(sampler)})
            self.assertIn(f'{deck}{(sampler - 1) % 4 + 1}', [t.text for t in pad.iter('Text')])
            trigger = next(b for b in pad.iter('PushButton') if b.findtext('ObjectName') == 'MixpiPadTap')
            self.assertEqual(trigger.findtext('Size'), '200f,56f')
            self.assertEqual(self.model.writes(trigger), [(f'{key},cue_gotoandplay', 1)])
            self.assertEqual(self.model.writes(trigger, 'release'), [(f'{key},cue_gotoandplay', 0)])
            display = [c for c in trigger.findall('Connection') if c.findtext('ConnectValueFromWidget') == 'false']
            self.assertEqual(display[-1].findtext('ConfigKey'), f'{key},play')
            strip = next(g for g in pad.iter('WidgetGroup') if g.findtext('ObjectName') == 'MixpiPadStrip')
            self.assertEqual(strip.findtext('Size'), '200f,48f')
            stop, clear = strip.findall('Children/PushButton')
            self.assertEqual((stop.findtext('Size'), clear.findtext('Size')), ('100f,48f', '100f,48f'))
            self.assertEqual(self.model.writes(stop), [(f'{key},stop', 1)])
            self.assertEqual(self.model.writes(clear), [(f'{key},eject', 1)])
            gate = next(c for c in clear.findall('Connection') if c.findtext('BindProperty') == 'enabled')
            self.assertEqual(gate.findtext('ConfigKey'), f'{key},play')
            self.assertIsNotNone(gate.find('Transform/Not'))
            # No progress fill and no ⋯ menu (plan 4.2).
            self.assertFalse(any('⋯' in (t.text or '') for t in pad.iter('Text')))

    def test_loaded_and_empty_pads_follow_track_loaded(self):
        for sampler, pad in enumerate(self.pads(), 1):
            key = f'[Sampler{sampler}]'
            loaded, empty = pad.find('Children')
            open_load = next(b for b in empty.iter('PushButton'))
            for value in (0, 1):
                state = {f'{key},track_loaded': value, '[Tab],sampler': 1}
                self.assertEqual(self.model.visible(loaded, state), bool(value))
                self.assertEqual(self.model.visible(open_load, state), not value)
            self.assertEqual(open_load.findtext('Size'), '200f,104f')
            final = self.model.final(open_load)
            self.assertEqual((final[SCREEN], final['[MixPi],sample_pad'], final['[MixPi],sample_load'],
                              final['[Tab],library']), (3, sampler, 1, 1))
            self.assertIn('+  Empty · tap to load', [t.text for t in empty.iter('Text')])

    def test_load_sample_header_button_opens_the_chooser(self):
        load = self.button_by_text('+  LOAD SAMPLE')
        self.assertEqual(load.findtext('Size'), '190f,48f')
        final = self.model.final(load)
        self.assertEqual((final['[Tab],library'], final[SCREEN], final['[MixPi],sample_load'],
                          final['[MixPi],sample_pad']), (1, 3, 1, 0))
        header = self.model.one('MixpiSamplerHeader')
        saved = next(l for l in header.iter('Label') if l.findtext('Text') == 'Bank saved')
        self.assertEqual(saved.findtext('Connection/ConfigKey'), '[MixPi],saved')
        self.assertIn('Starlight SAMPLER mode: deck A pads 1-4 · deck B pads 5-8',
                      [t.text for t in header.iter('Text')])

    # ---------- R-11 icons ----------

    def test_menu_and_pen_are_48_px_icon_buttons_with_skin_svgs(self):
        menu, pen = self.model.one('SidebarButton'), self.model.one('LibraryActionsButton')
        expected = {menu: ['mixpi-icon-menu.svg', 'mixpi-icon-close.svg'],
                    pen: ['mixpi-icon-pen.svg', 'mixpi-icon-pen.svg']}
        for button, icons in expected.items():
            self.assertEqual(button.findtext('Size'), '48f,48f')
            states = button.findall('State')
            self.assertEqual(button.findtext('NumberStates'), str(len(states)))
            self.assertEqual([s.findtext('Unpressed') for s in states], icons)
            self.assertEqual([s.findtext('Pressed') for s in states], icons)
            self.assertEqual([s.findtext('Text') for s in states], [None] * len(states))
        self.assertEqual(pen.findtext('Connection/ConfigKey'), '[Library],show_track_menu')
        self.assertEqual(pen.findtext('Connection/EmitOnDownPress'), 'true')
        self.assertEqual(menu.findtext('Connection/ConfigKey'), '[Sidebar],sidebar_visible')
        used = {e.text for e in self.root.iter() if e.tag in ('Pressed', 'Unpressed')}
        for name in used:
            svg = ET.parse(self.skin/name).getroot()
            self.assertEqual(svg.tag, '{http://www.w3.org/2000/svg}svg')
        for name in ('mixpi-icon-menu.svg', 'mixpi-icon-close.svg', 'mixpi-icon-pen.svg', 'mixpi-icon-gear.svg'):
            svg = ET.parse(self.skin/name).getroot()
            self.assertEqual((svg.get('width'), svg.get('height')), ('48', '48'))

    # ---------- carried guards ----------

    def test_repeat_keeps_original_and_pinned_waveform_definitions(self):
        first=(self.skin/'skin.xml').read_bytes()
        SKIN.build(self.skin)
        self.assertEqual(first,(self.skin/'skin.xml').read_bytes())
        self.assertEqual(self.root.findtext('MinimumSize'),'800,444')
        self.assertEqual(self.root.findall('.//Variable'),[])
        self.assertEqual(len(self.root.findall('.//Library')),1)
        self.assertEqual(len(self.root.findall('.//LibrarySidebar')),1)
        self.assertEqual(len(self.root.findall('.//Visual')),4)
        self.assertEqual(len(self.root.findall('.//Overview')),2)
        self.assertEqual(self.root.findall('.//Visual')[0].findtext('BeatColor'),'#40ffffff')
        self.assertIn('original',(self.skin/'.mixpi-performance-original/skin.xml').read_text())
        self.assertEqual((self.skin/'style.qss').read_text().count(SKIN.BEGIN),1)

    def test_native_library_style_scope_covers_browse_only(self):
        wrappers = [group for group in self.root.findall('.//WidgetGroup')
                    if group.findtext('ObjectName') == 'LibraryWrapper']
        self.assertEqual(len(wrappers), 1)
        browse = next(group for group in self.root.findall('.//WidgetGroup')
                      if group.findtext('ObjectName') == 'MixpiBrowse')
        self.assertEqual(browse.get('trigger'), '[Tab],library')
        self.assertIn(wrappers[0], list(browse.iter()))
        for tag in ('Library', 'LibrarySidebar', 'SearchBox'):
            self.assertEqual(len(wrappers[0].findall('.//' + tag)), 1)
        self.assertEqual(wrappers[0].findall('.//Visual'), [])
        self.assertEqual(wrappers[0].findall('.//Overview'), [])
        keys = [key.text for key in wrappers[0].findall('.//ConfigKey')]
        self.assertNotIn('[Channel1],play', keys)
        self.assertNotIn('[Channel2],play', keys)

    def test_decks_label_and_quick_controls_are_tab_scoped(self):
        rows = [group for group in self.root.findall('.//WidgetGroup')
                if group.findtext('ObjectName') == 'MixpiDeckButtons']
        self.assertEqual(len(rows), 2)
        for row in rows:
            buttons = row.findall('Children/PushButton')
            self.assertEqual([button.findtext('State/Text') for button in buttons[:4]],
                             ['KEY', 'Q', 'SYNC', 'LOOP'])
            for button in buttons[:4]:
                guard = next(connection for connection in button.findall('Connection')
                             if connection.findtext('BindProperty') == 'visible')
                self.assertEqual(guard.findtext('ConfigKey'), '[Tab],overview')
            self.assertEqual([button.findtext('State/Text') for button in buttons[4:]],
                             ['LOAD', 'CUE', '▶'])
            cue = buttons[5]
            self.assertFalse(any(connection.findtext('BindProperty') == 'visible'
                                 for connection in cue.findall('Connection')))

    def test_six_pixel_corners_only_override_owned_buttons(self):
        style = (self.skin/'style.qss').read_text()
        override = style.split('/* MixPi native navigation */', 1)[1]
        self.assertIn('border-radius: 6px;', override)
        for selector in ('#MixpiButton', '#MixpiPlay', '#MixpiRecord', '#MixpiUsbChip',
                         '#LibraryWrapper #LibrarySourcesButton', '#LibraryWrapper #LibraryBackButton'):
            self.assertIn(selector, override)
        self.assertNotIn('\nPushButton {', style)
        self.assertNotIn('\nQWidget {', style)
        self.assertNotIn('\nWPushButton {', style)

    def test_owned_styles_use_image_fonts_and_no_text_under_13px(self):
        style = (FILES/'mixpi-performance.qss').read_text()
        for value in re.findall(r'font-size:\s*(\d+)px', style):
            self.assertGreaterEqual(int(value), 13)
        families = set()
        for value in re.findall(r'font-family:\s*([^;]+);', style):
            families.update(name.strip().strip('"') for name in value.split(','))
        self.assertLessEqual(families, {'Ubuntu', 'Ubuntu Condensed', 'Ubuntu Mono', 'Open Sans'})
        selectors = ' '.join(part.rsplit('}', 1)[-1] for part in
                             re.sub(r'/\*.*?\*/', '', style, flags=re.S).split('{')[:-1])
        for selector in re.findall(r'(#[A-Za-z]+)', selectors):
            self.assertTrue(selector.startswith(('#Mixpi', '#Library')), selector)

    def test_recording_four_states_preserve_independent_momentary_command(self):
        record = next(button for button in self.root.findall('.//PushButton')
                      if button.findtext('Connection/ConfigKey') ==
                      '[Recording],toggle_recording')
        self.assertEqual(record.findtext('ObjectName'), 'MixpiRecord')
        self.assertEqual(record.findtext('Size'), '72f,48f')
        self.assertEqual(record.findtext('NumberStates'), '4')
        self.assertEqual(record.findtext('LeftClickIsPushButton'), 'true')
        self.assertEqual([(state.findtext('Number'), state.findtext('Text'))
                          for state in record.findall('State')],
                         [('0', '● REC'), ('1', 'WAIT'),
                          ('2', '■ STOP'), ('3', '■ STOP')])
        command, display = record.findall('Connection')
        self.assertEqual(command.findtext('ConnectValueFromWidget'), 'true')
        self.assertEqual(command.findtext('ConnectValueToWidget'), 'false')
        self.assertEqual(command.findtext('EmitOnPressAndRelease'), 'true')
        self.assertEqual(display.findtext('ConfigKey'), '[Recording],status')
        self.assertEqual(display.findtext('ConnectValueFromWidget'), 'false')
        self.assertEqual(display.findtext('ConnectValueToWidget'), 'true')
        style = (self.skin/'style.qss').read_text()
        for state in (1, 2, 3):
            self.assertIn(f'#MixpiRecord[value="{state}"]', style)
        for button in self.root.findall('.//PushButton'):
            if button.findtext('ObjectName') in ('MixpiButton', 'MixpiPlay', 'MixpiTab'):
                self.assertEqual(button.findtext('NumberStates'), '2')

    def test_effect_popup_style_is_scoped_and_has_selected_contrast(self):
        style = (self.skin/'style.qss').read_text()
        self.assertIn('#MixpiEffectSelector QAbstractItemView {', style)
        popup = style.split('#MixpiEffectSelector QAbstractItemView {', 1)[1].split('}', 1)[0]
        for declaration in ('color: #f5f6fa', 'background: #20334a',
                            'selection-color: #101318',
                            'selection-background-color: #b5e15c'):
            self.assertIn(declaration, popup)
        self.assertNotIn('\nQWidget {', style)

    def test_fx_mix_box_and_ordinary_selectors(self):
        fx = SKIN.fx()
        self.assertNotIn('BEAT FX', [text.text for text in fx.findall('.//Text')])
        mix = next(group for group in fx.findall('.//WidgetGroup')
                   if group.findtext('ObjectName') == 'MixpiFxMix')
        self.assertEqual(mix.findtext('Children/SliderComposed/Connection/ConfigKey'),
                         '[EffectRack1_EffectUnit1],mix')
        self.assertEqual(len(fx.findall('.//EffectSelector')), 3)

    def test_settings_effective_columns_and_advanced(self):
        panel = SKIN.settings()
        basic = next(group for group in panel.findall('.//WidgetGroup')
                     if group.findtext('ObjectName') == 'MixpiSettingsBasic')
        self.assertEqual(basic.findtext('Layout'), 'horizontal')
        self.assertEqual([child.findtext('ObjectName') for child in basic.find('Children')],
                         ['MixpiPlaybackSettings', 'MixpiInterfaceSettings'])
        self.assertNotIn('[MixPi],waveform_fps', [key.text for key in basic.findall('.//ConfigKey')])
        combo = basic.find('.//ComboBox')
        self.assertEqual([state.findtext('Text') for state in combo.findall('State')],
                         ['Custom', '4%', '6%', '8%', '10%', '16%', '24%', '50%', '90%'])
        self.assertIn('[MixPi],desktop_bar', [key.text for key in basic.findall('.//ConfigKey')])
        advanced = next(group for group in panel.findall('.//WidgetGroup')
                        if group.findtext('ObjectName') == 'MixpiSettingsAdvanced')
        buttons = {b.findtext('State/Text'): b for b in panel.findall('.//PushButton')}
        # settings_advanced is a plain control: a two-state toggle sends 1 on
        # every press, so both buttons must be explicit set-value push buttons.
        for text, write in (('Advanced…', 'IsEqual'), ('Back', 'Not')):
            b = buttons[text]
            self.assertEqual(b.findtext('LeftClickIsPushButton'), 'true')
            command = b.find('Connection')
            self.assertEqual(command.findtext('ConfigKey'), '[MixPi],settings_advanced')
            self.assertEqual(command.findtext('EmitOnDownPress'), 'true')
            self.assertEqual(command.findtext('ConnectValueToWidget'), 'false')
            self.assertIsNotNone(command.find('Transform/' + write))
        self.assertEqual(buttons['Advanced…'].findtext('Connection/Transform/IsEqual'), '1')
        self.assertIn(buttons['Advanced…'], list(basic.iter()))
        self.assertIn(buttons['Back'], list(advanced.iter()))

    def test_advanced_back_and_preferences_share_one_touch_row(self):
        advanced = next(group for group in SKIN.settings().findall('.//WidgetGroup')
                        if group.findtext('ObjectName') == 'MixpiSettingsAdvanced')
        row = next(group for group in advanced.findall('Children/WidgetGroup')
                   if any(b.findtext('State/Text') == 'Back' for b in group.findall('Children/PushButton')))
        self.assertEqual(row.findtext('Layout'), 'horizontal')
        self.assertEqual(row.findtext('Size'), '0me,48f')
        back, preferences = row.findall('Children/PushButton')
        self.assertEqual(back.findtext('State/Text'), 'Back')
        self.assertEqual(preferences.findtext('State/Text'), 'Mixxx preferences…')
        self.assertEqual(preferences.findtext('LeftClickIsPushButton'), 'true')
        self.assertEqual(preferences.findtext('Size'), '0me,48f')
        command, = preferences.findall('Connection')
        self.assertEqual(command.findtext('ConfigKey'), '[MixPi],show_preferences')
        self.assertEqual(command.findtext('EmitOnDownPress'), 'true')
        self.assertEqual(command.findtext('ConnectValueFromWidget'), 'true')
        self.assertEqual(command.findtext('ConnectValueToWidget'), 'false')
        self.assertIsNone(command.find('Transform'))
        self.assertIsNone(command.find('EmitOnPressAndRelease'))

    # Controls that Mixxx itself creates as toggling ControlPushButtons. A
    # two-state button on any other control sends 1 on every press (B1).
    REAL_TOGGLES = ('keylock', 'quantize', 'sync_enabled', 'play', 'headSplit', 'enabled')

    def toggle_offenders(self, root):
        offenders = []
        for b in root.findall('.//PushButton'):
            if not b.findtext('ObjectName', '').startswith('Mixpi'):
                continue  # copied unchanged from the patched Pioneered library.xml
            if b.findtext('NumberStates') != '2' or b.findtext('LeftClickIsPushButton') == 'true':
                continue
            writes = [c.findtext('ConfigKey') for c in b.findall('Connection')
                      if c.findtext('ConnectValueFromWidget') == 'true']
            if len(writes) != 1 or writes[0].split(',', 1)[1] not in self.REAL_TOGGLES:
                offenders.append((b.findtext('State/Text'), writes))
        return offenders

    def test_guard_catches_a_toggle_on_a_plain_control(self):
        self.root.find('.//Children').append(SKIN.button('Back', '[MixPi],settings_advanced'))
        self.assertEqual(self.toggle_offenders(self.root),
                         [('Back', ['[MixPi],settings_advanced'])])

    def test_loop_intervals_retrigger_on_press_and_release(self):
        buttons=self.root.findall('.//PushButton')
        for ch in (1,2):
            for _,size_ in SKIN.LOOPS:
                key=f'[Channel{ch}],beatloop_{size_}_activate'
                b=next(b for b in buttons if b.findtext('Connection/ConfigKey')==key)
                self.assertEqual(b.findtext('Connection/EmitOnPressAndRelease'),'true')
                self.assertEqual(b.findtext('LeftClickIsPushButton'),'true')
                self.assertEqual(b.findall('Connection')[1].findtext('ConfigKey'),
                                 f'[Channel{ch}],beatloop_{size_}_enabled')
            exitb=next(b for b in buttons if b.findtext('Connection/ConfigKey')==f'[Channel{ch}],loop_exit')
            self.assertEqual(exitb.findtext('Connection/EmitOnPressAndRelease'),'true')
            reloop=next(b for b in buttons if b.findtext('Connection/ConfigKey')==f'[Channel{ch}],reloop_toggle')
            gate=reloop.findall('Connection')[-1]
            self.assertEqual(gate.findtext('BindProperty'),'enabled')
            self.assertIsNotNone(gate.find('Transform/Not'))

    def test_carryover_half_double_close_preserve_commands(self):
        for channel in (1, 2):
            panel = SKIN.loops(channel)
            commands = {button.findtext('Connection/ConfigKey'): button
                        for button in panel.findall('.//PushButton')}
            for suffix in ('loop_halve', 'loop_double', 'loop_exit', 'reloop_toggle'):
                command = commands[f'[Channel{channel}],{suffix}']
                self.assertEqual(command.findtext('Connection/EmitOnPressAndRelease'), 'true')
                self.assertEqual(command.findtext('LeftClickIsPushButton'), 'true')
            close = commands['[MixPi],loop_deck']
            self.assertIsNotNone(close.find('Connection/Transform/Not'))
            self.assertEqual(close.findtext('Connection/ConnectValueToWidget'), 'false')
        self.assertEqual(len(self.root.findall('.//Overview')), 2)

    def test_settings_expand_instead_of_retaining_deck_details(self):
        perform = next(group for group in self.root.findall('.//WidgetGroup')
                       if group.findtext('ObjectName') == 'MixpiPerform')
        details = perform.find('Children')[-1]
        gate = details.find('Connection')
        self.assertEqual(gate.findtext('ConfigKey'), '[MixPi],loop_deck')
        self.assertEqual(gate.findtext('Transform/IsEqual'), '3')
        self.assertIsNotNone(gate.find('Transform/Not'))
        fx = next(group for group in self.root.findall('.//WidgetGroup')
                  if group.findtext('ObjectName') == 'MixpiFxPage')
        self.assertEqual(len(fx.find('Children')), 1)

    def test_paired_keys_are_display_only_opt_in(self):
        for key in self.root.findall('.//Key'):
            self.assertEqual(key.findtext('PairedNotation'), 'true')
            self.assertEqual(key.findtext('Connection/ConnectValueFromWidget'), 'false')
        patch = (FILES / 'mixxx-performance-settings.patch').read_text()
        self.assertIn('context.selectBool(node, "PairedNotation", false)', patch)
        self.assertIn('KeyUtils::KeyNotation::LancelotAndTraditional', patch)

    def test_fx_route_disables_others_before_enabling_selected(self):
        buttons=[b for b in self.root.findall('.//PushButton')
                 if b.findtext('State/Text') in ('DECK 1','DECK 2','MASTER')]
        self.assertEqual(len(buttons),3)
        for b in buttons:
            writes=[c for c in b.findall('Connection') if c.findtext('ConnectValueFromWidget')=='true']
            self.assertEqual(len(writes),3)
            self.assertTrue(all(c.find('Transform/Not') is not None for c in writes[:2]))
            self.assertIsNone(writes[-1].find('Transform'))
            self.assertTrue(all(c.findtext('ConnectValueToWidget')=='false' for c in writes))
        for b in self.root.findall('.//PushButton'):
            if b.findtext('State/Text')=='ON / OFF':
                self.assertEqual(len(b.findall('Connection')),1)
                self.assertTrue(b.findtext('Connection/ConfigKey').endswith('],enabled'))

    def test_transport_and_tabs_have_real_controls_and_touch_sizes(self):
        rows=[g for g in self.root.findall('.//WidgetGroup') if g.findtext('ObjectName')=='MixpiDeckButtons']
        self.assertEqual(len(rows),2)
        for row in rows:
            self.assertEqual(row.findtext('Size'),'0me,56f')
            self.assertEqual(len(row.findall('Children/PushButton')),7)
            self.assertTrue(all(b.findtext('Size')=='0me,48f' for b in row.findall('Children/PushButton')))
        self.assertTrue(all(b.findtext('LeftClickIsPushButton')=='true' for b in self.tabs()))
        self.assertFalse(any('safe_to_remove' in (c.text or '').lower()
                             for c in self.root.findall('.//ConfigKey')))
        self.assertEqual(len(self.root.findall('.//EffectSelector')),3)

    def test_focus_reuses_real_waveforms_outside_loop_panel(self):
        groups = self.root.findall('.//WidgetGroup')
        focused = [group for group in groups if group.findtext('ObjectName') == 'MixpiFocusedOverview']
        self.assertEqual(len(focused), 2)
        for channel, group in enumerate(focused, 1):
            self.assertEqual(group.findtext('Size'), '0me,48f')
            self.assertEqual(group.findtext('Children/Visual/Channel'), str(channel))
            self.assertEqual(group.findtext('Connection/ConfigKey'), '[MixPi],loop_deck')
            self.assertEqual(group.findtext('Connection/Transform/IsEqual'), str(channel))
            keys = [button.findtext('Connection/ConfigKey') for button in group.findall('Children/PushButton')]
            self.assertEqual(keys, [f'[Channel{channel}],waveform_zoom_up', f'[Channel{channel}],waveform_zoom_down'])
        waves = next(group for group in groups if group.findtext('ObjectName') == 'MixpiWaveforms')
        self.assertEqual(waves.findtext('Connection/Transform/IsEqual'), '0')
        for channel in (1, 2):
            strip = self.root.findall('.//Overview')[channel - 1]
            self.assertEqual(strip.findtext('Connection/Transform/IsEqual'), str(channel))
            self.assertIsNotNone(strip.find('Connection/Transform/Not'))

    def test_deck_waveforms_use_the_eos_info_column(self):
        # F-4 A/B decision: restore the 100 px EOS column (700 px waveforms).
        infos = [g for g in self.root.findall('.//WidgetGroup')
                 if g.findtext('ObjectName') == 'MixpiWaveInfo']
        self.assertEqual(len(infos), 2)
        for channel, info in enumerate(infos, 1):
            self.assertEqual(info.findtext('Size'), '100f,0me')
            key = info.find('Children/Key')
            self.assertEqual(key.findtext('ObjectName'), 'MixpiWaveKey')
            self.assertEqual(key.findtext('Size'), '92f,36f')
            self.assertEqual(key.findtext('PairedNotation'), 'true')
            self.assertEqual(key.findtext('Channel'), str(channel))
            row = next(g for g in self.root.findall('.//WidgetGroup') if info in list(g.find('Children')))
            self.assertEqual(row.findtext('ObjectName'), 'MixpiWaveRow')
            self.assertEqual(row.find('Children/Visual').findtext('Size'), '0me,0me')

    def test_deck_readouts_fit_one_time_string_in_a_deck_half(self):
        # Owner decision 1: one time (elapsed, tap for remaining). On the Pi at
        # 21 px, "-14:41.23" is 88 px wide and "125.50" fits the 100 px BPM cell.
        stats = [g for g in self.root.findall('.//WidgetGroup')
                 if g.findtext('ObjectName') == 'MixpiDeckStats']
        self.assertEqual(len(stats), 4)  # Decks and Sampler, both decks
        heights = []
        for group in stats:
            widths = {child.findtext('ObjectName'): int(child.findtext('Size').split('me,')[0])
                      for child in group.find('Children')}
            self.assertEqual(widths, {'MixpiTime': 120, 'MixpiBpm': 100, 'MixpiRate': 60, 'MixpiKey': 120})
            self.assertLessEqual(sum(widths.values()), 400)
            child_heights = {size(child)[1] for child in group.find('Children')}
            self.assertEqual(len(child_heights), 1)
            heights.append(child_heights.pop())
            self.assertEqual(group.find('Children/NumberPos').findtext('NumberOfDigits'), '6')
        self.assertEqual(heights, [54, 54, 48, 48])  # Decks 82 px row, Sampler 72 px row
        style = (self.skin/'style.qss').read_text()
        self.assertIn('#MixpiTime, #MixpiRate, #MixpiKey { color: #f4f6fa; font-size: 21px; }', style)

    def test_overlay_probe_is_explicit_and_repeatable(self):
        SKIN.build(self.skin, 'overlay')
        overlay = ET.parse(self.skin/'skin.xml').getroot()
        self.assertEqual(len(overlay.findall('.//Visual')), 2)
        waves = next(group for group in overlay.findall('.//WidgetGroup')
                     if group.findtext('ObjectName') == 'MixpiWaveforms')
        self.assertEqual(waves.findtext('Connection/Transform/IsEqual'), '3')
        self.assertIsNotNone(waves.find('Connection/Transform/Not'))
        SKIN.build(self.skin)
        self.assertEqual(len(ET.parse(self.skin/'skin.xml').findall('.//Visual')), 4)

    def test_tracks_shows_load_and_cue_instead_of_cue_and_play(self):
        rows = [g for g in self.root.findall('.//WidgetGroup')
                if g.findtext('ObjectName') == 'MixpiDeckButtons']
        for channel, row in enumerate(rows, 1):
            key = f'[Channel{channel}]'
            buttons = {b.findtext('State/Text'): b for b in row.findall('Children/PushButton')}
            load = buttons['LOAD']
            command, enabled, visible = load.findall('Connection')
            self.assertEqual(command.findtext('ConfigKey'), f'{key},LoadSelectedTrack')
            self.assertEqual(command.findtext('EmitOnPressAndRelease'), 'true')
            self.assertEqual(load.findtext('LeftClickIsPushButton'), 'true')
            self.assertEqual((enabled.findtext('ConfigKey'), enabled.findtext('BindProperty')),
                             (f'{key},play', 'enabled'))
            self.assertIsNotNone(enabled.find('Transform/Not'))
            self.assertEqual((visible.findtext('ConfigKey'), visible.findtext('BindProperty')),
                             ('[Tab],library', 'visible'))
            self.assertIsNone(visible.find('Transform'))
            play = buttons['▶']
            gate = play.findall('Connection')[-1]
            self.assertEqual((gate.findtext('ConfigKey'), gate.findtext('BindProperty')),
                             ('[Tab],library', 'visible'))
            self.assertIsNotNone(gate.find('Transform/Not'))
            self.assertEqual(play.findtext('Connection/ConfigKey'), f'{key},play')
            cue = buttons['CUE']
            self.assertEqual([c.findtext('ConfigKey') for c in cue.findall('Connection')],
                             [f'{key},cue_default'])
            self.assertEqual(cue.findtext('Connection/EmitOnPressAndRelease'), 'true')
            names = [b.findtext('State/Text') for b in row.findall('Children/PushButton')]
            self.assertLess(names.index('LOAD'), names.index('CUE'))
            for b in buttons.values():
                self.assertGreaterEqual(int(b.findtext('Size').split(',')[1].rstrip('f')), 48)
        keys = [k.text or '' for k in self.root.findall('.//ConfigKey')]
        self.assertFalse(any('LoadSelectedTrackAndPlay' in key for key in keys))

    def test_loop_quick_controls_keep_decks_navigation_and_sampler_reset(self):
        loops = [button for button in self.root.findall('.//PushButton')
                 if button.findtext('State/Text') == 'LOOP']
        for button in loops:
            self.assertEqual(button.findtext('LeftClickIsPushButton'), 'true')
            keys = [connection.findtext('ConfigKey') for connection in button.findall('Connection')]
            self.assertEqual(keys, ['[MixPi],loop_deck', '[Tab],overview', '[Tab],overview', '[MixPi],sample_load'])
            self.assertEqual(button.findall('Connection')[1].findtext('BindProperty'), 'visible')

    def test_settings_confirmed_native_controls_and_next_launch_labels(self):
        keys = {key.text for key in self.root.findall('.//ConfigKey')}
        self.assertIn('[MixPi],buffer_frames', keys)
        self.assertIn('[MixPi],buffer_available', keys)
        self.assertIn('[MixPi],read_ahead', keys)
        self.assertIn('[MixPi],cache_mb', keys)
        self.assertIn('* Next launch', [text.text for text in self.root.findall('.//Text')])

    @unittest.skipUnless(os.environ.get('PIONEERED_TEST_SKIN'),'pinned upstream checkout optional')
    def test_build_on_pinned_pioneered_preserves_visual_and_overview(self):
        path=Path(self.temp.name)/'upstream'
        shutil.copytree(os.environ['PIONEERED_TEST_SKIN'],path,ignore=shutil.ignore_patterns('.git'))
        TOUCH.apply(path)
        before={p:p.read_bytes() for p in (path/'waveform.xml',path/'deck.xml',path/'library.xml')}
        SKIN.build(path)
        first=(path/'skin.xml').read_bytes()
        SKIN.build(path)
        self.assertEqual(first,(path/'skin.xml').read_bytes())
        self.assertEqual(before,{p:p.read_bytes() for p in before})
        for p in path.rglob('*.xml'):
            ET.parse(p)

if __name__=='__main__':
    unittest.main()
