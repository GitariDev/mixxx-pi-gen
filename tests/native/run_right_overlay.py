"""Compile the exact patched production header with real Qt, without Mixxx."""
import argparse
import os
import platform
from pathlib import Path
import subprocess
import tempfile
from library_interface_runner import reconstruct, qt_flags, qt_environment

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('--baseline', action='store_true')
parser.add_argument('--holdout', action='store_true')
args = parser.parse_args()
with tempfile.TemporaryDirectory(prefix='mixpi-right-overlay-') as temporary:
    target = Path(temporary)
    if not args.baseline:
        reconstruct(target)
    command = ['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror']
    if not args.baseline:
        command += ['-DUSE_OVERLAY', '-I' + str(target / 'src')]
    command += [str(ROOT / 'tests/native/right_overlay_test.cpp'), '-o', str(target / 'test'), *qt_flags()]
    print('COMMAND', repr(command), flush=True)
    subprocess.run(command, check=True, timeout=60)
    environment = qt_environment()
    subprocess.run([str(target / 'test')] + (['holdout'] if args.holdout else []),
                   env=environment, check=True, timeout=20)
