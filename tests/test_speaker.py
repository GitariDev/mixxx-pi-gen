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
    def test_invalid_delays_are_rejected_before_changing_audio(self):
        with patch.object(speaker, "run") as run:
            for delays in ([], {"a": -1}, {"a": 501}, {"a": True}, {"a": 1.2}, {"a": "10"}):
                with self.assertRaisesRegex(RuntimeError, "whole milliseconds"):
                    speaker.adjust_delays(delays)
            run.assert_not_called()

    def test_delay_route_has_correct_units_and_is_hidden_from_selection(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(speaker, "STATE", Path(directory) / "speaker.json"), patch.object(speaker, "outputs", return_value=[{"name": "a"}]), patch.object(speaker, "run", return_value="[]") as run:
            target = speaker.choose_outputs(["a"], delays={"a": 21, "unplugged": 75})
            load = run.call_args_list[0].args
            self.assertIn("module-ladspa-sink", load)
            self.assertIn("control=1,0.021", load)
            self.assertIn("sink_master=a", load)
            self.assertIn("channels=2", load)
            self.assertEqual(speaker.saved_delays(), {"a": 21, "unplugged": 75})
            # PipeWire 1.4 does not retain custom properties on LADSPA sinks.
            sinks = [{"name": "a"}, {"name": target}]
            self.assertEqual(speaker.selectable_outputs(sinks), [{"name": "a"}])
            with patch.object(speaker, "run", return_value=target):
                self.assertEqual(speaker.selected_outputs(sinks), ["a"])
                self.assertEqual(speaker.current_delays(sinks), {"a": 21, "unplugged": 75})

    def test_timing_edit_keeps_combined_volume_and_mute(self):
        old = speaker.COMBINED_PREFIX + "old"
        sinks = [{"name": "a"}, {"name": "b"}, {"name": old, "owner_module": 99,
                 "volume": {"front-left": {"value": 32000}, "front-right": {"value": 30000}}, "mute": True}]
        def command(*args, **kwargs):
            if args[1] == "get-default-sink":
                return old
            if args[1] == "load-module":
                return "123"
            return "[]"
        with patch.object(speaker, "outputs", return_value=sinks), patch.object(speaker, "run", side_effect=command) as run:
            target = speaker.choose_outputs(["a", "b"], save=False, delays={"a": 10})
            run.assert_any_call("pactl", "set-sink-volume", target, "32000", "30000")
            run.assert_any_call("pactl", "set-sink-mute", target, "1")
            for call in run.call_args_list:
                if call.args[1] in ("set-sink-volume", "set-sink-mute"):
                    self.assertNotIn(call.args[2], ("a", "b"))

    def test_failed_delayed_combine_cleans_new_filters_without_saving(self):
        def command(*args, **kwargs):
            if "module-combine-sink" in args:
                raise RuntimeError("Cannot combine")
            return "123"
        with tempfile.TemporaryDirectory() as directory, patch.object(speaker, "STATE", Path(directory) / "speaker.json"), patch.object(speaker, "outputs", return_value=[{"name": "a"}, {"name": "b"}]), patch.object(speaker, "run", side_effect=command) as run:
            with self.assertRaisesRegex(RuntimeError, "Cannot combine"):
                speaker.choose_outputs(["a", "b"], delays={"a": 50})
            run.assert_any_call("pactl", "unload-module", "123", check=False)
            self.assertFalse(speaker.STATE.exists())
            self.assertFalse(any(c.args[1] == "set-default-sink" for c in run.call_args_list))

    def test_reset_to_zero_retires_delay_after_moving_music(self):
        old = speaker.DELAY_PREFIX + "old"
        sinks = [{"name": "a"}, {"name": old, "owner_module": 123}]
        with patch.object(speaker, "outputs", return_value=sinks), patch.object(speaker, "run", return_value='[{"index":7,"properties":{}}]') as run:
            self.assertEqual(speaker.choose_outputs(["a"], save=False, delays={"a": 0}), "a")
            move = next(i for i,c in enumerate(run.call_args_list) if c.args[1] == "move-sink-input")
            unload = next(i for i,c in enumerate(run.call_args_list) if c.args[1] == "unload-module")
            self.assertLess(move, unload)
            self.assertFalse(any(c.args[1] == "load-module" for c in run.call_args_list))

    def test_adjustment_retains_missing_outputs_and_other_saved_preferences(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(speaker, "STATE", Path(directory) / "speaker.json"):
            speaker.STATE.write_text('{"outputs":["a","missing"],"other":true,"delays_ms":{"missing":20}}')
            with patch.object(speaker, "active", return_value=True), patch.object(speaker, "outputs", return_value=[]), patch.object(speaker, "selected_outputs", return_value=["a"]), patch.object(speaker, "current_delays", return_value={"a": 0, "missing": 20}), patch.object(speaker, "choose_outputs") as choose:
                speaker.adjust_delays({"a": 10})
                choose.assert_called_once_with(["a"], save=False, delays={"a": 10, "missing": 20})
                self.assertEqual(speaker.saved_outputs(), ["a", "missing"])
                self.assertTrue(speaker.saved_state()["other"])
                self.assertEqual(speaker.saved_delays(), {"a": 10, "missing": 20})

    def test_stale_or_inactive_adjustment_does_not_change_routing(self):
        with patch.object(speaker, "choose_outputs") as choose, patch.object(speaker, "active", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "Start Speaker"):
                speaker.adjust_delays({"a": 10})
            choose.assert_not_called()
        with patch.object(speaker, "choose_outputs") as choose, patch.object(speaker, "active", return_value=True), patch.object(speaker, "outputs", return_value=[]), patch.object(speaker, "selected_outputs", return_value=["b"]):
            with self.assertRaisesRegex(RuntimeError, "active outputs changed"):
                speaker.adjust_delays({"a": 10})
            choose.assert_not_called()

    def test_saved_delay_survives_output_selection_and_malformed_state(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(speaker, "STATE", Path(directory) / "speaker.json"), patch.object(speaker, "outputs", return_value=[{"name": "a"}]), patch.object(speaker, "run", return_value="[]") as run:
            speaker.STATE.write_text('{"delays_ms":{"a":25}}')
            speaker.choose_outputs(["a"])
            self.assertIn("control=1,0.025", run.call_args_list[0].args)
            for contents in ('[]', '{', '{"delays_ms":{"a":-1}}'):
                speaker.STATE.write_text(contents)
                self.assertEqual(speaker.saved_delays(), {})

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

    def test_headphone_route_maps_stereo_to_rear_without_changing_hardware_volume(self):
        raw = {"name": "alsa_output.usb_Starlight.surround40", "channel_map": "front-left,front-right,rear-left,rear-right"}
        sinks = [raw, {"name": "mixpi_starlight_main"}]
        with patch.object(speaker, "outputs", return_value=sinks), patch.object(speaker, "run") as run:
            speaker.prepare_outputs()
            remap = run.call_args_list[0].args
            self.assertIn("sink_name=mixpi_starlight_headphones", remap)
            self.assertIn("master_channel_map=rear-left,rear-right", remap)
            self.assertIn("channel_map=front-left,front-right", remap)
            self.assertIn("remix=no", remap)
            self.assertFalse(any(raw["name"] in c.args for c in run.call_args_list))

    def test_raw_starlight_is_hidden_and_legacy_selection_migrates_to_main(self):
        raw = {"name": "alsa_output.usb_Starlight.surround40"}
        main = {"name": "mixpi_starlight_main"}
        headphones = {"name": "mixpi_starlight_headphones"}
        sinks = [raw, main, headphones]
        self.assertEqual(speaker.selectable_outputs(sinks), [main, headphones])
        self.assertEqual(speaker.migrate_outputs([raw["name"]], sinks), [main["name"]])
        with patch.object(speaker, "outputs", return_value=sinks), patch.object(speaker, "run", return_value="[]"):
            target = speaker.choose_outputs([main["name"], headphones["name"]], save=False)
            self.assertTrue(target.startswith(speaker.COMBINED_PREFIX))

    def test_multiple_outputs_create_stereo_route_and_preserve_internal_streams(self):
        sinks = [{"name": "starlight"}, {"name": "builtin"}]
        def command(*args, **kwargs):
            if args[1:3] == ("load-module", "module-combine-sink"):
                return "123"
            if args[1:] == ("--format=json", "list", "sink-inputs"):
                return '[{"index": 7, "properties": {}}, {"index": 8, "properties": {"node.virtual": true}}]'
            return ""
        with tempfile.TemporaryDirectory() as directory, patch.object(speaker, "STATE", Path(directory) / "speaker.json"), patch.object(speaker, "outputs", return_value=sinks), patch.object(speaker, "run", side_effect=command) as run:
            target = speaker.choose_outputs(["starlight", "builtin", "builtin"])
            self.assertEqual(speaker.saved_outputs(), ["builtin", "starlight"])
            load = next(c.args for c in run.call_args_list if c.args[1] == "load-module")
            self.assertIn("sinks=builtin,starlight", load)
            self.assertIn("remix=no", load)
            self.assertIn("latency_compensate=true", load)
            run.assert_any_call("pactl", "move-sink-input", "7", target, check=False)
            self.assertFalse(any(c.args[:3] == ("pactl", "move-sink-input", "8") for c in run.call_args_list))

    def test_empty_missing_and_duplicate_hardware_selections_are_rejected(self):
        raw = "alsa_output.usb_Starlight.surround40"
        sinks = [{"name": raw}, {"name": "mixpi_starlight_main"}]
        with patch.object(speaker, "outputs", return_value=sinks), patch.object(speaker, "run") as run:
            for names in ([], [raw, "missing"], [raw, "mixpi_starlight_main"]):
                with self.assertRaises(RuntimeError):
                    speaker.choose_outputs(names)
            run.assert_not_called()

    def test_old_single_output_preferences_remain_readable(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(speaker, "STATE", Path(directory) / "speaker.json"):
            speaker.STATE.write_text('{"output": "builtin"}')
            self.assertEqual(speaker.saved_outputs(), ["builtin"])

    def test_combined_status_filters_disconnected_members_and_virtual_device(self):
        name = speaker.COMBINED_PREFIX + "test"
        sinks = [{"name": "builtin"}, {"name": name, "owner_module": 123}]
        with patch.object(speaker, "run", side_effect=[name, '[{"name": "module-combine-sink", "argument": "sink_name=' + name + ' sinks=builtin,missing"}]']):
            self.assertEqual(speaker.selected_outputs(sinks), ["builtin"])
        self.assertEqual(speaker.selectable_outputs(sinks), [{"name": "builtin"}])

    def test_combined_route_reused_then_retired_after_switch_to_single(self):
        import hashlib
        name = speaker.COMBINED_PREFIX + hashlib.sha256(b"a,b").hexdigest()[:16]
        sinks = [{"name": "a"}, {"name": "b"}, {"name": name, "owner_module": 123}]
        with patch.object(speaker, "outputs", return_value=sinks), patch.object(speaker, "run", return_value="[]") as run:
            self.assertEqual(speaker.choose_outputs(["b", "a"], save=False), name)
            self.assertFalse(any(c.args[1] in ("load-module", "unload-module") for c in run.call_args_list))
            run.reset_mock()
            speaker.choose_outputs(["a"], save=False)
            run.assert_any_call("pactl", "unload-module", "123", check=False)
            self.assertEqual(run.call_args_list[0].args, ("pactl", "set-default-sink", "a"))

    def test_failed_default_change_removes_new_module_without_saving(self):
        def command(*args, **kwargs):
            if args[1] == "load-module":
                return "123"
            if args[1] == "set-default-sink":
                raise RuntimeError("Disconnected")
            return ""
        with patch.object(speaker, "outputs", return_value=[{"name": "a"}, {"name": "b"}]), patch.object(speaker, "run", side_effect=command) as run:
            with self.assertRaisesRegex(RuntimeError, "Disconnected"):
                speaker.choose_outputs(["a", "b"])
            run.assert_any_call("pactl", "unload-module", "123", check=False)

    def test_restart_restores_available_saved_outputs_without_forgetting_missing(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(speaker, "STATE", Path(directory) / "speaker.json"):
            speaker.STATE.write_text('{"outputs": ["a", "b", "missing"]}')
            with patch.object(speaker, "active", return_value=False), patch.object(speaker, "mixxx_running", return_value=False), patch.object(speaker, "outputs", return_value=[{"name": "a"}, {"name": "b"}]), patch.object(speaker, "prepare_outputs", return_value=[{"name": "a"}, {"name": "b"}]), patch.object(speaker, "choose_outputs", return_value="combined") as choose, patch.object(speaker, "run"):
                speaker.start()
                choose.assert_called_once_with(["a", "b"], save=False)
                self.assertEqual(speaker.saved_outputs(), ["a", "b", "missing"])

    def test_failed_start_stops_audio_target(self):
        def command(*args, **kwargs):
            if args[:3] == ("systemctl", "--user", "start"):
                raise RuntimeError("device unavailable")
            return ""
        with patch.object(speaker, "active", return_value=False), patch.object(speaker, "mixxx_running", return_value=False), patch.object(speaker, "run", side_effect=command) as run:
            with self.assertRaisesRegex(RuntimeError, "device unavailable"):
                speaker.start()
            run.assert_any_call("systemctl", "--user", "stop", speaker.TARGET, check=False)

    def spotify_player(self, status=None, steps=100):
        """Fake player API; status None means no phone has chosen Mix Pi."""
        calls = []
        def request(path, body=None):
            calls.append((path, body))
            if status is None:
                return 204, None
            if path == "/status":
                return 200, status
            if path == "/player/volume" and body is None:
                return 200, {"value": status["volume"], "max": steps}
            return 200, None
        return patch.object(speaker, "spotify_request", side_effect=request), calls

    def test_spotify_status_reports_track_and_percent_volume(self):
        track = {"name": "Tezeta", "artist_names": ["Mulatu Astatke", "Guest"], "album_name": "Ethiopiques"}
        player, _ = self.spotify_player({"stopped": False, "paused": False, "volume": 16, "volume_steps": 64, "track": track})
        with player:
            self.assertEqual(speaker.spotify_control(), {"connected": True, "playing": True, "title": "Tezeta",
                "artist": "Mulatu Astatke, Guest", "album": "Ethiopiques", "volume": 25})
        player, _ = self.spotify_player({"stopped": False, "paused": True, "volume": 50, "volume_steps": 100, "track": track})
        with player:
            self.assertFalse(speaker.spotify_control()["playing"])

    def test_spotify_without_phone_or_track_has_nothing_to_play(self):
        player, _ = self.spotify_player()
        with player:
            self.assertEqual(speaker.spotify_control(), {"connected": False})
        for status in ({"stopped": True, "paused": False, "volume": 40, "volume_steps": 100, "track": {"name": "Old"}},
                       {"stopped": False, "paused": False, "volume": 40, "volume_steps": 100, "track": None}):
            player, _ = self.spotify_player(status)
            with player:
                state = speaker.spotify_control()
                self.assertEqual((state["connected"], state["playing"], state["title"], state["volume"]), (True, False, "", 40))

    def test_spotify_transport_commands_reach_the_player(self):
        for action, path in (("toggle", "/player/playpause"), ("next", "/player/next"), ("previous", "/player/prev")):
            player, calls = self.spotify_player({"volume": 40, "volume_steps": 100, "track": None})
            with player:
                speaker.spotify_control(action)
            self.assertEqual(calls, [(path, {}), ("/status", None)])

    def test_spotify_volume_uses_player_steps_and_rejects_bad_levels(self):
        player, calls = self.spotify_player({"volume": 32, "volume_steps": 64, "track": None}, steps=64)
        with player:
            speaker.spotify_control("volume", "75")
            self.assertIn(("/player/volume", {"volume": 48}), calls)
            del calls[:]
            for level in ("101", "-1", "1.5", "loud", ""):
                with self.assertRaisesRegex(RuntimeError, "0 to 100"):
                    speaker.spotify_control("volume", level)
            for command in (("volume",), ("volume", "1", "2"), ("toggle", "now"), ("shuffle",)):
                with self.assertRaisesRegex(RuntimeError, "Unknown Spotify command"):
                    speaker.spotify_control(*command)
            self.assertEqual(calls, [])
        player, calls = self.spotify_player()
        with player:
            self.assertEqual(speaker.spotify_control("volume", "30"), {"connected": False})
            self.assertNotIn(("/player/volume", {"volume": 30}), calls)

    def test_spotify_player_that_is_not_running_is_reported(self):
        with patch.object(speaker, "SPOTIFY_API", "http://127.0.0.1:9"):
            with self.assertRaisesRegex(RuntimeError, "Spotify is not running"):
                speaker.spotify_control()

    def test_spotify_service_serves_the_control_api_on_loopback_only(self):
        unit = (ROOT / "stage3/02-desktop/files/systemd/user/mixpi-spotify.service").read_text()
        host, port = speaker.SPOTIFY_API.rsplit("/", 1)[1].split(":")
        self.assertIn("server.enabled=true", unit)
        self.assertIn("server.address=" + host, unit)
        self.assertIn("server.port=" + port, unit)
        self.assertEqual(host, "127.0.0.1")


if __name__ == "__main__":
    unittest.main()
