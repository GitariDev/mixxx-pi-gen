"""Validate real control semantics and pinned waveform reuse in the owned pages.

Qt rendering/audio still require the separate Pi trial. These checks detect
misrouted controls, missing release events, and unsafe loop-toggle semantics.
"""
import copy
import importlib.util
import os
from pathlib import Path
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

class PerformanceSkinTests(unittest.TestCase):
    def test_library_body_opts_into_native_right_overlay(self):
        body = next(group for group in self.root.findall('.//WidgetGroup')
                    if group.findtext('ObjectName') == 'MixpiLibraryBody')
        self.assertEqual(body.findtext('Layout'), 'right-overlay')
        self.assertEqual([child.findtext('ObjectName') for child in body.find('Children')],
                         ['MixpiLibraryMain', 'SidebarWrapper'])
        self.assertEqual(body.find('Children')[1].findtext('Size'), '290f,0me')

    def test_media_actions_are_native_gated_and_separate_from_sampler(self):
        buttons = self.root.findall('.//PushButton')
        for name in ('media_load',):
            action = next(button for button in buttons
                          if button.findtext('Connection/ConfigKey') == f'[MixPi],{name}')
            gate = action.findall('Connection')[-1]
            self.assertEqual(gate.findtext('ConfigKey'), '[MixPi],media_available')
            self.assertEqual(gate.findtext('BindProperty'), 'enabled')
        self.assertFalse(any(button.findtext('Connection/ConfigKey') == '[MixPi],media_eject'
                             for button in buttons))
        self.assertTrue(any(button.findtext('Connection/ConfigKey') == '[MixPi],sample_load'
                            for button in buttons))

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

    def test_sources_moves_inside_native_sidebar_above_back(self):
        library = ET.parse(self.skin/'library.xml').getroot()
        original = next(button for button in library.findall('.//PushButton')
                        if button.findtext('ObjectName') == 'LibrarySourcesButton')
        sidebar = next(group for group in self.root.findall('.//WidgetGroup')
                       if group.findtext('ObjectName') == 'SidebarWrapper')
        children = list(sidebar.find('Children'))
        self.assertEqual([child.findtext('ObjectName') for child in children[:3]],
                         ['LibrarySourcesButton', 'LibraryBackButton', 'LibrarySidebar'])
        self.assertEqual([[(item.tag, item.text) for item in connection]
                          for connection in children[0].findall('Connection')],
                         [[(item.tag, item.text) for item in connection]
                          for connection in original.findall('Connection')])
        self.assertEqual(children[1].findtext('Connection/ConfigKey'), '[Library],sidebar_back')
        self.assertEqual(children[1].findall('Connection')[1].findtext('ConfigKey'),
                         '[Library],sidebar_can_go_back')
        self.assertEqual(sidebar.findtext('Connection/ConfigKey'), '[Sidebar],sidebar_visible')
        self.assertEqual(sidebar.findtext('Connection/BindProperty'), 'visible')
        toolbar = next(group for group in self.root.findall('.//WidgetGroup')
                       if group.findtext('ObjectName') == 'MixpiLibraryToolbar')
        self.assertEqual([button.findtext('ObjectName') for button in toolbar.findall('Children/PushButton')],
                         ['LibraryActionsButton', 'SidebarButton'])
        toggle = toolbar.findall('Children/PushButton')[-1]
        self.assertEqual([state.findtext('Text') for state in toggle.findall('State')], ['Show', 'Hide'])
        self.assertEqual(toggle.findtext('Connection/ConfigKey'), '[Sidebar],sidebar_visible')

    def test_decks_label_and_quick_controls_are_tab_scoped(self):
        tabs = [button.findtext('State/Text') for button in self.root.findall('.//PushButton')
                if button.findtext('ObjectName') == 'MixpiTab']
        self.assertEqual(tabs, ['DECKS', 'TRACKS', 'FX', 'SAMPLER'])
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
            for button in buttons[4:]:
                self.assertFalse(any(connection.findtext('BindProperty') == 'visible'
                                     for connection in button.findall('Connection')))

    def test_two_pixel_corners_only_override_owned_buttons(self):
        style = (self.skin/'style.qss').read_text()
        override = style.split('/* MixPi native navigation */', 1)[1]
        self.assertIn('border-radius: 2px;', override)
        for selector in ('#MixpiButton', '#MixpiPlay', '#MixpiTab', '#MixpiRecord',
                         '#LibraryWrapper #LibrarySourcesButton', '#LibraryWrapper #LibraryBackButton'):
            self.assertIn(selector, override)
        self.assertNotIn('\nPushButton {', override)
        self.assertNotIn('\nQWidget {', override)

    def test_recording_four_states_preserve_independent_momentary_command(self):
        record = next(button for button in self.root.findall('.//PushButton')
                      if button.findtext('Connection/ConfigKey') ==
                      '[Recording],toggle_recording')
        self.assertEqual(record.findtext('ObjectName'), 'MixpiRecord')
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

    def test_two_state_buttons_without_push_mode_target_real_toggles(self):
        self.assertEqual(self.toggle_offenders(self.root), [])

    def test_guard_catches_a_toggle_on_a_plain_control(self):
        self.root.find('.//Children').append(SKIN.button('Back', '[MixPi],settings_advanced'))
        self.assertEqual(self.toggle_offenders(self.root),
                         [('Back', ['[MixPi],settings_advanced'])])

    def test_loop_intervals_retrigger_on_press_and_release(self):
        buttons=self.root.findall('.//PushButton')
        for ch in (1,2):
            for _,size in SKIN.LOOPS:
                key=f'[Channel{ch}],beatloop_{size}_activate'
                b=next(b for b in buttons if b.findtext('Connection/ConfigKey')==key)
                self.assertEqual(b.findtext('Connection/EmitOnPressAndRelease'),'true')
                self.assertEqual(b.findtext('LeftClickIsPushButton'),'true')
                self.assertEqual(b.findall('Connection')[1].findtext('ConfigKey'),
                                 f'[Channel{ch}],beatloop_{size}_enabled')
            exitb=next(b for b in buttons if b.findtext('Connection/ConfigKey')==f'[Channel{ch}],loop_exit')
            self.assertEqual(exitb.findtext('Connection/EmitOnPressAndRelease'),'true')
            reloop=next(b for b in buttons if b.findtext('Connection/ConfigKey')==f'[Channel{ch}],reloop_toggle')
            gate=reloop.findall('Connection')[-1]
            self.assertEqual(gate.findtext('BindProperty'),'enabled')
            self.assertIsNotNone(gate.find('Transform/Not'))

    def test_carryover_half_double_close_and_tab_cancel_preserve_commands(self):
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
        tabs = [button for button in self.root.findall('.//PushButton')
                if button.findtext('ObjectName') == 'MixpiTab']
        for tab in tabs:
            reset = {connection.findtext('ConfigKey'): connection
                     for connection in tab.findall('Connection')[1:]}
            for key in ('[MixPi],loop_deck', '[MixPi],sample_load'):
                self.assertIsNotNone(reset[key].find('Transform/Not'))
                self.assertEqual(reset[key].findtext('ConnectValueToWidget'), 'false')
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
            self.assertEqual(len(row.findall('Children/PushButton')),6)
            self.assertTrue(all(b.findtext('Size')=='0me,48f' for b in row.findall('Children/PushButton')))
        tabs=[b for b in self.root.findall('.//PushButton') if b.findtext('ObjectName')=='MixpiTab']
        self.assertEqual([b.findtext('State/Text') for b in tabs],['DECKS','TRACKS','FX','SAMPLER'])
        self.assertTrue(all(b.findtext('LeftClickIsPushButton')=='true' for b in tabs))
        self.assertFalse(any('safe_to_remove' in (c.text or '').lower()
                             for c in self.root.findall('.//ConfigKey')))
        self.assertEqual(len(self.root.findall('.//EffectSelector')),3)

    def test_focus_reuses_real_waveforms_outside_loop_panel(self):
        groups = self.root.findall('.//WidgetGroup')
        focused = [group for group in groups if group.findtext('ObjectName') == 'MixpiFocusedOverview']
        self.assertEqual(len(focused), 2)
        for channel, group in enumerate(focused, 1):
            self.assertEqual(group.findtext('Size'), '0me,52f')
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

    def test_sampler_load_browser_destinations_and_explicit_stop(self):
        attributes = {attribute.get('config_key'): attribute.text
                      for attribute in self.root.findall('manifest/attributes/attribute')}
        self.assertEqual(attributes['[Master],num_samplers'], '4')
        self.assertEqual(attributes['[MixPi],sample_load'], '0')
        buttons = self.root.findall('.//PushButton')
        load = next(button for button in buttons if button.findtext('State/Text') == 'LOAD SAMPLE')
        self.assertEqual([connection.findtext('ConfigKey') for connection in load.findall('Connection')],
                         ['[MixPi],sample_load', '[Tab],library'])
        for sampler in range(1, 5):
            destination = next(button for button in buttons
                               if button.findtext('Connection/ConfigKey') == f'[Sampler{sampler}],LoadSelectedTrack')
            self.assertEqual(destination.findtext('Connection/EmitOnPressAndRelease'), 'true')
            guard = destination.findall('Connection')[-1]
            self.assertEqual(guard.findtext('ConfigKey'), f'[Sampler{sampler}],play')
            self.assertEqual(guard.findtext('BindProperty'), 'enabled')
            self.assertIsNotNone(guard.find('Transform/Not'))
            self.assertTrue(any(button.findtext('Connection/ConfigKey') == f'[Sampler{sampler}],stop'
                                for button in buttons))
        self.assertFalse(any('LoadSelectedTrackAndPlay' in (key.text or '')
                             for key in self.root.findall('.//ConfigKey')))
        self.assertEqual(len(self.root.findall('.//Library')), 1)

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
        settings = next(button for button in self.root.findall('.//PushButton')
                        if button.findtext('State/Text') == 'SETTINGS')
        guard = next(connection for connection in settings.findall('Connection')
                     if connection.findtext('BindProperty') == 'enabled')
        self.assertEqual(guard.findtext('ConfigKey'), '[MixPi],settings_available')
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
