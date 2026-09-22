"""Real filesystem safety and checksum tests for the USB → Pi copy helper."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import sys

SCRIPT = Path(__file__).resolve().parents[1] / "stage3/02-desktop/files/bin/mixpi-media"
loader = importlib.machinery.SourceFileLoader("mixpi_media", str(SCRIPT))
spec = importlib.util.spec_from_loader(loader.name, loader)
media = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = media
loader.exec_module(media)


class MediaTransferTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        # macOS /var is a symlink; fixture paths must use their physical path.
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / "USB"
        self.exports = self.root / "exports"
        self.audio = self.root / "audio"
        self.state = self.root / "state"
        for directory in (self.source, self.exports, self.audio):
            directory.mkdir()
        (self.source / "Contents/Éthiopie").mkdir(parents=True)
        (self.source / "Contents/Éthiopie/Track 01.mp3").write_bytes(b"music\x00" * 5000)

    def tearDown(self):
        self.temp.cleanup()

    def plan(self, **kwargs):
        return media.make_plan(self.source, "Ethio Jazz / DJ", "unique-usb-id",
                               self.exports, self.audio, self.state, reserve=4096, **kwargs)

    def export(self):
        database = self.source / "PIONEER/rekordbox/export.pdb"
        database.parent.mkdir(parents=True)
        database.write_bytes(b"test playlist database")

    def assert_no_staging(self):
        staging = self.state / "staging"
        self.assertFalse(staging.exists() and list(staging.iterdir()))

    def test_complete_export_preserves_paths_and_source(self):
        self.export()
        (self.source / "Contents/set.m3u8").write_text("Éthiopie/Track 01.mp3\n")
        before = {path.relative_to(self.source): path.read_bytes()
                  for path in self.source.rglob("*") if path.is_file()}
        plan = self.plan()
        self.assertEqual(plan.kind, "Rekordbox export")
        self.assertEqual(plan.destination.parent, self.exports)
        self.assertFalse(self.state.exists(), "Planning must not create state")
        result = media.copy_plan(plan)
        self.assertEqual(result["status"], "copied")
        for path, data in before.items():
            self.assertEqual((plan.destination / path).read_bytes(), data)
            self.assertEqual((self.source / path).read_bytes(), data)
        self.assertEqual(set(before), {path.relative_to(self.source)
                                      for path in self.source.rglob("*") if path.is_file()})
        receipt = json.loads((plan.destination / media.RECEIPT).read_text())
        self.assertEqual(set(receipt["sha256"]), {str(path) for path in before})
        self.assert_no_staging()

    def test_plain_files_go_to_music_backup(self):
        plan = self.plan()
        self.assertEqual(plan.destination.parent, self.audio)
        media.copy_plan(plan)
        self.assertTrue((plan.destination / "Contents/Éthiopie/Track 01.mp3").is_file())

    def test_real_mount_layout_copies_to_sibling_under_media_user(self):
        self.export()
        mount_parent = self.root / "media/pi"
        mount_parent.mkdir(parents=True)
        mounted_source = mount_parent / "MANTACORE"
        self.source.rename(mounted_source)
        plan = media.make_plan(mounted_source, "MANTACORE", "usb-id",
                               mount_parent, self.audio, self.state, reserve=4096)
        self.assertEqual(plan.destination.parent, mounted_source.parent)
        self.assertNotEqual(plan.destination, mounted_source)
        media.copy_plan(plan)
        self.assertTrue((plan.destination / "PIONEER/rekordbox/export.pdb").is_file())

    def test_export_excludes_unrelated_files_and_os_metadata(self):
        self.export()
        (self.source / "private-documents").mkdir()
        (self.source / "private-documents/unrelated.txt").write_text("not music")
        (self.source / ".Trashes").mkdir()
        (self.source / ".Trashes/deleted.mp3").write_bytes(b"deleted")
        (self.source / "Contents/.Spotlight-V100").mkdir()
        (self.source / "Contents/.Spotlight-V100/index").write_bytes(b"index")
        (self.source / "Contents/.DS_Store").write_bytes(b"metadata")
        (self.source / "Contents/._appledouble").write_bytes(b"metadata")
        # Unrelated symlinks cannot break copying an otherwise valid export.
        (self.source / "unrelated-link").symlink_to(self.root)
        plan = self.plan()
        self.assertEqual(len(plan.files), 2)
        media.copy_plan(plan)
        for relative in ("private-documents", ".Trashes", "Contents/.Spotlight-V100",
                         "Contents/.DS_Store", "Contents/._appledouble", "unrelated-link"):
            self.assertFalse((plan.destination / relative).exists())
            self.assertTrue((self.source / relative).exists())

    def test_ordinary_files_skip_platform_metadata(self):
        (self.source / ".fseventsd").mkdir()
        (self.source / ".fseventsd/log").write_bytes(b"log")
        (self.source / "System Volume Information").mkdir()
        (self.source / "System Volume Information/index").write_bytes(b"index")
        (self.source / "set.m3u8").write_text("Contents/Éthiopie/Track 01.mp3\n")
        plan = self.plan()
        self.assertEqual(len(plan.files), 2)
        media.copy_plan(plan)
        self.assertTrue((plan.destination / "set.m3u8").exists())
        self.assertFalse((plan.destination / ".fseventsd").exists())
        self.assertFalse((plan.destination / "System Volume Information").exists())

    def test_repeat_copy_verifies_existing_without_duplicate(self):
        plan = self.plan()
        media.copy_plan(plan)
        self.assertEqual(media.copy_plan(self.plan())["status"], "already_copied")
        self.assertEqual(len(list(self.audio.iterdir())), 1)
        self.assert_no_staging()

    def test_corrupt_existing_copy_is_not_replaced(self):
        plan = self.plan()
        media.copy_plan(plan)
        target = plan.destination / "Contents/Éthiopie/Track 01.mp3"
        target.write_bytes(b"damaged")
        with self.assertRaisesRegex(media.TransferError, "failed verification"):
            media.copy_plan(plan)
        self.assertEqual(target.read_bytes(), b"damaged")

    def test_existing_unrelated_directory_not_overwritten(self):
        plan = self.plan()
        plan.destination.mkdir()
        marker = plan.destination / "keep"
        marker.write_text("keep me")
        with self.assertRaises(media.TransferError):
            media.copy_plan(plan)
        self.assertEqual(marker.read_text(), "keep me")

    def test_low_space_does_not_publish(self):
        plan = self.plan()
        with patch.object(media.shutil, "disk_usage", return_value=type("Usage", (), {"free": plan.total})()):
            with self.assertRaisesRegex(media.TransferError, "Not enough SD space"):
                media.copy_plan(plan)
        self.assertFalse(plan.destination.exists())
        self.assert_no_staging()

    def test_low_space_readiness_blocks_copy_before_it_starts(self):
        plan = self.plan()
        with patch.object(media.shutil, "disk_usage", return_value=type("Usage", (), {"free": plan.total})()):
            self.assertIn("Not enough SD space", media.readiness_error(plan))
            self.assertFalse(plan.summary()["ready"])
            self.assertIn("Not enough SD space", plan.summary()["unavailable_reason"])
        self.assertFalse(self.state.exists())

    def test_existing_copy_can_be_verified_when_sd_has_low_space(self):
        plan = self.plan()
        media.copy_plan(plan)
        with patch.object(media.shutil, "disk_usage", return_value=type("Usage", (), {"free": 0})()):
            self.assertIsNone(media.readiness_error(plan))
            self.assertTrue(plan.summary()["ready"])
            self.assertEqual(media.copy_plan(plan)["status"], "already_copied")

    def test_cancel_mid_copy_cleans_partial_and_preserves_source(self):
        plan = self.plan()
        cancel = threading.Event()
        with self.assertRaises(media.Cancelled):
            media.copy_plan(plan, cancel, lambda fraction, _: cancel.set())
        self.assertFalse(plan.destination.exists())
        self.assertTrue((self.source / "Contents/Éthiopie/Track 01.mp3").exists())
        self.assert_no_staging()

    def test_disconnect_or_changed_source_does_not_publish(self):
        plan = self.plan()
        (self.source / "Contents/Éthiopie/Track 01.mp3").write_bytes(b"different")
        with self.assertRaisesRegex(media.TransferError, "contents changed"):
            media.copy_plan(plan)
        self.assertFalse(plan.destination.exists())

    def test_changes_during_copy_cancel_publication(self):
        plan = self.plan()
        changed = False
        def progress(fraction, _):
            nonlocal changed
            if not changed and fraction > 0:
                (self.source / "new.mp3").write_bytes(b"new song")
                changed = True
        with self.assertRaisesRegex(media.TransferError, "contents changed"):
            media.copy_plan(plan, progress=progress)
        self.assertFalse(plan.destination.exists())
        self.assert_no_staging()

    def test_symlink_and_special_file_rejected(self):
        link = self.source / "link"
        link.symlink_to(self.root)
        with self.assertRaisesRegex(media.TransferError, "Symlinks and special files"):
            self.plan()
        link.unlink()
        os.mkfifo(link)
        with self.assertRaisesRegex(media.TransferError, "Symlinks and special files"):
            self.plan()

    def test_source_replaced_with_symlink_after_plan_is_rejected(self):
        plan = self.plan()
        path = self.source / "Contents/Éthiopie/Track 01.mp3"
        path.unlink()
        path.symlink_to(SCRIPT)
        with self.assertRaises(media.TransferError):
            media.copy_plan(plan)
        self.assertFalse(plan.destination.exists())

    def test_destination_symlink_rejected(self):
        plan = self.plan()
        self.audio.rmdir()
        self.audio.symlink_to(self.exports)
        with self.assertRaisesRegex(media.TransferError, "must not be a symlink"):
            media.copy_plan(plan)
        self.assertEqual(list(self.exports.iterdir()), [])

    def test_incomplete_rekordbox_export_is_rejected(self):
        (self.source / "PIONEER").mkdir()
        with self.assertRaisesRegex(media.TransferError, "export.pdb"):
            self.plan()

    def test_atomic_publish_never_replaces_even_empty_directory(self):
        staged = self.root / "staged"
        target = self.root / "existing"
        staged.mkdir()
        target.mkdir()
        (staged / "data").write_text("new")
        with self.assertRaises(OSError):
            media.atomic_publish(staged, target)
        self.assertEqual(list(target.iterdir()), [])
        self.assertTrue((staged / "data").exists())

    def test_traversal_inventory_rejected(self):
        for value in ("../outside", "/outside", "Contents/../../outside"):
            with self.assertRaises(media.TransferError):
                media.validate_relative(value)

    def test_corruption_before_verification_never_publishes(self):
        plan = self.plan()
        corrupted = False
        def progress(fraction, message):
            nonlocal corrupted
            if message == "Verifying copied files…" and not corrupted:
                target = next((self.state / "staging").glob("copy-*/Contents/Éthiopie/Track 01.mp3"))
                target.write_bytes(b"corrupt output")
                corrupted = True
        with self.assertRaisesRegex(media.TransferError, "failed verification"):
            media.copy_plan(plan, progress=progress)
        self.assertFalse(plan.destination.exists())
        self.assert_no_staging()

    def test_same_size_and_time_source_changes_do_not_reuse_old_backup(self):
        plan = self.plan()
        media.copy_plan(plan)
        path = self.source / "Contents/Éthiopie/Track 01.mp3"
        original = path.stat()
        path.write_bytes(b"x" * original.st_size)
        os.utime(path, ns=(original.st_atime_ns, original.st_mtime_ns))
        with self.assertRaisesRegex(media.TransferError, "USB contents differ"):
            media.copy_plan(self.plan())
        self.assertNotEqual(path.read_bytes(), (plan.destination / path.relative_to(self.source)).read_bytes())

    def test_staging_inside_source_does_not_create_files_on_usb(self):
        plan = self.plan()
        plan.state_root = self.source / "forbidden-staging"
        with self.assertRaisesRegex(media.TransferError, "Staging must be outside"):
            media.copy_plan(plan)
        self.assertFalse(plan.state_root.exists())

    def test_second_simultaneous_copy_cannot_start(self):
        plan = self.plan()
        self.state.mkdir()
        with (self.state / "copy.lock").open("w") as lock:
            media.fcntl.flock(lock, media.fcntl.LOCK_EX | media.fcntl.LOCK_NB)
            with self.assertRaisesRegex(media.TransferError, "Another USB copy"):
                media.copy_plan(plan)
        self.assertFalse(plan.destination.exists())

    def test_directory_created_during_copy_is_not_replaced(self):
        plan = self.plan()
        def progress(fraction, _):
            if fraction > 0 and not plan.destination.exists():
                plan.destination.mkdir()
                (plan.destination / "keep").write_text("other process")
        with self.assertRaises(OSError):
            media.copy_plan(plan, progress=progress)
        self.assertEqual((plan.destination / "keep").read_text(), "other process")
        self.assert_no_staging()

    def test_identical_labels_on_distinct_drives_remain_separate(self):
        first = self.plan()
        second = media.make_plan(self.source, "Ethio Jazz / DJ", "another-usb-id",
                                 self.exports, self.audio, self.state)
        self.assertNotEqual(first.destination, second.destination)

    def test_mount_listing_excludes_entire_boot_disk_and_unmounted_media(self):
        data = {"blockdevices": [
            {"path": "/dev/sda", "tran": "usb", "children": [
                {"path": "/dev/sda1", "mountpoints": ["/boot/firmware"]},
                {"path": "/dev/sda2", "mountpoints": ["/"]},
                {"path": "/dev/sda3", "mountpoints": ["/media/pi/DATA"]}]},
            {"path": "/dev/sdb", "tran": "usb", "children": [
                {"path": "/dev/sdb1", "label": "Music", "uuid": "123",
                 "size": 12345, "mountpoints": ["/media/pi/Music"]}]},
            {"path": "/dev/sdc", "tran": "usb", "children": [
                {"path": "/dev/sdc1", "mountpoints": [None]}]},
            {"path": "/dev/mmcblk0", "rm": False, "children": [
                {"path": "/dev/mmcblk0p3", "mountpoints": ["/media/pi/INTERNAL"]}]},
        ]}
        drives = media.mounted_drives(data)
        self.assertEqual(len(drives), 1)
        self.assertEqual(drives[0]["source"], "/media/pi/Music")
        self.assertEqual(drives[0]["uuid"], "123")


if __name__ == "__main__":
    unittest.main()
