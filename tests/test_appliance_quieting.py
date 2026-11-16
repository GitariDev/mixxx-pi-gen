"""F-13, Tier 1 only (owner decision 3): stage-file checks for each change."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
WAYLAND = ROOT / 'stage3/04-enable-wayland/01-run.sh'
I3 = ROOT / 'stage3/02-desktop/files/i3.conf'


def code_lines(path):
    return [line.strip() for line in path.read_text().splitlines()
            if line.strip() and not line.strip().startswith('#')]


def session_files():
    """Files that start or reference programs in the image session."""
    for path in sorted(ROOT.glob('stage*/**/*')):
        if path.is_file() and path.suffix != '.patch' and '__pycache__' not in path.parts:
            yield path


class ApplianceQuietingTier1Tests(unittest.TestCase):
    def test_modemmanager_is_masked(self):
        self.assertIn('systemctl mask ModemManager.service', code_lines(WAYLAND))
        for path in ROOT.glob('stage*/**/*run.sh'):
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertNotRegex('\n'.join(code_lines(path)),
                                    r'(enable|unmask)[^\n]*ModemManager')

    def test_foot_server_disabled_only_while_nothing_uses_footclient(self):
        self.assertIn('systemctl --global disable foot-server.socket foot-server.service',
                      code_lines(WAYLAND))
        for path in session_files():
            with self.subTest(path=str(path.relative_to(ROOT))):
                text = path.read_text(errors='replace')
                if path.name.endswith('run.sh'):
                    text = '\n'.join(code_lines(path))  # the reason comment names it
                self.assertNotIn('footclient', text)
        settings = (ROOT / 'stage3/02-desktop/files/bin/mixpi-settings').read_text()
        self.assertIn('("Terminal", "Advanced commands", ["foot"])', settings)
        self.assertIn('set $term foot', code_lines(I3))

    def test_tier_two_and_kept_services_still_start(self):
        # Tier 2 is deferred; udiskie and lxpolkit are kept (plan F-13 step 4).
        lines = code_lines(I3)
        for program in ('udiskie --tray', 'nm-applet', 'blueman-applet', 'lxpolkit'):
            with self.subTest(program=program):
                self.assertTrue(any(line.startswith('exec') and program in line for line in lines))
        script = WAYLAND.read_text()
        for unit in ('swaync', 'obex', 'mpris-proxy', 'bluetooth'):
            with self.subTest(unit=unit):
                self.assertIsNone(re.search(rf'(mask|disable)[^\n]*{unit}', script))

    def test_udiskie_mounts_without_popups(self):
        # Option B: USB mounts showed udiskie pop-ups over the decks.
        starts = [line for line in code_lines(I3) if line.startswith('exec') and 'udiskie' in line]
        self.assertEqual(len(starts), 1, starts)
        words = re.search(r'exec udiskie([^\']*)', starts[0])[1].split()
        self.assertIn('--no-notify', words)
        self.assertIn('--tray', words)  # eject and mount menu kept
        for option in ('-n', '--notify', '-N', '-A', '--no-automount', '-T', '--no-tray', '-s',
                       '--smart-tray'):
            with self.subTest(option=option):
                self.assertNotIn(option, words)
        # No shipped udiskie config file can turn notifications back on.
        for path in session_files():
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertNotIn('udiskie', [part.lower() for part in path.parts])


if __name__ == '__main__':
    unittest.main()
