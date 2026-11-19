# Build G acceptance on the test card (tester brief)

Read `ACCEPTANCE-C-tester.md`, `-D-`, `-E-` and `-F-` (same folder) first. Their card rules, safety rules, tools and hit map hold, with one change: **MANTACORE's port rule is lifted** (plan 12.8). Leave its hub port enabled, and do not disable it after a boot. MANTACORE stays read-only: never write, move or delete anything there, and do not browse it.

Build G (55 patches) is installed in place. It changes two things from build F:
- `mixxx-overview-playposition.patch`: the overview strip no longer freezes about 6 h 46 min after a load (upstream `bef0af3172`);
- `mixxx-shared-columns-width.patch`: a re-shown column keeps its saved width, and there is no start-up write.

Write your evidence in `deploy/ui-redesign-20261117/acceptance-G/` (report `ACCEPTANCE.md`, `shots/`, `logs/`) and on the card in `/home/pi/uiG-20261119/tester/`. You change no code and make no commits.

## Before you start
- **The owner may be playing on the card:** "Don't let me interrupt. I'll stop you if i need too." Go ahead, and note any sign of it in the report.
- **Save the owner's state first:** copy `mixxx.cfg`, `samplers.xml` and `effects.xml` to `/home/pi/uiG-20261119/owner-state/` while Mixxx runs. Never touch `soundconfig.xml` or `mixxxdb.sqlite`.
- **The owner's current settings are their state:** tempo range 24 %, the FX cards, FX 2 → DECK 2, the hot cues, and GANDER1 opened by the ★ start. Keep them all.

## Checks (PASS / FAIL / BLOCKED, with evidence)
1. **The overview strip moves.** Load a track on each deck from This Pi › Tracks. For each deck:
   - Play untouched and take three shots 10 s apart. Crop y 374-424: deck 1 is x 0-400, deck 2 is x 400-800.
   - The white line moves about 400 px × 10 s ÷ the track length each time (about 19 px for a 3½-minute track), and the played part is shaded.
   - Repeat after opening and closing Sources (☰ at (772,72), then ✕), and after a page switch (FX, then DECKS).
   - The real 6¾-hour overflow is covered by the native fixture, not by this check.
2. **A re-shown column keeps its width, repro A.** TRACKS (126,24) › This Pi › Tracks, with KEY at its saved 50 px (edges about 725-775).
   - ✎ (716,72) › Arrange columns (650,217): untick Key (177,220), wait 1.5 s, tick Key (177,220), then Close (588,405).
   - Expected: KEY is still 50 px, and `SharedColumns` has `key hidden=0 width=50`.
   - Repeat with BPM: it comes back at 100 px (edges about 628-725).
3. **A re-shown column keeps its width, repro B.** On This Pi › Tracks, hide BPM through Arrange columns. Open a History entry and show BPM there.
   - Expected: BPM is 100 px in History, then on This Pi › Tracks, and `SharedColumns` has `bpm hidden=0 width=100`.
   - Show `#` in a playlist the same way: it comes back at its saved 30 px, not 160.
   - Hide `#` again afterwards.
4. **No start-up write.** Restart Mixxx with no other change: Ctrl+Q, then start it with `card/mixxxctl.sh start`.
   - Watch `mixxx.cfg`'s mtime and the `SharedColumns` line for the first 15 s. Neither changes.
   - Opening a list (History, a folder, GANDER1's rekordbox list) writes nothing either.
5. **FILENAME.** Open a folder and Load sample › SAMPLES. FILENAME shows as on build F, and the layout matches build F's (`acceptance-F/shots/`).
6. **Smoke:**
   - A settings change is in `mixxx.cfg` within 1 s.
   - An effect change is in `effects.xml` within 1 s.
   - A column drag is saved within 1 s and kept after `pkill -KILL -x mixxx` and a start.
   - OPEN switches to Tracks.
   - The ★ start opens GANDER1.
   - Run two decks plus one effect for 2 minutes. Record the CPU readout and the underrun counter (build F: 4.42 %, 0).
   - `throttled=0x0`.

## Restore at the end
1. Undo your own changes: column widths, sorts, hidden columns, and the tracks you loaded.
2. Restore the owner's files from `owner-state/` as build C's step 5 does. Then check that the `SharedColumns` line equals the saved one.
3. Load "Your Body" on deck 1 and "YOU'RE THE ONE" on deck 2, both paused, with deck 1 SYNC off.
4. Leave Mixxx on DECKS, with the top bar hidden and MANTACORE's port enabled.

## Report
Write `acceptance-G/ACCEPTANCE.md`. Reply with:
- the counts;
- each FAIL in one line;
- the overview line's x values for each deck;
- the CPU and underrun numbers;
- anything the owner changed while you worked;
- the final state.
