import os
from pathlib import Path
import subprocess
import sys
import unittest

from native.library_interface_runner import qt_available

from test_media_ownership import production_file

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / ('tests/native/import_cancellation_continuation_runner.py'
                 if os.environ.get('MIXXX_IMPORT_CANCELLATION_PATCH')
                 else 'tests/native/media_continuation_runner.py')


class MediaContinuationTests(unittest.TestCase):
    @unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
    def test_native_first_use_and_merged_dialog(self):
        subprocess.run([sys.executable, str(RUNNER)],
                       check=True, timeout=150)

    @unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
    def test_reserved_cancellation_identity_and_admission_cases(self):
        subprocess.run([sys.executable, str(RUNNER), '--holdout'],
                       check=True, timeout=150)

    def test_async_entry_is_wired_and_only_success_clears_load_modes(self):
        source = production_file('src/library/library.cpp')
        self.assertIn('return openRemovableSourceAsync(volume, receiver, std::move(completion))', source)
        self.assertIn('QString::fromStdString(observed.database), receiver', source)
        self.assertIn('if (result.isEmpty()) {\n                    ControlObject::set', source)

    def test_discovery_allowlist_never_becomes_a_selection_callback(self):
        source = production_file('src/library/rekordbox/rekordboxfeature.cpp')
        self.assertIn('m_pendingSelection->cancel()', source)
        self.assertIn('m_deviceRefreshPending || m_deviceDiscoveryActive || m_trackImportActive', source)
        self.assertIn('m_pImportingDevice != item || !m_importMediaUse', source)


if __name__ == '__main__':
    unittest.main()
