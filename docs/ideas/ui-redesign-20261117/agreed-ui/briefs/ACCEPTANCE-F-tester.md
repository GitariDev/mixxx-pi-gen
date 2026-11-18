# Build F acceptance on the test card (tester brief)

Read `ACCEPTANCE-C-tester.md`, `-D-` and `-E-` (same folder) first. Their card rules, safety rules, tools and hit map hold. Build F (`c97fbbd`, 53 patches) is installed in place. The only change from build E is `mixxx-shared-columns.patch` (spec 2c): one column setup for every track table, saved within a second. Write your evidence in `deploy/ui-redesign-20261117/acceptance-F/` (report `ACCEPTANCE.md`, `shots/`, `logs/`) and on the card in `/home/pi/uiF-20261118/tester/`. You change no code and make no commits.

- **The owner may be playing on the card:** "Don't let me interrupt. I'll stop you if i need too." Go ahead, and note any sign of it in the report.
- Save the owner's state first: copy `mixxx.cfg`, `samplers.xml` and `effects.xml` to `/home/pi/uiF-20261118/owner-state/` while Mixxx runs, and keep `soundconfig.xml` untouched.
- **Restore at the end, with one exception:** the column setup (`[Library],SharedColumns`, the shared columns, order and widths) as it was when you started, after build F's first run. Restore the files as build C's step 5 does, but check that the `SharedColumns` line in the restored `mixxx.cfg` is the first-run value. If the saved copy has none, keep whatever setup build F made on its first run. Never write to `mixxxdb.sqlite`.
- Take a header shot before you change anything, so the owner's first-run setup is recorded.

## Checks (PASS / FAIL / BLOCKED, with evidence)

The builder's Pi checks (take a shot first to find the column edges; the header row is at about y 118):
1. **First run.** The shared setup matches the owner's This Pi › Tracks setup from before the update (compare with `acceptance-E/conformance/e01-tracks.png`). `[Library],SharedColumns` is in `mixxx.cfg`.
2. **Saved on change.** On This Pi › Tracks, drag a column edge about 60 px wider. Within 3 s `grep SharedColumns ~/.mixxx/mixxx.cfg` shows the new value. Then `pkill -KILL -x mixxx`, start: the width is kept.
3. **Shared.** Open a playlist (This Pi has Playlists on), a GANDER1 rekordbox list, History, a folder, and Load sample › SAMPLES (70,124). They have the same columns, order and widths; `#` shows only in the playlist.
4. **Sort per list.** Sort Tracks by one column and the playlist by another, then switch back and forth: each list keeps its own sort.
5. **Arrange columns.** ✎ (716,72) › Arrange columns: hide BPM. It is hidden in every other list too. Show it again.
6. **Narrowed and back.** ☰ (772,72): the narrowed table fits. Close Sources each of these ways, and each time check that Tracks gets its full widths back with no restart:
   - ✕ at (772,72);
   - EDIT (629,122), then ✕ at (772,74) in Edit sources;
   - EDIT, then DONE (692,74), then ✕.

   Repeat each way at least three times. This is acceptance E's one-off fault.
7. **Smoke.**
   - A settings change is in `mixxx.cfg` within 1 s.
   - OPEN switches to Tracks.
   - The ★ start opens GANDER1.
   - Two decks plus one effect for 2 minutes: record the CPU readout and the underrun counter (build E: 4.08 %, 0).
   - `throttled=0x0`.

Undo your own changes (the wider column, the sorts, BPM) before you restore, so the owner's first-run setup is what stays. Then load "Your Body" (deck 1) and "YOU'RE THE ONE" (deck 2) from This Pi › Tracks, paused, deck 1 SYNC off, and leave Mixxx on DECKS with GANDER1 READY and MANTACORE's port disabled.

## Report
`acceptance-F/ACCEPTANCE.md`. Reply with the counts, each FAIL in one line, the CPU and underrun numbers, the first-run column setup you recorded, and the final state.
