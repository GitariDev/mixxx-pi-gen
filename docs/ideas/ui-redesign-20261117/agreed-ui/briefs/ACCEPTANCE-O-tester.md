# Build O acceptance on the test card (tester brief)

Read `ACCEPTANCE-M-tester.md` and acceptance M's `deploy/ui-redesign-20261117/acceptance-M/ACCEPTANCE.md` first. Their card rules, safety rules and tools hold, including `logs/wfmeasure.py`. Then read `AGREED-UI-SPEC.md` **2h** (with the owner's notes after build M) and plan 12.15-12.16, and the wave briefs `J14-S-header-line.md` and `J15-NJ-waveform-gain.md`. Build O is build M plus J14 (the header's 1 px line) and J15 (main waveforms at 0.80), installed in place (`deploy/ui-redesign-20261117/buildO-update/UPDATE-LOG.md`).

Write your evidence in `deploy/ui-redesign-20261117/acceptance-O/`. Record the screen, the mounted drives and the owner's column widths at the start, and restore them at the end.

## Checks (PASS / FAIL / BLOCKED)
1. **J15, the main waveforms at 0.80.** Load acceptance M's loud master (ReplayGain 0.24) to deck 1 and its quiet master (0.78) to deck 2, play, and shoot several times, as in acceptance M's `70-wf-*`. Measure with the same script.
   - Expected: the loud track's peaks stop at about 0.80 of the half-row and never touch the top or bottom edge (acceptance M: flat on the edges in 12-31 % of columns). Its tallest columns sit flat at about 0.80. The quiet track is about 0.80 × its acceptance M heights.
   - Swap the decks and repeat once (each deck's row behaves the same).
   - The Loop panel's waveform strip and the overview strips look as in build M (compare with acceptance M's shots).
2. **J14, the header line.** This Pi › Tracks. Note TITLE's right edge, drag it narrower so the sections end before the scroll bar, and shoot. Sample pixels: under the empty part (x 740, 770) the line row is `#2c333d`, the rows above `#1d222a`, the first table row below; under the sections (x 300, 600, 700) one line, not two, at the same y; the header height equals build M's. Then drag TITLE back to the noted edge and check the owner's widths are restored (shared column setup unchanged).
3. **J12 still holds** (short): EJECT GANDER1 → SAFE TO REMOVE → OPEN → READY, a GANDER1 track loads.
4. **J10, J11, J4 still hold** (short, as acceptance M 3a-3c).
5. **Clean quits:** 3 Ctrl+Q quits with a GANDER1 track on deck 1, each "shutdown complete with code 0", no SEGV.
6. **Smoke:** zoom + then − back to the value found (saved within 1 s); `throttled=0x0` and temperature; two decks plus one effect for 2 minutes with key lock off (CPU and underruns, like for like with acceptances L and M); the package list equals image O's (`deploy/test-image-20261122o/deploy-files/image-o-packages.txt`).

## Restore
The state you found: the same drives mounted, decks empty, the zoom value, the ★, the owner's column widths, deck key locks, and `mixxx.cfg` equal to the owner's copy taken at the start. Every USB port enabled.

## Report
The counts, each FAIL in one line, the J15 measurements next to acceptance M's, the header pixel samples, the quit results, the CPU numbers and the final state. Mark at most five shots as the main proof, each with one sentence of what it shows.
