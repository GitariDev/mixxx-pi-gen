"""Native paired-key widget compilation; not full application acceptance."""
import importlib.util
import os
from pathlib import Path
import unittest

from native.library_interface_runner import qt_available

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
class NativeKeyWidgetTests(unittest.TestCase):
    def test_shipping_widget_and_native_formatter(self):
        spec = importlib.util.spec_from_file_location(
            'key_widget_runner', ROOT / 'tests/native/key_widget_runner.py')
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        runner.run()


if __name__ == '__main__':
    unittest.main()
