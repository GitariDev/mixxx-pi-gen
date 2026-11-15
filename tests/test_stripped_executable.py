import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'strip_check', ROOT / 'tools/performance/check-stripped-executable.py')
strip_check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(strip_check)


class StrippedExecutableTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.staged = self.root / 'staged'
        self.packaged = self.root / 'packaged'
        self.tool = self.root / 'strip'
        self.staged.write_bytes(b'code-with-symbols')
        self.packaged.write_bytes(b'code')
        self.tool.write_bytes(b'frozen-tool')
        self.tool_hash = strip_check.digest(self.tool)

    def run_check(self):
        return strip_check.verify(self.staged, self.packaged, self.tool, self.tool_hash)

    def fake_strip(self, command, **options):
        self.assertEqual(command[0:2], [str(self.tool), '-o'])
        self.assertEqual(command[3], str(self.staged))
        self.assertNotIn(Path(command[2]), (self.staged, self.packaged, self.tool))
        self.assertTrue(options['check'])
        self.assertEqual(options['timeout'], 60)
        Path(command[2]).write_bytes(b'code')

    def test_exact_equivalence_preserves_inputs_and_removes_scratch(self):
        with patch.object(strip_check.subprocess, 'run', side_effect=self.fake_strip) as run:
            receipt = self.run_check()
        self.assertEqual(receipt['strip_equivalence'], 'PASS')
        self.assertFalse(receipt['application_executed'])
        self.assertFalse(Path(run.call_args.args[0][2]).exists())
        self.assertEqual(self.staged.read_bytes(), b'code-with-symbols')
        self.assertEqual(self.packaged.read_bytes(), b'code')

    def test_changed_packaged_code_is_rejected(self):
        self.packaged.write_bytes(b'other-code')
        with patch.object(strip_check.subprocess, 'run', side_effect=self.fake_strip):
            with self.assertRaisesRegex(ValueError, 'differs'):
                self.run_check()

    def test_wrong_tool_is_rejected_before_execution(self):
        self.tool.write_bytes(b'replacement-tool')
        with patch.object(strip_check.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'frozen digest'):
                self.run_check()
        run.assert_not_called()

    def test_tool_failure_is_not_a_pass(self):
        with patch.object(strip_check.subprocess, 'run',
                          side_effect=subprocess.CalledProcessError(1, 'strip')):
            with self.assertRaises(subprocess.CalledProcessError):
                self.run_check()

    def test_mutation_during_verification_is_rejected(self):
        def mutate(command, **options):
            self.fake_strip(command, **options)
            self.staged.write_bytes(b'changed')

        with patch.object(strip_check.subprocess, 'run', side_effect=mutate):
            with self.assertRaisesRegex(ValueError, 'input changed'):
                self.run_check()

    def test_missing_output_is_not_a_pass(self):
        with patch.object(strip_check.subprocess, 'run'):
            with self.assertRaises(FileNotFoundError):
                self.run_check()


if __name__ == '__main__':
    unittest.main()
