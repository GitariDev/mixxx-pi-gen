# Build Q acceptance on the test card (tester brief)

Read `ACCEPTANCE-P-tester.md` and acceptance P's `deploy/ui-redesign-20261117/acceptance-P/ACCEPTANCE.md` first, with its helpers in `acceptance-P/logs/` (`u.sh`, `edge.sh`, `mc.sh`, `px.py`, `pxdiff.py`). Their card rules, safety rules and tools hold. Then read `AGREED-UI-SPEC.md` 2a and 2e with `mockups/m-sources-sub.png`, and the J17 brief `J17-NJ-menu-current-row.md`. Build Q is build P plus J17 only, installed in place (`deploy/ui-redesign-20261117/buildQ-update/UPDATE-LOG.md`).

Write your evidence in `deploy/ui-redesign-20261117/acceptance-Q/`. Record the start state and restore it at the end. Never tap CUE on a paused deck; never drag table columns; unload only with Alt+Shift+Left/Right while stopped.

## Checks (PASS / FAIL / BLOCKED). The edge is `#a3c45e` at x 483 of the row; a row without it reads `#161a20`. Rows: TRACKS y 174, A - MAIN PLAYLIST y 226, DRAKE SHIT y 278.
1. **The round 9 sequence** (acceptance P `o9-*`, which failed on build P): GANDER1 OPEN/BROWSE → ☰ (edge TRACKS) → tap A - MAIN PLAYLIST (600,226) → ☰ (edge 226) → tap the empty part (640,420): **edge stays at 226** → ✕, ☰: **edge at 226, not 174**, table still the playlist. Repeat with a drag on the empty part (630,420 → 630,300) instead of the tap.
2. **The folder row:** DRAKE SHIT (a folder, ›): open it, pick a list inside if there is one, BACK, then an empty-area tap and ✕/☰: record where the edge is and whether it marks the list or folder in view; FAIL only if the edge sits on a row whose list is not in view.
3. **TRACKS in view:** tap TRACKS, ☰, empty-area tap, ✕/☰: edge on TRACKS.
4. **Acceptance P checks 1-5 again** (first ☰ after a fresh start and OPEN inside with the edge on TRACKS, 2 of 2; the remount path; load, play, pause, unload, page change; J4 eject → top level no edge; BACK → edge on GANDER1; J5 with ☰ shown before).
5. **J12, J10, J11** still hold (short); **3 clean quits** with a GANDER1 track on deck 1; **smoke:** J15 at 0.80 (one shot), J14 header unchanged, zoom + then − back, `throttled=0x0`, CPU two decks plus one effect 2 minutes key lock off.

## Restore and report
As acceptance P (the table back to the drive's Tracks or the list found at the start, decks empty, Decks page, `mixxx.cfg` equal to the start copy, all port flags 0). At most five main-proof shots, each with one sentence. If you cannot write a file under deploy/, put its full text in your final report.
