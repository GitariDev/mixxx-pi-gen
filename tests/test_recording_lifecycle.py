"""Separate raw diagnostics and real production WAV lifecycle qualification."""
import importlib.util
import os
from pathlib import Path
import unittest

from native.library_interface_runner import qt_available
from native.library_interface_runner import reconstruct, sndfile_flags
import tempfile
import subprocess
import shutil


ROOT = Path(__file__).resolve().parents[1]


class RecordingLifecyclePatchIdentity(unittest.TestCase):
    def test_patch_applies_after_media_registry_and_reverses_exactly(self):
        patch = ROOT / "stage3/01-install-packages/files/mixxx-recording-lifecycle.patch"
        with tempfile.TemporaryDirectory(prefix="recording-patch-identity-") as temporary:
            target = Path(temporary)
            paths = ("src/engine/sidechain/enginerecord.cpp", "src/engine/sidechain/enginerecord.h")
            reconstruct(target, exclude=('mixxx-recording-lifecycle.patch',))
            before = {relative: (target / relative).read_bytes() for relative in paths}
            subprocess.run(["git", "apply", "--check", str(patch)], cwd=target, check=True, timeout=15)
            subprocess.run(["git", "apply", str(patch)], cwd=target, check=True, timeout=15)
            subprocess.run(["git", "apply", "--reverse", str(patch)], cwd=target, check=True, timeout=15)
            for relative in paths:
                self.assertEqual(before[relative], (target / relative).read_bytes())


@unittest.skipUnless(qt_available(), "Qt6 development dependencies required; does not install dependencies")
class RecordingLifecycleDiagnostics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / "tests/native/recording_lifecycle_runner.py"
        spec = importlib.util.spec_from_file_location("recording_lifecycle_runner", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls.results = {result["mode"]: result for result in module.run(
            None, baseline=os.environ.get("RECORDING_LIFECYCLE_BASELINE") == "1")}

    def test_normal_stop_growth_restart_raw_payload(self):
        self.assertTrue(self.results["normal"]["diagnosticCompleted"])
        self.assertEqual([item["bytes"] for item in self.results["normal"]["outputs"]], [32768, 16384])

    def test_split_and_failure_holdouts(self):
        for mode in ("split", "invalid-destination", "encoder-failure", "lease-denial", "split-init-failure"):
            with self.subTest(mode=mode):
                self.assertTrue(self.results[mode]["diagnosticCompleted"])

    def test_real_file_size_limit_rejects_writes(self):
        result = self.results["write-failure"]
        self.assertLessEqual(result["actualBytes"], 4096)
        self.assertLessEqual(result["claimedBytes"], result["actualBytes"])

    def test_write_failure_must_report_error_and_stop(self):
        self.assertTrue(self.results["write-failure"]["honestWriteFailure"],
                        "Known baseline defect: real QFile failure still reports ON/success")

    def test_new_recording_must_recover_after_write_failure(self):
        self.assertTrue(self.results["write-failure"]["recoveryPayloadValid"],
                        "Known baseline defect: QDataStream retains failed write status across reopen")

    def test_shutdown_diagnostic_is_not_destructor_finalization(self):
        self.assertTrue(self.results["shutdown"]["diagnosticCompleted"])
        self.assertEqual(self.results["shutdown"]["outputs"][0]["bytes"], 16384)

    def test_qt_stream_reset_isolates_recovery_cause(self):
        result = self.results["qdatastream-recovery"]
        self.assertEqual(result["withoutResetReturn"], -1)
        self.assertEqual(result["withResetReturn"], 16384)
        self.assertTrue(result["resetRecoversPayload"])


@unittest.skipUnless(qt_available(), "Qt6 development dependencies required")
class RecordingLifecycleRealWave(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            sndfile_flags()
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            raise unittest.SkipTest(str(error)) from error
        cls.temporary = tempfile.TemporaryDirectory(prefix="wav-acceptance-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.directory = Path(cls.temporary.name)
        path = ROOT / "tests/native/recording_lifecycle_wav_runner.py"
        spec = importlib.util.spec_from_file_location("recording_wav_runner", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls.results = {item["mode"]: item for item in module.run(
            cls.directory / "candidate.json", baseline=os.environ.get("RECORDING_LIFECYCLE_BASELINE") == "1")}
        path = ROOT / "tests/native/recording_lifecycle_wav_decode.py"
        spec = importlib.util.spec_from_file_location("recording_wav_decode", path)
        cls.decoder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.decoder)

    def check_signal(self, mode, filename, blocks):
        return self.decoder.assert_signal(self.directory / "candidate-output" / mode / filename, blocks)

    def test_create_grow_normal_stop_decode_and_restart(self):
        self.assertGreater(self.results["normal"]["grownLength"], self.results["normal"]["initialLength"])
        self.check_signal("normal", "first.wav", 2)
        self.check_signal("normal", "recovery.wav", 1)

    def test_split_finalizes_both_outputs(self):
        self.check_signal("split", "first.wav", 2)
        self.check_signal("split", "split.wav", 1)
        self.check_signal("split", "recovery.wav", 1)

    def test_destructor_finalizes_actual_encoder(self):
        self.check_signal("destructor", "first.wav", 1)

    def test_failed_write_reports_stops_and_recovers(self):
        result = self.results["write-failure"]
        self.assertEqual(result["failureStatus"], 0)
        self.assertEqual(result["failureNotifications"][-1], {"recording": False, "error": True})
        self.check_signal("write-failure", "recovery.wav", 1)

    def test_final_header_write_failure_reports_and_recovers(self):
        result = self.results["stop-failure"]
        self.assertEqual(result["stopNotifications"][-1], {"recording": False, "error": True})
        self.check_signal("stop-failure", "recovery.wav", 1)

    def test_invalid_destination_recovers(self):
        self.assertEqual(self.results["invalid-destination"]["initialStatus"], 0)
        self.check_signal("invalid-destination", "recovery.wav", 1)

    def test_failed_seek_is_not_reported_as_success(self):
        result = self.results["seek-failure"]
        self.assertEqual(result["failureStatus"], 0)
        self.assertEqual(result["stopNotifications"][-1], {"recording": False, "error": True})
        self.check_signal("seek-failure", "recovery.wav", 1)

    def test_split_must_not_hide_preceding_finalization_failure(self):
        result = self.results["split-stop-failure"]
        self.assertEqual(result["failureStatus"], 0)
        self.assertEqual(result["stopNotifications"][-1], {"recording": False, "error": True})
        self.assertEqual(sum(item["recording"] for item in result["stopNotifications"]), 1)
        self.assertFalse((self.directory / "candidate-output/split-stop-failure/failed-split.wav").exists())
        self.check_signal("split-stop-failure", "recovery.wav", 1)


if __name__ == "__main__":
    unittest.main()
