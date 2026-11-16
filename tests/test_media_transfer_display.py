import os
from pathlib import Path
import platform
import re
import subprocess
import tempfile
import unittest

from native.library_interface_runner import qt_available, qt_flags, qt_environment

from native.library_interface_runner import reconstruct


ROOT = Path(__file__).resolve().parents[1]


WORDING = ROOT / 'stage3/01-install-packages/files/mixxx-dialog-wording.patch'


class DialogWordingPatchTests(unittest.TestCase):
    """F-10: strings only; the eject gate and controlled media are untouched."""

    def test_new_user_strings_keep_the_safety_meaning(self):
        text = WORDING.read_text()
        added = '\n'.join(line[1:] for line in text.splitlines()
                          if line.startswith('+') and not line.startswith('+++'))
        for wording in ('Mixxx is not using this drive. This does not mean it is safe to remove.',
                        'Mixxx may still use this drive.', 'No copy has run yet.',
                        'The last copy was interrupted.', 'The last copy result is not available.'):
            self.assertIn(f'QStringLiteral("{wording}")', added)
        # With controlled media off, Eject opens the controlled dialog in its
        # unavailable state; its first message now says so in plain words.
        self.assertIn('tr("Eject is not available on this system. Keep the drive connected.")', added)
        self.assertNotIn('reviewed profile/service', added)
        for internal in ('clearance', 'retained', 'Unresolved', 'progress unavailable'):
            self.assertNotIn(internal, added)
        self.assertEqual(sorted(re.findall(r'^diff --git a/(\S+) ', text, re.MULTILINE)),
                         ['src/library/mixpicontrolledmedia.h', 'src/library/mixpimediaactivity.h',
                          'src/library/mixpimediadialog.h'])
        self.assertNotIn('setEnabled', added)
        self.assertNotIn('m_controlled', added)


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
