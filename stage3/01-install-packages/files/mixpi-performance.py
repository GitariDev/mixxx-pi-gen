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
# Agreed UI radius 3 (AGREED-UI-SPEC section 1, --mx-radius). It replaces
# build B's 6 px corners.
NAVIGATION_STYLE = '''/* MixPi native navigation */
#MixpiButton, #MixpiPlay, #MixpiRecord, #MixpiUsbChip, #MixpiPrimary, #MixpiClose,
#LibraryWrapper #LibraryActionsButton, #LibraryWrapper #SidebarButton,
#LibraryWrapper #LibrarySourcesButton, #LibraryWrapper #LibraryBackButton {
    border-radius: 3px;
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
# WidgetStack page order ([Tab],current index).
PAGES = ('overview', 'library', 'fx', 'sampler')
USB_CHIP, REC_WIDTH, GEAR, CPU_WIDTH = 150, 72, 48, 56
TOP_GAPS = (11, 8, 3)
PAD_SIZE, PAD_STRIP = (200, 104), 48
# A pad (m-sampler.png): 4 px top, head 24, name 24, the 48 px buttons, 4 px
# gaps around them.
PAD_INFO, PAD_GAP = 52, 4
SAMPLER_INFO = 72
SAMPLER_LOAD, SAMPLER_CLEAR = 168, 150
# Clear samples popover (m-sampler-clear.png): a 480 px sheet, 24 px from the
# screen's edges at most; 52 px rows; the tick drawn 18 px in.
CLEAR_SHEET_WIDTH, CLEAR_MARGIN = 480, 24
CLEAR_ROW, CLEAR_TICK_SPACE = 52, 52
# The sheet's fixed parts: the 1 px border twice, the 56 px head, the 40 px
# note and the 68 px foot. The list takes the rest of the 480 px screen less
# the margins (primitives.css .mx-popover-sheet max-height: 100%), 266 px:
# five rows fit; more scroll.
CLEAR_FIXED = 2 + 56 + 40 + 68
CLEAR_LIST_MAX = 480 - 2 * CLEAR_MARGIN - CLEAR_FIXED
# Icons the generator writes into the skin (R-11): 24 px glyphs from the
# prototype, centred in 48 px buttons, drawn unscaled (FIXED) by WPushButton.
ICON_STROKE = 'fill="none" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"'
# The close control (AGREED-UI-SPEC section 1): a red ✕ in --mx-danger-text,
# two 20 x 2.5 px strokes crossing at the centre.
CLOSE_STROKES = ('<path d="M4.93 4.93 19.07 19.07M19.07 4.93 4.93 19.07" '
                 'stroke-width="2.5" stroke-linecap="butt"/>')
ICONS = {
    'mixpi-icon-menu.svg': (48, 48, '#e4e7ec', '<path d="M4 7h16M4 12h16M4 17h16"/>'),
    'mixpi-icon-close.svg': (48, 48, '#ec7f74', CLOSE_STROKES),
    'mixpi-icon-pen.svg': (48, 48, '#e4e7ec',
        '<path d="M4 20h4L19.4 8.6a2.1 2.1 0 0 0-3-3L5 17v3z"/><path d="M14.6 7.4l2 2"/>'),
    'mixpi-icon-gear.svg': (48, 48, '#e4e7ec',
        '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08'
        'a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74'
        'l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 '
        '1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08'
        'a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74'
        'l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25'
        'a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>'),
    # The chip's labels sit right of the icon (R-4).
    'mixpi-icon-usb.svg': (USB_CHIP, 48, '#5fae6e',
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
DECK_TITLE_MIN, DECK_ARTIST_MIN = 56, 31
WAVE_INFO_SIZE = '92f,0me'
WAVE_KEY_SIZE = '84f,28f'
# Tool panel hit map (plan 5.3): Jump x 177..742 step 113 at y 134/196; Cues
# x 106/302/498/694 at y 141/217.
JUMPS = (1, 2, 4, 8, 16, 32)
JUMP_WIDTH, JUMP_HEIGHT = 107, 56
# LOOP rows (spec s2, owner 2026-11-18 "Shorter rows then"): 48 px at 800x480;
# with the desktop top bar shown (800x444) the panel is 36 px shorter, so each
# of the four rows gives up 9 px (4 x 39 + 3 x 4 = 168). Below the touch
# minimum in that mode only, by the owner's choice.
LOOP_ROW, LOOP_ROW_SHORT, LOOP_GAP = 48, 39, 4
CUE_TILE = (196, 70)
# Transport per deck (plan R-16): KEY 48, Q 48, SYNC 60, LOOP 60, CUE 76, ▶ the rest.
# Tracks (spec s3, m-tracks.png): LOAD n 84 · the track name · CUE 68 · ▶ 68.
TRANSPORT = {'KEY': 48, 'Q': 48, 'SYNC': 60, 'LOOP': 60, 'CUE': 76}
LOAD_WIDTH, TRACKS_CUE, TRACKS_PLAY = 84, 68, 68
SETTINGS_RAIL = 200
# Spec s11/s12: rail rows are 52 px menu rows; the Desktop bar button is 180 px;
# the Brightness slider runs to the 56 px "80%" readout at the right.
RAIL_ROW, DESKTOP_BAR_WIDTH, BRIGHTNESS_SLIDER = 52, 180, 316
# Spec 2f: Settings › Interface gets a sixth row, Zoom. The page has 376 px
# (480 - the 48 px top bar - the 48 px Settings header - the pane's 4 px
# padding above and below); five 66 px rows leave 46, short of a 48 px
# button. So the five rows give up 1 px each (65, the 48 px controls still
# centred) and Zoom, with no subtext, takes the 51 px left: 5 x 65 + 51 = 376.
INTERFACE_ROW, ZOOM_ROW = 65, 51
# Load sample source row (spec s7, m-loadsample.png): 8 + SAMPLES 124 + 8 + SOURCES… 124.
SOURCE_ROW = {'SAMPLES': 124, 'SOURCES…': 124}
# Segments (LOOP / JUMP / CUES, FX 1 / FX 2, routes) are one joined control.
SEGMENT_NAMES = ('MixpiSegFirst', 'MixpiSegMid', 'MixpiSegLast')
# Sliders (spec s8): the fill runs the full height of the track up to the
# thumb's centre. The 48 px widget is the track; the thumb is 24 px wide.
SLIDER_HEIGHT, THUMB_WIDTH = 48, 24
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


def wrapper_size(size):
    """A wrapper's size: fixed axes become Maximum from 0, so a shown wrapper
    whose child is hidden takes no space (its size hint is then 0); expanding
    axes stay expanding."""
    return ','.join('0max' if part.endswith('f') else part for part in size.split(','))


def when_all(widget, size, *conditions):
    """Visible only while every (key, transform) condition is above 0."""
    key, transform = conditions[0]
    show_when(widget, key, transform=transform)
    for key, transform in conditions[1:]:
        widget = show_when(group('MixpiWhen', size=wrapper_size(size), children=[widget]), key,
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
# Sources (screen 1) is a side menu over the right of the page (spec s5), so
# each layout stays shown under it.
LOAD_MODE = (('[MixPi],sample_load', None),)
TRACKS_MODE = (('[MixPi],sample_load', '<Not/>'),)
# Spec s5 side menu: 320 px at the right (x 480-800), from under the header to
# the bottom of the screen.
SOURCES_MENU_WIDTH = 320
# Its shadow (spec 2d): a 40 px strip left of it, over the table (x 440-480).
SOURCES_MENU_SHADOW_WIDTH = 40


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


def shrinking_rows(e, short=LOOP_ROW_SHORT, full=LOOP_ROW):
    """Spec 2a: a height of FULL at 800x480 that gives way to SHORT at 800x444.
    Mixxx sets a non-fixed Size number as the minimum (LegacySkinParser::setupSize);
    MaximumSize caps the growth."""
    for c in list(e):
        if c.tag in ('Size', 'MaximumSize'):
            e.remove(c)
    at = list(e).index(e.find('Children')) if e.find('Children') is not None else len(e)
    if e.tag == 'PushButton':
        at = list(e).index(e.find('NumberStates'))
    e.insert(at, node('Size', f'0me,{short}me'))
    e.insert(at + 1, node('MaximumSize', f'-1,{full}'))
    return e


def close_button(key, transform='<Not/>'):
    """The close control (spec section 1): a 48 px square with the red ✕, at
    the right end of its header. It only writes KEY; it shows no state."""
    b = button('', key, size='48f,48f', push=True, name='MixpiClose', transform=transform)
    b.find('Connection/ConnectValueToWidget').text = 'false'
    return icon_states(b, 'mixpi-icon-close.svg', 'mixpi-icon-close.svg')


def segments(buttons):
    """Join buttons into one segmented control: first, middle and last names."""
    for index, b in enumerate(buttons):
        position = 0 if index == 0 else 2 if index == len(buttons) - 1 else 1
        b.find('ObjectName').text = SEGMENT_NAMES[position]
    return buttons


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


def rate_cell(channel, width, height):
    """Tempo % with the fader range above it (e.g. "±8%") from [MixPi],tempo_range,
    the native whole-percent range that Settings changes."""
    caption = node('Number')
    for k, v in dict(ObjectName='MixpiRange', Size='0me,16f', Text='±%1%', NumberOfDigits=0).items():
        prop(caption, k, v)
    connection(caption, '[MixPi],tempo_range', write=False)
    return group('MixpiRateCell', size=f'{width}f,{height}f', children=[
        caption, typed('NumberRate', channel, f'0me,{height - 16}f', 'MixpiRate', NumberOfDigits=1)])


def deck_chips(channel):
    """Plan 4.2 deck chips, display only, each shown while its control is above 0:
    ON PI (R-5), USB (N3's mixpi_from_usb: on a drive, not yet handed over), SYNC
    in the deck colour, MASTER (sync_leader) and PFL."""
    return [('ON PI', 'mixpi_on_pi', 52, 'MixpiChipPi'),
            ('USB', 'mixpi_from_usb', 40, 'MixpiChipUsb'),
            ('SYNC', 'sync_enabled', 48, f'MixpiChipSync{channel}'),
            ('MASTER', 'sync_leader', 64, 'MixpiChip'),
            ('PFL', 'pfl', 40, 'MixpiChip')]


def deck_info(channel, compact=False, size=None):
    """R-16 deck info. Compact: the 28 px title strip on Tracks. Full: 72 px,
    row 1 badge, title, dim artist and display chips; row 2 time, BPM, tempo, key."""
    key = f'[Channel{channel}]'
    badge = label(str(channel), '28f,28f' if compact else '24f,24f', f'MixpiDeckNumber{channel}',
                  align='center')
    if compact:
        title = typed('TrackProperty', channel, '0me,28f', 'MixpiDeckTitle',
                      Property='title', Elide='right', TooltipId='track_title')
        head = group('MixpiTitleStrip', 'horizontal', '0me,28f', [badge, title])
        return group('MixpiDeckInfo', size=size or '400me,28f', children=[head])
    # Spec s6 deck row: the title, then the dimmer artist right after it, then
    # the chips at the right end. The title is Maximum (it never grows past its
    # text; WLabel's size hint is the whole text) and the artist is Ignored (no
    # size hint, but it takes all the spare width). So when the chips need room,
    # Qt's layout takes it from the artist first ("…"), and only then from the
    # title. The minimums are primitives.css's (title 3.5em of 16 px, artist
    # 2.2em of 14 px). The title's 56 px also keeps its elided text non-empty,
    # so a new track's text always changes the label and Qt asks the layout
    # again (at 1 px every title elided to the same empty text and the row kept
    # its old widths). The strip's layout is not centred (QSS-P: AlignVCenter
    # only), so the row fills its half and the artist gets the spare width;
    # WWidgetGroup's default AlignCenter gave the row only its size hint, in
    # which the Ignored artist has no width (the C1 card preview).
    title = typed('TrackProperty', channel, f'{DECK_TITLE_MIN}max,24f', 'MixpiDeckTitle',
                  Property='title', Elide='right', TooltipId='track_title')
    artist = typed('TrackProperty', channel, f'{DECK_ARTIST_MIN}i,24f', 'MixpiDeckArtist',
                   Property='artist', Elide='right', TooltipId='track_title')
    head = group('MixpiTitleStrip', 'horizontal', f'0me,{DECK_TITLE}f', [
        badge, title, artist] + [chip(text, f'{key},{control}', f'{width}f,22f', name)
                                 for text, control, width, name in deck_chips(channel)])
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
        rate_cell(channel, widths['rate'], h),
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
    """LOOP / JUMP / CUES: one segmented control (spec s2), Choose role."""
    tabs = []
    for text, value in (('LOOP', 0), ('JUMP', 1), ('CUES', 2)):
        b = preset(text, '[MixPi],tool_tab', value, size='96f,48f')
        write(b, '[MixPi],cue_clear', 0)
        tabs.append(b)
    return segments(tabs)


def cue_clear_toggle():
    """CLEAR switches cue taps to clear (skin-only [MixPi],cue_clear). Two
    set-value buttons in one place, never a two-state toggle (F-1). CLEAR is
    Danger (spec section 1 roles); the cue tap that follows is the confirm."""
    on = button('CLEAR', '[MixPi],cue_clear', size='90f,48f', push=True, transform='<Not/>',
                display='[MixPi],cue_clear', name='MixpiDanger')
    off = button('CLEAR', '[MixPi],cue_clear', size='90f,48f', push=True, name='MixpiDanger')
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
    # Closing only writes zero; it does not mirror the selected deck into its state.
    close = close_button('[MixPi],loop_deck')
    write(close, '[MixPi],cue_clear', 0)
    heading = f'DECK {channel}'
    # Spec s2 header: the deck badge, "DECK n", the LOOP / JUMP / CUES
    # segments, and the close ✕ at the right end (CLEAR stays left of it on CUES).
    header = group('MixpiToolHeader', 'horizontal', '0me,48f', [
        gap('4f,48f'), label(str(channel), '32f,32f', f'MixpiWaveBadge{channel}', align='center'),
        label(heading, '96f,48f', 'MixpiToolTitle')] + tool_tabs(channel) + [
        gap('0me,48f'), cue_clear_toggle(), gap('8f,48f'), close, gap('4f,48f')])
    # LOOP (spec s2): the 12 sizes in two rows of six (Choose), then ½ and ×2
    # (neutral, green border), then EXIT LOOP (Danger) and RELOOP (Sound).
    # The rows and the body are MinimumExpanding with the short height as their
    # minimum and the full height as their maximum: at 800x480 the body is the
    # only growing item in the panel and fills its 204 px (four 48 px rows);
    # at 800x444 it gets its 168 px minimum (four 39 px rows). The skin knows
    # the window height only through this layout, as the other pages do.
    loop = shrinking_rows(group('MixpiLoopBody'), 4 * LOOP_ROW_SHORT + 3 * LOOP_GAP,
                          4 * LOOP_ROW + 3 * LOOP_GAP)
    for index, offset in enumerate((0, 6)):
        row = shrinking_rows(group('MixpiLoopRow', 'horizontal'))
        for text, value in LOOPS[offset:offset+6]:
            add(row, shrinking_rows(button(text, f'{key},beatloop_{value}_activate', momentary=True,
                                           display=f'{key},beatloop_{value}_enabled')))
        add(loop, *([gap(f'0me,{LOOP_GAP}f')] if index else []), row)
    sizes = shrinking_rows(group('MixpiLoopSizes', 'horizontal', children=[
        shrinking_rows(button('½', f'{key},loop_halve', momentary=True, name='MixpiSize')),
        shrinking_rows(button('×2', f'{key},loop_double', momentary=True, name='MixpiSize'))]))
    # m-loop.png draws both at rest while a loop is on (spec 2b): they show no
    # state, only the pressed look while pressed (Danger and Sound have no lit
    # state here).
    tools = shrinking_rows(group('MixpiLoopTools', 'horizontal', children=[
        shrinking_rows(button('EXIT LOOP', f'{key},loop_exit', momentary=True, name='MixpiDanger')),
        shrinking_rows(button('RELOOP', f'{key},reloop_toggle', momentary=True, name='MixpiSound'))]))
    for b in tools.find('Children'):
        b.find('Connection/ConnectValueToWidget').text = 'false'
    # Reloop jumps back to the saved loop. Disable it while already looping,
    # so a second tap cannot turn looping off (Exit has its own command).
    # Disabled, it keeps its at-rest look (mixpi-performance.qss, MixpiLoopTools).
    connection(tools.find('Children')[1], f'{key},loop_enabled', transform='<Not/>', bind='enabled')
    add(loop, gap(f'0me,{LOOP_GAP}f'), sizes, gap(f'0me,{LOOP_GAP}f'), tools)
    show_when(loop, '[MixPi],tool_tab', 0)
    # JUMP: beatjump_N_backward / _forward, two labelled rows of six (plan 5.3 hit map).
    # JUMP and CUES keep build B's layout (spec s2): their rows still start at
    # y 106, 6 px under the header's old bottom edge.
    jump = group('MixpiJumpBody', size='0me,146f', children=[gap('0me,6f')])
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
    cues = group('MixpiCuesBody', size='0me,168f', children=[gap('0me,6f')])
    for index, first in enumerate((1, 5)):
        add(cues, *([gap('0me,6f')] if index else []),
            group('MixpiCueRow', 'horizontal', f'0me,{CUE_TILE[1]}f',
                  [gap('8f,70f')] + [cue_tile(channel, n) for n in range(first, first + 4)] + [gap('0me,70f')]))
    add(cues, label("Pads 1-4 match the Starlight's hot cue pads. 5-8 are screen only.",
                    '0me,16f', 'MixpiScreenHint'))
    show_when(cues, '[MixPi],tool_tab', 2)
    # 48 header + 4 + 204 loop body = 256, the waveform area at 800x480. The
    # panel's height is Ignored, so it adds nothing to the page's minimum: at
    # 800x444 (desktop bar shown) the area is 220 px, and the LOOP body takes
    # 220 - 52 = 168 px (spec 2a). JUMP and CUES still fit at 444. The
    # trailing gap keeps JUMP and CUES at the top; it is hidden on LOOP, where
    # it would share the spare height with the body (Qt splits it evenly).
    tail = show_when(gap('0me,0me'), '[MixPi],tool_tab', 0, negate=True)
    panel = group('MixpiLoopPanel', size='0me,0i', children=[
        header, gap('0me,4f'), loop, jump, cues, tail])
    connection(panel, '[MixPi],loop_deck', transform=f'<IsEqual>{channel}</IsEqual>', bind='visible')
    return panel


def loops(channel, loop_display='focus'):
    """The deck tool panel; the name is kept for the loop-semantics tests."""
    return tool_panel(channel, loop_display)


def slider(key, name='MixpiDepth', size=f'0me,{SLIDER_HEIGHT}f'):
    """Spec s8 slider: the widget is the track (QSS: surface-2, a 1 px border).
    The fill, --mx-slider-fill, runs the full inner height from the left end
    to the thumb's centre. WSliderComposed draws the handle between 0 and
    width - 24 and the bar from BarMargins' start to start + value x (width -
    start - end); with margins 0,24 the bar (a pen as wide as the inner
    height, on the middle axis) ends at the thumb's left edge, and the handle
    image carries the fill colour on its left half, up to its centre."""
    e = node('SliderComposed')
    for k, v in dict(ObjectName=name, Size=size, Horizontal='true',
                     Handle='mixpi-slider-handle.svg', BarColor='#5d7238',
                     BarWidth=SLIDER_HEIGHT - 2, BarAxisPos=SLIDER_HEIGHT // 2,
                     BarMargins=f'0,{THUMB_WIDTH}').items():
        prop(e, k, v)
    connection(e, key)
    return e


def fx_unit(unit):
    """R-17: one effect unit. Unit 1 = the Starlight's deck A FX pads, unit 2 = deck B."""
    rack = f'[EffectRack1_EffectUnit{unit}]'
    deck = 'A' if unit == 1 else 'B'
    routes = ['[Channel1]', '[Channel2]', '[Master]']
    header = group('MixpiFxHeader', 'horizontal', '0me,56f', [gap('8f,56f'), label('ROUTE', '48f,48f', 'MixpiCaption')])
    buttons = []
    for index, (route, text) in enumerate(zip(routes, ['DECK 1', 'DECK 2', 'MASTER'])):
        key = f'{rack},group_{route}_enable'
        own = index == unit - 1
        b = button(f'{text} · PAD 4' if own else text, key, size='120f,48f',
                   push=True, display=key)
        # Disable other routes before enabling this one. Touch selection is
        # exclusive without changing per-effect depth or enable controls.
        first = b.find('Connection')
        b.remove(first)
        for other in routes:
            if other != route:
                connection(b, f'{rack},group_{other}_enable', read=False, transform='<Not/>')
        b.append(first)
        buttons.append(b)
    # Spec s8: the route segments, then MIX and its slider.
    add(header, *segments(buttons), gap('10f,56f'))
    add(header, group('MixpiFxMix', 'horizontal', '0me,56f', [
        label('MIX', '40f,48f', 'MixpiCaption'), slider(f'{rack},mix')]))
    cards = group('MixpiFxCards', 'horizontal', '0me,144f')
    for slot in range(1, 4):
        effect = f'[EffectRack1_EffectUnit{unit}_Effect{slot}]'
        select = node('EffectSelector')
        for k, v in dict(ObjectName='MixpiEffectSelector', EffectRack=1,
                         EffectUnit=unit, Effect=slot, Elide='right', Size='0me,48f').items():
            prop(select, k, v)
        # Spec s8: the effect ON/OFF is a button (Sound), lit and reading ON
        # when on, reading OFF at rest. Not a switch.
        on_off = button('OFF', f'{effect},enabled', size='76f,48f', state_labels=('OFF', 'ON'),
                        name='MixpiSound')
        add(cards, group('MixpiFxCard', children=[
            group('MixpiFxCardHead', 'horizontal', '0me,22f', [
                label(f'EFFECT {slot}', '0me,22f', 'MixpiCaption'),
                label(f'deck {deck} FX pad {slot}', '120f,22f', 'MixpiFxPad', align='right')]),
            group('MixpiFxCardRow', 'horizontal', '0me,48f', [select, on_off]),
            group('MixpiFxCardSlider', 'horizontal', f'0me,{SLIDER_HEIGHT}f', [
                gap('2f,48f'), slider(f'{effect},meta'), gap('2f,48f')])]))
    return show_when(group('MixpiFxUnit', size='0me,200f', children=[header, cards]),
                     '[MixPi],fx_unit', unit)


def fx():
    """R-17 and owner answer 5: FX 1 (deck A pads) and FX 2 (deck B pads), each
    with today's exclusive DECK 1 / DECK 2 / MASTER switcher, MIX and 3 cards."""
    switch = group('MixpiFxSwitch', 'horizontal', '0me,56f', [gap('8f,56f')])
    # Spec s8 mode segments, then the hint.
    add(switch, *segments([preset(text, '[MixPi],fx_unit', unit, size='196f,48f')
                           for text, unit in (('FX 1 · DECK A PADS', 1), ('FX 2 · DECK B PADS', 2))]),
        gap('2f,48f'))
    add(switch, label('Starlight FX pads: 1-3 effects · 4 send to deck',
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


def setting_row(title, sub, controls, height=66):
    """A Settings row: a 190 px label column, then 48 px choices."""
    labels = group('MixpiSettingText', size=f'190f,{height}f', children=[
        gap('0me,0me'), label(title, '0me,24f', 'MixpiSettingTitle', elide='right')] +
        # Sub-lines wrap to two lines (QSS word wrap on #MixpiSettingLabel).
        ([label(sub, '0me,34f', 'MixpiSettingLabel')] if sub else []) +
        [gap('0me,0me')])
    return group('MixpiSetting', 'horizontal', f'0me,{height}f',
                 [gap(f'14f,{height}f'), labels, gap(f'10f,{height}f')] + list(controls) +
                 [gap(f'0me,{height}f')])


def zoom_buttons():
    """Settings › Interface, Zoom (spec 2f): + then −, neutral 96 x 48 buttons
    like the page's other two-button rows, apart like Quantize's DECK 1 and
    DECK 2. Each tap writes 1, then 0 on release, as the Loop panel's − and +
    do; [MixPi],waveform_zoom_in/_out (mixxx-zoom-setting.patch) step the saved
    zoom and both decks' waveforms. They show no state."""
    buttons = []
    for text, key in (('+', '[MixPi],waveform_zoom_in'), ('−', '[MixPi],waveform_zoom_out')):
        b = button(text, key, size='96f,48f', momentary=True)
        b.find('Connection/ConnectValueToWidget').text = 'false'
        buttons.append(b)
    return [buttons[0], gap('6f,48f'), buttons[1]]


def choices(key, items, width=96):
    widths = width if isinstance(width, tuple) else (width,) * len(items)
    return [preset(text, key, value, size=f'{w}f,48f') for (text, value), w in zip(items, widths)]


def setting_note(text):
    """A note line under a Settings row (m-settings-media.png): the full row
    width, dim text on surface with a 2 px accent edge at the left."""
    return group('MixpiSettingNoteRow', 'horizontal', '0me,44f', [
        gap('14f,44f'), label(text, '0me,36f', 'MixpiSettingNote'), gap('14f,44f')])


def eject_indicator():
    """Settings › Media, Eject (m-settings-media.png): the ON/OFF toggle, 88 px
    wide, the word and the knob, from [MixPi],media_eject_available. It is an
    indicator only: no button, nothing written, so no setting or skin change
    can open the eject gate (rubric criterion 4)."""
    def toggle(on):
        word = label('ON' if on else 'OFF', '0me,46f', 'MixpiToggleWord', align='center')
        knob = group('MixpiToggleKnobCell', 'horizontal', '42f,46f', [
            gap('0me,46f'), label('', '32f,32f', 'MixpiToggleKnob'), gap('0me,46f')])
        parts = [word, knob] if on else [knob, word]
        return group('MixpiToggleOn' if on else 'MixpiToggleOff', 'horizontal', '88f,48f', parts)
    return group('MixpiEjectState', 'horizontal', '88f,48f', [
        show_when(toggle(True), '[MixPi],media_eject_available'),
        show_when(toggle(False), '[MixPi],media_eject_available', negate=True)])


def brightness():
    """Settings › Interface, Brightness (m-settings-interface.png): the slider
    on [MixPi],backlight (N-C: a potmeter, 5-100 %), enabled while
    [MixPi],backlight_available, then the "80%" readout."""
    level = slider('[MixPi],backlight', size=f'{BRIGHTNESS_SLIDER}f,{SLIDER_HEIGHT}f')
    connection(level, '[MixPi],backlight_available', bind='enabled')
    readout = node('Number')
    for k, v in dict(ObjectName='MixpiSettingValue', Size='56f,48f', Text='%1%', NumberOfDigits=0).items():
        prop(readout, k, v)
    connection(readout, '[MixPi],backlight', write=False)
    return [level, readout]


def rail_row(text, value):
    """A Settings rail row (spec section 1, current menu row): the label is
    left-aligned as drawn. WPushButton draws its text centred across the whole
    button (no padding), so a label under a clear button carries the text; the
    label lights from the page: surface-2, a 4 px accent edge, semibold."""
    b = preset('', '[MixPi],settings_page', value, size=f'{SETTINGS_RAIL}f,{RAIL_ROW}f')
    b.find('ObjectName').text = 'MixpiRailButton'
    text_label = label(text, f'{SETTINGS_RAIL}f,{RAIL_ROW}f', 'MixpiRailLabel')
    connection(text_label, '[MixPi],settings_page', transform=f'<IsEqual>{value}</IsEqual>',
               bind='highlight')
    # The first child of a stacked group is on top: the button takes the taps.
    return group('MixpiRailRow', 'stacked', f'{SETTINGS_RAIL}f,{RAIL_ROW}f', [b, text_label])


def settings():
    """R-18: Settings is a full screen (screen 5) with a rail of four panes."""
    # Spec s11/s12 header: "SETTINGS", the hint, and the close ✕ at the right.
    header = group('MixpiSettingsHeader', 'horizontal', f'0me,{TOP_HEIGHT}f', [
        gap('4f,48f'), label('SETTINGS', '110f,48f', 'MixpiScreenTitle'),
        label('Every change saves within a second.', '0me,48f', 'MixpiScreenHint', elide='right'),
        # R-13 pulses [MixPi],saved for 2 s after each save.
        show_when(label('Saved', '90f,48f', 'MixpiSavedNote', align='center'), '[MixPi],saved'),
        close_button(SCREEN), gap('4f,48f')])
    rail = group('MixpiSettingsRail', size=f'{SETTINGS_RAIL}f,0me')
    for text, value in SETTINGS_PAGES:
        add(rail, rail_row(text, value))
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
    # Spec s12 (m-settings-interface.png). The button reads "SHOW TOP BAR";
    # its other states are build B's, in the same upper case.
    bar = button('TOP BAR UNAVAILABLE', '[MixPi],desktop_bar', push=True, name='MixpiDesktopBar',
                 state_labels=('SHOW TOP BAR', 'HIDE TOP BAR', 'CHECKING TOP BAR…',
                               'TOP BAR UNAVAILABLE'), size=f'{DESKTOP_BAR_WIDTH}f,48f')
    connection(bar, '[MixPi],desktop_bar_available', bind='enabled')
    interface = group('MixpiInterfaceSettings', children=[
        setting_row('Desktop bar', 'Desktop · Mixxx · Speaker · Settings', [bar], height=INTERFACE_ROW),
        setting_row('Deck time', 'Tap the time on a deck to switch',
                    segments(choices('[Controls],ShowDurationRemaining',
                                     [('ELAPSED', 0), ('REMAINING', 1)], (96, 104))), height=INTERFACE_ROW),
        setting_row('Brightness', 'Screen backlight', brightness(), height=INTERFACE_ROW),
        setting_row('Night dim', 'Drops the screen to a low level for dark rooms',
                    segments(choices('[MixPi],night_dim', [('OFF', 0), ('ON', 1)])), height=INTERFACE_ROW),
        setting_row('CPU readout', 'The CPU % at the top right',
                    segments(choices('[MixPi],show_cpu', [('SHOW', 1), ('HIDE', 0)])), height=INTERFACE_ROW),
        # Spec 2f: the last row, no subtext.
        setting_row('Zoom', '', zoom_buttons(), height=ZOOM_ROW),
        gap('0me,0me')])
    media = group('MixpiMediaSettings', children=[
        # N2: [MixPi],scan_bar_hidden 0/1 (also saved as ScanBarHidden).
        setting_row('Scan bar', 'Hidden: the % shows on the USB chip',
                    segments(choices('[MixPi],scan_bar_hidden', [('SHOW', 0), ('HIDE', 1)]))),
        setting_row('RAM cache', 'MB. Also the room for handover copies. Next launch.',
                    segments(choices('[MixPi],cache_mb', [('OFF', 0), ('512', 512), ('1024', 1024)]))),
        setting_row('Eject', 'Safe eject on this card', [eject_indicator()]),
        # U-8: [MixPi],drive_insert (N-B, wave C1): 0 ASK, 1 AUTO LOAD.
        setting_row('Plugging in a drive', 'What happens when a drive goes in',
                    segments(choices('[MixPi],drive_insert', [('ASK', 0), ('AUTO LOAD', 1)], (96, 104)))),
        setting_note('ASK shows a small strip with LOAD and DISMISS. AUTO LOAD opens the drive at once.'),
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


def load_to_pad(sampler, size, name, text, to_sampler=True):
    """[SamplerN],LoadSelectedTrack on press and release, then back to the Sampler
    tab, or (TO_SAMPLER false: Choose pad opened from Tracks' Actions) to Tracks."""
    b = button(text, f'[Sampler{sampler}],LoadSelectedTrack', size=size, momentary=True, name=name)
    # A playing pad cannot take a new sound (the rule of the old LOAD TO row).
    connection(b, f'[Sampler{sampler}],play', transform='<Not/>', bind='enabled')
    if to_sampler:
        write(b, '[Tab],sampler', 1, 'release')
    reset_views(b, when='release')
    return b


def browse_page(library, overview):
    """Tracks (screen 0), Sources (1), Load sample (3) and Choose pad (4) share one
    Library, sidebar and search box. Only fixed-content layouts change."""
    parts = toolbar_parts(library)
    search, actions = parts['SearchBox'], parts['LibraryActionsButton']
    # The native side menu has its own BACK and EDIT (mixxx-sources-menu.patch),
    # so the skin's LibraryBackButton and LibrarySourcesButton (build B's EDIT
    # LIST) are left out.
    sidebar_button = parts['SidebarButton']

    # ☰ / ✕ (R-11, spec s5): the existing two-state key; open also writes
    # screen 1. Open, it is the standard close control (QSS-T: no lit state).
    fixed_size(sidebar_button, '48f,48f')
    icon_states(sidebar_button, 'mixpi-icon-menu.svg', 'mixpi-icon-close.svg')
    connection(sidebar_button, SCREEN, read=False, transform=f'<IsEqual>{SCREEN_SOURCES}</IsEqual>')
    # ✎ (R-11): Actions keeps its key and object name; the native menu anchors under it.
    fixed_size(actions, '48f,48f')
    icon_states(actions, 'mixpi-icon-pen.svg', 'mixpi-icon-pen.svg')
    fixed_size(search, '250me,44f')
    # A SearchBox takes no Connection (LegacySkinParser::parseSearchBox), so a
    # group carries its visibility.
    search = group('MixpiSearch', 'horizontal', '250me,48f', [search])

    # Sources opened from Load sample returns there.
    sample_sources_close = close_button('[Sidebar],sidebar_visible')
    write(sample_sources_close, SCREEN, SCREEN_LOAD_SAMPLE)
    load_close = close_button('[Tab],sampler', transform=None)
    reset_views(load_close)
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

    load_head = when_all(group('MixpiLoadHead', 'horizontal', '310f,48f', [
        label('LOAD SAMPLE', '130f,48f', 'MixpiScreenTitle'), sample_hints()]),
        '310f,48f', *LOAD_MODE)
    actions_cell = when_all(group('MixpiActionsCell', 'horizontal', '56f,48f', [gap('8f,48f'), actions]),
                            '56f,48f', *TRACKS_MODE)
    # Spec s3/s5/s7: left to right, the Load sample title and hint, the search
    # (it fills the space), ✎ (Tracks), and the ☰ / ✕ slot at the right end.
    # Sources keeps this header: search, ✎, and ☰ turned into ✕.
    header = group('MixpiBrowseHeader', 'horizontal', f'0me,{TOP_HEIGHT}f', [
        gap('4f,48f'), load_head, search, actions_cell, gap('8f,48f'), slot, gap('4f,48f')])

    # Sources (spec s5): the native side menu, 320 px at the right end, over
    # the page from under the header to the bottom (x 480-800, y 96-480). The
    # right-overlay layout puts its second child over the first's right side.
    sidebar = parts['SidebarWrapper']
    fixed_size(sidebar, f'{SOURCES_MENU_WIDTH}f,0me')
    menu = show_when(group('MixpiSourcesMenu', size=f'{SOURCES_MENU_WIDTH}f,0me', children=[sidebar]),
                     SCREEN, SCREEN_SOURCES)

    # Load sample: a row of sources, the list, and one LOAD TO PAD button.
    open_sources = button('SOURCES…', '[Sidebar],sidebar_visible', size=f"{SOURCE_ROW['SOURCES…']}f,48f",
                          push=True)
    open_sources.find('Connection/ConnectValueToWidget').text = 'false'
    write(open_sources, SCREEN, SCREEN_SOURCES)
    source_row = group('MixpiSampleSources', 'horizontal', '0me,56f', [gap('8f,48f')])
    # N4's sample browser: [MixPi],sample_source reads back what is shown (1
    # Samples, 2 This Pi, 3 USB, 4 Recordings, 0 a list picked in Sources).
    # Spec s7 (R-8 override): only SAMPLES has a button here; This Pi and
    # Recordings are reached through SOURCES…. SAMPLES writes 1 and lights from it.
    width = SOURCE_ROW['SAMPLES']
    samples = preset('SAMPLES', '[MixPi],sample_source', 1, size=f'{width}f,48f')
    cell = group('MixpiSourceCell', 'horizontal', f'{width + 8}f,48f', [samples, gap('8f,48f')])
    add(source_row, when_all(cell, f'{width + 8}f,48f', ('[MixPi],sample_source_available', None)))
    add(source_row, open_sources,
        label('Or a list picked in Sources.', '0me,48f', 'MixpiScreenHint', elide='right'))
    source_row = when_all(source_row, '0me,56f', *LOAD_MODE)

    # The table narrows to x 0-480 while the menu is open, so its scroll bar
    # stays at its right edge (x 456-480), left of the menu.
    table = group('MixpiLibraryMain', 'horizontal', children=[
        parts['Library'],
        show_when(gap(f'{SOURCES_MENU_WIDTH}f,0me', 'MixpiSourcesRoom'), SCREEN, SCREEN_SOURCES)])
    titles = decks(compact=True)
    titles.find('ObjectName').text = 'MixpiTrackTitles'
    titles = when_all(titles, '0me,28f', *TRACKS_MODE)
    # While the menu is open the screen's bottom rows (overviews and the LOAD
    # row) are hidden, as under every full-screen view, so the page carries
    # its own copy under the menu: the menu covers deck 2's half of them
    # (m-sources-top.png). The overviews hide while the full-screen edit list
    # is open.
    overviews = group('MixpiSourcesOverviews', 'horizontal', f'0me,{OVERVIEW_HEIGHT}f')
    for channel in (1, 2):
        add(overviews, fixed_size(concrete(overview, channel), f'400me,{OVERVIEW_HEIGHT}f'))
    show_when(overviews, '[Library],sidebar_sources_editing', negate=True)
    loads = group('MixpiSourcesTransport', 'horizontal', f'0me,{TRANSPORT_HEIGHT}f', [
        group('MixpiSourcesDeck', 'horizontal', f'400me,{TRANSPORT_HEIGHT}f', tracks_controls(channel))
        for channel in (1, 2)])
    sources_bottom = when_all(group('MixpiSourcesBottom', size=f'0me,{OVERVIEW_HEIGHT + TRANSPORT_HEIGHT}f',
                                    children=[overviews, loads]),
                              f'0me,{OVERVIEW_HEIGHT + TRANSPORT_HEIGHT}f', on_screen(SCREEN_SOURCES),
                              *TRACKS_MODE)

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

    base = group('MixpiBrowseBase', children=[source_row, table, titles, sources_bottom, footer])
    # The menu's shadow (spec 2d, m-sources-top.png, m-sources-sub.png): a
    # 40 px gradient strip (mixpi-sources-menu.qss) on the menu's left edge,
    # over the table, x 440-480. The right-overlay's third child
    # (mixxx-sources-menu-shadow.patch) is placed against the menu and lets
    # touches through to the table. A plain gradient, no graphics effect.
    shadow = show_when(group('MixpiSourcesMenuShadow', size=f'{SOURCES_MENU_SHADOW_WIDTH}f,0me'),
                       SCREEN, SCREEN_SOURCES)
    body = group('MixpiBrowseBody', 'right-overlay', children=[base, menu, shadow])
    wrapper = group('LibraryWrapper', children=[header, body])
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


def sampler_title(sampler, size, name='MixpiSamplerTitle', prop_name='titleInfo', align=None):
    title = node('TrackProperty')
    for k, v in dict(ObjectName=name, Group=f'[Sampler{sampler}]', Property=prop_name,
                     Elide='right', Size=size).items():
        prop(title, k, v)
    if align:
        prop(title, 'Alignment', align)
    return title


def pad_head(sampler, rest):
    """A pad's top row: the badge and pad label (64 px, fixed) at the left,
    then REST, which holds an expanding gap so the row fills the pad."""
    return group('MixpiPadHead', 'horizontal', '0me,24f', [pad_tag(sampler, '64f,24f')] + rest)


def choose_pad():
    """Choose pad (screen 4): a sheet over the dimmed list, 8 tiles in the pad order."""
    tiles = []
    for sampler in range(1, SAMPLERS + 1):
        key = f'[Sampler{sampler}]'
        info = group('MixpiChooseInfo', size='165f,96f', children=[
            pad_tag(sampler),
            show_when(sampler_title(sampler, '0me,40f', 'MixpiChooseName'), f'{key},track_loaded'),
            show_when(label('Empty', '0me,40f', 'MixpiChooseEmpty'), f'{key},track_loaded', negate=True)])
        # Opened from Load sample (sample_load 1): back to the Sampler. Opened
        # from Tracks' Actions menu (N4: sample_pad 0, screen 4, sample_load 0):
        # back to Tracks. Exactly one of the two is shown, above the labels.
        from_sample = show_when(load_to_pad(sampler, '165f,96f', 'MixpiChooseTile', ''),
                                '[MixPi],sample_load')
        from_tracks = show_when(load_to_pad(sampler, '165f,96f', 'MixpiChooseTile', '', to_sampler=False),
                                '[MixPi],sample_load', negate=True)
        tiles.append(group('MixpiChooseCell', 'stacked', '165f,96f', [from_sample, from_tracks, info]))
    rows = []
    for row in (tiles[:4], tiles[4:]):
        cells = [gap('18f,96f')]
        for index, tile in enumerate(row):
            cells += ([gap('8f,96f')] if index else []) + [tile]
        rows.append(group('MixpiChooseRow', 'horizontal', '0me,96f', cells + [gap('18f,96f')]))
    # The close ✕ at the right of the title (spec section 1; it replaces build
    # B's CANCEL) returns where Choose pad came from: Load sample (screen 3) or
    # Tracks (0). One ✕ per origin, exactly one shown.
    closes = []
    for value, negate in ((SCREEN_LOAD_SAMPLE, False), (SCREEN_NONE, True)):
        close = close_button(SCREEN, transform=f'<IsEqual>{value}</IsEqual>' if value else '<Not/>')
        closes.append(show_when(close, '[MixPi],sample_load', negate=negate))
    sheet = group('MixpiChooseSheet', size='720f,340f', children=[
        gap('0me,16f'),
        group('MixpiChooseTitleRow', 'horizontal', '0me,48f', [
            gap('18f,48f'), label('Load to which pad?', '0me,48f', 'MixpiSheetTitle'),
            *closes, gap('8f,48f')]),
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
    """Spec s6 (m-sampler.png): a loaded pad shows its number, label, duration
    and name, and ▶ TRIGGER (Sound, lit while it plays) and ■ STOP (Caution);
    the pad has the play-coloured edge while it plays. An empty pad reads
    "+ Empty · tap to load" and opens Load sample."""
    key = f'[Sampler{sampler}]'
    width, height = PAD_SIZE
    info = group('MixpiPadInfo', size=f'{width}f,{PAD_INFO}f', children=[
        # m-sampler.png: the badge and label at the pad's left edge, the
        # duration at its right edge. Fixed widths plus an expanding gap, so
        # WWidgetGroup's default AlignCenter cannot centre them (C2 card preview).
        pad_head(sampler, [
            chip('ON PI', f'{key},mixpi_on_pi', '48f,20f', 'MixpiChipPi'), gap('0me,24f'),
            sampler_title(sampler, '56f,24f', 'MixpiPadTime', 'durationTextSeconds', align='right')]),
        sampler_title(sampler, '0me,24f', 'MixpiPadName')])
    button_width = (width - 3 * PAD_GAP) // 2
    trigger = button('▶ TRIGGER', f'{key},cue_gotoandplay', size=f'{button_width}f,{PAD_STRIP}f',
                     momentary=True, display=f'{key},play', name='MixpiSound')
    connection(trigger, f'{key},track_loaded', bind='enabled')
    stop = button('■ STOP', f'{key},stop', size=f'{button_width}f,{PAD_STRIP}f', momentary=True,
                  name='MixpiCaution')
    loaded = group('MixpiPadLoaded', size=f'{width}f,{height}f', children=[
        info,
        group('MixpiPadStrip', 'horizontal', f'{width}f,{PAD_STRIP}f', [
            gap(f'{PAD_GAP}f,48f'), trigger, gap(f'{PAD_GAP}f,48f'), stop, gap(f'{PAD_GAP}f,48f')]),
        gap(f'0me,{height - PAD_INFO - PAD_STRIP}f')])
    # The play-coloured edge while the pad plays (is-playing in m-sampler.png).
    connection(loaded, f'{key},play', bind='highlight')
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
            pad_head(sampler, [gap('0me,24f')]),
            label('+ Empty · tap to load', '0me,0me', 'MixpiPadEmptyText',
                                    align='center')])])
    show_when(empty, f'{key},track_loaded', negate=True)
    return group(f'MixpiPad{"A" if sampler <= 4 else "B"}', size=f'{width}f,{height}f',
                 children=[loaded, empty])


def clear_row(sampler):
    """One row of the Clear samples popover (m-sampler-clear.png), shown while
    the pad is loaded: the tick, the pad badge and label, the name and the
    duration. A ticked row is surface-2 (spec section 1: the tick and the
    background, no left edge).

    The row is the tick row (spec section 1): a transparent button the width
    of the row is on top and takes every tap on it. It has no image, because
    an image drawn FIXED makes a button the image's size (WPushButton calls
    setFixedSize), which left only the 52 px tick box tappable on the card.
    Two set-value buttons in one place, as CLEAR on CUES (F-1), never a
    two-state toggle: the clear row writes 1, the ticked row writes 0, and
    exactly one is shown. Under them, display-only (no connection but its
    visibility), the tick box: a 52 px image at the row's left (FIXED: drawn
    from the top-left corner, unscaled)."""
    key = f'[Sampler{sampler}]'
    tick_key = f'[MixPi],sampler_clear_tick{sampler}'
    taps, ticks = [], []
    for ticked in (True, False):
        tap = button('', tick_key, size=f'0me,{CLEAR_ROW}f', push=True, name='MixpiClearRowTap',
                     transform='<Not/>' if ticked else None)
        tap.find('Connection/ConnectValueToWidget').text = 'false'
        taps.append(show_when(tap, tick_key, negate=not ticked))
        box = button('', tick_key, size=f'{CLEAR_TICK_SPACE}f,{CLEAR_ROW}f', name='MixpiClearTick')
        box.remove(box.find('Connection'))
        icon_states(box, 'mixpi-clear-row-on.svg' if ticked else 'mixpi-clear-row-off.svg')
        ticks.append(show_when(box, tick_key, negate=not ticked))
    text = group('MixpiClearRowText', 'horizontal', f'0me,{CLEAR_ROW}f', [
        gap(f'{CLEAR_TICK_SPACE}f,{CLEAR_ROW}f'), pad_tag(sampler, f'64f,{CLEAR_ROW}f'),
        gap(f'8f,{CLEAR_ROW}f'),
        sampler_title(sampler, f'0me,{CLEAR_ROW}f', 'MixpiClearName'),
        sampler_title(sampler, f'56f,{CLEAR_ROW}f', 'MixpiClearTime', 'durationTextSeconds'),
        gap(f'16f,{CLEAR_ROW}f')])
    connection(text, tick_key, bind='highlight')
    # The first shown child of a stacked group is on top: the row button takes
    # the taps; the tick box is drawn over the text.
    row = group('MixpiClearRow', 'stacked', f'0me,{CLEAR_ROW}f', taps + ticks + [text])
    return show_when(row, f'{key},track_loaded')


def clear_popover():
    """CLEAR SAMPLES… (spec s6, m-sampler-clear.png): a 480 px sheet over the
    dimmed screen. N-C's controls: [MixPi],sampler_clear_open (1 opens it and
    clears every tick), sampler_clear_tick1-8, sampler_clear_count (ticked
    loaded pads, read only) and sampler_clear (1 clears the ticked pads and
    closes)."""
    close = close_button('[MixPi],sampler_clear_open')
    head = group('MixpiClearHead', 'horizontal', '0me,56f', [
        label('CLEAR SAMPLES', '0me,56f', 'MixpiSheetTitle'), close, gap('4f,56f')])
    rows = group('MixpiClearRows', size='0me,0min', children=[clear_row(n) for n in range(1, SAMPLERS + 1)])
    # More loaded pads than fit scroll, with the 24 px bar at the right edge.
    # A QScrollArea keeps the first size hint of its rows (taken at start,
    # before the samples load), so its height hint is ignored here. Under it,
    # in the same place, a space of 52 px per loaded pad gives the list its
    # height, up to CLEAR_LIST_MAX: every loaded row shows, and the bar shows
    # only when they do not fit.
    scroll = node('Scrollable')
    for k, v in dict(ObjectName='MixpiClearList', Size='0me,0i', HorizontalScrollBarPolicy='off').items():
        prop(scroll, k, v)
    ET.SubElement(scroll, 'Children').append(rows)
    space = group('MixpiClearListSpace', size='0me,0min', children=[
        show_when(gap(f'0me,{CLEAR_ROW}f'), f'[Sampler{n}],track_loaded') for n in range(1, SAMPLERS + 1)])
    listing = group('MixpiClearListArea', 'stacked', '0me,0p', [scroll, space])
    prop(listing, 'MaximumSize', f'{CLEAR_SHEET_WIDTH},{CLEAR_LIST_MAX}')
    note = label('The pads go empty. The files stay where they are.', '0me,40f', 'MixpiClearNote')
    cancel = button('CANCEL', '[MixPi],sampler_clear_open', size='120f,48f', push=True, transform='<Not/>')
    cancel.find('Connection/ConnectValueToWidget').text = 'false'
    # CLEAR (n): Danger, n = [MixPi],sampler_clear_count; not enabled at 0.
    confirm = button('CLEAR (0)', '[MixPi],sampler_clear', size='120f,48f', push=True,
                     display='[MixPi],sampler_clear_count', name='MixpiClearConfirm',
                     state_labels=tuple(f'CLEAR ({n})' for n in range(SAMPLERS + 1)))
    connection(confirm, '[MixPi],sampler_clear_count', bind='enabled')
    foot = group('MixpiClearFoot', 'horizontal', '0me,68f', [
        gap('0me,68f'), cancel, gap('8f,68f'), confirm, gap('12f,68f')])
    sheet = group('MixpiClearSheet', size=f'{CLEAR_SHEET_WIDTH}f,0p', children=[head, listing, note, foot])
    middle = group('MixpiClearCenter', 'horizontal', '0me,0p', [gap('0me,0me'), sheet, gap('0me,0me')])
    # Ignored size: the hidden popover adds nothing to the window's minimum.
    scrim = group('MixpiClearScrim', size='0i,0i', children=[
        gap(f'0me,{CLEAR_MARGIN}me'), middle, gap(f'0me,{CLEAR_MARGIN}me')])
    # One condition only: in a stacked group a shown wrapper whose child is
    # hidden still covers everything under it and takes the taps. Only the
    # Sampler page opens it, and while it is open the scrim covers the tabs.
    return show_when(scrim, '[MixPi],sampler_clear_open')


def sampler_page():
    # Spec s6 header: + LOAD SAMPLE (Confirm), CLEAR SAMPLES… (Danger), the hint.
    load = button('+ LOAD SAMPLE', '[Tab],library', size=f'{SAMPLER_LOAD}f,48f', push=True,
                  name='MixpiPrimary')
    load.find('Connection/ConnectValueToWidget').text = 'false'
    reset_views(load, keep=('[MixPi],sample_load', SCREEN))
    write(load, '[MixPi],sample_load', 1)
    write(load, SCREEN, SCREEN_LOAD_SAMPLE)
    clear = button('CLEAR SAMPLES…', '[MixPi],sampler_clear_open', size=f'{SAMPLER_CLEAR}f,48f', push=True,
                   name='MixpiDanger')
    clear.find('Connection/ConnectValueToWidget').text = 'false'
    # R-13 pulses [MixPi],saved after each save; until then the note stays hidden.
    saved = show_when(label('Bank saved', '110f,48f', 'MixpiSavedNote', align='center'), '[MixPi],saved')
    header = group('MixpiSamplerHeader', 'horizontal', f'0me,{TOP_HEIGHT}f', [
        gap('4f,48f'), load, gap('8f,48f'), clear, saved,
        label('Starlight SAMPLER mode: deck A pads 1-4 · deck B pads 5-8', '0me,48f',
              'MixpiScreenHint', align='right', elide='right'), gap('4f,48f')])
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
    """A tab writes its page and closes every view (plan 4.1: every tab writes screen 0).

    While Settings is open the WidgetStack is hidden, and a hidden WWidgetStack
    ignores its page triggers; when it shows again it takes the page from
    [Tab],current. So the tab also writes [Tab],current, before screen 0."""
    b = button(text, f'[Tab],{key}', size=f'{width}f,48f', push=True, name='MixpiTab')
    write(b, '[Tab],current', PAGES.index(key))
    return reset_views(b)


def tab_stack(text, key, width):
    """A tab and its twins in one place. Qt puts the first child of a stacked
    group on top, so the last child, an unlit twin, is always there underneath:
    - SAMPLER only: a twin lit from [MixPi],sample_load (Load sample, Choose pad,
      Sources opened from Load sample);
    - the normal tab, lit from its page, unless Settings is open (the gear is
      lit then), the Media page is open (the USB chip is lit then; spec s13,
      m-media.png) or, for TRACKS and SAMPLER, a sample screen is open.
    All of them send the same writes."""
    size = f'{width}f,48f'

    def unlit():
        b = tab(text, key, width)
        b.find('Connection/ConnectValueToWidget').text = 'false'
        return b
    # One condition per stacked level, each level with its own unlit base: a
    # shown group whose only child is hidden would still cover what is under it.
    conditions = ([('[MixPi],sample_load', '<Not/>')] if key in ('library', 'sampler') else []) + \
        [off_screen(SCREEN_SETTINGS), off_screen(SCREEN_MEDIA)]
    widget = tab(text, key, width)
    for condition_key, condition in conditions:
        show_when(widget, condition_key, transform=condition)
        widget = group('MixpiTabPair', 'stacked', size, [widget, unlit()])
    if key == 'sampler':
        lit = unlit()
        connection(lit, '[MixPi],sample_load', write=False)
        # Not lit over the Media page either: an unlit twin under it.
        media_key, not_media = off_screen(SCREEN_MEDIA)
        lit = group('MixpiTabPair', 'stacked', size, [show_when(lit, media_key, transform=not_media), unlit()])
        widget.find('Children').insert(0, show_when(lit, '[MixPi],sample_load'))
    return widget


def usb_chip():
    """R-4 skin part: the 150x48 chip writes [MixPi],media_load (today's dialog,
    N3's Media screen). Its look follows [MixPi],media_state; MixpiUsbName is set
    from native code to the drive name; SCAN NN% shows while a hidden scan runs."""
    # Screen 2 (Media) first: the skin hides every waveform row before the native
    # page shows, so no GL surface is ever above it (build B, R-2/R-4).
    # Lit while the Media page is open, as the gear is on Settings (spec s13,
    # m-media.png): the button reads screen == 2.
    tap = button('', SCREEN, size=f'{USB_CHIP}f,48f', push=True, name='MixpiUsbButton',
                 transform=f'<IsEqual>{SCREEN_MEDIA}</IsEqual>')
    write(tap, '[MixPi],media_load', 1)
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


def record_button():
    """REC: build B's four states (● REC, WAIT, ■ STOP, ■ STOP) on one button.
    At rest the mockups draw a red 9 px dot (--mx-danger) before REC (spec 2b,
    m-tracks.png). A button draws its text in one colour, so at rest the face
    under the button draws the dot and REC, centred as one; the button on top
    is transparent then and takes the taps. WAIT and ■ STOP are the button's
    own text, as in build B."""
    tap = button('', '[Recording],toggle_recording', size=f'{REC_WIDTH}f,48f', momentary=True,
                 display='[Recording],status', name='MixpiRecord',
                 state_labels=('', 'WAIT', '■ STOP', '■ STOP'))
    face = group('MixpiRecordFace', 'horizontal', f'{REC_WIDTH}f,48f', [
        gap('0me,48f'), label('', '9f,9f', 'MixpiRecordDot'), gap('7f,48f'),
        label('REC', '0min,48f', 'MixpiRecordText', align='center'), gap('0me,48f')])
    show_when(face, '[Recording],status', 0)
    # In a stacked group the first child is on top: the button takes the taps.
    return group('MixpiRecordChip', 'stacked', f'{REC_WIDTH}f,48f', [tap, face])


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
    record = record_button()
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
    # Spec s12 CPU readout: shown while [MixPi],show_cpu is 1 (N-C). The box
    # keeps its 56 px, so the chip, REC and the gear stay where they are.
    readout = show_when(group('MixpiCpuReadout', size=f'{CPU_WIDTH}f,48f', children=[cpu_label, cpu_value]),
                        '[MixPi],show_cpu')
    add(top, group('MixpiCpuBox', size=f'{CPU_WIDTH}f,48f', children=[readout]))
    return top


def loop_button(channel):
    """LOOP (Sound, info tone) opens the tool panel; it is lit while the panel
    is open, and while a loop plays (a Starlight loop pad shows on screen)."""
    def one(display, transform):
        b = button('LOOP', '[MixPi],loop_deck', size=f"{TRANSPORT['LOOP']}f,48f", push=True,
                   transform=f'<IsEqual>{channel}</IsEqual>', name='MixpiSound')
        b.find('Connection/ConnectValueToWidget').text = 'false'
        write(b, '[Tab],overview', 1)
        write(b, '[MixPi],sample_load', 0)
        connection(b, display, write=False, transform=transform)
        return b
    is_open = one('[MixPi],loop_deck', f'<IsEqual>{channel}</IsEqual>')
    show_when(is_open, '[MixPi],loop_deck', channel)
    looping = one(f'[Channel{channel}],loop_enabled', None)
    pair = group('MixpiLoopPair', 'stacked', f"{TRANSPORT['LOOP']}f,48f", [is_open, looping])
    return show_when(pair, '[Tab],library', negate=True)


def tracks_controls(channel):
    """Tracks' row for one deck (spec s3): LOAD n · the track name · CUE · ▶."""
    key = f'[Channel{channel}]'
    # LOAD sends press and release like the sampler pads, and is off while the deck plays (F-3).
    load = button(f'LOAD {channel}', f'{key},LoadSelectedTrack', size=f'{LOAD_WIDTH}f,48f',
                  momentary=True, name=f'MixpiLoad{channel}')
    connection(load, f'{key},play', transform='<Not/>', bind='enabled')
    title = typed('TrackProperty', channel, f'0me,48f', 'MixpiLoadTitle',
                  Property='title', Elide='right', TooltipId='track_title')
    title_cell = group('MixpiLoadCell', 'horizontal', '0me,48f', [
        show_when(title, f'{key},play', negate=True),
        show_when(label('Playing · stop to load', '0me,48f', 'MixpiLoadTitle', elide='right'),
                  f'{key},play')])
    tracks_cue = button('CUE', f'{key},cue_default', size=f'{TRACKS_CUE}f,48f', momentary=True,
                        name='MixpiCue')
    tracks_play = button('▶', f'{key},play', size=f'{TRACKS_PLAY}f,48f', name='MixpiPlay')
    return [load, title_cell, tracks_cue, tracks_play]


def transport_row(channel):
    """The same row on Decks, FX and Sampler. Tracks (spec s3): LOAD n · the
    track name · CUE · ▶, with ▶ right of CUE on both decks."""
    key = f'[Channel{channel}]'
    deck_name = f'MixpiDeck{channel}'
    off_tracks = lambda e: show_when(e, '[Tab],library', negate=True)
    on_tracks = lambda e: show_when(e, '[Tab],library')
    keylock = off_tracks(button('KEY', f'{key},keylock', size=f"{TRANSPORT['KEY']}f,48f", name=deck_name))
    quantize = off_tracks(button('Q', f'{key},quantize', size=f"{TRANSPORT['Q']}f,48f", name=deck_name))
    sync = off_tracks(button('SYNC', f'{key},sync_enabled', size=f"{TRANSPORT['SYNC']}f,48f", name=deck_name))
    load, title_cell, tracks_cue, tracks_play = (on_tracks(e) for e in tracks_controls(channel))
    cue = off_tracks(button('CUE', f'{key},cue_default', size=f"{TRANSPORT['CUE']}f,48f",
                            momentary=True, name='MixpiCue'))
    play = off_tracks(button('▶', f'{key},play', name='MixpiPlay'))
    return group('MixpiDeckButtons', 'horizontal', f'400me,{TRANSPORT_HEIGHT}f', [
        keylock, quantize, sync, loop_button(channel), cue, load, title_cell, tracks_cue, play,
        tracks_play])


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
    # The Clear samples popover dims the whole screen (m-sampler-clear.png), so
    # the root is one stacked group with the popover first (on top).
    main = group('MixpiMain')
    ET.SubElement(root, 'Children').append(group('MixpiRoot', 'stacked', children=[clear_popover(), main]))
    children = main.find('Children')
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
    # The waveform rows (GL) show only with no full-screen view (plan 4.1 rule 3).
    add(perform, show_when(group('MixpiWaveArea', 'stacked', children=[
        loops(1, loop_display), loops(2, loop_display), waves]), SCREEN, SCREEN_NONE), decks())
    pages.append(perform)
    pages.append(browse_page(library, overview))
    fxpage=group('MixpiFxPage', children=[fx(), decks(size='0me,1e')])
    fxpage.set('trigger','[Tab],fx')
    pages.append(fxpage)
    pages.append(sampler_page())
    # R-18: Settings is a full screen; the pages are hidden under it (no widget
    # over a live waveform, plan 4.1 rule 3).
    # Settings (5) and the native Media page (2) cover the whole area: the pages
    # are hidden under them.
    children.append(when_all(group('MixpiPages', children=[stack]), '0me,0me',
                             off_screen(SCREEN_MEDIA), off_screen(SCREEN_SETTINGS)))
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
        # Spec s8 thumb: 24 px wide, 3 px in from the track's top and bottom,
        # radius 2, a short centre line. Its left half carries the fill colour
        # over the track's inner height, so the fill reaches the thumb's centre.
        'mixpi-slider-handle.svg': (
            f'<rect x="0" y="1" width="{THUMB_WIDTH // 2}" height="{SLIDER_HEIGHT - 2}" fill="#5d7238"/>'
            f'<rect x="0.5" y="3.5" width="{THUMB_WIDTH - 1}" height="{SLIDER_HEIGHT - 7}" rx="2" '
            'fill="#e4e7ec" stroke="#0d1014" stroke-width="1"/>'
            f'<rect x="{THUMB_WIDTH // 2 - 1}" y="13" width="2" height="{SLIDER_HEIGHT - 26}" fill="#262c35"/>'),
        'mixpi-cpu-on.svg':'<rect width="70" height="16" rx="3" fill="#a3c45e"/>',
        'mixpi-cpu-off.svg':'<rect width="70" height="16" rx="3" fill="#3a424e"/>',
    }.items():
        dims = (f'width="{THUMB_WIDTH}" height="{SLIDER_HEIGHT}"' if 'handle' in name
                else 'width="70" height="16"')
        (skin/name).write_text(f'<svg xmlns="http://www.w3.org/2000/svg" {dims}>{body}</svg>\n')
    for name, svg in icon_files().items():
        (skin/name).write_text(svg)
    for name, svg in drawn_files().items():
        (skin/name).write_text(svg)


# The menu tick (pioneered-menus.qss, spec section 1 ticked rows): dark ink on
# the accent box, inside the indicator's 2 px border.
TICK_PATH = ('<path d="M3.5 9.5 7.5 13 14.5 5" fill="none" stroke="#0d1014" stroke-width="2.5" '
             'stroke-linecap="round" stroke-linejoin="round"/>')
TICK_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 18 18">'
            + TICK_PATH + '</svg>\n')


def drawn_files():
    """SVGs the skin and its styles name, other than the 24 px glyph icons."""
    w, h = CLEAR_TICK_SPACE, CLEAR_ROW
    box = 'x="19" y="15" width="22" height="22" rx="2"'

    def row(on):
        # m-sampler-clear.png: a 24 px tick box 18 px in, dim border when
        # clear; the accent box with the ink tick when ticked.
        body = (f'<rect {box} fill="#a3c45e" stroke="#a3c45e" stroke-width="2"/>'
                f'<g transform="translate(21 17)">{TICK_PATH}</g>' if on else
                f'<rect {box} fill="none" stroke="#949dab" stroke-width="2"/>')
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
                f'viewBox="0 0 {w} {h}">{body}</svg>\n')
    return {
        'mixpi-icon-tick.svg': TICK_SVG,
        'mixpi-clear-row-off.svg': row(False),
        'mixpi-clear-row-on.svg': row(True),
        # The effect selector's ▾ (m-fx.png): dim, inside the field.
        'mixpi-icon-caret.svg': ('<svg xmlns="http://www.w3.org/2000/svg" width="12" height="8" '
                                 'viewBox="0 0 12 8"><path d="M1 1h10L6 7z" fill="#949dab"/></svg>\n'),
    }


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
