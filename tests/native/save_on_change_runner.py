"""Compile the shipped save-on-change code (R-13) with real Qt and run each check.

Production: preferences/configobject.{h,cpp} (ConfigObject::save,
the change counter, ConfigAutosave), the control framework (control.cpp,
controlobject.cpp, controlproxy.cpp) and mixer/samplerbank.{h,cpp}, all from
the patched stack. Interface doubles (tests/native/save_on_change_doubles.h):
the players and the library lookup, tracks, the media-use registry, file
dialogs, command-line arguments, statistics and MIDI types.

--pinned builds only the "never-missing" check against the pinned
ConfigObject, which removes the old file before the rename; it must fail.
"""
import argparse
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native.library_interface_runner import (PATCH_DIR, populate_pinned, qt_flags,
                                             qt_environment, moc_path, reconstruct)

ROOT = Path(__file__).resolve().parents[2]
PATCH = 'mixxx-save-on-change.patch'
MODES = ('debounce', 'burst', 'constant', 'idle', 'kill', 'readonly', 'persist',
         'never-missing', 'bank', 'bank-unchanged', 'bank-slow')
KILL_AFTER_SECONDS = 3

PINNED_FILES = [
    'preferences/configobject.h', 'preferences/configobject.cpp', 'preferences/usersettings.h',
    'control/control.cpp', 'control/control.h', 'control/controlobject.cpp',
    'control/controlobject.h', 'control/controlproxy.cpp', 'control/controlproxy.h',
    'control/controlbehavior.h', 'control/controlvalue.h', 'util/mutex.h',
    'util/thread_annotations.h', 'util/compatibility/qmutex.h', 'util/compatibility/qatomic.h',
    'util/compatibility/qhash.h', 'util/assert.h', 'util/color/rgbcolor.h', 'util/optional.h',
    'mixer/samplerbank.h', 'mixer/samplerbank.cpp',
]
DOUBLED = ('util/cmdlineargs.h', 'util/xml.h', 'track/track.h', 'mixer/basetrackplayer.h',
           'mixer/sampler.h', 'mixer/playermanager.h', 'control/controlpushbutton.h',
           'util/file.h', 'library/media/mediause.h')
DOUBLES = {
    'widget/wwidget.h': '#pragma once\n',
    'util/debug.h': '''#pragma once
#include <QString>
#include <QtDebug>
inline void reportFatalErrorAndQuit(const QString& message) { qFatal("%s", qPrintable(message)); }
inline void reportCriticalErrorAndQuit(const QString& message) { qFatal("%s", qPrintable(message)); }
''',
    'controllers/midi/midimessage.h': '''#pragma once
enum class MidiOpCode { NoteOff, NoteOn, ControlChange };
''',
    'util/stat.h': '''#pragma once
#include <QString>
struct Stat {
    enum StatType { UNSPECIFIED };
    enum ComputeFlags { COUNT = 1, SUM = 2, AVERAGE = 4, SAMPLE_VARIANCE = 8, MIN = 16, MAX = 32 };
    static void track(const QString&, StatType, ComputeFlags, double) {}
};
''',
}


def build(target, pinned=False):
    """Reconstruct the stack (with or without the patch) and compile the fixture."""
    names, _ = reconstruct(target, exclude=(PATCH,))
    if not pinned:
        # Not yet in MIXXX_PATCHES: apply it on top of the registered stack,
        # which is where the registration puts it.
        touched = [line.split()[2][2:] for line in (PATCH_DIR / PATCH).read_text().splitlines()
                   if line.startswith('diff --git ')]
        populate_pinned(target, touched)
        subprocess.run(['git', 'apply', str(PATCH_DIR / PATCH)], cwd=target, check=True, timeout=15)
    populate_pinned(target, ['src/' + name for name in PINNED_FILES])
    support = target / 'interfaces'
    for name in DOUBLED:
        (support / name).parent.mkdir(parents=True, exist_ok=True)
        (support / name).write_text('#pragma once\n#include "save_on_change_doubles.h"\n')
    for name, text in DOUBLES.items():
        (support / name).parent.mkdir(parents=True, exist_ok=True)
        (support / name).write_text(text)
    includes = ['-I' + str(support), '-I' + str(target / 'src'), '-I' + str(ROOT / 'tests/native')]
    defines = ['-DMIXPI_PINNED_SAVE'] if pinned else []
    sources = [target / 'src/preferences/configobject.cpp']
    if not pinned:
        for header in ('control/control.h', 'control/controlobject.h', 'control/controlproxy.h',
                       'mixer/samplerbank.h'):
            path = target / 'src' / header
            subprocess.run([moc_path(), *includes, str(path),
                            '-o', str(path.parent / ('moc_' + path.stem + '.cpp'))],
                           check=True, timeout=30)
        doubles_moc = target / 'moc_save_on_change_doubles.cpp'
        subprocess.run([moc_path(), *includes, str(ROOT / 'tests/native/save_on_change_doubles.h'),
                        '-o', str(doubles_moc)], check=True, timeout=30)
        sources += [target / 'src' / name for name in
                    ('control/control.cpp', 'control/controlobject.cpp',
                     'control/controlproxy.cpp', 'mixer/samplerbank.cpp')]
        sources.append(doubles_moc)
    binary = target / 'save-on-change-test'
    command = ['c++', '-std=c++20', '-Wall', '-Wextra', *defines, *includes,
               *[str(source) for source in sources],
               str(ROOT / 'tests/native/save_on_change_test.cpp'), '-o', str(binary),
               '-pthread', *qt_flags(('QtCore', 'QtGui', 'QtWidgets', 'QtXml'))]
    print('COMPILE', repr(command), flush=True)
    subprocess.run(command, check=True, timeout=300)
    return binary


def parse_config(text):
    """mixxx.cfg as ConfigObject::parse reads it; raises on a malformed line."""
    values, group = {}, None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith('[') and line.endswith(']'):
            group = line
            continue
        if group is None:
            raise ValueError('key before any group: ' + line)
        key, _, value = line.partition(' ')
        values[(group, key)] = value.strip()
    return values


def run_kill(binary, directory):
    process = subprocess.Popen([str(binary), 'kill', str(directory)], env=qt_environment(),
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    line = process.stdout.readline()
    if line.strip() != 'SET':
        process.kill()
        raise RuntimeError('kill mode did not reach SET: ' + line)
    time.sleep(KILL_AFTER_SECONDS)
    process.send_signal(signal.SIGKILL)
    stdout, stderr = process.communicate(timeout=10)
    text = (directory / 'mixxx.cfg').read_text()
    values = parse_config(text)
    ok = (process.returncode == -signal.SIGKILL and
          values.get(('[Test]', 'key')) == 'survives-sigkill' and
          values.get(('[Test]', 'existing')) == '1')
    report = ('PASS' if ok else 'FAIL') + \
        ' after SIGKILL 3 s after a change the file parses and holds the value\n'
    return subprocess.CompletedProcess(process.args, 0 if ok else 1,
                                       line + stdout + report + 'FILE ' + repr(text) + '\n',
                                       stderr)


def run(modes=MODES, pinned=False):
    """One CompletedProcess per mode, in the order given."""
    with tempfile.TemporaryDirectory(prefix='mixpi-save-on-change-') as temporary:
        target = Path(temporary)
        binary = build(target / 'build', pinned=pinned)
        results = []
        for mode in modes:
            directory = target / 'run' / mode
            directory.mkdir(parents=True)
            if mode == 'kill':
                result = run_kill(binary, directory)
            else:
                result = subprocess.run([str(binary), mode, str(directory)], env=qt_environment(),
                                        capture_output=True, text=True, timeout=120)
            directory.chmod(0o755)
            print('MODE', mode, 'RC', result.returncode, result.stdout, result.stderr[-4000:],
                  flush=True)
            results.append(result)
        return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pinned', action='store_true')
    parser.add_argument('modes', nargs='*')
    options = parser.parse_args()
    chosen = options.modes or (['never-missing'] if options.pinned else list(MODES))
    raise SystemExit(max(result.returncode for result in run(chosen, options.pinned)))
