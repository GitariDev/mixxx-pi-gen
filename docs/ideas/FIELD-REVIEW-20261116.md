# Field review — 64 GB test card, 2026-11-16

The owner booted the 64 GB test card (pi-gen 3beff6e, built 2026-11-15, Mixxx
2.5.6+rmodified-1, `/usr/bin/mixxx` sha256 46b86cf5…) and did a short run. The
owner's comments come first. The SSH walkthrough on the same card follows.

Local evidence (gitignored): `deploy/recovery-20261116/pi-review/`, which holds:
- `shots/*.png`: 800×480 grim captures, numbered in walkthrough order
- `owner-photos/`: the owner's four photos
- `testcard-mixxx.cfg` and `testcard-mixxx-log.txt`
- `tools/`: pinned SSH, screenshot and virtual-touch tools, with a README

## Owner comments (verbatim intent)

1. **Recording** seemed to work. *Verified:* `~/Music/Mixxx/Recordings/2026-11-16_16h03m51s.wav` (36.5 MB) and its `.cue` are on disk.
2. **Actions** worked perfectly, but the UI formatting is clunky. So is the saving of browse settings and how they look. Test Browse, its screens and its settings.
3. **On Tracks/Browse**, replace the per-deck CUE and PLAY buttons with **LOAD** and **CUE**. LOAD loads the highlighted track into that deck.
4. **Waveforms and beat grids** look slightly different from EOS, which reads as a visibility regression. Find what changed and, if it performs well, revert the main Deck 1 and Deck 2 views to the EOS look.
5. **Settings → Advanced → Back** does not work. Mixxx **Preferences** should open from Advanced.
6. Copy two samples to the Pi for sampler testing. *Done:* `~/Music/Samples/03 - Times' up.flac` and `MergeFX Sample Sound 101.wav`, with matching sha256. Pad 1 = "Times' up" and Pad 2 = SNARE9 are loaded through Sampler → LOAD SAMPLE.

## SSH walkthrough findings

The walkthrough used real touch injection through a uinput touchscreen, with a grim capture after each step.

### Confirmed bugs
- **B1 Advanced Back is dead** (`17`–`22`):
  - Tapping Back anywhere on its width leaves Advanced open.
  - FPS buttons on the same panel respond (`20-fps45`), and "Advanced…" (0→1) works.
  - Back is a 2-state toggle on `[MixPi],settings_advanced` that should send 0. Its generated XML (`mixpi-performance.py` around lines 272–281) looks correct, so something resets the value or swallows the press.
  - Suspects: the `stacked` (StackAll) z-order inside `MixpiWaveArea`/`MixpiSettings`, or the press re-entering after the hide. Reproduce in the native Qt harness before fixing.
  - The robust fix is explicit set-value buttons (Back sets 0, Advanced sets 1), as the FPS choices already do, instead of toggles.
- **B2 No Preferences entry point:** Settings has no way to open Mixxx's preferences dialog (owner item 5).
- **B3 Touch-drag on the Sources list activates items instead of scrolling** (`05`):
  - A drag opened PLAYLISTS. Only dragging the 8 px scrollbar scrolls (`06`–`08`).
  - The highlight stayed on TRACKS while the Playlists page showed.
- **B4 Deck time readouts are clipped:** `-3:14` and `-2:45` run under the BPM box on Decks and Sampler (`00`, `24`).

### Waveform delta versus EOS (owner item 4)
These waveform settings are identical on EOS and the test card: `[Waveform] WaveformType 17` (RGB GLSL), `DefaultZoom 3`, `ZoomSynchronization 1`, `VSync 0`. Both render on V3D 4.2. `waveform.xml`, `waveforms.xml` and every `<Visual>`/`<Overview>` definition are byte-identical. No Mixxx patch touches the renderers.

What changed:
- **Info column** `MixpiWaveInfo` went from 100 px to 136 px. The waveforms are 36 px narrower, and the key label is wider (paired Camelot notation).
- **Beat spacing at 102 BPM** (Frontin' The Best) is about 52 px per beat on the test card (`35-decks-zoom.png`) against about 86 px in the Nov 9 EOS-era capture (`deploy/recovery-20261109/mixpi-loop-closed.png`). The test card looks about 1.65× more zoomed out, which gives denser white full-height grid lines and a spikier waveform.
  - Caveat: that EOS capture was taken right after the zoom ± tests, so it is not a clean baseline.
- **Generated skin:** EOS `skin.xml` is sha 180733c8… and its exact copy is `deploy/recovery-20261110/full-native-build/native-skin/skin.xml`. Its generator is `deploy/recovery-20261111/field-implementation-tranche1/before/stage3/01-install-packages/files/mixpi-performance.py` (sha 69547cec…).
- **Next step:** do a controlled A/B on the test card. Use the same track, position and zoom, with the EOS skin.xml swapped in temporarily and then restored. Measure px/beat, waveform width and height, and grid contrast. Then restore the EOS deck view if FPS and CPU allow.

### Tracks / Browse (owner items 2, 3)
- The library table fills only about 550 of 770 px; the rest of the header is a blank grey block (`01`).
- The BPM column carries Mixxx's bpm-lock checkbox as a black square, which is noise on touch.
- The selected row is a light grey bar with a separate cell outline.
- **Computer/Browse** (`09`–`12`, `29`):
  - It opens with Mixxx's default wide columns (PREVIEW, FILENAME, ARTIST, TITLE, ALBUM, GENRE, COMMENT, DURATION…), so you have to scroll sideways.
  - The preview headphone and play icons do nothing useful, because the preview deck is hidden.
  - Folder rows are plain text with no icons.
  - **No browse header state is persisted.** `mixxxdb.settings` has `header_state_pb` for library and rekordbox but none for browse, so every visit starts from the default.
  - REMOVABLE DEVICES listed a stale `SD-BACKUP` entry next to MANTACORE. `/media/pi` holds only MANTACORE.
- **Arrange columns dialog** (`04`): light-theme Qt dialog with 17 px rows, the wrong style and size for touch.
- **Bottom bar on Tracks/FX/Sampler** shows per-deck CUE and PLAY. Owner wants LOAD and CUE (item 3).

### Other screens
- **Load/Eject dialog** (`25`) shows internal wording to users: "No tracked use; not eject clearance", "No retained transfer result". Eject is disabled because controlled media is OFF, as intended.
- **Sampler** (`24`, `31`–`34`):
  - LOAD SAMPLE opens Tracks with a "LOAD TO PAD 1–4 / DONE" bar, and both loads work.
  - The bottom deck readouts are clipped as in B4.
- **Loop panel** (`36`) runs in focus-fallback mode ("WAVEFORM BELOW"), with zoom ± beside the detail waveform. It works.
- **FX** (`23`) works. Slot 1 shows "SELECT EFFECT…".
- **Settings basic** (`15`): SETTINGS and DECKS tabs are both highlighted at the same time.

### System and audio
- **Audio:** `soundconfig.xml` routes only Master to `hw:3,0`, the Starlight output with 4 channels.
  - **No headphone/cue output is configured**, so pre-listening is impossible.
  - This is the deferred audio-handoff item. EOS's own sound profile should be copied from EOS read-only and compared.
- **Controller:** Starlight MIDI is loaded. The log has about 50 "not open for output" warnings (LED feedback) plus deprecated-key warnings.
- **GPU:** V3D, RGB (GLSL).
- **Resources:** about 2–3 % CPU in the Mixxx readout, 51.6 °C, `throttled=0x0`, 651 MB RAM used of 3.8 GB.
- **Appliance quieting candidates:**
  - ModemManager
  - obexd and mpris-proxy
  - blueman-applet, blueman-tray and an open blueman-manager window
  - nm-applet, swaync, udiskie
  - a stray `foot` terminal
- **Failures:** `xdg-desktop-portal-wlr.service` fails at every boot. `waybar.service` failed twice; the Settings "Show top bar" button still reports available.
- **Library:** 307 tracks (305 audio files under `~/Music/Backup` plus recordings).
