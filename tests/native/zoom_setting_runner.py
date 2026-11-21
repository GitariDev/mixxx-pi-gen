"""Wave J9: compile the shipped Zoom setting with real Qt and run each check.

Production code, from the patched stack: util/mixpizoomsetting.h (Settings ›
Interface, Zoom + and −), preferences/configobject.{h,cpp} (the save on
change and its timing) and the control framework (control, controlobject,
controlproxy, controlpotmeter, controlpushbutton, controlbehavior). The decks'
[ChannelN],waveform_zoom controls and the Loop panel's
[ChannelN],waveform_zoom_up/_down are fixture controls with the rules of
BaseTrackPlayerImpl (tests/test_zoom_setting.py checks that those rules are
still Mixxx's). The waveform factory's setDefaultZoom is a recording double.

Modes (each its own process and folder): steps, ends, loop, percent, kill (a change,
then SIGKILL 1 s later; a new process then reads mixxx.cfg as a restart
does). --baseline builds the stack without mixxx-zoom-setting.patch; the
header is then absent and the same checks must fail.
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
from native.agreed_controls_runner import DOUBLES, PINNED_FILES

ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT / 'tests/native'
PATCH = 'mixxx-zoom-setting.patch'
MODES = ('steps', 'ends', 'loop', 'percent', 'kill')
KILL_AFTER_SECONDS = 1.0


def stack(target, baseline):
    names, _ = reconstruct(target, exclude=(PATCH,) if baseline else ())
    if not baseline and PATCH not in names:
        subprocess.run(['git', 'apply', str(PATCH_DIR / PATCH)], cwd=target, check=True, timeout=15)
    populate_pinned(target, ['src/' + name for name in PINNED_FILES])
    return names


def build(target, baseline):
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
    binary = target / 'zoom-setting-test'
    command = ['c++', '-std=c++20', '-Wall', '-Wextra', *includes,
               *(['-DMIXPI_ZOOM_BASELINE=1'] if baseline else []),
               *[str(source) for source in sources],
               str(NATIVE / 'zoom_setting_test.cpp'), '-o', str(binary),
               '-pthread', *qt_flags(('QtCore', 'QtGui', 'QtWidgets', 'QtXml'))]
    print('COMPILE', repr(command), flush=True)
    subprocess.run(command, check=True, timeout=600)
    return binary


def run_kill(binary, directory):
    """Press +, SIGKILL the process 1 s later, then start a new process on the same mixxx.cfg."""
    process = subprocess.Popen([str(binary), 'kill', str(directory)], env=qt_environment(),
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    line = process.stdout.readline()
    if line.strip() != 'SET':
        process.kill()
        stdout, stderr = process.communicate(timeout=10)
        return subprocess.CompletedProcess(process.args, 1, line + stdout, stderr)
    time.sleep(KILL_AFTER_SECONDS)
    process.send_signal(signal.SIGKILL)
    stdout, stderr = process.communicate(timeout=10)
    killed = process.returncode == -signal.SIGKILL
    restart = subprocess.run([str(binary), 'restart', str(directory)], env=qt_environment(),
                             capture_output=True, text=True, timeout=60)
    report = ('PASS' if killed else 'FAIL') + ' the process was killed with SIGKILL 1 s after the tap\n'
    return subprocess.CompletedProcess(process.args, 0 if killed and restart.returncode == 0 else 1,
                                       line + stdout + report + restart.stdout, stderr + restart.stderr)


def run(modes=MODES, baseline=False):
    """One CompletedProcess per mode, in the order given."""
    with tempfile.TemporaryDirectory(prefix='mixpi-zoom-setting-') as temporary:
        target = Path(temporary) / 'build'
        target.mkdir()
        names = stack(target, baseline)
        print('PATCHES', len(names), 'BASELINE' if baseline else PATCH, flush=True)
        binary = build(target, baseline)
        results = []
        for mode in modes:
            directory = Path(temporary) / 'run' / mode
            directory.mkdir(parents=True)
            if mode == 'kill':
                result = run_kill(binary, directory)
            else:
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
