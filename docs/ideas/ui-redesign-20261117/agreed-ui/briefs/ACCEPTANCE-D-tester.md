# Build D acceptance on the test card (tester brief)

Read `ACCEPTANCE-C-tester.md` (same folder) first: its card rules, safety rules, tools and hit map all hold, with the changes below. Build D (`ce2186c`, 50 patches) is installed in place. The orchestrator's conformance shots of build D are in `deploy/ui-redesign-20261117/acceptance-D/conformance/d*.png`. Write your evidence in `deploy/ui-redesign-20261117/acceptance-D/` (report `ACCEPTANCE.md`, `shots/`, `logs/`) and on the card in `/home/pi/uiD-20261118/tester/`. You change no code and make no commits.

Before you start, save the owner's state again: copy `mixxx.cfg`, `samplers.xml` and `effects.xml` to `/home/pi/uiD-20261118/owner-state/` while Mixxx runs. They are the files you restore at the end. Never touch `soundconfig.xml`.

Owner decisions since build C: spec `AGREED-UI-SPEC.md` section 2a, plan 12.5. **Fonts are build B's now, not the mockups'.**

## Checks (PASS / FAIL / BLOCKED with evidence)

### 1. What build D changed
1. **★ for the saved start** (`SidebarDefaultSource RekordboxFeature`, the owner's value; never rewrite it except by pressing ★ in a step that restores it):
   - With GANDER1 in, after a fresh start, TRACKS shows GANDER1's lists, the Sources menu's accent edge is on GANDER1, and Edit sources shows ★ and "TRACKS STARTS HERE" on the GANDER1 row.
   - Eject GANDER1 cleanly (Media page), Ctrl+Q, start: Tracks starts at This Pi and the edge is on This Pi. Plug it back (port toggle while unmounted).
   - The edge follows the source in view: open History from the menu, close and reopen the menu: the edge is on History.
2. **Edit sources child rows:** This Pi's lists (Tracks, Playlists, Crates, Auto DJ) and More's lists show indented under their source, with only ON/OFF. Switch Playlists ON, DONE, Ctrl+Q, start: still ON, and This Pi in the menu lists Playlists. Then switch it back OFF and check again after a restart (restore).
3. **Narrowed table fits:** with Sources open, the table shows TITLE, ARTIST, BPM and KEY with no sideways bar (This Pi › Tracks and inside GANDER1). Close the menu: the full-width columns come back as before. With Sources open, pick another list, Ctrl+Q, start: the full-width columns are unchanged. Load sample → SOURCES…: its table fits the same way.
4. **OPEN and BROWSE switch to Tracks:** from DECKS, SAMPLER and FX: USB chip → OPEN (or BROWSE) → Tracks with the TRACKS tab lit and GANDER1's tracks. ✕ on the Media page still goes back to the tab you came from.
5. **Fonts back to build B:** compare each spec screen with build B's shots (`deploy/ui-redesign-20261117/owner-review/s*.png`) for the font family, size and weight only. Check that no text is clipped, especially the Media page OPEN and EJECT, the Sources BACK and EDIT, the Settings rail, the pad buttons and the Clear samples rows.
6. **Loop panel with the desktop top bar shown (800×444):** Settings › Interface › SHOW TOP BAR, then the loop panel: all four rows are visible (EXIT LOOP and RELOOP included) and work (set 4, ½, ×2, EXIT LOOP, RELOOP). Hide the bar: at 800×480 the rows are 48 px again.
7. **Skin repairs:** the Clear samples list shows every loaded pad's row with no scroll bar (two pads), and a tap on a row's name ticks it. The Media page lights the USB chip and no tab.

### 2. Regression smoke
- A settings change in `mixxx.cfg` within 1 s; an effect change in `effects.xml` within 1 s and kept after `pkill -KILL -x mixxx`.
- Samples over a restart (Ctrl+Q and start): pads 1-2 kept.
- Two eject-and-replug cycles of GANDER1 with no sway or Mixxx crash; no udiskie pop-up; the ASK ping shows.
- REC 30 s gives WAV + CUE; F-4 86 ± 2 px per beat at 102 BPM; both decks plus one effect for 2 minutes: CPU readout and Mixxx's underrun counter (record both; build C: about 3.4 %, 0); `throttled=0x0`.

### 3. Restore the owner's state at the end
The same as build C's step 5, from `/home/pi/uiD-20261118/owner-state/`. Also check that `SidebarDefaultSource` is `RekordboxFeature` again and Playlists is OFF. GANDER1 stays plugged in and READY, with Tracks showing This Pi › Tracks when you finish (load the two tracks from there).

## Report
`acceptance-D/ACCEPTANCE.md`, with the same form as build C's. Reply with the counts, each FAIL in one line, the CPU and underrun numbers, and the final state.
