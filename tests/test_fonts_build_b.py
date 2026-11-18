"""Every MixPi style sheet uses build B's fonts (owner, 2026-11-18: "All fonts
back to build B"; AGREED-UI-SPEC sections 1 and 2a).

Build B is commit ef0874d. Its fonts came from its style sheets
(mixpi-performance.qss, pioneered-touch.qss, pioneered-menus.qss) over the
pinned Pioneered skin's own rules: `*` gives every widget Open Sans, and
`#LibraryWrapper WLibrarySidebar`, `#SearchBox` and the table header are bold.
Where build B set no family, the rules here name "Open Sans". An element new in
build C takes the build B font of the element with the same role.
"""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
FILES = ROOT / 'stage3/01-install-packages/files'
BUILD_B_MEDIA = ROOT / 'tests/fixtures/media-screen-build-b.qss'
UC, OS, U, MONO = 'Ubuntu Condensed', 'Open Sans', 'Ubuntu', 'Ubuntu Mono'
BOLD, NORMAL = 'bold', 'normal'


def rules(path):
    """(selectors, declarations) of each rule, in file order."""
    text = re.sub(r'/\*.*?\*/', '', Path(path).read_text(), flags=re.S)
    found = []
    for selector, body in re.findall(r'([^{}]+)\{([^{}]*)\}', text):
        declarations = {}
        for item in body.split(';'):
            if ':' in item:
                name, value = item.split(':', 1)
                declarations[name.strip()] = value.strip()
        found.append(([s.strip() for s in selector.split(',')], declarations))
    return found


def specificity(selector):
    """CSS specificity as Qt counts it: ids, then classes/attributes/pseudo
    states, then type names."""
    ids = selector.count('#')
    attributes = selector.count('[') + len(re.findall(r'(?<!:):(?!:)', selector))
    types = len(re.findall(r'(?:^|[\s>])([A-Za-z][A-Za-z0-9]*)', selector))
    return ids, attributes, types


def font(path, *selectors, weight=NORMAL):
    """(family, px, weight) for a widget the SELECTORS match: the more specific
    rule wins, then the later one (as Qt cascades). WEIGHT is the weight
    Pioneered's own rules give it where none is set here."""
    matched = []
    for order, (names, declarations) in enumerate(rules(path)):
        for name in set(names) & set(selectors):
            matched.append((specificity(name), order, declarations))
    merged = {}
    for _, _, declarations in sorted(matched, key=lambda m: m[:2]):
        merged.update(declarations)
    family = merged.get('font-family', '"Open Sans"').split(',')[0].strip().strip('"\'')
    size = merged.get('font-size')
    return family, int(size[:-2]) if size else None, merged.get('font-weight', weight)


class FontsAreBuildB(unittest.TestCase):
    def check(self, name, table):
        for selectors, expected in table:
            selectors = (selectors,) if isinstance(selectors, str) else selectors
            options = {}
            if isinstance(expected[-1], dict):
                *expected, options = expected
            with self.subTest(file=name, selector=selectors[-1]):
                self.assertEqual(font(FILES / name, *selectors, **options), tuple(expected))

    def test_performance_skin(self):
        button = ('#MixpiButton',)
        self.check('mixpi-performance.qss', [
            # Buttons: build B's button rule (Ubuntu Condensed 16 px bold). The
            # agreed roles (segments, ½ ×2, Sound, Danger, Caution) are buttons.
            *[(name, (UC, 16, BOLD)) for name in (
                '#MixpiButton', '#MixpiRecord', '#MixpiDesktopBar', '#MixpiDeck1', '#MixpiDeck2',
                '#MixpiCue', '#MixpiLoad1', '#MixpiLoad2', '#MixpiSegFirst', '#MixpiSegMid',
                '#MixpiSegLast', '#MixpiSize', '#MixpiSound', '#MixpiDanger', '#MixpiCaution',
                '#MixpiCueTile1', '#MixpiCueTile2', '#MixpiCueClearTile', '#MixpiClearConfirm')],
            ('#MixpiPlay', (UC, 20, BOLD)),
            ('#MixpiPrimary', (UC, 18, BOLD)),
            # The tool panel's buttons: build B's 19 px.
            *[(button + (f'#MixpiLoopPanel {name}',), (UC, 19, BOLD)) for name in (
                '#MixpiButton', '#MixpiSize', '#MixpiDanger', '#MixpiSound')],
            ('#MixpiTab', (UC, 18, BOLD)),
            ('#MixpiUsbName', (UC, 15, BOLD)),
            ('#MixpiUsbState1', (UC, 13, BOLD)),
            ('#MixpiUsbScan', (UC, 13, BOLD)),
            ('#MixpiLoadTitle', (OS, 13, NORMAL)),
            ('#MixpiChip', (U, 13, BOLD)),
            ('#MixpiChipSync1', (U, 13, BOLD)),
            ('#MixpiStateChip', (U, 13, BOLD)),
            ('#MixpiRange', (OS, 13, BOLD)),
            ('#MixpiCaption', (U, 13, BOLD)),
            ('#MixpiWaveBadge1', (UC, 20, BOLD)),
            ('#MixpiToolTitle', (UC, 18, BOLD)),
            ('#MixpiFxPad', (OS, 13, NORMAL)),
            # The rail rows: build B's rail buttons; the current row too.
            ('#MixpiRailLabel', (UC, 18, BOLD)),
            (('#MixpiRailLabel', '#MixpiRailLabel[highlight="1"]'), (UC, 18, BOLD)),
            ('#MixpiSettingTitle', (OS, 16, BOLD)),
            ('#MixpiSettingLabel', (OS, 13, NORMAL)),
            ('#MixpiSettingNote', (OS, 13, NORMAL)),        # a hint: the setting label
            ('#MixpiToggleWord', (OS, 14, BOLD)),           # build B's EJECT ON/OFF
            ('#MixpiSettingValue', (MONO, 17, BOLD)),       # a readout: the CPU %
            ('#MixpiSettingSelector', (OS, 17, NORMAL)),
            ('#MixpiCpuLabel', (OS, 13, NORMAL)),
            ('#MixpiCpu', (MONO, 17, BOLD)),
            ('#MixpiScreenTitle', (UC, 22, BOLD)),
            ('#MixpiScreenHint', (U, 14, NORMAL)),
            ('#MixpiSavedNote', (OS, 14, NORMAL)),
            ('#MixpiSheetTitle', (UC, 23, BOLD)),
            ('#MixpiChooseName', (OS, 14, NORMAL)),
            ('#MixpiChooseEmpty', (OS, 14, NORMAL)),
            ('#MixpiPadBadgeA', (U, 15, BOLD)),
            ('#MixpiPadTag', (OS, 13, BOLD)),
            ('#MixpiPadTime', (MONO, 13, NORMAL)),
            ('#MixpiPadName', (OS, 15, BOLD)),
            ('#MixpiPadEmptyText', (OS, 15, NORMAL)),
            ('#MixpiClearName', (OS, 15, BOLD)),            # the sample title: a pad's name
            ('#MixpiClearTime', (MONO, 13, NORMAL)),        # its length: a pad's time
            ('#MixpiClearNote', (U, 14, NORMAL)),           # a hint
            ('#MixpiLabel', (OS, 17, NORMAL)),
            ('#MixpiWaveKey', (OS, 17, NORMAL)),
            ('#MixpiDeckTitle', (OS, 16, NORMAL)),
            ('#MixpiDeckArtist', (OS, 14, NORMAL)),
            ('#MixpiDeckNumber1', (OS, 16, BOLD)),
            ('#MixpiTime', (OS, 21, NORMAL)),
            ('#MixpiRate', (OS, 21, NORMAL)),
            ('#MixpiKey', (OS, 17, NORMAL)),
            ('#MixpiBpm', (OS, 25, BOLD)),
            ('#MixpiEffectSelector', (OS, 18, NORMAL)),
            (('#MixpiEffectSelector', '#MixpiEffectSelector QAbstractItemView::item:selected'),
             (OS, 18, NORMAL)),
        ])

    def test_pioneered_touch_and_menus(self):
        self.check('pioneered-touch.qss', [
            ('#LibraryActionsButton', (UC, 17, BOLD)),
            ('#LibrarySourcesButton', (UC, 17, BOLD)),
            ('#LibraryWrapper #SearchBox', (OS, 17, BOLD)),
            ('#LibraryWrapper QTableView', (OS, 17, NORMAL)),
            ('#LibraryWrapper WTrackTableViewHeader::section', (OS, 16, BOLD, {'weight': BOLD})),
        ])
        self.check('pioneered-menus.qss', [
            ('QMenu', (OS, 17, NORMAL)),
            ('QMenu QCheckBox', (OS, 17, NORMAL)),
            ('#MixpiColumnArrangement QListWidget', (OS, 17, NORMAL)),
            ('#MixpiColumnArrangement QPushButton', (OS, 17, NORMAL)),
        ])

    def test_sources_menu_and_edit(self):
        back = '#MixpiSourcesMenuHeader QPushButton#MixpiSourcesMenuBack'
        edit = '#MixpiSourcesMenuHeader QPushButton#MixpiSourcesMenuEdit'
        row_button = '#MixpiSourcesEditRow QPushButton#MixpiSourcesEditUp'
        star = '#MixpiSourcesEditRow QPushButton#MixpiSourcesEditStar'
        sub = '#MixpiSourcesEditRow QLabel#MixpiSourcesEditSub'
        self.check('mixpi-sources-menu.qss', [
            # The source list: build B's list (17 px, bold from Pioneered).
            ('WLibrarySidebar[mixpiSourceMenu="true"]', (OS, 17, BOLD)),
            (back, (OS, 16, BOLD)),                                  # build B's BACK
            ((back, edit), (UC, 17, BOLD)),                          # build B's EDIT LIST
            ('#MixpiSourcesMenuHeader QLabel#MixpiSourcesMenuPlace', (OS, 15, NORMAL)),  # the crumb
            ('#MixpiSourcesMenuTile QLabel#MixpiSourcesMenuName', (OS, 17, BOLD)),
            ('#MixpiSourcesMenuTile QLabel#MixpiSourcesMenuSub', (OS, 13, NORMAL)),
            ('#MixpiSourcesEditHeader QLabel#MixpiSourcesEditTitle', (UC, 22, BOLD)),  # a screen title
            ('#MixpiSourcesEditHeader QLabel#MixpiSourcesEditHint', (OS, 13, BOLD)),
            ('#MixpiSourcesEditHeader QPushButton#MixpiSourcesEditDone', (UC, 17, BOLD)),  # B's DONE
            ('#MixpiSourcesEditRow QLabel#MixpiSourcesEditName', (OS, 17, BOLD)),
            (sub, (OS, 13, NORMAL)),
            ((sub, sub + '[start="true"]'), (OS, 13, NORMAL)),
            (row_button, (OS, 15, BOLD)),
            ((row_button, star), (OS, 16, BOLD)),                    # build B's "Start here"
            ('#MixpiSourcesEditRow QCheckBox#MixpiSourcesEditSwitch', (OS, 14, BOLD)),  # ON/OFF word
        ])
        # The counts in a source's rows were part of build B's 17 px row text.
        style = (FILES / 'mixpi-sources-menu.qss').read_text()
        self.assertIn('qproperty-menuNotePixelSize: 17;', style)

    def test_media_page(self):
        label = '#MixpiPage QLabel'
        button = '#MixpiPage QPushButton'
        strip = '#MixpiBottomStrip QLabel'
        self.check('mixpi-media-page.qss', [
            ('#MixpiPage', (OS, 16, NORMAL)),
            ((label, '#MixpiPage QLabel#MixpiPageTitle'), (OS, 21, BOLD)),
            ((label, '#MixpiPage QLabel#MixpiPageHint'), (OS, 14, NORMAL)),
            (label, (OS, 15, NORMAL)),
            ((label, '#MixpiPage QLabel#MixpiMediaName'), (OS, 24, BOLD)),
            ((label, '#MixpiPage QLabel#MixpiMediaSize'), (OS, 14, NORMAL)),
            ((label, '#MixpiPage QLabel#MixpiMediaUse'), (OS, 14, NORMAL)),
            ((label, '#MixpiPage QLabel#MixpiMediaProblem'), (OS, 14, NORMAL)),
            ((label, '#MixpiPage QLabel#MixpiMediaChip'), (OS, 13, BOLD)),    # build B's pill
            (button, (OS, 17, BOLD)),
            ((button, '#MixpiPage QPushButton#MixpiMediaFilterOption'), (OS, 17, BOLD)),
            ((label, '#MixpiPage QLabel#MixpiMediaFooterCount'), (OS, 14, BOLD)),
            ((label, '#MixpiPage QLabel#MixpiMediaFooterText'), (OS, 14, NORMAL)),
            ((label, '#MixpiPage QLabel#MixpiEjectTitle'), (OS, 24, BOLD)),
            ((label, '#MixpiPage QLabel#MixpiEjectHint'), (OS, 14, NORMAL)),
            ((label, '#MixpiPage QLabel#MixpiEjectUser'), (OS, 16, NORMAL)),
            ((label, '#MixpiPage QLabel#MixpiEjectFate'), (OS, 15, NORMAL)),
            ((label, '#MixpiPage QLabel#MixpiEjectStep'), (OS, 15, NORMAL)),
            ((label, '#MixpiPage QLabel#MixpiEjectDot'), (OS, 13, NORMAL)),
            ((strip, '#MixpiBottomStrip QLabel#MixpiStripTitle'), (OS, 18, BOLD)),
            ((strip, '#MixpiBottomStrip QLabel#MixpiStripDetail'), (OS, 13, NORMAL)),
            ('#MixpiBottomStrip QPushButton', (OS, 17, BOLD)),
        ])

    def test_media_page_matches_build_b_media_rules(self):
        # The elements build B's Media page had: the same size and weight as
        # build B's own rules (kept as a test fixture), in Open Sans.
        pairs = [
            (('#MixpiPage',), ('#MixpiPage',)),
            (('#MixpiPage QLabel', '#MixpiPage QLabel#MixpiPageTitle'), ('#MixpiPage QLabel#MixpiPageTitle',)),
            (('#MixpiPage QLabel', '#MixpiPage QLabel#MixpiPageHint'), ('#MixpiPage QLabel#MixpiPageHint',)),
            (('#MixpiPage QLabel',), ('#MixpiPage QLabel',)),
            (('#MixpiPage QLabel', '#MixpiPage QLabel#MixpiMediaName'),
             ('#MixpiPage QLabel', '#MixpiPage QLabel#MixpiMediaName')),
            (('#MixpiPage QLabel', '#MixpiPage QLabel#MixpiMediaUse'),
             ('#MixpiPage QLabel', '#MixpiPage QLabel#MixpiMediaUse')),
            (('#MixpiPage QPushButton',), ('#MixpiPage QPushButton',)),
            (('#MixpiPage QLabel', '#MixpiPage QLabel#MixpiEjectTitle'),
             ('#MixpiPage QLabel', '#MixpiPage QLabel#MixpiEjectTitle')),
            *[(('#MixpiPage QLabel', f'#MixpiPage QLabel#{name}'), ('#MixpiPage QLabel', f'#MixpiPage QLabel#{name}'))
              for name in ('MixpiEjectHint', 'MixpiEjectUser', 'MixpiEjectFate', 'MixpiEjectStep',
                           'MixpiEjectDot')],
            (('#MixpiBottomStrip QLabel', '#MixpiBottomStrip QLabel#MixpiStripTitle'),
             ('#MixpiBottomStrip QLabel', '#MixpiBottomStrip QLabel#MixpiStripTitle')),
            (('#MixpiBottomStrip QLabel', '#MixpiBottomStrip QLabel#MixpiStripDetail'),
             ('#MixpiBottomStrip QLabel', '#MixpiBottomStrip QLabel#MixpiStripDetail')),
            (('#MixpiBottomStrip QPushButton',), ('#MixpiBottomStrip QPushButton',)),
        ]
        for now, build_b in pairs:
            with self.subTest(selector=now[-1]):
                self.assertEqual(font(FILES / 'mixpi-media-page.qss', *now),
                                 font(BUILD_B_MEDIA, *build_b))

    def test_no_font_build_b_never_used(self):
        # Build B used no semibold (600) and Ubuntu Mono only for numbers.
        mono = {'#MixpiCpu', '#MixpiPadTime', '#MixpiClearTime', '#MixpiSettingValue'}
        for name in ('mixpi-performance.qss', 'pioneered-touch.qss', 'pioneered-menus.qss',
                     'mixpi-sources-menu.qss', 'mixpi-media-page.qss'):
            for selectors, declarations in rules(FILES / name):
                with self.subTest(file=name, selector=selectors[0]):
                    self.assertNotIn(declarations.get('font-weight'), ('600', 'demibold'))
                    if 'Ubuntu Mono' in declarations.get('font-family', ''):
                        self.assertLessEqual(set(selectors), mono)
                    if 'font-size' in declarations:
                        self.assertGreaterEqual(int(declarations['font-size'][:-2]), 13)


if __name__ == '__main__':
    unittest.main()
