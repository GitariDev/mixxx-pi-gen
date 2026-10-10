# Spotify, Bluetooth and audio settings: chat handoff

Written on **2026-09-28** to preserve the context of the Codex task
**Add Spotify and audio settings** before the user deletes it from the wrong
project. Implementation and live Pi testing took place on **2026-09-25**.
This page is a historical record, not a fresh inspection of the Pi.

## User request and agreed scope

The user wanted Spotify on the Mix Pi so they could start a Jam and play music
without DJ mixing, while continuing to use the Hercules DJControl Starlight
as the audio output. They also wanted accessible audio settings.

The user initially chose phone control with playback through the Pi and
Starlight, then asked whether both phone control and direct Pi use were possible.
The final request broadened the feature into **Speaker mode**: make the Pi
appear as a speaker, expose audio settings and output selection, and add
Bluetooth if possible. The user confirmed they have Spotify Premium.

The implemented workflow uses Spotify on the phone for browsing, playback and
Jam invitations. The Pi receives Spotify Connect audio and provides local
speaker controls. A full Spotify browsing app on the touchscreen was not
installed. Bluetooth provides a second route for phone audio.

## Project and device context

- Correct Codex project: **DJ Skill Builder**.
- Repository: `/Users/gitaritirima/Documents/Workspace/Personal Projects/mixxx-pi-gen`.
- The original chat was accidentally under **panelai**, but the speaker code
  and project documentation were saved in the Mix Pi repository.
- Device: Raspberry Pi 4 running Debian 13 Trixie, with an 800×480 touchscreen,
  Sway/Waybar, Mixxx 2.5.6 and the Pioneered skin.
- Audio device: Hercules DJControl Starlight, four playback channels at
  44.1 kHz. Main output uses channels 1–2; headphone output uses 3–4.
- SSH used `pi@mixxxpi.local` and the existing Mac key
  `~/.ssh/mixpi_ed25519`. No key or Spotify credential contents are included here.

Inspection found that ordinary PipeWire/WirePlumber services were deliberately
masked in this image. Mixxx held the Starlight directly through ALSA. Merely
adding an audio-settings application would not have released the device for
Spotify. This led to explicit switching between DJ and Speaker modes.

## What was executed

### Live installation

Installed the official ARM64 **Raspotify 0.48.3** package, containing
**librespot 0.8.0**, plus `pavucontrol` for desktop audio settings and `wtype`
for the Mixxx Preferences shortcut. Existing PipeWire, WirePlumber, PulseAudio
utilities and Bluetooth audio libraries were reused.

The Raspotify system daemon was masked before installation. Spotify runs as
the desktop user's service only during Speaker mode. The package version and
SHA-256 were pinned in the image build script for reproducible future installs.

Backups of the existing launchers, Sway configuration and Waybar configuration
were saved on the Pi at:

`~/.local/state/mixpi-backups/speaker-20260925/`

### Touchscreen controls and switching

- Added **Speaker** to the top bar and speaker/audio access in **Settings**.
- Added a Speaker screen with **Start Speaker mode**, **Audio settings**,
  **Pair phone · Bluetooth**, **Stop Speaker mode**, **Back to Mixxx**,
  **Mixxx audio preferences**, an output selector, **Use output**, and **Refresh**.
- Starting Speaker mode requests confirmation if Mixxx is open, then sends a
  normal close request so Mixxx can save its state. It waits for Mixxx to exit
  and reports a problem rather than force-killing it.
- Returning through the Mixxx launcher stops the speaker services before
  opening Mixxx, releasing the ALSA device for DJ use.
- The Pi remains configured to boot into Mixxx; Speaker mode is started on demand.
- The Preferences shortcut focuses or opens Mixxx and sends `Ctrl+P`. During
  live verification, Mixxx's menu-hiding prompt was answered **Always show**,
  and the Sound Hardware preferences were then opened successfully.

### Audio and Bluetooth

Speaker mode starts its own PipeWire, WirePlumber and PulseAudio compatibility
services, while the image's original service masks remain in place.

Spotify advertises the device name **Mix Pi**. Its player uses the selected
PulseAudio output, 320 kbps streaming, volume normalization, an initial Spotify
volume of 50%, and no audio-file cache. Credential caching uses the desktop
user's private state directory.

A virtual stereo sink, `mixpi_starlight_main`, routes left/right only to the
Starlight's main channels 1–2 with remixing disabled. The custom picker labels
it **Starlight Main 1–2**. Built-in audio and other detected outputs remain
selectable. Output selection uses stable names rather than ALSA card numbers.
The output-change code avoids redirecting the virtual sink's own internal
stream back into itself.

Bluetooth was unblocked and powered on, given the alias **Mix Pi**, and made
discoverable for three minutes when pairing is requested. The existing Blueman
agent handles pairing approval on the Pi. WirePlumber advertises the Bluetooth
Audio Sink role while Speaker mode is active. Stopping Speaker mode ends the
pairing advertisement; it does not deliberately disconnect keyboards or mice.

### Source files

Paths below are relative to the Mix Pi repository.

| File or group | Purpose |
| --- | --- |
| `stage3/02-desktop/files/bin/mixpi-speaker` | GTK Speaker screen |
| `stage3/02-desktop/files/bin/mixpi-speaker-control` | Mode switching, output selection, Starlight routing and timed Bluetooth pairing |
| `stage3/02-desktop/files/bin/mixpi-audio-preferences` | Open/focus Mixxx and open Preferences |
| `stage3/02-desktop/files/bin/mixpi-mixxx` | Stop speaker audio before returning to Mixxx |
| `stage3/02-desktop/files/bin/mixpi-settings` | Add speaker/audio and Mixxx preferences launchers |
| `stage3/02-desktop/files/systemd/user/mixpi-speaker.target` | Group the on-demand speaker services |
| `stage3/02-desktop/files/systemd/user/mixpi-audio*.service` | Private PipeWire, WirePlumber and PulseAudio compatibility services |
| `stage3/02-desktop/files/systemd/user/mixpi-spotify.service` | Spotify Connect player |
| `stage3/02-desktop/files/i3.conf` | Touchscreen workspace/window rules |
| `stage3/02-desktop/files/waybar/config` and `style.css` | Top-bar Speaker control |
| `stage3/01-install-packages/00-packages` | Audio-settings and shortcut dependencies |
| `stage3/02-desktop/02-run.sh` and `05-run.sh` | Install speaker units and the pinned Spotify package in future images |
| `tests/test_speaker.py` and `tests/test_touchscreen_build.py` | Speaker handoff/routing and existing navigation/build checks |
| `docs/setup/SPEAKER-MODE.md` | User-facing operating guide |

Live helper scripts are installed in `/usr/local/bin/`; user service units
are in `~/.config/systemd/user/`. Output selection is stored in
`~/.config/mixpi/speaker.json`; Spotify authentication state is stored in
`~/.local/state/mixpi-spotify/` with a restrictive service umask.

## Verification and observed outcome

Completed on September 25:

- **16 tests passed:** 11 touchscreen/build/navigation/SSH checks and 5 speaker
  checks. Speaker tests covered refusing an unapproved Mixxx close, disconnected
  outputs, moving music without moving the channel-remap stream, main-channel
  routing and cleanup after a failed service start.
- Sway configuration validation, systemd unit validation and `git diff --check`
  passed.
- Screenshots showed the Speaker controls, desktop audio panel and Mixxx
  Sound Hardware preferences fitting the touchscreen.
- A silent PCM stream opened the Starlight at 44.1 kHz, with PipeWire links
  confirming front-left/front-right routing and no headphone-channel links.
- Returning to Mixxx stopped all five speaker target/services, and Mixxx
  reacquired the Starlight through ALSA.
- Bluetooth was powered and discoverable as **Mix Pi**, with Audio Sink support
  advertised. An initial power-on Busy response was handled by adding a bounded
  retry after unblocking the adapter.
- Spotify advertised discovery, authenticated from the user's phone and loaded
  tracks. The live uncorked Spotify stream was confirmed feeding
  `mixpi_starlight_main`, then the Starlight hardware.

The Pi was left in Speaker mode with the Starlight selected. Once phone playback
was observed, it was left running. This describes the end of that session;
it does not establish the Pi's current mode or playback state.

The user was asked to confirm audible playback, but no explicit confirmation
arrived in this chat. Software routing and track loading are verified;
hearing the sound is not. A Jam with another participant, actual Bluetooth
phone pairing/playback, a full image rebuild and a reboot were not verified.

## Evidence and recovery context

Local evidence is in `deploy/speaker-20260925/`:

- `verification.json`
- `mixpi-speaker-final.png`
- `mixpi-audio-settings.png`
- `mixpi-preferences-confirm.png`

The `deploy/` directory is ignored by Git, so these files are local evidence.
The implementation summary and outstanding checks are preserved in tracked docs.
The last screenshot preceded a final output-label cleanup.

The original chat made source changes and installed them live without making
a commit or pushing. When this handoff was written on September 28, repository
history showed the work included in commit **`3bf0bed`**,
**Save current speaker mode and touchscreen work before UI redesign**.
That later commit was not executed by this chat. Additional UI work was already
present in the repository; it was left untouched during this documentation task.

## Follow-up and chat relocation

On September 28 the user asked to move this chat into **DJ Skill Builder**.
The project was found, but the available task tools did not provide changing
an existing task's project. Attempting to inspect Codex through Computer Use
was rejected because that tool cannot control the Codex app. The chat was
therefore not moved, copied or deleted.

The user then requested this handoff document so the misplaced chat could be
deleted without losing the requirements and execution history. For later work,
start with this page and the [Speaker mode operating guide](../setup/SPEAKER-MODE.md).
The remaining acceptance checks are audible Starlight playback, a shared Jam,
Bluetooth phone pairing/playback, and persistence through an image build/reboot.
Before live changes, inspect the current device and repository because later
work may have changed the UI or service implementation.
