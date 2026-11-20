"""Wave J6: sorting a drive's list never empties the table.

The owner, 2026-11-20 16:03 on the card: on a rekordbox drive list, a tap on
the KEY header emptied the table. Stock Mixxx sorts KEY by "CASE key_id ...",
and only This Pi's own library has key_id; rekordbox_library has only the key
text, so the query fails and filterAndSort() gives no row an index. Owner:
"Let's fix that for all columns where this could happen."

mixxx-external-sort.patch:
- a table without key_id (rekordbox, Serato, Traktor) sorts KEY by its key
  text, in This Pi's order (circle of fifths in the user's notation); each key
  text is read as This Pi reads a key tag (KeyUtils::guessKeyFromText());
- if a sort query still fails, filterAndSort() keeps the rows in their
  previous order and logs it, so the table never empties;
- This Pi's own library, the column setup and every drive stay as they were.

The native checks are in tests/native/external_sort_test.cpp.in, built by
tests/native/external_sort_runner.py with every external table's production
schema and column list.
"""
from pathlib import Path
import os
import re
import subprocess
import sys
import unittest

from native.library_interface_runner import qt_available
from native import library_interface_runner as RUNNER

ROOT = Path(__file__).resolve().parents[1]
PATCH = RUNNER.PATCH_DIR / 'mixxx-external-sort.patch'
TEST = ROOT / 'tests/native/external_sort_test.cpp.in'


def checks(path=TEST):
    """The name of every check(QStringLiteral("name") ...) in the fixture, as a pattern."""
    names = re.findall(r'check\(QStringLiteral\("([^"]+)"\)', path.read_text())
    return names


def added(path):
    text = PATCH.read_text()
    start = text.index('diff --git a/' + path + ' ')
    end = text.find('\ndiff --git', start + 1)
    return '\n'.join(line[1:] for line in text[start:end if end > 0 else None].splitlines()
                     if line.startswith('+') and not line.startswith('+++'))


def removed():
    return [line for line in PATCH.read_text().splitlines()
            if line.startswith('-') and not line.startswith('---')]


class ExternalSortPatchTests(unittest.TestCase):
    def test_patch_changes_only_the_track_cache_and_column_cache(self):
        self.assertEqual(sorted(re.findall(r'^diff --git a/(\S+) b/\S+$', PATCH.read_text(), re.MULTILINE)),
                         ['src/library/basetrackcache.cpp', 'src/library/basetrackcache.h',
                          'src/library/columncache.cpp'])

    def test_patch_only_adds(self):
        # Nothing of stock Mixxx is taken away: This Pi's key_id CASE stays.
        self.assertEqual(removed(), [])

    def test_patch_is_registered_after_the_quit_fix(self):
        names = subprocess.check_output(['bash', str(ROOT / 'stage3/01-install-packages/01-run.sh'),
                                         '--mixxx-print-patches'], text=True).split()
        if PATCH.name not in names:
            self.skipTest(PATCH.name + ' is not registered yet')
        self.assertLess(names.index('mixxx-quit-library-widget.patch'), names.index(PATCH.name))

    def test_key_sort_reads_only_key_text_where_there_is_no_key_id(self):
        cache = added('src/library/basetrackcache.cpp')
        self.assertIn('fieldIndex(ColumnCache::COLUMN_LIBRARYTABLE_KEY_ID) < 0', cache)
        self.assertIn('KeyUtils::guessKeyFromText(text)', cache)
        self.assertIn('KeyUtils::keyToCircleOfFifthsOrder(key, notation)', cache)
        self.assertIn('literal.replace(quote, QStringLiteral("\'\'"));', cache)
        columns = added('src/library/columncache.cpp')
        self.assertIn('if (m_columnIndexByEnum[COLUMN_LIBRARYTABLE_KEY_ID] < 0) {', columns)

    def test_failed_sort_keeps_rows(self):
        cache = added('src/library/basetrackcache.cpp')
        self.assertIn('keepPreviousOrder(filter, trackIds, trackToIndex);', cache)
        self.assertIn('LOG_FAILED_QUERY(query);', cache)
        self.assertIn('rows in their previous order', cache)

    def test_patch_reads_only(self):
        text = '\n'.join(added(path) for path in ('src/library/basetrackcache.cpp', 'src/library/columncache.cpp'))
        for writer in ('INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER', 'QIODevice::WriteOnly',
                       'ofstream', '.write('):
            self.assertNotIn(writer, text)


@unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
class ExternalSortNativeTests(unittest.TestCase):
    def run_fixture(self, *arguments):
        return subprocess.run([sys.executable, '-B', str(ROOT / 'tests/native/external_sort_runner.py'),
                               *arguments], cwd=ROOT, capture_output=True, text=True, timeout=900)

    def test_native_external_sort(self):
        result = self.run_fixture()
        print(result.stdout[-6000:], result.stderr[-8000:], flush=True)
        self.assertEqual(result.returncode, 0, result.stdout[-6000:] + result.stderr[-3000:])
        passed = re.findall(r'^PASS (.+)$', result.stdout, re.MULTILINE)
        self.assertNotIn('FAIL ', result.stdout)
        self.assertIn('OK 0', result.stdout)
        # 6 tables x 2 sort checks, 3 key tables x 3 notations, This Pi, 2 failed-sort checks, read only.
        self.assertEqual(len(passed), 6 * 2 + 3 * 3 + 1 + 2 + 1, passed)
        for table in ('rekordbox', 'Serato', 'iTunes', 'Traktor', 'Rhythmbox', 'Banshee'):
            self.assertIn(table + ': every column sorts ascending and descending with all 14 rows', passed)
            self.assertIn(table + ': tapping every header in turn (sort history of 3) keeps all 14 rows', passed)
        for table in ('rekordbox', 'Serato', 'Traktor'):
            for notation in ('OpenKey', 'Lancelot', 'Traditional'):
                self.assertIn("%s: KEY sorts in This Pi's order (circle of fifths, %s), both ways"
                              % (table, notation), passed)
        self.assertIn("This Pi: KEY still sorts by Mixxx's own key_id CASE", passed)
        self.assertGreaterEqual(len(checks()), 7)

    def test_checks_fail_without_the_patch(self):
        result = self.run_fixture('--baseline')
        print(result.stdout[-6000:], result.stderr[-8000:], flush=True)
        self.assertNotEqual(result.returncode, 0)
        for check in ('rekordbox: every column sorts ascending and descending with all 14 rows',
                      'Serato: every column sorts ascending and descending with all 14 rows',
                      'Traktor: every column sorts ascending and descending with all 14 rows',
                      'rekordbox: tapping every header in turn (sort history of 3) keeps all 14 rows',
                      "rekordbox: KEY sorts in This Pi's order (circle of fifths, OpenKey), both ways",
                      'rekordbox: a sort query that fails keeps all 14 rows, in the previous order',
                      'rekordbox: a first sort that fails still shows all 14 rows'):
            self.assertIn('FAIL ' + check, result.stdout)
        self.assertIn('  key ASC: 0 rows', result.stdout)
        # Tables without a KEY column, and This Pi, sort without the patch too.
        for check in ('iTunes: every column sorts ascending and descending with all 14 rows',
                      'Rhythmbox: every column sorts ascending and descending with all 14 rows',
                      'Banshee: every column sorts ascending and descending with all 14 rows',
                      "This Pi: KEY still sorts by Mixxx's own key_id CASE",
                      'sorting writes nothing: every table keeps its rows and values'):
            self.assertIn('PASS ' + check, result.stdout)


if __name__ == '__main__':
    unittest.main()
