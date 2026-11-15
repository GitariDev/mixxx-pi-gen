import importlib.machinery
import importlib.util
import fcntl
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from media_copy_fakes import ScratchAdmission
from native.library_interface_runner import reconstruct
from test_media_identity import added_header
from test_media_ownership import PATCH, ROOT


loader = importlib.machinery.SourceFileLoader("media_ipc_test", str(ROOT / "stage3/02-desktop/files/bin/mixpi-media"))
spec = importlib.util.spec_from_loader(loader.name, loader)
media = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = media
loader.exec_module(media)


class CopyAdmissionTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("c++"), "C++ required")
    def test_only_kernel_exit_readiness_releases_orphan(self):
        header = added_header(PATCH, "src/library/media/copyservice.h")
        method = "static bool exited(" + header.split("static bool exited(", 1)[1].split("    int secureFile(", 1)[0]
        source = '''#include <poll.h>
#include <cassert>
int result = 0;
short readiness = 0;
int fixturePoll(pollfd* descriptor, int, int) { descriptor->revents = readiness; return result; }
#define poll fixturePoll
''' + method + '''
int main() {
    result = -1; assert(!exited(7));
    result = 0; assert(!exited(7));
    result = 1; readiness = POLLNVAL; assert(!exited(7));
    readiness = POLLHUP; assert(!exited(7));
    readiness = POLLIN; assert(exited(7));
    assert(!exited(-1));
}
'''
        with tempfile.TemporaryDirectory() as directory:
            unit = Path(directory) / "exit.cpp"
            unit.write_text(source)
            executable = Path(directory) / "exit"
            subprocess.run(["c++", "-std=c++17", "-Wall", "-Werror", str(unit), "-o", str(executable)], check=True)
            subprocess.run([str(executable)], check=True)

    def test_service_unavailable_never_plans_or_writes(self):
        with patch.object(media.socket, "socket", side_effect=OSError("unavailable")), \
                patch.object(media, "_make_plan") as body:
            with self.assertRaises(media.TransferError):
                media.make_plan("/no/source", "USB", "id")
            body.assert_not_called()

    def test_production_bodies_inside_lease_including_exception_cleanup(self):
        active = []
        class Admission(ScratchAdmission):
            def __enter__(self):
                active.append(self.paths)
                return self
            def __exit__(self, *error):
                active.pop()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source, destination, state = root / "source", root / "destination", root / "state"
            source.mkdir()
            destination.mkdir()
            (source / "track.wav").write_bytes(b"music" * 100)
            original_inventory = media.inventory
            def inventory(*args, **kwargs):
                self.assertTrue(active)
                return original_inventory(*args, **kwargs)
            original_cleanup = media.shutil.rmtree
            def cleanup(*args, **kwargs):
                self.assertTrue(active)
                return original_cleanup(*args, **kwargs)
            with patch.object(media, "CopyAdmission", Admission), patch.object(media, "inventory", inventory):
                plan = media.make_plan(source, "USB", "id", destination, destination, state, reserve=0)
                self.assertFalse(active)
                with patch.object(media.shutil, "rmtree", cleanup), patch.object(media, "atomic_publish", side_effect=OSError("test")):
                    with self.assertRaises(OSError):
                        media.copy_plan(plan)
                self.assertFalse(active)
                self.assertEqual((source / "track.wav").read_bytes(), b"music" * 100)
                self.assertFalse(list((state / "staging").iterdir()))
                self.assertEqual(media.copy_plan(plan)["status"], "copied")

    def test_generation_change_rejected_before_copy_body(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(media, "CopyAdmission", ScratchAdmission):
                plan = type("Plan", (), {"admission_paths": [("R", temporary)], "admission_proofs": ["stale"]})()
                with patch.object(media, "_copy_plan") as body:
                    with self.assertRaises(media.TransferError):
                        media.copy_plan(plan)
                    body.assert_not_called()


@unittest.skipUnless(sys.platform.startswith("linux") and shutil.which("c++"), "Linux peer-pidfd kernel and C++ required")
class NativeCopyIPC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory(prefix="copy-native-")
        root = Path(cls.build.name)
        include = root / "library/media"
        include.mkdir(parents=True)
        source = root / "source"
        source.mkdir()
        reconstruct(source)
        shutil.copytree(source / "src/library/media", include, dirs_exist_ok=True)
        (include / "mediause.h").write_text('#include "mediauseregistry.h"\n#include <filesystem>\n#include <fstream>\n#include <sstream>\n#include <fcntl.h>\n#include <sys/stat.h>\n#include <unistd.h>\nnamespace mixxx::media { inline Binding observePath(const std::string&) { return {}; } }\n')
        cls.executable = root / "server"
        subprocess.run(["c++", "-std=c++17", "-pthread", "-Wall", "-Wextra", "-Werror", "-I" + str(root),
                        str(ROOT / "tests/native/media_copy_server.cpp"), "-o", str(cls.executable)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="copy-process-")
        self.root = Path(self.temporary.name)
        for name in ("source", "destination", "other"):
            (self.root / name).mkdir()
        self.server = subprocess.Popen([str(self.executable), str(self.root)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        self.assertEqual(self.server.stdout.readline().strip(), "READY")

    def tearDown(self):
        self.server.stdin.close()
        self.server.wait(timeout=5)
        self.server.stdout.close()
        self.temporary.cleanup()

    def control(self, command, generation):
        self.server.stdin.write(command + " " + generation + "\n")
        self.server.stdin.flush()
        return self.server.stdout.readline().strip()

    def connect(self):
        client = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        client.settimeout(3)
        client.connect(str(self.root / "ipc/control"))
        self.addCleanup(client.close)
        return client

    def request(self, client, message):
        client.send(message.encode())
        return client.recv(16384).decode()

    def begin(self, client):
        return self.request(client, f"BEGIN\nR{self.root}/source\nW{self.root}/destination/new/subfolder")

    def test_two_generations_finish_and_unrelated_selection(self):
        client = self.connect()
        response = self.begin(client)
        self.assertTrue(response.startswith("OK\n"), response)
        self.assertNotEqual(*response.splitlines()[1:])
        self.assertEqual(self.control("drain", "A"), "BUSY")
        self.assertEqual(self.control("drain", "B"), "BUSY")
        self.assertEqual(self.control("drain", "C"), "IDLE")
        self.assertEqual(self.request(client, "CHECK"), "OK")
        self.assertEqual(self.request(client, "FINISH"), "OK")
        self.assertEqual(self.control("status", "A"), "IDLE")
        self.assertEqual(self.control("status", "B"), "IDLE")

    def test_drain_before_begin_and_malformed(self):
        self.assertEqual(self.control("drain", "A"), "IDLE")
        self.assertEqual(self.begin(self.connect()), "DENIED")
        self.assertEqual(self.control("status", "B"), "BUSY")
        for payload in ("FINISH", "BEGIN\n", "BEGIN\nR/../etc", "BEGIN\nR/etc", "BEGIN\nX" + str(self.root)):
            self.assertEqual(self.request(self.connect(), payload), "DENIED")

    def test_replacement_and_disconnect_keep_guard_while_process_alive(self):
        client = self.connect()
        self.assertTrue(self.begin(client).startswith("OK\n"))
        (self.root / "revision").write_text("replacement")
        self.assertEqual(self.request(client, "CHECK"), "DENIED")
        client.close()
        self.assertEqual(self.control("drain", "A"), "BUSY")
        self.assertEqual(self.control("drain", "B"), "BUSY")

    def test_confirmed_child_exit_releases_orphan_and_new_session_cannot_finish_it(self):
        script = "import socket,sys; s=socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET); s.connect(sys.argv[1]+'/ipc/control'); s.send(('BEGIN\\nR'+sys.argv[1]+'/source').encode()); print(s.recv(16384).decode().splitlines()[0],flush=True); s.close(); sys.stdin.read()"
        child = subprocess.Popen([sys.executable, "-c", script, str(self.root)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(), "OK")
            self.assertEqual(self.control("drain", "A"), "BUSY")
            self.assertEqual(self.request(self.connect(), "FINISH"), "DENIED")
            self.assertEqual(self.control("status", "A"), "BUSY")
        finally:
            child.stdin.close()
            child.wait(timeout=5)
            child.stdout.close()
        deadline = time.monotonic() + 2
        while self.control("status", "A") != "IDLE":
            self.assertLess(time.monotonic(), deadline)
            time.sleep(0.01)

    def test_symlink_unknown_and_cancel(self):
        (self.root / "link").symlink_to(self.root / "source")
        self.assertEqual(self.request(self.connect(), f"BEGIN\nR{self.root}/link"), "DENIED")
        (self.root / "revision").write_text("unknown")
        self.assertEqual(self.begin(self.connect()), "DENIED")
        (self.root / "revision").unlink()
        client = self.connect()
        self.assertTrue(self.begin(client).startswith("OK\n"))
        self.assertEqual(self.request(client, "CANCEL"), "OK")
        self.assertEqual(self.control("drain", "A"), "IDLE")

    def test_descendant_cross_generation_is_not_covered_by_parent_lease(self):
        client = self.connect()
        self.assertTrue(self.begin(client).startswith("OK\n"))
        nested = self.root / "source/other"
        nested.mkdir()
        self.assertEqual(self.request(client, "CHECK\n" + str(nested)), "DENIED")
        self.assertEqual(self.control("drain", "A"), "BUSY")

    def test_actual_copy_and_move_bodies_with_authenticated_transport(self):
        source, destination = self.root / "source", self.root / "destination"
        audio = source / "recording.wav"
        audio.write_bytes(b"audio" * 10000)
        admission_class = media.CopyAdmission
        def admission(paths):
            return admission_class(paths, self.root / "ipc")
        with patch.object(media, "CopyAdmission", admission):
            plan = media.make_plan(source, "fixture", "fixture", destination, destination, self.root / "state", reserve=0)
            self.assertEqual(media.copy_plan(plan)["status"], "copied")
            self.assertEqual((plan.destination / audio.name).read_bytes(), audio.read_bytes())
            recordings = media.list_recordings(source, in_use=set())
            target = media.usb_target({"source": str(destination), "fstype": "ext4"})
            self.assertEqual(media.move_recordings(source, recordings, target, self.root / "state")["status"], "moved")
            self.assertFalse(audio.exists())
            self.assertEqual((destination / media.RECORDINGS_FOLDER / audio.name).read_bytes(), b"audio" * 10000)
        self.assertEqual(self.control("drain", "A"), "IDLE")
        self.assertEqual(self.control("drain", "B"), "IDLE")

    def test_admitted_recordings_move_finishes_after_destination_drain(self):
        source, destination = self.root / "source", self.root / "destination"
        audio = source / "recording.wav"
        content = b"admitted recording" * 10000
        audio.write_bytes(content)
        admission_class = media.CopyAdmission
        move_body = media._move_recordings

        def admission(paths):
            return admission_class(paths, self.root / "ipc")

        def drain_then_move(*args, **kwargs):
            self.assertEqual(self.control("drain", "B"), "BUSY")
            return move_body(*args, **kwargs)

        with patch.object(media, "CopyAdmission", admission):
            recordings = media.list_recordings(source, in_use=set())
            target = media.usb_target({"source": str(destination), "fstype": "ext4"})
            with patch.object(media, "_move_recordings", side_effect=drain_then_move):
                result = media.move_recordings(source, recordings, target, self.root / "state")
            self.assertEqual(result["status"], "moved")
            self.assertFalse(audio.exists())
            self.assertEqual((destination / media.RECORDINGS_FOLDER / audio.name).read_bytes(), content)
        self.assertEqual(self.control("status", "B"), "IDLE")
        self.assertEqual(self.control("drain", "A"), "IDLE")

    def test_real_client_normal_finish_and_service_loss_terminates_helper(self):
        script = "import sys,time; sys.path.insert(0,sys.argv[1]); from test_media_copy_ipc import media; root=sys.argv[2]; lease=media.CopyAdmission([('R',root+'/source'),('W',root+'/destination/new')],root+'/ipc'); lease.__enter__(); print('ACTIVE',flush=True); command=sys.stdin.readline(); lease.__exit__(None,None,None) if command.strip()=='finish' else time.sleep(10)"
        for finish in (True, False):
            child = subprocess.Popen([sys.executable, "-c", script, str(ROOT / "tests"), str(self.root)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
            try:
                self.assertEqual(child.stdout.readline().strip(), "ACTIVE")
                self.assertEqual(self.control("drain", "A"), "BUSY")
                self.control("release", "A")
                if finish:
                    child.stdin.write("finish\n")
                    child.stdin.flush()
                    self.assertEqual(child.wait(timeout=5), 0)
                    self.assertEqual(self.control("drain", "A"), "IDLE")
                    self.control("release", "A")
                else:
                    self.server.terminate()
                    self.server.wait(timeout=5)
                    self.assertEqual(child.wait(timeout=5), 74)
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait(timeout=5)
                child.stdin.close()
                child.stdout.close()

    def test_restart_quarantines_live_old_session_guard(self):
        guard = os.open(self.root / "ipc/sessions.lock", os.O_RDWR)
        try:
            fcntl.flock(guard, fcntl.LOCK_SH)
            self.server.terminate()
            self.server.wait(timeout=5)
            self.server.stdin.close()
            self.server.stdout.close()
            self.server = subprocess.Popen([str(self.executable), str(self.root)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
            self.assertEqual(self.server.stdout.readline().strip(), "READY")
            self.assertEqual(self.control("drain", "A"), "BUSY")
            self.assertEqual(self.begin(self.connect()), "DENIED")
        finally:
            os.close(guard)
        deadline = time.monotonic() + 2
        while self.control("status", "A") != "IDLE":
            self.assertLess(time.monotonic(), deadline)
            time.sleep(0.01)

    def test_foreign_uid_rejected_despite_root_permission_bypass(self):
        if os.getuid() == 0 or not shutil.which("sudo") or subprocess.run(["sudo", "-n", "true"], capture_output=True).returncode:
            self.skipTest("different-UID synthetic process unavailable")
        self.assertEqual((self.root / "ipc").stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.root / "ipc/control").stat().st_mode & 0o777, 0o600)
        script = "import socket,sys; client=socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET); client.settimeout(2); client.connect(sys.argv[1]);\ntry:\n client.send(b'BEGIN\\nR/'); result=client.recv(16384); assert result in (b'', b'DENIED')\nexcept (BrokenPipeError,ConnectionResetError): pass"
        result = subprocess.run(["sudo", "-n", sys.executable, "-c", script, str(self.root / "ipc/control")], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
