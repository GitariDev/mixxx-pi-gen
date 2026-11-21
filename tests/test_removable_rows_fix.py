"""Council round 6 (wave J11): Removable Devices keeps rows that are not drives.

Found by council round 6 (Fable) and confirmed on the card (acceptance K,
70-now.png): J10's BrowseFeature::releaseGoneFolder
(mixxx-eject-folders-view.patch) removed from Folders › Removable Devices
every row whose path was not in the mount table, on any mount change (a
plug-in, a pull, an eject). The card's /media/SD-Backup is a plain folder of
the Pi's own card (stage3/02-desktop/04-run.sh), never a mount point, so it
left the list until the list was opened again. Build B and stock Mixxx list
it.

mixxx-removable-rows-fix.patch: releaseGoneFolder remembers the mount points
it saw when it last read the mount table (BrowseFeature::m_seenMounts) and
drops only a row that was one of them and is not mounted now. Everything else
J10 does stays: the folder shown in Tracks goes when its mount goes, ☰ lands
on the top level, / never goes, and only the mount table is read.

The native checks are in tests/native/removable_rows_fix_test.cpp (built by
tests/native/removable_rows_fix_runner.py).
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
PATCH = RUNNER.PATCH_DIR / 'mixxx-removable-rows-fix.patch'
TEST = ROOT / 'tests/native/removable_rows_fix_test.cpp'
FEATURE = 'src/library/browse/browsefeature.cpp'
HEADER = 'src/library/browse/browsefeature.h'


def changed(path, sign):
    text = PATCH.read_text()
    start = text.index('diff --git a/' + path + ' ')
    end = text.find('\ndiff --git', start + 1)
    return [line[1:] for line in text[start:end if end > 0 else None].splitlines()
            if line.startswith(sign) and not line.startswith(sign * 3)]


class RemovableRowsFixPatchTests(unittest.TestCase):
    def test_patch_changes_only_the_browse_feature(self):
        self.assertEqual(sorted(re.findall(r'^diff --git a/(\S+) b/\S+$', PATCH.read_text(), re.MULTILINE)),
                         [FEATURE, HEADER])
        self.assertEqual(changed(HEADER, '-'), [])

    def test_patch_is_registered_last_after_j10(self):
        names = subprocess.check_output(['bash', str(ROOT / 'stage3/01-install-packages/01-run.sh'),
                                         '--mixxx-print-patches'], text=True).split()
        if PATCH.name not in names:
            self.skipTest(PATCH.name + ' is not registered yet')
        self.assertEqual(names[-2:], ['mixxx-eject-folders-view.patch', PATCH.name])

    def test_only_a_row_that_was_a_mount_point_goes(self):
        removed = changed(FEATURE, '-')
        added = '\n'.join(changed(FEATURE, '+'))
        # J10's two lines that dropped every row not in the mount table.
        self.assertEqual([line.strip() for line in removed], [
            'for (int row = 0; !points.isEmpty() && row < root->childRows(); ++row) {',
            'if (!points.contains(QDir::cleanPath(pDevices->child(device)->getData().toString()))) {'])
        for line in ('for (const QString& point : std::as_const(m_seenMounts)) {',
                     'if (!points.contains(point)) {', 'gone.append(point);',
                     'if (!points.isEmpty()) {', 'm_seenMounts = points;',
                     'for (int row = 0; !gone.isEmpty() && row < root->childRows(); ++row) {',
                     'if (gone.contains(QDir::cleanPath(pDevices->child(device)->getData().toString()))) {'):
            self.assertIn(line, added)
        self.assertIn('QStringList m_seenMounts;', '\n'.join(changed(HEADER, '+')))
        # Read only: nothing on a drive, no settings.
        for writer in ('QIODevice::WriteOnly', '.write(', 'setValue', 'QDir(', 'QFileInfo(', 'entryInfoList'):
            self.assertNotIn(writer, added)


@unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
class RemovableRowsFixNativeTests(unittest.TestCase):
    def run_fixture(self, *arguments):
        return subprocess.run([sys.executable, '-B', str(ROOT / 'tests/native/removable_rows_fix_runner.py'),
                               *arguments], cwd=ROOT, capture_output=True, text=True, timeout=300)

    def test_native_removable_rows_fix(self):
        result = self.run_fixture()
        print(result.stdout[-4000:], result.stderr[-2000:], flush=True)
        self.assertEqual(result.returncode, 0, result.stdout[-6000:] + result.stderr[-3000:])
        for check in checks(TEST):
            self.assertIn('PASS ' + check, result.stdout)
        self.assertNotIn('FAIL ', result.stdout)
        self.assertIn('OK 0', result.stdout)
        self.assertGreaterEqual(len(checks(TEST)), 15)

    def test_checks_fail_without_the_patch(self):
        result = self.run_fixture('--baseline')
        print(result.stdout[-4000:], result.stderr[-2000:], flush=True)
        self.assertNotEqual(result.returncode, 0)
        for check in ('J11 pull: the open list keeps SD-Backup (a plain folder, never a mount)',
                      'J11 eject: the open list keeps SD-Backup',
                      'J11 plug-in: the open list keeps SD-Backup',
                      'J11: with SD-Backup\'s folder in Tracks a pull leaves the table, the row and the menu alone',
                      'J10 with J11: Removable Devices drops GANDER1 and keeps SD-Backup and IXIAN'):
            self.assertIn('FAIL ' + check, result.stdout)
        # J10 holds without this patch: a gone drive's row and its folder go.
        for check in ('J11 pull: the pulled drive\'s row (GANDER1) goes',
                      'J11 eject: the ejected drive\'s row (IXIAN) goes',
                      'J10 with J11: the pulled drive\'s folder leaves the table',
                      'J10 with J11: ☰ opens at the top level, no edge, nothing current',
                      'nothing on the drives or in SD-Backup was written'):
            self.assertIn('PASS ' + check, result.stdout)


if __name__ == '__main__':
    unittest.main()
