"""Sources (agreed UI s5, build C U-4; was R-9 and R-10).

Sources is a side menu on the right (m-sources-top.png, m-sources-sub.png):
a 52 px header with [‹ BACK] [EDIT] at the top level, or [‹ BACK] and the
place inside a source; 52 px rows with the icon, the title, a small line, a
count at the right and › where a row can be entered; the current row has the
accent edge; a 24 px scroll bar when the list is longer than the panel. EDIT
opens the full-screen edit list (m-sources-edit.png): EDIT SOURCES, the hint,
DONE and the close ✕; rows with ★, icon, title and line, ON/OFF, ▲ UP and
▼ DOWN. The native part is mixxx-sources-menu.patch; its rules are in
mixpi-sources-menu.qss.

The native checks are in tests/native/library_interface_sources_test.cpp:
the real WLibrarySidebar at 320x380 at the right of an 800x480 screen for the
menu, and the actual Library methods for the edit list.
tests/test_library_interface.py runs the same fixture without the menu part.
"""
import importlib.util
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

from native.library_interface_runner import qt_available

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'library_interface_runner', ROOT / 'tests/native/library_interface_runner.py')
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)
PATCH = RUNNER.PATCH_DIR / 'mixxx-sources-screen.patch'
MENU_PATCH = RUNNER.PATCH_DIR / 'mixxx-sources-menu.patch'
MENU_QSS = RUNNER.PATCH_DIR / 'mixpi-sources-menu.qss'
FIXTURE = ROOT / 'tests/native/library_interface_sources_test.cpp'


def fixture_checks(function):
    """The name of every require(..., "name") in one function of the fixture."""
    source = FIXTURE.read_text()
    start = source.index('void ' + function + '(')
    end = source.index('\n}\n', start)
    body = source[start:end]
    names = []
    for begin in [match.end() for match in re.finditer(r'\brequire\(', body)]:
        names.append(re.findall(r'"([^"\n]*)"', body[begin:body.index(');', begin)])[-1])
    return names


def patch_names():
    return subprocess.check_output(['bash', str(ROOT / 'stage3/01-install-packages/01-run.sh'),
                                    '--mixxx-print-patches'], text=True).split()


class SourcesScreenPatchTests(unittest.TestCase):
    def test_patch_changes_only_the_library_interface_and_the_sidebar(self):
        self.assertEqual(sorted(re.findall(r'^diff --git a/(\S+) b/\S+$', PATCH.read_text(), re.MULTILINE)),
                         ['src/library/library.cpp', 'src/library/library.h',
                          'src/widget/libraryinterface.h', 'src/widget/wlibrarysidebar.cpp',
                          'src/widget/wlibrarysidebar.h'])

    def test_patch_follows_council_fixes(self):
        names = patch_names()
        self.assertLess(names.index('mixxx-council-fixes.patch'), names.index('mixxx-sources-screen.patch'))

    def test_edit_done_patch_confirms_the_read_only_editing_control(self):
        # Pi preview p5: EDIT LIST never read DONE. The control is read-only
        # for the skin, and set() on a read-only control is dropped, so the
        # sidebar confirms it (mixxx-sources-edit-done.patch).
        done = RUNNER.PATCH_DIR / 'mixxx-sources-edit-done.patch'
        text = done.read_text()
        self.assertEqual(sorted(re.findall(r'^diff --git a/(\S+) b/\S+$', text, re.MULTILINE)),
                         ['src/library/library.cpp', 'src/widget/wlibrarysidebar.cpp',
                          'src/widget/wlibrarysidebar.h'])
        added = '\n'.join(line for line in text.splitlines() if line.startswith('+'))
        self.assertIn('m_sourcesEditingControl->setAndConfirm(shown ? 1 : 0);', added)
        self.assertNotIn('m_sourcesEditingControl->set(', added)
        names = patch_names()
        self.assertLess(names.index('mixxx-source-groups.patch'), names.index('mixxx-sources-edit-done.patch'))


class SourcesMenuPatchTests(unittest.TestCase):
    def test_menu_patch_changes_only_its_files(self):
        self.assertEqual(sorted(re.findall(r'^diff --git a/(\S+) b/\S+$', MENU_PATCH.read_text(), re.MULTILINE)),
                         ['src/library/library.cpp', 'src/widget/libraryinterface.h',
                          'src/widget/touchsourcenavigation.h', 'src/widget/wlibrarysidebar.cpp',
                          'src/widget/wlibrarysidebar.h'])

    def test_menu_patch_comes_last(self):
        names = patch_names()
        if 'mixxx-sources-menu.patch' not in names:
            self.skipTest('mixxx-sources-menu.patch is not registered yet')
        self.assertLess(names.index('mixxx-sources-edit-done.patch'), names.index('mixxx-sources-menu.patch'))
        self.assertLess(names.index('mixxx-media-lists.patch'), names.index('mixxx-sources-menu.patch'))

    def test_side_menu_and_edit_list_in_the_reconstructed_source(self):
        if 'mixxx-sources-menu.patch' not in patch_names():
            self.skipTest('mixxx-sources-menu.patch is not registered yet')
        with tempfile.TemporaryDirectory(prefix='mixpi-sources-menu-') as temporary:
            target = Path(temporary)
            RUNNER.reconstruct(target)
            library = (target / 'src/library/library.cpp').read_text()
            interface = (target / 'src/widget/libraryinterface.h').read_text()
            sidebar = (target / 'src/widget/wlibrarysidebar.cpp').read_text()
        # Sizes from the agreed mockups (buttons at the 48 px touch minimum).
        for size in ('kSourceMenuWidth = 320', 'kSourceMenuHeaderHeight = 52', 'kSourceMenuRowHeight = 52',
                     'kSourceMenuButtonWidth = 88', 'kSourceTouch = 48', 'kSourceEditTopBar = 48',
                     'kSourceEditRowHeight = 52', 'kSourceEditDoneWidth = 96', 'kSourceEditSwitchWidth = 88',
                     'kSourceEditStepWidth = 84', 'kSourceScreenMinimumWidth = kSourceMenuWidth'):
            self.assertIn(size, interface)
        # Exact copy from the mockups.
        for words in ('tr("BACK")', 'tr("EDIT")'):
            self.assertIn(words, sidebar)
        for words in ('"EDIT SOURCES"', '"Switch sources on or off, set the order, ★ where Tracks starts."',
                      '"DONE"', '"▲ UP"', '"▼ DOWN"', '"TRACKS STARTS HERE"', '"ON"', '"OFF"',
                      '"USB · rekordbox"', '"Played tracks by date"', '"Browse files and drives"',
                      '"Sounds for the pads"'):
            self.assertIn(words, interface)
        # The mockups' icons: the ‹ chevron and the pencil on a list (not the
        # ✎ actions pencil of the skin).
        self.assertIn('<path d=\\"M15 5l-7 7 7 7\\"/>', interface)
        self.assertIn('<path d=\\"M3 6h10M3 11h8M3 16h5\\"/>', interface)
        self.assertIn('<path d=\\"M12 20l.6-3L19 10.6l2.4 2.4L15 19.4z\\"/>', interface)
        # The edit list is full screen under the top bar; EDIT in the menu
        # opens it through the Library.
        self.assertIn('pSidebarWidget->sourcesEditRequested = [this] {\n        showSidebarSourcesMenu();', library)
        self.assertIn('list->done = [this] {\n            m_pSidebarWidget->endSourcesEditing(false);', library)
        self.assertIn('list->closed = [this] {\n            m_pSidebarWidget->endSourcesEditing(true);', library)
        self.assertIn('QWidget* pHost = skinRoot(this);', sidebar)
        # The scroll bar starts under the header; no QMenu, no drag-to-reorder.
        self.assertIn('addScrollBarWidget(m_sourceScrollTop, Qt::AlignTop);', sidebar)
        edit = interface[interface.index('class SourceEditList'):]
        self.assertNotIn('InternalMove', edit)
        start = library.index('void Library::showSidebarSourcesMenu() {')
        menu = library[start:library.index('\n}\n', start)]
        self.assertNotIn('QMenu', menu)
        self.assertNotIn('popup(', menu)

    def test_style_has_every_menu_and_edit_rule(self):
        style = MENU_QSS.read_text()
        for selector in ('WLibrarySidebar[mixpiSourceMenu="true"]', '#MixpiSourcesMenuHeader',
                         'QPushButton#MixpiSourcesMenuBack', 'QPushButton#MixpiSourcesMenuEdit',
                         'QLabel#MixpiSourcesMenuPlace', 'QPushButton#MixpiSourcesMenuTile:checked',
                         '#MixpiSourcesMenuIcon', '#MixpiSourcesMenuChevron', '#MixpiSourcesMenuEdge',
                         '#MixpiSourcesEditHeader', 'QPushButton#MixpiSourcesEditDone',
                         'QPushButton#MixpiSourcesEditClose', 'QPushButton#MixpiSourcesEditStar[start="true"]',
                         'QCheckBox#MixpiSourcesEditSwitch[on="true"]', '#MixpiSourcesEditRow[off="true"]',
                         'QPushButton#MixpiSourcesEditUp:disabled'):
            self.assertIn(selector, style)
        # Section 1 rules: 3 px radius, 24 px scroll bars, no outline on the
        # close at rest (its border is its own fill), lit = 26% tint + 2 px.
        self.assertNotRegex(style, r'border-radius:\s*(?![03]px|4px|6px)\d+px')
        self.assertEqual(re.findall(r'QScrollBar:vertical \{\s*width: (\d+)px', style), ['24'])
        close = style[style.index('QPushButton#MixpiSourcesEditClose {'):]
        close = close[:close.index('}')]
        self.assertIn('background-color: #1d222a;', close)
        self.assertIn('border: 1px solid #1d222a;', close)
        self.assertIn('color: #ec7f74;', close)
        lit = style[style.index('QPushButton#MixpiSourcesEditStar[start="true"] {'):]
        lit = lit[:lit.index('}')]
        self.assertIn('rgba(163, 196, 94, 26%)', lit)
        self.assertIn('border: 2px solid #a3c45e;', lit)
        # Only the agreed tokens (and the mockups' scroll thumb, #5b6472).
        tokens = {'#0d1014', '#161a20', '#1d222a', '#262c35', '#13161b', '#2c333d', '#3a424e', '#e4e7ec',
                  '#949dab', '#7f8896', '#a3c45e', '#8fad50', '#253019', '#bcd88a', '#d6784a', '#d0574d',
                  '#ec7f74', '#34191b', '#5b6472',
                  # The off row: text, line and icon at 45% over the row.
                  '#73767c', '#4f555f', '#6c4433'}
        body = re.sub(r'/\*.*?\*/', '', style, flags=re.S)
        self.assertEqual(set(re.findall(r'#[0-9a-f]{6}\b', body)) - tokens, set())
        # Fonts are build B's (spec section 1 and 2a, build D): the families,
        # sizes and weights are checked in tests/test_fonts_build_b.py. Here
        # only the 13 px minimum for text.
        for size in re.findall(r'font-size: (\d+)px', style):
            self.assertGreaterEqual(int(size), 13)

    def test_old_sources_screen_rules_match_nothing_new(self):
        # The old #MixpiSource* rules in pioneered-menus.qss (removed in C2)
        # name no widget of the menu or the edit list.
        old = set(re.findall(r'#(MixpiSource[A-Za-z]*)', (RUNNER.PATCH_DIR / 'pioneered-menus.qss').read_text()))
        new = set(re.findall(r'"(MixpiSources[A-Za-z]*)"', MENU_PATCH.read_text()))
        self.assertTrue(new)
        self.assertEqual(old & new, set())

    @unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
    def test_native_sources_menu_and_edit_list(self):
        result = subprocess.run(['python3', str(ROOT / 'tests/native/library_interface_sources_runner.py'),
                                 '--sources-screen'], capture_output=True, text=True, timeout=200)
        self.assertEqual(result.returncode, 0, result.stdout[-6000:] + result.stderr[-3000:])
        checks = fixture_checks('sourceScreenChecks') + fixture_checks('editListChecks')
        self.assertGreaterEqual(len(checks), 60)
        for check in checks:
            self.assertIn('PASS ' + check, result.stdout)
        self.assertNotIn('FAIL ', result.stdout)


if __name__ == '__main__':
    unittest.main()
