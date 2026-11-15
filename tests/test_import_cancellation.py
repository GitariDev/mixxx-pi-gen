import os
from pathlib import Path
import subprocess
import sys
import unittest

from native.library_interface_runner import qt_available


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
class ImportCancellationTests(unittest.TestCase):
    def run_native(self, holdout=False):
        command = [sys.executable, '-B',
                   str(ROOT / 'tests/native/import_cancellation_runner.py')]
        if holdout:
            command.append('--holdout')
        result = subprocess.run(command, cwd=ROOT, capture_output=True,
                                text=True, timeout=180)
        print(result.stdout, result.stderr, flush=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_worker_rollback_and_lifecycle(self):
        self.run_native()

    def test_completion_races_and_replacement_holdout(self):
        self.run_native(holdout=True)
