import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from native.library_interface_runner import qt_available

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'library_interface_runner', ROOT / 'tests/native/library_interface_runner.py')
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class LibraryInterfacePatchTests(unittest.TestCase):
    @unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
    def test_native_actions_active_view_routing(self):
        subprocess.run(['python3', str(ROOT / 'tests/native/library_actions_routing_runner.py')],
                       check=True, timeout=150)

    @unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
    def test_native_actions_view_churn_holdout(self):
        subprocess.run(['python3', str(ROOT / 'tests/native/library_actions_routing_runner.py'),
                        '--holdout'], check=True, timeout=150)

    @unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
    def test_native_sources_model_and_persistence(self):
        subprocess.run(['python3', str(ROOT / 'tests/native/library_interface_sources_runner.py')],
                       check=True, timeout=150)

    @unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
    def test_native_sources_churn_serialization_index_holdout(self):
        subprocess.run(['python3', str(ROOT / 'tests/native/library_interface_sources_runner.py'),
                        '--holdout'], check=True, timeout=150)

    def test_full_stack_apply_reverse_restores_pinned_bytes(self):
        with tempfile.TemporaryDirectory(prefix='mixpi-library-interface-stack-') as temporary:
            target = Path(temporary)
            names, baseline = RUNNER.reconstruct(target)
            for name in reversed(names):
                subprocess.run(['git', 'apply', '--reverse', '--check',
                                str(RUNNER.PATCH_DIR / name)], cwd=target, check=True)
                subprocess.run(['git', 'apply', '--reverse',
                                str(RUNNER.PATCH_DIR / name)], cwd=target, check=True)
            restored = {str(path.relative_to(target)): path.read_bytes()
                        for path in target.rglob('*') if path.is_file()}
            self.assertEqual(baseline, restored)


if __name__ == '__main__':
    unittest.main()
