"""R-9 and R-10: Sources full screen (rail, Back, crumb, auto-close) and
Sources edit (one list instead of the Sources menu).

The native checks are in tests/native/library_interface_sources_test.cpp: the
real WLibrarySidebar at 800x384 for the Sources screen, and the actual Library
methods for Sources edit. tests/test_library_interface.py runs the same
fixture without the Sources screen part.
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

SCREEN_CHECKS = (
    'an 800 px touch sidebar shows the Sources screen',
    'at 800x384 the rail is 264 px wide and fills the height',
    'the list takes the right part, under a 48 px bar',
    'the rail lists the visible sources in saved order and skips hidden ones',
    'rail tiles are 64 px high',
    'a tile has the source name and the sub-line for its kind',
    'Back is 96x48 above the list and off at the top level',
    'Sources rows are at least 56 px',
    "a tap on a tile shows that source's lists on the right",
    'the crumb names the source, Back is on and its tile is lit',
    'a tap on a row with children drills in; the crumb shows the path',
    'a tap on a list without children opens it once and closes Sources (each control written once)',
    'a drag over three rows scrolls the list and opens nothing',
    'a row that shows nothing yet (a drive still loading) keeps Sources open',
    'a drag on the rail scrolls it and opens no source',
    'the rail follows a new saved order',
    'a model reset during a drill returns to the top and rebuilds the rail',
    'Sources edit takes the right part, the rail stays, and the editing control is 1',
    'DONE restores the navigation view',
    'a narrow touch sidebar keeps the one-list layout',
)
EDIT_CHECKS = (
    'EDIT LIST shows the Sources edit list in place of the Sources list',
    'Sources edit is one list: no menu, no second order list',
    'edit rows are 56 px; Up, Down and Start here 48 px; the switch 64x48; text 13 px or more',
    'a grab of Sources edit is dark',
    'a switch writes the same SidebarSource key as before and shows the source',
    "the last visible source's switch is disabled",
    'Up moves a source and saves the order',
    'Down moves it back and saves the order',
    'Start here writes the start source and its row carries the star',
    'switching an optional source on loads it once, at its saved place',
    'a drag on Sources edit scrolls it and presses nothing',
    'DONE ends Sources edit and shows the list again',
)


class SourcesScreenPatchTests(unittest.TestCase):
    def test_patch_changes_only_the_library_interface_and_the_sidebar(self):
        self.assertEqual(sorted(re.findall(r'^diff --git a/(\S+) b/\S+$', PATCH.read_text(), re.MULTILINE)),
                         ['src/library/library.cpp', 'src/library/library.h',
                          'src/widget/libraryinterface.h', 'src/widget/wlibrarysidebar.cpp',
                          'src/widget/wlibrarysidebar.h'])

    def test_patch_follows_council_fixes(self):
        names = subprocess.check_output(['bash', str(ROOT / 'stage3/01-install-packages/01-run.sh'),
                                         '--mixxx-print-patches'], text=True).split()
        self.assertLess(names.index('mixxx-council-fixes.patch'), names.index('mixxx-sources-screen.patch'))

    def test_sources_menu_is_replaced_by_the_edit_list(self):
        with tempfile.TemporaryDirectory(prefix='mixpi-sources-screen-') as temporary:
            target = Path(temporary)
            RUNNER.reconstruct(target)
            library = (target / 'src/library/library.cpp').read_text()
            interface = (target / 'src/widget/libraryinterface.h').read_text()
            sidebar = (target / 'src/widget/wlibrarysidebar.cpp').read_text()
        start = library.index('void Library::showSidebarSourcesMenu() {')
        menu = library[start:library.index('\n}\n', start)]
        self.assertNotIn('QMenu', menu)
        self.assertNotIn('popup(', menu)
        self.assertIn('LibraryInterface::SourceEditList', menu)
        self.assertIn('"sidebar_sources_editing"', library)
        for size in ('kSourceRailWidth = 264', 'kSourceTileHeight = 64', 'kSourceBarHeight = 48',
                     'kSourceRowHeight = 56', 'kSourceBackWidth = 96', 'kSourceSwitchWidth = 64'):
            self.assertIn(size, interface)
        self.assertIn('const QMargins margins(LibraryInterface::kSourceRailWidth,', sidebar)
        self.assertIn('setViewportMargins(margins)', sidebar)
        self.assertIn('ConfigKey("[MixPi]", "screen")', sidebar)
        self.assertIn('ConfigKey("[Sidebar]", "sidebar_visible")', sidebar)
        # No drag-to-reorder in the new list.
        edit = interface[interface.index('class SourceEditList'):]
        self.assertNotIn('InternalMove', edit)

    def test_menu_style_has_the_sources_screen_rules(self):
        style = (RUNNER.PATCH_DIR / 'pioneered-menus.qss').read_text()
        for selector in ('#MixpiSourceRail', '#MixpiSourceTile', '#MixpiSourceBar', '#MixpiSourceBack',
                         '#MixpiSourceCrumb', '#MixpiSourceEdit', '#MixpiSourceEditSwitch::indicator',
                         '#MixpiSourceStartHere'):
            self.assertIn(selector, style)

    @unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
    def test_native_sources_screen_and_edit_list(self):
        result = subprocess.run(['python3', str(ROOT / 'tests/native/library_interface_sources_runner.py'),
                                 '--sources-screen'], capture_output=True, text=True, timeout=200)
        self.assertEqual(result.returncode, 0, result.stdout[-6000:] + result.stderr[-3000:])
        for check in SCREEN_CHECKS + EDIT_CHECKS:
            self.assertIn('PASS ' + check, result.stdout)
        self.assertNotIn('FAIL ', result.stdout)


if __name__ == '__main__':
    unittest.main()
