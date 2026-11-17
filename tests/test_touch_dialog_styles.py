"""F-9: the menu style block gives touch-sized menus and a dark Arrange dialog.

Rendering is checked natively in tests/native/library_interface_test.cpp,
which loads this same file. This checks the rules themselves and that the skin
patch installs them.
"""
import importlib.util
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
QSS = ROOT / 'stage3/01-install-packages/files/pioneered-menus.qss'
SPEC = importlib.util.spec_from_file_location(
    'pioneered_touch_styles', ROOT / 'stage3/01-install-packages/files/pioneered-touch.py')
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)


def rules(text):
    """Selector -> merged properties, in file order (later rules win)."""
    result = {}
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    for selectors, body in re.findall(r'([^{}]+)\{([^}]*)\}', text):
        properties = dict((name.strip(), value.strip()) for name, value in
                          (item.split(':', 1) for item in body.split(';') if ':' in item))
        for selector in selectors.split(','):
            result.setdefault(' '.join(selector.split()), {}).update(properties)
    return result


def pixels(value):
    return [int(number) for number in re.findall(r'(\d+)px', value)]


def dark(colour):
    red, green, blue = (int(colour[index:index + 2], 16) for index in (1, 3, 5))
    return 0.299 * red + 0.587 * green + 0.114 * blue < 64


class TouchDialogStyleTests(unittest.TestCase):
    def setUp(self):
        self.rules = rules(QSS.read_text())

    def rule(self, selector):
        self.assertIn(selector, self.rules)
        return self.rules[selector]

    def test_arrange_dialog_is_dark_with_17px_text(self):
        for selector in ('#MixpiColumnArrangement', '#MixpiColumnArrangement QListWidget',
                         '#MixpiColumnArrangement QPushButton'):
            rule = self.rule(selector)
            self.assertEqual(rule['font-size'], '17px', selector)
            self.assertEqual(rule['color'], '#e4e7ec', selector)  # --mx-text
        for selector in ('#MixpiColumnArrangement', '#MixpiColumnArrangement QListWidget'):
            self.assertTrue(dark(self.rule(selector)['background-color']), selector)

    def test_arrange_rows_buttons_and_check_boxes_are_touch_sized(self):
        self.assertGreaterEqual(pixels(self.rule('#MixpiColumnArrangement QListWidget::item')['min-height'])[0], 48)
        self.assertGreaterEqual(pixels(self.rule('#MixpiColumnArrangement QPushButton')['min-height'])[0], 48)
        indicator = self.rule('#MixpiColumnArrangement QListWidget::indicator')
        self.assertEqual((indicator['width'], indicator['height']), ('28px', '28px'))

    def test_menu_rows_are_at_least_48px(self):
        item = self.rule('QMenu::item')
        top, _, bottom, _ = pixels(item['padding'])
        self.assertGreaterEqual(pixels(item['min-height'])[0] + top + bottom, 48)
        checkbox = self.rule('QMenu QCheckBox')
        self.assertGreaterEqual(pixels(checkbox['min-height'])[0] + 2 * pixels(checkbox['padding'])[0], 48)

    def test_menu_and_dialog_rows_follow_the_agreed_rules(self):
        # Spec section 1: a tapped row is surface-3; a ticked row is the tick
        # and surface-2 with no left edge; the tick is ink on the accent.
        self.assertEqual(self.rule('QMenu::item:pressed')['background-color'], '#262c35')
        checked = self.rule('QMenu QCheckBox:checked')
        self.assertEqual(checked['background-color'], '#1d222a')
        self.assertNotIn('border-left', checked)
        tick = self.rule('QMenu QCheckBox::indicator:checked')
        self.assertEqual(tick['background-color'], '#a3c45e')
        self.assertEqual(tick['image'], 'url(skin:/mixpi-icon-tick.svg)')
        current = self.rule('#MixpiColumnArrangement QListWidget::item:selected')
        self.assertEqual(current['background-color'], '#1d222a')
        self.assertNotIn('border-left', current)
        button = self.rule('#MixpiColumnArrangement QPushButton')
        self.assertEqual((button['background-color'], button['border'], button['border-radius']),
                         ('#1d222a', '1px solid #3a424e', '3px'))
        for selector in ('QMenu', '#MixpiColumnArrangement', '#MixpiColumnArrangement QListWidget'):
            self.assertEqual(self.rule(selector)['background-color'], '#161a20', selector)

    def test_dialog_rules_leave_the_scroll_bar_to_the_library_style(self):
        for selector in self.rules:
            if selector.startswith('#MixpiColumnArrangement'):
                self.assertNotRegex(selector, r'\bQ(Widget|ScrollBar|AbstractScrollArea)\b')

    def test_sources_screen_rules_are_dark_with_readable_text(self):
        # R-9, R-10: the rail, the bar and Sources edit. Sizes are set in the
        # patch; the style gives colours and text of 13 px or more.
        sources = {selector: rule for selector, rule in self.rules.items()
                   if selector.startswith('#MixpiSource')}
        for selector in ('#MixpiSourceRail', '#MixpiSourceBar', '#MixpiSourceEdit',
                         '#MixpiSourceEdit #MixpiSourceEditRow',
                         '#MixpiSourceRail QPushButton#MixpiSourceTile'):
            self.assertTrue(dark(self.rule(selector)['background-color']), selector)
        sized = [selector for selector, rule in sources.items() if 'font-size' in rule]
        self.assertGreaterEqual(len(sized), 8)
        for selector in sized:
            self.assertGreaterEqual(pixels(sources[selector]['font-size'])[0], 13, selector)
        switch = self.rule('#MixpiSourceEditSwitch::indicator')
        self.assertEqual((switch['width'], switch['height']), ('56px', '32px'))
        self.assertIn('#MixpiSourceEditSwitch::indicator:checked', self.rules)

    def test_skin_patch_installs_the_style_block(self):
        styled = PATCH.patch_styles('#LibraryWrapper QTableView { color: #fff; }\n')
        block = styled[styled.index(PATCH.STYLE_BEGIN):styled.index(PATCH.STYLE_END)]
        self.assertIn('#MixpiColumnArrangement QListWidget::item', block)
        self.assertIn('QMenu::item { min-height: 32px;', block)
        self.assertEqual(styled, PATCH.patch_styles(styled), 'the managed block is replaced, not repeated')


if __name__ == '__main__':
    unittest.main()
