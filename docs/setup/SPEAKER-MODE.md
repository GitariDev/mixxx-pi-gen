# Spotify and Bluetooth speaker mode

Tap **Speaker** in the top bar, then **Start speaker mode**. If Mixxx is open,
confirm the switch: Mixxx closes normally and saves its settings, then the
speaker audio services start. The Pi still boots into Mixxx by default.

## Spotify and Jam

1. Connect your phone and the Pi to the same Wi-Fi.
2. In Spotify on your phone, open **Devices** and choose **Mix Pi**.
3. Play music. To share the queue, choose **Start a Jam** and invite friends.

Spotify Premium is required for this Connect receiver and for hosting a Jam.
The Pi runs librespot from the Raspotify package; browsing and Jam invitations
stay in the Spotify phone app. This is an unofficial Spotify Connect receiver.

## Audio output and volume

The Speaker screen has an **Speaker output** selector. Choose an output and tap
**Use output**. **Refresh** detects changes after connecting a device.

With the Hercules DJControl Starlight attached, the initial output is
**Starlight · Main 1–2**. This maps stereo audio only to its main output channels;
it does not send the speaker mix to headphone channels 3–4. The raw four-channel
Starlight output is also available for manual routing. Built-in Pi audio and
other outputs detected by PipeWire can be selected.

Tap **Volume & mixer** for volume, mute, playback streams and device profiles.
Select **All Output Devices** at the bottom if the virtual Starlight output is
hidden by the hardware-only filter. The phone also controls Spotify volume.
The first speaker session starts with moderate output and Spotify volume.

## Bluetooth audio from a phone

1. Start Speaker mode and tap **Pair phone**.
2. In the phone's Bluetooth settings, select **Mix Pi**.
3. Accept the pairing request on the Pi, then play audio on your phone.

The Pi is discoverable for three minutes after tapping Pair phone. Previously
paired phones can reconnect while Speaker mode is active. Bluetooth audio uses
the selected speaker output. Pause Spotify before playing Bluetooth audio if
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
- Raspotify 0.48.3 / librespot 0.8.0 ARM64 is pinned with its SHA-256 in
  `stage3/02-desktop/05-run.sh`. Its system daemon stays masked. Only the
  per-user `mixpi-spotify.service` runs the player.
- The user-selected output is stored by stable sink name in
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
[Raspotify](https://github.com/dtcooper/raspotify),
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
