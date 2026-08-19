# Troubleshooting quick reference

**Aliases:** no audio, no display, crash, lag, USB reset, undervoltage, log,
recovery

| Symptom | First checks |
| --- | --- |
| Mixxx did not open | `Super+Enter`, run `mixxx`, inspect `/home/pi/.mixxx/mixxx.log`. |
| Preferences hidden | Open touch keyboard and press `Ctrl+P`; toggle fullscreen with `Super+F`. |
| USB music missing | Follow [`usb-media.md`](usb-media.md); start with `lsblk`, not formatting. |
| Controller missing | Connect before launch, run `lsusb`, restart Mixxx, then load mapping in Preferences. |
| No master/headphones | Run `aplay -l`; verify Mixxx Sound Hardware outputs and Starlight connections. |
| Wrong display mode | `Alt+D` → `wdisplays`; inspect `swaymsg -t get_outputs`. |
| Audio dropout/UI stutter | Remove hubs, use stable 5.1 V/3 A power, check cooling, reduce competing USB load, inspect logs. |
| Dialog appears behind fullscreen | Retry after `Super+F`; the bundled fullscreen helper should normally prevent this. |

## Performance-readiness test

- Analyze two known tracks, load both decks, and select the intended audio device.
- Exercise play/cue/seek/tempo/sync/crossfader/effects and headphone preview.
- Run two-deck playback for 30 minutes while watching for audio gaps, controller resets, overheating, undervoltage, storage errors, or display corruption.
- Shut down from the Waybar power menu before removing power.

