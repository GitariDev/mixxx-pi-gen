# Spotify and Bluetooth speaker mode

Tap **Speaker** in the top bar, then **Start speaker mode**. If Mixxx is open,
confirm the switch: Mixxx closes normally and saves its settings, then the
speaker audio services start. The Pi still boots into Mixxx by default.

## Spotify and Jam

1. Connect your phone and the Pi to the same Wi-Fi.
2. In Spotify on your phone, open **Devices** and choose **Mix Pi**.
3. Play music. To share the queue, choose **Start a Jam** and invite friends.

Spotify Premium is required for this Connect receiver and for hosting a Jam.
The Pi runs go-librespot; browsing and Jam invitations stay in the Spotify
phone app. This is an unofficial Spotify Connect receiver.

### Controls on the Pi

Tap **Spotify controls** at the bottom of the Speaker screen for **Previous**,
**Play/Pause**, **Next** and the Spotify volume, with the current track shown
above them. They act on whatever is playing on Mix Pi, including a Jam's shared
queue, and the phone shows the change. Drag the volume slider or tap **−** / **+**
for 5% steps; this is the same Spotify volume the phone controls, separate from
the output levels in **Volume & mixer**.

The controls open as a window in the centre of the screen, with the Speaker
screen blurred and dimmed behind it. Tapping outside does nothing; only its
**Close** button dismisses it. The button is available while Speaker mode is
on. Until a phone has chosen **Mix Pi** the window says **No phone connected**
and its controls are unavailable.

## Audio output and volume

Open **Speaker outputs**, tick one or more outputs, then tap outside the menu
and press **Use outputs**. For simultaneous playback, select **Starlight · Main
1–2**, **Starlight · Headphones 3–4**, and/or **Pi · 3.5 mm jack**. **Refresh** detects changes after connecting
a device and preserves pending selections. At least one output must be selected.

Selections are remembered across speaker sessions. If a selected device is
missing at startup, the available selections are used; if all are missing, an
available output is chosen. Reconnect the device and select it again, or restart
speaker mode to restore the saved selection. Multiple outputs use a stereo
combined device with latency compensation; timing still depends on the attached
speakers.

With the Hercules DJControl Starlight attached, the initial output is
**Starlight · Main 1–2**. This maps stereo audio only to its main output channels;
select **Starlight · Headphones 3–4** to also send music to its headphone jack.
Both Starlight jacks and the Pi jack can play together without Mixxx. The physical
headphone knob controls the headphone jack, including a subwoofer connected
there. The headphone route starts at 50% when first created; adjust its level
in **Volume & mixer**. It carries the full stereo mix, so a connected sub uses
its own crossover. The raw four-channel device is hidden to avoid ambiguous
routing; old raw-device preferences migrate to the main output.

Tap **Volume & mixer** for volume, mute, playback streams and device profiles.
Select **All Output Devices** at the bottom if the virtual Starlight output is
hidden by the hardware-only filter. The phone and **Spotify controls** both
set the Spotify volume.
The first speaker session starts with moderate output and Spotify volume.

## Bluetooth audio from a phone

1. Start Speaker mode and tap **Pair phone**.
2. In the phone's Bluetooth settings, select **Mix Pi**.
3. Accept the pairing request on the Pi, then play audio on your phone.

The Pi is discoverable for three minutes after tapping Pair phone. Previously
paired phones can reconnect while Speaker mode is active. Bluetooth audio uses
the selected speaker outputs. Pause Spotify before playing Bluetooth audio if
you do not want both streams audible together.

## Return to DJing

Tap **Mixxx** in the top bar or **Back to Mixxx** on the Speaker screen. This
stops Spotify and the speaker audio services before starting Mixxx, releasing
the controller for Mixxx's direct ALSA audio. **Settings → Mixxx preferences** opens
the full Preferences dialog; select **Sound Hardware** for DJ output routing.
These controls are also accessible through **Settings**.

## Implementation and checks

- `mixpi-speaker` provides the touchscreen controls; `mixpi-speaker-control`
  handles mode changes, output selection and timed pairing.
- `mixpi-speaker.target` starts private PipeWire, WirePlumber, PulseAudio
  compatibility and Spotify Connect services. The build's existing masks for
  ordinary PipeWire services remain in place, and speaker services are not
  enabled at boot.
- go-librespot 0.10.3 ARM64 is pinned with its SHA-256 in
  `stage3/02-desktop/05-run.sh` and installed as `/usr/local/bin/go-librespot`.
  Only the per-user `mixpi-spotify.service` runs the player. Its control API
  listens on `127.0.0.1:3678` only; `mixpi-speaker-control spotify
  status|toggle|next|previous|volume N` is the single caller.
- The user-selected outputs are stored as a list of stable sink names in
  `~/.config/mixpi/speaker.json`. Spotify credentials, once paired, stay in
  `~/.local/state/mixpi-spotify/` with a restrictive service umask.
- Live configuration backups from installation are under
  `~/.local/state/mixpi-backups/speaker-20260925/` on the Pi.

On 2026-09-25, live checks confirmed Spotify zeroconf publication, Bluetooth
Audio Sink support and timed discovery, a silent PCM stream through Starlight
main channels only, shutdown of all speaker services when returning to Mixxx,
and Mixxx reopening its saved Starlight ALSA output. Screenshots confirmed the
Speaker controls, desktop audio settings and Mixxx Sound Hardware dialog fit
800×480. The phone subsequently authenticated Spotify and played tracks; the live stream
was confirmed flowing through the stereo Starlight sink into main channels 1–2.
Audible output, Jam participation and phone Bluetooth pairing still need user
confirmation. A complete image rebuild and reboot were not performed.

All 16 touchscreen/build/navigation and speaker tests passed. Service unit
validation and `git diff --check` also passed. Evidence is saved locally in
`deploy/speaker-20260925/`.

Sources: [Spotify Jam](https://support.spotify.com/au/article/jam/),
[go-librespot](https://github.com/devgianlu/go-librespot),
[Raspotify](https://github.com/dtcooper/raspotify) (the receiver until October 10),
[WirePlumber Bluetooth](https://pipewire.pages.freedesktop.org/wireplumber/daemon/configuration/bluetooth.html).

## September 28 interface update

The source now uses the shared dark DJ utility theme, a single Start/Stop
control, separate phone-source instructions, and an explicit output section.
Pairing and output selection are enabled only while Speaker mode is on.
Settings removes the duplicate audio shortcut and groups tools by task.
See [the design and validation notes](../design/DESIGN.md). These new screens
were tested in a Linux GTK virtual display, then deployed to the live Pi over
SSH on September 28. All three windows fit 800×412 with empty logs. Speaker
mode remained active through Starlight, without restarting its audio services.
The existing copied library and Mixxx profile were preserved. Live evidence
and rollback details are in `deploy/ui-20260928/RESULTS.md`.

## September 30 multiple-output update

The output menu now has touch-sized checkboxes and **Use outputs** applies the
selection. Two or more outputs create a PipeWire `module-combine-sink` with
stereo routing and latency compensation. Internal combine/remap streams are
excluded when moving music, and obsolete combined devices are removed after
switching. Existing single-output preferences remain readable.

Validation: 12 routing/preference tests, 14 GTK interaction/layout tests on an
isolated headless Pi display, and 11 touchscreen/build checks passed. A private
PipeWire/WirePlumber session on the Pi verified simultaneous output links,
selection reporting, route reuse and cleanup. The installed controls were
checked at 800×412 with an empty application log; existing audio service PIDs,
default output and music-stream routing were unchanged. Physical speaker timing
still needs listening verification. Evidence is in
`deploy/speaker-multi-20260930/`; the previous installed files are backed up at
`~/.local/state/mixpi-backups/speaker-multi-20260930-203838/` on the Pi.

## September 30 jack-routing correction

Live signal measurements showed the raw Starlight choice received music only on
front channels 1–2; headphone channels 3–4 were silent. Separate stereo remaps
now expose both physical jacks with explicit channel mappings and remixing off.
Adding these routes preserves the physical device's mixer levels. The Pi jack
already received music and was unmuted at 40%; it was raised to 60% for listening
verification. The headphone output was enabled at 50%, alongside the existing
main output.

All 14 routing/preference tests and 14 GTK tests passed. An isolated PCM test
confirmed headphone-only playback reaches rear channels while front channels
remain silent. Live PCM measurements then confirmed music on all four Starlight
channels and the Pi output together. These are software monitor measurements;
audible output still requires the user's listening check. Audio services and the
Spotify stream were preserved during installation. Evidence and diagnostics are
in `deploy/speaker-jacks-20260930/`, with the prior installation and settings at
`~/.local/state/mixpi-backups/speaker-jacks-20260930-205410/` on the Pi.

Listening follow-up: the Pi jack was actually unplugged, so its audible output
was not tested. The user confirmed the Starlight headphone/sub output works
when isolated at 75%. Both Starlight outputs were then enabled and saved
(main 100%, headphones 75%), and the Speaker screen refreshed to show those
two selections. Software monitoring confirmed simultaneous signal on channels
1–2 and 3–4, with no signal on the unused Pi output. These percentages describe
the verified live session.

## Manual speaker timing

On the Speaker screen, apply your output selection, then tap **Fine adjustment**.
The Audio sync menu shows only the outputs currently playing. Each has **−10**,
**−1**, **+1** and **+10** millisecond buttons, covering 0–500 ms. Increase the
delay on the output you hear **first**. For example, if the Pi jack sounds late,
leave it at zero and delay the Starlight output until a steady beat sounds like
one hit. Starlight main and headphone/sub outputs have independent adjustments.

Tap **Apply & save** to hear and remember the values. Applying can briefly
interrupt audio while the route changes. **Reset** sets the displayed values to
zero; **Apply & save** removes those delays. **Close** discards unapplied edits.
The button is unavailable while output selection has unapplied changes.
Saved timing returns when Speaker mode starts, including after an output is
reconnected. This controls Speaker mode; Mixxx uses its separate ALSA settings.
A mismatch that keeps growing needs further clock/scheduling investigation.

Implementation: nonzero offsets insert stereo `module-ladspa-sink` routes using
`swh-plugins`' `delay_1898` / `delay_l` filter before the selected outputs.
Automatic device-latency compensation remains enabled. Intentional sample delay
is not advertised as device latency, so compensation does not cancel it.
Zero bypasses the filter. Internal routes stay hidden from the output picker;
settings use `delays_ms` in `~/.config/mixpi/speaker.json`. Changing timing
preserves saved disconnected outputs and the existing jack mixer levels.
New routes are created before switching, and failed creation removes the new
filters while leaving the old route and saved settings intact.

The image package list now includes `swh-plugins`; an existing Pi also needs
that package installed before using nonzero delays. The optional signal test
runs entirely on private PipeWire sockets with hardware discovery disabled:

```sh
MIXPI_AUDIO_INTEGRATION=1 python3 -m unittest discover -s tests -p test_speaker_audio.py -v
```

October 3 validation: 22 routing/preference tests, 17 GTK tests and 11
build/navigation checks passed. A private ARM64 Debian session using PipeWire
1.4.2 measured 1, 50 and 500 ms offsets within one sample (0.021 ms) in both
stereo channels, with reset, route reuse and filter cleanup verified. The real
GTK menu fits 760×350 with all three rows visible. Evidence and the prepared
installation package are in `deploy/speaker-sync-20261003/`.

After user approval, the controls and `swh-plugins` were installed on the Pi on
October 3. Fine adjustment was opened with the Pi jack and both Starlight jacks
visible, initially at zero delay. The actual screen fits 800×480 with no logged
application errors. Audio service PIDs, default output, music-stream routing and
saved settings were unchanged during installation. The previous helpers,
Sway configuration and settings are backed up at
`~/.local/state/mixpi-backups/speaker-sync-20261003-164504/`. The user's listening
adjustment and audible alignment remain to be confirmed.

## October 10 Spotify controls

The Speaker screen gained a **Spotify controls** button beside Fine adjustment,
leaving the three sections of the screen as they were. It opens a modal dialog
window that Sway floats in the centre of the screen without a title bar. Close
requests from the window manager are ignored, so only **Close** dismisses it.
While open it re-reads the player every two seconds, so tracks changed from a
phone or by Jam guests appear there.

Sway 1.10 cannot blur what is behind a window, so the Speaker screen blurs
itself: `mixpi_ui.backdrop()` renders the window to a picture, softens it with
three shrink-and-enlarge passes (about 30 ms on the Pi), dims it and lays it
over the screen until the dialog closes. The top bar is a separate Waybar
surface and stays sharp. `python3-gi-cairo` is now listed explicitly for this;
the Pi already has it through Blueman.

librespot 0.8.0 has no local control interface (no MPRIS, no API; checked on the
Pi), so the receiver changes to go-librespot, which adds a loopback HTTP API and
lists Jam among its features. The service keeps the device name, speaker type,
320 kbps, loudness normalisation, 50% first volume, PulseAudio output and
remembered login, and registers through the Pi's Avahi daemon. Its state lives
in the same private `~/.local/state/mixpi-spotify/` folder. The phone has to
choose **Mix Pi** once after the change, because the saved login is in a
different format.

Validation: 126 tests passed on the Pi in a throwaway headless Sway (2 optional
fixtures skipped), including 6 new control cases and 4 new GTK cases at 800×412;
the Mac run skips GTK. The exact service command was started on the Pi from
`/tmp` as **Mix Pi check** for a few seconds: it created its private state
folder, registered with Avahi, was visible from the Mac's Spotify Connect
browse, and answered every control command with the no-phone state. The dialog
was also opened natively on Wayland in that headless Sway with the image's
window rules: 600×243, centred at 100,118 on 800×480, no title bar, and the
screen sharp again after Close. The live Speaker session and its librespot
stream were left running throughout. Screenshots are in
`deploy/spotify-controls-20261010/`.

### Live installation

Installed on the Pi on October 10 from commit `d4897a0`: the pinned
`go-librespot` binary, `mixpi-spotify.service`, `mixpi-speaker`,
`mixpi-speaker-control`, `mixpi_ui.py` and the Sway rule for the dialog, with a
Sway reload. The phone then chose **Mix Pi** and played through go-librespot
into the combined Starlight main + headphone output. On the physical screen the
dialog opened centred over the blurred Speaker screen, stayed open after a tap
outside it, and showed the playing track and the phone's volume changes within
two seconds. A volume command sent from the Pi was accepted by the live session.

**Do not restart `mixpi-spotify.service` on its own.** `mixpi-speaker.target`
requires it, so systemd extends the restart to the target and, through
`PartOf=`, to PipeWire, WirePlumber and the Pulse service. The Starlight
remaps, combined output and timing filters that Speaker mode loads at start
are lost and the default output falls back to the raw four-channel device. The
first install attempt did exactly this; its safety check noticed and rolled the
files back. The second stopped Speaker mode with `mixpi-speaker-control stop`,
installed, ran `mixpi-speaker-control start` to rebuild the saved outputs, and
reapplied the output levels recorded before the first attempt (starting Speaker
mode resets the headphone route to 50%). Outputs, default device, levels and
`speaker.json` then matched the session as it was before installation.

The first status the dialog showed, before the phone had fully reconnected,
was a session at 100% Spotify volume with nothing playing; it settled at the
configured 50% and then followed the phone. Worth a glance at the slider the
first time Speaker mode starts with a remembered login.

Still to check by hand: tapping **Previous**, **Play/Pause** and **Next**
during playback, dragging the slider, and a Jam with guests. The user journal
is not kept on this Pi, so `journalctl --user -u mixpi-spotify` shows nothing.
Backups: `~/.local/state/mixpi-backups/spotify-controls-20261010-162806/`
(first attempt, with the reference session) and `…-162921/` (the install).
The librespot login files remain in `~/.local/state/mixpi-spotify/` beside
go-librespot's `state.json`. Evidence: `deploy/spotify-controls-20261010/`.
