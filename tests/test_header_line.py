"""Spec 2h (owner's choice B, wave J14): the Tracks table header's 1 px line
runs the full width.

The header's empty area past the last section (seen after TITLE's edge is
dragged narrower) gets the sections' 1 px #2c333d bottom line, to the scroll
bar. The header keeps its height (34 px sections plus their line; wave H1's
concern) and the sections keep one line, not two.

Qt draws a header widget's stylesheet border in the widget's last pixel row,
the row the sections' own border-bottom is in, so neither grows. The offscreen
render on VM b (deploy/ui-redesign-20261117/wave-J14) shows this: header 35 px
before and after, and only the 59 pixels of row y 132 at x 716-774 change.
"""

import re
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
FILES = ROOT / "stage3/01-install-packages/files"
TOUCH = FILES / "pioneered-touch.qss"
LINE_RULE = "#LibraryWrapper QTableView > WTrackTableViewHeader"


def without_comments(text):
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def rules(text):
    """(selector, body) pairs, comments removed."""
    return [(selector.strip(), body.strip())
            for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", without_comments(text))]


def declarations(body):
    return [item.strip() for item in body.split(";") if item.strip()]


class HeaderLineTests(unittest.TestCase):
    def setUp(self):
        self.rules = rules(TOUCH.read_text())

    def rule(self, selector):
        bodies = [body for name, body in self.rules if name == selector]
        self.assertEqual(len(bodies), 1, selector)
        return declarations(bodies[0])

    def test_empty_part_of_header_has_the_sections_line(self):
        # Only the bottom line: a top, left or right border, padding or a
        # height would change the header's size or draw a second line.
        self.assertEqual(self.rule(LINE_RULE), ["border-bottom: 1px solid #2c333d"])

    def test_line_matches_the_sections_line(self):
        section = self.rule("#LibraryWrapper WTrackTableViewHeader::section")
        self.assertIn("border-bottom: 1px solid #2c333d", section)
        self.assertIn("min-height: 34px", section)
        self.assertIn("border: 0px", section)

    def test_h1_background_rule_is_unchanged(self):
        self.assertEqual(self.rule("#LibraryWrapper WTrackTableViewHeader"),
                         ["background-color: #1d222a"])

    def test_only_the_track_table_header_gets_the_line(self):
        for name in ("pioneered-touch.qss", "pioneered-menus.qss", "mixpi-sources-menu.qss",
                     "mixpi-media-page.qss", "mixpi-performance.qss"):
            for selector, body in rules((FILES / name).read_text()):
                for part in selector.split(","):
                    part = part.strip()
                    if "HeaderView" not in part or "::" in part:
                        continue
                    # No bare QHeaderView rule, and no later stylesheet
                    # changing the header widget's border.
                    self.assertNotRegex(part, r"(^|\s)QHeaderView\b", (name, part))
                    if part != LINE_RULE:
                        self.assertNotIn("border", body, (name, part))


if __name__ == "__main__":
    unittest.main()
