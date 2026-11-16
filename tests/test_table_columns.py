"""F-7/F-8: Browse defaults, stretch and saved header state (native Qt fixture)."""
from pathlib import Path
import shutil
import subprocess
import unittest

from native.library_interface_runner import qt_available

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / 'tests/native/table_columns_runner.py'


def native_ready():
    return qt_available() and shutil.which('protoc') is not None


class TableColumnsNativeTests(unittest.TestCase):
    @unittest.skipUnless(native_ready(), 'Qt6 and protobuf development tools required')
    def test_native_browse_defaults_stretch_and_persistence(self):
        result = subprocess.run(['python3', str(RUNNER)], capture_output=True, text=True,
                                timeout=600)
        self.assertEqual(result.returncode, 0, result.stdout[-4000:] + result.stderr[-4000:])
        self.assertIn('FAILURES 0', result.stdout)
        self.assertNotIn('FAIL ', result.stdout)

    @unittest.skipUnless(native_ready(), 'Qt6 and protobuf development tools required')
    def test_fixture_reproduces_the_field_fault_without_the_patch(self):
        result = subprocess.run(['python3', str(RUNNER), '--baseline'], capture_output=True,
                                text=True, timeout=600)
        self.assertEqual(result.returncode, 0, result.stdout[-4000:] + result.stderr[-4000:])
        self.assertIn('BASELINE_REPRODUCED', result.stdout)
        for check in ('FAIL every saved Browse column has a stable name',
                      'FAIL Browse order survives a model switch and a switch back',
                      'FAIL Browse default columns are Filename BPM Key Duration',
                      'FAIL library visible sections fill 770 px with Title'):
            self.assertIn(check, result.stdout)
        # The row itself is written on a model switch even before the fix.
        self.assertIn('PASS model switch writes mixxx.db.model.browse.header_state_pb', result.stdout)

    @unittest.skipUnless(native_ready(), 'Qt6 and protobuf development tools required')
    def test_width_checks_fail_without_acceptance_fixes(self):
        # Acceptance finding 4 (F-8): without the fix an added column keeps
        # its 0 px saved width and is drawn at the minimum section size.
        result = subprocess.run(['python3', str(RUNNER), '--without-acceptance-fixes'],
                                capture_output=True, text=True, timeout=600)
        self.assertEqual(result.returncode, 0, result.stdout[-4000:] + result.stderr[-4000:])
        self.assertIn('WITHOUT_ACCEPTANCE_FIXES_FAILS', result.stdout)
        self.assertIn('FAIL a column added in Arrange gets a readable width (at least 160 px)',
                      result.stdout)
        self.assertIn('FAIL a column shown from the header menu gets a readable width', result.stdout)
        self.assertIn('PASS saved Artist width (210 px) is restored after a restart', result.stdout)


if __name__ == '__main__':
    unittest.main()
