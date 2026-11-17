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
        if not connections:
            return []  # display-only
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

    def enabled(self, element, state):
        for c in element.findall('Connection'):
            if c.findtext('BindProperty') == 'enabled':
                if not transform(c, float(state.get(c.findtext('ConfigKey'), 0))) > 0:
                    return False
        return True

    def tappable(self, button, state):
        """Visible, enabled and on top. In a stacked group Qt lowers every later
        child (QStackedLayout::insertWidget), so the first visible child is on
        top and takes the taps over its whole area."""
        if not (self.visible(button, state) and self.enabled(button, state)):
            return False
        element = button
        while element in self.parent:
            parent = self.parent[element]
            if parent.tag == 'Children':
                group = self.parent[parent]
                if group.findtext('Layout') == 'stacked':
                    for sibling in parent:
                        if sibling is element:
                            break
                        if self.visible(sibling, state):
                            return False
            element = parent
        return True

    def apply(self, state, writes):
        """Control writes as WWidgetStack sees them: a visible stack switches page
        on a trigger or on [Tab],current and keeps the other triggers at 0; a hidden
        stack ignores both, and on show takes its page from [Tab],current."""
        stack = next(self.root.iter('WidgetStack'))
        triggers = [page.get('trigger') for page in stack.find('Children')]

        def show_page(index):
            state['[Tab],current'] = index
            for i, trigger in enumerate(triggers):
                state[trigger] = 1 if i == index else 0
        for key, value in writes:
            was = self.visible(stack, state)
            state[key] = value
            if was and key in triggers and value:
                show_page(triggers.index(key))
            elif was and key == '[Tab],current':
                show_page(int(value))
            if not was and self.visible(stack, state):
                show_page(int(state.get('[Tab],current', 0)))

    def tap(self, button, state):
        """A touch tap as WPushButton handles it: press, then release only if the
        button is still shown (a hidden widget loses the mouse grab)."""
        assert self.tappable(button, state), (button.findtext('ObjectName'), button.findtext('State/Text'))
        self.apply(state, self.writes(button, 'press', state))
        if self.visible(button, state):
            self.apply(state, self.writes(button, 'release', state))
        return state


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
        self.assertEqual(names, ['MixpiTabPair', 'MixpiTabPair', 'MixpiTabPair', 'MixpiTabPair',
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
        texts = [b.findtext('State/Text') for b in tabs]
        # The tab, one unlit base per condition level, and SAMPLER's lit twin.
        self.assertEqual({t: texts.count(t) for t in texts}, {'DECKS': 2, 'TRACKS': 3, 'FX': 2, 'SAMPLER': 4})
        pages = ['overview', 'library', 'fx', 'sampler']
        names = {'DECKS': 'overview', 'TRACKS': 'library', 'FX': 'fx', 'SAMPLER': 'sampler'}
        stack = next(self.root.iter('WidgetStack'))
        self.assertEqual([p.get('trigger') for p in stack.find('Children')], [f'[Tab],{p}' for p in pages])
        for tab in tabs:
            self.assertEqual(tab.findtext('LeftClickIsPushButton'), 'true')
            page = names[tab.findtext('State/Text')]
            writes = self.model.writes(tab)
            # The page index goes to [Tab],current before screen 0 shows the stack again.
            self.assertEqual(writes[:2], [(f'[Tab],{page}', 1.0), ('[Tab],current', pages.index(page))])
            self.assertEqual(dict(writes[2:]), {SCREEN: 0, '[MixPi],loop_deck': 0,
                                                '[MixPi],sample_load': 0, '[MixPi],sample_pad': 0,
                                                '[Sidebar],sidebar_visible': 0})
            self.assertEqual(self.model.writes(tab, 'release'), [])

    def test_active_tab_is_lit_and_sampler_stays_lit_in_sample_screens(self):
        lit = self.lit_tab
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
        decks = Model.state(0, **{'[Tab]__overview': 1})
        self.assertEqual([lit(t, decks) for t in ('DECKS', 'TRACKS', 'FX', 'SAMPLER')],
                         [True, False, False, False])

    def test_active_tab_style_is_filled_with_a_three_pixel_underline(self):
        style = (self.skin/'style.qss').read_text()
        rule = style.split('#MixpiTab[value="1"] {', 1)[1].split('}', 1)[0]
        self.assertIn('border-bottom: 3px solid #b5e15c;', rule)
        self.assertIn('background:', rule)

    def gear(self):
        return self.button_by_key(SCREEN, 'MixpiIconButton') if False else next(
            b for b in self.model.one('MixpiTopbar').iter('PushButton')
            if b.findtext('ObjectName') == 'MixpiIconButton')

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
        self.assertEqual(sampler.find('Children')[2].findtext('Size'), '0me,1e')
        self.assertEqual(48 + sum(heights[:2]) + SKIN.SAMPLER_INFO + 48 + 56, 480)
        # At 800x444 (desktop bar shown) every page's minimum fits 444 - 48 - 104.
        self.assertLessEqual(sum(heights[:2]) + 1, 444 - 48 - 104)
        info = sampler.find('Children')[2]
        for deck in info.findall('Children/WidgetGroup'):
            self.assertEqual(sum(size(c)[1] for c in deck.find('Children')), SKIN.SAMPLER_INFO)

    def laid_out(self, page, state):
        """(top, heights) of a vertical page's visible children, as QBoxLayout places
        fixed rows plus expanding rows in the 328 px page under the top bar. A page
        without an expanding row is centred by WWidgetGroup's default AlignCenter."""
        rows = [c for c in page.find('Children') if self.model.visible(c, state)]
        heights, expanding = [], 0
        for row in rows:
            w, h, wp, hp = size(row)
            self.assertNotEqual(hp, 'i', 'an Ignored row gets no height')
            if hp == 'f':
                heights.append(h)
            else:
                expanding += 1
                heights.append(None)
        fixed = sum(h for h in heights if h is not None)
        if expanding:
            return 48, [h if h is not None else (328 - fixed) // expanding for h in heights]
        return 48 + (328 - fixed) // 2, heights

    def test_sampler_page_is_top_aligned_with_the_deck_row_shown(self):
        page = self.page('MixpiSampler')
        info = page.find('Children')[2]
        for loop_deck in (0, 3):
            state = {'[Tab],sampler': 1, '[MixPi],loop_deck': loop_deck, SCREEN: 0}
            self.assertTrue(self.model.visible(info, state))
            top, heights = self.laid_out(page, state)
            self.assertEqual((top, heights, sum(heights)), (48, [48, 208, 72], 328))
        style = (FILES/'mixpi-performance.qss').read_text()
        self.assertIn("#MixpiSampler { qproperty-layoutAlignment: 'AlignTop'; }", style)

    def test_widgets_without_skin_connections_carry_none(self):
        # LegacySkinParser builds these with allowConnections false: a binding
        # on them is silently dropped, so their visibility lives on a group.
        for tag in ('SearchBox', 'Library', 'LibrarySidebar', 'StarRating'):
            for e in self.root.iter(tag):
                self.assertEqual(e.findall('Connection'), [], tag)

    def test_two_state_buttons_without_push_mode_target_real_toggles(self):
        self.assertEqual(self.toggle_offenders(self.root), [])

    # ---------- the browse page: Tracks, Sources, Load sample, Choose pad ----------

    VIEWS = ['SidebarButton', 'MixpiTracksCrumb', 'MixpiSourcesHead', 'MixpiLoadHead', 'MixpiSearch',
             'LibraryActionsButton', 'LibrarySourcesButton', 'MixpiSourcesBody',
             'MixpiSampleSources', 'MixpiLibraryMain', 'MixpiTrackTitles', 'MixpiSampleFooter',
             'MixpiChooseScrim']

    def shown(self, state):
        return [name for name in self.VIEWS if self.model.visible(self.model.one(name), state)]

    def test_tracks_toolbar_is_menu_crumb_search_pen(self):
        self.assertEqual(self.shown(Model.state(0, **{'[Tab]__library': 1})),
                         ['SidebarButton', 'MixpiTracksCrumb', 'MixpiSearch', 'LibraryActionsButton',
                          'MixpiLibraryMain', 'MixpiTrackTitles'])
        header = self.model.one('MixpiBrowseHeader')
        self.assertEqual(header.findtext('Size'), '0me,48f')
        self.assertEqual(self.model.one('MixpiTracksCrumb').findtext('Size'), '220f,48f')
        order = [e.findtext('ObjectName') for e in header.iter() if e.findtext('ObjectName') in self.VIEWS]
        self.assertLess(order.index('SidebarButton'), order.index('MixpiTracksCrumb'))
        self.assertLess(order.index('MixpiTracksCrumb'), order.index('MixpiSearch'))
        self.assertLess(order.index('MixpiSearch'), order.index('LibraryActionsButton'))

    def test_sources_is_a_full_screen_with_the_sidebar_under_its_header(self):
        self.assertEqual(self.shown(Model.state(1)),
                         ['SidebarButton', 'MixpiSourcesHead', 'LibrarySourcesButton',
                          'MixpiSourcesBody'])
        # The native sidebar has its own Back; the header has no Back and no search.
        self.assertEqual(self.model.by_name('LibraryBackButton'), [])
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
        self.assertEqual(edit.findtext('NumberStates'), '2')
        self.assertEqual([(st.findtext('Number'), st.findtext('Text')) for st in edit.findall('State')],
                         [('0', 'EDIT LIST'), ('1', 'DONE')])
        command, display = [c for c in edit.findall('Connection') if c.find('BindProperty') is None]
        self.assertEqual([(item.tag, item.text) for item in command],
                         [(item.tag, item.text) for item in original.find('Connection')])
        self.assertEqual(self.model.writes(edit), [('[Library],show_sidebar_sources_menu', 1)])
        self.assertEqual(self.model.writes(edit, 'release'), [])
        # DONE while the native edit list is open: a read-only display connection.
        self.assertEqual((display.findtext('ConfigKey'), display.findtext('ConnectValueFromWidget'),
                          display.findtext('ConnectValueToWidget')),
                         ('[Library],sidebar_sources_editing', 'false', 'true'))

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
                             ['MixpiLoadHead', 'MixpiSearch', 'MixpiSampleSources', 'MixpiLibraryMain',
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

    # ---------- replays of the Pi preview sequences (fix round 1) ----------

    def start(self):
        # Manifest attributes at skin load; nothing here is saved.
        state = {a.get('config_key'): float(a.text)
                 for a in self.root.findall('manifest/attributes/attribute')}
        state['[Library],show_track_menu'] = 0
        return state

    def tab_button(self, text, state):
        found = [b for b in self.tabs() if b.findtext('State/Text') == text and self.model.tappable(b, state)]
        self.assertEqual(len(found), 1, text)
        return found[0]

    def shown_button(self, state, **match):
        found = [b for b in self.root.iter('PushButton')
                 if all((b.findtext(k) if k != 'key' else b.findtext('Connection/ConfigKey')) == v
                        for k, v in match.items()) and self.model.tappable(b, state)]
        self.assertEqual(len(found), 1, match)
        return found[0]

    def assert_load_sample(self, state, choose=False):
        self.assertEqual(state[SCREEN], 4 if choose else 3)
        self.assertEqual((state['[Tab],library'], state['[MixPi],sample_load']), (1, 1))
        self.assertEqual(self.shown(state)[:5], ['MixpiLoadHead', 'MixpiSearch', 'MixpiSampleSources',
                                                 'MixpiLibraryMain', 'MixpiSampleFooter'])
        self.assertFalse(self.model.visible(self.model.one('MixpiBottom'), state))
        # The sheet covers the list exactly when Choose pad is open.
        tiles = self.tiles()
        self.assertEqual([self.model.tappable(t, state) for t in tiles], [choose] * 8)
        self.assertEqual(self.model.tappable(self.load_targets()[0], state), not choose)

    def test_replay_sequence_a_load_sample_then_choose_pad(self):
        model, state = self.model, self.start()
        model.tap(self.tab_button('SAMPLER', state), state)
        model.tap(self.button_by_text('+  LOAD SAMPLE'), state)
        self.assert_load_sample(state)
        model.tap(self.shown_button(state, ObjectName='MixpiPrimary', key=SCREEN), state)  # LOAD TO PAD…
        self.assert_load_sample(state, choose=True)
        tile = self.tiles()[4]
        self.assertEqual(model.writes(tile), [('[Sampler5],LoadSelectedTrack', 1)])
        model.tap(tile, state)
        self.assertEqual((state[SCREEN], state['[Tab],sampler'], state['[MixPi],sample_load']), (0, 1, 0))
        self.assertEqual(state['[Sampler5],LoadSelectedTrack'], 0)
        self.assertTrue(model.visible(self.model.one('MixpiBottom'), state))

    def test_replay_sequence_b_cancel_close_tracks_actions_then_load_sample(self):
        model, state = self.model, self.start()
        model.tap(self.tab_button('SAMPLER', state), state)
        model.tap(self.button_by_text('+  LOAD SAMPLE'), state)
        model.tap(self.shown_button(state, ObjectName='MixpiPrimary', key=SCREEN), state)
        model.tap(self.button_by_text('CANCEL'), state)
        self.assert_load_sample(state)
        model.tap(self.shown_button(state, ObjectName='MixpiIconButton', key='[Tab],sampler'), state)  # ✕
        self.assertEqual((state[SCREEN], state['[Tab],sampler'], state['[MixPi],sample_load']), (0, 1, 0))
        model.tap(self.tab_button('TRACKS', state), state)
        pen = self.model.one('LibraryActionsButton')
        model.tap(pen, state)
        self.assertEqual(state['[Library],show_track_menu'], 1)
        # On the Pi the open Actions menu (a Qt popup) eats the next tap; the
        # preview's SAMPLER tap closed the menu, so LOAD SAMPLE then hit the list.
        state['[Library],show_track_menu'] = 0
        model.tap(self.tab_button('SAMPLER', state), state)
        model.tap(self.button_by_text('+  LOAD SAMPLE'), state)
        self.assert_load_sample(state)
        model.tap(self.shown_button(state, ObjectName='MixpiPrimary', key=SCREEN), state)
        self.assert_load_sample(state, choose=True)

    def test_overlay_buttons_are_on_top_of_their_labels(self):
        for sampler, pad in enumerate(self.pads(), 1):
            key = f'[Sampler{sampler}]'
            trigger = next(b for b in pad.iter('PushButton') if b.findtext('ObjectName') == 'MixpiPadTap')
            open_load = next(b for b in pad.iter('PushButton') if b.findtext('ObjectName') == 'MixpiPadLoad')
            self.assertTrue(self.model.tappable(trigger, {'[Tab],sampler': 1, f'{key},track_loaded': 1}))
            self.assertTrue(self.model.tappable(open_load, {'[Tab],sampler': 1}))
        playing = dict(Model.state(4), **{'[Sampler2],play': 1})
        self.assertEqual([self.model.tappable(t, playing) for t in self.tiles()],
                         [True, False] + [True] * 6)

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

    def lit_tab(self, text, state):
        """The tab on top (Qt: first visible child of a stacked group) and whether it is lit."""
        shown = [b for b in self.tabs() if b.findtext('State/Text') == text and self.model.tappable(b, state)]
        self.assertEqual(len(shown), 1, (text, state))
        display = [c for c in shown[0].findall('Connection')
                   if c.find('BindProperty') is None and c.findtext('ConnectValueToWidget') == 'true']
        return bool(display) and transform(display[-1], float(state.get(display[-1].findtext('ConfigKey'), 0))) == 1

    def test_settings_screen_lights_only_the_gear(self):
        gear = self.gear()
        for page in ('overview', 'library', 'fx', 'sampler'):
            state = Model.state(5, **{f'[Tab]__{page}': 1})
            state['[Tab],library'] = 1 if page == 'library' else 0
            self.assertEqual([self.lit_tab(t, state) for t in ('DECKS', 'TRACKS', 'FX', 'SAMPLER')],
                             [False] * 4, page)
        self.assertEqual(transform(gear.find('Connection'), 5.0), 1)
        self.assertEqual(transform(gear.find('Connection'), 0.0), 0)

    def test_gear_opens_the_full_screen_settings(self):
        gear = self.gear()
        self.assertEqual(gear.findtext('Size'), '48f,48f')
        self.assertEqual(gear.findtext('Connection/ConfigKey'), SCREEN)
        self.assertEqual(gear.findtext('Connection/ConnectValueToWidget'), 'true')
        self.assertEqual(self.model.writes(gear), [
            (SCREEN, 5), ('[MixPi],loop_deck', 0), ('[MixPi],sample_load', 0),
            ('[MixPi],sample_pad', 0), ('[Sidebar],sidebar_visible', 0)])
        guard = next(c for c in gear.findall('Connection') if c.findtext('BindProperty') == 'enabled')
        self.assertEqual(guard.findtext('ConfigKey'), '[MixPi],settings_available')
        self.assertEqual([s.findtext('Unpressed') for s in gear.findall('State')],
                         ['mixpi-icon-gear.svg'] * 2)

    def test_usb_chip_follows_media_state_and_opens_the_media_view(self):
        chip = self.model.one('MixpiUsbChip')
        self.assertEqual((chip.findtext('Layout'), chip.findtext('Size')), ('stacked', '150f,48f'))
        tap = chip.find('Children')[0]
        self.assertEqual((tap.findtext('ObjectName'), tap.findtext('Size')), ('MixpiUsbButton', '150f,48f'))
        self.assertEqual(self.model.writes(tap), [('[MixPi],media_load', 1)])
        gate = tap.findall('Connection')[-1]
        self.assertEqual((gate.findtext('ConfigKey'), gate.findtext('BindProperty')),
                         ('[MixPi],media_available', 'enabled'))
        self.assertEqual({s.findtext('Unpressed') for s in tap.findall('State')}, {'mixpi-icon-usb.svg'})
        self.assertTrue(self.model.tappable(tap, {'[MixPi],media_available': 1}))
        name = self.model.one('MixpiUsbName')
        self.assertEqual((name.tag, name.findtext('Text')), ('Label', 'USB'))
        body = self.model.one('MixpiUsbBody')
        self.assertEqual([(c.findtext('ConfigKey'), c.findtext('BindProperty')) for c in body.findall('Connection')],
                         [('[MixPi],media_state', 'highlight')])
        words = ['NO USB', 'READY', 'IN USE', 'EJECTING', 'SAFE TO REMOVE']
        for value in range(5):
            shown = [l.findtext('Text') for l in body.iter('Label')
                     if l.findtext('ObjectName').startswith('MixpiUsbState')
                     and self.model.visible(l, {'[MixPi],media_state': value})]
            self.assertEqual(shown, [words[value]])
        scan = self.model.one('MixpiUsbScan')
        self.assertEqual((scan.tag, scan.findtext('Text')), ('Number', 'SCAN %1%'))
        self.assertEqual(scan.findtext('Connection/ConfigKey'), '[MixPi],scan_percent')
        for active in (0, 1):
            for hidden in (0, 1):
                state = {'[MixPi],scan_active': active, '[MixPi],scan_bar_hidden': hidden}
                self.assertEqual(self.model.visible(scan, state), bool(active and hidden))
        self.assertNotIn('LOAD / EJECT', [t.text for t in self.root.iter('Text')])
        style = (FILES/'mixpi-performance.qss').read_text()
        self.assertIn('#MixpiUsbBody[highlight="4"]', style)
        self.assertFalse(any(b.findtext('Connection/ConfigKey') == '[MixPi],media_eject'
                             for b in self.root.iter('PushButton')))

    PAGES_ON = {'[Tab],overview': 1, '[Tab],fx': 1, '[Tab],sampler': 1}

    def rows(self):
        return [g for g in self.root.iter('WidgetGroup') if g.findtext('ObjectName') == 'MixpiDeckButtons']

    def test_deck_page_rows_are_waveforms_256_and_info_72(self):
        perform = self.page('MixpiPerform')
        area, info = perform.find('Children')
        self.assertEqual(area.findtext('Size'), '0me,0me')
        self.assertEqual(info.findtext('Size'), '0me,72f')
        waves = self.model.one('MixpiWaveforms')
        self.assertEqual([size(r)[3] for r in waves.find('Children')], ['me', 'me'])  # 2 x 128 of 256
        self.assertEqual(328 - 72, 2 * 128)
        # At 800x444 the page has 444 - 48 - 104 = 292 px: the tallest tool body
        # (shown alone) plus the panel header and the 72 px info must fit.
        panel = self.tool(1)
        fixed = lambda g: sum(size(c)[1] for c in g.find('Children') if size(c)[3] == 'f')
        bodies = [g for g in panel.find('Children') if g.findtext('ObjectName', '').endswith('Body')]
        self.assertEqual(len(bodies), 3)
        for body in bodies:
            self.assertEqual(fixed(body), size(body)[1])
            self.assertLessEqual(4 + 48 + 6 + size(body)[1] + 72, 444 - 48 - 104)
        # Tool panels first: in the overlay trial they sit above the waveforms.
        self.assertEqual([c.findtext('ObjectName') for c in area.find('Children')],
                         ['MixpiLoopPanel', 'MixpiLoopPanel', 'MixpiWaveforms'])

    def test_deck_waveform_column_is_92_px_with_badge_key_and_states(self):
        infos = [g for g in self.root.iter('WidgetGroup') if g.findtext('ObjectName') == 'MixpiWaveInfo']
        self.assertEqual(len(infos), 2)
        for channel, info in enumerate(infos, 1):
            self.assertEqual(info.findtext('Size'), '92f,0me')
            badge = info.find('Children/Label')
            self.assertEqual((badge.findtext('ObjectName'), badge.findtext('Text')),
                             (f'MixpiWaveBadge{channel}', str(channel)))
            key = info.find('Children/Key')
            self.assertEqual((key.findtext('Size'), key.findtext('PairedNotation'), key.findtext('Channel')),
                             ('84f,28f', 'true', str(channel)))
            chips = list(info.iter('PushButton'))
            self.assertEqual([(c.findtext('State/Text'), c.findtext('Connection/ConfigKey')) for c in chips],
                             [('MT', f'[Channel{channel}],keylock'), ('Q', f'[Channel{channel}],quantize')])
            for c in chips:
                self.assertEqual(self.model.writes(c), [])
            row = self.model.parent[self.model.parent[info]]
            self.assertEqual(row.findtext('ObjectName'), 'MixpiWaveRow')
            self.assertEqual(row.find('Children/Visual').findtext('Size'), '0me,0me')

    def test_deck_info_chips_are_display_only(self):
        for channel in (1, 2):
            key = f'[Channel{channel}]'
            heads = [g for g in self.root.iter('WidgetGroup') if g.findtext('ObjectName') == 'MixpiTitleStrip'
                     and any(e.findtext('Text') == 'MASTER' for e in g.iter('Label'))
                     and g.find('Children/TrackProperty').findtext('Channel') == str(channel)]
            self.assertEqual(len(heads), 3)  # Decks, FX, Sampler
            for head in heads:
                chips = {l.findtext('Text'): l for l in head.iter('Label') if l.findtext('Text') in ('ON PI', 'MASTER', 'PFL')}
                self.assertEqual({t: l.findtext('Connection/ConfigKey') for t, l in chips.items()},
                                 {'ON PI': f'{key},mixpi_on_pi', 'MASTER': f'{key},sync_leader', 'PFL': f'{key},pfl'})
                for l in chips.values():
                    self.assertEqual(l.findtext('Connection/BindProperty'), 'visible')
                self.assertEqual([p.findtext('Property') for p in head.iter('TrackProperty')], ['title', 'artist'])

    def tool(self, channel):
        return [g for g in self.root.iter('WidgetGroup') if g.findtext('ObjectName') == 'MixpiLoopPanel'][channel - 1]

    def test_tool_panel_tabs_and_bodies(self):
        for channel in (1, 2):
            panel = self.tool(channel)
            self.assertEqual(panel.findtext('Connection/Transform/IsEqual'), str(channel))
            tabs = [b for b in panel.iter('PushButton') if b.findtext('ObjectName') == f'MixpiToolTab{channel}']
            self.assertEqual([b.findtext('State/Text') for b in tabs], ['LOOP', 'JUMP', 'CUES'])
            for value, tab in enumerate(tabs):
                self.assertEqual(self.model.final(tab), {'[MixPi],tool_tab': value, '[MixPi],cue_clear': 0})
                state = {'[MixPi],loop_deck': channel, '[MixPi],tool_tab': value, '[Tab],overview': 1}
                shown = [n for n in ('MixpiLoopBody', 'MixpiJumpBody', 'MixpiCuesBody')
                         if self.model.visible(next(g for g in panel.iter('WidgetGroup') if g.findtext('ObjectName') == n), state)]
                self.assertEqual(shown, [['MixpiLoopBody', 'MixpiJumpBody', 'MixpiCuesBody'][value]])
            close = next(b for b in panel.iter('PushButton') if b.findtext('State/Text') == '×  CLOSE')
            self.assertEqual(self.model.final(close), {'[MixPi],loop_deck': 0, '[MixPi],cue_clear': 0})

    def test_tool_panel_jump_and_cues_use_real_controls(self):
        key = '[Channel1]'
        panel = self.tool(1)
        jumps = [b for b in panel.iter('PushButton') if 'beatjump' in b.findtext('Connection/ConfigKey')]
        self.assertEqual([b.findtext('Connection/ConfigKey') for b in jumps],
                         [f'{key},beatjump_{n}_backward' for n in (1, 2, 4, 8, 16, 32)] +
                         [f'{key},beatjump_{n}_forward' for n in (1, 2, 4, 8, 16, 32)])
        for b in jumps:
            self.assertEqual(b.findtext('Size'), '107f,56f')
            self.assertEqual(b.findtext('Connection/EmitOnPressAndRelease'), 'true')
        for n in range(1, 9):
            cell = [g for g in panel.iter('WidgetGroup') if g.findtext('ObjectName') == 'MixpiCueCell'][n - 1]
            clear, tap = cell.findall('Children/PushButton')
            self.assertEqual(tap.findtext('Connection/ConfigKey'), f'{key},hotcue_{n}_activate')
            self.assertEqual(clear.findtext('Connection/ConfigKey'), f'{key},hotcue_{n}_clear')
            for b in (tap, clear):
                self.assertEqual(b.findtext('Size'), '196f,70f')
                display = [c for c in b.findall('Connection') if c.findtext('ConnectValueFromWidget') == 'false'][-1]
                self.assertEqual(display.findtext('ConfigKey'), f'{key},hotcue_{n}_enabled')
                self.assertEqual([transform(display, v) for v in (0, 1, 2)], [0, 1, 1])
            for clearing, top in ((0, tap), (1, clear)):
                state = {'[MixPi],loop_deck': 1, '[MixPi],tool_tab': 2, '[Tab],overview': 1,
                         '[MixPi],cue_clear': clearing, f'{key},hotcue_{n}_enabled': 1}
                self.assertTrue(self.model.tappable(top, state))
        clear_pair = next(g for g in panel.iter('WidgetGroup') if g.findtext('ObjectName') == 'MixpiCueClear')
        on, off = clear_pair.findall('Children/PushButton')
        self.assertEqual(self.model.final(off), {'[MixPi],cue_clear': 1})
        self.assertEqual(self.model.final(on), {'[MixPi],cue_clear': 0})
        self.assertFalse(self.model.visible(off, {'[MixPi],loop_deck': 1, '[MixPi],tool_tab': 0, '[Tab],overview': 1}))
        self.assertTrue(self.model.visible(off, {'[MixPi],loop_deck': 1, '[MixPi],tool_tab': 2, '[Tab],overview': 1}))

    def test_tool_panel_hit_map(self):
        panel = self.tool(1)
        header = next(g for g in panel.iter('WidgetGroup') if g.findtext('ObjectName') == 'MixpiToolHeader')
        x, centres = 0, {}
        for e in header.find('Children'):
            w = size(e)[0]
            centres.setdefault(e.findtext('State/Text') or e.findtext('ObjectName'), x + w / 2)
            x += w if size(e)[2] == 'f' else 0
        self.assertEqual([centres['LOOP'], centres['JUMP'], centres['CUES']], [182, 288, 394])
        x = 800
        for e in reversed(list(header.find('Children'))):
            if size(e)[2] != 'f':
                break
            x -= size(e)[0]
            centres[e.findtext('ObjectName') + '<'] = x + size(e)[0] / 2
        self.assertEqual((centres['MixpiCueClear<'], centres['MixpiButton<']), (627, 737))
        row = next(g for g in panel.iter('WidgetGroup') if g.findtext('ObjectName') == 'MixpiJumpRow')
        x, jumps = 0, []
        for e in row.find('Children'):
            if e.tag == 'PushButton':
                jumps.append(x + size(e)[0] / 2)
            x += size(e)[0]
        for got, plan in zip(jumps, (177, 290, 403, 516, 629, 742)):
            self.assertLessEqual(abs(got - plan), 1)
        cue_row = next(g for g in panel.iter('WidgetGroup') if g.findtext('ObjectName') == 'MixpiCueRow')
        x, cues = 0, []
        for e in cue_row.find('Children'):
            if e.findtext('ObjectName') == 'MixpiCueCell':
                cues.append(x + size(e)[0] / 2)
            x += size(e)[0]
        self.assertEqual(cues, [106, 302, 498, 694])
        # y: panel top 48 + 4, header 48 → centre 76; bodies start at 106.
        self.assertEqual(48 + 4 + 24, 76)
        self.assertEqual([48 + 4 + 48 + 6 + 28, 48 + 4 + 48 + 6 + 56 + 6 + 28], [134, 196])
        self.assertEqual([106 + 35, 106 + 70 + 6 + 35], [141, 217])

    def test_fx_has_two_units_one_visible_per_switch_value(self):
        units = [g for g in self.root.iter('WidgetGroup') if g.findtext('ObjectName') == 'MixpiFxUnit']
        self.assertEqual(len(units), 2)
        for unit, group in enumerate(units, 1):
            selectors = list(group.iter('EffectSelector'))
            self.assertEqual([(s.findtext('EffectUnit'), s.findtext('Effect')) for s in selectors],
                             [(str(unit), str(n)) for n in (1, 2, 3)])
            keys = [k.text for k in group.iter('ConfigKey')]
            self.assertIn(f'[EffectRack1_EffectUnit{unit}],mix', keys)
            other = 3 - unit
            self.assertFalse(any(f'EffectUnit{other}' in k for k in keys))
            deck = 'A' if unit == 1 else 'B'
            self.assertEqual([t.text for t in group.iter('Text') if t.text.startswith('deck ')],
                             [f'deck {deck} FX pad {n}' for n in (1, 2, 3)])
            for value in (1, 2):
                self.assertEqual(self.model.visible(group, {'[Tab],fx': 1, '[MixPi],fx_unit': value}), value == unit)
            ons = [b for b in group.iter('PushButton') if b.findtext('Connection/ConfigKey', '').endswith('],enabled')]
            self.assertEqual(len(ons), 3)
            for b in ons:
                self.assertEqual([s.findtext('Text') for s in b.findall('State')], ['OFF', 'ON'])
                self.assertEqual(len(b.findall('Connection')), 1)
        switch = [b for b in self.root.iter('PushButton') if b.findtext('Connection/ConfigKey') == '[MixPi],fx_unit']
        self.assertEqual([b.findtext('State/Text') for b in switch], ['FX 1 · DECK A PADS', 'FX 2 · DECK B PADS'])
        self.assertEqual([self.model.final(b) for b in switch], [{'[MixPi],fx_unit': 1}, {'[MixPi],fx_unit': 2}])
        attributes = {a.get('config_key'): a.text for a in self.root.findall('manifest/attributes/attribute')}
        self.assertEqual(attributes['[MixPi],fx_unit'], '1')

    def test_settings_is_a_full_screen_with_a_rail(self):
        settings = self.model.one('MixpiSettings')
        pages = self.model.one('MixpiPages')
        for screen in range(6):
            self.assertEqual(self.model.visible(settings, {SCREEN: screen}), screen == 5)
            self.assertEqual(self.model.visible(pages, {SCREEN: screen}), screen != 5)
        rail = [b for b in settings.iter('PushButton') if b.findtext('ObjectName') == 'MixpiRailButton']
        self.assertEqual([b.findtext('State/Text') for b in rail], ['PLAYBACK', 'INTERFACE', 'MEDIA', 'ADVANCED'])
        for value, b in enumerate(rail):
            self.assertEqual(b.findtext('Size'), '200f,56f')
            self.assertEqual(b.findtext('LeftClickIsPushButton'), 'true')
            self.assertEqual(self.model.final(b), {'[MixPi],settings_page': value})
        panes = list(self.model.one('MixpiSettingsPanes').find('Children'))
        for value in range(4):
            state = {SCREEN: 5, '[MixPi],settings_page': value}
            self.assertEqual([self.model.visible(p, state) for p in panes], [i == value for i in range(4)])
        close = next(b for b in settings.iter('PushButton') if b.findtext('ObjectName') == 'MixpiIconButton')
        self.assertEqual(self.model.final(close), {SCREEN: 0})
        saved = next(l for l in settings.iter('Label') if l.findtext('Text') == 'Saved')
        self.assertEqual(saved.findtext('Connection/ConfigKey'), '[MixPi],saved')
        # Rail tap points (plan 5.3): x 100, y 124/180/236/292.
        self.assertEqual([48 + 48 + 28 + 56 * i for i in range(4)], [124, 180, 236, 292])
        attributes = {a.get('config_key'): a for a in self.root.findall('manifest/attributes/attribute')}
        self.assertEqual(attributes['[MixPi],settings_page'].text, '0')

    def pane_writes(self, pane):
        return {b.findtext('State/Text'): self.model.final(b) for b in pane.iter('PushButton')}

    def test_settings_panes_keep_todays_controls(self):
        panes = list(self.model.one('MixpiSettingsPanes').find('Children'))
        playback, interface, media, advanced = (self.pane_writes(p) for p in panes)
        self.assertEqual({k: playback[k] for k in ('ST', 'RB FAST', 'RB FINE')},
                         {'ST': {'[MixPi],keylock_engine': 0}, 'RB FAST': {'[MixPi],keylock_engine': 1},
                          'RB FINE': {'[MixPi],keylock_engine': 2}})
        self.assertEqual([playback[k] for k in ('256', '512', '1024')],
                         [{'[MixPi],buffer_frames': v} for v in (256, 512, 1024)])
        self.assertEqual([playback[k] for k in ('6%', '8%', '10%', '16%', '24%')],
                         [{'[MixPi],tempo_range_index': v} for v in (2, 3, 4, 5, 6)])
        for b in panes[0].iter('PushButton'):
            if b.findtext('Connection/ConfigKey') == '[MixPi],buffer_frames':
                guard = next(c for c in b.findall('Connection') if c.findtext('BindProperty') == 'enabled')
                self.assertEqual(guard.findtext('ConfigKey'), '[MixPi],buffer_available')
        self.assertEqual(playback['DECK 1'], {'[Channel1],quantize': 1})
        self.assertEqual(playback['OFF'], {'[Master],headSplit': 1})
        self.assertEqual(interface['ELAPSED'], {'[Controls],ShowDurationRemaining': 0})
        self.assertEqual(interface['REMAINING'], {'[Controls],ShowDurationRemaining': 1})
        bar = next(b for b in panes[1].iter('PushButton') if b.findtext('ObjectName') == 'MixpiDesktopBar')
        self.assertEqual(self.model.final(bar), {'[MixPi],desktop_bar': 1})
        self.assertEqual(media['SHOW'], {'[MixPi],scan_bar_hidden': 0})
        self.assertEqual(media['HIDE'], {'[MixPi],scan_bar_hidden': 1})
        self.assertEqual([media[k] for k in ('OFF', '512', '1024')],
                         [{'[MixPi],cache_mb': v} for v in (0, 512, 1024)])
        texts = [t.text for t in panes[2].iter('Text')]
        self.assertIn('MB. Also the room for handover copies. Next launch.', texts)
        self.assertIn('A small ping at the bottom with LOAD or DISMISS', texts)
        eject = {l.findtext('Text'): l for l in panes[2].iter('Label') if l.findtext('Text') in ('ON', 'OFF')}
        for value in (0, 1):
            state = {SCREEN: 5, '[MixPi],settings_page': 2, '[MixPi],media_eject_available': value}
            self.assertEqual([t for t, l in eject.items() if self.model.visible(l, state)],
                             ['ON' if value else 'OFF'])
        self.assertEqual([advanced[k] for k in ('30', '45', '60')],
                         [{'[MixPi],waveform_fps': v} for v in (30, 45, 60)])
        self.assertEqual([advanced[k] for k in ('2', '8', '24')],
                         [{'[MixPi],read_ahead': v} for v in (2, 8, 24)])
        # F-2: the Preferences button is on Advanced and is a push button.
        prefs = next(b for b in panes[3].iter('PushButton') if b.findtext('State/Text') == 'Mixxx preferences…')
        self.assertEqual(prefs.findtext('LeftClickIsPushButton'), 'true')
        command, = prefs.findall('Connection')
        self.assertEqual(command.findtext('ConfigKey'), '[MixPi],show_preferences')
        self.assertEqual(command.findtext('EmitOnDownPress'), 'true')
        self.assertEqual(command.findtext('ConnectValueToWidget'), 'false')
        self.assertIsNone(command.find('Transform'))
        keys = {k.text for k in self.root.iter('ConfigKey')}
        self.assertNotIn('[MixPi],settings_advanced', keys)  # the native control takes 0/1 only
        self.assertIn('Next launch', ' '.join(t.text or '' for t in self.root.iter('Text')))

    def test_fx_and_sampler_pages_fill_328(self):
        fx = self.page('MixpiFxPage')
        heights = [size(c)[1] for c in fx.find('Children')]
        self.assertEqual(heights[0], 256)
        self.assertEqual(fx.find('Children')[1].findtext('Size'), '0me,1e')
        content = self.model.one('MixpiFx')
        for unit in (1, 2):
            state = {'[Tab],fx': 1, '[MixPi],fx_unit': unit}
            shown = [size(c)[1] for c in content.find('Children') if self.model.visible(c, state)]
            self.assertEqual(shown, [56, 200])
            self.assertEqual(sum(shown) + 72, 328)

    def test_sampler_pads_show_on_pi(self):
        for sampler, pad in enumerate(self.pads(), 1):
            chips = [l for l in pad.iter('Label') if l.findtext('Text') == 'ON PI']
            self.assertEqual([c.findtext('Connection/ConfigKey') for c in chips], [f'[Sampler{sampler}],mixpi_on_pi'])

    def test_header_slot_puts_the_right_button_on_top(self):
        menu = self.model.one('SidebarButton')
        closes = {b.findtext('Connection/ConfigKey'): b for b in self.model.one('MixpiHeaderSlot').iter('PushButton')
                  if b.findtext('ObjectName') == 'MixpiIconButton'}
        cases = [(Model.state(0, **{'[Tab]__library': 1}), menu),
                 (Model.state(1), menu),
                 (Model.state(1, **{'[MixPi]__sample_load': 1}), closes['[Sidebar],sidebar_visible']),
                 (Model.state(3), closes['[Tab],sampler']),
                 # A native close of Sources opened from Load sample: still Load sample.
                 (Model.state(0, **{'[MixPi]__sample_load': 1, '[Tab]__library': 1}), closes['[Tab],sampler']),
                 # A native USB open clears sample mode: Tracks, with the menu.
                 (Model.state(3, **{'[MixPi]__sample_load': 0}), menu)]
        for state, expected in cases:
            top = [b for b in [menu] + list(closes.values()) if self.model.tappable(b, state)]
            self.assertEqual(top, [expected], state)

    def test_menu_is_always_there_on_plain_tracks(self):
        menu = self.model.one('SidebarButton')
        # Screen 4 is left out: the Choose pad sheet covers the page by design.
        for screen in (0, 1, 3):
            state = Model.state(screen, **{'[MixPi]__sample_load': 0, '[Tab]__library': 1})
            self.assertTrue(self.model.tappable(menu, state), screen)

    def test_replay_native_close_of_sources_opened_from_load_sample(self):
        # Build A: SAMPLER, LOAD SAMPLE, SOURCES…, then a leaf in the native rail;
        # N2's auto-close writes screen 0 and sidebar_visible 0.
        model, state = self.model, self.start()
        model.tap(self.tab_button('SAMPLER', state), state)
        model.tap(self.button_by_text('+  LOAD SAMPLE'), state)
        model.tap(self.button_by_text('SOURCES…'), state)
        self.assertEqual((state[SCREEN], state['[Sidebar],sidebar_visible'], state['[MixPi],sample_load']), (1, 1, 1))
        model.apply(state, [(SCREEN, 0), ('[Sidebar],sidebar_visible', 0)])
        self.assertEqual(self.shown(state), ['MixpiLoadHead', 'MixpiSearch', 'MixpiSampleSources',
                                             'MixpiLibraryMain', 'MixpiSampleFooter'])
        self.assertFalse(model.visible(self.model.one('MixpiBottom'), state))
        self.assertTrue(self.lit_tab('SAMPLER', state))
        self.assertFalse(self.lit_tab('TRACKS', state))
        # LOAD TO PAD… and Choose pad work from here.
        model.tap(self.shown_button(state, ObjectName='MixpiPrimary', key=SCREEN), state)
        self.assertEqual(state[SCREEN], 4)
        self.assertTrue(model.tappable(self.tiles()[0], state))
        model.tap(self.button_by_text('CANCEL'), state)
        # Its ✕ returns to the Sampler; TRACKS is plain Tracks with the menu.
        model.tap(self.shown_button(state, ObjectName='MixpiIconButton', key='[Tab],sampler'), state)
        self.assertEqual((state[SCREEN], state['[MixPi],sample_load'], state['[Tab],sampler']), (0, 0, 1))
        model.tap(self.tab_button('TRACKS', state), state)
        self.assertEqual(self.shown(state), ['SidebarButton', 'MixpiTracksCrumb', 'MixpiSearch',
                                             'LibraryActionsButton', 'MixpiLibraryMain', 'MixpiTrackTitles'])
        self.assertTrue(model.visible(self.model.one('MixpiBottom'), state))
        self.assertTrue(model.tappable(self.model.one('SidebarButton'), state))

    def test_replay_tab_from_settings_opens_that_tab(self):
        # Build A preview: FX, FX 2, gear, MEDIA, SAMPLER landed on FX.
        for text, page in (('SAMPLER', 'sampler'), ('DECKS', 'overview'), ('TRACKS', 'library'), ('FX', 'fx')):
            model, state = self.model, self.start()
            state['[MixPi],settings_available'] = 1  # native (performance settings)
            model.tap(self.tab_button('FX', state), state)
            model.tap(self.button_by_text('FX 2 · DECK B PADS'), state)
            model.tap(self.gear(), state)
            self.assertEqual(state[SCREEN], 5)
            self.assertFalse(model.visible(next(self.root.iter('WidgetStack')), state))
            media = next(b for b in self.root.iter('PushButton')
                         if b.findtext('ObjectName') == 'MixpiRailButton' and b.findtext('State/Text') == 'MEDIA')
            model.tap(media, state)
            model.tap(self.tab_button(text, state), state)
            self.assertEqual(state[SCREEN], 0)
            self.assertEqual([p for p in ('overview', 'library', 'fx', 'sampler') if state[f'[Tab],{p}']], [page])
            self.assertTrue(self.lit_tab(text, state), text)
            self.assertTrue(model.visible(self.model.one('MixpiBottom'), state))

    def reserved(self, element, state, axis):
        """(fixed px, flexible?) a shown element takes along AXIS (0 width, 1 height)."""
        if not self.model.visible(element, state):
            return 0, False
        w, h, wp, hp = size(element)
        length, policy = (w, wp) if axis == 0 else (h, hp)
        if policy == 'f':
            return length, False
        if policy == 'max':
            children = element.find('Children')
            parts = [self.reserved(c, state, axis) for c in (children if children is not None else [])]
            along = (element.findtext('Layout') == 'horizontal') == (axis == 0)
            fixed = [p[0] for p in parts]
            return (sum(fixed) if along else max(fixed or [0])), any(p[1] for p in parts)
        return 0, True

    def test_full_screen_views_fill_432_under_the_top_bar(self):
        root_rows = list(self.root.find('Children'))[1:]  # under the top bar
        wrapper = self.model.one('LibraryWrapper')
        cases = {
            'tracks': (Model.state(0, **{'[Tab]__library': 1}), 104, 48 + 28),
            'sources': (Model.state(1), 0, 48),
            'sources from load sample': (Model.state(1, **{'[MixPi]__sample_load': 1}), 0, 48),
            'load sample': (Model.state(3), 0, 48 + 56 + 64),
            'choose pad': (Model.state(4), 0, 48 + 56 + 64),
            'load sample after a native close': (Model.state(0, **{'[MixPi]__sample_load': 1, '[Tab]__library': 1}),
                                                 0, 48 + 56 + 64),
            'settings': (Model.state(5, **{'[Tab]__overview': 1}), 0, None),
            'decks': (Model.state(0, **{'[Tab]__overview': 1}), 104, None),
        }
        for name, (state, bottom, browse_fixed) in cases.items():
            parts = [self.reserved(row, state, 1) for row in root_rows]
            self.assertEqual(sum(p[0] for p in parts), bottom, name)
            self.assertEqual(sum(1 for p in parts if p[1]), 1, name)  # one view takes the rest of 432
            if browse_fixed is not None:
                rows = [self.reserved(c, state, 1) for c in wrapper.find('Children')]
                self.assertEqual(sum(p[0] for p in rows), browse_fixed, name)
                self.assertTrue(any(p[1] for p in rows), name)

    def test_sources_title_sits_right_after_the_close(self):
        header = self.model.one('MixpiBrowseHeader')
        for state in (Model.state(1), Model.state(1, **{'[MixPi]__sample_load': 1})):
            x = 0
            for child in header.find('Children'):
                if child.findtext('ObjectName') == 'MixpiSourcesHead':
                    break
                x += self.reserved(child, state, 0)[0]
            self.assertEqual(x, 48)

    def test_settings_sub_lines_wrap_and_fx_hint_fits(self):
        style = (FILES/'mixpi-performance.qss').read_text()
        self.assertIn('qproperty-wordWrap: true;', style.split('#MixpiSettingLabel {', 1)[1].split('}', 1)[0])
        for l in self.model.one('MixpiSettings').iter('Label'):
            if l.findtext('ObjectName') == 'MixpiSettingLabel':
                self.assertIsNone(l.find('Elide'))
                self.assertEqual(size(l)[1], 34)  # two 13 px lines
        hint = next(l.findtext('Text') for l in self.model.one('MixpiFxSwitch').iter('Label'))
        self.assertEqual(hint, 'Starlight FX pads: 1-3 effects · 4 send to deck')

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
        rows = self.rows()
        self.assertEqual(len(rows), 2)
        for channel, row in enumerate(rows, 1):
            names = lambda state: [b.findtext('State/Text') for b in row.iter('PushButton')
                                   if self.model.tappable(b, state)]
            for page in ('overview', 'fx', 'sampler'):
                self.assertEqual(names({f'[Tab],{page}': 1}), ['KEY', 'Q', 'SYNC', 'LOOP', 'CUE', '▶'], page)
            self.assertEqual(names({'[Tab],library': 1}), [f'LOAD {channel}', 'CUE'])
            # Decks widths (plan R-16): KEY 48, Q 48, SYNC 60, LOOP 60, CUE 76, ▶ the rest.
            fixed = [size(b)[0] for b in row.iter('PushButton')
                     if self.model.tappable(b, {'[Tab],overview': 1}) and size(b)[2] == 'f']
            self.assertEqual(fixed, [48, 48, 60, 60, 76])
            self.assertLessEqual(sum(fixed), 400)
            self.assertEqual(row.findtext('Size'), '400me,56f')

    def test_six_pixel_corners_only_override_owned_buttons(self):
        style = (self.skin/'style.qss').read_text()
        override = style.split('/* MixPi native navigation */', 1)[1]
        self.assertIn('border-radius: 6px;', override)
        for selector in ('#MixpiButton', '#MixpiPlay', '#MixpiRecord', '#MixpiUsbChip',
                         '#LibraryWrapper #LibrarySourcesButton'):
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
                      if c.find('BindProperty') is None and c.findtext('ConnectValueFromWidget', 'true') == 'true']
            if not writes:
                continue  # display-only chip: a tap writes nothing
            if len(writes) != 1 or writes[0].split(',', 1)[1] not in self.REAL_TOGGLES:
                offenders.append((b.findtext('State/Text'), writes))
        return offenders

    # ---------- R-16 deck page ----------

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

    def test_paired_keys_are_display_only_opt_in(self):
        for key in self.root.findall('.//Key'):
            self.assertEqual(key.findtext('PairedNotation'), 'true')
            self.assertEqual(key.findtext('Connection/ConnectValueFromWidget'), 'false')
        patch = (FILES / 'mixxx-performance-settings.patch').read_text()
        self.assertIn('context.selectBool(node, "PairedNotation", false)', patch)
        self.assertIn('KeyUtils::KeyNotation::LancelotAndTraditional', patch)

    def test_fx_route_disables_others_before_enabling_selected(self):
        units = [g for g in self.root.iter('WidgetGroup') if g.findtext('ObjectName') == 'MixpiFxUnit']
        for unit, group in enumerate(units, 1):
            rack = f'[EffectRack1_EffectUnit{unit}]'
            buttons = [b for b in group.iter('PushButton') if 'group_[' in b.findtext('Connection/ConfigKey')]
            texts = [b.findtext('State/Text') for b in buttons]
            own = ['DECK 1', 'DECK 2'][unit - 1]
            self.assertEqual(texts, [t + (' · PAD 4' if t == own else '') for t in ('DECK 1', 'DECK 2', 'MASTER')])
            for b, route in zip(buttons, ('[Channel1]', '[Channel2]', '[Master]')):
                writes = self.model.writes(b)
                self.assertEqual(len(writes), 3)
                self.assertEqual(writes[-1], (f'{rack},group_{route}_enable', 1))
                self.assertTrue(all(v == 0 for _, v in writes[:2]))
                self.assertTrue(all(c.findtext('ConnectValueToWidget') == 'false' for c in b.findall('Connection')
                                    if c.findtext('ConnectValueFromWidget') == 'true'))

    # ---------- R-18 settings ----------

    def test_transport_and_tabs_have_real_controls_and_touch_sizes(self):
        for row in self.rows():
            for b in row.iter('PushButton'):
                self.assertEqual(size(b)[1], 48)
        self.assertTrue(all(b.findtext('LeftClickIsPushButton') == 'true' for b in self.tabs()))
        self.assertFalse(any('safe_to_remove' in (c.text or '').lower()
                             for c in self.root.findall('.//ConfigKey')))

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

    def test_deck_readouts_fit_one_time_string_in_a_deck_half(self):
        # Owner decision 1: one time (elapsed, tap for remaining). On the Pi at
        # 21 px, "-14:41.23" is 88 px wide and "125.50" fits the 100 px BPM cell.
        stats = [g for g in self.root.findall('.//WidgetGroup')
                 if g.findtext('ObjectName') == 'MixpiDeckStats']
        self.assertEqual(len(stats), 6)  # Decks, FX and Sampler, both decks
        for group in stats:
            self.assertEqual(group.findtext('Size'), '0me,48f')
            children = list(group.find('Children'))
            self.assertEqual([c.findtext('ObjectName') for c in children],
                             ['MixpiTimeCell', 'MixpiBpm', 'MixpiRate', 'MixpiKey'])
            self.assertEqual([size(c)[0] for c in children], [120, 100, 60, 120])
            time = next(group.iter('NumberPos'))
            self.assertEqual(time.findtext('NumberOfDigits'), '6')
            captions = {l.findtext('Text'): l for l in group.iter('Label')}
            for mode, shown in ((0, 'ELAPSED · TAP'), (1, 'REMAINING · TAP'), (2, 'ELAPSED · TAP')):
                state = dict(self.PAGES_ON, **{'[Controls],ShowDurationRemaining': mode})
                self.assertEqual([t for t, l in captions.items() if self.model.visible(l, state)], [shown])
        for info in (g for g in self.root.iter('WidgetGroup') if g.findtext('ObjectName') == 'MixpiDeckInfo'):
            self.assertIn(size(info)[1], (28, 72))
        style = (self.skin/'style.qss').read_text()
        self.assertIn('#MixpiTime, #MixpiRate, #MixpiKey { color: #f4f6fa; font-size: 21px; }', style)

    # ---------- R-17 FX ----------

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
        for channel, row in enumerate(self.rows(), 1):
            key = f'[Channel{channel}]'
            load = next(b for b in row.iter('PushButton') if b.findtext('State/Text') == f'LOAD {channel}')
            self.assertEqual(load.findtext('Size'), '104f,48f')
            command, enabled, visible = load.findall('Connection')
            self.assertEqual(command.findtext('ConfigKey'), f'{key},LoadSelectedTrack')
            self.assertEqual(command.findtext('EmitOnPressAndRelease'), 'true')
            self.assertEqual(load.findtext('LeftClickIsPushButton'), 'true')
            self.assertEqual((enabled.findtext('ConfigKey'), enabled.findtext('BindProperty')),
                             (f'{key},play', 'enabled'))
            self.assertIsNotNone(enabled.find('Transform/Not'))
            self.assertEqual((visible.findtext('ConfigKey'), visible.findtext('BindProperty')),
                             ('[Tab],library', 'visible'))
            # The deck title beside LOAD, inside the 230 px cell (plan 4.2).
            cell = next(g for g in row.iter('WidgetGroup') if g.findtext('ObjectName') == 'MixpiLoadCell')
            self.assertEqual(104 + size(cell)[0], 230)
            title = next(cell.iter('TrackProperty'))
            self.assertEqual((title.findtext('Channel'), title.findtext('Property')), (str(channel), 'title'))
            for play in (0, 1):
                state = {'[Tab],library': 1, f'{key},play': play}
                self.assertEqual(self.model.visible(title, state), not play)
                self.assertEqual(self.model.enabled(load, state), not play)
            cues = [b for b in row.iter('PushButton') if b.findtext('State/Text') == 'CUE']
            self.assertEqual(len(cues), 2)
            for cue in cues:
                self.assertEqual(self.model.writes(cue), [(f'{key},cue_default', 1)])
                self.assertEqual(self.model.writes(cue, 'release'), [(f'{key},cue_default', 0)])
            play = next(b for b in row.iter('PushButton') if b.findtext('State/Text') == '▶')
            self.assertEqual(play.findtext('Connection/ConfigKey'), f'{key},play')
            self.assertFalse(self.model.visible(play, {'[Tab],library': 1}))
        keys = [k.text or '' for k in self.root.findall('.//ConfigKey')]
        self.assertFalse(any('LoadSelectedTrackAndPlay' in key for key in keys))

    def test_loop_quick_controls_keep_decks_navigation_and_sampler_reset(self):
        for channel, row in enumerate(self.rows(), 1):
            loops = [b for b in row.iter('PushButton') if b.findtext('State/Text') == 'LOOP']
            self.assertEqual(len(loops), 2)
            for b in loops:
                self.assertEqual(b.findtext('LeftClickIsPushButton'), 'true')
                self.assertEqual(self.model.writes(b), [('[MixPi],loop_deck', channel), ('[Tab],overview', 1),
                                                        ('[MixPi],sample_load', 0)])
            # Lit while the panel is open, and in the deck colour while a loop plays.
            for state, lit in (({'[MixPi],loop_deck': channel}, '[MixPi],loop_deck'),
                               ({f'[Channel{channel}],loop_enabled': 1}, f'[Channel{channel}],loop_enabled')):
                state['[Tab],overview'] = 1
                top = [b for b in loops if self.model.tappable(b, state)]
                self.assertEqual(len(top), 1)
                display = [c for c in top[0].findall('Connection') if c.findtext('ConnectValueFromWidget') == 'false']
                self.assertEqual(display[-1].findtext('ConfigKey'), lit)
                self.assertEqual(transform(display[-1], 1.0 if lit.endswith('loop_enabled') else float(channel)), 1)

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
