# MixPi UI redesign spec, 2026-11-17 (orchestrator draft for the prototype and the plan)

Status: proposal. Nothing here is approved. The owner's words in
`docs/ideas/UI-REDESIGN-REQUEST-20261117.md` win over this file. The prototype
artifact (`prototype/mixpi-ui.html` in this folder) draws this spec next to a
re-creation of the current UI.

Screen: 800×480 landscape, touch. Mixxx fills it when the desktop bar is hidden
(the default since F-14); with the desktop bar shown Mixxx gets 800×444 and the
waveform rows shrink first. Every touch target is at least 48 px in both
directions. Lists scroll with a visible scroll bar at least 24 px wide (kept as
the scroll method), plus touch drag (F-6).

## 0. Facts the design rests on (checked in source)

- Starlight mapping (pinned Mixxx `3ebac449`, `res/controllers/Hercules DJControl Starlight.midi.xml`
  and `Hercules-DJControl-Starlight-scripts.js:76-77`): per deck Play, Cue, Sync, PFL, 4 pads,
  jog (touch = scratch, Shift = seek), volume, tempo, bass, filter; crossfader; Shift; Vinyl.
  Pad modes: hot cue 1-4, beat loop 1/2/4/8, FX (pads 1-3 = effect 1-3 enable, pad 4 = deck
  routing), sampler. **Sampler mode triggers `[Sampler1..4]` from deck A pads and
  `[Sampler5..8]` from deck B pads, and the script raises `num_samplers` to 8.** The skin
  shows only 4 (`mixpi-performance.py` manifest sets `[Master],num_samplers` 4). No browse
  encoder and no load button: library work stays on the touch screen.
- Tracks from removable media are already copied to a RAM cache on load when CACHE MB is on
  (`mixxx-removable-ram-cache.patch`, `/dev/shm/mixpi-track-cache`). Handover can build on it.
- Today LOAD / EJECT opens a dialog whose "Load" opens a drive as a library source and whose
  "Eject…" is off (controlled media OFF). The owner says load is normally automatic and eject
  is the safe, deliberate action.

## 1. Shell

Top bar, 48 px, always visible in Mixxx:

| Item | Size | Notes |
|---|---|---|
| DECKS · TRACKS · FX · SAMPLER tabs | 84/84/72/96 × 48 | Active tab: filled accent, not only a border. One active at a time. |
| USB chip (replaces LOAD / EJECT) | 150 × 48 | USB icon + drive name + state: none / ready / in use / scanning NN% / ejecting / safe to remove. Tap opens Media. |
| ● REC | 72 × 48 | Unchanged behaviour. |
| Settings (gear icon) | 48 × 48 | Opens Settings. |
| CPU | 56 × 48 | Unchanged. |

Big, deep-context screens (Sources, Media, Load sample, Settings) cover everything under the
top bar, with a 48 px header whose ✕ sits where Tracks' ☰ sits. Quick things (Actions menu,
Choose pad, Eject confirm, pad menu) are sheets over the current page. Transport rows on
Decks, FX and Sampler are the same; Tracks swaps them for LOAD/CUE.

## 2. Decks (performance)

| Row | Height | Content |
|---|---|---|
| Waveforms | 2 × 128 | Left column 92 px: deck badge (deck colour), key, MT/Q state. Waveform 708 px. |
| Deck info | 72 | Per deck 400 px. Row 1 (28): badge, title, artist (dim), MASTER/SYNC chips. Row 2 (44): time (tap: elapsed ↔ remaining), BPM box, tempo %, key chip. A "ON PI" chip shows when the deck plays a handover copy. |
| Overview | 48 | Played part dimmed, hot cue ticks in their colours, loop region. |
| Transport | 56 | Per deck (395 px, 4 px gaps): KEY 48, Q 48, SYNC 60, LOOP 60, CUE 76, ▶ 83. All 48 px tall. |

LOOP opens the deck tool panel over the waveforms (focus mode, waveform moves to the
overview row, as today). New: tabs **Loop · Jump · Cues**. Loop = today's 12 sizes plus
½, ×2, Exit, Reloop. Jump = beat jump 1/2/4/8/16/32 back and forward. Cues = hot cues 1-8
(tap sets or jumps, Clear mode). These carry the XDJ-AZ pad modes the Starlight lacks.

## 3. Tracks (browse)

| Row | Height | Content |
|---|---|---|
| Toolbar | 48 | ☰ (Sources; turns into ✕ while Sources is open) · source crumb ("MANTACORE › Friday") · search · ✎ (Actions). |
| List | rest | Header 32, rows 48. Columns from Arrange (F-7/F-8 widths kept). Scroll bar 24 px. |
| Overview | 40 | Both decks, for cueing. |
| Bottom | 56 | LOAD 1 · CUE 1 · LOAD 2 · CUE 2. LOAD shows the deck's current title under the label; it stays off while that deck plays (unchanged rule). |

✎ Actions menu: Load to Deck 1 · Load to Deck 2 · Load to a sampler pad… · Arrange columns ·
Full Mixxx menu. ☰ and ✎ are 48 × 48 icon buttons with no text.

## 4. Sources (full screen)

Opened by ☰. Covers everything under the top bar. The ☰ becomes ✕ in the same spot.

- Left rail 264 px: one 64 px tile per source, with icon, name and a sub-line:
  MANTACORE (USB · rekordbox · 58.6 GB), This Pi (Tracks, Playlists, Crates),
  Recordings, History, Folders (Computer). Drives appear first, in plug-in order.
- Right pane: the chosen source's contents as 56 px rows with a chevron, a crumb with Back,
  and track counts. Tapping a list opens it in Tracks and closes Sources.
- ✎ Edit (top right) opens the show/hide and order list (today's checkboxes and Up/Down)
  as its own step, so browsing never mixes with editing.

## 5. Media and eject (Pioneer model)

Media screen (USB chip) shows one card per drive: name, size, "rekordbox export found",
status pill, and actions **Eject** (primary, 56 px), Browse, Copy to Pi, Scan.

- **Insert:** the drive mounts read-write (owner decision) and shows in the top bar and in
  Sources. Mixxx reads it only when you open it: no library scan starts by itself. (Owner
  question: Ready / Ask / Scan.)
- **Eject:** a sheet lists what uses the drive (decks, pads, scan, copy). "Eject" stops the
  scan, moves each loaded or playing track and pad sample to Pi storage, closes every file,
  flushes, unmounts and powers the port down. The chip then says **Safe to remove**.
- **Handover:** a deck playing from the drive keeps playing from the Pi copy ("ON PI" chip).
  The copy is deleted when that deck or pad loads something else or ejects (the "transition
  out"), and any copies left at boot are deleted.
- Controlled media stays OFF until the owner approves this design.

## 6. Scan bar

A 48 px strip over the overview row (never over the transport row): "Scanning · <file name
only> · 1,240 of 3,050", a progress bar, **Hide** and **Cancel**. Hide saves the choice; later
scans show only the USB chip with a progress ring and NN%. Settings › Media turns the bar back on.

## 7. Sampler: 8 pads and a separate Load sample screen

- Sampler tab: header 48 (LOAD SAMPLE, bank "Saved" state) and 8 pads in 2 rows of 4, about
  196 × 115 each (pads 1-4 = Starlight deck A pads, 5-8 = deck B pads). Each pad: tap area
  (name on up to 2 lines, length, progress while playing) and a 48 px strip with ■ Stop and
  ⋯ (Load here, Empty pad). An empty pad opens Load sample for itself.
  Below: a compact 40 px deck strip (title, time, BPM, key), the overview and the full transport.
- LOAD SAMPLE opens **Load sample**, full screen and separate from Tracks: source chips
  (Samples, This Pi, MANTACORE, Recordings), search, 52 px rows with a 48 px preview button,
  and one **Load to pad…** button. It opens **Choose pad**: the 8 pads with what each holds;
  playing pads are off. Tapping a pad loads it and returns to Sampler.
- The bank is saved on change (section 9).

## 8. FX and Settings

- FX: same parts restyled: route chips DECK 1 / DECK 2 / MASTER, MIX slider with a 48 px
  handle, three effect cards (selector, depth, ON), each labelled with its Starlight pad.
- Settings: left rail Playback · Interface · Media · Advanced; right pane as today. A small
  "Saved" note confirms each change. Media holds: on insert (Ready/Ask/Scan), scan progress
  (Bar/Icon), handover store, and Copy to Pi.

## 9. Saving and shutdown (C-2, C-3)

- Save `mixxx.cfg` and the sampler bank shortly after each change (debounced, atomic write).
- Clean quit on SIGTERM (C-2 `a8a86fa`), and the session stops Mixxx before power-off/reboot.

## 10. Visual language

Dark stage palette, one accent per role: deck 1 blue, deck 2 amber, active state lime
(today's tab colour), danger red, safe green. Radius 6. Inter-like sans for labels,
tabular numbers for time/BPM. No text below 13 px; labels 15-17 px; time and BPM 22-26 px.
