# Raspberry Pi HDMI installation and smoke-test plan

This project boots to Sway and starts Mixxx automatically. A touchscreen is not
required: use an HDMI display plus a USB keyboard and mouse for setup and
testing.

## Hardware

- Raspberry Pi 3, 4, 400, or 5 with the correct power supply and cooling
- Spare microSD card, 16 GB or larger
- HDMI cable/adapter and HDMI display
- USB keyboard and mouse
- Optional for the full test: DJ controller, USB audio interface/headphones,
  Ethernet, USB drive containing non-critical test music

## Installation checkpoints

1. Download the current nightly image and verify its SHA-256 digest.
2. Insert the spare microSD card and identify its macOS `/dev/diskN` device by
   capacity and media name.
3. Unmount (do not eject) that exact disk, flash the image, and wait for writes
   to sync.
4. Eject the card, connect HDMI/keyboard/mouse to the Pi, insert the card, and
   power on. Allow at least 60 seconds for the first boot and filesystem resize.
5. Confirm Mixxx starts automatically and fills the HDMI display.

## HDMI and keyboard checks

- If the resolution is wrong, close Mixxx, press `Alt+D`, run `wdisplays`, and
  select a supported mode. For a permanent setting, add an `output` rule to
  `/home/pi/.config/sway/config` after identifying the display with
  `swaymsg -t get_outputs`.
- `Super+Enter` opens a terminal.
- `Super+F` toggles fullscreen for the focused window.
- Mixxx logs are at `/home/pi/.mixxx/mixxx.log`.

## Smoke test

1. Confirm HDMI remains stable at the selected resolution for 10 minutes.
2. In a terminal, inspect `swaymsg -t get_outputs`, `aplay -l`, and `lsusb`.
3. Import two test tracks from USB or `/home/pi`, analyze them, and load both
   decks.
4. Start playback, cue, seek, change pitch, crossfade, and verify waveforms are
   smooth.
5. Select the intended audio device in Mixxx and verify master/headphone output.
6. Connect the DJ controller, enable its mapping, and test every critical
   control.
7. Run a 30-minute two-deck playback test while checking for audio dropouts,
   display corruption, overheating/undervoltage, or crashes.
8. Shut down from the power menu before removing power.

## Recovery information

- Local image login: user `pi`, password `mixxx`. The touchscreen test build
  uses SSH keys for remote login; follow [SSH provisioning](docs/setup/TOUCHSCREEN-BUILD.md).
- If Mixxx does not appear, use `Super+Enter`, run `mixxx`, and inspect
  `/home/pi/.mixxx/mixxx.log`.
- Re-flashing destroys all data on the selected card; always re-check the disk
  identifier immediately before writing.
