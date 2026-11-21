"""Wave J9: render Settings › Interface at 800x480 offscreen, for the eye.

Not a check: there is no Mixxx skin parser outside Mixxx, so this builds the
generated skin (stage3/01-install-packages/files/mixpi-performance.py, on the
fixture Pioneered of tests/test_performance_skin.py), evaluates the Settings
screen with the skin's own connection rules (the Model of
test_performance_skin) for Settings › Interface, and lays it out with plain
Qt widgets as Mixxx's WidgetGroup does: no margins or spacing, the Size
policies of LegacySkinParser, and the generated style.qss applied. The 48 px
top bar is left blank. Fonts are whatever the machine has.

usage: zoom_setting_render.py OUT.png [--generator PATH]
--generator renders another copy of mixpi-performance.py (for example the
base commit's) for a side-by-side of the first five rows.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests'))
from native.library_interface_runner import qt_flags, qt_environment

STATE = {'[MixPi],screen': 5, '[MixPi],settings_page': 1, '[Controls],ShowDurationRemaining': 0,
         '[MixPi],night_dim': 0, '[MixPi],show_cpu': 1, '[MixPi],backlight': 100,
         '[MixPi],backlight_available': 1, '[MixPi],desktop_bar': 0, '[MixPi],desktop_bar_available': 1,
         '[MixPi],saved': 0}


def skin(generator, folder):
    import test_performance_skin as T
    if generator:
        copy = folder / 'generator'
        shutil.copytree(ROOT / 'stage3/01-install-packages/files', copy)
        target = copy / 'zz_render_generator.py'
        shutil.copyfile(generator, target)
        spec = importlib.util.spec_from_file_location('zz_render_generator', target)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        T.SKIN = module
    test = T.PerformanceSkinTests('test_screen_is_a_skin_only_unsaved_control')
    test.setUp()
    return T, test


def tree(T, model, element):
    size = element.findtext('Size', '0me,0me')
    node = {'name': element.findtext('ObjectName', ''), 'size': size}
    for c in element.findall('Connection'):
        bind = c.findtext('BindProperty')
        if bind == 'enabled':
            node['enabled'] = T.transform(c, float(STATE.get(c.findtext('ConfigKey'), 0))) > 0
        elif bind == 'highlight':
            node['highlight'] = int(T.transform(c, float(STATE.get(c.findtext('ConfigKey'), 0))))
    if element.tag == 'WidgetGroup':
        node.update(kind='group', layout=element.findtext('Layout', 'vertical'),
                    children=[tree(T, model, child) for child in element.find('Children')
                              if model.visible(child, STATE) and child.tag in
                              ('WidgetGroup', 'Label', 'PushButton', 'SliderComposed', 'Number')])
    elif element.tag in ('Label', 'Number'):
        text = element.findtext('Text', '')
        if element.tag == 'Number':
            key = element.findtext('Connection/ConfigKey')
            text = text.replace('%1', format(float(STATE.get(key, 0)), '.0f'))
        node.update(kind='label', text=text, align=element.findtext('Alignment', ''))
    elif element.tag == 'PushButton':
        states = int(element.findtext('NumberStates'))
        shown = [c for c in element.findall('Connection') if c.find('BindProperty') is None
                 and c.findtext('ConnectValueToWidget', 'true') == 'true']
        value = 0
        if shown:
            value = int(T.transform(shown[-1], float(STATE.get(shown[-1].findtext('ConfigKey'), 0)))) % states
        texts = [s.findtext('Text', '') for s in element.findall('State')]
        node.update(kind='button', text=texts[value] if texts else '', value=value)
        if element.findtext('ObjectName') == 'MixpiClose':
            node['text'] = '✕'
    elif element.tag == 'SliderComposed':
        key = element.findtext('Connection/ConfigKey')
        node.update(kind='slider', value=float(STATE.get(key, 0)) / 100.0,
                    bar=element.findtext('BarColor', '#5d7238'))
    return node


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('out')
    parser.add_argument('--generator')
    options = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='mixpi-zoom-render-') as temporary:
        folder = Path(temporary)
        T, test = skin(options.generator, folder)
        try:
            settings = test.model.one('MixpiSettings')
            (folder / 'tree.json').write_text(json.dumps(tree(T, test.model, settings)))
            shutil.copyfile(test.skin / 'style.qss', folder / 'style.qss')
        finally:
            test.temp.cleanup()
        binary = folder / 'render'
        subprocess.run(['c++', '-std=c++17', str(ROOT / 'tests/native/zoom_setting_render.cpp'),
                        '-o', str(binary), *qt_flags(('QtCore', 'QtGui', 'QtWidgets'))],
                       check=True, timeout=300)
        subprocess.run([str(binary), str(folder / 'tree.json'), str(folder / 'style.qss'),
                        str(Path(options.out).resolve())], check=True, env=qt_environment(), timeout=60)
        print('RENDER', options.out)


if __name__ == '__main__':
    main()
