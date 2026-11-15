import os
from pathlib import Path
import platform
import subprocess
import tempfile
import unittest

from native.library_interface_runner import qt_available, qt_flags, qt_environment

ROOT = Path(__file__).resolve().parents[1]


class RuntimeSelectionProbeTests(unittest.TestCase):
    @unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
    def test_exact_identity_and_no_click_refusals(self):
        self.run_native(False)

    @unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
    def test_reserved_sorted_filtered_identity(self):
        self.run_native(True)

    def run_native(self, holdout):
        with tempfile.TemporaryDirectory(prefix='mixpi-selection-probe-') as directory:
            target = Path(directory) / 'selection-test'
            command = ['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-DQT_WIDGETS_LIB', '-DQT_GUI_LIB']
            command += [str(ROOT / 'tests/native/runtime_selection_probe_test.cpp'), '-o', str(target)]
            command += qt_flags(('QtCore', 'QtGui', 'QtWidgets', 'QtTest'))
            subprocess.run(command, check=True, timeout=90)
            subprocess.run([str(target), 'holdout' if holdout else 'main'], check=True, timeout=20,
                           env=qt_environment())
