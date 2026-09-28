# Mix Pi touchscreen utilities

The Speaker, Settings and USB → Pi windows use a shared native GTK 3 design.
This extends the rig’s Pioneer/Pioneered DJ theme to its utilities. It is an
original interface inspired by DJ equipment; it uses no Pioneer logos or assets.

## Review and direction

The previous screens had equally weighted actions, duplicate Settings entries
for the same speaker window, separate Start and Stop controls always available,
and transfer details presented as a single paragraph. The new hierarchy makes
mode, source, destination and the next action visible independently.

- Settings groups eight distinct destinations into Playback, Connections and
  Files & System. Each shortcut has a short explanation. It uses the full-width
  desktop layout rather than the old 640×340 floating panel.
- Speaker mode uses one state-dependent Start/Stop button. Spotify and Bluetooth
  instructions sit side by side; output selection and volume have their own
  section. Pairing/output controls are unavailable until speaker mode is on.
  Refresh checks outputs again after hardware changes and keeps an unapplied
  choice if that device is still connected.
- USB → Pi separates the selected drive, copy summary, destination, and transfer
  state. Progress has readable percentages. Completion means checksum
  verification succeeded; Open copy becomes available only after success.

## Surface and color

| Role | Color |
| --- | --- |
| Background | `#101216` |
| Panels | `#1b2027` |
| Controls | `#272e38` |
| Primary text | `#f4f6f8` |
| Supporting text | `#b7c1cd` |
| Primary action / ready | `#ffbb55` with `#101216` text |
| Successful / active state | `#79dfac` |
| Error | `#ffaaaa` |
| Keyboard focus | `#75cfff` |

The specified text/status pairs measure at least 8.1:1 against their panels;
primary action text measures 11.2:1. Disabled controls are intentionally muted.

Flat dark panels, tight geometry and restrained amber accents connect the
utilities to a DJ deck. Status always includes words; color never carries the
meaning alone. No decorative meters imply audio playback or signal strength.

## Typography and touch

Use the installed DejaVu Sans font: 24 px screen titles, 16 px controls/body,
14 px supporting text, and 12 px uppercase section labels. Primary controls are
at least 48 px high, with spacing between them. Native drop-down rows are at
least 44 px. Buttons have an explicit keyboard focus outline.

The physical screen is 800×480. The layout is verified at **800×412** to allow
for both the 36 px Waybar and a 32 px Sway tab strip. Headers and bottom actions
stay visible; the central area can scroll for longer messages or smaller
windows. Normal, empty, error, low-space and completion states fit without
scrolling at the tested size. Long output names/paths ellipsize; the destination
path has a tooltip and the completed folder can be opened directly.

## Behavior and recovery

Speaker status and mode operations run off the GTK main thread. A fresh state
check precedes a DJ-to-speaker switch. If Mixxx is open, a labelled confirmation
explains that playback stops; **Keep playing** is the default. Audio backend
handoff, saved routing and Starlight main-channel isolation are unchanged.

USB discovery, planning, copying and verification also run in a worker. Source
and copy controls are disabled during a transfer; Cancel stays reachable.
Closing during work requests safe cancellation and leaves the window open until
cleanup finishes. Refresh resets stale progress/errors. Copy and verification
continue to use the existing no-overwrite, source-preserving backend.

## Implementation

`stage3/02-desktop/files/bin/mixpi_ui.py` owns the shared CSS and widgets and is
installed beside the helper scripts by `04-run.sh`. No web runtime or new
production package is needed. CLI media operations still work without GTK.

Native UI tests are in `tests/test_touch_ui.py`. They use real GTK widgets with
fixture audio state and temporary USB files, sharing one GTK application host
inside the test process. The existing backend tests exercise transfer integrity
and audio-routing behavior. Run on Debian with Python GI, GTK 3, Xvfb, xauth,
D-Bus, DejaVu fonts, jq and a C++ compiler:

```sh
MIXPI_UI_SCREENSHOTS=output/ui-review \
  dbus-run-session -- xvfb-run -a -s '-screen 0 800x480x24' \
  python3 -m unittest discover -s tests -v
```

The optional upstream Pioneered fixture still requires `PIONEERED_TEST_SKIN`.
GTK tests skip on hosts without GTK/display support. These checks do not prove
physical touch accuracy, audible playback, phone pairing or a new image boot.
On September 28 the redesign was deployed over SSH and all three screens were
visually checked on the physical Pi at 800×412, with empty UI logs. Audio service
PIDs, library inventory/receipt, and Mixxx profile hashes were unchanged. The
database quick check passed. No new playback, pairing, real USB transfer or
reboot was exercised. Local deployment evidence: `deploy/ui-20260928/RESULTS.md`.

The subsequent Pair phone check exposed GTK's distinct `messagedialog` CSS
node: the original selector left its background light while styling text white.
The shared theme now covers that node, and notices/confirmations have explicit
titles and a Sway floating rule so they stay centered above the utility window.
A native regression test measures actual rendered text/background contrast.
The fix was installed on the Pi and the actual Pair phone button was exercised:
the instructions were readable, Bluetooth was discoverable/pairable for 180
seconds, and the Audio Sink role was present. Phone-side acceptance/audio
remains a user check. Evidence: `deploy/ui-20260928/dialog-fix/`.

## References used

- [Open Design repository](https://github.com/nexu-io/open-design) and its
  [design-system package model](https://github.com/nexu-io/open-design/tree/main/design-systems):
  keep the visual contract and reusable implementation together.
- [Open Design HUD reference](https://github.com/nexu-io/open-design/blob/main/design-systems/hud/DESIGN.md):
  fast state recognition and purposeful status color. Its dense cockpit
  typography and decorative treatment were not adopted for a small touchscreen.
- [AlphaTheta XDJ-AZ](https://alphatheta.com/en/product/all-in-one-dj-system/xdj-az/black/):
  visual reference for dark DJ hardware, grouped functions and screen hierarchy.
- W3C [contrast guidance](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html)
  and [target-size guidance](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html)
  inform contrast and touch spacing. This native UI review is not a full WCAG audit.
