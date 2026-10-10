"""Real filesystem safety tests for moving Mixxx recordings from the Pi to USB."""
import hashlib
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "stage3/02-desktop/files/bin/mixpi-media"
loader = importlib.machinery.SourceFileLoader("mixpi_media_recordings", str(SCRIPT))
spec = importlib.util.spec_from_loader(loader.name, loader)
media = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = media
loader.exec_module(media)

FIRST, SECOND = "2026-10-09_20h00m00s", "2026-10-10_21h05m33s"


class RecordingsMoveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        # macOS /var is a symlink; fixture paths must use their physical path.
        self.root = Path(self.temp.name).resolve()
        self.folder = self.root / "Music/Mixxx/Recordings"
        self.usb = self.root / "media/pi/MANTACORE"
        self.state = self.root / "state"
        self.folder.mkdir(parents=True)
        (self.usb / "PIONEER/rekordbox").mkdir(parents=True)
        (self.usb / "PIONEER/rekordbox/export.pdb").write_bytes(b"playlist database")
        (self.usb / "Contents/Éthiopie").mkdir(parents=True)
        (self.usb / "Contents/Éthiopie/Track 01.mp3").write_bytes(b"music\x00" * 5000)
        self.saved = self.usb / media.RECORDINGS_FOLDER
        for age, name in enumerate((FIRST, SECOND)):
            self.record(name, bytes([age + 1]) * 300000, 1_700_000_000 + age * 86400)

    def tearDown(self):
        self.temp.cleanup()

    def record(self, name, audio, when, cue=True):
        (self.folder / f"{name}.wav").write_bytes(audio)
        os.utime(self.folder / f"{name}.wav", (when, when))
        if cue:
            (self.folder / f"{name}.cue").write_text(f'FILE "{name}.wav" WAVE\n')
            os.utime(self.folder / f"{name}.cue", (when, when))

    def listed(self, in_use=()):
        return media.list_recordings(self.folder, in_use)

    def target(self, **changes):
        return dict(media.usb_target({"source": str(self.usb), "fstype": "vfat"}), **changes)

    def move(self, recordings=None, **options):
        return media.move_recordings(self.folder, self.listed() if recordings is None else recordings,
                                     options.pop("target", None) or self.target(),
                                     state_root=self.state, **options)

    def tree(self, root):
        return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted(root.rglob("*")) if path.is_file()}

    def test_lists_newest_first_with_cue_and_skips_everything_else(self):
        (self.folder / ".hidden.wav").write_bytes(b"partial")
        (self.folder / ".DS_Store").write_bytes(b"metadata")
        (self.folder / "subfolder").mkdir()
        (self.folder / "link.wav").symlink_to(SCRIPT)
        recordings = self.listed()
        self.assertEqual([item["name"] for item in recordings], [SECOND, FIRST])
        self.assertEqual([entry["path"] for entry in recordings[0]["files"]],
                         [SECOND + ".cue", SECOND + ".wav"])
        self.assertEqual(recordings[0]["bytes"],
                         sum((self.folder / f"{SECOND}.{kind}").stat().st_size for kind in ("wav", "cue")))
        self.assertFalse(recordings[0]["busy"])
        self.assertEqual(media.list_recordings(self.root / "never-recorded"), [])

    def test_recordings_folder_follows_mixxx_preference(self):
        config = self.root / "mixxx.cfg"
        config.write_text("[Library]\nDirectory /music\n\n[Recording]\nCueEnabled 1\n"
                          "Directory /home/pi/My Mixes/Live Sets\nEncoding WAV\n")
        self.assertEqual(media.recordings_directory(config), Path("/home/pi/My Mixes/Live Sets"))
        config.write_text("[Recording]\nEncoding WAV\n")
        self.assertEqual(media.recordings_directory(config), Path.home() / "Music/Mixxx/Recordings")
        self.assertEqual(media.recordings_directory(self.root / "missing.cfg"),
                         Path.home() / "Music/Mixxx/Recordings")

    @unittest.skipUnless(os.path.isdir("/proc/self/fd"), "Linux /proc required")
    def test_open_recording_is_reported_in_use(self):
        with (self.folder / f"{SECOND}.wav").open("ab"):
            self.assertEqual(media.files_in_use(self.folder), {SECOND + ".wav"})
            recordings = media.list_recordings(self.folder)
        self.assertEqual([item["busy"] for item in recordings], [True, False])
        self.assertEqual(media.files_in_use(self.folder), set())

    def test_move_verifies_removes_originals_and_leaves_rekordbox_alone(self):
        before = self.tree(self.folder)
        export = self.tree(self.usb)
        messages = []
        result = self.move(progress=lambda fraction, message: messages.append((fraction, message)))
        self.assertEqual(result["status"], "moved")
        self.assertEqual(result["recordings"], 2)
        self.assertEqual(result["files"], 4)
        self.assertEqual(Path(result["destination"]), self.saved)
        self.assertEqual(self.tree(self.saved), before)
        self.assertEqual(list(self.folder.iterdir()), [])
        after = self.tree(self.usb)
        self.assertEqual({path: digest for path, digest in after.items()
                          if not path.startswith(media.RECORDINGS_FOLDER)}, export)
        self.assertEqual((self.saved / f"{FIRST}.wav").stat().st_mtime, 1_700_000_000)
        self.assertEqual(messages[-1][0], 1.0)
        self.assertEqual([fraction for fraction, _ in messages], sorted(fraction for fraction, _ in messages))
        self.assertTrue(any(message.startswith("Verifying") for _, message in messages))

    def test_only_selected_recordings_move(self):
        self.move([item for item in self.listed() if item["name"] == SECOND])
        self.assertEqual(sorted(path.name for path in self.saved.iterdir()), [SECOND + ".cue", SECOND + ".wav"])
        self.assertEqual(sorted(path.name for path in self.folder.iterdir()), [FIRST + ".cue", FIRST + ".wav"])

    def test_interrupted_move_resumes_without_duplicating(self):
        self.saved.mkdir()
        (self.saved / f"{SECOND}.wav").write_bytes((self.folder / f"{SECOND}.wav").read_bytes())
        (self.saved / f".{FIRST}.wav{media.PARTIAL}").write_bytes(b"half a file")
        before = self.tree(self.folder)
        self.move()
        self.assertEqual(self.tree(self.saved), before)
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_different_file_with_same_name_is_never_replaced(self):
        self.saved.mkdir()
        (self.saved / f"{FIRST}.wav").write_bytes(b"someone else's mix")
        before = self.tree(self.folder)
        with self.assertRaisesRegex(media.TransferError, "was not replaced.*1 already moved"):
            self.move()
        self.assertEqual((self.saved / f"{FIRST}.wav").read_bytes(), b"someone else's mix")
        # The newer recording was listed first and had already been moved safely.
        remaining = self.tree(self.folder)
        self.assertEqual(set(remaining), {FIRST + ".cue", FIRST + ".wav"})
        self.assertEqual(self.tree(self.saved)[SECOND + ".wav"], before[SECOND + ".wav"])

    def test_cancel_mid_copy_keeps_pi_recordings_and_clears_partial(self):
        before = self.tree(self.folder)
        cancel = threading.Event()
        with self.assertRaisesRegex(media.Cancelled, "Move cancelled. Recordings are still on the Pi"):
            self.move(cancel=cancel, progress=lambda fraction, _: cancel.set())
        self.assertEqual(self.tree(self.folder), before)
        self.assertEqual(list(self.saved.iterdir()), [])

    def test_corruption_on_usb_keeps_the_pi_recording(self):
        before = self.tree(self.folder)
        def corrupt(fraction, message):
            # After the audio is written, before it is read back from the drive.
            if message == f"Copying {SECOND}.wav":
                partial = self.saved / f".{SECOND}.wav{media.PARTIAL}"
                partial.write_bytes(b"x" * partial.stat().st_size)
        with self.assertRaisesRegex(media.TransferError, "failed verification"):
            self.move(progress=corrupt)
        self.assertEqual(self.tree(self.folder), before)
        # Only files that passed verification may be on the drive.
        self.assertEqual([path.name for path in self.saved.iterdir()], [SECOND + ".cue"])

    def test_recording_changed_after_listing_is_not_moved(self):
        recordings = self.listed()
        with (self.folder / f"{SECOND}.wav").open("ab") as handle:
            handle.write(b"still recording")
        with self.assertRaisesRegex(media.TransferError, "changed after it was listed"):
            self.move(recordings)
        self.assertTrue((self.folder / f"{SECOND}.wav").exists())
        self.assertEqual(list(self.saved.iterdir()), [])

    def test_recording_changed_during_move_stays_on_pi(self):
        changed = False
        def grow(fraction, message):
            nonlocal changed
            # Both files are verified on USB; the cue sheet is rewritten before deletion.
            if not changed and message == f"Verifying {SECOND}.wav on USB":
                changed = True
                (self.folder / f"{SECOND}.cue").write_text("TRACK 02 AUDIO\n")
        with self.assertRaisesRegex(media.TransferError, "changed during the move"):
            self.move(progress=grow)
        self.assertTrue((self.folder / f"{SECOND}.wav").exists())
        self.assertEqual((self.folder / f"{SECOND}.cue").read_text(), "TRACK 02 AUDIO\n")

    def test_in_use_read_only_fat_limit_and_space_block_before_any_write(self):
        recordings = self.listed()
        self.assertIsNone(media.move_error(recordings, self.target()))
        self.assertIn("Select at least one", media.move_error([], self.target()))
        self.assertIn("is in use", media.move_error(self.listed({SECOND + ".wav"}), self.target()))
        self.assertIn("read-only", media.move_error(recordings, self.target(read_only=True)))
        self.assertIn("Not enough USB space", media.move_error(recordings, self.target(free=media.USB_RESERVE)))
        huge = [dict(recordings[0], files=[dict(recordings[0]["files"][0], size=media.FAT_FILE_LIMIT + 1)])]
        self.assertIn("over 4 GiB", media.move_error(huge, self.target()))
        self.assertNotIn("over 4 GiB", media.move_error(huge, self.target(fstype="exfat", free=0)))
        before = self.tree(self.folder)
        with self.assertRaisesRegex(media.TransferError, "Not enough USB space.*still on the Pi"):
            with patch.object(media, "usb_target", return_value=self.target(free=0)):
                self.move()
        self.assertEqual(self.tree(self.folder), before)
        self.assertFalse(self.saved.exists())
        self.assertFalse(self.state.exists())

    def test_replaced_drive_is_refused(self):
        with self.assertRaisesRegex(media.TransferError, "changed or was removed"):
            self.move(target=self.target(device=-1))
        self.assertFalse(self.saved.exists())
        self.assertEqual(len(list(self.folder.iterdir())), 4)

    def test_second_simultaneous_transfer_cannot_start(self):
        self.state.mkdir()
        with (self.state / "copy.lock").open("w") as lock:
            media.fcntl.flock(lock, media.fcntl.LOCK_EX | media.fcntl.LOCK_NB)
            with self.assertRaisesRegex(media.TransferError, "Another USB transfer"):
                self.move()
        self.assertEqual(len(list(self.folder.iterdir())), 4)

    def test_symlinked_recordings_folder_on_usb_is_refused(self):
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir()
        self.saved.symlink_to(elsewhere)
        with self.assertRaisesRegex(media.TransferError, "must not be a symlink"):
            self.move()
        self.assertEqual(list(elsewhere.iterdir()), [])
        self.assertEqual(len(list(self.folder.iterdir())), 4)

    def test_usb_to_pi_copy_ignores_moved_recordings(self):
        plain = self.root / "media/pi/PLAIN"
        (plain / "Sets").mkdir(parents=True)
        (plain / "Sets/track.mp3").write_bytes(b"music" * 2000)
        backups = self.root / "backups"
        backups.mkdir()
        def plan():
            return media.make_plan(plain, "PLAIN", "plain-id", self.root / "exports", backups, self.state)
        first = plan()
        media.move_recordings(self.folder, self.listed(),
                              media.usb_target({"source": str(plain), "fstype": "exfat"}),
                              state_root=self.state)
        second = plan()
        self.assertEqual(second.fingerprint, first.fingerprint)
        self.assertEqual([entry["path"] for entry in second.files], ["Sets/track.mp3"])


if __name__ == "__main__":
    unittest.main()
