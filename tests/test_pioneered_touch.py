"""The skin patch must be repeatable and preserve a usable rollback copy.

Actual Qt rendering and touch interaction are checked on the Pi. To exercise
the complete pinned upstream skin as well, set PIONEERED_TEST_SKIN to an
unmodified checkout; the test works on a temporary copy.
"""

import importlib.util
import os
import re
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
            "[Config]", "ResizableSkin Pioneered", "hide_menubar 1", "show_menubar_hint 0",
            "MixPiBootstrapLibrary 1", "[Controls]", "PositionDisplay 0"})
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o600)

    def test_position_display_is_seeded_for_new_profiles_only(self):
        DEFAULTS["seed"](self.config)
        self.assertIn("[Controls]\nPositionDisplay 0\n", self.config.read_text())
        for source in ("[Controls]\nPositionDisplay 2\nRateDir 1\n",
                       "[Controls]\nPositionDisplay 1\n",
                       "[Controls]\nRateDir 1\n",
                       "[Config]\nLocale en_US\n"):
            with self.subTest(source=source):
                self.config.write_text(source)
                DEFAULTS["seed"](self.config)
                result = self.config.read_text()
                self.assertEqual(result.count("PositionDisplay"), source.count("PositionDisplay"))
                if "PositionDisplay" in source:
                    position = next(line for line in source.splitlines() if line.startswith("PositionDisplay"))
                    self.assertIn(position + "\n", result)
                self.assertNotIn("PositionDisplay 0", result.replace(source, ""))

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
        (self.skin / "tab.xml").write_text('''<Template>
  <PushButton>
    <NumberStates>2</NumberStates>
    <State><Number>0</Number><Text>Tab</Text></State>
    <State><Number>1</Number><Text>Tab</Text></State>
    <Connection>
      <ConfigKey>[Tab],<Variable name="config_key"/></ConfigKey>
    </Connection>
  </PushButton>
</Template>''')
        (self.skin / "effect.xml").write_text(
            "<Template>\n" + PATCH.EFFECT_TOGGLE_ORIGINAL + "\n</Template>\n")
        (self.skin / "deck.xml").write_text(
            "<Template>\n" + PATCH.TRACK_NUMBER_ORIGINAL + "\n</Template>\n")
        shutil.copyfile(ROOT / "tests/fixtures/pioneered-library.xml",
                        self.skin / "library.xml")
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
            self.skin / "style.qss", self.skin / "library.xml",
            self.skin / "effect.xml", self.skin / "deck.xml",
            self.skin / "tab.xml", self.config)}
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
        self.assertIn("height: 24px;", styles)
        self.assertIn("#Unrelated { color: red; }", styles)

    def test_sources_screen_rows_and_list_scroll_bars_are_touch_sized(self):
        # R-9: Sources is a full screen with 56 px rows and 24 px scroll bars.
        PATCH.apply(self.skin)
        styles = (self.skin / "style.qss").read_text()
        block = styles.split(PATCH.STYLE_BEGIN, 1)[1].split(PATCH.STYLE_END, 1)[0]
        def rule(selector):
            self.assertEqual(block.count(selector + " {"), 1, selector)
            return block.split(selector + " {", 1)[1].split("}", 1)[0]
        self.assertIn("min-height: 56px;", rule("#LibraryWrapper WLibrarySidebar::item"))
        self.assertIn("width: 24px;", rule("#LibraryWrapper QScrollBar:vertical"))
        self.assertIn("height: 24px;", rule("#LibraryWrapper QScrollBar:horizontal"))
        self.assertIn("min-height: 56px;", rule("#LibraryWrapper QScrollBar::handle:vertical"))
        # ✎ lights with the accent tint while its menu is open; ☰ open is the
        # standard close control (spec s5, R-11): surface-2, no outline.
        self.assertIn("border: 2px solid #a3c45e;", rule('#LibraryActionsButton[value="1"]'))
        close = rule('#SidebarButton[value="1"]')
        self.assertIn("background-color: #1d222a;", close)
        self.assertIn("border: 1px solid #1d222a;", close)
        pressed = rule('#SidebarButton[value="1"][pressed="true"]')
        self.assertIn("background-color: #34191b;", pressed)
        self.assertIn("border-color: #d0574d;", pressed)
        # The search field: the page colour, a line border, radius 3 (spec section 1).
        search = rule("#LibraryWrapper #SearchBox")
        for declaration in ("background-color: #0d1014;", "border: 1px solid #2c333d;", "border-radius: 3px;"):
            self.assertIn(declaration, search)

    def test_track_table_hides_bpm_lock_and_uses_one_dark_selection(self):
        PATCH.apply(self.skin)
        styles = (self.skin / "style.qss").read_text()
        block = styles.split(PATCH.STYLE_BEGIN, 1)[1].split(PATCH.STYLE_END, 1)[0]
        def rule(selector):
            self.assertEqual(block.count(selector + " {"), 1, selector)
            return block.split(selector + " {", 1)[1].split("}", 1)[0]
        indicator = rule("#LibraryWrapper #LibraryBPMButton::indicator")
        for declaration in ("width: 0px;", "height: 0px;", "image: none;"):
            self.assertIn(declaration, indicator)
        table = rule("#LibraryWrapper WTrackTableView")
        # The mockups' selected row: deck 1 at 32% over the page colour.
        self.assertIn("selection-background-color: #263b51;", table)
        self.assertIn("selection-color: #e4e7ec;", table)
        self.assertIn("qproperty-focusBorderColor: #263b51;", table)
        # Spec 2b: every library table (Tracks, Load sample, the table beside
        # Sources) in the mockups' colours (layout.css .mxl-tbl/.mxl-row): #000
        # rows, --mx-surface #161a20 alternate rows, --mx-text, and the dark
        # selection. It overrides Pioneered's #32323c stripes, white text and
        # light selection, which come earlier in the file.
        rows = rule("#LibraryWrapper QTableView")
        for declaration in ("background-color: #000000;", "alternate-background-color: #161a20;",
                            "color: #e4e7ec;", "selection-background-color: #263b51;",
                            "selection-color: #e4e7ec;"):
            self.assertIn(declaration, rows)
        self.assertNotIn("#32323c", re.sub(r"/\*.*?\*/", "", block, flags=re.S))
        # The header's empty area past the last section (after TITLE's edge is
        # dragged narrower) takes the sections' --mx-surface-2, as the mockups'
        # full-width header row does, not Qt's default #efefef. Only the track
        # table header: no bare QHeaderView rule that would reach other headers.
        header = rule("#LibraryWrapper WTrackTableViewHeader")
        self.assertEqual(header.strip(), "background-color: #1d222a;")
        self.assertIn("background-color: #1d222a;",
                      rule("#LibraryWrapper WTrackTableViewHeader::section"))
        self.assertNotRegex(re.sub(r"/\*.*?\*/", "", block, flags=re.S), r"(?m)^[^{}]*QHeaderView")
        # The managed block is last, so it overrides the upstream light selection.
        self.assertTrue(styles.rstrip().endswith(PATCH.STYLE_END))

    def test_sources_menu_remains_reachable_beside_sidebar_toggle(self):
        PATCH.apply(self.skin)
        PATCH.apply(self.skin)
        root = ET.parse(self.skin / "library.xml")
        buttons = root.findall(".//PushButton")
        sources = [button for button in buttons
                   if button.findtext("ObjectName") == "LibrarySourcesButton"]
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0].findtext("Connection/ConfigKey"),
                         "[Library],show_sidebar_sources_menu")
        self.assertEqual(sources[0].findtext("Connection/EmitOnDownPress"), "true")
        self.assertEqual(sources[0].findtext("LeftClickIsPushButton"), "true")
        self.assertEqual(sources[0].findtext("NumberStates"), "1")
        parent = next(node for node in root.iter() if sources[0] in list(node))
        self.assertTrue(any(node.findtext("ObjectName") == "SidebarButton"
                            for node in parent.findall("PushButton")))

    def test_touch_navigation_keeps_tracks_visible_and_back_in_pane(self):
        PATCH.apply(self.skin)
        root = ET.parse(self.skin / "library.xml")
        sidebar = root.find(".//LibrarySidebar")
        self.assertEqual(sidebar.findtext("TouchNavigation"), "true")
        groups = root.findall(".//WidgetGroup")
        pane = next(g for g in groups if g.findtext("ObjectName") == "SidebarWrapper")
        self.assertEqual(pane.findtext("Size"), "260p,0me")
        self.assertEqual(pane.findtext("Layout"), "vertical")
        back = pane.find("Children/PushButton")
        self.assertEqual(back.findtext("ObjectName"), "LibraryBackButton")
        self.assertEqual(back.findtext("Size"), "0me,48p")
        connections = back.findall("Connection")
        self.assertEqual(connections[0].findtext("ConfigKey"), "[Library],sidebar_back")
        self.assertEqual(connections[1].findtext("BindProperty"), "enabled")
        self.assertEqual(connections[1].findtext("ConfigKey"),
                         "[Library],sidebar_can_go_back")
        table = next(g for g in groups if g.find("Children/Library") is not None)
        self.assertEqual(table.findall("Connection"), [])
        self.assertEqual(pane.findtext("Connection/BindProperty"), "visible")
        toolbar = next(g for g in groups if g.findtext("ObjectName") == "SidebarContainer")
        self.assertEqual(list(toolbar.find("Children"))[-1].findtext("ObjectName"),
                         "SidebarButton")

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

    def test_effect_toggle_routes_master_without_changing_depth(self):
        PATCH.apply(self.skin)
        root = ET.parse(self.skin / "effect.xml")
        button = root.find(".//PushButton")
        keys = ["".join(key.itertext()) for key in button.findall("Connection/ConfigKey")]
        self.assertEqual(keys, ["[EffectRack_EffectUnit_Effect],enabled",
                                "[EffectRack_EffectUnit],group_[Master]_enable"])
        self.assertNotIn(",meta", (self.skin / "effect.xml").read_text())
        connections = button.findall("Connection")
        self.assertEqual(connections[0].findtext("ConnectValueToWidget"), "true")
        self.assertEqual(connections[1].findtext("ConnectValueToWidget"), "false")

    def test_track_number_uses_mixxx_property_and_registered_tooltip(self):
        PATCH.apply(self.skin)
        label = ET.parse(self.skin / "deck.xml").find(".//TrackProperty")
        self.assertEqual(label.findtext("Property"), "trackNumber")
        self.assertEqual(label.findtext("TooltipId"), "track_title")

    def test_changed_upstream_effect_or_deck_fails_before_writing(self):
        for name, old, new in (("effect.xml", "group_[Master]", "group_[Channel1]"),
                               ("effect.xml", "],meta", "],super1"),
                               ("deck.xml", "<Elide>right", "<Elide>left")):
            with self.subTest(name=name, old=old):
                path = self.skin / name
                original = path.read_text()
                path.write_text(original.replace(old, new))
                before = {p: p.read_bytes() for p in self.skin.iterdir()}
                with self.assertRaisesRegex(ValueError, "pinned Pioneered"):
                    PATCH.apply(self.skin, self.config)
                self.assertEqual(before, {p: p.read_bytes() for p in self.skin.iterdir()})
                self.assertFalse((self.skin / ".mixpi-touch-original").exists())
                path.write_text(original)

    @unittest.skipUnless(os.environ.get("PIONEERED_TEST_SKIN"), "pinned upstream checkout optional")
    def test_pinned_upstream_skin(self):
        skin = self.path / "upstream"
        shutil.copytree(os.environ["PIONEERED_TEST_SKIN"], skin,
                        ignore=shutil.ignore_patterns(".git", ".mixpi-touch-original"))
        PATCH.apply(skin, self.config)
        first = {name: (skin / name).read_bytes() for name in
                 ("library.xml", "style.qss", "effect.xml", "deck.xml", "tab.xml")}
        PATCH.apply(skin, self.config)
        self.assertEqual(first, {name: (skin / name).read_bytes() for name in first})
        for path in skin.rglob("*.xml"):
            ET.parse(path)
        actions = [button for button in ET.parse(skin / "library.xml").findall(".//PushButton")
                   if button.findtext("ObjectName") == "LibraryActionsButton"]
        self.assertEqual(len(actions), 1)
        toggle = next(button for button in ET.parse(skin / "effect.xml").findall(".//PushButton")
                      if button.findtext("ObjectName") == "EffectToggle")
        self.assertEqual(len(toggle.findall("Connection")), 2)
        self.assertNotIn(",meta", "".join(toggle.itertext()))
        # The depth meter keeps its read-only meta connection.
        self.assertIn(",meta", "".join(ET.parse(skin / "effect.xml").find(".//VuMeter").itertext()))


if __name__ == "__main__":
    unittest.main()
