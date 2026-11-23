"""Three-band waveforms: compile the shipped setting and height rule with real Qt and run each check.

Production code, from the patched stack: util/mixpiwaveformcolours.h
(Settings › Advanced, Waveform colours: [MixPi],waveform_colours),
waveform/mixpiwaveformgain.h (heightCompensation: the main waveforms skip the
Filtered renderer's doubled height), preferences/configobject.{h,cpp} (the
save on change and its timing) and the control framework (control,
controlobject, controlproxy, controlpotmeter, controlpushbutton,
controlbehavior). The waveform factory's switch
(WaveformWidgetFactory::setWidgetTypeFromHandle) is a recording double;
tests/test_waveform_three_band.py checks the CoreServices wiring to it.

Modes (each its own process and folder): setting, refused, start, height.
--baseline builds the stack without mixxx-waveform-three-band.patch; the
setting and heightCompensation are then absent and the same checks must fail.
"""
import argparse
from pathlib import Path
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
MODES = ('setting', 'refused', 'start', 'height')


def stack(target, baseline):
    names, _ = reconstruct(target, exclude=(PATCH,) if baseline else ())
    if not baseline and PATCH not in names:
        subprocess.run(['git', 'apply', str(PATCH_DIR / PATCH)], cwd=target, check=True, timeout=15)
        names.append(PATCH)
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
