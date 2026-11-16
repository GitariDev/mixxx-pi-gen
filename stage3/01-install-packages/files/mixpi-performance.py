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
NAVIGATION_STYLE = '''/* MixPi native navigation */
#MixpiButton, #MixpiPlay, #MixpiTab, #MixpiRecord,
#LibraryWrapper #LibraryActionsButton, #LibraryWrapper #SidebarButton,
#LibraryWrapper #LibrarySourcesButton, #LibraryWrapper #LibraryBackButton {
    border-radius: 2px;
}
'''
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


def label(text, size='0me,0me', name='MixpiLabel'):
    e = node('Label')
    prop(e, 'Text', text)
    prop(e, 'ObjectName', name)
    prop(e, 'Size', size)
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


def deck_info(channel, compact=False):
    title = typed('TrackProperty', channel, '0me,28f', 'MixpiDeckTitle',
                  Property='title', Elide='right', TooltipId='track_title')
    head = group('MixpiTitleStrip', 'horizontal', '0me,28f',
                 [label(str(channel), '28f,28f', 'MixpiDeckNumber'), title])
    info = group('MixpiDeckInfo', size='400me,28f' if compact else '400me,82f', children=[head])
    if not compact:
        widths = DECK_STAT_WIDTHS
        stats = group('MixpiDeckStats', 'horizontal', '0me,54f', [
            typed('NumberPos', channel, f"{widths['time']}me,54f", 'MixpiTime', NumberOfDigits=6),
            typed('NumberBpm', channel, f"{widths['bpm']}me,54f", 'MixpiBpm'),
            typed('NumberRate', channel, f"{widths['rate']}me,54f", 'MixpiRate', NumberOfDigits=1),
        ])
        connection(stats.find('Children/NumberBpm'), f'[Channel{channel}],visual_bpm', write=False)
        key = typed('Key', channel, f"{widths['key']}me,54f", 'MixpiKey', PairedNotation='true')
        connection(key, f'[Channel{channel}],visual_key', write=False)
        add(stats, key)
        add(info, stats)
    return info


def decks(compact=False):
    return group('MixpiDecks', 'horizontal', '0me,28f' if compact else '0me,82f',
                 [deck_info(1, compact), deck_info(2, compact)])


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


def browse_page(library):
    toolbar = copy.deepcopy(library.find('Children/WidgetGroup'))
    toolbar.find('ObjectName').text = 'MixpiLibraryToolbar'
    toolbar.find('Size').text = '0me,48f'
    sources = next(element for element in toolbar.find('Children')
                   if element.findtext('ObjectName') == 'LibrarySourcesButton')
    toolbar.find('Children').remove(sources)
    for e in toolbar.find('Children'):
        fixed_size(e, '90f,48f' if e.findtext('ObjectName')=='SidebarButton' else
                   '96f,48f' if e.findtext('ObjectName')=='LibraryActionsButton' else '0me,48f')
        if e.findtext('ObjectName') == 'SidebarButton':
            for state, text in zip(e.findall('State'), ('Show', 'Hide')):
                state.find('Text').text = text
    sidebar = next(copy.deepcopy(e) for e in library.findall('.//WidgetGroup')
                   if e.findtext('ObjectName')=='SidebarWrapper')
    fixed_size(sidebar,'290f,0me')
    fixed_size(sources, '0me,48f')
    sidebar.find('Children').insert(0, sources)
    table = copy.deepcopy(library.find('.//Library'))
    # An 800 px title strip is clipped by the main column while sources are
    # visible. The right pane therefore covers Deck 2's title, but never either
    # overview or any transport control. Native rows remain full tap targets.
    titles = decks(compact=True)
    fixed_size(titles,'800f,28f')
    prop(titles,'Pos','0,0')
    clipped_titles = group('MixpiClippedTitles',size='0me,28f',children=[titles])
    clipped_titles.remove(clipped_titles.find('Layout'))
    main = group('MixpiLibraryMain',children=[table,clipped_titles])
    destinations = group('MixpiSamplerDestinations', 'horizontal', '0me,48f',
                         [label('LOAD TO', '90f,48f')])
    for sampler in range(1, 5):
        destination = button(f'PAD {sampler}', f'[Sampler{sampler}],LoadSelectedTrack',
                             momentary=True)
        connection(destination, f'[Sampler{sampler}],play', transform='<Not/>', bind='enabled')
        add(destinations, destination)
    done = button('DONE', '[Tab],sampler', size='90f,48f', push=True)
    connection(done, '[MixPi],sample_load', read=False, transform='<Not/>')
    add(destinations, done)
    connection(destinations, '[MixPi],sample_load', bind='visible')
    wrapper = group('LibraryWrapper', children=[toolbar, destinations,
        group('MixpiLibraryBody','right-overlay',children=[main,sidebar])])
    page = group('MixpiBrowse', children=[wrapper])
    page.set('trigger','[Tab],library')
    return page


def sampler_page():
    load = button('LOAD SAMPLE', '[MixPi],sample_load', size='180f,48f', push=True)
    connection(load, '[Tab],library', read=False)
    cards = group('MixpiSamplerCards', 'horizontal')
    for sampler in range(1, 5):
        key = f'[Sampler{sampler}]'
        title = node('TrackProperty')
        for name, value in dict(ObjectName='MixpiSamplerTitle', Group=key,
                                Property='titleInfo', Elide='right', Size='0me,48f').items():
            prop(title, name, value)
        trigger = button(f'PAD {sampler}', f'{key},cue_gotoandplay', momentary=True,
                         display=f'{key},play')
        connection(trigger, f'{key},track_loaded', bind='enabled')
        stop = button('STOP', f'{key},stop', momentary=True, display=f'{key},play')
        add(cards, group('MixpiSamplerCard', size='200me,0me', children=[title, trigger, stop]))
    page = group('MixpiSampler', children=[
        group('MixpiSamplerHeader', 'horizontal', '0me,48f',
              [load, label('Select a track, then its pad. Stop a pad to replace it.')]),
        cards, decks()])
    page.set('trigger', '[Tab],sampler')
    return page


def summary(channel, overview, visual, loop_display):
    strip = concrete(overview, channel)
    fixed_size(strip, '0me,52f')
    if loop_display == 'overlay':
        return strip
    focused = concrete(visual, channel)
    fixed_size(focused, '0me,52f')
    connection(focused, f'[Channel{channel}],track_loaded', bind='enabled')
    detail = group('MixpiFocusedOverview', 'horizontal', '0me,52f', [
        button('−', f'[Channel{channel}],waveform_zoom_up', size='48f,48f', momentary=True),
        focused,
        button('+', f'[Channel{channel}],waveform_zoom_down', size='48f,48f', momentary=True)])
    connection(detail, '[MixPi],loop_deck', transform=f'<IsEqual>{channel}</IsEqual>', bind='visible')
    connection(strip, '[MixPi],loop_deck',
               transform=f'<IsEqual>{channel}</IsEqual><Not/>', bind='visible')
    return group('MixpiSummary', 'stacked', '400me,52f', [strip, detail])


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
            attr.text = '4'
    # These are skin-only view states. Do not persist an open overlay or startup tab.
    attrs = manifest.find('attributes')
    for key, value in [('[MixPi],loop_deck','0'), ('[Tab],overview','1'),
                       ('[Tab],library','0'), ('[Tab],fx','0'), ('[Tab],sampler','0'),
                       ('[MixPi],sample_load','0'), ('[Tab],current','0')]:
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
    top = group('MixpiTopbar','horizontal','0me,50f')
    def tab(text, key):
        b = button(text,f'[Tab],{key}',size='84f,48f',push=True,name='MixpiTab')
        connection(b,'[MixPi],loop_deck',read=False,transform='<Not/>')
        connection(b,'[MixPi],sample_load',read=False,transform='<Not/>')
        return b
    for text, key in [('DECKS','overview'),('TRACKS','library'),('FX','fx'),('SAMPLER','sampler')]:
        b = tab(text, key)
        if key == 'overview':
            # Settings is a view inside Decks ([Tab],overview stays 1). While it
            # is open, show a twin that never mirrors the tab state, so only
            # SETTINGS is highlighted. Both send the same writes.
            connection(b,'[MixPi],loop_deck',transform='<IsEqual>3</IsEqual><Not/>',bind='visible')
            twin = tab(text, key)
            twin.find('Connection/ConnectValueToWidget').text = 'false'
            connection(twin,'[MixPi],loop_deck',transform='<IsEqual>3</IsEqual>',bind='visible')
            b = group('MixpiTabPair','stacked','84f,48f',[b,twin])
        add(top,b)
    for text, control in [('LOAD / EJECT', 'media_load')]:
        action = button(text, f'[MixPi],{control}', size='132f,48f', push=True)
        connection(action, '[MixPi],media_available', bind='enabled')
        add(top, action)
    settings_button = button('SETTINGS','[MixPi],loop_deck',size='96f,48f',push=True,
                             transform='<IsEqual>3</IsEqual>')
    connection(settings_button, '[MixPi],settings_available', bind='enabled')
    connection(settings_button,'[Tab],overview',read=False,transform='<IsEqual>1</IsEqual>')
    add(top, group('MixpiTopSpacer','horizontal'), settings_button,
        button('● REC','[Recording],toggle_recording',size='80f,48f',momentary=True,
               display='[Recording],status', name='MixpiRecord',
               state_labels=('● REC', 'WAIT', '■ STOP', '■ STOP')))
    cpu = node('Number')
    for k,v in dict(ObjectName='MixpiCpu', Size='76f,24f', Text='%1%', NumberOfDigits=0).items():
        prop(cpu,k,v)
    connection(cpu,'[MixPi],audio_load_percent',write=False)
    connection(cpu, '[MixPi],settings_available', bind='visible')
    unavailable = label('—', '76f,24f')
    connection(unavailable, '[MixPi],settings_available', transform='<Not/>', bind='visible')
    cpu_label = label('CPU', '76f,22f')
    cpu_value = group('MixpiCpuValue', 'stacked', '76f,24f', [cpu, unavailable])
    add(top,group('MixpiCpuBox',size='80f,48f',children=[cpu_label,cpu_value]))
    children.append(top)
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
    summaries=group('MixpiSummaries','horizontal','0me,52f')
    transport=group('MixpiTransport','horizontal','0me,52f')
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
        row=group('MixpiDeckButtons','horizontal','0me,52f',[
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
    children.extend([summaries,transport])
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

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('skin',type=Path)
    parser.add_argument('--loop-display', choices=['focus', 'overlay'], default='focus',
                        help='Overlay is an opt-in renderer trial; focus avoids native GL stacking.')
    args=parser.parse_args()
    build(args.skin, args.loop_display)
    print(f'MixPi performance pages ready: {args.skin}')
