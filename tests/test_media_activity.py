import os
from pathlib import Path
import platform
import subprocess
import tempfile
import unittest

from native.library_interface_runner import qt_available, qt_flags, qt_environment

from native.library_interface_runner import reconstruct


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
class MediaActivityTests(unittest.TestCase):
    def run_native(self, holdout=False):
        with tempfile.TemporaryDirectory(prefix='mixpi-media-activity-') as temporary:
            target = Path(temporary)
            override = os.environ.get('MEDIA_ACTIVITY_SOURCE')
            source = Path(override).resolve() if override else target
            if not override:
                reconstruct(target)
            command = ['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror']
            if os.environ.get('MEDIA_ACTIVITY_BASELINE'):
                command += ['-DBASELINE']
            command += ['-I' + str(source / 'src'),
                        str(ROOT / 'tests/native/media_activity_test.cpp'),
                        '-o', str(target / 'test')]
            command += qt_flags()
            compiled = subprocess.run(command, capture_output=True, text=True, timeout=90)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            environment = qt_environment()
            result = subprocess.run([str(target / 'test'), *(['holdout'] if holdout else [])],
                                    env=environment, capture_output=True, text=True, timeout=30)
            print(result.stdout, result.stderr, flush=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_live_dialog_and_readonly_registry(self):
        self.run_native()

    def test_generation_replacement_holdout(self):
        self.run_native(holdout=True)
