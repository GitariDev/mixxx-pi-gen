"""Compile the shipped wave C2 native controls with real Qt and run each check.

Production code, from the patched stack: mixer/mixpisamplerclear.h (Clear
samples), util/mixpidisplaycontrols.h (Brightness, Night dim, CPU readout),
effects/effectsautosave.h (effects saved within a second),
preferences/configobject.{h,cpp} (the save on change and its timing) and the
control framework (control, controlobject, controlproxy, controlpotmeter,
controlpushbutton, controlbehavior). Interface doubles
(tests/native/agreed_controls_doubles.h): the command-line arguments and the
XML helper that configobject.cpp includes. The sampler players are fixture
controls with Mixxx's eject rules; the backlight is a fake sysfs folder.

The selector check compiles widget/weffectselector.cpp with the effect doubles
of tests/native/effect_selector_stubs.h.
"""
import argparse
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native.library_interface_runner import (PATCH_DIR, populate_pinned, qt_flags,
                                             qt_environment, moc_path, reconstruct)

ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT / 'tests/native'
# In stack order; applied on top of the registered stack when not yet registered.
PATCHES = ('mixxx-effects-save.patch', 'mixxx-save-within-second.patch',
           'mixxx-agreed-controls.patch')
MODES = ('settings-fast', 'effects-save', 'effects-kill', 'clear', 'backlight',
         'backlight-readonly', 'backlight-saved', 'backlight-none', 'selector')
# Seconds between "SET" (the effect change) and SIGKILL in effects-kill.
KILL_AFTER_SECONDS = 1.0

PINNED_FILES = [
    'preferences/configobject.h', 'preferences/configobject.cpp', 'preferences/usersettings.h',
    'control/control.cpp', 'control/control.h', 'control/controlobject.cpp',
    'control/controlobject.h', 'control/controlproxy.cpp', 'control/controlproxy.h',
    'control/controlpotmeter.cpp', 'control/controlpotmeter.h',
    'control/controlpushbutton.cpp', 'control/controlpushbutton.h',
    'control/controlbehavior.cpp', 'control/controlbehavior.h', 'control/controlvalue.h',
    'util/mutex.h', 'util/thread_annotations.h', 'util/compatibility/qmutex.h',
    'util/compatibility/qatomic.h', 'util/compatibility/qhash.h', 'util/assert.h',
    'util/math.h', 'util/color/rgbcolor.h', 'util/optional.h',
    'widget/weffectselector.h', 'widget/weffectselector.cpp',
]
DOUBLES = {
    'widget/wwidget.h': '#pragma once\n',
    'util/cmdlineargs.h': '#pragma once\n#include "agreed_controls_doubles.h"\n',
    'util/xml.h': '#pragma once\n#include "agreed_controls_doubles.h"\n',
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


def stack(target):
    """The registered stack with these patches on top, as Mixxx is built."""
    names, _ = reconstruct(target, exclude=PATCHES)
    for name in PATCHES:
        text = (PATCH_DIR / name).read_text()
        touched = re.findall(r'^diff --git a/(\S+) b/\S+$', text, re.MULTILINE)
        new = set(re.findall(r'^--- /dev/null\n\+\+\+ b/(\S+)$', text, re.MULTILINE))
        populate_pinned(target, [path for path in touched if path not in new])
        subprocess.run(['git', 'apply', str(PATCH_DIR / name)], cwd=target, check=True, timeout=15)
    populate_pinned(target, ['src/' + name for name in PINNED_FILES])
    return names


def build_controls(target):
    support = target / 'interfaces'
    for name, text in DOUBLES.items():
        (support / name).parent.mkdir(parents=True, exist_ok=True)
        (support / name).write_text(text)
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
    binary = target / 'agreed-controls-test'
    command = ['c++', '-std=c++20', '-Wall', '-Wextra', *includes,
               *[str(source) for source in sources],
               str(NATIVE / 'agreed_controls_test.cpp'), '-o', str(binary),
               '-pthread', *qt_flags(('QtCore', 'QtGui', 'QtWidgets', 'QtXml'))]
    print('COMPILE', repr(command), flush=True)
    subprocess.run(command, check=True, timeout=600)
    return binary


def build_selector(target):
    doubles = target / 'selector-doubles'
    for name in ('effects/defs.h', 'effects/effectsmanager.h', 'effects/visibleeffectslist.h',
                 'widget/wbasewidget.h', 'widget/effectwidgetutils.h'):
        destination = doubles / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text('#include "effect_selector_stubs.h"\n')
    work = target / 'selector'
    work.mkdir()
    subprocess.run([moc_path(), str(target / 'src/widget/weffectselector.h'),
                    '-o', str(work / 'moc_weffectselector.cpp')], check=True, timeout=30)
    subprocess.run([moc_path(), '-feffect_selector_stubs.h', str(NATIVE / 'effect_selector_stubs.h'),
                    '-o', str(work / 'moc_effect_stubs.cpp')], check=True, timeout=30)
    binary = target / 'agreed-selector-test'
    # The doubles come first: the patched tree has the real effects headers.
    command = ['c++', '-std=c++20', '-I' + str(doubles), '-I' + str(NATIVE), '-I' + str(work),
               '-I' + str(target / 'src'),
               str(NATIVE / 'agreed_selector_test.cpp'), str(work / 'moc_effect_stubs.cpp'),
               str(target / 'src/widget/weffectselector.cpp'), '-o', str(binary),
               *qt_flags(('QtCore', 'QtGui', 'QtWidgets', 'QtXml'))]
    print('COMPILE', repr(command), flush=True)
    subprocess.run(command, check=True, timeout=300)
    return binary


def run_kill(binary, directory):
    """Change an effect, SIGKILL the process 1 s later, then load the file in a new process."""
    process = subprocess.Popen([str(binary), 'effects-kill', str(directory)], env=qt_environment(),
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    line = process.stdout.readline()
    if line.strip() != 'SET':
        process.kill()
        raise RuntimeError('effects-kill did not reach SET: ' + line)
    time.sleep(KILL_AFTER_SECONDS)
    process.send_signal(signal.SIGKILL)
    stdout, stderr = process.communicate(timeout=10)
    killed = process.returncode == -signal.SIGKILL
    load = subprocess.run([str(binary), 'effects-load', str(directory)], env=qt_environment(),
                          capture_output=True, text=True, timeout=60)
    report = ('PASS' if killed else 'FAIL') + ' the process was killed with SIGKILL 1 s after the change\n'
    return subprocess.CompletedProcess(process.args, 0 if killed and load.returncode == 0 else 1,
                                       line + stdout + report + load.stdout, stderr + load.stderr)


def run(modes=MODES):
    """One CompletedProcess per mode, in the order given."""
    with tempfile.TemporaryDirectory(prefix='mixpi-agreed-controls-') as temporary:
        target = Path(temporary) / 'build'
        target.mkdir()
        stack(target)
        controls = build_controls(target) if set(modes) - {'selector'} else None
        selector = build_selector(target) if 'selector' in modes else None
        results = []
        for mode in modes:
            directory = Path(temporary) / 'run' / mode
            directory.mkdir(parents=True)
            if mode == 'effects-kill':
                result = run_kill(controls, directory)
            elif mode == 'selector':
                result = subprocess.run(
                    [str(selector), str(ROOT / 'stage3/01-install-packages/files/mixpi-performance.qss')],
                    env=qt_environment(), capture_output=True, text=True, timeout=60)
            else:
                result = subprocess.run([str(controls), mode, str(directory)], env=qt_environment(),
                                        capture_output=True, text=True, timeout=120)
            for path in directory.rglob('*'):
                path.chmod(0o755 if path.is_dir() else 0o644)
            print('MODE', mode, 'RC', result.returncode, result.stdout, result.stderr[-4000:],
                  flush=True)
            results.append(result)
        return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('modes', nargs='*')
    options = parser.parse_args()
    raise SystemExit(max(result.returncode for result in run(options.modes or list(MODES))))
