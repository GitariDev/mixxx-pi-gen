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
COUNCIL = ROOT / 'stage3/01-install-packages/files/mixxx-council-fixes.patch'


def hunks(text, path):
    """The diff text of one file in a patch."""
    start = text.index(f'diff --git a/{path} b/{path}')
    end = text.find('diff --git ', start + 1)
    return text[start:end if end >= 0 else len(text)]


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


class SelectedDriveWordingPatchTests(unittest.TestCase):
    """F-10 with a drive selected: strings only in the Load/Eject files."""

    def test_selected_drive_strings_are_plain_and_nothing_else_changes(self):
        text = COUNCIL.read_text()
        for path in ('src/library/mixpimediadialog.h', 'src/library/mixpimedia.h'):
            diff = hunks(text, path).splitlines()
            removed = [line[1:] for line in diff if line.startswith('-') and not line.startswith('---')]
            added = [line[1:] for line in diff if line.startswith('+') and not line.startswith('+++')
                     and not line[1:].strip().startswith('//')]
            # Each changed line differs only in its string; the code is equal.
            def code(line):
                return re.sub(r'(tr|QStringLiteral)\("[^"]*"\)', 'S', line)
            self.assertEqual([code(line) for line in removed], [code(line) for line in added], path)
            self.assertTrue(removed, path)
        added = '\n'.join(line[1:] for line in hunks(text, 'src/library/mixpimediadialog.h').splitlines()
                          if line.startswith('+') and not line.startswith('+++'))
        self.assertIn('Eject is not available on this system. Keep the drive connected.', added)
        for internal in ('reviewed', 'service', 'clearance', 'retained', 'observation', 'discovery'):
            self.assertNotIn(internal, added)


@unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
class MediaTransferDisplayTests(unittest.TestCase):
    def run_native(self, holdout=False, without_council=False, expect_pass=True):
        with tempfile.TemporaryDirectory(prefix='mixpi-transfer-display-') as temporary:
            target = Path(temporary)
            reconstruct(target, exclude=('mixxx-council-fixes.patch',) if without_council else ())
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
            files = ROOT / 'stage3/01-install-packages/files'
            environment['MIXPI_SKIN_QSS'] = ':'.join(
                str(files / name) for name in ('pioneered-menus.qss', 'mixpi-media-page.qss',
                                               'pioneered-touch.qss', 'mixpi-performance.qss'))
            result = subprocess.run([str(executable), *(['holdout'] if holdout else [])],
                                    env=environment, capture_output=True, text=True, timeout=30)
            print(result.stdout, result.stderr, flush=True)
            if expect_pass:
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return result

    def test_actual_dialog_transfer_labels(self):
        result = self.run_native()
        self.assertIn('0 failures', result.stdout)

    def test_selected_drive_checks_fail_without_council_fixes(self):
        # F-10 (council round 1): with the build-2 strings the selected-drive
        # status line has internal terms, and the checks say so.
        result = self.run_native(without_council=True, expect_pass=False)
        self.assertNotEqual(result.returncode, 0)
        for failure in ('selected dialog labels have no internal terms or device number',
                        'selected drive: no visible label has an internal term or device number',
                        'selected drive: the status line says eject is not available, as the '
                        'controlled dialog does'):
            self.assertIn('FAIL ' + failure, result.stderr)
        self.assertNotIn('FAIL selected drive: the controlled dialog shows exactly', result.stderr)
        self.assertNotIn('FAIL selected drive: no unmount or eject request is made', result.stderr)

    def test_bounded_history_and_active_jobs_holdout(self):
        self.run_native(holdout=True)
