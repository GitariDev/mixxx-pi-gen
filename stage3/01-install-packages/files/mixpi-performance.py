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
    # The chip's labels sit right of the icon (R-4).
    'mixpi-icon-usb.svg': (USB_CHIP, 48, '#43d17a',
        '<circle cx="12" cy="19.5" r="2"/><path d="M12 17.5V3.5M9.5 6 12 3.5 14.5 6M12 14.5 7.5 12V9.2'
        'M12 12.6l4.5-2.6V8"/><rect x="15" y="5.6" width="3" height="2.4" rx=".4"/>'
        '<circle cx="7.5" cy="8" r="1.2"/>'),
}
ICON_OFFSET = {'mixpi-icon-usb.svg': (10, 12)}
# One time string (elapsed or remaining, PositionDisplay 0/1) plus the full
# BPM, rate and paired key fit a 400 px deck half (F-5, owner decision 1).
DECK_STAT_WIDTHS = {'time': 120, 'bpm': 100, 'rate': 60, 'key': 120}
# R-16: deck info 72 px (title row 24, readouts 48); waveform rows 2x128 with a
# 92 px deck column (the waveform widens by 8 px against F-4's 100 px column).
DECK_TITLE, DECK_STATS = 24, 48
DECK_INFO = DECK_TITLE + DECK_STATS
WAVE_INFO_SIZE = '92f,0me'
WAVE_KEY_SIZE = '84f,28f'
# Tool panel hit map (plan 5.3): Jump x 177..742 step 113 at y 134/196; Cues
# x 106/302/498/694 at y 141/217.
JUMPS = (1, 2, 4, 8, 16, 32)
JUMP_WIDTH, JUMP_HEIGHT = 107, 56
CUE_TILE = (196, 70)
# Transport per deck (plan R-16): KEY 48, Q 48, SYNC 60, LOOP 60, CUE 76, ▶ the rest.
# Tracks: LOAD 104 and the deck title in a 230 px cell, then CUE.
TRANSPORT = {'KEY': 48, 'Q': 48, 'SYNC': 60, 'LOOP': 60, 'CUE': 76}
LOAD_WIDTH, LOAD_CELL = 104, 230
SETTINGS_RAIL = 200
SETTINGS_PAGES = (('PLAYBACK', 0), ('INTERFACE', 1), ('MEDIA', 2), ('ADVANCED', 3))
# The USB chip's second line, per [MixPi],media_state (R-4).
MEDIA_STATES = ('NO USB', 'READY', 'IN USE', 'EJECTING', 'SAFE TO REMOVE')
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
# The browse page's two layouts follow sample mode ([MixPi],sample_load), not a
# screen number: a native close (N2's auto-close of Sources) writes screen 0
# and cannot know that Sources was opened from Load sample. With sample_load
# still 1 the page stays on Load sample; its ✕ or any tab clears sample_load.
LOAD_MODE = ((SCREEN, '<IsEqual>1</IsEqual><Not/>'), ('[MixPi],sample_load', None))
TRACKS_MODE = ((SCREEN, '<IsEqual>1</IsEqual><Not/>'), ('[MixPi],sample_load', '<Not/>'))


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


def chip(text, key, size, name='MixpiChip'):
    """A display-only label shown while KEY is above 0 (no write, no tap)."""
    return show_when(label(text, size, name, align='center'), key)


def state_chip(text, key, size='36f,22f'):
    """A display-only two-state chip (lit from KEY); it writes nothing."""
    e = node('PushButton')
    for k, v in dict(ObjectName='MixpiStateChip', Size=size, NumberStates=2).items():
        prop(e, k, v)
    for number in (0, 1):
        st = ET.SubElement(e, 'State')
        prop(st, 'Number', number)
        prop(st, 'Text', text)
    connection(e, key, write=False)
    return e


def deck_info(channel, compact=False, size=None):
    """R-16 deck info. Compact: the 28 px title strip on Tracks. Full: 72 px,
    row 1 badge, title, dim artist and display chips; row 2 time, BPM, tempo, key."""
    key = f'[Channel{channel}]'
    badge = label(str(channel), '28f,28f' if compact else '28f,24f', f'MixpiDeckNumber{channel}',
                  align='center')
    if compact:
        title = typed('TrackProperty', channel, '0me,28f', 'MixpiDeckTitle',
                      Property='title', Elide='right', TooltipId='track_title')
        head = group('MixpiTitleStrip', 'horizontal', '0me,28f', [badge, title])
        return group('MixpiDeckInfo', size=size or '400me,28f', children=[head])
    title = typed('TrackProperty', channel, '0me,24f', 'MixpiDeckTitle',
                  Property='title', Elide='right', TooltipId='track_title')
    artist = typed('TrackProperty', channel, '110f,24f', 'MixpiDeckArtist',
                   Property='artist', Elide='right', TooltipId='track_title')
    head = group('MixpiTitleStrip', 'horizontal', f'0me,{DECK_TITLE}f', [
        badge, title, artist,
        chip('ON PI', f'{key},mixpi_on_pi', '52f,22f', 'MixpiChipPi'),
        chip('MASTER', f'{key},sync_leader', '64f,22f'),
        chip('PFL', f'{key},pfl', '40f,22f')])
    widths, h = DECK_STAT_WIDTHS, DECK_STATS
    # F-5: one time string; a tap on it switches elapsed/remaining natively.
    mode = '[Controls],ShowDurationRemaining'
    caption = group('MixpiTimeCaption', 'horizontal', '0me,16f', [
        show_when(label('ELAPSED · TAP', '0me,16f', 'MixpiCaption'), mode, 1, negate=True),
        show_when(label('REMAINING · TAP', '0me,16f', 'MixpiCaption'), mode, 1)])
    time = group('MixpiTimeCell', size=f"{widths['time']}f,{h}f", children=[
        caption, typed('NumberPos', channel, f'0me,{h - 16}f', 'MixpiTime', NumberOfDigits=6)])
    stats = group('MixpiDeckStats', 'horizontal', f'0me,{h}f', [
        time,
        typed('NumberBpm', channel, f"{widths['bpm']}me,{h}f", 'MixpiBpm'),
        typed('NumberRate', channel, f"{widths['rate']}me,{h}f", 'MixpiRate', NumberOfDigits=1),
    ])
    connection(stats.find('Children/NumberBpm'), f'{key},visual_bpm', write=False)
    key_widget = typed('Key', channel, f"{widths['key']}me,{h}f", 'MixpiKey', PairedNotation='true')
    connection(key_widget, f'{key},visual_key', write=False)
    add(stats, key_widget)
    return group('MixpiDeckInfo', size=size or f'400me,{DECK_INFO}f', children=[head, stats])


def decks(compact=False, size=None):
    height = 28 if compact else DECK_INFO
    return group('MixpiDecks', 'horizontal', size or f'0me,{height}f',
                 [deck_info(1, compact), deck_info(2, compact)])


def wave_row(channel, visual):
    """R-16: a 128 px waveform row with the 92 px deck column (badge, key, MT and Q)."""
    v = concrete(visual, channel)
    fixed_size(v, '0me,0me')
    key = typed('Key', channel, WAVE_KEY_SIZE, 'MixpiWaveKey', PairedNotation='true')
    connection(key, f'[Channel{channel}],visual_key', write=False)
    info = group('MixpiWaveInfo', size=WAVE_INFO_SIZE, children=[
        label(str(channel), '34f,34f', f'MixpiWaveBadge{channel}', align='center'),
        key,
        group('MixpiWaveChips', 'horizontal', '0me,22f', [
            state_chip('MT', f'[Channel{channel}],keylock'),
            gap('4f,22f'),
            state_chip('Q', f'[Channel{channel}],quantize', '28f,22f'),
            gap('0me,22f')]),
        gap('0me,0me')])
    return group('MixpiWaveRow', 'horizontal', children=[info, v])


def tool_tabs(channel):
    tabs = []
    for index, (text, value) in enumerate((('LOOP', 0), ('JUMP', 1), ('CUES', 2))):
        b = preset(text, '[MixPi],tool_tab', value, size='100f,48f')
        b.find('ObjectName').text = f'MixpiToolTab{channel}'
        write(b, '[MixPi],cue_clear', 0)
        tabs += ([gap('6f,48f')] if index else []) + [b]
    return tabs


def cue_clear_toggle():
    """CLEAR switches cue taps to clear (skin-only [MixPi],cue_clear). Two
    set-value buttons in one place, never a two-state toggle (F-1)."""
    on = button('CLEAR', '[MixPi],cue_clear', size='90f,48f', push=True, transform='<Not/>',
                display='[MixPi],cue_clear')
    off = button('CLEAR', '[MixPi],cue_clear', size='90f,48f', push=True)
    off.find('Connection/ConnectValueToWidget').text = 'false'
    show_when(on, '[MixPi],cue_clear')
    # Qt puts the first child of a stacked group on top: ON covers OFF while set.
    clear = group('MixpiCueClear', 'stacked', '90f,48f', [on, off])
    return show_when(clear, '[MixPi],tool_tab', 2)


def cue_tile(channel, number):
    key = f'[Channel{channel}]'
    lit = f'<Not/><Not/>'  # hotcue_N_enabled is the status: 0 none, 1 set, 2 playing
    tap = button('', f'{key},hotcue_{number}_activate', size=f'{CUE_TILE[0]}f,{CUE_TILE[1]}f',
                 momentary=True, display=f'{key},hotcue_{number}_enabled', name=f'MixpiCueTile{channel}',
                 state_labels=(f'{number}  ·  tap to set', str(number)))
    tap.findall('Connection')[-1].append(ET.fromstring(f'<Transform>{lit}</Transform>'))
    clear = button('', f'{key},hotcue_{number}_clear', size=f'{CUE_TILE[0]}f,{CUE_TILE[1]}f',
                   momentary=True, display=f'{key},hotcue_{number}_enabled', name='MixpiCueClearTile',
                   state_labels=(f'{number}', f'{number}  ·  tap to clear'))
    clear.findall('Connection')[-1].append(ET.fromstring(f'<Transform>{lit}</Transform>'))
    connection(clear, f'{key},hotcue_{number}_enabled', transform=lit, bind='enabled')
    show_when(clear, '[MixPi],cue_clear')
    return group('MixpiCueCell', 'stacked', f'{CUE_TILE[0]}f,{CUE_TILE[1]}f', [clear, tap])


def tool_panel(channel, loop_display='focus'):
    """R-16 tool panel (LOOP · JUMP · CUES) over the waveform rows, opened by LOOP."""
    key = f'[Channel{channel}]'
    close = button('×  CLOSE', '[MixPi],loop_deck', size='110f,48f', transform='<Not/>', push=True)
    # Closing only writes zero; it does not mirror the selected deck into its state.
    close.find('Connection/ConnectValueToWidget').text = 'false'
    write(close, '[MixPi],cue_clear', 0)
    heading = f'DECK {channel}'
    header = group('MixpiToolHeader', 'horizontal', '0me,48f', [
        gap('8f,48f'), label(str(channel), '34f,34f', f'MixpiWaveBadge{channel}', align='center'),
        label(heading, '90f,48f', 'MixpiToolTitle')] + tool_tabs(channel) + [
        gap('0me,48f'), cue_clear_toggle(), gap('10f,48f'), close, gap('8f,48f')])
    # LOOP: today's 12 sizes, then ½, ×2, EXIT, RELOOP (same controls and rules).
    loop = group('MixpiLoopBody', size='0me,156f')
    for index, offset in enumerate((0, 6)):
        row = group('MixpiLoopRow', 'horizontal', '0me,48f')
        for text, value in LOOPS[offset:offset+6]:
            add(row, button(text, f'{key},beatloop_{value}_activate', momentary=True,
                            display=f'{key},beatloop_{value}_enabled'))
        add(loop, *([gap('0me,6f')] if index else []), row)
    tools = group('MixpiLoopTools', 'horizontal', '0me,48f', [
        button('½', f'{key},loop_halve', momentary=True),
        button('×2', f'{key},loop_double', momentary=True),
        button('EXIT', f'{key},loop_exit', momentary=True, display=f'{key},loop_enabled'),
        button('RELOOP', f'{key},reloop_toggle', momentary=True, display=f'{key},loop_enabled')])
    # Reloop jumps back to the saved loop. Disable it while already looping,
    # so a second tap cannot turn looping off (Exit has its own command).
    connection(tools.find('Children')[3], f'{key},loop_enabled', transform='<Not/>', bind='enabled')
    add(loop, gap('0me,6f'), tools)
    show_when(loop, '[MixPi],tool_tab', 0)
    # JUMP: beatjump_N_backward / _forward, two labelled rows of six (plan 5.3 hit map).
    jump = group('MixpiJumpBody', size='0me,140f')
    for index, (direction, caption) in enumerate((('backward', '◀  BACK'), ('forward', 'FORWARD  ▶'))):
        row = group('MixpiJumpRow', 'horizontal', f'0me,{JUMP_HEIGHT}f', [
            gap('8f,56f'), label(caption, '110f,56f', 'MixpiCaption'), gap('6f,56f')])
        for n, beats in enumerate(JUMPS):
            text = f'◀ {beats}' if direction == 'backward' else f'{beats} ▶'
            add(row, *([gap('6f,56f')] if n else []),
                button(text, f'{key},beatjump_{beats}_{direction}', size=f'{JUMP_WIDTH}f,{JUMP_HEIGHT}f',
                       momentary=True))
        add(row, gap('0me,56f'))
        add(jump, *([gap('0me,6f')] if index else []), row)
    add(jump, label('Beats. Quantize keeps the jump on the grid.', '0me,22f', 'MixpiScreenHint'))
    show_when(jump, '[MixPi],tool_tab', 1)
    # CUES: hot cues 1-8 as 4x2 tiles; CLEAR switches a tap to hotcue_N_clear.
    cues = group('MixpiCuesBody', size='0me,162f')
    for index, first in enumerate((1, 5)):
        add(cues, *([gap('0me,6f')] if index else []),
            group('MixpiCueRow', 'horizontal', f'0me,{CUE_TILE[1]}f',
                  [gap('8f,70f')] + [cue_tile(channel, n) for n in range(first, first + 4)] + [gap('0me,70f')]))
    add(cues, label("Pads 1-4 match the Starlight's hot cue pads. 5-8 are screen only.",
                    '0me,16f', 'MixpiScreenHint'))
    show_when(cues, '[MixPi],tool_tab', 2)
    panel = group('MixpiLoopPanel', children=[
        gap('0me,4f'), header, gap('0me,6f'), loop, jump, cues, gap('0me,0me')])
    connection(panel, '[MixPi],loop_deck', transform=f'<IsEqual>{channel}</IsEqual>', bind='visible')
    return panel


def loops(channel, loop_display='focus'):
    """The deck tool panel; the name is kept for the loop-semantics tests."""
    return tool_panel(channel, loop_display)


def slider(key, name='MixpiDepth', size='0me,48f'):
    e = node('SliderComposed')
    for k, v in dict(ObjectName=name, Size=size, Horizontal='true',
                     Handle='mixpi-slider-handle.svg', BarColor='#b5e15c', BarWidth=8).items():
        prop(e, k, v)
    connection(e, key)
    return e


def fx_unit(unit):
    """R-17: one effect unit. Unit 1 = the Starlight's deck A FX pads, unit 2 = deck B."""
    rack = f'[EffectRack1_EffectUnit{unit}]'
    deck = 'A' if unit == 1 else 'B'
    routes = ['[Channel1]', '[Channel2]', '[Master]']
    header = group('MixpiFxHeader', 'horizontal', '0me,56f', [gap('8f,56f'), label('ROUTE', '56f,48f', 'MixpiCaption')])
    for index, (route, text) in enumerate(zip(routes, ['DECK 1', 'DECK 2', 'MASTER'])):
        key = f'{rack},group_{route}_enable'
        own = index == unit - 1
        b = button(f'{text} · PAD 4' if own else text, key, size='150f,48f' if own else '120f,48f',
                   push=True, display=key)
        # Disable other routes before enabling this one. Touch selection is
        # exclusive without changing per-effect depth or enable controls.
        first = b.find('Connection')
        b.remove(first)
        for other in routes:
            if other != route:
                connection(b, f'{rack},group_{other}_enable', read=False, transform='<Not/>')
        b.append(first)
        add(header, b)
    add(header, group('MixpiFxMix', 'horizontal', '0me,56f', [
        label('MIX', '48f,48f', 'MixpiCaption'), slider(f'{rack},mix', size='0me,48f')]))
    cards = group('MixpiFxCards', 'horizontal', '0me,144f')
    for slot in range(1, 4):
        effect = f'[EffectRack1_EffectUnit{unit}_Effect{slot}]'
        select = node('EffectSelector')
        for k, v in dict(ObjectName='MixpiEffectSelector', EffectRack=1,
                         EffectUnit=unit, Effect=slot, Elide='right', Size='0me,48f').items():
            prop(select, k, v)
        add(cards, group('MixpiFxCard', children=[
            group('MixpiFxCardHead', 'horizontal', '0me,22f', [
                label(f'EFFECT {slot}', '0me,22f', 'MixpiCaption'),
                label(f'deck {deck} FX pad {slot}', '120f,22f', 'MixpiFxPad', align='right')]),
            group('MixpiFxCardRow', 'horizontal', '0me,48f', [
                select, button('OFF', f'{effect},enabled', size='64f,48f', state_labels=('OFF', 'ON'))]),
            slider(f'{effect},meta')]))
    return show_when(group('MixpiFxUnit', size='0me,200f', children=[header, cards]),
                     '[MixPi],fx_unit', unit)


def fx():
    """R-17 and owner answer 5: FX 1 (deck A pads) and FX 2 (deck B pads), each
    with today's exclusive DECK 1 / DECK 2 / MASTER switcher, MIX and 3 cards."""
    switch = group('MixpiFxSwitch', 'horizontal', '0me,56f', [gap('8f,56f')])
    for index, (text, unit) in enumerate((('FX 1 · DECK A PADS', 1), ('FX 2 · DECK B PADS', 2))):
        add(switch, *([gap('6f,48f')] if index else []),
            preset(text, '[MixPi],fx_unit', unit, size='206f,48f'))
    add(switch, label('Starlight FX mode: pads 1-3 switch these effects; pad 4 sends the unit to its deck.',
                      '0me,48f', 'MixpiScreenHint', elide='right'))
    return group('MixpiFx', size='0me,256f', children=[switch, fx_unit(1), fx_unit(2)])


def preset(text, key, value, size='0me,48f'):
    b = button(text, key, push=True, size=size,
               transform=f'<IsEqual>{value}</IsEqual>' if value else '<Not/>')
    b.find('Connection/ConnectValueToWidget').text = 'false'
    connection(b, key, write=False, transform=f'<IsEqual>{value}</IsEqual>')
    return b


def preferences_button():
    # The patched Mixxx opens its Preferences dialog, queued, on a request above 0.
    b = button('Mixxx preferences…', '[MixPi],show_preferences', push=True, size='220f,48f')
    b.find('Connection/ConnectValueToWidget').text = 'false'
    return b


def setting_row(title, sub, controls):
    """A Settings row: a 190 px label column, then 48 px choices."""
    labels = group('MixpiSettingText', size='190f,66f', children=[
        gap('0me,0me'), label(title, '0me,24f', 'MixpiSettingTitle', elide='right')] +
        ([label(sub, '0me,34f', 'MixpiSettingLabel', elide='right')] if sub else []) +
        [gap('0me,0me')])
    return group('MixpiSetting', 'horizontal', '0me,66f',
                 [gap('14f,66f'), labels, gap('10f,66f')] + list(controls) + [gap('0me,66f')])


def choices(key, items, width=96):
    return [preset(text, key, value, size=f'{width}f,48f') for text, value in items]


def settings():
    """R-18: Settings is a full screen (screen 5) with a rail of four panes."""
    close = button('', SCREEN, size='48f,48f', push=True, name='MixpiIconButton', transform='<Not/>')
    close.find('Connection/ConnectValueToWidget').text = 'false'
    icon_states(close, 'mixpi-icon-close-plain.svg', 'mixpi-icon-close-plain.svg')
    header = group('MixpiSettingsHeader', 'horizontal', f'0me,{TOP_HEIGHT}f', [
        close, label('SETTINGS', '150f,48f', 'MixpiScreenTitle'),
        label('Every change saves within a second.', '0me,48f', 'MixpiScreenHint', elide='right'),
        # R-13 pulses [MixPi],saved for 2 s after each save.
        show_when(label('Saved', '90f,48f', 'MixpiSavedNote', align='center'), '[MixPi],saved')])
    rail = group('MixpiSettingsRail', size=f'{SETTINGS_RAIL}f,0me')
    for text, value in SETTINGS_PAGES:
        b = preset(text, '[MixPi],settings_page', value, size=f'{SETTINGS_RAIL}f,56f')
        b.find('ObjectName').text = 'MixpiRailButton'
        add(rail, b)
    add(rail, gap('0me,0me'))
    buffers = choices('[MixPi],buffer_frames', [('256', 256), ('512', 512), ('1024', 1024)])
    for b in buffers:
        connection(b, '[MixPi],buffer_available', bind='enabled')
    playback = group('MixpiPlaybackSettings', children=[
        setting_row('Key lock engine', '', choices('[MixPi],keylock_engine',
                    [('ST', 0), ('RB FAST', 1), ('RB FINE', 2)], 110)),
        setting_row('Audio buffer', 'Frames', buffers),
        # [MixPi],tempo_range_index: 0 Custom, 1 4%, 2 6%, 3 8%, 4 10%, 5 16%, 6 24%, 7 50%, 8 90%.
        setting_row('Tempo range', 'Fader range ±. Others in Mixxx preferences.',
                    choices('[MixPi],tempo_range_index',
                            [('6%', 2), ('8%', 3), ('10%', 4), ('16%', 5), ('24%', 6)], 72)),
        setting_row('Quantize', '', [
            button('DECK 1', '[Channel1],quantize', size='110f,48f', name='MixpiDeck1'),
            gap('6f,48f'),
            button('DECK 2', '[Channel2],quantize', size='110f,48f', name='MixpiDeck2')]),
        setting_row('Split cue', 'Headphones: cue left, master right',
                    [button('OFF', '[Master],headSplit', size='96f,48f', state_labels=('OFF', 'ON'))]),
        gap('0me,0me')])
    bar = button('Top bar unavailable', '[MixPi],desktop_bar', push=True, name='MixpiDesktopBar',
                 state_labels=('Show top bar', 'Hide top bar', 'Checking top bar…',
                               'Top bar unavailable'), size='220f,48f')
    connection(bar, '[MixPi],desktop_bar_available', bind='enabled')
    interface = group('MixpiInterfaceSettings', children=[
        setting_row('Desktop bar', 'Desktop · Mixxx · Speaker · Settings', [bar]),
        setting_row('Deck time', 'Tap the time on a deck to switch',
                    choices('[Controls],ShowDurationRemaining', [('ELAPSED', 0), ('REMAINING', 1)], 130)),
        gap('0me,0me')])
    eject = group('MixpiEjectState', 'horizontal', '96f,48f', [
        show_when(label('ON', '96f,48f', 'MixpiEjectOn', align='center'), '[MixPi],media_eject_available'),
        show_when(label('OFF', '96f,48f', 'MixpiEjectOff', align='center'),
                  '[MixPi],media_eject_available', negate=True)])
    media = group('MixpiMediaSettings', children=[
        # N2: [MixPi],scan_bar_hidden 0/1 (also saved as ScanBarHidden).
        setting_row('Scan bar', 'Hidden: the % shows on the USB chip',
                    choices('[MixPi],scan_bar_hidden', [('SHOW', 0), ('HIDE', 1)])),
        setting_row('RAM cache', 'MB. Also the room for handover copies. Next launch.',
                    choices('[MixPi],cache_mb', [('OFF', 0), ('512', 512), ('1024', 1024)])),
        setting_row('Eject', 'Safe eject on this card', [eject]),
        setting_row('Plugging in a drive', 'A small ping at the bottom with LOAD or DISMISS',
                    [label('Always', '96f,48f', 'MixpiScreenHint')]),
        gap('0me,0me')])
    advanced = group('MixpiAdvancedSettings', children=[
        setting_row('Waveform FPS', '', choices('[MixPi],waveform_fps', [('30', 30), ('45', 45), ('60', 60)])),
        setting_row('Read ahead', 'Chunks. Next launch.', choices('[MixPi],read_ahead', [('2', 2), ('8', 8), ('24', 24)])),
        setting_row('Mixxx preferences', 'Audio routing, controllers', [preferences_button()]),
        gap('0me,0me')])
    panes = group('MixpiSettingsPanes')
    for value, pane in enumerate((playback, interface, media, advanced)):
        add(panes, show_when(pane, '[MixPi],settings_page', value))
    body = group('MixpiSettingsBody', 'horizontal', children=[rail, panes])
    return group('MixpiSettings', children=[header, body])


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
    # The native sidebar has its own Back inside the rail (mixxx-sources-screen.patch),
    # so the skin's LibraryBackButton is left out.
    sidebar_button = parts['SidebarButton']

    # ☰ / ✕ (R-11): the existing two-state key; open also writes screen 1.
    fixed_size(sidebar_button, '48f,48f')
    icon_states(sidebar_button, 'mixpi-icon-menu.svg', 'mixpi-icon-close.svg')
    connection(sidebar_button, SCREEN, read=False, transform=f'<IsEqual>{SCREEN_SOURCES}</IsEqual>')
    # ✎ (R-11): Actions keeps its key and object name; the native menu anchors under it.
    fixed_size(actions, '48f,48f')
    icon_states(actions, 'mixpi-icon-pen.svg', 'mixpi-icon-pen.svg')
    # EDIT LIST reads DONE while the native edit list is open.
    fixed_size(sources, '128f,48f')
    sources.find('NumberStates').text = '2'
    sources.find('State/Text').text = 'EDIT LIST'
    done = node('State')
    prop(done, 'Number', 1)
    prop(done, 'Text', 'DONE')
    sources.insert(list(sources).index(sources.find('State')) + 1, done)
    connection(sources, '[Library],sidebar_sources_editing', write=False)
    fixed_size(search, '250me,40f')
    # A SearchBox takes no Connection (LegacySkinParser::parseSearchBox), so a
    # group carries its visibility.
    search = group('MixpiSearch', 'horizontal', '250me,48f', [search])

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
    # The first shown child is on top and takes the taps, and a shown wrapper
    # whose button is hidden still covers what is under it. So the order and the
    # outer conditions are chosen so that, for each screen, the top shown child
    # holds the button that belongs there (tested by the tap model).
    # Each level holds mutually exclusive children, so a shown child always has
    # its button: sample mode shows one of the two closes, otherwise the menu.
    closes = group('MixpiSampleCloses', 'stacked', '48f,48f', [
        show_when(sample_sources_close, SCREEN, SCREEN_SOURCES),
        show_when(load_close, SCREEN, SCREEN_SOURCES, negate=True)])
    slot = group('MixpiHeaderSlot', 'stacked', '48f,48f', [
        show_when(closes, '[MixPi],sample_load'),
        show_when(sidebar_button, '[MixPi],sample_load', negate=True)])

    crumb = when_all(label('', '220f,48f', 'MixpiTracksCrumb', elide='right'), '220f,48f', *TRACKS_MODE)
    sources_head = group('MixpiSourcesHead', 'horizontal', '0me,48f', [
        label('SOURCES', '120f,48f', 'MixpiScreenTitle'),
        show_when(label('Pick a source, then a list.', '0me,48f', 'MixpiScreenHint', elide='right'),
                  '[MixPi],sample_load', negate=True),
        show_when(label('Pick the list to load samples from.', '0me,48f', 'MixpiScreenHint',
                        elide='right'), '[MixPi],sample_load')])
    show_when(sources_head, SCREEN, SCREEN_SOURCES)
    load_head = when_all(group('MixpiLoadHead', 'horizontal', '380f,48f', [
        label('LOAD SAMPLE', '150f,48f', 'MixpiScreenTitle'), sample_hints()]),
        '380f,48f', *LOAD_MODE)
    header = group('MixpiBrowseHeader', 'horizontal', f'0me,{TOP_HEIGHT}f', [
        slot, crumb, sources_head, load_head,
        show_when(search, SCREEN, SCREEN_SOURCES, negate=True),
        when_all(actions, '48f,48f', *TRACKS_MODE),
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
    source_row = when_all(source_row, '0me,56f', *LOAD_MODE)

    table = show_when(group('MixpiLibraryMain', children=[parts['Library']]),
                      SCREEN, SCREEN_SOURCES, negate=True)
    titles = decks(compact=True)
    titles.find('ObjectName').text = 'MixpiTrackTitles'
    titles = when_all(titles, '0me,28f', *TRACKS_MODE)

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
        targets, gap('8f,64f')]), '0me,64f', *LOAD_MODE)

    wrapper = group('LibraryWrapper', children=[header, sources_body, source_row, table, titles, footer])
    # In a stacked group Qt lowers each later child (QStackedLayout::insertWidget),
    # so the first child is on top: the Choose pad sheet comes first.
    page = group('MixpiBrowse', 'stacked', children=[choose_pad(), wrapper])
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
        tiles.append(group('MixpiChooseCell', 'stacked', '165f,96f', [tile, info]))
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
            chip('ON PI', f'{key},mixpi_on_pi', '48f,20f', 'MixpiChipPi'),
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
        group('MixpiPadTapArea', 'stacked', f'{width}f,{PAD_TAP}f', [trigger, info]),
        group('MixpiPadStrip', 'horizontal', f'{width}f,{PAD_STRIP}f', [stop, clear])])
    show_when(loaded, f'{key},track_loaded')
    open_load = button('', '[Tab],library', size=f'{width}f,{height}f', push=True, name='MixpiPadLoad')
    open_load.find('Connection/ConnectValueToWidget').text = 'false'
    reset_views(open_load, keep=('[MixPi],sample_load', '[MixPi],sample_pad', SCREEN))
    write(open_load, '[MixPi],sample_load', 1)
    write(open_load, '[MixPi],sample_pad', sampler)
    write(open_load, SCREEN, SCREEN_LOAD_SAMPLE)
    empty = group('MixpiPadEmpty', 'stacked', f'{width}f,{height}f', [
        open_load,
        group('MixpiPadInfo', size=f'{width}f,{height}f', children=[
            pad_tag(sampler), label('+  Empty · tap to load', '0me,32f', 'MixpiPadEmptyText'),
            gap('0me,0me')])])
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
    # Expanding with a 1 px minimum: it takes the 72 px left at 480 px, and gives
    # way first at 444 px (desktop bar shown). An Ignored policy got no height and
    # the group's centred layout then pushed the page down by 36 px.
    info = decks(size='0me,1e')
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


def tab_stack(text, key, width):
    """A tab and its twins in one place. Qt puts the first child of a stacked
    group on top, so the last child, an unlit twin, is always there underneath:
    - SAMPLER only: a twin lit from [MixPi],sample_load (Load sample, Choose pad,
      Sources opened from Load sample);
    - the normal tab, lit from its page, unless Settings is open (the gear is
      lit then) or, for TRACKS and SAMPLER, a sample screen is open.
    All of them send the same writes."""
    size = f'{width}f,48f'

    def unlit():
        b = tab(text, key, width)
        b.find('Connection/ConnectValueToWidget').text = 'false'
        return b
    # One condition per stacked level, each level with its own unlit base: a
    # shown group whose only child is hidden would still cover what is under it.
    conditions = ([('[MixPi],sample_load', '<Not/>')] if key in ('library', 'sampler') else []) + \
        [off_screen(SCREEN_SETTINGS)]
    widget = tab(text, key, width)
    for condition_key, condition in conditions:
        show_when(widget, condition_key, transform=condition)
        widget = group('MixpiTabPair', 'stacked', size, [widget, unlit()])
    if key == 'sampler':
        lit = unlit()
        connection(lit, '[MixPi],sample_load', write=False)
        widget.find('Children').insert(0, show_when(lit, '[MixPi],sample_load'))
    return widget


def usb_chip():
    """R-4 skin part: the 150x48 chip writes [MixPi],media_load (today's dialog,
    N3's Media screen). Its look follows [MixPi],media_state; MixpiUsbName is set
    from native code to the drive name; SCAN NN% shows while a hidden scan runs."""
    tap = button('', '[MixPi],media_load', size=f'{USB_CHIP}f,48f', push=True, name='MixpiUsbButton')
    for state in tap.findall('State'):
        state.append(node('Unpressed', 'mixpi-icon-usb.svg', scalemode='FIXED'))
        state.append(node('Pressed', 'mixpi-icon-usb.svg', scalemode='FIXED'))
    connection(tap, '[MixPi],media_available', bind='enabled')
    states = group('MixpiUsbStates', 'horizontal', '0me,18f')
    for value, text in enumerate(MEDIA_STATES):
        add(states, show_when(label(text, '0me,18f', f'MixpiUsbState{value}', elide='right'),
                              '[MixPi],media_state', value))
    scan = node('Number')
    for k, v in dict(ObjectName='MixpiUsbScan', Size='0me,18f', Text='SCAN %1%', NumberOfDigits=0).items():
        prop(scan, k, v)
    connection(scan, '[MixPi],scan_percent', write=False)
    scan = when_all(scan, '0me,18f', ('[MixPi],scan_active', None), ('[MixPi],scan_bar_hidden', None))
    lines = group('MixpiUsbLines', size='0me,48f', children=[
        gap('0me,0me'),
        label('USB', '0me,20f', 'MixpiUsbName', elide='right'),
        # The scan line covers the state line (first child on top, opaque).
        group('MixpiUsbLine2', 'stacked', '0me,18f', [scan, states]),
        gap('0me,0me')])
    body = group('MixpiUsbBody', 'horizontal', f'{USB_CHIP}f,48f', [gap('42f,48f'), lines, gap('6f,48f')])
    connection(body, '[MixPi],media_state', bind='highlight')
    # The transparent button is first, so it is on top and takes the taps.
    return group('MixpiUsbChip', 'stacked', f'{USB_CHIP}f,48f', [tap, body])


def topbar():
    """R-1: the 48 px top bar in PROTO's order."""
    top = group('MixpiTopbar', 'horizontal', f'0me,{TOP_HEIGHT}f')
    for text, key, width in TOPBAR:
        add(top, tab_stack(text, key, width))
    # R-18: the gear opens the full-screen Settings (screen 5) and is lit there.
    gear = button('', SCREEN, size=f'{GEAR}f,48f', push=True, name='MixpiIconButton',
                  transform=f'<IsEqual>{SCREEN_SETTINGS}</IsEqual>')
    icon_states(gear, 'mixpi-icon-gear.svg', 'mixpi-icon-gear.svg')
    connection(gear, '[MixPi],settings_available', bind='enabled')
    reset_views(gear, keep=(SCREEN,))
    record = button('● REC', '[Recording],toggle_recording', size=f'{REC_WIDTH}f,48f', momentary=True,
                    display='[Recording],status', name='MixpiRecord',
                    state_labels=('● REC', 'WAIT', '■ STOP', '■ STOP'))
    # The gaps put the chip, REC and the gear on the plan's tap points
    # (x 527, 649, 717; plan 5.3) with the brief's widths.
    add(top, group('MixpiTopSpacer', 'horizontal'), usb_chip(), gap(f'{TOP_GAPS[0]}f,48f'), record,
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


def loop_button(channel):
    """LOOP opens the tool panel; it is lit while the panel is open, and in the
    deck colour while a loop plays (a Starlight loop pad shows on screen)."""
    def one(display, transform):
        b = button('LOOP', '[MixPi],loop_deck', size=f"{TRANSPORT['LOOP']}f,48f", push=True,
                   transform=f'<IsEqual>{channel}</IsEqual>', name=f'MixpiDeck{channel}')
        b.find('Connection/ConnectValueToWidget').text = 'false'
        write(b, '[Tab],overview', 1)
        write(b, '[MixPi],sample_load', 0)
        connection(b, display, write=False, transform=transform)
        return b
    is_open = one('[MixPi],loop_deck', f'<IsEqual>{channel}</IsEqual>')
    show_when(is_open, '[MixPi],loop_deck', channel)
    is_open.find('ObjectName').text = 'MixpiButton'
    looping = one(f'[Channel{channel}],loop_enabled', None)
    pair = group('MixpiLoopPair', 'stacked', f"{TRANSPORT['LOOP']}f,48f", [is_open, looping])
    return show_when(pair, '[Tab],library', negate=True)


def transport_row(channel):
    """The same row on Decks, FX and Sampler; Tracks swaps in LOAD + title + CUE."""
    key = f'[Channel{channel}]'
    deck_name = f'MixpiDeck{channel}'
    off_tracks = lambda e: show_when(e, '[Tab],library', negate=True)
    on_tracks = lambda e: show_when(e, '[Tab],library')
    keylock = off_tracks(button('KEY', f'{key},keylock', size=f"{TRANSPORT['KEY']}f,48f", name=deck_name))
    quantize = off_tracks(button('Q', f'{key},quantize', size=f"{TRANSPORT['Q']}f,48f", name=deck_name))
    sync = off_tracks(button('SYNC', f'{key},sync_enabled', size=f"{TRANSPORT['SYNC']}f,48f", name=deck_name))
    # LOAD sends press and release like the sampler pads, and is off while the deck plays (F-3).
    load = button(f'LOAD {channel}', f'{key},LoadSelectedTrack', size=f'{LOAD_WIDTH}f,48f',
                  momentary=True, name=f'MixpiLoad{channel}')
    connection(load, f'{key},play', transform='<Not/>', bind='enabled')
    on_tracks(load)
    title = typed('TrackProperty', channel, f'0me,48f', 'MixpiLoadTitle',
                  Property='title', Elide='right', TooltipId='track_title')
    title_cell = on_tracks(group('MixpiLoadCell', 'horizontal', f'{LOAD_CELL - LOAD_WIDTH}f,48f', [
        show_when(title, f'{key},play', negate=True),
        show_when(label('Playing · stop to load', '0me,48f', 'MixpiLoadTitle', elide='right'),
                  f'{key},play')]))
    cue = off_tracks(button('CUE', f'{key},cue_default', size=f"{TRANSPORT['CUE']}f,48f",
                            momentary=True, name='MixpiCue'))
    tracks_cue = on_tracks(button('CUE', f'{key},cue_default', size='0me,48f', momentary=True,
                                  name='MixpiCue'))
    play = off_tracks(button('▶', f'{key},play', name='MixpiPlay'))
    return group('MixpiDeckButtons', 'horizontal', f'400me,{TRANSPORT_HEIGHT}f', [
        keylock, quantize, sync, loop_button(channel), cue, load, title_cell, tracks_cue, play])


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
                       ('[Sidebar],sidebar_visible', '0'), ('[MixPi],tool_tab', '0'),
                       ('[MixPi],cue_clear', '0'), ('[MixPi],fx_unit', '1'),
                       ('[MixPi],settings_page', '0')]:
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
    waves=group('MixpiWaveforms', children=[wave_row(1, visual), wave_row(2, visual)])
    visible = '<IsEqual>0</IsEqual>' if loop_display == 'focus' else '<IsEqual>3</IsEqual><Not/>'
    connection(waves, '[MixPi],loop_deck', transform=visible, bind='visible')
    connection(waves, '[MixPi],loop_deck', transform='<IsEqual>0</IsEqual>', bind='enabled')
    # The tool panels come first in the stacked group, so in the overlay trial
    # they sit on top of the waveforms (Qt lowers each later child).
    add(perform, group('MixpiWaveArea', 'stacked', children=[
        loops(1, loop_display), loops(2, loop_display), waves]), decks())
    pages.append(perform)
    pages.append(browse_page(library))
    fxpage=group('MixpiFxPage', children=[fx(), decks(size='0me,1e')])
    fxpage.set('trigger','[Tab],fx')
    pages.append(fxpage)
    pages.append(sampler_page())
    # R-18: Settings is a full screen; the pages are hidden under it (no widget
    # over a live waveform, plan 4.1 rule 3).
    children.append(show_when(group('MixpiPages', children=[stack]), SCREEN, SCREEN_SETTINGS, negate=True))
    children.append(show_when(settings(), SCREEN, SCREEN_SETTINGS))
    summaries=group('MixpiSummaries','horizontal',f'0me,{OVERVIEW_HEIGHT}f')
    transport=group('MixpiTransport','horizontal',f'0me,{TRANSPORT_HEIGHT}f')
    for ch in (1,2):
        add(summaries, summary(ch, overview, visual, loop_display))
        add(transport, transport_row(ch))
    # Overviews and transport show only while no full-screen view is open
    # (plan 4.1): no touch CUE or PLAY under Sources, Load sample or Choose pad.
    bottom = group('MixpiBottom', size=f'0me,{OVERVIEW_HEIGHT + TRANSPORT_HEIGHT}f',
                   children=[summaries, transport])
    # Not in sample mode either: Load sample after a native close of Sources.
    children.append(when_all(bottom, f'0me,{OVERVIEW_HEIGHT + TRANSPORT_HEIGHT}f',
                             on_screen(SCREEN_NONE), ('[MixPi],sample_load', '<Not/>')))
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
        # R-17: 28x44 handles (plan: 28x48 inside the 48 px slider).
        'mixpi-slider-handle.svg':'<rect x="2" y="2" width="24" height="40" rx="6" fill="#e9eef5" stroke="#121821" stroke-width="2"/>',
        'mixpi-cpu-on.svg':'<rect width="70" height="16" rx="3" fill="#a6d95c"/>',
        'mixpi-cpu-off.svg':'<rect width="70" height="16" rx="3" fill="#333b48"/>',
    }.items():
        dims='width="28" height="44"' if 'handle' in name else 'width="70" height="16"'
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
