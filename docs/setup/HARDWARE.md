# Hardware inventory

Identifications below combine the photos from 2026-08-19, recent task history,
and repository configuration. Confidence is stated where a label is not fully
visible.

## Confirmed or high-confidence components

| Component | Identification | Evidence and notes |
| --- | --- | --- |
| Computer | Raspberry Pi 4 Model B | Board layout matches a Pi 4B; recent setup task explicitly established a Pi 4B. Exact RAM capacity is not visible. |
| Display | Generic 7-inch DSI display, 800×480 | The rear PCB is printed `7inch DSI Display 800*480 Pixel`. It uses the Pi display ribbon plus GPIO power leads. Exact brand/model is not legible. |
| DJ controller | Hercules DJControl Starlight | Brand and Starlight layout are visible; recent task history independently identified it. Compact two-deck controller with integrated audio connections. |
| Navigation | USB mouse | Added and working; resolves the immediate settings/Preferences access problem without relying on the touch keyboard. Exact model is not important. |
| Speaker | Harman Kardon speaker | Badge is visible. The exact Onyx Studio generation is unconfirmed from these angles. |
| Portable power | USB power bank | Display reads about 44% in one photo. Brand, capacity, and supported output profile are unconfirmed. |
| Music/system storage | USB flash drive(s) | USB boot and removable music were used in recent setup work; exact current role of each attached drive must be labelled physically. |

## Visible assembly

- The Pi is mounted directly behind the display and connected by a DSI ribbon.
- GPIO jumper leads appear to power the screen from the Pi header.
- The Pi is exposed; fit a stable stand/enclosure before mobile use so cables cannot lever against the USB-C, micro-HDMI, DSI, or GPIO connections.
- Cable congestion is already significant. Label both ends of `POWER`, `BOOT`, `MUSIC`, `CONTROLLER`, `MASTER`, and `HEADPHONES` cables.
- A loose cooling fan/heatsink solution appears in the work area, but installation is not confirmed.

## Power and cooling notes

- Use a stable Pi 4 supply near 5.1 V / 3 A for development. A power bank is only suitable after a sustained load test confirms no undervoltage, USB resets, or audio dropouts.
- The display and a **5 V** fan can use different physical pins on the same 5 V/GND rails: 5 V on physical pin 2 or 4; ground on a ground pin such as 6, 9, 14, 20, 25, 30, 34, or 39.
- Never use a normal 3.3 V GPIO output as a fan power source.
- Run at least a 30-minute two-deck test with the controller, display, boot storage, and audio connected before treating a power arrangement as performance-ready.

## Questions to resolve

- Exact Pi RAM capacity and boot-storage device.
- Display manufacturer/product link and whether touch uses DSI or a separate USB link.
- Power-bank brand, capacity, 5 V continuous-current rating, and whether all ports share one limit.
- Exact Harman Kardon model and whether audio is wired, USB, or Bluetooth.
- Whether headphone cue and master are both routed through the Starlight's audio interface.
- Which controller will replace/upgrade the Starlight and whether it will provide the primary audio interface.
- Final fan model, voltage, current draw, and mounting direction.

## Connection policy

- Treat the Starlight as one supported device, not the identity of the image.
- Keep Mixxx's controller mapping selected at runtime; do not install one user's controller ID as a universal default.
- Identify devices by stable properties such as vendor/product and ALSA/PipeWire names, never by a transient `card 1`, `/dev/sdX`, or USB-port number.
- Keep boot storage, music storage, controller, audio output, mouse, and optional auxiliary surface logically separate even if a powered hub is later used.
- Prefer class-compliant USB MIDI/HID and USB Audio devices with existing Mixxx mappings and Linux support.
- Make controller-specific mappings additive files with their own test checklist and rollback path.
- Re-run the complete audio/controller/power smoke test whenever the connection topology changes.
