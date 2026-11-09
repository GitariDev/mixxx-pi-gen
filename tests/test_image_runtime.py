"""Exercise image configuration stages against a disposable filesystem."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ImageRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.rootfs = Path(self.temp.name) / 'rootfs'
        self.config = self.rootfs / 'home/pi/.config'
        for folder in (self.config, self.rootfs / 'etc/lightdm',
                       self.rootfs / 'usr/lib/udev/rules.d',
                       self.rootfs / 'boot/firmware'):
            folder.mkdir(parents=True)

    def run_stage(self, relative):
        stage = ROOT / relative
        # Run the real stage, redirecting chroot paths and stubbing ownership only.
        harness = r'''
        chown() { :; }
        export -f chown
        on_chroot() {
            local commands
            commands=$(cat)
            commands=${commands//\/home\/pi/$ROOTFS_DIR\/home\/pi}
            commands=${commands//\/boot\/firmware/$ROOTFS_DIR\/boot\/firmware}
            bash -eu -c "$commands"
        }
        source "$1"
        '''
        subprocess.run(['bash', '-eu', '-c', harness, 'image-test', str(stage)],
                       cwd=stage.parent, env={**os.environ, 'ROOTFS_DIR': str(self.rootfs)},
                       check=True, capture_output=True)

    def test_desktop_stages_preserve_private_files_and_executable_helpers(self):
        private = self.config / 'private-settings'
        private.write_text('local settings')
        private.chmod(0o600)
        units = self.config / 'systemd/user'
        units.mkdir(parents=True)
        mask = units / 'xdg-desktop-portal-gtk.service'
        mask.symlink_to('/dev/null')
        real_unit = units / 'xdg-desktop-portal-wlr.service'
        real_unit.write_text('[Service]\nExecStart=/custom/backend\n')
        for _ in range(2):
            self.run_stage('stage3/02-desktop/02-run.sh')
            self.run_stage('stage3/04-enable-wayland/02-run.sh')
            self.assertEqual(private.stat().st_mode & 0o777, 0o600)
            self.assertEqual(private.read_text(), 'local settings')
            self.assertEqual((self.config / 'sway/config').stat().st_mode & 0o777, 0o644)
            helper = self.config / 'sway/scripts/auto_exit_fullscreen.sh'
            self.assertEqual(helper.stat().st_mode & 0o777, 0o755)
            self.assertFalse(mask.is_symlink())
            self.assertIn('/custom/backend', real_unit.read_text())
            portal = self.config / 'xdg-desktop-portal/sway-portals.conf'
            self.assertTrue(portal.is_file())

    def test_kernel_stage_preserves_boot_arguments_and_is_repeatable(self):
        cmdline = self.rootfs / 'boot/firmware/cmdline.txt'
        cmdline.write_text('console=serial0,115200 root=PARTUUID=123 rootwait preempt=full '
                           'cpufreq.default_governor=powersave preempt=full\n')
        expected = ('console=serial0,115200 root=PARTUUID=123 rootwait '
                    'cpufreq.default_governor=performance\n')
        for _ in range(2):
            self.run_stage('stage3/03-kernel-setup/00-run.sh')
            self.assertEqual(cmdline.read_text(), expected)


if __name__ == '__main__':
    unittest.main()
