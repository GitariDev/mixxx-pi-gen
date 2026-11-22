# Build P acceptance on the test card (tester brief)

Read `ACCEPTANCE-O-tester.md` and acceptance O's `deploy/ui-redesign-20261117/acceptance-O/ACCEPTANCE.md` first. Their card rules, safety rules and tools hold. Then read `AGREED-UI-SPEC.md` **2e**, the J16 brief `J16-NJ-menu-place.md`, and the investigation `deploy/ui-redesign-20261117/investigation-R8-edge/REPORT.md` (its matrix and helpers). Build P is build O plus J16 only, installed in place (`deploy/ui-redesign-20261117/buildP-update/UPDATE-LOG.md`).

Write your evidence in `deploy/ui-redesign-20261117/acceptance-P/`. Record the start state (screen, mounts, decks, `mixxx.cfg` copy) and restore it at the end.

Rules as acceptance O, and: never tap CUE on a paused deck; never drag table columns; unload decks only with Alt+Shift+Left/Right while stopped.

## Checks (PASS / FAIL / BLOCKED). The edge is `#a3c45e` at x 483 of the row; a row without it reads `#161a20`.
1. **First OPEN after a start (the reproduced fault):** Ctrl+Q, start Mixxx, do **not** open ☰. Media › GANDER1 OPEN → Tracks; then ☰: inside "GANDER1 › rekordbox", edge on TRACKS (483, 174). Repeat once (2 of 2). Also once with BROWSE instead of OPEN after a fresh start.
2. **First OPEN after a start via the remount:** start Mixxx, no ☰, EJECT GANDER1 → OPEN (remount) → ☰: inside, edge on TRACKS.
3. **After load, play, pause, unload, page change:** from check 1's state, tap TRACKS, LOAD 1 a GANDER1 track, play, pause, unload, DECKS, TRACKS, ☰: inside, edge on TRACKS. Repeat acceptance M's 1f sequence exactly (EJECT, OPEN, load, play, pause, unload, ☰).
4. **J4 unchanged:** eject GANDER1 → DONE → ☰: top level, no edge on a row not in view. BACK from inside: top level with the edge on GANDER1.
5. **J5 with ☰ shown before:** ☰ once, close, OPEN, ☰: inside with the edge (as in acceptance O `68-j4-menu.png`).
6. **J12, J10, J11 still hold** (short).
7. **Clean quits:** 3 Ctrl+Q quits with a GANDER1 track on deck 1; code 0, no SEGV.
8. **Smoke:** the J15 waveform at 0.80 (one shot of acceptance O's loud track: 13 px short of the edges), the J14 header line (unchanged pixels, no column drag; compare an unchanged full-width header with acceptance O's), zoom + then − back, `throttled=0x0`, CPU two decks plus one effect 2 minutes key lock off.

## Restore and report
As acceptance O. At most five main-proof shots, each with one sentence.
