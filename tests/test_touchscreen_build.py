"""Host checks; actual rendering, pairing and playback require the Pi."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "stage3/02-desktop/files/bin"


class BuildSyntaxTests(unittest.TestCase):
    def test_shell_syntax(self):
        files = list(ROOT.glob("stage*/**/*run.sh"))
        files += [ROOT / "build.sh", ROOT / "config", ROOT / "source-versions",
                  BIN / "mixpi-mixxx",
                  ROOT / "stage3/02-desktop/files/ssh/mixpi-import-ssh-key"]
        for path in files:
            with self.subTest(path=path.relative_to(ROOT)):
                subprocess.run(["bash", "-n", str(path)], check=True, capture_output=True)

    def test_python_syntax(self):
        for name in ("mixpi-session", "mixpi-settings"):
            compile((BIN / name).read_text(), name, "exec")

    def test_waybar_valid_and_leaves_room_for_skin(self):
        config = json.loads((ROOT / "stage3/02-desktop/files/waybar/config").read_text())
        self.assertGreaterEqual(480 - config["height"] - 24, 420)
        self.assertTrue(config["exclusive"])
        for side in ("left", "center", "right"):
            for module in config[f"modules-{side}"]:
                self.assertIn(module, config)


@unittest.skipUnless(shutil.which("jq"), "jq required")
class MixxxNavigationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.log = self.path / "calls"
        self.tree = self.path / "tree.json"
        self.env = {**os.environ, "PATH": f"{self.path}:{os.environ['PATH']}",
                    "CALLS": str(self.log), "TREE": str(self.tree), "RUNNING": "1"}
        self.command("swaymsg", 'if [ "$1" = "-r" ]; then cat "$TREE"; else printf "%s\\n" "$*" >> "$CALLS"; fi')
        self.command("pgrep", 'exit "$RUNNING"')

    def command(self, name, body):
        path = self.path / name
        path.write_text("#!/bin/sh\n" + body + "\n")
        path.chmod(0o755)

    def run_launcher(self, nodes):
        self.tree.write_text(json.dumps({"nodes": nodes}))
        subprocess.run(["bash", str(BIN / "mixpi-mixxx")], env=self.env, check=True)
        return self.log.read_text()

    def test_returns_to_native_window_without_restarting_audio(self):
        calls = self.run_launcher([{"id": 42, "app_id": "org.mixxx.Mixxx"}])
        self.assertEqual(calls.strip(), "[con_id=42] fullscreen disable, focus")

    def test_returns_to_xwayland_window(self):
        calls = self.run_launcher([{"id": 8, "window_properties": {"class": "Mixxx"}}])
        self.assertIn("[con_id=8]", calls)
        self.assertNotIn("exec", calls)

    def test_launches_on_deck_workspace_if_closed(self):
        calls = self.run_launcher([{"id": 2, "app_id": "foot"}])
        self.assertEqual(calls.splitlines(), ['workspace "1:Mixxx"', 'exec /usr/bin/mixxx'])

    def test_does_not_duplicate_process_still_starting(self):
        self.env["RUNNING"] = "0"
        calls = self.run_launcher([])
        self.assertNotIn("exec", calls)


@unittest.skipUnless(shutil.which("ssh-keygen"), "OpenSSH required")
class SSHProvisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.boot = self.path / "boot"
        self.home = self.path / "pi"
        self.boot.mkdir()
        self.home.mkdir()
        key = self.path / "key"
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
        self.public = key.with_suffix(".pub").read_text()
        source = (ROOT / "stage3/02-desktop/files/ssh/mixpi-import-ssh-key").read_text()
        # Redirect the boot and home mounts and ownership calls for host testing.
        source = source.replace("/boot/firmware", str(self.boot)).replace("/home/pi", str(self.home))
        source = source.replace("-o pi -g pi", "").replace("chown pi:pi", "true")
        self.script = self.path / "import-key"
        self.script.write_text(source)

    def run_import(self, value):
        key_file = self.boot / "mixpi-authorized-key.pub"
        key_file.write_text(value)
        return subprocess.run(["bash", str(self.script)], capture_output=True, text=True)

    def test_import_is_private_and_repeatable(self):
        for _ in range(2):
            result = self.run_import(self.public)
            self.assertEqual(result.returncode, 0, result.stderr)
        authorized = self.home / ".ssh/authorized_keys"
        self.assertEqual(authorized.read_text(), self.public)
        self.assertEqual(authorized.stat().st_mode & 0o777, 0o600)
        self.assertFalse((self.boot / "mixpi-authorized-key.pub").exists())

    def test_invalid_key_does_not_remove_provision_file(self):
        result = self.run_import("ssh-ed25519 AAAA invalid\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.home / ".ssh/authorized_keys").exists())
        self.assertTrue((self.boot / "mixpi-authorized-key.pub").exists())

    def test_rejects_private_keys_and_authorized_key_options(self):
        for value in ("-----BEGIN OPENSSH PRIVATE KEY-----\n",
                      'command="echo no" ' + self.public, self.public + self.public):
            with self.subTest(value=value[:35]):
                self.assertNotEqual(self.run_import(value).returncode, 0)


if __name__ == "__main__":
    unittest.main()
