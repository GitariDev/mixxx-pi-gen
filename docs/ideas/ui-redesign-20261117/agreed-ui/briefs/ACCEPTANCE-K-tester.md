# Build K acceptance on the test card (tester brief)

Read `ACCEPTANCE-J-tester.md` and acceptance J's `deploy/ui-redesign-20261117/acceptance-J/ACCEPTANCE.md` first; their card rules, safety rules and tools hold. Build K is build J plus wave J10 only, installed in place. Write evidence in `deploy/ui-redesign-20261117/acceptance-K/`. Start only when the orchestrator says the owner has handed the card over; record what's on screen at the start and restore it at the end. Re-plugs are by the owner's hand only (stop with `OWNER ACTION NEEDED:`); never switch a USB port off.

## Checks (PASS / FAIL / BLOCKED)
1. **The Folders eject (J10, spec 2e and 2g):**
   - Open ☰ › Folders › REMOVABLE DEVICES › GANDER1 › Contents › "21 Savage Metro Boomin Drake" › SAVAGE MODE II; the table shows its file.
   - Eject GANDER1 from the Media page (DONE) and close the page:
     - the table shows no GANDER1 row;
     - ☰ opens at the top level with no edge;
     - Folders › REMOVABLE DEVICES no longer lists GANDER1.
   - Compare with acceptance J shots 201–203.
2. **J4 still holds:** after the owner re-plugs GANDER1, open GANDER1 › Tracks (rekordbox), then eject it: its rows go, and ☰ opens at the top level.
3. **Clean quits:** 3 Ctrl+Q quits, with a GANDER1 track on a deck, each log ending "shutdown complete with code 0", and no SEGV.
4. **Smoke:**
   - the Zoom row: + then − back to the value found;
   - a setting saved within 1 s;
   - two decks plus one effect for 2 minutes, with the deck 1 key lock as the owner left it; report the CPU % and underruns, and also with key lock off for the like-for-like number;
   - `throttled=0x0`.

## Report
The counts, each FAIL in one line, the quit results, the CPU numbers, any owner activity and the final state.
