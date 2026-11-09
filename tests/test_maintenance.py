"""Host tests for timer state/recovery; no host services are changed."""
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
FILES = ROOT / "stage3/02-desktop/files"
LOADER = importlib.machinery.SourceFileLoader(
    "mixpi_maintenance", str(FILES / "sbin/mixpi-maintenance"))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
HELPER = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(HELPER)


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name)
        self.snapshot = self.state / "timers.json"
        self.running = {"apt-daily.timer", "fstrim.timer", "systemd-tmpfiles-clean.timer"}
        self.original = self.running.copy()
        self.calls = []
        patch = mock.patch.object(HELPER, "systemctl", side_effect=self.systemctl)
        patch.start()
        self.addCleanup(patch.stop)
        patch = mock.patch.object(HELPER, "packages_busy", return_value=False)
        self.busy = patch.start()
        self.addCleanup(patch.stop)

    def systemctl(self, *args):
        self.calls.append(args)
        command, *_, timer = args
        if command == "show":
            return subprocess.CompletedProcess(args, 0,
                                               "active\n" if timer in self.running else "inactive\n")
        if command == "stop":
            # The durable snapshot must precede even the first stop.
            self.assertEqual(set(json.loads(self.snapshot.read_text())), self.original)
            self.running.discard(timer)
        elif command == "start":
            self.running.add(timer)
        return subprocess.CompletedProcess(args, 0, "")

    def test_exact_approved_timer_list(self):
        self.assertEqual(set(HELPER.TIMERS), {
            "apt-daily.timer", "apt-daily-upgrade.timer", "man-db.timer",
            "dpkg-db-backup.timer", "logrotate.timer", "fstrim.timer",
            "e2scrub_all.timer", "rpi-zram-writeback.timer",
            "systemd-tmpfiles-clean.timer"})

    def test_snapshot_and_restore_only_previously_active_timers(self):
        HELPER.pause(self.state)
        self.assertFalse(self.running)
        self.assertEqual(set(json.loads(self.snapshot.read_text())), self.original)
        HELPER.restore(self.state)
        self.assertEqual(self.running, self.original)
        self.assertFalse(self.snapshot.exists())
        self.assertTrue(all(call[-1].endswith(".timer") for call in self.calls))

    def test_repeat_pause_keeps_original_snapshot_and_restore_is_repeatable(self):
        HELPER.pause(self.state)
        first = self.snapshot.read_bytes()
        HELPER.pause(self.state)
        self.assertEqual(self.snapshot.read_bytes(), first)
        HELPER.restore(self.state)
        count = len(self.calls)
        HELPER.restore(self.state)
        self.assertEqual(len(self.calls), count)
        self.assertEqual(self.running, self.original)

    def test_no_active_or_installed_timers_does_not_start_any(self):
        self.running.clear()
        self.original.clear()
        HELPER.pause(self.state)
        HELPER.restore(self.state)
        self.assertFalse(any(call[0] in {"start", "stop"} for call in self.calls))

    def test_running_package_job_finishes_before_pause_returns(self):
        self.busy.side_effect = [True, True, False]
        with mock.patch.object(HELPER.time, "sleep") as sleep:
            HELPER.pause(self.state)
        self.assertEqual(sleep.call_args_list, [mock.call(1), mock.call(1)])
        self.assertFalse(self.running)
        self.assertFalse(any(call[-1].endswith(".service") for call in self.calls))

    def test_partial_stop_failure_can_be_restored(self):
        def fail_second(*args):
            if args == ("stop", "fstrim.timer"):
                raise subprocess.CalledProcessError(1, args)
            return self.systemctl(*args)
        with mock.patch.object(HELPER, "systemctl", side_effect=fail_second):
            with self.assertRaises(subprocess.CalledProcessError):
                HELPER.pause(self.state)
        self.assertNotIn("apt-daily.timer", self.running)
        HELPER.restore(self.state)
        self.assertEqual(self.running, self.original)

    def test_failed_restore_attempts_every_timer_and_keeps_snapshot_for_retry(self):
        HELPER.pause(self.state)
        def fail_first(*args):
            if args == ("start", "apt-daily.timer"):
                raise subprocess.CalledProcessError(1, args)
            return self.systemctl(*args)
        with mock.patch.object(HELPER, "systemctl", side_effect=fail_first):
            with self.assertRaises(RuntimeError):
                HELPER.restore(self.state)
        self.assertTrue(self.snapshot.exists())
        self.assertIn("fstrim.timer", self.running)
        self.assertIn("systemd-tmpfiles-clean.timer", self.running)
        HELPER.restore(self.state)
        self.assertEqual(self.running, self.original)

    def test_interrupted_package_wait_can_be_restored(self):
        self.busy.side_effect = KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            HELPER.pause(self.state)
        HELPER.restore(self.state)
        self.assertEqual(self.running, self.original)

    def test_snapshot_cannot_name_arbitrary_units(self):
        for value in (["sshd.service"], {"apt-daily.timer": True}, "apt-daily.timer"):
            with self.subTest(value=value):
                self.snapshot.write_text(json.dumps(value))
                for action in (HELPER.pause, HELPER.restore):
                    with self.assertRaises(ValueError):
                        action(self.state)
        self.assertFalse(self.calls)


class PackageJobTests(unittest.TestCase):
    def test_active_apt_service_is_busy(self):
        with mock.patch.object(HELPER, "active", side_effect=[False, True]):
            self.assertTrue(HELPER.packages_busy())

    def test_manual_dpkg_process_is_busy(self):
        with tempfile.TemporaryDirectory() as temporary:
            comm = Path(temporary) / "comm"
            comm.write_text("dpkg\n")
            with mock.patch.object(HELPER, "active", return_value=False), \
                    mock.patch.object(HELPER.Path, "glob", return_value=[comm]):
                self.assertTrue(HELPER.packages_busy())

    def test_held_package_lock_is_busy_then_idle_after_release(self):
        with tempfile.TemporaryDirectory() as temporary:
            lock = Path(temporary) / "lock"
            lock.touch()
            # POSIX record locks are process-owned, so hold one in a child.
            child = subprocess.Popen(
                ["python3", "-c", "import fcntl,sys; "
                 "f=open(sys.argv[1], 'r+'); fcntl.lockf(f, fcntl.LOCK_EX); "
                 "print('locked', flush=True); sys.stdin.read()", str(lock)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
            try:
                self.assertEqual(child.stdout.readline(), "locked\n")
                with mock.patch.object(HELPER, "active", return_value=False), \
                        mock.patch.object(HELPER.Path, "glob", return_value=[]), \
                        mock.patch.object(HELPER, "PACKAGE_LOCKS", (str(lock),)):
                    self.assertTrue(HELPER.packages_busy())
                    child.communicate(timeout=5)
                    self.assertFalse(HELPER.packages_busy())
            finally:
                if child.poll() is None:
                    child.kill()
                    child.communicate()


class ServiceWiringTests(unittest.TestCase):
    def test_fixed_service_supervises_mixxx_and_always_restores(self):
        unit = (FILES / "systemd/user/mixpi-mixxx.service").read_text()
        self.assertIn("ExecStartPre=/usr/bin/sudo -n /usr/local/sbin/mixpi-maintenance pause\n", unit)
        self.assertIn("ExecStart=/usr/bin/mixxx\n", unit)
        self.assertIn("ExecStopPost=/usr/bin/sudo -n /usr/local/sbin/mixpi-maintenance restore\n", unit)
        self.assertIn("TimeoutStartSec=infinity\n", unit)
        self.assertIn("PartOf=graphical-session.target\n", unit)
        sudoers = (FILES / "sudoers/020_mixpi-maintenance").read_text()
        self.assertIn("(root) NOPASSWD: /usr/local/sbin/mixpi-maintenance pause, "
                      "/usr/local/sbin/mixpi-maintenance restore\n", sudoers)

    def test_sway_launcher_imports_environment_before_starting_fixed_service(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            log = path / "calls"
            command = path / "systemctl"
            command.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$CALLS"\n')
            command.chmod(0o755)
            subprocess.run(["bash", str(FILES / "bin/mixpi-mixxx-start")], check=True,
                           env={"PATH": f"{path}:/usr/bin:/bin", "CALLS": str(log),
                                "WAYLAND_DISPLAY": "wayland-1", "SWAYSOCK": "/run/sway.sock"})
            self.assertEqual(log.read_text().splitlines(), [
                "--user import-environment WAYLAND_DISPLAY",
                "--user import-environment SWAYSOCK",
                "--user start mixpi-mixxx.service"])


if __name__ == "__main__":
    unittest.main()
