"""Native GTK interaction/layout checks. Run under Xvfb; skip on non-GTK hosts.

MIXPI_UI_SCREENSHOTS=/path saves actual 800x412 application renders.
Linux: xvfb-run -s '-screen 0 800x480x24' python3 -m unittest discover -s tests
"""
import copy
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "stage3/02-desktop/files/bin"
sys.path.insert(0, str(BIN))
try:
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk, Gio, GLib, Gtk
    HAS_GTK = Gtk.init_check()[0]
except (ImportError, ValueError):
    HAS_GTK = False


def load(name):
    loader = importlib.machinery.SourceFileLoader("ui_" + name.replace("-", "_"), str(BIN / name))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


def children(widget):
    yield widget
    if isinstance(widget, Gtk.Container):
        for child in widget.get_children():
            yield from children(child)


@unittest.skipUnless(HAS_GTK, "GTK 3 and a display required (use Xvfb)")
class TouchUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import mixpi_ui
        cls.speaker = load("mixpi-speaker")
        cls.settings = load("mixpi-settings")
        cls.media = load("mixpi-media")
        # GTK exports one application per process; all fixture windows share it.
        cls.host = Gtk.Application(application_id="org.mixpi.UiTests")
        cls.host.register(None)
        real_shell = mixpi_ui.shell
        def fixture_shell(_application, *arguments):
            return real_shell(cls.host, *arguments)
        for module in (mixpi_ui, cls.speaker, cls.settings):
            mock = patch.object(module, "shell", fixture_shell)
            mock.start()
            cls.addClassCleanup(mock.stop)

    @classmethod
    def tearDownClass(cls):
        cls.host.quit()

    def setUp(self):
        self.apps = []
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def tearDown(self):
        for app in self.apps:
            if getattr(app, "timing_dialog", None):
                app.timing_dialog.destroy()
            if app.window:
                app.window.destroy()
        self.pump()

    def pump(self):
        context = GLib.MainContext.default()
        for _ in range(15):
            while context.pending():
                context.iteration(False)
            time.sleep(0.005)

    def wait_idle(self, app):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            self.pump()
            if not app.busy:
                return
        self.fail("UI worker did not finish")

    def activate(self, app):
        self.apps.append(app)
        app.do_activate()
        app.window.set_decorated(False)
        app.window.resize(800, 412)
        self.pump()
        if hasattr(app, "busy"):
            self.wait_idle(app)
        return app

    def snapshot(self, app, name):
        self.pump()
        # Allow GTK's disabled/enabled color transition to finish before capture.
        time.sleep(0.2)
        self.pump()
        self.assertEqual(tuple(app.window.get_size()), (800, 412))
        for item in children(app.window):
            # The recordings list is the one area meant to scroll.
            if isinstance(item, Gtk.ScrolledWindow) and item.get_name() != "recordings":
                adjustment = item.get_vadjustment()
                self.assertLessEqual(adjustment.get_upper(), adjustment.get_page_size() + 1,
                                     f"{name}: content needs scrolling at the Pi size")
            if isinstance(item, Gtk.Button) and item.get_visible():
                self.assertGreaterEqual(item.get_allocated_height(), 44, name)
        destination = os.environ.get("MIXPI_UI_SCREENSHOTS")
        if destination:
            Path(destination).mkdir(parents=True, exist_ok=True)
            pixbuf = Gdk.pixbuf_get_from_window(app.window.get_window(), 0, 0, 800, 412)
            pixbuf.savev(str(Path(destination) / (name + ".png")), "png", [], [])

    def speaker_app(self, active=False):
        state = {"active": active, "mixxx": not active, "outputs": [
            {"name": "mixpi_starlight_main", "description": "Starlight"},
            {"name": "hdmi", "description": "HDMI speaker"},
        ] if active else [], "selected": ["mixpi_starlight_main"] if active else []}
        mock = patch.object(self.speaker.Speaker, "state", side_effect=lambda: copy.deepcopy(state))
        mock.start()
        self.addCleanup(mock.stop)
        return self.activate(self.speaker.Speaker()), state

    def spotify_app(self, **player):
        """Active Speaker screen with a fake player; returns app, player state and commands."""
        player = {"connected": True, "playing": True, "title": "Tezeta", "artist": "Mulatu Astatke",
                  "album": "Ethiopiques", "volume": 40, **player}
        commands = []
        def spotify(*command):
            if command:
                commands.append(command)
            if player.get("error"):
                raise ValueError(player["error"])
            return dict(player)
        mock = patch.object(self.speaker.Speaker, "spotify", side_effect=spotify)
        mock.start()
        self.addCleanup(mock.stop)
        app, _ = self.speaker_app(True)
        return app, player, commands

    def wait_spotify(self, app):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            self.pump()
            if not app.spotify_waiting and not app.spotify_volume_timer:
                return
        self.fail("Spotify worker did not finish")

    def dialog_snapshot(self, dialog, name):
        self.pump()
        if os.environ.get("MIXPI_UI_SCREENSHOTS"):
            folder = Path(os.environ["MIXPI_UI_SCREENSHOTS"])
            folder.mkdir(parents=True, exist_ok=True)
            pixbuf = Gdk.pixbuf_get_from_window(dialog.get_window(), 0, 0, *dialog.get_size())
            pixbuf.savev(str(folder / (name + ".png")), "png", [], [])

    def media_app(self):
        self.drives = []
        mock = patch.object(self.media, "mounted_drives", side_effect=lambda: list(self.drives))
        mock.start()
        self.addCleanup(mock.stop)
        return self.activate(self.media.create_media_app())

    def recordings_app(self, names=(), rekordbox=True):
        """Recordings mode over fixture folders; returns app, Pi folder and USB mount."""
        folder, usb = self.root / "Recordings", self.root / "usb"
        folder.mkdir()
        usb.mkdir()
        if rekordbox:
            (usb / "PIONEER/rekordbox").mkdir(parents=True)
            (usb / "PIONEER/rekordbox/export.pdb").write_bytes(b"playlists")
        for index, name in enumerate(names):
            (folder / f"{name}.wav").write_bytes(bytes([index]) * 40960)
            (folder / f"{name}.cue").write_text("TRACK 01 AUDIO\n")
            os.utime(folder / f"{name}.wav", (1000 + index, 1000 + index))
        for name, value in (("recordings_directory", lambda: folder), ("STATE_ROOT", self.root / "state")):
            mock = patch.object(self.media, name, value)
            mock.start()
            self.addCleanup(mock.stop)
        app = self.media_app()
        return app, folder, usb

    def plug(self, usb):
        self.drives.append({"source": str(usb), "label": "DJ USB", "uuid": "test-usb",
                            "device": "/dev/sda1", "size": 32 * 1024 ** 3, "fstype": "vfat"})

    def switch(self, app, recordings=True):
        (app.recordings_mode if recordings else app.music_mode).set_active(True)
        self.wait_idle(app)

    def plan(self):
        source = self.root / "USB"
        source.mkdir()
        (source / "set.wav").write_bytes(b"music" * 4096)
        destination = self.root / "backups"
        destination.mkdir()
        return self.media.make_plan(source, "DJ USB", "test-usb", audio_root=destination,
                                    state_root=self.root / "state", reserve=0)

    def test_settings_layout_and_unique_actions(self):
        app = self.activate(self.settings.Settings())
        self.snapshot(app, "settings")
        with patch.object(self.settings.subprocess, "Popen") as launch:
            tiles = [w for w in children(app.window) if isinstance(w, Gtk.Button) and w.get_style_context().has_class("tile")]
            for item in tiles:
                item.clicked()
            commands = [tuple(call.args[0]) for call in launch.call_args_list]
            self.assertEqual(len(commands), 8)
            self.assertEqual(len(set(commands)), 8)
            self.assertIn(("/usr/local/bin/mixpi-audio-preferences",), commands)

    def test_speaker_off_and_on_layout(self):
        app, state = self.speaker_app()
        self.assertFalse(app.pair_button.get_sensitive())
        self.assertFalse(app.apply.get_sensitive())
        self.snapshot(app, "speaker-off")
        state.update(active=True, mixxx=False, selected=["mixpi_starlight_main"], outputs=[{"name": "mixpi_starlight_main"}])
        app.refresh()
        self.wait_idle(app)
        self.assertTrue(app.pair_button.get_sensitive())
        self.assertEqual(app.toggle.get_label(), "Stop speaker mode")
        self.snapshot(app, "speaker-on")

    def test_output_selection_survives_refresh_and_disconnection(self):
        app, state = self.speaker_app(True)
        app.output_checks["mixpi_starlight_main"].set_active(False)
        app.output_checks["hdmi"].set_active(True)
        app.refresh()
        self.wait_idle(app)
        self.assertEqual(app.checked_outputs(), {"hdmi"})
        self.assertTrue(app.apply.get_sensitive())
        state["outputs"] = state["outputs"][:1]
        app.refresh()
        self.wait_idle(app)
        self.assertEqual(app.checked_outputs(), {"mixpi_starlight_main"})
        self.assertFalse(app.apply.get_sensitive())
        state["outputs"] = []
        state["selected"] = []
        app.refresh()
        self.wait_idle(app)
        self.assertFalse(app.output.get_sensitive())
        self.assertFalse(app.apply.get_sensitive())
        self.snapshot(app, "speaker-no-output")

    def test_multi_selection_empty_selection_and_applied_state(self):
        app, state = self.speaker_app(True)
        app.output_checks["hdmi"].set_active(True)
        app.refresh()
        self.wait_idle(app)
        self.assertEqual(app.checked_outputs(), {"hdmi", "mixpi_starlight_main"})
        self.assertEqual(app.output_label.get_text(), "2 outputs selected ▾")
        state["selected"] = ["hdmi", "mixpi_starlight_main"]
        app.current_state = None
        app.show_state(state)
        self.assertFalse(app.apply.get_sensitive())
        self.snapshot(app, "speaker-multiple")
        app.output.set_active(True)
        self.pump()
        self.assertTrue(app.output_popover.get_visible())
        background = app.output_popover.get_style_context().get_background_color(Gtk.StateFlags.NORMAL)
        self.assertLess(max(background.red, background.green, background.blue), .2)
        self.assertLessEqual(app.output_popover.get_allocated_width(), 800)
        self.assertLessEqual(app.output_popover.get_allocated_height(), 412)
        if os.environ.get("MIXPI_POPOVER_SCREENSHOT"):
            import subprocess
            subprocess.run(["grim", os.environ["MIXPI_POPOVER_SCREENSHOT"]], check=True)
        app.output_popover.popdown()
        for check in app.output_checks.values():
            check.set_active(False)
        self.assertFalse(app.apply.get_sensitive())
        app.refresh()
        self.wait_idle(app)
        self.assertEqual(app.checked_outputs(), set())

    def test_starlight_main_headphones_and_pi_can_all_be_selected(self):
        app, state = self.speaker_app(True)
        headphones = "mixpi_starlight_headphones"
        state["outputs"].extend([{"name": headphones}, {"name": "builtin", "properties": {"alsa.card_name": "bcm2835 Headphones"}}])
        app.show_state(state)
        app.output_checks[headphones].set_active(True)
        app.output_checks["builtin"].set_active(True)
        self.assertEqual(app.checked_outputs(), {"mixpi_starlight_main", headphones, "builtin"})
        self.assertEqual(app.output_checks[headphones].get_label(), "Starlight · Headphones 3–4")
        self.assertEqual(app.output_checks["builtin"].get_label(), "Pi · 3.5 mm jack")

    def test_fine_adjustment_bounds_apply_reset_and_close(self):
        app, state = self.speaker_app(True)
        name = "mixpi_starlight_main"
        state["delays_ms"] = {name: 20}
        app.show_state(state)
        app.fine.clicked()
        self.pump()
        self.assertTrue(app.timing_dialog.get_visible())
        self.assertEqual(app.timing_labels[name].get_text(), "20 ms")
        app.change_delay(name, 10)
        app.change_delay(name, -1)
        self.assertEqual(app.timing_values[name], 29)
        with patch.object(app, "task") as task:
            app.apply_delays()
            import json
            self.assertEqual(json.loads(task.call_args.args[0][2]), {name: 29})
            task.call_args.args[1]()
        self.assertFalse(app.timing_apply.get_sensitive())
        app.reset_delays()
        app.change_delay(name, -1)
        self.assertEqual(app.timing_values[name], 0)
        app.change_delay(name, 600)
        self.assertEqual(app.timing_values[name], 500)
        for step, control in app.timing_steps[name]:
            self.assertEqual(control.get_sensitive(), step < 0)
        app.timing_dialog.destroy()
        self.assertIsNone(app.timing_dialog)

    def test_fine_adjustment_three_outputs_fit_and_pending_selection_disables_button(self):
        app, state = self.speaker_app(True)
        state["outputs"].extend([{"name": "mixpi_starlight_headphones"}, {"name": "builtin", "properties": {"alsa.card_name": "bcm2835 Headphones"}}])
        state["selected"] = ["mixpi_starlight_main", "mixpi_starlight_headphones", "builtin"]
        app.show_state(state)
        app.fine.clicked()
        self.pump()
        dialog = app.timing_dialog
        width, height = dialog.get_size()
        self.assertLessEqual(width, 800)
        self.assertLessEqual(height, 412)
        for widget in children(dialog):
            if isinstance(widget, Gtk.Button):
                self.assertGreaterEqual(widget.get_allocated_height(), 44)
            if isinstance(widget, Gtk.ScrolledWindow):
                adjustment = widget.get_vadjustment()
                self.assertLessEqual(adjustment.get_upper(), adjustment.get_page_size() + 1)
        if os.environ.get("MIXPI_UI_SCREENSHOTS"):
            folder = Path(os.environ["MIXPI_UI_SCREENSHOTS"])
            folder.mkdir(parents=True, exist_ok=True)
            pixbuf = Gdk.pixbuf_get_from_window(dialog.get_window(), 0, 0, width, height)
            pixbuf.savev(str(folder / "speaker-fine-adjustment.png"), "png", [], [])
        dialog.destroy()
        app.output_checks["builtin"].set_active(False)
        self.assertFalse(app.fine.get_sensitive())

    def test_fine_adjustment_failed_apply_keeps_edits_and_recovers(self):
        app, _ = self.speaker_app(True)
        app.fine.clicked()
        app.change_delay("mixpi_starlight_main", 10)
        import subprocess
        failure = subprocess.CompletedProcess([], 1, "", "Device disconnected")
        with patch.object(self.speaker.subprocess, "run", return_value=failure), patch.object(self.speaker, "message"):
            app.apply_delays()
            self.assertFalse(app.timing_dialog.get_content_area().get_sensitive())
            self.wait_idle(app)
            self.assertTrue(app.timing_dialog.get_content_area().get_sensitive())
            self.assertTrue(app.timing_dialog.get_action_area().get_sensitive())
            self.assertEqual(app.timing_values["mixpi_starlight_main"], 10)
            self.assertTrue(app.timing_apply.get_sensitive())

    def test_speaker_handoff_cancel_does_not_stop_music(self):
        app, _ = self.speaker_app()
        with patch.object(self.speaker, "message", return_value=False) as confirm, patch.object(app, "task") as task:
            app.toggle_mode()
            self.wait_idle(app)
            confirm.assert_called_once()
            task.assert_not_called()

    def test_speaker_handoff_confirm_and_output_command(self):
        app, state = self.speaker_app()
        with patch.object(self.speaker, "message", return_value=True), patch.object(app, "task") as task:
            app.toggle_mode()
            self.wait_idle(app)
            self.assertEqual(task.call_args.args[0], [self.speaker.CONTROL, "start", "--close-mixxx"])
        state.update(active=True, mixxx=False, selected=["hdmi"], outputs=[{"name": "hdmi"}, {"name": "mixpi_starlight_main"}])
        app.refresh()
        self.wait_idle(app)
        app.output_checks["mixpi_starlight_main"].set_active(True)
        with patch.object(app, "task") as task:
            app.select_output()
            self.assertEqual(task.call_args.args[0], [self.speaker.CONTROL, "output", "hdmi", "mixpi_starlight_main"])

    def test_speaker_status_failure_recovers(self):
        app, _ = self.speaker_app(True)
        with patch.object(app, "state", side_effect=OSError("Audio disconnected")), patch.object(self.speaker, "message"):
            app.refresh()
            self.wait_idle(app)
            self.assertFalse(app.apply.get_sensitive())
            self.assertFalse(app.pair_button.get_sensitive())
            self.assertIn("unavailable", app.status.get_text())
            self.snapshot(app, "speaker-error")
        app.refresh()
        self.wait_idle(app)
        self.assertTrue(app.pair_button.get_sensitive())

    def test_speaker_failed_command_restores_controls(self):
        app, _ = self.speaker_app(True)
        import subprocess
        failure = subprocess.CompletedProcess([], 1, "", "Output was disconnected")
        with patch.object(self.speaker.subprocess, "run", return_value=failure), patch.object(self.speaker, "message") as dialog:
            app.task([self.speaker.CONTROL, "output", "missing"])
            self.assertTrue(app.busy)
            self.assertFalse(app.body.get_sensitive())
            self.wait_idle(app)
            self.assertTrue(app.body.get_sensitive())
            self.assertTrue(app.footer.get_sensitive())
            self.assertFalse(app.apply.get_sensitive())
            dialog.assert_called_once()

    def test_spotify_controls_need_speaker_mode_and_fit_the_screen(self):
        off, _ = self.speaker_app()
        self.assertFalse(off.spotify_button.get_sensitive())
        self.assertFalse(off.spotify_dialog.get_visible())
        app, _, commands = self.spotify_app()
        self.assertTrue(app.spotify_button.get_sensitive())
        app.spotify_button.clicked()
        self.wait_spotify(app)
        dialog = app.spotify_dialog
        self.assertTrue(dialog.get_visible())
        self.assertEqual(dialog.get_transient_for(), app.window)
        self.assertEqual(app.spotify_title.get_text(), "Tezeta")
        self.assertEqual(app.spotify_detail.get_text(), "Mulatu Astatke · Ethiopiques")
        self.assertEqual(app.spotify_play.get_label(), "Pause")
        self.assertEqual(app.spotify_volume.get_value(), 40)
        self.assertEqual(app.spotify_level.get_text(), "40%")
        self.assertEqual(commands, [])
        # The Speaker screen behind is covered edge to edge by its blurred picture.
        self.assertEqual(app.spotify_backdrop.get_allocated_width(), 800)
        self.assertEqual(app.spotify_backdrop.get_allocated_height(), 412)
        self.snapshot(app, "speaker-spotify-backdrop")
        self.dialog_snapshot(dialog, "speaker-spotify-controls")
        width, height = dialog.get_size()
        self.assertLessEqual(width, 780)
        self.assertLessEqual(height, 412)
        for widget in children(dialog):
            if isinstance(widget, (Gtk.Button, Gtk.Scale)):
                self.assertGreaterEqual(widget.get_allocated_height(), 44)

    def test_spotify_controls_stay_open_until_their_close_button(self):
        app, player, _ = self.spotify_app()
        app.spotify_button.clicked()
        self.wait_spotify(app)
        dialog = app.spotify_dialog
        self.assertTrue(dialog.get_modal())
        # A window-manager close, a Speaker refresh, a second tap and a new track leave it open.
        self.assertTrue(dialog.emit("delete-event", Gdk.Event.new(Gdk.EventType.DELETE)))
        app.refresh()
        self.wait_idle(app)
        app.spotify_button.clicked()
        player.update(title="Yekermo Sew", playing=False)
        app.poll_spotify()
        self.wait_spotify(app)
        self.assertTrue(dialog.get_visible())
        self.assertTrue(dialog.get_sensitive())
        self.assertEqual(len(app.window.get_child().get_children()), 2)
        self.assertEqual(app.spotify_title.get_text(), "Yekermo Sew")
        self.assertEqual(app.spotify_play.get_label(), "Play")
        self.assertIsNotNone(app.spotify_poll)
        close = [w for w in children(dialog) if isinstance(w, Gtk.Button) and w.get_label() == "Close"]
        self.assertEqual(len(close), 1)
        close[0].clicked()
        self.pump()
        self.assertFalse(dialog.get_visible())
        self.assertIsNone(app.spotify_poll)
        # Closing uncovers the Speaker screen, and the controls can be opened again.
        self.assertIsNone(app.spotify_backdrop)
        self.assertEqual(len(app.window.get_child().get_children()), 1)
        app.spotify_button.clicked()
        self.wait_spotify(app)
        self.assertTrue(dialog.get_visible())
        self.assertEqual(app.spotify_title.get_text(), "Yekermo Sew")

    def test_spotify_controls_send_taps_in_order_and_one_settled_volume(self):
        app, player, commands = self.spotify_app()
        app.spotify_button.clicked()
        self.wait_spotify(app)
        for control in (app.spotify_previous, app.spotify_play, app.spotify_next):
            control.clicked()
        self.wait_spotify(app)
        self.assertEqual(commands, [("previous",), ("toggle",), ("next",)])
        del commands[:]
        for level in (45, 52, 63):
            app.spotify_volume.set_value(level)
        self.assertEqual(app.spotify_level.get_text(), "63%")
        self.wait_spotify(app)
        self.assertEqual(commands, [("volume", "63")])
        # The player still reports its old level; the level just chosen stays put.
        self.assertEqual(app.spotify_volume.get_value(), 63)
        app.spotify_louder.clicked()
        app.spotify_louder.clicked()
        app.spotify_quieter.clicked()
        self.wait_spotify(app)
        self.assertEqual(commands[-1], ("volume", "68"))
        # A status check that started before a tap must not undo what the tap showed.
        app.spotify_waiting += 1
        app.spotify_done(app.spotify_request - 1, {"connected": False}, None)
        self.assertEqual(app.spotify_title.get_text(), "Tezeta")
        app.spotify_volume_held = 0
        player["volume"] = 20
        app.poll_spotify()
        self.wait_spotify(app)
        self.assertEqual(app.spotify_volume.get_value(), 20)
        self.assertEqual(commands[-1], ("volume", "68"))

    def test_spotify_controls_explain_no_phone_no_music_and_failure(self):
        app, player, _ = self.spotify_app(connected=False)
        transport = (app.spotify_previous, app.spotify_play, app.spotify_next)
        volume = (app.spotify_quieter, app.spotify_volume, app.spotify_louder)
        def shown():
            app.poll_spotify()
            self.wait_spotify(app)
            return (app.spotify_title.get_text(), [w.get_sensitive() for w in transport], [w.get_sensitive() for w in volume])
        app.spotify_button.clicked()
        self.wait_spotify(app)
        self.assertEqual(shown(), ("No phone connected", [False] * 3, [False] * 3))
        self.assertEqual(app.spotify_level.get_text(), "")
        self.dialog_snapshot(app.spotify_dialog, "speaker-spotify-no-phone")
        player.update(connected=True, title="", artist="", album="", playing=False)
        self.assertEqual(shown(), ("Nothing playing", [False] * 3, [True] * 3))
        player["error"] = "Spotify is not running. Start Speaker mode, then try again."
        self.assertEqual(shown(), ("Spotify controls unavailable", [False] * 3, [False] * 3))
        self.assertEqual(app.spotify_detail.get_text(), player["error"])
        self.assertTrue(app.spotify_title.get_style_context().has_class("error"))
        del player["error"]
        player.update(title="Tezeta", playing=True)
        self.assertEqual(shown(), ("Tezeta", [True] * 3, [True] * 3))
        self.assertFalse(app.spotify_title.get_style_context().has_class("error"))

    def test_confirmation_fits_touchscreen_and_defaults_to_keep_playing(self):
        import mixpi_ui
        app, _ = self.speaker_app()
        checked = []
        def inspect_dialog():
            dialogs = [w for w in Gtk.Window.list_toplevels() if isinstance(w, Gtk.MessageDialog)]
            if not dialogs:
                return True
            dialog = dialogs[0]
            width, height = dialog.get_size()
            checked.append((width, height, dialog.get_default_widget().get_label()))
            dialog.response(Gtk.ResponseType.CANCEL)
            return False
        GLib.timeout_add(100, inspect_dialog)
        self.assertFalse(mixpi_ui.message(app.window, "Stop DJ playback and start speaker mode?",
            "Mixxx will close and save its settings. Spotify and Bluetooth will use the speaker output.",
            confirm="Start speaker mode"))
        self.assertEqual(len(checked), 1)
        self.assertLessEqual(checked[0][0], 800)
        self.assertLessEqual(checked[0][1], 412)
        self.assertEqual(checked[0][2], "Keep playing")

    def test_pairing_notice_has_readable_rendered_colors(self):
        import mixpi_ui
        app, _ = self.speaker_app(True)
        checked = []
        def luminance(color):
            def linear(v):
                return v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4
            return sum(linear(v) * weight for v, weight in
                       zip((color.red, color.green, color.blue), (.2126, .7152, .0722)))
        def inspect_dialog():
            dialogs = [w for w in Gtk.Window.list_toplevels() if isinstance(w, Gtk.MessageDialog)]
            if not dialogs:
                return True
            dialog = dialogs[0]
            background = dialog.get_style_context().get_background_color(Gtk.StateFlags.NORMAL)
            for item in dialog.get_message_area().get_children():
                if isinstance(item, Gtk.Label):
                    color = item.get_style_context().get_color(Gtk.StateFlags.NORMAL)
                    low, high = sorted((luminance(color), luminance(background)))
                    checked.append((high + .05) / (low + .05))
            if os.environ.get("MIXPI_UI_SCREENSHOTS"):
                Path(os.environ["MIXPI_UI_SCREENSHOTS"]).mkdir(parents=True, exist_ok=True)
                width, height = dialog.get_size()
                pixbuf = Gdk.pixbuf_get_from_window(dialog.get_window(), 0, 0, width, height)
                pixbuf.savev(str(Path(os.environ["MIXPI_UI_SCREENSHOTS"]) / "pairing-notice.png"), "png", [], [])
            dialog.response(Gtk.ResponseType.CLOSE)
            return False
        GLib.timeout_add(200, inspect_dialog)
        mixpi_ui.message(app.window, "Choose Mix Pi on your phone",
            "Open your phone’s Bluetooth settings and select Mix Pi. Accept the matching pairing request on the Pi, then play audio.\n\nMix Pi is visible for 3 minutes.")
        self.assertEqual(len(checked), 2)
        self.assertTrue(all(ratio >= 4.5 for ratio in checked), checked)

    def test_media_empty_ready_and_verified(self):
        app = self.media_app()
        self.assertFalse(app.copy.get_sensitive())
        self.snapshot(app, "usb-empty")
        plan = self.plan()
        app.select.append_text("DJ USB · 32.0 GiB")
        app.busy = True
        app.select.set_active(0)
        app.busy = False
        app.show_plan(plan)
        self.snapshot(app, "usb-ready")
        app.start_copy()
        self.assertFalse(app.copy.get_sensitive())
        self.assertFalse(app.refresh.get_sensitive())
        self.wait_idle(app)
        self.assertTrue(app.open_copy.get_sensitive())
        self.assertEqual((plan.destination / "set.wav").read_bytes(), (plan.source / "set.wav").read_bytes())
        self.snapshot(app, "usb-complete")
        app.start_copy()
        self.wait_idle(app)
        self.assertEqual(app.phase.get_text(), "Existing copy verified")
        self.assertTrue(app.open_copy.get_sensitive())

    def test_media_cancel_and_error_recovery(self):
        app = self.media_app()
        app.show_plan(self.plan())
        def cancellable(*args):
            app.cancel_event.wait(2)
            self.media.check_cancel(app.cancel_event)
        with patch.object(self.media, "copy_plan", side_effect=cancellable):
            app.start_copy()
            self.assertTrue(app.close())
            self.wait_idle(app)
        self.assertEqual(app.phase.get_text(), "Transfer cancelled")
        self.assertFalse(app.copy.get_sensitive())
        self.snapshot(app, "usb-cancelled")
        app.refresh_drives()
        self.wait_idle(app)
        self.assertEqual(app.phase.get_text(), "No USB drive found")
        app.finished(lambda _: None, None, OSError("USB drive disconnected"))
        self.snapshot(app, "usb-error")

    def test_media_low_space_and_long_labels(self):
        app = self.media_app()
        plan = self.plan()
        plan.reserve = 10 ** 18
        app.show_plan(plan)
        self.assertFalse(app.copy.get_sensitive())
        app.select.append_text("Very long USB drive name with Unicode 音楽 " * 4)
        # No selection signal: a UI fixture with a long drive label.
        app.busy = True
        app.select.set_active(0)
        app.busy = False
        self.snapshot(app, "usb-low-space")


    def test_recordings_move_keeps_rekordbox_and_unticked_recordings(self):
        names = ("2026-10-09_20h00m00s", "2026-10-10_21h05m33s")
        app, folder, usb = self.recordings_app(names)
        self.plug(usb)
        self.switch(app)
        self.assertFalse(app.step.get_visible())
        self.assertIs(app.drive_row.get_parent(), app.usb_panel)
        self.assertEqual(list(app.checks), list(reversed(names)), "newest first")
        self.assertEqual(app.phase.get_text(), "Ready to move")
        self.assertEqual(app.copy.get_label(), "Move to USB")
        self.assertTrue(app.copy.get_sensitive())
        self.assertIn("Rekordbox", app.usb_note.get_text())
        self.snapshot(app, "recordings-ready")
        app.checks[names[0]].set_active(False)
        self.assertIn("1 of 2 selected", app.status.get_text())
        app.start_copy()
        self.assertFalse(app.recordings_mode.get_sensitive())
        self.wait_idle(app)
        self.assertEqual(app.phase.get_text(), "Move complete · Verified")
        saved = usb / self.media.RECORDINGS_FOLDER
        self.assertEqual(sorted(path.name for path in saved.iterdir()),
                         [names[1] + ".cue", names[1] + ".wav"])
        self.assertEqual(sorted(path.name for path in folder.iterdir()),
                         [names[0] + ".cue", names[0] + ".wav"])
        self.assertEqual((usb / "PIONEER/rekordbox/export.pdb").read_bytes(), b"playlists")
        self.assertEqual(list(app.checks), [names[0]])
        self.assertFalse(app.checks[names[0]].get_active(), "an unticked recording stays unticked")
        self.assertFalse(app.copy.get_sensitive())
        self.assertTrue(app.open_copy.get_sensitive())
        self.snapshot(app, "recordings-complete")
        self.drives.clear()
        self.switch(app, False)
        self.assertTrue(app.step.get_visible())
        self.assertIs(app.drive_row.get_parent(), app.body)
        self.assertEqual(app.body.get_children().index(app.drive_row), 1)
        self.assertEqual(app.copy.get_label(), "Copy to Pi")
        self.assertEqual(app.phase.get_text(), "No USB drive found")
        self.snapshot(app, "usb-empty-after-recordings")

    def test_recordings_empty_no_usb_in_use_and_long_list(self):
        app, folder, usb = self.recordings_app()
        self.switch(app)
        self.assertEqual(app.phase.get_text(), "No recordings on this Pi")
        self.assertFalse(app.copy.get_sensitive())
        self.snapshot(app, "recordings-empty")
        names = [f"2026-10-0{day}_22h10m00s" for day in range(1, 8)]
        for day, name in enumerate(names):
            (folder / f"{name}.wav").write_bytes(b"mix" * 1000)
            os.utime(folder / f"{name}.wav", (2000 + day, 2000 + day))
        with patch.object(self.media, "files_in_use", return_value={names[-1] + ".wav"}):
            app.refresh_drives()
            self.wait_idle(app)
            self.assertEqual(app.phase.get_text(), "No USB drive found")
            self.assertIn("6 of 7 selected", app.status.get_text())
            self.assertFalse(app.copy.get_sensitive())
            self.assertFalse(app.checks[names[-1]].get_sensitive())
            self.assertFalse(app.checks[names[-1]].get_active())
            for check in app.checks.values():
                self.assertGreaterEqual(check.get_allocated_height(), 44)
            self.snapshot(app, "recordings-no-usb")
            self.plug(usb)
            app.refresh_drives()
            self.wait_idle(app)
            self.assertEqual(app.phase.get_text(), "Ready to move")
            self.assertNotIn(names[-1], [item["name"] for item in app.selected()])

    def test_recordings_low_space_cancel_and_error_recovery(self):
        app, folder, usb = self.recordings_app(("2026-10-10_21h05m33s",), rekordbox=False)
        self.plug(usb)
        real_target = self.media.usb_target
        with patch.object(self.media, "usb_target", side_effect=lambda drive: dict(real_target(drive), free=1024)):
            self.switch(app)
            self.assertEqual(app.phase.get_text(), "Cannot move yet")
            self.assertIn("Not enough USB space", app.status.get_text())
            self.assertFalse(app.copy.get_sensitive())
            self.assertIn("Other files", app.usb_note.get_text())
            self.snapshot(app, "recordings-low-space")
        app.refresh_drives()
        self.wait_idle(app)
        self.assertTrue(app.copy.get_sensitive())
        def cancellable(*arguments, **options):
            app.cancel_event.wait(2)
            raise self.media.Cancelled("Move cancelled. Recordings are still on the Pi.")
        with patch.object(self.media, "move_recordings", side_effect=cancellable):
            app.start_copy()
            self.assertTrue(app.close())
            self.wait_idle(app)
        self.assertEqual(app.phase.get_text(), "Transfer cancelled")
        self.assertFalse(app.copy.get_sensitive())
        self.assertEqual(len(app.checks), 1)
        self.snapshot(app, "recordings-cancelled")
        app.refresh_drives()
        self.wait_idle(app)
        self.assertEqual(app.phase.get_text(), "Ready to move")
        (usb / self.media.RECORDINGS_FOLDER).mkdir()
        (usb / self.media.RECORDINGS_FOLDER / "2026-10-10_21h05m33s.wav").write_bytes(b"another mix")
        app.start_copy()
        self.wait_idle(app)
        self.assertEqual(app.phase.get_text(), "Could not complete transfer")
        self.assertIn("was not replaced", app.status.get_text())
        self.assertTrue((folder / "2026-10-10_21h05m33s.wav").exists())
        self.snapshot(app, "recordings-error")


if __name__ == "__main__":
    unittest.main()
