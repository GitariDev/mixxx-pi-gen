"""Three-band waveforms: compile the shipped setting and height rule with real Qt and run each check.

Production code, from the patched stack:
- util/mixpiwaveformcolours.h (Settings › Advanced, Waveform colours:
  [MixPi],waveform_colours, the read-only
  [MixPi],waveform_three_band_available, and the one-time three-band default).
- waveform/renderers/waveformwidgetrenderer.h: the real
  WaveformWidgetRenderer::getGain, its main-row flag and m_gain. The class's
  three out-of-line members (constructor, destructor, resizeRenderer) and the
  headers it only names types from (marks, colours, the waveform data) are
  test doubles; nothing about the gain is.
- waveform/mixpiwaveformgain.h (waveformHeightGain, filteredHeightCompensation).
- The all-shader Filtered renderer's own argument to getGains, cut out of the
  stack's waveform/renderers/allshader/waveformrendererfiltered.cpp
  (filtered_choice) and compiled into the fixture, so the fixture asks
  getGain what the shipped renderer asks, for a main row and for the Loop
  panel's waveform. In the baseline that argument is Mixxx's `true` and the
  real getGain doubles the height (main row 1.80, Loop panel 0.76).
- preferences/configobject.{h,cpp} (Mixxx's own parser, the save on change and
  its timing) and the control framework (control, controlobject,
  controlproxy, controlpotmeter, controlpushbutton, controlbehavior).

The waveform factory (WaveformWidgetFactory::mixpiAppliedType,
mixpiSwitchTo and findHandleIndexFromType, which the availability control
follows) is a recording double; tests/test_waveform_three_band.py
checks the main window's wiring to it as text. The real switch of GL widgets
is checked on the card (HANDOFF.md).

Modes (each its own process and folder): setting, refused, start, default,
thread, height. --baseline builds the stack without
mixxx-waveform-three-band.patch; the setting and the height rule are then
absent and the same checks must fail.
"""
import argparse
from pathlib import Path
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native.library_interface_runner import (PATCH_DIR, populate_pinned, qt_flags,
                                             qt_environment, moc_path, reconstruct)
from native.agreed_controls_runner import DOUBLES, PINNED_FILES

ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT / 'tests/native'
PATCH = 'mixxx-waveform-three-band.patch'
MODES = ('setting', 'refused', 'start', 'default', 'thread', 'height')
FILTERED = 'src/waveform/renderers/allshader/waveformrendererfiltered.cpp'
# Real headers the renderer header needs, and the Filtered renderer's source.
RENDERER_FILES = [
    'waveform/renderers/waveformwidgetrenderer.h', 'waveform/renderers/waveformrendererabstract.h',
    'track/track_decl.h', 'util/class.h',
    'waveform/renderers/allshader/waveformrendererfiltered.cpp',
]
# Headers waveformwidgetrenderer.h only takes type names from.
RENDERER_DOUBLES = {
    'waveform/renderers/waveformmark.h': '''#pragma once
#include <QBrush>
#include <QList>
#include <QPoint>
#include <QPointF>
#include <QSharedPointer>
#include <QString>
#include <cmath>
#include <memory>
#include "util/assert.h"
#include "util/math.h"
class WaveformMark;
typedef QSharedPointer<WaveformMark> WaveformMarkPointer;
class Cue;
typedef std::shared_ptr<Cue> CuePointer;
''',
    'waveform/renderers/waveformsignalcolors.h': '#pragma once\nclass WaveformSignalColors {};\n',
    'waveform/waveform.h': '''#pragma once
#include <QSharedPointer>
class Waveform;
typedef QSharedPointer<const Waveform> ConstWaveformPointer;
''',
}


def filtered_choice(source):
    """What the all-shader Filtered renderer passes getGains as applyCompensation."""
    found = re.findall(r'getGains\(\s*&allGain,\s*(.+?),\s*&bandGain\[0\]', source, re.DOTALL)
    if len(found) != 1:
        raise RuntimeError('expected one getGains call in the Filtered renderer, found %d' % len(found))
    return ' '.join(found[0].split())


def stack(target, baseline):
    names, _ = reconstruct(target, exclude=(PATCH,) if baseline else ())
    if not baseline and PATCH not in names:
        subprocess.run(['git', 'apply', str(PATCH_DIR / PATCH)], cwd=target, check=True, timeout=15)
        names.append(PATCH)
    populate_pinned(target, ['src/' + name for name in PINNED_FILES + RENDERER_FILES])
    return names


def build(target, baseline):
    support = target / 'interfaces'
    for name, text in {**DOUBLES, **RENDERER_DOUBLES}.items():
        (support / name).parent.mkdir(parents=True, exist_ok=True)
        (support / name).write_text(text)
    choice = filtered_choice((target / FILTERED).read_text())
    print('FILTERED ASKS', choice, flush=True)
    (support / 'mixpi_filtered_choice.h').write_text(
        '#pragma once\n#define MIXPI_FILTERED_ASKS (' + choice + ')\n')
    includes = ['-I' + str(support), '-I' + str(target / 'src'), '-I' + str(NATIVE)]
    for header in ('control/control.h', 'control/controlobject.h', 'control/controlproxy.h',
                   'control/controlpotmeter.h', 'control/controlpushbutton.h'):
        path = target / 'src' / header
        subprocess.run([moc_path(), *includes, str(path),
                        '-o', str(path.parent / ('moc_' + path.stem + '.cpp'))],
                       check=True, timeout=30)
    sources = [target / 'src' / name for name in
               ('preferences/configobject.cpp', 'control/control.cpp', 'control/controlobject.cpp',
                'control/controlproxy.cpp', 'control/controlpotmeter.cpp',
                'control/controlpushbutton.cpp', 'control/controlbehavior.cpp')]
    binary = target / 'waveform-three-band-test'
    command = ['c++', '-std=c++20', '-Wall', '-Wextra', *includes,
               *(['-DMIXPI_THREE_BAND_BASELINE=1'] if baseline else []),
               *[str(source) for source in sources],
               str(NATIVE / 'waveform_three_band_test.cpp'), '-o', str(binary),
               '-pthread', *qt_flags(('QtCore', 'QtGui', 'QtWidgets', 'QtXml'))]
    print('COMPILE', repr(command), flush=True)
    subprocess.run(command, check=True, timeout=600)
    return binary


def run(modes=MODES, baseline=False):
    """One CompletedProcess per mode, in the order given."""
    with tempfile.TemporaryDirectory(prefix='mixpi-waveform-three-band-') as temporary:
        target = Path(temporary) / 'build'
        target.mkdir()
        names = stack(target, baseline)
        print('PATCHES', len(names), 'BASELINE' if baseline else PATCH, flush=True)
        binary = build(target, baseline)
        results = []
        for mode in modes:
            directory = Path(temporary) / 'run' / mode
            directory.mkdir(parents=True)
            result = subprocess.run([str(binary), mode, str(directory)], env=qt_environment(),
                                    capture_output=True, text=True, timeout=120)
            print('MODE', mode, 'RC', result.returncode, result.stdout, result.stderr[-4000:], flush=True)
            results.append(result)
        return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('modes', nargs='*')
    parser.add_argument('--baseline', action='store_true')
    options = parser.parse_args()
    raise SystemExit(max(result.returncode
                         for result in run(options.modes or list(MODES), options.baseline)))
