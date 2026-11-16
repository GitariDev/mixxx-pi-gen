"""Compile the shipped util/unixsignalquit.h and send the test app real signals.

Production: src/util/unixsignalquit.h from the patched stack, real Qt event
loop and QSocketNotifier. With --without-clean-quit the stack is rebuilt
without mixxx-clean-quit.patch; the header is then absent, so the fixture is
built as the pinned app (no handler) and the same checks must fail.
"""
import argparse
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native.library_interface_runner import qt_flags, qt_environment

ROOT = Path(__file__).resolve().parents[2]
PATCH = 'mixxx-clean-quit.patch'
MODES = ('term', 'early', 'hup')


def reconstruction():
    spec = importlib.util.spec_from_file_location(
        'library_reconstruction', ROOT / 'tests/native/library_interface_runner.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(without_clean_quit=False):
    """One CompletedProcess per mode, in MODES order."""
    with tempfile.TemporaryDirectory(prefix='mixpi-clean-quit-') as temporary:
        target = Path(temporary)
        reconstruction().reconstruct(target, exclude=(PATCH,) if without_clean_quit else ())
        header = target / 'src/util/unixsignalquit.h'
        if header.exists() == without_clean_quit:
            raise RuntimeError('unexpected handler header state: ' + str(header.exists()))
        command = ['c++', '-std=c++20', '-I' + str(target / 'src')]
        if without_clean_quit:
            command.append('-DMIXPI_PINNED_NO_HANDLER')
        command += [str(ROOT / 'tests/native/clean_quit_test.cpp'),
                    '-o', str(target / 'clean-quit-test'), *qt_flags(('QtCore',))]
        print('COMPILE', repr(command), flush=True)
        subprocess.run(command, check=True, timeout=180)
        results = []
        for mode in MODES:
            result = subprocess.run([str(target / 'clean-quit-test'), mode], env=qt_environment(),
                                    capture_output=True, text=True, timeout=30)
            print('MODE', mode, 'RC', result.returncode, result.stdout, result.stderr, flush=True)
            results.append(result)
        return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--without-clean-quit', action='store_true')
    options = parser.parse_args()
    raise SystemExit(max(abs(result.returncode) for result in run(options.without_clean_quit)))
