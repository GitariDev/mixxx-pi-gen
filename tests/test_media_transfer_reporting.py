"""Portable production reporting/state fixtures; not Linux peer-pidfd IPC evidence."""
import importlib.machinery
import importlib.util
import array
import math
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from media_copy_fakes import ScratchAdmission
from native.library_interface_runner import reconstruct


ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader("media_reporting_test", str(ROOT / "stage3/02-desktop/files/bin/mixpi-media"))
spec = importlib.util.spec_from_loader(loader.name, loader)
media = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = media
loader.exec_module(media)


class ReportingAdmission(media.CopyAdmission):
    instances = []
    fail_on = None
    response_override = None

    def __init__(self, paths):
        super().__init__(paths)
        self.proofs = ScratchAdmission(paths).proofs
        self.messages = []
        self.closed = False
        self.__class__.instances.append(self)

    def __enter__(self):
        self.active = True
        self.previous = getattr(media._admission, "current", None)
        self.worker = threading.Thread(target=self.stopped.wait)
        self.worker.start()
        return self

    def exchange(self, message):
        self.messages.append(message)
        if self.fail_on and message.startswith(self.fail_on):
            raise media.TransferError("report transport failed")
        if self.response_override is not None and message.startswith("TRANSFER"):
            return self.response_override
        return "OK\nTRANSFER:1" if message == "TRANSFER_BEGIN\n1" else "OK"

    def close(self):
        self.closed = True


class TransferReportingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="transfer-report-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.source, self.destination, self.state = (self.root / name for name in ("source", "destination", "state"))
        self.source.mkdir()
        self.destination.mkdir()
        (self.source / "track.wav").write_bytes(b"audio" * 300000)
        ReportingAdmission.instances = []
        ReportingAdmission.fail_on = None
        ReportingAdmission.response_override = None
        admission = patch.object(media, "CopyAdmission", ReportingAdmission)
        admission.start()
        self.addCleanup(admission.stop)

    def plan(self):
        return media.make_plan(self.source, "USB", "fixture", self.destination,
                               self.destination, self.state, reserve=0)

    def reports(self, admission=None):
        admission = admission or ReportingAdmission.instances[-1]
        return [message for message in admission.messages if message.startswith("TRANSFER")]

    def test_planning_and_lists_are_not_transfer_jobs(self):
        self.plan()
        media.list_recordings(self.source)
        for admission in ReportingAdmission.instances:
            self.assertEqual(self.reports(admission), [])

    def test_actual_copy_then_existing_backup_verification(self):
        plan = self.plan()
        published = []
        original = media.atomic_publish

        def publish(*args):
            self.assertNotIn("TRANSFER_END\nverified", self.reports())
            published.append(True)
            return original(*args)

        with patch.object(media, "atomic_publish", side_effect=publish):
            self.assertEqual(media.copy_plan(plan)["status"], "copied")
        self.assertTrue(published)
        reports = self.reports()
        self.assertEqual(reports[0], "TRANSFER_BEGIN\n1")
        self.assertTrue(any(message.startswith("TRANSFER\ncopying\n") for message in reports))
        self.assertTrue(any(message.startswith("TRANSFER\nverifying\n") for message in reports))
        self.assertEqual(reports[-1], "TRANSFER_END\nverified")
        values = [int(message.splitlines()[2]) for message in reports if message.startswith("TRANSFER\n")]
        self.assertEqual(values, sorted(values))
        self.assertTrue(all(0 <= value <= 99 for value in values))
        self.assertEqual(media.copy_plan(plan)["status"], "already_copied")
        self.assertFalse(any(message.startswith("TRANSFER\ncopying\n") for message in self.reports()))
        self.assertEqual(self.reports()[-1], "TRANSFER_END\nverified")

    def test_cancel_is_not_failure_or_verification(self):
        plan = self.plan()
        cancel = threading.Event()

        def cancel_copy(fraction, message):
            cancel.set()

        with self.assertRaises(media.Cancelled):
            media.copy_plan(plan, cancel, cancel_copy)
        self.assertEqual(self.reports()[-1], "TRANSFER_END\ncancelled")
        self.assertFalse(plan.destination.exists())
        self.assertTrue((self.source / "track.wav").exists())

    def test_publish_failure_stays_failed(self):
        plan = self.plan()
        with patch.object(media, "atomic_publish", side_effect=OSError("publish failed")):
            with self.assertRaisesRegex(OSError, "publish failed"):
                media.copy_plan(plan)
        self.assertEqual(self.reports()[-1], "TRANSFER_END\nfailed")
        self.assertNotIn("TRANSFER_END\nverified", self.reports())

    def test_report_failure_does_not_mask_original_or_release_admission(self):
        plan = self.plan()
        ReportingAdmission.fail_on = "TRANSFER_END\nfailed"
        with patch.object(media, "atomic_publish", side_effect=OSError("original failure")):
            with self.assertRaisesRegex(OSError, "original failure"):
                media.copy_plan(plan)
        admission = ReportingAdmission.instances[-1]
        self.assertNotIn("CANCEL", admission.messages)
        self.assertNotIn("FINISH", admission.messages)
        self.assertTrue(admission.closed)
        self.assertTrue(admission.report_broken)

    def test_old_server_or_invalid_ack_never_enters_transfer_body(self):
        plan = self.plan()
        for response in ("OK", "OK\nTRANSFER:0", "OK\nTRANSFER:1\nextra"):
            with self.subTest(response=response):
                ReportingAdmission.response_override = response
                with patch.object(media, "_copy_plan") as body:
                    with self.assertRaises(media.TransferError):
                        media.copy_plan(plan)
                    body.assert_not_called()
                self.assertNotIn("FINISH", ReportingAdmission.instances[-1].messages)
                self.assertNotIn("CANCEL", ReportingAdmission.instances[-1].messages)

    def test_mid_copy_reporting_failure_stops_without_publication(self):
        plan = self.plan()
        ReportingAdmission.fail_on = "TRANSFER\ncopying"
        with self.assertRaisesRegex(media.TransferError, "report transport failed"):
            media.copy_plan(plan)
        self.assertFalse(plan.destination.exists())
        self.assertEqual(list((self.state / "staging").iterdir()), [])
        self.assertNotIn("TRANSFER_END\nverified", self.reports())

    def test_hash_corruption_is_failed_not_verified(self):
        plan = self.plan()
        with patch.object(media, "hash_file", side_effect=lambda *args, **kwargs: "wrong"):
            with self.assertRaisesRegex(media.TransferError, "verification"):
                media.copy_plan(plan)
        self.assertEqual(self.reports()[-1], "TRANSFER_END\nfailed")
        self.assertFalse(plan.destination.exists())

    def test_invalid_and_regressing_callback_progress_is_rejected(self):
        admission = ReportingAdmission([("R", self.source)])
        reporter = media.TransferProgress(admission, lambda *args: None)
        reporter.update("copying", 0.5, "copied")
        before = list(admission.messages)
        for value in (-1, 0.49, 1.01, math.nan, math.inf, True, "1"):
            with self.subTest(value=value), self.assertRaises(media.TransferError):
                reporter.update("verifying", value, "bad")
        with self.assertRaises(media.TransferError):
            reporter.update("invented", 0.5, "bad phase")
        self.assertEqual(admission.messages, before)
        reporter.update("verifying", 1, "complete")
        self.assertEqual(admission.messages[-1], "TRANSFER\nverifying\n99")
        self.assertNotIn("TRANSFER_END\nverified", admission.messages)

    def recordings(self):
        folder, usb = self.root / "recordings", self.root / "usb"
        folder.mkdir()
        usb.mkdir()
        name = "2026-11-12_14h00m00s.wav"
        (folder / name).write_bytes(b"recorded" * 100000)
        os.utime(folder / name, (1700000000, 1700000000))
        recordings = media.list_recordings(folder)
        self.assertTrue(recordings)
        target = media.usb_target({"source": str(usb), "fstype": "vfat"})
        return folder, usb, name, recordings, target

    def test_actual_recording_move_verifies_before_deletion(self):
        folder, usb, name, recordings, target = self.recordings()
        original_unlink = os.unlink
        observed = []

        def unlink(path, *args, **kwargs):
            if path == name and "dir_fd" in kwargs:
                reports = self.reports()
                self.assertTrue(any(message.startswith("TRANSFER\nverifying\n") for message in reports))
                self.assertNotIn("TRANSFER_END\nverified", reports)
                self.assertEqual((usb / media.RECORDINGS_FOLDER / name).read_bytes(), (folder / name).read_bytes())
                observed.append(True)
            return original_unlink(path, *args, **kwargs)

        with patch.object(media.os, "unlink", side_effect=unlink):
            self.assertEqual(media.move_recordings(folder, recordings, target, self.state)["status"], "moved")
        self.assertTrue(observed)
        self.assertFalse((folder / name).exists())
        self.assertEqual(self.reports()[-1], "TRANSFER_END\nverified")

    def test_recording_verification_reporting_failure_preserves_source(self):
        folder, usb, name, recordings, target = self.recordings()
        ReportingAdmission.fail_on = "TRANSFER\nverifying"
        with self.assertRaises(media.TransferError):
            media.move_recordings(folder, recordings, target, self.state)
        self.assertTrue((folder / name).exists())
        self.assertFalse((usb / media.RECORDINGS_FOLDER / name).exists())
        self.assertNotIn("TRANSFER_END\nverified", self.reports())

    def test_recording_hash_failure_reports_failed_and_preserves_source(self):
        folder, usb, name, recordings, target = self.recordings()
        with patch.object(media, "hash_file", return_value="corrupt"):
            with self.assertRaisesRegex(media.TransferError, "verification"):
                media.move_recordings(folder, recordings, target, self.state)
        self.assertTrue((folder / name).exists())
        self.assertFalse((usb / media.RECORDINGS_FOLDER / name).exists())
        self.assertEqual(self.reports()[-1], "TRANSFER_END\nfailed")

    def test_recording_cancel_reports_cancelled_and_preserves_source(self):
        folder, usb, name, recordings, target = self.recordings()
        cancel = threading.Event()
        with self.assertRaises(media.Cancelled):
            media.move_recordings(folder, recordings, target, self.state, cancel,
                                  lambda fraction, message: cancel.set())
        self.assertTrue((folder / name).exists())
        self.assertFalse((usb / media.RECORDINGS_FOLDER / name).exists())
        self.assertEqual(self.reports()[-1], "TRANSFER_END\ncancelled")

    def test_existing_recording_copy_is_verified_before_source_removal(self):
        folder, usb, name, recordings, target = self.recordings()
        destination = usb / media.RECORDINGS_FOLDER
        destination.mkdir()
        (destination / name).write_bytes((folder / name).read_bytes())
        self.assertEqual(media.move_recordings(folder, recordings, target, self.state)["status"], "moved")
        reports = self.reports()
        self.assertFalse(any(message.startswith("TRANSFER\ncopying\n") for message in reports))
        self.assertEqual(reports[-1], "TRANSFER_END\nverified")
        self.assertFalse((folder / name).exists())

    def test_cancel_reporting_failure_preserves_original_cancel_exception(self):
        plan = self.plan()
        cancel = threading.Event()
        cancel.set()
        ReportingAdmission.fail_on = "TRANSFER_END\ncancelled"
        with self.assertRaises(media.Cancelled):
            media.copy_plan(plan, cancel)
        self.assertNotIn("CANCEL", ReportingAdmission.instances[-1].messages)
        self.assertFalse(plan.destination.exists())


@unittest.skipUnless(shutil.which("c++"), "C++ compiler required")
class NativeTransferStateTests(unittest.TestCase):
    def test_portable_production_state_and_extracted_request(self):
        with tempfile.TemporaryDirectory(prefix="mixpi-transfer-native-") as temporary:
            target = Path(temporary)
            reconstruct(target, exclude=('mixxx-transfer-reporting.patch',)
                        if os.environ.get("TRANSFER_REPORTING_BASELINE") else ())
            header = (target / "src/library/media/copyservice.h").read_text()
            structs = header.split("    struct Path {", 1)[1].split("    static bool exited(", 1)[0]
            hex_method = header.split("    static std::string hex(", 1)[1].split("    std::string request(", 1)[0]
            request = header.split("    std::string request(", 1)[1].split("    std::string m_directory;", 1)[0]
            snapshot = header.split("    TransferSnapshot transferStatus(", 1)[1].split("    void tick()", 1)[0] if "TransferSnapshot transferStatus(" in header else ""
            source = (ROOT / "tests/native/media_transfer_test.cpp.in").read_text()
            source = source.replace("@CLIENT_STRUCTS@", "struct Path {" + structs)
            source = source.replace("@PRODUCTION_HEX@", "static std::string hex(" + hex_method)
            source = source.replace("@PRODUCTION_REQUEST@", "std::string request(" + request)
            source = source.replace("@PRODUCTION_SNAPSHOT@", "TransferSnapshot transferStatus(" + snapshot if snapshot else "")
            unit, executable = target / "test.cpp", target / "test"
            unit.write_text(source)
            command = ["c++", "-std=c++17", "-pthread", "-Wall", "-Wextra", "-Werror",
                       "-I" + str(target / "src"), str(unit), "-o", str(executable)]
            subprocess.run(command, check=True, timeout=60)
            subprocess.run([str(executable)], check=True, timeout=10)


@unittest.skipUnless(sys.platform.startswith("linux") and shutil.which("c++"),
                     "Linux peer-pidfd kernel required; portable fixtures are not Linux IPC")
class LinuxTransferReportingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory(prefix="mixpi-transfer-ipc-")
        target = Path(cls.build.name)
        cls.addClassCleanup(cls.build.cleanup)
        reconstruct(target)
        (target / "src/library/media/mediause.h").write_text(
            '#include "mediauseregistry.h"\n#include <filesystem>\n#include <fstream>\n'
            '#include <sstream>\n#include <fcntl.h>\n#include <sys/stat.h>\n#include <unistd.h>\n'
            'namespace mixxx::media { inline Binding observePath(const std::string&) { return {}; } }\n')
        cls.executable = target / "server"
        subprocess.run(["c++", "-std=c++17", "-pthread", "-Wall", "-Wextra", "-Werror",
                        "-I" + str(target / "src"), str(ROOT / "tests/native/media_transfer_server.cpp"),
                        "-o", str(cls.executable)], check=True, timeout=60)

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="mixpi-transfer-peer-")
        self.root = Path(self.temporary.name).resolve()
        for name in ("source", "destination"):
            (self.root / name).mkdir()
        self.server = subprocess.Popen([str(self.executable), str(self.root)], stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, text=True)
        self.assertEqual(self.server.stdout.readline().strip(), "READY")

    def tearDown(self):
        self.server.stdin.close()
        self.server.wait(timeout=5)
        self.server.stdout.close()
        self.temporary.cleanup()

    def control(self, command):
        self.server.stdin.write(command + "\n")
        self.server.stdin.flush()
        return self.server.stdout.readline().strip()

    def snapshot(self, generation="A", source="A-source"):
        return tuple(map(int, self.control(f"transfer {generation} {source}").split()))

    def request(self, client, message):
        client.sendall(message.encode())
        return client.recv(16384).decode()

    def connect(self):
        client = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        self.addCleanup(client.close)
        client.settimeout(3)
        client.connect(str(self.root / "ipc/control"))
        if os.getuid() == 0:
            descriptor = os.open("/proc/self/ns/mnt", os.O_RDONLY)
            try:
                client.sendmsg([b"NAMESPACE"], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array("i", [descriptor]))])
                self.assertEqual(client.recv(16384), b"OK")
            finally:
                os.close(descriptor)
        return client

    def begin(self, client):
        self.assertTrue(self.request(client, "BEGIN\nR" + str(self.root / "source")).startswith("OK\n"))
        self.assertEqual(self.request(client, "TRANSFER_BEGIN\n1"), "OK\nTRANSFER:1")

    def wait_snapshot(self, expected):
        deadline = time.monotonic() + 2
        while True:
            result = self.snapshot()
            if result[3] == expected:
                return result
            self.assertLess(time.monotonic(), deadline, result)
            time.sleep(0.01)

    def test_real_transport_verified_progress_and_explicit_release(self):
        client = self.connect()
        self.begin(client)
        self.assertEqual(self.request(client, "TRANSFER\ncopying\n30"), "OK")
        self.assertEqual(self.snapshot(), (1, 1, 1, 1, 30, 1))
        self.assertEqual(self.control("drain A"), "BUSY")
        self.assertEqual(self.request(client, "TRANSFER\nverifying\n99"), "OK")
        self.assertEqual(self.request(client, "TRANSFER_END\nverified"), "OK")
        self.assertEqual(self.snapshot(), (1, 1, 2, 2, 100, 0))
        self.assertEqual(self.control("status A"), "BUSY")
        self.assertEqual(self.request(client, "FINISH"), "OK")
        self.assertEqual(self.control("status A"), "IDLE")

    def test_real_malformed_progress_disconnect_remains_busy(self):
        client = self.connect()
        self.begin(client)
        self.assertEqual(self.request(client, "TRANSFER\ncopying\n30"), "OK")
        self.assertEqual(self.request(client, "TRANSFER\ncopying\n29"), "DENIED")
        snapshot = self.wait_snapshot(5)
        self.assertEqual(snapshot, (1, 0, 1, 5, 30, 0))
        self.assertEqual(self.control("drain A"), "BUSY")

    def test_real_replacement_cannot_receive_old_job_reports(self):
        client = self.connect()
        self.begin(client)
        (self.root / "revision").write_text("new")
        self.assertEqual(self.request(client, "TRANSFER\nverifying\n99"), "DENIED")
        self.wait_snapshot(5)
        self.assertEqual(self.snapshot("Anew", "A-sourcenew"), (0, 0, 0, 0, 0, 0))
        self.assertEqual(self.control("drain A"), "BUSY")

    def test_real_worker_disconnect_and_exit_do_not_invent_success(self):
        script = '''import array,os,socket,sys
root=sys.argv[1]
client=socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET)
client.connect(root+'/ipc/control')
if os.getuid()==0:
 descriptor=os.open('/proc/self/ns/mnt',os.O_RDONLY)
 client.sendmsg([b'NAMESPACE'],[(socket.SOL_SOCKET,socket.SCM_RIGHTS,array.array('i',[descriptor]))])
 assert client.recv(16384)==b'OK'
 os.close(descriptor)
for request in ('BEGIN\\nR'+root+'/source','TRANSFER_BEGIN\\n1','TRANSFER\\ncopying\\n25'):
 client.sendall(request.encode())
 assert client.recv(16384).startswith(b'OK')
client.close()
print('DISCONNECTED',flush=True)
sys.stdin.read()
'''
        child = subprocess.Popen([sys.executable, "-c", script, str(self.root)], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(), "DISCONNECTED")
            self.assertEqual(self.wait_snapshot(5), (1, 0, 1, 5, 25, 0))
            self.assertEqual(self.control("drain A"), "BUSY")
        finally:
            child.stdin.close()
            child.wait(timeout=5)
            child.stdout.close()
        deadline = time.monotonic() + 2
        while self.control("status A") != "IDLE":
            self.assertLess(time.monotonic(), deadline)
            time.sleep(0.01)
        self.assertEqual(self.snapshot()[3], 5)


if __name__ == "__main__":
    unittest.main()
