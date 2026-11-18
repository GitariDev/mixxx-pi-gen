"""Build C, wave C1: the agreed Media page (U-10, spec s13) and the insert
choice [MixPi],drive_insert (U-8, spec s11), mixxx-media-agreed.patch and
mixpi-media-page.qss."""
import os
from pathlib import Path
import re
import tempfile
import unittest

from native.library_interface_runner import qt_available
from native import media_screen_runner as runner

ROOT = Path(__file__).resolve().parents[1]
PATCH = runner.PATCH_DIR / runner.AGREED
QSS = runner.PATCH_DIR / 'mixpi-media-page.qss'
DESIGN = ROOT / 'docs/ideas/ui-redesign-20261117/agreed-ui/design'


def section(path):
    text = PATCH.read_text()
    return text.split('+++ b/' + path + '\n', 1)[1].split('\ndiff --git ', 1)[0]


def added(path):
    return '\n'.join(line[1:] for line in section(path).splitlines() if line[:1] in ('+', ' '))


def changed(path, sign):
    return [line[1:] for line in section(path).splitlines() if line[:1] == sign and line[:3] != sign * 3]


class MediaAgreedPatchTests(unittest.TestCase):
    def test_patch_touches_only_n_b_files(self):
        files = re.findall(r'^diff --git a/(\S+) ', PATCH.read_text(), re.MULTILINE)
        self.assertEqual(sorted(files), ['src/library/mixpidriveinsert.h', 'src/library/mixpimedia.h',
                                         'src/library/mixpimediapage.h', 'src/widget/mixpipage.h'])

    def test_copy_to_pi_and_the_pi_memory_column_are_gone(self):
        page = added('src/library/mixpimediapage.h')
        media = added('src/library/mixpimedia.h')
        for text in (page, media):
            for gone in ('COPY TO PI', 'copyRequested', 'MixpiMediaCopy', '/usr/local/bin/mixpi-media',
                         'PLAYING FROM PI MEMORY', 'CLEANED OUT', 'MixpiMediaHandover'):
                self.assertNotIn(gone, text)
        self.assertIn('QStringLiteral("playing from Pi memory")', page)

    def test_eject_and_controlled_media_are_untouched(self):
        # R-5, R-6: the gate, engine A and the controlled profile keep their code.
        for path in ('src/library/mixpimedia.h', 'src/library/mixpimediapage.h'):
            for line in changed(path, '+') + changed(path, '-'):
                for word in ('mixpiEjectGateOpen', 'media-eject', 'showControlled', 'MixpiControlled',
                             'udisksctl', 'beginDrain', 'retire', 'MixpiEjectEngine', 'power-off'):
                    self.assertNotIn(word, line, path)

    def test_nothing_new_writes_to_a_drive(self):
        lines = []
        for path in ('src/library/mixpimedia.h', 'src/library/mixpimediapage.h', 'src/widget/mixpipage.h',
                     'src/library/mixpidriveinsert.h'):
            lines += changed(path, '+')
        for line in lines:
            for word in ('WriteOnly', 'ReadWrite', 'QFile::copy', 'QFile::rename', 'remove(', 'QProcess',
                         'startDetached', 'mkpath'):
                self.assertNotIn(word, line)

    def test_drive_insert_is_a_persist_control_used_where_the_ping_was(self):
        control = added('src/library/mixpidriveinsert.h')
        self.assertIn('ConfigKey(QStringLiteral("[MixPi]"), QStringLiteral("drive_insert"))', control)
        self.assertIn('new ControlObject(mixpiDriveInsertKey(), true, false, true, 0.0)', control)
        media = added('src/library/mixpimedia.h')
        self.assertIn('m_driveInsert(mixpiNewDriveInsertControl())', media)
        # The block that ran when shouldPing(...) && ensureWidgets() held.
        ping = media.split('ensureWidgets()) {\n', 1)[1].split('\n                }\n', 1)[0]
        self.assertIn('mixpiDriveInserted(m_strip.data(), m_driveInsert->get(), identity, model.name,', ping)
        self.assertNotIn('m_strip->showPing', ping)
        self.assertIn('m_strip->showPing(identity, model.name,', ''.join(changed('src/library/mixpimedia.h', '-')))
        # AUTO LOAD goes through the ping's LOAD path (loadFromPing -> openVolume).
        self.assertIn('loadFromPing(m_autoLoads.takeFirst())', media)

    def test_close_is_at_the_right_end_of_the_header(self):
        page = added('src/widget/mixpipage.h')
        header = page.split('auto* row = new QHBoxLayout(header);', 1)[1].split('layout->addWidget(header);', 1)[0]
        self.assertLess(header.index('row->addWidget(m_title)'), header.index('row->addLayout(m_headerRow)'))
        self.assertLess(header.index('row->addLayout(m_headerRow)'), header.index('row->addStretch(1)'))
        self.assertLess(header.index('row->addStretch(1)'), header.index('row->addWidget(m_close)'))
        self.assertIn('static constexpr int kHeaderHeight = 52;', page)


def rules(text):
    """(selector, body) for each rule, comments removed."""
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    return [(selector.strip(), body) for selector, body in re.findall(r'([^{}]+)\{([^}]*)\}', text)]


class MediaAgreedStyleTests(unittest.TestCase):
    def test_colours_come_from_the_tokens(self):
        # tokens.css, and layout.css for the scroll thumb (#5b6472).
        tokens = {value.lower() for name in ('tokens.css', 'layout.css')
                  for value in re.findall(r'#[0-9a-fA-F]{6}', (DESIGN / name).read_text())}
        for colour in re.findall(r'#[0-9a-fA-F]{6}\b', re.sub(r'/\*.*?\*/', '', QSS.read_text(), flags=re.DOTALL)):
            self.assertIn(colour.lower(), tokens, colour)
        # The see-through lit tint (26% of the accent) and the scrim.
        self.assertIn('rgba(163, 196, 94, 66)', QSS.read_text())

    def test_radius_text_and_touch_rules(self):
        for selector, body in rules(QSS.read_text()):
            for size in re.findall(r'font-size:\s*(\d+)px', body):
                self.assertGreaterEqual(int(size), 13, selector)
            for radius in re.findall(r'border-radius:\s*(\d+)px', body):
                if 'Chip' in selector:
                    self.assertEqual(radius, '11', selector)  # a pill on a 22 px chip
                elif 'QScrollBar' in selector or 'EjectDot' in selector:
                    continue
                else:
                    self.assertIn(radius, ('0', '3'), selector)
            # min-height is the content box: with the borders it is 48 px (the
            # native fixture measures every button).
            border = max([int(width) for width in re.findall(r'border:\s*(\d+)px', body)] or [0])
            for height in re.findall(r'min-height:\s*(\d+)px', body):
                if 'QPushButton' in selector and 'Close' not in selector:
                    self.assertGreaterEqual(int(height) + 2 * border, 48, selector)

    def test_close_has_no_outline_at_rest_and_a_red_cross(self):
        bodies = dict(rules(QSS.read_text()))
        rest = bodies['#MixpiPage QPushButton#MixpiPageClose']
        self.assertIn('border: 1px solid transparent;', rest)
        self.assertIn('background-color: #1d222a;', rest)
        self.assertIn('color: #ec7f74;', rest)
        pressed = bodies['#MixpiPage QPushButton#MixpiPageClose:pressed']
        self.assertIn('background-color: #34191b;', pressed)
        self.assertIn('border-color: #d0574d;', pressed)

    def test_eject_is_caution_never_green(self):
        bodies = dict(rules(QSS.read_text()))
        caution = bodies['#MixpiPage QPushButton[role="caution"], #MixpiBottomStrip QPushButton[role="caution"]']
        self.assertIn('background-color: #30260e;', caution)
        self.assertIn('border: 1px solid #dfa33a;', caution)
        self.assertIn('color: #e8b65c;', caution)

    def test_every_old_media_selector_in_use_is_restyled(self):
        """Nothing from pioneered-menus.qss's old Media section leaks through:
        every old rule for a widget the page still has is matched here, with
        each of its properties set again."""
        old = rules((runner.PATCH_DIR / 'pioneered-menus.qss').read_text())
        new = rules(QSS.read_text())
        page = added('src/library/mixpimediapage.h') + added('src/widget/mixpipage.h')
        for selector, body in old:
            names = re.findall(r'#(Mixpi\w+)', selector)
            if not names or 'Mixpi' not in selector:
                continue
            last = names[-1]
            if last not in ('MixpiPage', 'MixpiBottomStrip') and f'"{last}"' not in page:
                continue  # a widget the agreed page no longer has
            if any(gone in selector for gone in ('[primary="true"]', 'MixpiMediaPill', '[block="true"]')):
                continue  # no widget carries these any more
            properties = {name.strip() for name in re.findall(r'([\w-]+)\s*:', body)}
            for part in selector.split(','):
                part = ' '.join(part.split())
                covering = [new_body for new_selector, new_body in new
                            if part in [' '.join(item.split()) for item in new_selector.split(',')]]
                self.assertTrue(covering, part)
                set_again = {name.strip() for new_body in covering for name in re.findall(r'([\w-]+)\s*:', new_body)}
                for name in properties:
                    if name == 'border-left' and 'border' in set_again:
                        continue
                    self.assertTrue(name in set_again or (name.startswith('border') and 'border' in set_again),
                                    f'{part}: {name}')


@unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
class MediaAgreedNativeTests(unittest.TestCase):
    def test_agreed_media_page_and_insert_choice(self):
        with tempfile.TemporaryDirectory(prefix='mixpi-media-agreed-') as temporary:
            target = Path(temporary)
            binary = runner.build_agreed(target)
            renders = os.environ.get('MIXPI_MEDIA_RENDERS', '')
            fonts = ':'.join(str(target / name) for name in runner.FONTS)
            result = runner.run(binary, *([renders] if renders else []), qss=runner.AGREED_QSS,
                                environment_extra={'MIXPI_FONTS': fonts})
            print(result.stdout, result.stderr, flush=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(' 0 failures', result.stdout)
            for name in ('header: order is title, ALL, READY, IN USE, close',
                         'close: surface-2 to its edge, no outline at rest',
                         'filters: ALL is the default',
                         'filters: READY shows the ready drives',
                         'filters: IN USE shows the drive in use',
                         'rows: each drive has a USB icon, size, chip, OPEN and EJECT',
                         'rows: OPEN is Navigate and EJECT is Caution',
                         'removed: no COPY TO PI',
                         'removed: no deck or song lines, no paragraph, no Pi memory column',
                         'footer: 2 tracks playing from Pi memory, at the bottom',
                         'footer: hidden while no track plays from Pi memory',
                         'scroll: three drives show a 24 px bar at the right edge',
                         'scroll: a drag brings the third row\'s EJECT into view',
                         'open: after it, the button reads BROWSE',
                         'insert: ASK shows the ping with LOAD and DISMISS',
                         'insert: AUTO LOAD loads the drive at once with no ping',
                         'no drive: the short line No USB drive, without the paragraph'):
                self.assertIn('PASS ' + name, result.stdout)

    def test_open_and_browse_switch_to_tracks(self):
        # Build D (spec s13, acceptance C R-4): OPEN and BROWSE read the
        # drive, then Tracks shows, from any tab; the close X still goes back.
        with tempfile.TemporaryDirectory(prefix='mixpi-media-open-tracks-') as temporary:
            binary = runner.build_open_tracks(Path(temporary))
            result = runner.run(binary)
            print(result.stdout, result.stderr[-3000:], flush=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr[-3000:])
            self.assertIn('FAILURES 0', result.stdout)
            for name in ('the Media page covers the pages (screen 2)',
                         'OPEN from DECKS: the page closes and Tracks shows',
                         'OPEN: screen is 0 after the page closes',
                         'BROWSE from SAMPLER: the page closes and Tracks shows',
                         'OPEN from FX: Tracks shows',
                         'OPEN from TRACKS: Tracks stays',
                         'close: the red X goes back to DECKS, as before'):
                self.assertIn('PASS ' + name, result.stdout)

    def test_open_returns_to_the_old_tab_without_the_fix(self):
        # Build C's fault, reproduced with the same fixture.
        with tempfile.TemporaryDirectory(prefix='mixpi-media-open-baseline-') as temporary:
            binary = runner.build_open_tracks(Path(temporary), fix=False)
            result = runner.run(binary)
            print(result.stdout, result.stderr[-3000:], flush=True)
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn('FAIL OPEN from DECKS: the page closes and Tracks shows', result.stdout)
            self.assertIn('FAIL BROWSE from SAMPLER: the page closes and Tracks shows', result.stdout)
            self.assertIn('PASS close: the red X goes back to DECKS, as before', result.stdout)

    def test_drive_insert_saved_and_read_back(self):
        with tempfile.TemporaryDirectory(prefix='mixpi-media-insert-') as temporary:
            target = Path(temporary)
            binary = runner.build_insert(target / 'build')
            work = target / 'run'
            work.mkdir()
            outputs = []
            for mode in ('first', 'next', 'third'):
                result = runner.run(binary, str(work), mode)
                print(mode, result.stdout, result.stderr[-3000:], flush=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr[-3000:])
                outputs.append(result.stdout)
            self.assertIn('PASS first start: drive_insert starts at 0', outputs[0])
            self.assertIn('PASS AUTO LOAD is in mixxx.cfg within a second or so of the change', outputs[0])
            self.assertIn('PASS next start: drive_insert starts at 1', outputs[1])
            self.assertIn('PASS third start: drive_insert starts at 0', outputs[2])


if __name__ == '__main__':
    unittest.main()
