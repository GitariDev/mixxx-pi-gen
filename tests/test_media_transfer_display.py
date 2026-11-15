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
class MediaTransferDisplayTests(unittest.TestCase):
    def run_native(self, holdout=False):
        with tempfile.TemporaryDirectory(prefix='mixpi-transfer-display-') as temporary:
            target = Path(temporary)
            reconstruct(target)
            provider = (target / 'src/library/mixpimedia.h').read_text()
            self.assertIn('copyService().transferStatus(binding)', provider)
            self.assertLess(provider.index('binding.source != selected.revision'),
                            provider.index('copyService().transferStatus(binding)'))
            command = ['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror']
            executable = target / 'test'
            command += ['-I' + str(target / 'src'),
                        str(ROOT / 'tests/native/media_transfer_display_test.cpp'),
                        '-o', str(executable)]
            command += qt_flags()
            compiled = subprocess.run(command, capture_output=True, text=True, timeout=90)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            environment = qt_environment()
            result = subprocess.run([str(executable), *(['holdout'] if holdout else [])],
                                    env=environment, capture_output=True, text=True, timeout=30)
            print(result.stdout, result.stderr, flush=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_actual_dialog_transfer_labels(self):
        self.run_native()

    def test_bounded_history_and_active_jobs_holdout(self):
        self.run_native(holdout=True)
