"""Speaker handoff failures and routing behavior without Linux audio hardware."""
import importlib.machinery
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader("speaker", str(ROOT / "stage3/02-desktop/files/bin/mixpi-speaker-control"))
spec = importlib.util.spec_from_loader(loader.name, loader)
speaker = importlib.util.module_from_spec(spec)
loader.exec_module(speaker)


class SpeakerTests(unittest.TestCase):
    def test_does_not_close_mixxx_without_explicit_handoff(self):
        with patch.object(speaker, "active", return_value=False), patch.object(speaker, "mixxx_running", return_value=True), patch.object(speaker, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "Mixxx is open"):
                speaker.start()
            run.assert_not_called()

    def test_output_change_moves_music_but_not_channel_remap(self):
        sinks = [{"name": "starlight"}]
        streams = '[{"index": 7, "properties": {"media.class": "Stream/Output/Audio"}}, {"index": 8, "properties": {"media.class": "Stream/Output/Audio", "node.virtual": "true"}}]'
        with patch.object(speaker, "outputs", return_value=sinks), patch.object(speaker, "run", return_value=streams) as run:
            speaker.choose_output("starlight", save=False)
            run.assert_any_call("pactl", "move-sink-input", "7", "starlight", check=False)
            self.assertFalse(any(call.args[:3] == ("pactl", "move-sink-input", "8") for call in run.call_args_list))

    def test_disconnected_output_does_not_change_default(self):
        with patch.object(speaker, "outputs", return_value=[]), patch.object(speaker, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "disconnected"):
                speaker.choose_output("starlight")
            run.assert_not_called()

    def test_starlight_routes_only_front_channels(self):
        sinks = [{"name": "alsa_output.usb_Starlight.surround40", "channel_map": "front-left,front-right,rear-left,rear-right"}]
        with patch.object(speaker, "outputs", return_value=sinks), patch.object(speaker, "run") as run:
            speaker.prepare_outputs()
            remap = run.call_args_list[0].args
            self.assertIn("master_channel_map=front-left,front-right", remap)
            self.assertIn("remix=no", remap)
            self.assertIn("master=alsa_output.usb_Starlight.surround40", remap)

    def test_failed_start_stops_audio_target(self):
        def command(*args, **kwargs):
            if args[:3] == ("systemctl", "--user", "start"):
                raise RuntimeError("device unavailable")
            return ""
        with patch.object(speaker, "active", return_value=False), patch.object(speaker, "mixxx_running", return_value=False), patch.object(speaker, "run", side_effect=command) as run:
            with self.assertRaisesRegex(RuntimeError, "device unavailable"):
                speaker.start()
            run.assert_any_call("systemctl", "--user", "stop", speaker.TARGET, check=False)


if __name__ == "__main__":
    unittest.main()
