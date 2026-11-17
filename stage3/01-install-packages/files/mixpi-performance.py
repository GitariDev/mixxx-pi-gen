#!/usr/bin/env python3
"""Build the repo-owned performance pages on the patched, pinned Pioneered base.

Keeps the upstream Visual/Overview definitions, icons, and original templates.
Only skin XML and styles are changed; audio, waveform FPS and user data are not.
Apply pioneered-touch.py first. The first skin.xml is kept for rollback.
"""
import argparse
import copy
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET

BEGIN = '/* MixPi performance BEGIN */'
END = '/* MixPi performance END */'
# Redesign radius 6 (UI-REDESIGN-PLAN R-1 step 5, spec section 10). It
# replaces the 2 px corners of the field-fix round.
NAVIGATION_STYLE = '''/* MixPi native navigation */
#MixpiButton, #MixpiPlay, #MixpiRecord, #MixpiUsbChip, #MixpiPrimary,
#LibraryWrapper #LibraryActionsButton, #LibraryWrapper #SidebarButton,
#LibraryWrapper #LibrarySourcesButton, #LibraryWrapper #LibraryBackButton {
    border-radius: 6px;
}
'''
# [MixPi],screen (plan 4.1): which full-screen view is open. Skin-only, not saved.
SCREEN = '[MixPi],screen'
SCREEN_NONE, SCREEN_SOURCES, SCREEN_MEDIA, SCREEN_LOAD_SAMPLE, SCREEN_CHOOSE_PAD, SCREEN_SETTINGS = range(6)
SAMPLERS = 8
# Every tab, ✕ and opener resets these view states (and then sets its own).
VIEW_RESETS = ('[MixPi],loop_deck', '[MixPi],sample_load', SCREEN,
               '[MixPi],sample_pad', '[Sidebar],sidebar_visible')
# Fixed sizes (plan 5.3 and PROTO rdTop/rdSampler/rdSampleBrowser).
TOPBAR = [('DECKS', 'overview', 84), ('TRACKS', 'library', 84),
          ('FX', 'fx', 72), ('SAMPLER', 'sampler', 96)]
TOP_HEIGHT, OVERVIEW_HEIGHT, TRANSPORT_HEIGHT = 48, 48, 56
USB_CHIP, REC_WIDTH, GEAR, CPU_WIDTH = 150, 72, 48, 56
TOP_GAPS = (11, 8, 3)
PAD_SIZE, PAD_TAP, PAD_STRIP = (200, 104), 56, 48
SAMPLER_INFO = 72
# Icons the generator writes into the skin (R-11): 24 px glyphs from the
# prototype, centred in 48 px buttons, drawn unscaled (FIXED) by WPushButton.
ICON_STROKE = 'fill="none" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"'
ICONS = {
    'mixpi-icon-menu.svg': (48, 48, '#eef2f7', '<path d="M4 7h16M4 12h16M4 17h16"/>'),
    'mixpi-icon-close.svg': (48, 48, '#b5e15c', '<path d="M6 6l12 12M18 6 6 18"/>'),
    'mixpi-icon-close-plain.svg': (48, 48, '#eef2f7', '<path d="M6 6l12 12M18 6 6 18"/>'),
    'mixpi-icon-pen.svg': (48, 48, '#eef2f7',
        '<path d="M4 20h4L19.4 8.6a2.1 2.1 0 0 0-3-3L5 17v3z"/><path d="M14.6 7.4l2 2"/>'),
    'mixpi-icon-gear.svg': (48, 48, '#eef2f7',
        '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08'
        'a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74'
        'l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 '
        '1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08'
        'a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74'
        'l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25'
        'a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>'),
    # The chip's text is drawn centred by the button; the icon sits left of it.
    'mixpi-icon-usb.svg': (USB_CHIP, 48, '#43d17a',
        '<circle cx="12" cy="19.5" r="2"/><path d="M12 17.5V3.5M9.5 6 12 3.5 14.5 6M12 14.5 7.5 12V9.2'
        'M12 12.6l4.5-2.6V8"/><rect x="15" y="5.6" width="3" height="2.4" rx=".4"/>'
        '<circle cx="7.5" cy="8" r="1.2"/>'),
}
ICON_OFFSET = {'mixpi-icon-usb.svg': (36, 12)}
# One time string (elapsed or remaining, PositionDisplay 0/1) plus the full
# BPM, rate and paired key fit a 400 px deck half (F-5, owner decision 1).
DECK_STAT_WIDTHS = {'time': 120, 'bpm': 100, 'rate': 60, 'key': 120}
WAVE_INFO_SIZE = '100f,0me'
WAVE_KEY_SIZE = '92f,36f'
LOOPS = [('1/32', '0.03125'), ('1/16', '0.0625'), ('1/8', '0.125'),
         ('1/4', '0.25'), ('1/2', '0.5'), ('1', '1'), ('2', '2'), ('4', '4'),
         ('8', '8'), ('16', '16'), ('32', '32'), ('64', '64')]


def node(tag, text=None, **attrs):
    e = ET.Element(tag, attrs)
    e.text = text
    return e


def prop(e, tag, text):
    e.append(node(tag, str(text)))
    return e


def group(name, layout='vertical', size='0me,0me', children=()):
    e = node('WidgetGroup')
    prop(e, 'ObjectName', name)
    prop(e, 'Layout', layout)
    prop(e, 'Size', size)
    c = ET.SubElement(e, 'Children')
    c.extend(children)
    return e


def add(e, *items):
    e.find('Children').extend(items)
    return e


def connection(e, key, *, read=True, write=True, momentary=False,
               transform=None, bind=None):
    c = ET.SubElement(e, 'Connection')
    prop(c, 'ConfigKey', key)
    if bind:
        prop(c, 'BindProperty', bind)
    else:
        prop(c, 'ConnectValueFromWidget', str(write).lower())
        prop(c, 'ConnectValueToWidget', str(read).lower())
        if write:
            prop(c, 'EmitOnPressAndRelease' if momentary else 'EmitOnDownPress', 'true')
    if transform:
        c.append(ET.fromstring('<Transform>' + transform + '</Transform>'))
    return c


def write(e, key, value, when='press'):
    """A write-only connection that sets KEY to VALUE.

    A push button emits 1 on press and 0 on release; the inverse transform
    maps that to VALUE. 'release' writes after the press-and-release commands
    of the same button, while the button is still on screen.
    """
    emitted = 1 if when == 'press' else 0
    if value == emitted:
        transform = None
    elif value in (0, 1):
        transform = '<Not/>'
    elif when == 'press':
        transform = f'<IsEqual>{value}</IsEqual>'
    else:
        transform = f'<IsEqual>{value}</IsEqual><Not/>'
    c = connection(e, key, read=False, transform=transform)
    if when != 'press':
        c.find('EmitOnDownPress').text = 'false'
    return c


def show_when(e, key, value=None, negate=False, prop_name='visible', transform=None):
    """Bind a property to KEY (== VALUE, optionally negated)."""
    if transform is None:
        transform = (f'<IsEqual>{value}</IsEqual>' if value is not None else '') + \
                    ('<Not/>' if negate else '')
    connection(e, key, transform=transform or None, bind=prop_name)
    return e


# Two visible bindings on one widget do not combine; a condition list is
# applied as nested groups, innermost on the widget itself.
SCREEN_AT_MOST_1 = '<Add>-1.5</Add><Invert/>'
SCREEN_AT_LEAST_3 = '<Add>-2.5</Add>'
SCREEN_AT_MOST_4 = '<Add>-4.5</Add><Invert/>'


def when_all(widget, size, *conditions):
    """Visible only while every (key, transform) condition is above 0."""
    key, transform = conditions[0]
    show_when(widget, key, transform=transform)
    for key, transform in conditions[1:]:
        widget = show_when(group('MixpiWhen', size=size, children=[widget]), key,
                           transform=transform)
    return widget


def on_screen(value):
    return (SCREEN, f'<IsEqual>{value}</IsEqual>')


def off_screen(value):
    return (SCREEN, f'<IsEqual>{value}</IsEqual><Not/>')


SAMPLE_SCREENS = ((SCREEN, SCREEN_AT_MOST_4), (SCREEN, SCREEN_AT_LEAST_3))


def reset_views(e, keep=(), when='press'):
    for key in VIEW_RESETS:
        if key not in keep:
            write(e, key, 0, when)
    return e


def icon_states(e, *icons):
    """Replace a button's states with icon-only states (no text)."""
    for state in e.findall('State'):
        e.remove(state)
    number = e.find('NumberStates')
    number.text = str(len(icons))
    at = list(e).index(number) + 1
    for index, icon in enumerate(icons):
        st = node('State')
        prop(st, 'Number', index)
        for tag in ('Unpressed', 'Pressed'):
            st.append(node(tag, icon, scalemode='FIXED'))
        e.insert(at + index, st)
    return e


def gap(size, name='MixpiGap'):
    return group(name, 'horizontal', size)


def button(text, key, *, size='0me,48f', momentary=False,
           display=None, transform=None, push=False, name='MixpiButton', state_labels=None):
    e = node('PushButton')
    prop(e, 'ObjectName', name)
    prop(e, 'Size', size)
    labels = (text, text) if state_labels is None else state_labels
    prop(e, 'NumberStates', len(labels))
    if momentary or push:
        prop(e, 'LeftClickIsPushButton', 'true')
    for state, state_text in enumerate(labels):
        st = ET.SubElement(e, 'State')
        prop(st, 'Number', state)
        prop(st, 'Text', state_text)
    connection(e, key, read=display is None, momentary=momentary, transform=transform)
    if display:
        connection(e, display, write=False)
    return e


def label(text, size='0me,0me', name='MixpiLabel', align=None, elide=None):
    e = node('Label')
    prop(e, 'Text', text)
    prop(e, 'ObjectName', name)
    prop(e, 'Size', size)
    if align:
        prop(e, 'Alignment', align)
    if elide:
        prop(e, 'Elide', elide)
    return e


def typed(tag, channel, size, name, **props):
    e = node(tag)
    for key, value in dict(ObjectName=name, Channel=channel, Size=size, **props).items():
        prop(e, key, value)
    return e


def concrete(template, channel):
    e = copy.deepcopy(template)
    for parent in e.iter():
        for child in list(parent):
            if child.tag == 'Variable':
                if child.get('name') != 'channel':
                    raise ValueError('Unexpected variable in pinned waveform')
                index = list(parent).index(child)
                text = str(channel) + (child.tail or '')
                if index:
                    previous = parent[index - 1]
                    previous.tail = (previous.tail or '') + text
                else:
                    parent.text = (parent.text or '') + text
                parent.remove(child)
    return e


def fixed_size(e, value):
    for c in list(e):
        if c.tag in ('Size', 'SizePolicy', 'MinimumSize', 'MaximumSize'):
            e.remove(c)
    prop(e, 'Size', value)
    return e


def deck_info(channel, compact=False, title_height=28, stats_height=54):
    title = typed('TrackProperty', channel, f'0me,{title_height}f', 'MixpiDeckTitle',
                  Property='title', Elide='right', TooltipId='track_title')
    head = group('MixpiTitleStrip', 'horizontal', f'0me,{title_height}f',
                 [label(str(channel), f'28f,{title_height}f', f'MixpiDeckNumber{channel}'), title])
    height = title_height + (0 if compact else stats_height)
    info = group('MixpiDeckInfo', size=f'400me,{height}f', children=[head])
    if not compact:
        widths = DECK_STAT_WIDTHS
        h = stats_height
        stats = group('MixpiDeckStats', 'horizontal', f'0me,{h}f', [
            typed('NumberPos', channel, f"{widths['time']}me,{h}f", 'MixpiTime', NumberOfDigits=6),
            typed('NumberBpm', channel, f"{widths['bpm']}me,{h}f", 'MixpiBpm'),
            typed('NumberRate', channel, f"{widths['rate']}me,{h}f", 'MixpiRate', NumberOfDigits=1),
        ])
        connection(stats.find('Children/NumberBpm'), f'[Channel{channel}],visual_bpm', write=False)
        key = typed('Key', channel, f"{widths['key']}me,{h}f", 'MixpiKey', PairedNotation='true')
        connection(key, f'[Channel{channel}],visual_key', write=False)
        add(stats, key)
        add(info, stats)
    return info


def decks(compact=False, title_height=28, stats_height=54, size=None):
    height = title_height + (0 if compact else stats_height)
    return group('MixpiDecks', 'horizontal', size or f'0me,{height}f',
                 [deck_info(1, compact, title_height, stats_height),
                  deck_info(2, compact, title_height, stats_height)])


def loops(channel, loop_display='focus'):
    key = f'[Channel{channel}]'
    close = button('Close', '[MixPi],loop_deck', size='100f,48f',
                   transform='<Not/>', push=True)
    # Closing only writes zero; it does not mirror the selected deck into its state.
    close.find('Connection/ConnectValueToWidget').text = 'false'
    heading = f'DECK {channel}  •  LOOP'
    if loop_display == 'focus':
        heading += '  •  WAVEFORM BELOW'
    panel = group('MixpiLoopPanel', children=[group('MixpiLoopHeader', 'horizontal',
                  '0me,48f', [label(heading), close])])
    for offset in (0, 6):
        row = group('MixpiLoopRow', 'horizontal', '0me,48f')
        for text, value in LOOPS[offset:offset+6]:
            add(row, button(text, f'{key},beatloop_{value}_activate', momentary=True,
                            display=f'{key},beatloop_{value}_enabled'))
        add(panel, row)
    add(panel, group('MixpiLoopTools', 'horizontal', '0me,48f', [
        button('½', f'{key},loop_halve', momentary=True),
        button('×2', f'{key},loop_double', momentary=True),
        button('Exit', f'{key},loop_exit', momentary=True,
               display=f'{key},loop_enabled'),
        button('Reloop', f'{key},reloop_toggle', momentary=True,
               display=f'{key},loop_enabled'),
    ]))
    # Reloop jumps back to the saved loop. Disable it while already looping,
    # so a second tap cannot turn looping off (Exit has its own command).
    reloop = panel.find('Children')[-1].find('Children')[3]
    connection(reloop, f'{key},loop_enabled', transform='<Not/>', bind='enabled')
    connection(panel, '[MixPi],loop_deck', transform=f'<IsEqual>{channel}</IsEqual>', bind='visible')
    return panel


def slider(key, name='MixpiDepth', size='0me,48f'):
    e = node('SliderComposed')
    for k, v in dict(ObjectName=name, Size=size, Horizontal='true',
                     Handle='mixpi-slider-handle.svg', BarColor='#67b9ff', BarWidth=8).items():
        prop(e, k, v)
    connection(e, key)
    return e


def fx():
    rack = '[EffectRack1_EffectUnit1]'
    header = group('MixpiFxHeader', 'horizontal', '0me,76f')
    routes = ['[Channel1]', '[Channel2]', '[Master]']
    for route, text in zip(routes, ['DECK 1', 'DECK 2', 'MASTER']):
        key = f'{rack},group_{route}_enable'
        b = button(text, key, size='110me,48f', push=True, display=key)
        # Disable other routes before enabling this one. Touch selection is
        # exclusive without changing per-effect depth or enable controls.
        first = b.find('Connection')
        b.remove(first)
        for other in routes:
            if other != route:
                connection(b, f'{rack},group_{other}_enable', read=False, transform='<Not/>')
        b.append(first)
        add(header, b)
    add(header, group('MixpiFxMix', 'horizontal', '290f,64f', [
        label('MIX', '48f,48f'), slider(f'{rack},mix', size='210me,48f')]))
    cards = group('MixpiFxCards', 'horizontal')
    for slot in range(1, 4):
        effect = f'[EffectRack1_EffectUnit1_Effect{slot}]'
        select = node('EffectSelector')
        for k, v in dict(ObjectName='MixpiEffectSelector', EffectRack=1,
                         EffectUnit=1, Effect=slot, Elide='right', Size='0me,48f').items():
            prop(select, k, v)
        add(cards, group('MixpiFxCard', children=[select,
            slider(f'{effect},meta'), button('ON / OFF', f'{effect},enabled')]))
    return group('MixpiFx', children=[header, cards])


def preset(text, key, value, size='0me,48f'):
    b = button(text, key, push=True, size=size,
               transform=f'<IsEqual>{value}</IsEqual>' if value else '<Not/>')
    b.find('Connection/ConnectValueToWidget').text = 'false'
    connection(b, key, write=False, transform=f'<IsEqual>{value}</IsEqual>')
    return b


def preferences_button():
    # The patched Mixxx opens its Preferences dialog, queued, on a request above 0.
    b = button('Mixxx preferences…', '[MixPi],show_preferences', push=True)
    b.find('Connection/ConnectValueToWidget').text = 'false'
    return b


def settings():
    def choices(title, key, items):
        return group('MixpiSetting', 'horizontal', '0me,48f',
                     [label(title, '90f,48f', 'MixpiSettingLabel')] +
                     [preset(text, key, value) for text, value in items])
    engine = choices('KEYLOCK', '[MixPi],keylock_engine',
                     [('ST',0),('RB Fast',1),('RB Fine',2)])
    fps = choices('FPS', '[MixPi],waveform_fps', [('30',30),('45',45),('60',60)])
    tempo_select = node('ComboBox')
    for name, value in dict(ObjectName='MixpiSettingSelector', Size='0me,48f').items():
        prop(tempo_select, name, value)
    for index, text in enumerate(['Custom'] + [f'{value}%' for value in (4,6,8,10,16,24,50,90)]):
        state = ET.SubElement(tempo_select, 'State')
        prop(state, 'Number', index)
        prop(state, 'Text', text)
    connection(tempo_select, '[MixPi],tempo_range_index')
    tempo = group('MixpiSetting', 'horizontal', '0me,48f', [
        label('TEMPO ±', '90f,48f', 'MixpiSettingLabel'), tempo_select])
    toggles = group('MixpiSetting', 'horizontal', '0me,48f', [
        button('Q 1','[Channel1],quantize'), button('Q 2','[Channel2],quantize'),
        button('SPLIT CUE','[Master],headSplit')])
    buffers = choices('BUFFER', '[MixPi],buffer_frames', [('256',256),('512',512),('1024',1024)])
    for b in buffers.findall('Children/PushButton'):
        connection(b, '[MixPi],buffer_available', bind='enabled')
    cache = choices('CACHE MB*', '[MixPi],cache_mb', [('OFF',0),('512',512),('1024',1024)])
    ahead = choices('READ AHEAD*', '[MixPi],read_ahead', [('2',2),('8',8),('24',24)])
    bar = button('Top bar unavailable', '[MixPi],desktop_bar', push=True, name='MixpiDesktopBar',
                 state_labels=('Show top bar', 'Hide top bar', 'Checking top bar…',
                               'Top bar unavailable'))
    connection(bar, '[MixPi],desktop_bar_available', bind='enabled')
    playback = group('MixpiPlaybackSettings', children=[
        label('PLAYBACK', '0me,28f'), engine, buffers, tempo, toggles])
    interface = group('MixpiInterfaceSettings', children=[
        label('INTERFACE', '0me,28f'), bar,
        label('Desktop · Mixxx · Speaker', '0me,28f', 'MixpiSettingLabel'),
        label('Settings stays available to restore it.', '0me,28f', 'MixpiSettingLabel'),
        # Explicit set-value buttons: settings_advanced is a plain control, so a
        # two-state toggle would send 1 on every press and Back would do nothing.
        preset('Advanced…', '[MixPi],settings_advanced', 1)])
    basic = group('MixpiSettingsBasic', 'horizontal', children=[playback, interface])
    connection(basic, '[MixPi],settings_advanced', transform='<Not/>', bind='visible')
    advanced = group('MixpiSettingsAdvanced', children=[
        label('ADVANCED · DISPLAY / NEXT LAUNCH', '0me,28f'),
        group('MixpiSettingsRow', 'horizontal', '0me,48f', [fps, ahead]),
        group('MixpiSettingsRow', 'horizontal', '0me,48f', [cache,
            label('* Next launch', '0me,48f', 'MixpiSettingLabel')]),
        group('MixpiSettingsRow', 'horizontal', '0me,48f', [
            preset('Back', '[MixPi],settings_advanced', 0), preferences_button()])])
    connection(advanced, '[MixPi],settings_advanced', bind='visible')
    panel = group('MixpiSettings', 'stacked', children=[basic, advanced])
    connection(panel,'[MixPi],loop_deck',transform='<IsEqual>3</IsEqual>',bind='visible')
    return panel


def toolbar_parts(library):
    """The singular native library widgets, copied once each (plan section 2, row 6)."""
    toolbar = library.find('Children/WidgetGroup')
    parts = {e.findtext('ObjectName'): copy.deepcopy(e) for e in toolbar.find('Children')}
    sidebar = next(copy.deepcopy(e) for e in library.findall('.//WidgetGroup')
                   if e.findtext('ObjectName') == 'SidebarWrapper')
    back = next(e for e in sidebar.find('Children') if e.findtext('ObjectName') == 'LibraryBackButton')
    sidebar.find('Children').remove(back)
    parts['LibraryBackButton'] = back
    parts['SidebarWrapper'] = sidebar
    parts['Library'] = copy.deepcopy(library.find('.//Library'))
    return parts


def sample_hints():
    # One label per [MixPi],sample_pad value: 0 = pick a pad later.
    hints = group('MixpiSampleHint', 'horizontal', '0me,48f')
    for pad in range(SAMPLERS + 1):
        text = 'Pick a sound, then a pad' if pad == 0 else f'For pad {pad}'
        add(hints, show_when(label(text, '0me,48f', 'MixpiScreenHint', elide='right'),
                             '[MixPi],sample_pad', pad))
    return hints


def load_to_pad(sampler, size, name, text):
    """[SamplerN],LoadSelectedTrack on press and release, then back to the Sampler tab."""
    b = button(text, f'[Sampler{sampler}],LoadSelectedTrack', size=size, momentary=True, name=name)
    # A playing pad cannot take a new sound (the rule of the old LOAD TO row).
    connection(b, f'[Sampler{sampler}],play', transform='<Not/>', bind='enabled')
    write(b, '[Tab],sampler', 1, 'release')
    reset_views(b, when='release')
    return b


def browse_page(library):
    """Tracks (screen 0), Sources (1), Load sample (3) and Choose pad (4) share one
    Library, sidebar and search box. Only fixed-content layouts change."""
    parts = toolbar_parts(library)
    search, actions, sources = parts['SearchBox'], parts['LibraryActionsButton'], parts['LibrarySourcesButton']
    sidebar_button, back = parts['SidebarButton'], parts['LibraryBackButton']

    # ☰ / ✕ (R-11): the existing two-state key; open also writes screen 1.
    fixed_size(sidebar_button, '48f,48f')
    icon_states(sidebar_button, 'mixpi-icon-menu.svg', 'mixpi-icon-close.svg')
    connection(sidebar_button, SCREEN, read=False, transform=f'<IsEqual>{SCREEN_SOURCES}</IsEqual>')
    # ✎ (R-11): Actions keeps its key and object name; the native menu anchors under it.
    fixed_size(actions, '48f,48f')
    icon_states(actions, 'mixpi-icon-pen.svg', 'mixpi-icon-pen.svg')
    fixed_size(sources, '128f,48f')
    sources.find('State/Text').text = 'EDIT LIST'
    fixed_size(back, '96f,48f')
    back.find('State/Text').text = '‹ BACK'
    fixed_size(search, '250me,40f')

    # Sources opened from Load sample returns there.
    sample_sources_close = button('', '[Sidebar],sidebar_visible', size='48f,48f', push=True,
                                  name='MixpiIconButton', transform='<Not/>')
    sample_sources_close.find('Connection/ConnectValueToWidget').text = 'false'
    write(sample_sources_close, SCREEN, SCREEN_LOAD_SAMPLE)
    icon_states(sample_sources_close, 'mixpi-icon-close.svg', 'mixpi-icon-close.svg')
    load_close = button('', '[Tab],sampler', size='48f,48f', push=True, name='MixpiIconButton')
    load_close.find('Connection/ConnectValueToWidget').text = 'false'
    reset_views(load_close)
    icon_states(load_close, 'mixpi-icon-close-plain.svg', 'mixpi-icon-close-plain.svg')
    slot = group('MixpiHeaderSlot', 'stacked', '48f,48f', [
        when_all(sidebar_button, '48f,48f', ('[MixPi],sample_load', '<Not/>'),
                 (SCREEN, SCREEN_AT_MOST_1)),
        when_all(sample_sources_close, '48f,48f', ('[MixPi],sample_load', None),
                 on_screen(SCREEN_SOURCES)),
        when_all(load_close, '48f,48f', *SAMPLE_SCREENS)])

    crumb = show_when(label('', '220f,48f', 'MixpiTracksCrumb', elide='right'), SCREEN, SCREEN_NONE)
    sources_head = group('MixpiSourcesHead', 'horizontal', '0me,48f', [
        label('SOURCES', '120f,48f', 'MixpiScreenTitle'),
        show_when(label('Pick a source, then a list.', '0me,48f', 'MixpiScreenHint', elide='right'),
                  '[MixPi],sample_load', negate=True),
        show_when(label('Pick the list to load samples from.', '0me,48f', 'MixpiScreenHint',
                        elide='right'), '[MixPi],sample_load')])
    show_when(sources_head, SCREEN, SCREEN_SOURCES)
    load_head = when_all(group('MixpiLoadHead', 'horizontal', '380f,48f', [
        label('LOAD SAMPLE', '150f,48f', 'MixpiScreenTitle'), sample_hints()]),
        '380f,48f', *SAMPLE_SCREENS)
    header = group('MixpiBrowseHeader', 'horizontal', f'0me,{TOP_HEIGHT}f', [
        slot, crumb, sources_head, load_head,
        show_when(search, SCREEN, SCREEN_SOURCES, negate=True),
        show_when(actions, SCREEN, SCREEN_NONE),
        show_when(back, SCREEN, SCREEN_SOURCES),
        show_when(sources, SCREEN, SCREEN_SOURCES)])

    # Sources: the sidebar takes the whole area under the header (y 96-480).
    sidebar = parts['SidebarWrapper']
    fixed_size(sidebar, '0me,0me')
    sources_body = show_when(group('MixpiSourcesBody', children=[sidebar]), SCREEN, SCREEN_SOURCES)

    # Load sample: a row of sources, the list, and one LOAD TO PAD button.
    open_sources = button('SOURCES…', '[Sidebar],sidebar_visible', size='150f,48f', push=True)
    open_sources.find('Connection/ConnectValueToWidget').text = 'false'
    write(open_sources, SCREEN, SCREEN_SOURCES)
    source_row = group('MixpiSampleSources', 'horizontal', '0me,56f', [open_sources])
    # The native sample browser (wave 2) offers fixed places through
    # [MixPi],sample_source; the buttons stay hidden until it says it is there.
    for text, value in (('SAMPLES', 1), ('THIS PI', 2), ('RECORDINGS', 4)):
        add(source_row, show_when(preset(text, '[MixPi],sample_source', value, size='150f,48f'),
                                  '[MixPi],sample_source_available'))
    add(source_row, label('Shows the list picked in Sources.', '0me,48f', 'MixpiScreenHint',
                          elide='right'))
    source_row = when_all(source_row, '0me,56f', *SAMPLE_SCREENS)

    table = show_when(group('MixpiLibraryMain', children=[parts['Library']]),
                      SCREEN, SCREEN_SOURCES, negate=True)
    titles = show_when(decks(compact=True), SCREEN, SCREEN_NONE)
    titles.find('ObjectName').text = 'MixpiTrackTitles'

    choose = button('LOAD TO PAD…', SCREEN, size='250f,56f', push=True, name='MixpiPrimary',
                    transform=f'<IsEqual>{SCREEN_CHOOSE_PAD}</IsEqual>')
    choose.find('Connection/ConnectValueToWidget').text = 'false'
    targets = group('MixpiLoadTarget', 'horizontal', '250f,56f',
                    [show_when(choose, '[MixPi],sample_pad', 0)])
    for sampler in range(1, SAMPLERS + 1):
        add(targets, show_when(load_to_pad(sampler, '250f,56f', 'MixpiPrimary',
                                           f'LOAD TO PAD {sampler}'), '[MixPi],sample_pad', sampler))
    footer = when_all(group('MixpiSampleFooter', 'horizontal', '0me,64f', [
        label('Tap a sound, then load it to a pad.', '0me,64f', 'MixpiScreenHint', elide='right'),
        targets, gap('8f,64f')]), '0me,64f', *SAMPLE_SCREENS)

    wrapper = group('LibraryWrapper', children=[header, sources_body, source_row, table, titles, footer])
    page = group('MixpiBrowse', 'stacked', children=[wrapper, choose_pad()])
    page.set('trigger', '[Tab],library')
    return page


def pad_tag(sampler, size='0me,24f'):
    deck = 'A' if sampler <= 4 else 'B'
    return group('MixpiPadTagRow', 'horizontal', size, [
        label(str(sampler), '24f,24f', f'MixpiPadBadge{deck}', align='center'),
        label(f'{deck}{(sampler - 1) % 4 + 1}', '40f,24f', 'MixpiPadTag')])


def sampler_title(sampler, size, name='MixpiSamplerTitle', prop_name='titleInfo'):
    title = node('TrackProperty')
    for k, v in dict(ObjectName=name, Group=f'[Sampler{sampler}]', Property=prop_name,
                     Elide='right', Size=size).items():
        prop(title, k, v)
    return title


def choose_pad():
    """Choose pad (screen 4): a sheet over the dimmed list, 8 tiles in the pad order."""
    tiles = []
    for sampler in range(1, SAMPLERS + 1):
        key = f'[Sampler{sampler}]'
        info = group('MixpiChooseInfo', size='165f,96f', children=[
            pad_tag(sampler),
            show_when(sampler_title(sampler, '0me,40f', 'MixpiChooseName'), f'{key},track_loaded'),
            show_when(label('Empty', '0me,40f', 'MixpiChooseEmpty'), f'{key},track_loaded', negate=True)])
        tile = load_to_pad(sampler, '165f,96f', 'MixpiChooseTile', '')
        tiles.append(group('MixpiChooseCell', 'stacked', '165f,96f', [info, tile]))
    rows = []
    for row in (tiles[:4], tiles[4:]):
        cells = [gap('18f,96f')]
        for index, tile in enumerate(row):
            cells += ([gap('8f,96f')] if index else []) + [tile]
        rows.append(group('MixpiChooseRow', 'horizontal', '0me,96f', cells + [gap('18f,96f')]))
    cancel = button('CANCEL', SCREEN, size='120f,48f', push=True,
                    transform=f'<IsEqual>{SCREEN_LOAD_SAMPLE}</IsEqual>')
    cancel.find('Connection/ConnectValueToWidget').text = 'false'
    sheet = group('MixpiChooseSheet', size='720f,340f', children=[
        gap('0me,16f'),
        group('MixpiChooseTitleRow', 'horizontal', '0me,48f', [
            gap('18f,48f'), label('Load to which pad?', '0me,48f', 'MixpiSheetTitle'),
            cancel, gap('18f,48f')]),
        gap('0me,12f'), rows[0], gap('0me,8f'), rows[1],
        group('MixpiChooseNoteRow', 'horizontal', '0me,44f', [
            gap('18f,44f'),
            label("Pads 1-4 play from the Starlight's deck A pads in SAMPLER mode, 5-8 from deck B. "
                  'A playing pad is off.', '0me,44f', 'MixpiScreenHint', elide='right'),
            gap('18f,44f')]),
        gap('0me,0me')])
    # Ignored height: the hidden sheet adds nothing to the page's minimum
    # (a stacked layout counts hidden children), so 800x444 still fits.
    scrim = group('MixpiChooseScrim', size='0me,0i', children=[
        gap('0me,4f'),
        group('MixpiChooseCenter', 'horizontal', '0me,340f', [gap('0me,340f'), sheet, gap('0me,340f')]),
        gap('0me,0me')])
    return show_when(scrim, SCREEN, SCREEN_CHOOSE_PAD)


def sampler_pad(sampler):
    """R-7: a 56 px tap area lit from play, a 48 px Stop/Clear strip; an empty pad opens Load sample."""
    key = f'[Sampler{sampler}]'
    width, height = PAD_SIZE
    info = group('MixpiPadInfo', size=f'{width}f,{PAD_TAP}f', children=[
        group('MixpiPadHead', 'horizontal', '0me,24f', [
            pad_tag(sampler, '0me,24f'),
            sampler_title(sampler, '56f,24f', 'MixpiPadTime', 'durationTextSeconds')]),
        sampler_title(sampler, '0me,32f', 'MixpiPadName')])
    trigger = button('', f'{key},cue_gotoandplay', size=f'{width}f,{PAD_TAP}f', momentary=True,
                     display=f'{key},play', name='MixpiPadTap')
    connection(trigger, f'{key},track_loaded', bind='enabled')
    stop = button('■ STOP', f'{key},stop', size=f'{width // 2}f,{PAD_STRIP}f', momentary=True)
    connection(stop, f'{key},play', bind='enabled')
    clear = button('× CLEAR', f'{key},eject', size=f'{width // 2}f,{PAD_STRIP}f', momentary=True)
    connection(clear, f'{key},play', transform='<Not/>', bind='enabled')
    loaded = group('MixpiPadLoaded', size=f'{width}f,{height}f', children=[
        group('MixpiPadTapArea', 'stacked', f'{width}f,{PAD_TAP}f', [info, trigger]),
        group('MixpiPadStrip', 'horizontal', f'{width}f,{PAD_STRIP}f', [stop, clear])])
    show_when(loaded, f'{key},track_loaded')
    open_load = button('', '[Tab],library', size=f'{width}f,{height}f', push=True, name='MixpiPadLoad')
    open_load.find('Connection/ConnectValueToWidget').text = 'false'
    reset_views(open_load, keep=('[MixPi],sample_load', '[MixPi],sample_pad', SCREEN))
    write(open_load, '[MixPi],sample_load', 1)
    write(open_load, '[MixPi],sample_pad', sampler)
    write(open_load, SCREEN, SCREEN_LOAD_SAMPLE)
    empty = group('MixpiPadEmpty', 'stacked', f'{width}f,{height}f', [
        group('MixpiPadInfo', size=f'{width}f,{height}f', children=[
            pad_tag(sampler), label('+  Empty · tap to load', '0me,32f', 'MixpiPadEmptyText'),
            gap('0me,0me')]),
        open_load])
    show_when(empty, f'{key},track_loaded', negate=True)
    return group(f'MixpiPad{"A" if sampler <= 4 else "B"}', size=f'{width}f,{height}f',
                 children=[loaded, empty])


def sampler_page():
    load = button('+  LOAD SAMPLE', '[Tab],library', size='190f,48f', push=True, name='MixpiPrimary')
    load.find('Connection/ConnectValueToWidget').text = 'false'
    reset_views(load, keep=('[MixPi],sample_load', SCREEN))
    write(load, '[MixPi],sample_load', 1)
    write(load, SCREEN, SCREEN_LOAD_SAMPLE)
    # R-13 pulses [MixPi],saved after each save; until then the note stays hidden.
    saved = show_when(label('Bank saved', '110f,48f', 'MixpiSavedNote', align='center'), '[MixPi],saved')
    header = group('MixpiSamplerHeader', 'horizontal', f'0me,{TOP_HEIGHT}f', [
        load, saved, gap('0me,48f'),
        label('Starlight SAMPLER mode: deck A pads 1-4 · deck B pads 5-8', '400f,48f',
              'MixpiScreenHint', align='right', elide='right')])
    rows = [group('MixpiPadRow', 'horizontal', f'0me,{PAD_SIZE[1]}f',
                  [sampler_pad(s) for s in range(first, first + 4)]) for first in (1, 5)]
    pads = group('MixpiPads', size=f'0me,{2 * PAD_SIZE[1]}f', children=rows)
    # Ignored height: below 480 px (desktop bar shown) the deck row gives way first.
    info = decks(title_height=24, stats_height=SAMPLER_INFO - 24, size='0me,0i')
    page = group('MixpiSampler', children=[header, pads, info])
    page.set('trigger', '[Tab],sampler')
    return page


def summary(channel, overview, visual, loop_display):
    strip = concrete(overview, channel)
    fixed_size(strip, f'0me,{OVERVIEW_HEIGHT}f')
    if loop_display == 'overlay':
        return strip
    focused = concrete(visual, channel)
    fixed_size(focused, f'0me,{OVERVIEW_HEIGHT}f')
    connection(focused, f'[Channel{channel}],track_loaded', bind='enabled')
    detail = group('MixpiFocusedOverview', 'horizontal', f'0me,{OVERVIEW_HEIGHT}f', [
        button('−', f'[Channel{channel}],waveform_zoom_up', size='48f,48f', momentary=True),
        focused,
        button('+', f'[Channel{channel}],waveform_zoom_down', size='48f,48f', momentary=True)])
    connection(detail, '[MixPi],loop_deck', transform=f'<IsEqual>{channel}</IsEqual>', bind='visible')
    connection(strip, '[MixPi],loop_deck',
               transform=f'<IsEqual>{channel}</IsEqual><Not/>', bind='visible')
    return group('MixpiSummary', 'stacked', f'400me,{OVERVIEW_HEIGHT}f', [strip, detail])


def tab(text, key, width):
    """A tab writes its page and closes every view (plan 4.1: every tab writes screen 0)."""
    b = button(text, f'[Tab],{key}', size=f'{width}f,48f', push=True, name='MixpiTab')
    return reset_views(b)


def tab_pair(text, key, width, state_key, state_value=None, twin_lit=False):
    """A tab and a twin in one place. The twin shows while STATE_KEY (== value)
    is set; it sends the same writes, and is lit only if TWIN_LIT."""
    normal, twin = tab(text, key, width), tab(text, key, width)
    twin.find('Connection/ConnectValueToWidget').text = 'false'
    if twin_lit:
        connection(twin, state_key, write=False,
                   transform=f'<IsEqual>{state_value}</IsEqual>' if state_value is not None else None)
    show_when(normal, state_key, state_value, negate=True)
    show_when(twin, state_key, state_value)
    return group('MixpiTabPair', 'stacked', f'{width}f,48f', [normal, twin])


def topbar():
    """R-1: the 48 px top bar in PROTO's order."""
    top = group('MixpiTopbar', 'horizontal', f'0me,{TOP_HEIGHT}f')
    for text, key, width in TOPBAR:
        if key == 'overview':
            # Settings is a view inside Decks ([Tab],overview stays 1). While it
            # is open, show a twin that never mirrors the tab state, so only
            # the gear is highlighted. Both send the same writes.
            add(top, tab_pair(text, key, width, '[MixPi],loop_deck', 3))
        elif key in ('library', 'sampler'):
            # Load sample, Choose pad and Sources opened from them live on the
            # Tracks page: SAMPLER stays lit there, TRACKS does not.
            add(top, tab_pair(text, key, width, '[MixPi],sample_load', twin_lit=key == 'sampler'))
        else:
            add(top, tab(text, key, width))
    # The USB chip opens today's media dialog (R-4 gives it states in wave 2).
    usb = button('     USB', '[MixPi],media_load', size=f'{USB_CHIP}f,48f', push=True, name='MixpiUsbChip')
    for state in usb.findall('State'):
        state.append(node('Unpressed', 'mixpi-icon-usb.svg', scalemode='FIXED'))
        state.append(node('Pressed', 'mixpi-icon-usb.svg', scalemode='FIXED'))
    connection(usb, '[MixPi],media_available', bind='enabled')
    # Wave 1: the gear keeps today's Settings view inside Decks (loop_deck 3).
    gear = button('', '[MixPi],loop_deck', size=f'{GEAR}f,48f', push=True, name='MixpiIconButton',
                  transform='<IsEqual>3</IsEqual>')
    icon_states(gear, 'mixpi-icon-gear.svg', 'mixpi-icon-gear.svg')
    connection(gear, '[MixPi],settings_available', bind='enabled')
    write(gear, '[Tab],overview', 1)
    reset_views(gear, keep=('[MixPi],loop_deck',))
    record = button('● REC', '[Recording],toggle_recording', size=f'{REC_WIDTH}f,48f', momentary=True,
                    display='[Recording],status', name='MixpiRecord',
                    state_labels=('● REC', 'WAIT', '■ STOP', '■ STOP'))
    # The gaps put the chip, REC and the gear on the plan's tap points
    # (x 527, 649, 717; plan 5.3) with the brief's widths.
    add(top, group('MixpiTopSpacer', 'horizontal'), usb, gap(f'{TOP_GAPS[0]}f,48f'), record,
        gap(f'{TOP_GAPS[1]}f,48f'), gear, gap(f'{TOP_GAPS[2]}f,48f'))
    cpu = node('Number')
    for k, v in dict(ObjectName='MixpiCpu', Size=f'{CPU_WIDTH}f,24f', Text='%1%', NumberOfDigits=0).items():
        prop(cpu, k, v)
    connection(cpu, '[MixPi],audio_load_percent', write=False)
    connection(cpu, '[MixPi],settings_available', bind='visible')
    unavailable = label('—', f'{CPU_WIDTH}f,24f')
    connection(unavailable, '[MixPi],settings_available', transform='<Not/>', bind='visible')
    cpu_label = label('CPU', f'{CPU_WIDTH}f,22f', 'MixpiCpuLabel')
    cpu_value = group('MixpiCpuValue', 'stacked', f'{CPU_WIDTH}f,24f', [cpu, unavailable])
    add(top, group('MixpiCpuBox', size=f'{CPU_WIDTH}f,48f', children=[cpu_label, cpu_value]))
    return top


def build(skin, loop_display='focus'):
    if loop_display not in ('focus', 'overlay'):
        raise ValueError('Unknown loop display mode')
    original = skin / '.mixpi-performance-original' / 'skin.xml'
    source = original.read_text() if original.exists() else (skin/'skin.xml').read_text()
    manifest = copy.deepcopy(ET.fromstring(source).find('manifest'))
    if manifest is None:
        raise ValueError('Missing Pioneered manifest')
    manifest.find('title').text = 'Pioneered • MixPi'
    manifest.find('description').text = 'MixPi performance pages on the pinned Pioneered waveform base'
    for attr in manifest.findall('attributes/attribute'):
        if attr.get('config_key') == '[Master],num_samplers':
            # The Starlight's SAMPLER mode plays pads 1-8 (plan section 2, row 1).
            attr.text = str(SAMPLERS)
    # These are skin-only view states. Do not persist an open overlay or startup tab.
    attrs = manifest.find('attributes')
    for key, value in [('[MixPi],loop_deck','0'), ('[Tab],overview','1'),
                       ('[Tab],library','0'), ('[Tab],fx','0'), ('[Tab],sampler','0'),
                       ('[MixPi],sample_load','0'), ('[Tab],current','0'),
                       (SCREEN, '0'), ('[MixPi],sample_pad', '0'),
                       ('[Sidebar],sidebar_visible', '0')]:
        a = ET.SubElement(attrs, 'attribute', {'config_key':key})
        a.text = value
    visual = ET.parse(skin/'waveform.xml').find('.//Visual')
    overview = ET.parse(skin/'deck.xml').find('.//Overview')
    library = ET.parse(skin/'library.xml').find('.//WidgetGroup/Children/WidgetGroup')
    if visual is None or overview is None or library is None or library.find('.//LibrarySidebar/TouchNavigation') is None:
        raise ValueError('Expected pinned waveforms and patched touch library')
    root = node('skin')
    root.append(manifest)
    prop(root,'ObjectName','Mixxx')
    root.append(node('Style', src='skin:style.qss'))
    prop(root,'MinimumSize','800,444')
    prop(root,'Layout','vertical')
    children = ET.SubElement(root,'Children')
    children.append(topbar())
    stack=node('WidgetStack',currentpage='[Tab],current')
    prop(stack,'Size','0me,0me')
    pages=ET.SubElement(stack,'Children')
    perform=group('MixpiPerform');perform.set('trigger','[Tab],overview')
    waves=group('MixpiWaveforms')
    for ch in (1,2):
        v=concrete(visual,ch);fixed_size(v,'0me,0me')
        # EOS width (F-4 A/B, 2026-11-16): the 100 px column gives a 700 px
        # waveform at the same CPU, frame rate and px per beat as 136 px.
        key=typed('Key',ch,WAVE_KEY_SIZE,'MixpiWaveKey',PairedNotation='true')
        connection(key,f'[Channel{ch}],visual_key',write=False)
        info=group('MixpiWaveInfo',size=WAVE_INFO_SIZE,children=[label(f'DECK {ch}'),key])
        add(waves,group('MixpiWaveRow','horizontal',children=[info,v]))
    visible = '<IsEqual>0</IsEqual>' if loop_display == 'focus' else '<IsEqual>3</IsEqual><Not/>'
    connection(waves, '[MixPi],loop_deck', transform=visible, bind='visible')
    connection(waves, '[MixPi],loop_deck', transform='<IsEqual>0</IsEqual>', bind='enabled')
    deck_details = decks()
    connection(deck_details, '[MixPi],loop_deck', transform='<IsEqual>3</IsEqual><Not/>', bind='visible')
    add(perform,group('MixpiWaveArea','stacked',children=[settings(),loops(1, loop_display),loops(2, loop_display),waves]),deck_details)
    pages.append(perform)
    pages.append(browse_page(library))
    fxpage=group('MixpiFxPage');fxpage.set('trigger','[Tab],fx')
    add(fxpage,fx());pages.append(fxpage)
    pages.append(sampler_page())
    children.append(stack)
    summaries=group('MixpiSummaries','horizontal',f'0me,{OVERVIEW_HEIGHT}f')
    transport=group('MixpiTransport','horizontal',f'0me,{TRANSPORT_HEIGHT}f')
    for ch in (1,2):
        add(summaries, summary(ch, overview, visual, loop_display))
        key=f'[Channel{ch}]'
        # Tracks shows LOAD and CUE; the other tabs keep CUE and ▶. LOAD sends
        # press and release like the sampler pads, and is off while the deck plays.
        load=button('LOAD',f'{key},LoadSelectedTrack',momentary=True)
        connection(load,f'{key},play',transform='<Not/>',bind='enabled')
        connection(load,'[Tab],library',bind='visible')
        play=button('▶',f'{key},play',name='MixpiPlay')
        connection(play,'[Tab],library',transform='<Not/>',bind='visible')
        row=group('MixpiDeckButtons','horizontal',f'0me,{TRANSPORT_HEIGHT}f',[
            button('KEY',f'{key},keylock'),button('Q',f'{key},quantize'),
            button('SYNC',f'{key},sync_enabled'),
            button('LOOP','[MixPi],loop_deck',transform=f'<IsEqual>{ch}</IsEqual>',push=True),
            load,button('CUE',f'{key},cue_default',momentary=True),play])
        for quick in row.findall('Children/PushButton')[:4]:
            connection(quick, '[Tab],overview', bind='visible')
        loop_button = row.findall('Children/PushButton')[3]
        connection(loop_button, '[Tab],overview', read=False, transform='<IsEqual>1</IsEqual>')
        connection(loop_button, '[MixPi],sample_load', read=False, transform='<Not/>')
        add(transport,row)
    # Overviews and transport show only while no full-screen view is open
    # (plan 4.1): no touch CUE or PLAY under Sources, Load sample or Choose pad.
    bottom = group('MixpiBottom', size=f'0me,{OVERVIEW_HEIGHT + TRANSPORT_HEIGHT}f',
                   children=[summaries, transport])
    children.append(show_when(bottom, SCREEN, SCREEN_NONE))
    ET.indent(root,space='  ')
    output=ET.tostring(root,encoding='unicode')+'\n'
    ET.fromstring(output)
    css=(skin/'style.qss').read_text()
    css=re.sub(re.escape(BEGIN)+r'.*?'+re.escape(END), '',css,flags=re.S)
    css=css.rstrip()+'\n\n'+BEGIN+'\n'+Path(__file__).with_name('mixpi-performance.qss').read_text()+NAVIGATION_STYLE+END+'\n'
    if not original.exists():
        original.parent.mkdir()
        shutil.copy2(skin/'skin.xml',original)
    (skin/'skin.xml').write_text(output)
    (skin/'style.qss').write_text(css)
    for name,body in {
        'mixpi-slider-handle.svg':'<rect x="2" y="3" width="16" height="30" rx="4" fill="#e5eaf2" stroke="#1d2738" stroke-width="2"/>',
        'mixpi-cpu-on.svg':'<rect width="70" height="16" rx="3" fill="#a6d95c"/>',
        'mixpi-cpu-off.svg':'<rect width="70" height="16" rx="3" fill="#333b48"/>',
    }.items():
        dims='width="20" height="36"' if 'handle' in name else 'width="70" height="16"'
        (skin/name).write_text(f'<svg xmlns="http://www.w3.org/2000/svg" {dims}>{body}</svg>\n')
    for name, svg in icon_files().items():
        (skin/name).write_text(svg)


def icon_files():
    files = {}
    for name, (width, height, colour, body) in ICONS.items():
        x, y = ICON_OFFSET.get(name, ((width - 24) // 2, (height - 24) // 2))
        files[name] = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
                       f'viewBox="0 0 {width} {height}"><g transform="translate({x} {y})" '
                       f'stroke="{colour}" {ICON_STROKE}>{body}</g></svg>\n')
    return files


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('skin',type=Path)
    parser.add_argument('--loop-display', choices=['focus', 'overlay'], default='focus',
                        help='Overlay is an opt-in renderer trial; focus avoids native GL stacking.')
    args=parser.parse_args()
    build(args.skin, args.loop_display)
    print(f'MixPi performance pages ready: {args.skin}')
