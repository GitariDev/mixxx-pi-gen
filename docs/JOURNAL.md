# Mixxx Pi journal

## Master overview

- **Goal:** a compact, touchscreen-first, standalone-feeling DJ system built on a Raspberry Pi and Mixxx.
- **Current rig:** Raspberry Pi 4B; generic 7-inch 800×480 DSI touchscreen; USB mouse; Hercules DJControl Starlight as the current/temporary DJ controller; portable USB storage; external speaker; portable power under test.
- **Software:** this image builds the Mixxx 2.5 branch on 64-bit Raspberry Pi OS Trixie, starts Sway, and launches Mixxx fullscreen. The Pioneered small-screen skin is bundled; the current screen layout is user-reported as the Pioneer/Pioneered view.
- **Working:** image boots, 7-inch touch display and mouse work, Mixxx opens, and full Preferences/settings access is no longer blocked by the lack of a keyboard.
- **Known friction:** finding removable music, cable/power clutter, confirming clean master/headphone audio routing, and selecting a more capable controller.
- **Next milestone:** define and test a controller upgrade while keeping the base image device-agnostic; see [`CONTROLLER-UPGRADE.md`](setup/CONTROLLER-UPGRADE.md).
- **Longer-term direction:** support replaceable DJ controllers, audio interfaces, storage, displays, and auxiliary control surfaces without baking a single device into the core image.

## 2026-08-19

- Established this journal and the query-friendly `docs/skills/` runbook directory.
- Reviewed the image-builder repository and confirmed:
  - Mixxx is built from the `2.5` branch.
  - Sway launches Mixxx on workspace 1 and forces the main window fullscreen.
  - `wvkbd` provides the touch keyboard from the Waybar keyboard icon.
  - `udevil`/`udiskie` are included for removable media and `PrivateMounts=no` is set for udev.
  - PipeWire audio, `qpwgraph`, Nautilus, `wdisplays`, and controller udev rules are included.
  - The Pioneered and `pi_dj` small-screen skins are bundled during the build.
- Reviewed the three setup photos and recorded component identifications in [`setup/HARDWARE.md`](setup/HARDWARE.md).
- Reviewed recent Mixxx Pi task history:
  - Initial HDMI install and smoke-test runbook was created.
  - The image was verified and tested via USB boot on a Raspberry Pi 4B.
  - An early USB flash attempt disconnected partway through; stable power and direct connections remain important.
  - Fullscreen skin Settings was initially mistaken for Preferences; `Ctrl+P` is the reliable path.
  - The controller was identified as a Hercules DJControl Starlight.
  - A 5 V fan may share the Pi's 5 V/GND rails with the display, subject to power budget and correct pin selection.
- Created initial plans for playlists, incoming tracks, effects, and an auxiliary control surface.
- Research conclusion: Mixxx can support this direction well through playlists/crates, Auto DJ, keyboard mappings, MIDI/HID mappings, JavaScript mapping logic, effect chains, and command-line startup options.
- Incorporated the supplied six-page **DJ Skills & Moves List** into the notebook:
  - adopted a consistent four-hot-cue scheme suited to the Starlight's four pads per deck;
  - added runbooks for phrasing/cues, fades/EQ handoffs, loops/tempo matching, sampling, and recorded practice;
  - expanded incoming-track acceptance and playlist selection criteria;
  - preserved the learning order: selection/cues, fades, loops/tempo, then sampling.
- **Setup update:** the Preferences/settings and no-keyboard issue is resolved. A USB mouse now provides reliable navigation.
- **Controller direction:** the Hercules Starlight is the current baseline, but an upgrade/replacement is planned. The target model is not selected yet.
- Added a connection-agnostic controller upgrade brief so future controllers, audio devices, storage, displays, and auxiliary inputs remain replaceable rather than hard-coded.

## Entry template

## YYYY-MM-DD

- **Changed:**
- **Tested:**
- **Learned:**
- **Problem:**
- **Idea:**
- **Next:**
