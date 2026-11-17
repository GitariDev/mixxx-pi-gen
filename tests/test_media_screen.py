"""R-2 and R-4: the native Media page, the USB chip state, the insert ping and
the Safe to remove strip (mixxx-media-screen.patch)."""
from pathlib import Path
import re
import tempfile
import unittest

from native.library_interface_runner import qt_available
from native import media_screen_runner as runner

ROOT = Path(__file__).resolve().parents[1]
PATCH = runner.PATCH_DIR / runner.SCREEN


def added(path):
    """The new text in the patch's hunks for a file: added and context lines."""
    text = PATCH.read_text()
    section = text.split('+++ b/' + path + '\n', 1)[1].split('\ndiff --git ', 1)[0]
    return '\n'.join(line[1:] for line in section.splitlines() if line[:1] in ('+', ' '))


class MediaScreenPatchTests(unittest.TestCase):
    def test_patch_touches_only_n3_files(self):
        files = re.findall(r'^diff --git a/(\S+) ', PATCH.read_text(), re.MULTILINE)
        self.assertEqual(sorted(files), ['src/library/mixpimedia.h', 'src/library/mixpimediapage.h',
                                         'src/widget/mixpipage.h'])

    def test_media_load_opens_the_page_not_the_dialogs(self):
        media = added('src/library/mixpimedia.h')
        show = media.split('    void show(bool) {', 1)[1].split('\n    }\n', 1)[0]
        self.assertIn('m_page->open()', show)
        for dialog in ('MixpiMediaDialog(', 'showControlled', 'MixpiControlledDialog'):
            self.assertNotIn(dialog, show)
        # The page code cannot reach the controlled dialog at all.
        for path in ('src/library/mixpimediapage.h', 'src/widget/mixpipage.h'):
            self.assertNotIn('MixpiControlled', added(path))
        self.assertNotIn('new MixpiMediaDialog', media)

    def test_controls_and_label_contract(self):
        media = added('src/library/mixpimedia.h')
        self.assertIn('ConfigKey("[MixPi]", "media_state")', media)
        self.assertIn('mixpiSetNamedLabelText<WLabel>(window(), QStringLiteral("MixpiUsbName")', media)
        self.assertIn('QStringLiteral("screen")', media)

    def test_no_scan_refresh_or_power_down(self):
        page = added('src/library/mixpimediapage.h')
        for word in ('SCAN', 'Refresh', 'REFRESH', 'power down', 'Power down'):
            self.assertNotIn('"' + word, page)

    def test_inventory_runs_only_on_mount_changes(self):
        media = added('src/library/mixpimedia.h')
        tick = media.split('    void tick() {', 1)[1].split('\n    }\n', 1)[0]
        self.assertIn('if (mounts != m_mounts)', tick)
        self.assertLess(tick.index('if (mounts != m_mounts)'), tick.index('observeNow()'))


@unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
class MediaScreenNativeTests(unittest.TestCase):
    def test_page_strips_and_usb_name(self):
        with tempfile.TemporaryDirectory(prefix='mixpi-media-screen-') as temporary:
            binary = runner.build_screen(Path(temporary))
            result = runner.run(binary)
            print(result.stdout, result.stderr, flush=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(' 0 failures', result.stdout)
            for name in ('page host: 800x480 window gives (0,48,800,432)',
                         'page host: 800x444 window gives (0,48,800,396)',
                         'ping: auto-dismiss after 15 s, as DISMISS',
                         'safe strip: hides after 30 s',
                         'usb name: the next refresh sets the reloaded Label (Elide right)'):
                self.assertIn('PASS ' + name, result.stdout)


if __name__ == '__main__':
    unittest.main()
