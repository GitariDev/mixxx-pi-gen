"""Build F (spec 2c, plan 12.7): one column setup for every track table.

The owner: "I want to keep the column setup across the different source menus
and have it be saved after edit like the settings." Columns, order and widths
are shared; sorting stays per list. Native Qt fixture
(tests/native/shared_columns_runner.py) plus source checks of the patch.
"""
from pathlib import Path
import shutil
import subprocess
import unittest

from native.library_interface_runner import qt_available

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / 'tests/native/shared_columns_runner.py'
PATCH = ROOT / 'stage3/01-install-packages/files/mixxx-shared-columns.patch'

NATIVE_CHECKS = (
    "first run: a playlist opened first shows This Pi > Tracks' columns, order and widths",
    'first run: the shared setup is written to mixxx.cfg',
    'first run: the old per-list rows stay as they were',
    'first run: the playlist keeps its own sort (BPM ascending)',
    'This Pi > Tracks shows the same setup',
    'This Pi > Tracks keeps its own sort (ARTIST descending)',
    'a folder (Browse) shows the shared columns in the shared order and widths',
    'a folder keeps its own Filename column in its default place',
    'the drag resized ARTIST to 270 px',
    'a resize by a drag in the header is on disk within 1 s',
    'a drag of 15 steps gives one write',
    'the new width shows in This Pi > Tracks',
    'the drag moved KEY to the front',
    'a move by a drag is on disk within 1 s',
    'a column moved in one list moves in the others (playlist)',
    '# shown from the header menu and dragged to third',
    'the header menu and the move are on disk within 1 s',
    'a column a list does not have is skipped there (# in This Pi > Tracks)',
    '# keeps its place (third) in the playlist after a change in This Pi > Tracks',
    'a column hidden in Arrange columns is on disk within 1 s',
    'a column hidden in Arrange columns is hidden in a folder too',
    '... and in the playlist, with its header menu box clear',
    'a column shown from the header menu is on disk within 1 s',
    'sort per list: This Pi > Tracks is still by TITLE ascending',
    'sort per list: the playlist is still by BPM descending',
    'sort per list: the folder is still by KEY ascending',
    'sorting changes nothing in the shared setup',
    'the old per-list rows are still unused and unchanged',
    'a change shows at once in another open table (Auto DJ)',
    'fit: the narrowed table fits its columns',
    'fit: the fitted widths are not saved',
    'fit: a move while narrowed is saved within 1 s',
    'fit: a change while narrowed saves the full widths, never the fitted ones',
    'close path: Sources closed, the table widens: full widths',
    'close path: Edit sources ✕ (table hidden): full widths',
    'close path: Edit sources ✕ (page hidden): full widths',
    'close path: a list picked, then ✕ while hidden: full widths',
    'fit: quitting while narrowed saves nothing fitted',
    'no DEBUG_ASSERT fired',
    'kill: the setup changed 2 s before a SIGKILL is there after a restart',
)


def native_ready():
    return qt_available() and shutil.which('protoc') is not None


class SharedColumnsNativeTests(unittest.TestCase):
    @unittest.skipUnless(native_ready(), 'Qt6 and protobuf development tools required')
    def test_one_column_setup_saved_on_change(self):
        result = subprocess.run(['python3', str(RUNNER)], capture_output=True, text=True, timeout=900)
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, result.stdout[-6000:] + result.stderr[-4000:])
        self.assertIn('FAILURES 0', result.stdout)
        self.assertNotIn('FAIL ', result.stdout)
        for check in NATIVE_CHECKS:
            self.assertIn('PASS ' + check, output)



class SharedColumnsPatchTests(unittest.TestCase):
    def setUp(self):
        self.patch = PATCH.read_text()

    def test_patch_touches_only_the_owned_files(self):
        touched = {line.split()[2][2:] for line in self.patch.splitlines() if line.startswith('diff --git ')}
        self.assertEqual(touched, {
            'src/widget/mixpisharedcolumns.h', 'src/widget/mixpitablefit.h',
            'src/widget/wtracktableview.cpp', 'src/widget/wtracktableviewheader.cpp',
            'src/widget/wtracktableviewheader.h'})

    def test_setup_is_a_setting_saved_by_the_autosave(self):
        # mixxx.cfg, written atomically within a second by the R-13 autosave.
        self.assertIn('QStringLiteral("SharedColumns")', self.patch)
        self.assertIn('pConfig->setValue(kSharedColumnsConfigKey, value);', self.patch)

    def test_first_run_reads_this_pi_tracks_and_leaves_old_rows(self):
        self.assertIn('"mixxx.db.model.library.header_state_pb"', self.patch)
        # The old per-list rows are never written again in shared mode.
        self.assertIn('const QString kSortSetting = QStringLiteral("mixpi_sort_pb");', self.patch)

    def test_fitted_widths_never_saved(self):
        self.assertIn('return m_columnFit.savedWidth(column);', self.patch)
        self.assertIn('if (event->type() == QEvent::Show && watched == parent()) {', self.patch)


if __name__ == '__main__':
    unittest.main()
