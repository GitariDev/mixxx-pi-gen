"""Build I, wave I2 (spec 2d, plan 12.9): the USB chip reads IN USE only once a
track or sample from the drive is loaded on a deck or pad, and the plug-in
ping (ASK) also shows while the Media page is open. mixxx-media-chip-ping.patch."""
import os
from pathlib import Path
import re
import tempfile
import unittest

from native.library_interface_runner import qt_available
from native import media_screen_runner as runner

PATCH = runner.PATCH_DIR / runner.CHIP_PING


def section(path):
    return PATCH.read_text().split('+++ b/' + path + '\n', 1)[1].split('\ndiff --git ', 1)[0]


def changed(path, sign):
    return [line[1:] for line in section(path).splitlines() if line[:1] == sign and line[:3] != sign * 3]


def added(path):
    return '\n'.join(line[1:] for line in section(path).splitlines() if line[:1] in ('+', ' '))


class MediaChipPingPatchTests(unittest.TestCase):
    def test_patch_touches_only_the_media_headers(self):
        files = re.findall(r'^diff --git a/(\S+) ', PATCH.read_text(), re.MULTILINE)
        self.assertEqual(sorted(files), ['src/library/mixpimedia.h', 'src/library/mixpimediapage.h'])

    def test_in_use_comes_only_from_decks_and_pads(self):
        page = added('src/library/mixpimediapage.h')
        state = page.split('inline MixpiMediaState idleState(', 1)[1].split('\n}\n', 1)[0]
        self.assertNotIn('opened', state.split('{', 1)[1])
        self.assertNotIn('busy', state.split('{', 1)[1])
        self.assertIn('user.group.startsWith(QStringLiteral("[Channel")) || isPad(user.group)', state)

    def test_the_chip_follows_each_load_and_unload(self):
        media = added('src/library/mixpimedia.h')
        hook = media.split('&PlayerInfo::trackChanged, this,', 1)[1].split('});', 1)[0]
        self.assertIn('m_handover->trackChanged(group);', hook)
        self.assertIn('refresh();', hook)

    def test_the_ping_no_longer_waits_for_the_page_to_close(self):
        self.assertIn('m_page && m_page->isVisible()) &&', ''.join(changed('src/library/mixpimedia.h', '-')))
        self.assertNotIn('isVisible', ''.join(changed('src/library/mixpimedia.h', '+')))
        ping = added('src/library/mixpimediapage.h').split('inline bool shouldPing(', 1)[1].split('\n}\n', 1)[0]
        self.assertIn('return firstCheckDone && !wasPresent && !alreadyPinged && mounted && !opened;', ping)

    def test_eject_and_the_drive_are_untouched(self):
        for path in ('src/library/mixpimedia.h', 'src/library/mixpimediapage.h'):
            for line in changed(path, '+') + changed(path, '-'):
                for word in ('mixpiEjectGateOpen', 'MixpiEjectEngine', 'MixpiControlled', 'udisksctl', 'beginDrain',
                             'WriteOnly', 'ReadWrite', 'QProcess', 'remove(', 'm_opened'):
                    self.assertNotIn(word, line, path)


@unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
class MediaChipPingNativeTests(unittest.TestCase):
    NAMES = ('open: an opened drive with nothing loaded reads READY',
             'deck: a track from the drive on deck 1 reads IN USE',
             'deck: ejecting deck 1\'s track reads READY',
             'deck: a This Pi track loaded over it reads READY',
             'pad: a sample from the drive on pad 3 reads IN USE',
             'pad: clearing pad 3 reads READY',
             'browse: a track in the library\'s preview player only leaves it READY',
             'two drives: deck 2 from MANTACORE: MANTACORE IN USE, SPARE READY, the chip shows MANTACORE',
             'two drives: pad 1 from SPARE as well: both IN USE',
             'two drives: deck 2 ejected: MANTACORE READY, SPARE still IN USE',
             'page: the row of a drive with a deck loaded from it reads IN USE',
             'page: an opened drive with nothing loaded reads READY, and its button BROWSE',
             'ping: a new drive is pinged while the Media page is open',
             'ping: ASK shows LOAD and DISMISS over the Media page',
             'ping: in the same place as on other screens, the bottom 56 px',
             'ping: LOAD and DISMISS are on top of the page, where a tap lands',
             'ping: the page\'s own row for the new drive shows too, READY',
             'ping: LOAD over the page opens that drive, as on other screens',
             'ping: a ping already up stays on top when the Media page opens',
             'ping: DISMISS leaves the Media page as it was',
             'ping: AUTO LOAD with the Media page open loads at once with no ping')

    def run_fixture(self, fix):
        with tempfile.TemporaryDirectory(prefix='mixpi-media-chip-ping-') as temporary:
            target = Path(temporary)
            binary = runner.build_chip_ping(target, fix=fix)
            renders = os.environ.get('MIXPI_MEDIA_RENDERS', '') if fix else ''
            fonts = ':'.join(str(target / name) for name in runner.FONTS)
            result = runner.run(binary, *([renders] if renders else []), qss=runner.AGREED_QSS,
                                environment_extra={'MIXPI_FONTS': fonts})
            print(result.stdout, result.stderr[-3000:], flush=True)
            return result

    def test_chip_timing_and_ping_on_the_media_page(self):
        result = self.run_fixture(fix=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr[-3000:])
        self.assertIn(' 0 failures', result.stdout)
        for name in self.NAMES:
            self.assertIn('PASS ' + name, result.stdout)

    def test_build_h_fails_without_the_patch(self):
        # Build H: IN USE at OPEN, no ping while the Media page is open.
        result = self.run_fixture(fix=False)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        for name in ('open: an opened drive with nothing loaded reads READY',
                     'page: an opened drive with nothing loaded reads READY, and its button BROWSE',
                     'browse: a track in the library\'s preview player only leaves it READY',
                     'ping: a new drive is pinged while the Media page is open',
                     'ping: a ping already up stays on top when the Media page opens'):
            self.assertIn('FAIL ' + name, result.stdout)
        # What build H already did right still passes.
        for name in ('deck: a track from the drive on deck 1 reads IN USE',
                     'pad: a sample from the drive on pad 3 reads IN USE',
                     'ping: AUTO LOAD with the Media page open loads at once with no ping'):
            self.assertIn('PASS ' + name, result.stdout)


if __name__ == '__main__':
    unittest.main()
