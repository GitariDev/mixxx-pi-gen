import os
import importlib.util
import json
from pathlib import Path
import runpy
import subprocess
import unittest

from native.library_interface_runner import qt_available
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "stage3/02-desktop/files/bin/mixpi-touch-defaults"


class InitialLibrarySeedingTests(unittest.TestCase):
    def test_only_new_profile_requests_internal_library(self):
        seed = runpy.run_path(str(SEED))["seed"]
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "profile/mixxx.cfg"
            seed(config)
            self.assertIn("MixPiBootstrapLibrary 1\n", config.read_text())
            first = config.read_bytes()
            seed(config)
            self.assertEqual(config.read_bytes(), first)

    def test_existing_empty_profile_is_not_reinterpreted_as_fresh(self):
        seed = runpy.run_path(str(SEED))["seed"]
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "mixxx.cfg"
            config.touch()
            seed(config)
            self.assertNotIn("MixPiBootstrapLibrary", config.read_text())

    def test_missing_config_symlink_target_is_not_a_fresh_profile(self):
        seed = runpy.run_path(str(SEED))["seed"]
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "mixxx.cfg"
            config.symlink_to("deliberately-missing.cfg")
            with self.assertRaises(OSError):
                seed(config)
            self.assertTrue(config.is_symlink())
            self.assertEqual(os.readlink(config), "deliberately-missing.cfg")

    def test_existing_pending_or_disabled_flags_are_preserved(self):
        seed = runpy.run_path(str(SEED))["seed"]
        for value in ("0", "1"):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as temporary:
                config = Path(temporary) / "mixxx.cfg"
                config.write_text("[Library]\nMixPiBootstrapLibrary " + value + "\n")
                seed(config)
                self.assertIn("MixPiBootstrapLibrary " + value + "\n", config.read_text())

    def test_core_uses_native_registration_and_consumes_only_success(self):
        patch = (ROOT / "stage3/01-install-packages/files/mixxx-initial-library.patch").read_text()
        self.assertIn("m_pTrackCollectionManager->addDirectory(mixxx::FileInfo(directory))", patch)
        self.assertIn("DirectoryDAO::AddResult::Ok", patch)
        self.assertIn("pConfig->setValue(bootstrapKey, false)", patch)
        self.assertIn("Result::Unmanaged && !hasRegisteredRoots", patch)
        self.assertIn("Result::Unavailable", patch)
        self.assertNotIn("sqlite", patch.lower())


@unittest.skipUnless(qt_available(), "Qt6 development dependencies required")
class InitialLibraryNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build_directory = tempfile.TemporaryDirectory(prefix="initial-library-native-")
        cls.addClassCleanup(cls.build_directory.cleanup)
        specification = importlib.util.spec_from_file_location(
            "initial_library_runner", ROOT / "tests/native/initial_library_runner.py")
        runner = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(runner)
        cls.binary = runner.build(Path(cls.build_directory.name))

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="initial-library-fixture-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()
        self.home = self.root / "home"
        self.home.mkdir()

    def run_initialization(self, enabled=True, registered=False, success=True):
        completed = subprocess.run([str(self.binary), str(self.home), str(int(enabled)),
                                    str(int(registered)), str(int(success))],
                                   check=True, capture_output=True, text=True, timeout=15)
        return json.loads(completed.stdout)

    def test_missing_internal_folders_are_created_and_registered(self):
        result = self.run_initialization()
        self.assertEqual(result, {"result": 2, "calls": 1,
                                  "registered": str(self.home / "Music/Backup")})
        self.assertTrue((self.home / "Music/Backup").is_dir())

    def test_existing_copies_are_untouched(self):
        backup = self.home / "Music/Backup"
        backup.mkdir(parents=True)
        track = backup / "original.wav"
        track.write_bytes(b"unchanged synthetic track")
        before = track.stat()
        self.assertEqual(self.run_initialization()["result"], 2)
        self.assertEqual(track.read_bytes(), b"unchanged synthetic track")
        self.assertEqual(track.stat().st_mtime_ns, before.st_mtime_ns)

    def test_existing_roots_win_without_filesystem_changes(self):
        result = self.run_initialization(registered=True)
        self.assertEqual(result, {"result": 1, "calls": 0, "registered": ""})
        self.assertFalse((self.home / "Music").exists())

    def test_unmanaged_profile_never_adds_a_root(self):
        result = self.run_initialization(enabled=False)
        self.assertEqual(result, {"result": 0, "calls": 0, "registered": ""})
        self.assertFalse((self.home / "Music").exists())

    def test_registration_failure_can_retry(self):
        self.assertEqual(self.run_initialization(success=False)["result"], 3)
        self.assertEqual(self.run_initialization()["result"], 2)

    def test_symlink_music_is_never_followed(self):
        external = self.root / "external"
        external.mkdir()
        (self.home / "Music").symlink_to(external)
        result = self.run_initialization()
        self.assertEqual(result["result"], 3)
        self.assertEqual(result["calls"], 0)
        self.assertEqual(list(external.iterdir()), [])

    def test_dangling_music_symlink_is_preserved(self):
        (self.home / "Music").symlink_to(self.root / "missing")
        self.assertEqual(self.run_initialization()["result"], 3)
        self.assertTrue((self.home / "Music").is_symlink())

    def test_backup_symlink_is_refused_then_recovers(self):
        (self.home / "Music").mkdir()
        external = self.root / "external"
        external.mkdir()
        backup = self.home / "Music/Backup"
        backup.symlink_to(external)
        self.assertEqual(self.run_initialization()["calls"], 0)
        self.assertEqual(list(external.iterdir()), [])
        backup.unlink()
        self.assertEqual(self.run_initialization()["result"], 2)

    def test_dangling_backup_symlink_is_preserved(self):
        (self.home / "Music").mkdir()
        backup = self.home / "Music/Backup"
        backup.symlink_to(self.root / "missing")
        self.assertEqual(self.run_initialization()["calls"], 0)
        self.assertTrue(backup.is_symlink())

    def test_non_directory_components_are_not_overwritten(self):
        for component in ("Music", "Music/Backup"):
            with self.subTest(component=component):
                target = self.home / component
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"preserve")
                self.assertEqual(self.run_initialization()["result"], 3)
                self.assertEqual(target.read_bytes(), b"preserve")
                target.unlink()

    def test_missing_home_is_not_created(self):
        self.home.rmdir()
        self.assertEqual(self.run_initialization()["result"], 3)
        self.assertFalse(self.home.exists())

    def test_root_is_not_a_usable_home(self):
        self.home = Path("/")
        self.assertEqual(self.run_initialization()["result"], 3)

    def test_removed_root_is_not_readded_after_flag_consumed(self):
        self.assertEqual(self.run_initialization()["result"], 2)
        backup = self.home / "Music/Backup"
        backup.rmdir()
        self.assertEqual(self.run_initialization(enabled=False)["result"], 0)
        self.assertFalse(backup.exists())


if __name__ == "__main__":
    unittest.main()
