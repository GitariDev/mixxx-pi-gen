"""Build G1: the DECKS overview strip froze after about 6 h 46 min without a seek.

Copies EngineBuffer::updateIndicators, setNewPlaypos and
fractionalPlayposFromAbsolute verbatim from the patched
src/engine/enginebuffer.cpp, with its constants and the constructor
initializers of the members they use, and drives them through the real
control framework (ControlObject, ControlProxy, ControlDoublePrivate) and the
real mixxx::audio::FramePos/SampleRate. Doubles stand in for the other engine
parts the functions call: LoopingControl, CueControl (counts its
updateIndicators), ClockControl, VisualPlayPosition, the read-ahead manager,
the scaler and the engine controls. The whole EngineBuffer (readers, scalers,
sync) is not built.

mixxx-overview-playposition.patch is applied on top of the registered stack
when it is not registered yet, which is where the registration puts it.
--baseline leaves it out (stock 2.5.6 enginebuffer.cpp): the checks must fail.

-fwrapv: the counter is a signed int, and its overflow is undefined
behaviour; the card's -O2 aarch64 build wraps, so the fixture does the same.
-O0 keeps the 0xA5 fill under the placement new (no dead-store removal), so
an uninitialised member shows as garbage.
"""
import argparse
from pathlib import Path
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native.library_interface_runner import (PATCH_DIR, ROOT, reconstruct, populate_pinned,
                                             qt_flags, qt_environment, moc_path)
from native.key_widget_runner import block
from native.position_display_runner import CONTROL_FILES, DOUBLES as CONTROL_DOUBLES

PATCH = 'mixxx-overview-playposition.patch'
SOURCE = 'src/engine/enginebuffer.cpp'
AUDIO_FILES = ['audio/frame.h', 'audio/frame.cpp', 'audio/types.h', 'audio/types.cpp',
               'util/types.h', 'util/math.h', 'util/optional.h', 'util/fpclassify.h',
               'util/fpclassify.cpp', 'engine/slipmodestate.h']
DOUBLES = {name: CONTROL_DOUBLES[name] for name in
           ('preferences/usersettings.h', 'controllers/midi/midimessage.h', 'util/stat.h',
            'util/assert.h')}
DOUBLES['engine/engine.h'] = '''#pragma once
#include "util/assert.h"
namespace mixxx {
// PIN src/engine/engine.h: audio::ChannelCount::stereo().
static constexpr int kEngineChannelCount = 2;
}
'''
# Members of the harness EngineBuffer (tests/native/overview_playposition_test.cpp).
MEMBERS = {'m_playPos', 'm_baserate_old', 'm_rate_old', 'm_trackEndPositionOld',
           'm_iSamplesSinceLastIndicatorUpdate', 'm_slipPos', 'm_dSlipRate', 'm_slipModeState',
           'm_iLastBufferSize'}
FUNCTIONS = (
    'void EngineBuffer::setNewPlaypos(mixxx::audio::FramePos position)',
    'double EngineBuffer::fractionalPlayposFromAbsolute(mixxx::audio::FramePos absolutePlaypos)',
    'void EngineBuffer::updateIndicators(double speed, int iBufferSize)',
)


def initializers(text):
    """The constructor's member initializers for MEMBERS, in source order."""
    start = text.index('EngineBuffer::EngineBuffer(')
    colon = text.index('\n        : ', start) + len('\n        : ')
    entries, depth, current, offset = [], 0, '', colon
    while True:
        character = text[offset]
        if depth == 0 and character == '{':
            break
        if character == '(':
            depth += 1
        elif character == ')':
            depth -= 1
        if depth == 0 and character == ',':
            entries.append(current.strip())
            current = ''
        else:
            current += character
        offset += 1
    entries.append(current.strip())
    kept = [entry for entry in entries if entry.split('(')[0] in MEMBERS]
    return kept


def shipped(text):
    constants = [re.search(r'^constexpr SINT kSamplesPerFrame = 2;.*$', text, re.MULTILINE)[0],
                 re.search(r'^constexpr int kPlaypositionUpdateRate = 15;.*$', text, re.MULTILINE)[0]]
    functions = [block(text, signature) for signature in FUNCTIONS]
    return constants, initializers(text), functions


def build(target, baseline=False):
    names, _ = reconstruct(target, exclude=(PATCH,) if baseline else ())
    if not baseline and PATCH not in names:
        populate_pinned(target, [SOURCE])
        subprocess.run(['git', 'apply', '--check', str(PATCH_DIR / PATCH)], cwd=target, check=True,
                       timeout=15)
        subprocess.run(['git', 'apply', str(PATCH_DIR / PATCH)], cwd=target, check=True, timeout=15)
        names.append(PATCH)
    print('PATCHES', ' '.join(names), flush=True)
    populate_pinned(target, [SOURCE] + ['src/' + name for name in CONTROL_FILES + AUDIO_FILES])
    support = target / 'interfaces'
    for name, text in DOUBLES.items():
        (support / name).parent.mkdir(parents=True, exist_ok=True)
        (support / name).write_text(text)
    constants, kept, functions = shipped((target / SOURCE).read_text())
    print('INITIALIZERS', ', '.join(kept), flush=True)
    (support / 'enginebuffer_shipped_constants.inc').write_text(
        '// Copied from ' + SOURCE + '\n' + '\n'.join(constants) + '\n')
    (support / 'enginebuffer_shipped.inc').write_text(
        '// Copied verbatim from ' + SOURCE + '\n'
        '#define MIXPI_SHIPPED_INITIALIZERS ' + ', '.join(kept) + '\n\n'
        + '\n\n'.join(functions) + '\n')
    for header in ('control/control.h', 'control/controlobject.h', 'control/controlproxy.h'):
        path = target / 'src' / header
        subprocess.run([moc_path(), '-I' + str(support), '-I' + str(target / 'src'), str(path),
                        '-o', str(path.parent / ('moc_' + path.stem + '.cpp'))], check=True, timeout=30)
    sources = [target / 'src' / name for name in
               ('control/control.cpp', 'control/controlobject.cpp', 'control/controlproxy.cpp',
                'audio/frame.cpp', 'audio/types.cpp', 'util/fpclassify.cpp')]
    command = ['c++', '-std=c++20', '-O0', '-fwrapv']
    command += ['-I' + str(support), '-I' + str(target / 'src')]
    command += [str(source) for source in sources]
    command += [str(ROOT / 'tests/native/overview_playposition_test.cpp'),
                '-o', str(target / 'overview-playposition-test'), *qt_flags(('QtCore',))]
    print('COMPILE', repr(command), flush=True)
    subprocess.run(command, check=True, timeout=300)
    return target / 'overview-playposition-test'


def run(baseline=False):
    with tempfile.TemporaryDirectory(prefix='mixpi-overview-playposition-') as temporary:
        binary = build(Path(temporary), baseline)
        result = subprocess.run([str(binary)], env=qt_environment(), capture_output=True,
                                text=True, timeout=120)
        print(result.stdout, result.stderr, flush=True)
        return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', action='store_true')
    options = parser.parse_args()
    raise SystemExit(run(options.baseline).returncode)
