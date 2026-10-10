"""Opt-in PipeWire signal check with private sockets and virtual hardware only.

MIXPI_AUDIO_INTEGRATION=1 python3 -m unittest discover -s tests -p test_speaker_audio.py
Requires Linux, PipeWire/Pulse, WirePlumber, D-Bus and swh-plugins.
"""
import array
import concurrent.futures
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.environ.get("MIXPI_AUDIO_INTEGRATION") == "1", "Opt-in isolated PipeWire test")
class SpeakerAudioTests(unittest.TestCase):
    def test_stereo_delay_and_reset_with_automatic_compensation(self):
        loader = importlib.machinery.SourceFileLoader("audio_control", str(ROOT / "stage3/02-desktop/files/bin/mixpi-speaker-control"))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        control = importlib.util.module_from_spec(spec)
        loader.exec_module(control)
        with tempfile.TemporaryDirectory(prefix="mixpi-delay-test-") as directory:
            runtime = Path(directory)
            config = runtime / "config/wireplumber/wireplumber.conf.d"
            config.mkdir(parents=True)
            (config / "disable-hardware.conf").write_text("wireplumber.profiles = { main = { monitor.alsa = disabled monitor.bluez = disabled monitor.v4l2 = disabled monitor.libcamera = disabled } }")
            env = dict(XDG_RUNTIME_DIR=directory, PIPEWIRE_RUNTIME_DIR=directory,
                       PULSE_RUNTIME_PATH=directory + "/pulse", PULSE_SERVER="unix:" + directory + "/pulse/native",
                       XDG_CONFIG_HOME=str(runtime / "config"), XDG_STATE_HOME=str(runtime / "state"),
                       XDG_CACHE_HOME=str(runtime / "cache"))
            with patch.dict(os.environ, env):
                processes = []
                def launch(args):
                    log = (runtime / (args[0] + ".log")).open("w")
                    process = subprocess.Popen(args, stdout=log, stderr=log)
                    log.close()
                    processes.append(process)
                def wait_socket(path):
                    deadline = time.monotonic() + 8
                    while not path.exists():
                        if time.monotonic() > deadline:
                            self.fail("Missing private socket: " + str(path))
                        time.sleep(.1)
                try:
                    launch(["pipewire"])
                    wait_socket(runtime / "pipewire-0")
                    launch(["pipewire-pulse"])
                    wait_socket(runtime / "pulse/native")
                    launch(["dbus-run-session", "--", "wireplumber"])
                    time.sleep(1)
                    control.STATE = runtime / "speaker.json"
                    raw = "test_output"
                    control.run("pactl", "load-module", "module-null-sink", "sink_name=" + raw,
                                "rate=48000", "channels=2", "channel_map=front-left,front-right")
                    main, headphones = raw, "test_other_output"
                    control.run("pactl", "load-module", "module-remap-sink", "sink_name=" + headphones,
                                "master=" + raw, "channels=2", "channel_map=front-left,front-right",
                                "master_channel_map=front-left,front-right", "remix=no")
                    for name in (main, headphones):
                        control.run("pactl", "set-sink-volume", name, "100%")
                    def measure(ms):
                        target = control.choose_outputs([main, headphones], delays={headphones: ms})
                        time.sleep(.3)
                        sinks = control.outputs()
                        self.assertEqual(set(control.selected_outputs(sinks)), {main, headphones}, [(s["name"], s.get("properties")) for s in sinks])
                        self.assertEqual(control.current_delays(sinks)[headphones], ms)
                        self.assertEqual(control.choose_outputs([main, headphones]), target)
                        streams = json.loads(control.run("pactl", "--format=json", "list", "sink-inputs"))
                        self.assertTrue(all(str(s["properties"].get("node.virtual")).lower() == "true" for s in streams), streams)
                        # Mix reference and delayed paths on one recording clock.
                        # Each input pulse becomes two pulses separated by the
                        # requested delay. Offset L/R pulses detect mono mixing.
                        audio = array.array("f", [0.0]) * (48000 * 5 * 2)
                        for start in (48000, 96000, 144000, 192000):
                            for i in range(4):
                                audio[(start + i) * 2] = .2
                                audio[(start + 4800 + i) * 2 + 1] = .15
                        reader = subprocess.Popen(["parecord", "--raw", "--format=float32le", "--rate=48000", "--channels=2",
                                                   "--channel-map=front-left,front-right", "--device=" + raw + ".monitor"],
                                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        try:
                            with concurrent.futures.ThreadPoolExecutor() as pool:
                                def capture():
                                    try:
                                        return reader.communicate(timeout=7)[0]
                                    except subprocess.TimeoutExpired:
                                        reader.terminate()
                                        return reader.communicate(timeout=3)[0]
                                captured = pool.submit(capture)
                                time.sleep(.3)
                                subprocess.run(["pacat", "--raw", "--format=float32le", "--rate=48000", "--channels=2", "--device=" + target],
                                               input=audio.tobytes(), check=True, timeout=10)
                                samples = array.array("f")
                                samples.frombytes(captured.result())
                        finally:
                            if reader.poll() is None:
                                reader.kill()
                                reader.wait()
                        edges = []
                        for channel in range(2):
                            values = samples[channel::2]
                            peaks = [i for i in range(1, len(values)) if values[i] > .07 and values[i-1] <= .07]
                            peaks = [v for i, v in enumerate(peaks) if i == 0 or v - peaks[i-1] > 24]
                            self.assertGreaterEqual(len(peaks), 3, (ms, channel, peaks))
                            edges.append(peaks)
                        if ms:
                            for peaks in edges:
                                self.assertGreaterEqual(len(peaks), 6, (ms, peaks))
                                self.assertEqual(len(peaks) % 2, 0, (ms, peaks))
                            measured = [[(b-a)/48 for a,b in zip(peaks[::2], peaks[1::2])] for peaks in edges]
                        else:
                            measured = [[0], [0]]
                        print("Measured manual delay (ms), requested", ms, ":", measured, flush=True)
                        for values in measured:
                            for actual in values:
                                self.assertAlmostEqual(actual, ms, delta=1.0)
                        for left, right in zip(edges[0], edges[1]):
                            self.assertAlmostEqual((right-left)/48, 100, delta=1.0)
                    for ms in (0, 50, 1, 500, 0):
                        measure(ms)
                    self.assertFalse(any(s["name"].startswith(control.DELAY_PREFIX) for s in control.outputs()))
                finally:
                    for process in reversed(processes):
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()


if __name__ == "__main__":
    unittest.main()
