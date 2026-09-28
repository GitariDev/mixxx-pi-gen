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
        def fixture_shell(_application, title, section):
            return real_shell(cls.host, title, section)
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
            if isinstance(item, Gtk.ScrolledWindow):
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
        ] if active else [], "output": "mixpi_starlight_main" if active else None}
        mock = patch.object(self.speaker.Speaker, "state", side_effect=lambda: copy.deepcopy(state))
        mock.start()
        self.addCleanup(mock.stop)
        return self.activate(self.speaker.Speaker()), state

    def media_app(self):
        mock = patch.object(self.media, "mounted_drives", return_value=[])
        mock.start()
        self.addCleanup(mock.stop)
        return self.activate(self.media.create_media_app())

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
        state.update(active=True, mixxx=False, output="mixpi_starlight_main", outputs=[{"name": "mixpi_starlight_main"}])
        app.refresh()
        self.wait_idle(app)
        self.assertTrue(app.pair_button.get_sensitive())
        self.assertEqual(app.toggle.get_label(), "Stop speaker mode")
        self.snapshot(app, "speaker-on")

    def test_output_selection_survives_refresh_and_disconnection(self):
        app, state = self.speaker_app(True)
        app.output.set_active_id("hdmi")
        app.refresh()
        self.wait_idle(app)
        self.assertEqual(app.output.get_active_id(), "hdmi")
        self.assertTrue(app.apply.get_sensitive())
        state["outputs"] = state["outputs"][:1]
        app.refresh()
        self.wait_idle(app)
        self.assertEqual(app.output.get_active_id(), "mixpi_starlight_main")
        self.assertFalse(app.apply.get_sensitive())
        state["outputs"] = []
        state["output"] = None
        app.refresh()
        self.wait_idle(app)
        self.assertFalse(app.output.get_sensitive())
        self.assertFalse(app.apply.get_sensitive())
        self.snapshot(app, "speaker-no-output")

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
        state.update(active=True, mixxx=False, output="hdmi", outputs=[{"name": "hdmi"}, {"name": "mixpi_starlight_main"}])
        app.refresh()
        self.wait_idle(app)
        app.output.set_active_id("mixpi_starlight_main")
        with patch.object(app, "task") as task:
            app.select_output()
            self.assertEqual(task.call_args.args[0], [self.speaker.CONTROL, "output", "mixpi_starlight_main"])

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


if __name__ == "__main__":
    unittest.main()
