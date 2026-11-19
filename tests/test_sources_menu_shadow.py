"""Wave I3 (S8): the Sources side menu's shadow (agreed UI spec 2d).

The owner chose to build the shadow as m-sources-top.png and m-sources-sub.png
draw it: on the menu's left edge, over the Tracks table, painted as a plain
gradient (no Qt graphics effect). A skin widget there would take the taps of
the table and its scroll bar, so mixxx-sources-menu-shadow.patch lets the
overlay layout place a third child, the skin's 40 px MixpiSourcesMenuShadow,
against the menu's left edge and makes it transparent for touches. The skin
side is pinned in tests/test_performance_skin.py; the native fixture is
tests/native/sources_menu_shadow_runner.py.
"""
import importlib.util
from pathlib import Path
import unittest

from native.library_interface_runner import qt_available

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / 'stage3/01-install-packages/files/mixxx-sources-menu-shadow.patch'

NATIVE_CHECKS = (
    "the skin's shadow rule is a plain gradient",
    'the menu stays 320 px at x 480-800',
    "the strip is 40 px against the menu's left edge (x 440-480)",
    'the table keeps its width; its scroll bar stays at x 456-480',
    'x 420 is not shaded',
    'x 448 reads about #1c2129',
    'x 456 reads about #1b2028',
    'x 464 reads about #191e25',
    'x 472 reads about #161a21',
    'x 479 reads about #14181d',
    'the menu at x 481 is not shaded',
    'the strip is transparent for touches',
    'control: an opaque strip would take the tap',
    'a tap at the strip on a row hits the table',
    'a tap at the strip on a row selects that row',
    'a press at the strip on the scroll bar hits the scroll bar',
    'a drag on the scroll bar under the strip scrolls the table',
    "the menu's BACK still takes its tap",
    'closed: x 479 is not shaded',
)
# The overlay layout without the patch leaves a third child unplaced.
BASELINE_FAILS = (
    "the strip is 40 px against the menu's left edge (x 440-480)",
    'x 479 reads about #14181d',
    'the strip is transparent for touches',
)


def runner():
    spec = importlib.util.spec_from_file_location(
        'sources_menu_shadow_runner', ROOT / 'tests/native/sources_menu_shadow_runner.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SourcesMenuShadowPatchTests(unittest.TestCase):
    def setUp(self):
        self.patch = PATCH.read_text()

    def test_patch_touches_only_the_overlay_layout(self):
        touched = [line.split()[2][2:] for line in self.patch.splitlines()
                   if line.startswith('diff --git ')]
        self.assertEqual(touched, ['src/widget/wrightoverlaylayout.h'])

    def test_third_child_is_placed_left_of_the_menu_and_lets_touches_through(self):
        added = '\n'.join(line[1:] for line in self.patch.splitlines()
                          if line.startswith('+') and not line.startswith('+++'))
        self.assertIn('if (m_items.size() == 3 && item->widget()) {', added)
        self.assertIn('item->widget()->setAttribute(Qt::WA_TransparentForMouseEvents);', added)
        self.assertIn('const int shadowLeft = qMax(content.left(), left - m_shadowWidth);', added)
        self.assertIn('shadow->setGeometry(shadowLeft, content.top(), left - shadowLeft,', added)
        for word in ('QGraphics', 'DropShadow', 'GraphicsEffect'):
            self.assertNotIn(word, self.patch)


@unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
class NativeSourcesMenuShadowTests(unittest.TestCase):
    def test_strip_is_drawn_and_lets_taps_and_drags_through(self):
        result = runner().run()
        output = result.stdout + result.stderr
        print(result.stdout)
        self.assertEqual(result.returncode, 0, output[-6000:])
        self.assertIn('FAILURES 0', result.stdout)
        self.assertNotIn('FAIL ', result.stdout)
        for check in NATIVE_CHECKS:
            self.assertIn('PASS ' + check, result.stdout)

    def test_overlay_layout_without_the_patch_fails(self):
        result = runner().run(baseline=True)
        output = result.stdout + result.stderr
        print(result.stdout)
        self.assertNotEqual(result.returncode, 0, output[-6000:])
        for check in BASELINE_FAILS:
            self.assertIn('FAIL ' + check, result.stdout)


if __name__ == '__main__':
    unittest.main()
