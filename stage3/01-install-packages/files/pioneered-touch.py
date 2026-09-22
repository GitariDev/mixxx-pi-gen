#!/usr/bin/env python3
"""Apply the MixxxPi touch customizations to a copy of the pinned Pioneered skin.

Usage: python3 pioneered-touch.py /path/to/Pioneered [--config /path/to/mixxx.cfg]
Stop Mixxx before using --config: Mixxx writes its in-memory settings on exit.
The first originals are retained in SKIN/.mixpi-touch-original/ and CONFIG's
adjacent .before-mixpi-touch file. Reapplying updates the managed style block.
This helper does not select a skin, restart Mixxx, or change the running process.
"""

import argparse
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET


ASSETS = Path(__file__).resolve().parent
STYLE_BEGIN = "/* MixxxPi touch BEGIN */"
STYLE_END = "/* MixxxPi touch END */"
BUTTON_BEGIN = "<!-- MixxxPi touch actions BEGIN -->"
BUTTON_END = "<!-- MixxxPi touch actions END -->"
LIBRARY_SETTINGS = {"RowHeight": "34", "Font": "Sans Serif,-1,17,5,50,0,0,0,0,0"}

BUTTON = """              <!-- MixxxPi touch actions BEGIN -->
              <PushButton>
                <ObjectName>LibraryActionsButton</ObjectName>
                <Size>96p,40p</Size>
                <NumberStates>2</NumberStates>
                <State><Number>0</Number><Text>Actions</Text></State>
                <State><Number>1</Number><Text>Actions</Text></State>
                <Connection>
                  <ConfigKey>[Library],show_track_menu</ConfigKey>
                  <EmitOnDownPress>true</EmitOnDownPress>
                </Connection>
              </PushButton>
              <!-- MixxxPi touch actions END -->
"""


def remove_managed(text, begin, end):
    if text.count(begin) != text.count(end) or text.count(begin) > 1:
        raise ValueError(f"Malformed managed block: {begin}")
    return re.sub(r"[ \t]*" + re.escape(begin) + r".*?" + re.escape(end) + r"\n?",
                  "", text, flags=re.DOTALL)


def patch_library(source):
    source = remove_managed(source, BUTTON_BEGIN, BUTTON_END)
    root = ET.fromstring(source)
    if len(root.findall(".//Library")) != 1:
        raise ValueError("Expected the pinned Pioneered Browse library layout")
    anchor = re.compile(r"(?m)^([ \t]*)<PushButton>\s*<ObjectName>SidebarButton</ObjectName>")
    if len(anchor.findall(source)) != 1:
        raise ValueError("Expected one Pioneered Show/Hide sidebar button")
    result = anchor.sub(lambda match: BUTTON + match.group(0), source)
    ET.fromstring(result)
    return result


def patch_styles(source):
    if "#LibraryWrapper" not in source:
        raise ValueError("Expected Pioneered's LibraryWrapper styles")
    source = remove_managed(source, STYLE_BEGIN, STYLE_END)
    # The upstream width: 0 also needs removing. Merely appending a height
    # override leaves the horizontal bar unusable.
    source = re.sub(
        r"#LibraryWrapper QScrollBar:horizontal\s*\{\s*height:\s*0;\s*width:\s*0;\s*\}\s*",
        "", source)
    styles = "\n\n".join((ASSETS / name).read_text().strip() for name in
                           ("pioneered-menus.qss", "pioneered-touch.qss"))
    return source.rstrip() + f"\n\n{STYLE_BEGIN}\n{styles}\n{STYLE_END}\n"


def patch_config(source):
    """Preserve all unrelated Mixxx INI lines, their case and their ordering."""
    sections = list(re.finditer(r"(?m)^\[([^\]\r\n]+)\][ \t]*\r?$", source))
    libraries = [section for section in sections if section.group(1) == "Library"]
    if len(libraries) > 1:
        raise ValueError("Multiple [Library] configuration sections")
    if not libraries:
        return source.rstrip() + "\n\n[Library]\n" + "".join(
            f"{key} {value}\n" for key, value in LIBRARY_SETTINGS.items())
    section = libraries[0]
    following = [item.start() for item in sections if item.start() > section.start()]
    end = following[0] if following else len(source)
    block = source[section.end():end]
    for key, value in LIBRARY_SETTINGS.items():
        line = re.compile(r"(?m)^" + re.escape(key) + r"[ \t]+[^\r\n]*$")
        if len(line.findall(block)) > 1:
            raise ValueError(f"Multiple [Library] {key} settings")
        if line.search(block):
            block = line.sub(f"{key} {value}", block)
        else:
            block = "\n" + f"{key} {value}" + block
    return source[:section.end()] + block + source[end:]


def apply(skin, config=None):
    # Validate every input and construct every output before changing any file.
    outputs = {
        skin / "library.xml": patch_library((skin / "library.xml").read_text()),
        skin / "style.qss": patch_styles((skin / "style.qss").read_text()),
    }
    ET.parse(skin / "skin.xml")
    if config:
        outputs[config] = patch_config(config.read_text())
    backup = skin / ".mixpi-touch-original"
    backup.mkdir(exist_ok=True)
    for path, output in outputs.items():
        original = (Path(str(config) + ".before-mixpi-touch") if path == config
                    else backup / path.name)
        if not original.exists():
            shutil.copy2(path, original)
        if path.read_text() != output:
            path.write_text(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skin", type=Path)
    parser.add_argument("--config", type=Path, help="Mixxx config; stop Mixxx before applying")
    args = parser.parse_args()
    try:
        apply(args.skin, args.config)
    except (OSError, ValueError, ET.ParseError) as error:
        parser.exit(1, f"Pioneered touch patch failed: {error}\n")
    print(f"Pioneered touch patch ready: {args.skin}")
    if not args.config:
        print("Set Library RowHeight=34 and Font=Sans Serif,-1,17,5,50,0,0,0,0,0 "
              "in the stopped Mixxx configuration for larger table rows.")


if __name__ == "__main__":
    main()
