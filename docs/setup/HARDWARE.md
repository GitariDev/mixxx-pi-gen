# Hardware inventory

Identifications below combine the photos from 2026-08-19, recent task history,
and repository configuration. Confidence is stated where a label is not fully
visible.

## Confirmed or high-confidence components

| Component | Identification | Evidence and notes |
| --- | --- | --- |
| Computer | Raspberry Pi 4 Model B Rev 1.1, 4 GB | Confirmed over SSH on 2026-09-22 (about 3.7 GiB usable RAM). |
| Display | Generic 7-inch DSI display, 800×480 | The rear PCB is printed `7inch DSI Display 800*480 Pixel`. It uses the Pi display ribbon plus GPIO power leads. Exact brand/model is not legible. |
| DJ controller | Hercules DJControl Starlight | Brand and Starlight layout are visible; recent task history independently identified it. Compact two-deck controller with integrated audio connections. |
| Navigation | USB mouse | Added and working; resolves the immediate settings/Preferences access problem without relying on the touch keyboard. Exact model is not important. |
| Speaker | Harman Kardon speaker | Badge is visible. The exact Onyx Studio generation is unconfirmed from these angles. |
| Portable power | USB power bank | Display reads about 44% in one photo. Brand, capacity, and supported output profile are unconfirmed. |
| Music/system storage | USB flash drive(s) | USB boot and removable music were used in recent setup work; exact current role of each attached drive must be labelled physically. |
| Enclosure | Cardboard glassware box ("6PCS DIAMONDS") with the screen on a slanted top | 2026-11-08 photos; user measured 235 mm wide, 152 mm deep, 100 mm at the back (hinged, high) wall and 57 mm at the front (about 16°). The Pi hangs under the slant near the back edge, components facing in; a 7-port powered hub with per-port switches lies on the floor. Only a few cable holes. |
| Cooling | Stick-on aluminium heatsinks on the SoC, RAM and USB controller | 2026-11-08 photos. The masking tape around them was removed that day. Two fans in hand, not fitted: a 30 mm 5 V fan in a Pi 4 case lid (single 2-pin Dupont housing) and a 60 × 24 mm fan labelled 12 V 0.22 A (white 2-pin housing, pitch unknown). See the [cooling plan](../ideas/COOLING-PLAN.md). |

## Visible assembly

- The Pi is mounted directly behind the display and connected by a DSI ribbon.
- GPIO jumper leads appear to power the screen from the Pi header.
- The Pi is exposed; fit a stable stand/enclosure before mobile use so cables cannot lever against the USB-C, micro-HDMI, DSI, or GPIO connections.
- Cable congestion is already significant. Label both ends of `POWER`, `BOOT`, `MUSIC`, `CONTROLLER`, `MASTER`, and `HEADPHONES` cables.
- A loose cooling fan/heatsink solution appears in the work area, but installation is not confirmed.
- **2026-11-08:** the Pi and display now sit in a cardboard box with the screen on the slanted top; see Enclosure above. The box protects the connectors but traps heat.

## Power and cooling notes

- **Post-gig update, 2026-09-22:** the hub was used without its separate supply,
  adding peripherals caused cutouts, and the Starlight did not fully power up.
  The USB 3 extender is also suspect. Exact wiring and failure cause remain
  unconfirmed. See the [power action plan](../ideas/POST-GIG-PLAN.md#power-baseline)
  for a dedicated supply, accessible case USB-C connection and full-load test.
- **Connected test:** user confirmed the same hub was powering the Pi. A short
  two-deck Starlight test worked by the user's report; 21 power samples over
  about 3 minutes stayed at `throttled=0x0`, peaking at 76.4 °C while an SSH
  backup also ran. This did not complete the 30-minute endurance or extender
  comparison tests. Starlight master 1–2 and headphones 3–4 were saved at
  44.1 kHz; the current boot card is 14.8 GiB and replacement card 62.2 GB.
- Use a stable Pi 4 supply near 5.1 V / 3 A for development. A power bank is only suitable after a sustained load test confirms no undervoltage, USB resets, or audio dropouts.
- The display and a **5 V** fan can use different physical pins on the same 5 V/GND rails: 5 V on physical pin 2 or 4; ground on a ground pin such as 6, 9, 14, 20, 25, 30, 34, or 39.
- Never use a normal 3.3 V GPIO output as a fan power source.
- Run at least a 30-minute two-deck test with the controller, display, boot storage, and audio connected before treating a power arrangement as performance-ready.
- **Cooling, 2026-11-08:** idle in the closed box read 66.2–67.6 °C at 1.5 GHz
  with software GL and `throttled=0x0`. After the GPU fix it read 61.8–63.3 °C
  (box state **Unconfirmed**). With V3D, the calibrated model puts the sealed
  box at about 73 °C for two decks and 80 °C with a copy.
- **Fan plan:** the [cooling plan](../ideas/COOLING-PLAN.md) mounts the 60 mm fan
  outside the back wall at the SoC heatsink's height, blowing in. It runs from a
  hub port through a USB 5→9 V boost cable (about 0.32 A, nothing from the Pi).
  The 30 mm fan sits on the heatsink as the backup, on header pins 2 and 14
  through jumpers, because the display's fixed leads have pins 4 and 6.

### Cooling test log

One row per 30-minute two-deck run, logged with
[`tools/cooling-model/log-temps.sh`](../../tools/cooling-model/log-temps.sh)
(procedure in the [cooling plan](../ideas/COOLING-PLAN.md#beforeafter-test)).

| Date | Layout | Room °C | Peak °C | Mean last 10 min °C | Throttle flags | Log |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-11-08 13:02 | Sealed box, idle, software GL, tape on (not a run) | 25 (user default) | 67.6 | — | 0x0 | SSH spot check |

## Questions to resolve

- Display manufacturer/product link and whether touch uses DSI or a separate USB link.
- Power-bank brand, capacity, 5 V continuous-current rating, and whether all ports share one limit.
- Exact Harman Kardon model and whether audio is wired, USB, or Bluetooth.
- Separate headphone-cue listening check, beyond the saved Starlight routing.
- Which controller will replace/upgrade the Starlight and whether it will provide the primary audio interface.
- Which 5 V header pin the display uses, the SoC heatsink's height in the closed box, and a closed-box idle reading with V3D; see the [cooling plan](../ideas/COOLING-PLAN.md#open-questions).

## Connection policy

- Treat the Starlight as one supported device, not the identity of the image.
- Keep Mixxx's controller mapping selected at runtime; do not install one user's controller ID as a universal default.
- Identify devices by stable properties such as vendor/product and ALSA/PipeWire names, never by a transient `card 1`, `/dev/sdX`, or USB-port number.
- Keep boot storage, music storage, controller, audio output, mouse, and optional auxiliary surface logically separate even if a powered hub is later used.
- Prefer class-compliant USB MIDI/HID and USB Audio devices with existing Mixxx mappings and Linux support.
- Make controller-specific mappings additive files with their own test checklist and rollback path.
- Re-run the complete audio/controller/power smoke test whenever the connection topology changes.
