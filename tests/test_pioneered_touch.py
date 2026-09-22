"""The skin patch must be repeatable and preserve a usable rollback copy.

Actual Qt rendering and touch interaction are checked on the Pi. To exercise
the complete pinned upstream skin as well, set PIONEERED_TEST_SKIN to an
unmodified checkout; the test works on a temporary copy.
"""

import importlib.util
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "pioneered_touch", ROOT / "stage3/01-install-packages/files/pioneered-touch.py")
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)
DEFAULTS_SCRIPT = ROOT / "stage3/02-desktop/files/bin/mixpi-touch-defaults"
DEFAULTS = runpy.run_path(str(DEFAULTS_SCRIPT))


class TouchDefaultsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.config = self.path / "profile/mixxx.cfg"

    def test_new_config_gets_only_skin_and_library_defaults(self):
        DEFAULTS["seed"](self.config)
        self.assertEqual(set(line for line in self.config.read_text().splitlines() if line), {
            "[Library]", "RowHeight 34", "Font Sans Serif,-1,17,5,50,0,0,0,0,0",
            "[Config]", "ResizableSkin Pioneered"})
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o600)

    def test_saved_choices_and_unrelated_settings_are_preserved(self):
        self.config.parent.mkdir()
        source = "[Config]\nResizableSkin Deere\n\n[Library]\nRowHeight 42\nFont Custom,20\n\n[Soundcard]\nSamplerate 48000\n"
        self.config.write_text(source)
        before = self.config.stat().st_mtime_ns
        DEFAULTS["seed"](self.config)
        DEFAULTS["seed"](self.config)
        self.assertEqual(self.config.read_text(), source)
        self.assertEqual(self.config.stat().st_mtime_ns, before)

    def test_missing_keys_added_without_selecting_skin_for_existing_config(self):
        self.config.parent.mkdir()
        self.config.write_text("[Config]\nLocale en_US\n\n[Library]\nRowHeight 42\nRescanOnStartup 0\n")
        self.config.chmod(0o640)
        DEFAULTS["seed"](self.config)
        first = self.config.read_text()
        self.assertIn("RowHeight 42\nRescanOnStartup 0\n", first)
        self.assertIn("Font Sans Serif,-1,17,5,50,0,0,0,0,0\n", first)
        self.assertNotIn("ResizableSkin", first)
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o640)
        DEFAULTS["seed"](self.config)
        self.assertEqual(self.config.read_text(), first)

    def test_running_mixxx_does_not_create_or_modify_config(self):
        pgrep = self.path / "pgrep"
        pgrep.write_text("#!/bin/sh\nexit 0\n")
        pgrep.chmod(0o755)
        result = subprocess.run([sys.executable, str(DEFAULTS_SCRIPT), "--config", str(self.config)],
                                env={**os.environ, "PATH": f"{self.path}:{os.environ['PATH']}"},
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("may be running", result.stderr)
        self.assertFalse(self.config.exists())


class PioneeredTouchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.skin = self.path / "Pioneered"
        self.skin.mkdir()
        (self.skin / "skin.xml").write_text("<skin><manifest/></skin>\n")
        (self.skin / "library.xml").write_text("""<Template>
  <WidgetGroup><Children>
    <SearchBox><ObjectName>SearchBox</ObjectName></SearchBox>
    <PushButton>
      <ObjectName>SidebarButton</ObjectName>
    </PushButton>
    <Library><ObjectName>Library</ObjectName></Library>
  </Children></WidgetGroup>
</Template>
""")
        (self.skin / "style.qss").write_text("""/* custom upstream style */
#LibraryWrapper QScrollBar:horizontal {
  height: 0;
  width: 0;
}
#Unrelated { color: red; }
""")
        self.config = self.path / "mixxx.cfg"
        self.config.write_text("""[Soundcard]
Samplerate 48000

[Library]
RowHeight 20
Font OldFont,9,-1,5,50,0,0,0,0,0
RescanOnStartup 0
SupportedFileExtensions mp3,flac

[Controller]
UnrelatedValue preserve this exactly
""")

    def test_repeat_apply_retains_first_originals_and_unrelated_settings(self):
        originals = {path: path.read_text() for path in (
            self.skin / "style.qss", self.skin / "library.xml", self.config)}
        PATCH.apply(self.skin, self.config)
        first = {path: path.read_text() for path in originals}
        PATCH.apply(self.skin, self.config)
        self.assertEqual(first, {path: path.read_text() for path in originals})
        for path, source in originals.items():
            backup = (Path(str(path) + ".before-mixpi-touch") if path == self.config
                      else self.skin / ".mixpi-touch-original" / path.name)
            self.assertEqual(backup.read_text(), source)
        config = self.config.read_text()
        self.assertIn("Samplerate 48000\n", config)
        self.assertIn("RescanOnStartup 0\nSupportedFileExtensions mp3,flac\n", config)
        self.assertIn("[Controller]\nUnrelatedValue preserve this exactly\n", config)
        self.assertIn("RowHeight 34\n", config)
        self.assertNotIn("RowHeight 20", config)

    def test_actions_emits_only_on_press_and_scrollbar_has_no_zero_width(self):
        PATCH.apply(self.skin)
        root = ET.parse(self.skin / "library.xml")
        actions = [button for button in root.findall(".//PushButton")
                   if button.findtext("ObjectName") == "LibraryActionsButton"]
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].findtext("Connection/ConfigKey"),
                         "[Library],show_track_menu")
        self.assertEqual(actions[0].findtext("Connection/EmitOnDownPress"), "true")
        styles = (self.skin / "style.qss").read_text()
        self.assertNotIn("width: 0;", styles)
        self.assertIn("height: 26px;", styles)
        self.assertIn("#Unrelated { color: red; }", styles)

    def test_changed_upstream_layout_fails_before_writing(self):
        path = self.skin / "library.xml"
        path.write_text(path.read_text().replace("SidebarButton", "NewSidebar"))
        originals = {path: path.read_text() for path in self.skin.iterdir()}
        with self.assertRaises(ValueError):
            PATCH.apply(self.skin, self.config)
        self.assertEqual(originals, {path: path.read_text() for path in self.skin.iterdir()})
        self.assertFalse(Path(str(self.config) + ".before-mixpi-touch").exists())

    def test_invalid_config_fails_before_skin_is_changed(self):
        self.config.write_text("[Library]\nRowHeight 20\n[Library]\nRowHeight 24\n")
        before = (self.skin / "library.xml").read_text()
        with self.assertRaises(ValueError):
            PATCH.apply(self.skin, self.config)
        self.assertEqual((self.skin / "library.xml").read_text(), before)
        self.assertFalse((self.skin / ".mixpi-touch-original").exists())

    def test_missing_config_section_can_be_added(self):
        result = PATCH.patch_config("[Soundcard]\nSamplerate 48000\n")
        self.assertIn("[Soundcard]\nSamplerate 48000\n", result)
        self.assertEqual(result.count("[Library]"), 1)
        self.assertIn("RowHeight 34\n", result)
        self.assertEqual(PATCH.patch_config(result), result)

    @unittest.skipUnless(os.environ.get("PIONEERED_TEST_SKIN"), "pinned upstream checkout optional")
    def test_pinned_upstream_skin(self):
        skin = self.path / "upstream"
        shutil.copytree(os.environ["PIONEERED_TEST_SKIN"], skin,
                        ignore=shutil.ignore_patterns(".git", ".mixpi-touch-original"))
        PATCH.apply(skin, self.config)
        first = {name: (skin / name).read_bytes() for name in ("library.xml", "style.qss")}
        PATCH.apply(skin, self.config)
        self.assertEqual(first, {name: (skin / name).read_bytes() for name in first})
        for path in skin.rglob("*.xml"):
            ET.parse(path)
        actions = [button for button in ET.parse(skin / "library.xml").findall(".//PushButton")
                   if button.findtext("ObjectName") == "LibraryActionsButton"]
        self.assertEqual(len(actions), 1)


if __name__ == "__main__":
    unittest.main()
