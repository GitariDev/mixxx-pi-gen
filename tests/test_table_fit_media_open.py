"""Build D, wave D1 (N-D2): mixxx-table-fit-media-open.patch.

1. With Sources open the narrowed table fits its columns (spec 2a, s5;
   m-sources-top.png), and the full-width sizes stay the saved ones.
2. OPEN and BROWSE on the Media page switch to Tracks (spec s13; acceptance C
   R-4).

The native checks are in test_table_columns.py (the fit, with the real
WTrackTableViewHeader) and test_media_agreed.py (OPEN, with the real
WWidgetStack and control framework); these check the patch itself.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATCH_DIR = ROOT / 'stage3/01-install-packages/files'
PATCH = PATCH_DIR / 'mixxx-table-fit-media-open.patch'


def section(path):
    return PATCH.read_text().split('+++ b/' + path + '\n', 1)[1].split('\ndiff --git ', 1)[0]


def added(path):
    return '\n'.join(line[1:] for line in section(path).splitlines() if line[:1] in ('+', ' '))


def removed(path):
    return [line[1:] for line in section(path).splitlines() if line[:1] == '-' and line[:3] != '---']


class TableFitMediaOpenPatchTests(unittest.TestCase):
    def test_patch_touches_only_n_d2_files(self):
        files = re.findall(r'^diff --git a/(\S+) ', PATCH.read_text(), re.MULTILINE)
        self.assertEqual(sorted(files), ['src/library/mixpimedia.h', 'src/library/mixpiopentracks.h',
                                         'src/widget/mixpitablefit.h', 'src/widget/wtracktableview.cpp',
                                         'src/widget/wtracktableview.h'])

    def test_open_closes_the_page_to_tracks(self):
        media = added('src/library/mixpimedia.h')
        self.assertIn('#include "library/mixpiopentracks.h"', media)
        block = media.split('guard->m_opened->insert(token);', 1)[1].split('guard->refresh();', 1)[0]
        self.assertIn('mixpiClosePageToTracks(guard->m_page.data());', block)
        # The ★ start drive still opens without showing Tracks.
        self.assertIn('if (start) {\n                    guard->m_page->closePage();', block)
        self.assertEqual(removed('src/library/mixpimedia.h'), ['                guard->m_page->closePage();'])
        helper = added('src/library/mixpiopentracks.h')
        body = helper.split('inline void mixpiClosePageToTracks(MixpiPage* page) {', 1)[1]
        # The page closes first (the stack shows again), then Tracks.
        self.assertLess(body.index('page->closePage();'),
                        body.index('ControlObject::set(ConfigKey(QStringLiteral("[Tab]"), '
                                   'QStringLiteral("library")), 1);'))

    def test_table_view_fits_and_saves_full_widths(self):
        view = added('src/widget/wtracktableview.cpp')
        resize = view.split('void WTrackTableView::resizeEvent(QResizeEvent* event) {', 1)[1].split('\n}\n', 1)[0]
        self.assertIn('resizeKeepingCurrentRow(event);', resize)
        self.assertIn('m_columnFit.fit();', resize)
        # loadTrackModel: the old header saves its full-width sizes; the new
        # one fits once the view shows again.
        self.assertIn('m_columnFit.withFullWidths(oldHeader, [oldHeader] { oldHeader->saveHeaderState(); });',
                      view)
        self.assertIn("    setVisible(true);\n\n    // Build D: the new list's columns fit the table if it is "
                      "narrowed.\n    m_columnFit.fit();", view)
        # ~WTrackTableView
        self.assertIn('    if (pHeader) {\n        // The full-width column sizes, never the fitted ones (build D).\n'
                      '        m_columnFit.withFullWidths(pHeader, [pHeader] { pHeader->saveHeaderState(); });',
                      view)
        # No header state is saved anywhere else with the fitted sizes.
        self.assertEqual(view.count('saveHeaderState()'), 2)
        # Arrange columns shows and saves the full-width sizes.
        arrange = view.split('m_columnFit.pause();', 1)[1].split('}, std::move(loadToPad));', 1)[0]
        self.assertIn('header->showColumnArrangement();', arrange)
        self.assertIn('m_columnFit.resume();', arrange)
        self.assertIn('static_assert(MixpiTableFit::kTitleMinimum == '
                      'LibraryInterface::kStretchColumnMinimumWidth);', view)

    def test_fit_rules_follow_the_mockup(self):
        fit = added('src/widget/mixpitablefit.h')
        # KEY in m-sources-top.png is 41 px wide (417-458); TITLE takes half.
        self.assertIn('static constexpr int kColumnMinimum = 40;', fit)
        self.assertIn('std::max(titleMinimum, available / 2)', fit)
        # Only a narrowed table is fitted; at the full width nothing changes.
        self.assertIn('const bool narrowed = available < m_widest;', fit)
        self.assertIn('if (!narrowed || full + titleMinimum <= available) {', fit)

    def test_fixture_view_mirrors_the_table_view(self):
        # table_columns_test.cpp's View calls the fit where WTrackTableView does.
        fixture = (ROOT / 'tests/native/table_columns_test.cpp').read_text()
        for line in ('QTableView::resizeEvent(event);\n#ifdef MIXPI_TABLE_FIT\n        m_columnFit.fit();',
                     'show();\n#ifdef MIXPI_TABLE_FIT\n        m_columnFit.fit();',
                     'm_columnFit.withFullWidths(pHeader, [pHeader] { pHeader->saveHeaderState(); });'):
            self.assertIn(line, fixture)


if __name__ == '__main__':
    unittest.main()
