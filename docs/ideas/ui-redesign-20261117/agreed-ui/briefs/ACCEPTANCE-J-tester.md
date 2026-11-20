# Build J acceptance on the test card (tester brief)

Read `ACCEPTANCE-H-tester.md` and `ACCEPTANCE-I-tester.md` (same folder) first. Their card rules, safety rules, tools, hit map and the save and restore of the owner's state hold, with these changes (spec 2e):
- **Never switch a USB port off.** No port-toggle re-plugs and no writes to any `.../portN/disable`. Every re-plug is done by the owner's hand: ask the orchestrator, who asks the owner, and wait.
- MANTACORE stays read-only (do not browse it). Its port stays enabled.
- GANDER1 is read only; clean ejects from the Media page are allowed.
- The owner's pads 1 and 2 stay as they are.
- **The owner uses the card between tests.** Start only when the orchestrator says the owner has handed it over, and record what you find on screen at the start.

Build J is installed in place. It changes three things from build I (results: waves J1, J4 and J5):
- the quit crash is fixed (J1);
- after an eject of the drive whose list is in the Tracks table, the table drops that drive's rows and ☰ opens at the top level (J4);
- after OPEN, BROWSE or the ping's LOAD, ☰ opens inside "DRIVE › rekordbox" with the edge on Tracks (J5).

The Sources menu's capitals, build I's USB chip and the ping's 15 s are kept by the owner's decision (spec 2e); they are not findings.

Write your evidence in `deploy/ui-redesign-20261117/acceptance-J/` (`ACCEPTANCE.md`, `shots/`, `logs/`, `pairs/`). You change no code and make no commits.

## Checks (PASS / FAIL / BLOCKED, with evidence)
1. **Clean quits** (council round 4: all three seats).
   - **Set-up:** load a GANDER1 track on deck 1 and a GANDER1 sample on a free pad.
   - **Quit:** Ctrl+Q, then start Mixxx and load the deck and pad again.
   - Do this **10 times**, backing up the logs between starts (each start keeps only 10 logs).
   - **Eject cycles:** before quits 4 and 8, eject GANDER1 from the Media page and have the owner re-plug it by hand, then load from it again. That is 2 owner re-plugs in this check; ask for both at once if the owner prefers to stay by the card.
   - Every quit's log ends "Mixxx shutdown complete with code 0", and the journal has no `status=11/SEGV`.
   - **Then one reboot** (`sudo -n systemctl reboot`) with a drive track loaded. After the boot, the previous log ends cleanly, and the pads and settings are back. Reinstall `vtouch.py` after the boot.
   - Unload your test tracks and pads at the end.
2. **After an eject (J4).** Use one of check 1's eject cycles.
   - With GANDER1 › Tracks in the table, eject GANDER1 from the Media page and close the page: the table shows none of GANDER1's rows.
   - ☰ (772,72) opens at the top level.
   - Repeat with This Pi › Tracks in the table: ejecting GANDER1 leaves This Pi's list in place.
3. **☰ after OPEN (J5).** Acceptance I repro 1, without the port toggle:
   - leave the menu inside This Pi, then OPEN (159,214) GANDER1 on the Media page, then ☰: it opens inside "GANDER1 › rekordbox" with the edge on TRACKS;
   - the same after the owner's re-plug, with the menu left inside "GANDER1 › rekordbox" before the eject;
   - the same with the ping's LOAD (tap within 15 s of the plug-in);
   - BACK goes to the top level with the edge on GANDER1.
   - Make the pair `acceptance-J/pairs/m-sources-sub.png` (mockup on the left).
4. **Build I's items still hold:**
   - the header empty area;
   - the menu shadow pixels and the taps through it;
   - the Tracks row inside a drive;
   - IN USE timing, and the chip as on build I;
   - the ping over the Media page;
   - TITLE stays 160, and there is no start-up write;
   - the overview strip moves;
   - the ★ start works.
5. **Smoke:**
   - a setting and an effect each saved within 1 s;
   - two decks plus one effect for 2 minutes: the CPU readout and the underrun counter (build I: 4.08 %, 0);
   - `throttled=0x0`.

## Restore at the end
Put back what you found at the start (the owner may have changed it while playing): the decks' tracks, paused, SYNC as found, the screen as found, the owner's settings, pads and FX, and GANDER1's list sort. Every USB port enabled.

## Report
Write `acceptance-J/ACCEPTANCE.md`. Reply with:
- the counts;
- each FAIL in one line;
- the 10 quit results;
- the CPU and underrun numbers;
- any owner activity;
- the final state.
