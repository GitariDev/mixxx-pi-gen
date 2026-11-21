"""Wave J8: drive tracks with accented file names load.

rekordbox writes a DeviceSQL string as short ASCII, long ASCII or, when it
holds a character outside ASCII, long UTF-16LE (kind 0x90; the length field
counts the four-byte header too). Mixxx's Kaitai parser declared those bodies
as text in an encoding, so what reached getText depended on the string mode
the Kaitai runtime was built with: Mixxx's CMakeLists.txt builds it with
KS_STR_ENCODING_NONE (the bytes as stored, which getText's UTF-16LE decoding
expects), while a runtime built with KS_STR_ENCODING_ICONV (as the native
fixtures build it) hands over UTF-8, which getText then read as UTF-16LE:
garbage paths and titles. Separately, rekordbox stores paths precomposed
(NFC) while a drive filled on a Mac can hold the same names decomposed (NFD);
Linux finds names byte for byte, so such a file was not found.

mixxx-rekordbox-utf16-text.patch keeps the DeviceSQL bodies as the bytes in
the file in every Kaitai string mode (rekordbox_pdb.ksy and its generated
rekordbox_pdb.cpp), and insertTrack stores the file's path in the form the
drive holds when the export's form is missing (only looks; never writes).

The native checks are in tests/native/rekordbox_utf16_text_test.cpp.in, built
by tests/native/rekordbox_utf16_text_runner.py on the actual import.
"""
from pathlib import Path
import re
import subprocess
import sys
import unittest

from native.library_interface_runner import qt_available
from native import library_interface_runner as RUNNER
from test_sample_browser import checks

ROOT = Path(__file__).resolve().parents[1]
PATCH = RUNNER.PATCH_DIR / 'mixxx-rekordbox-utf16-text.patch'
TEST = ROOT / 'tests/native/rekordbox_utf16_text_test.cpp.in'
FEATURE = 'src/library/rekordbox/rekordboxfeature.cpp'
PARSER = 'lib/rekordbox-metadata/rekordbox_pdb.cpp'
SCHEMA = 'lib/rekordbox-metadata/rekordbox_pdb.ksy'
DECODING = ('every title decodes to the text written', 'every artist decodes to the text written',
            'every album decodes to the text written', 'every genre decodes to the text written',
            'every key decodes to the text written', 'every comment decodes to the text written',
            'playlist and folder names decode to the text written')
LOCATION = ("every track's location is its file on the drive",
            "every track's location names an existing file, so the row loads",
            "a file stored decomposed (NFD) on the drive is found from the export's NFC path")
ASCII_TRACKS = ('1', '2', '8')


def added(path):
    text = PATCH.read_text()
    start = text.index('diff --git a/' + path + ' ')
    end = text.find('\ndiff --git', start + 1)
    return '\n'.join(line[1:] for line in text[start:end if end > 0 else None].splitlines()
                     if line.startswith('+') and not line.startswith('+++'))


class RekordboxTextPatchTests(unittest.TestCase):
    def test_patch_changes_only_the_reader_and_its_parser(self):
        self.assertEqual(sorted(re.findall(r'^diff --git a/(\S+) b/\S+$', PATCH.read_text(), re.MULTILINE)),
                         [PARSER, SCHEMA, FEATURE])

    def test_patch_is_registered_after_the_drive_track_cache(self):
        names = subprocess.check_output(['bash', str(ROOT / 'stage3/01-install-packages/01-run.sh'),
                                         '--mixxx-print-patches'], text=True).split()
        if PATCH.name not in names:
            self.skipTest(PATCH.name + ' is not registered yet')
        self.assertLess(names.index('mixxx-drive-track-cache.patch'), names.index(PATCH.name))

    def test_device_sql_bodies_are_the_bytes_in_the_file(self):
        parser = added(PARSER)
        self.assertEqual(parser.count('m_text = m__io->read_bytes(length() - 4);'), 2)
        self.assertEqual(parser.count('m_text = m__io->read_bytes(length() - 1);'), 1)
        self.assertNotIn('bytes_to_str', parser)
        # The schema says the same, so a regenerated parser keeps it.
        schema = PATCH.read_text().split('diff --git a/' + SCHEMA)[1].split('\ndiff --git')[0]
        removed = [line for line in schema.splitlines() if line.startswith('-') and not line.startswith('---')]
        self.assertEqual(sorted(line.strip() for line in removed if 'encoding' in line),
                         ['-        encoding: ASCII', '-        encoding: ASCII', '-        encoding: UTF-16LE'])

    def test_location_takes_the_form_the_drive_holds(self):
        feature = added(FEATURE)
        self.assertIn('QString location = driveFileLocation(devicePath, getText(track->file_path()));', feature)
        self.assertIn('QString::NormalizationForm_D', feature)
        self.assertIn('QFile::exists(', feature)

    def test_read_only(self):
        feature = added(FEATURE)
        for writer in ('INSERT', 'UPDATE', 'DELETE', 'DROP', 'ofstream', 'QIODevice::WriteOnly', '.write(',
                       'rename', 'remove('):
            self.assertNotIn(writer, feature)


@unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
class RekordboxTextNativeTests(unittest.TestCase):
    def run_fixture(self, *arguments):
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'tests/native/rekordbox_utf16_text_runner.py'),
                                 *arguments], cwd=ROOT, capture_output=True, text=True, timeout=400)
        print(' '.join(arguments) or 'default', result.stdout[-5000:], result.stderr[-2000:], flush=True)
        return result

    def rows(self, output, tracks):
        return [line for line in output.splitlines()
                if line.startswith('ROW | rb_id=') and line.split('=', 1)[1].split(' ', 1)[0] in tracks]

    def assert_passes(self, result):
        self.assertEqual(result.returncode, 0, result.stdout[-6000:] + result.stderr[-3000:])
        for check in checks(TEST):
            self.assertIn('PASS ' + check, result.stdout)
        self.assertNotIn('FAIL ', result.stdout)
        self.assertIn('OK 0', result.stdout)

    def test_every_string_kind_decodes_with_kaitai_as_mixxx_builds_it(self):
        self.assert_passes(self.run_fixture('--kaitai', 'none'))

    def test_every_string_kind_decodes_with_an_iconv_kaitai(self):
        patched = self.run_fixture('--kaitai', 'iconv')
        self.assert_passes(patched)
        baseline = self.run_fixture('--kaitai', 'iconv', '--baseline')
        self.assertNotEqual(baseline.returncode, 0)
        for check in DECODING + LOCATION:
            self.assertIn('FAIL ' + check, baseline.stdout)
        # ASCII-only tracks read exactly as before.
        self.assertEqual(len(self.rows(patched.stdout, ASCII_TRACKS)), len(ASCII_TRACKS))
        self.assertEqual(self.rows(patched.stdout, ASCII_TRACKS), self.rows(baseline.stdout, ASCII_TRACKS))

    def test_decomposed_file_names_fail_without_the_patch(self):
        patched = self.run_fixture('--kaitai', 'none')
        baseline = self.run_fixture('--kaitai', 'none', '--baseline')
        self.assertNotEqual(baseline.returncode, 0)
        for check in LOCATION:
            self.assertIn('FAIL ' + check, baseline.stdout)
        # With the runtime as Mixxx builds it, the text itself already
        # decoded right before the patch; only the decomposed file is missed.
        for check in DECODING:
            self.assertIn('PASS ' + check, baseline.stdout)
        # Every track but the decomposed one is stored exactly as before.
        others = tuple(str(number) for number in range(1, 10) if number != 4)
        self.assertEqual(self.rows(patched.stdout, others), self.rows(baseline.stdout, others))
        self.assertEqual(len(self.rows(patched.stdout, others)), len(others))


if __name__ == '__main__':
    unittest.main()
