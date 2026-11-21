# Build J acceptance on the test card (tester brief)

Read `ACCEPTANCE-H-tester.md` and `ACCEPTANCE-I-tester.md` (same folder) first. Their card rules, safety rules, tools, hit map and the save and restore of the owner's state hold, with these changes (spec 2e):
- **Never switch a USB port off.** No port-toggle re-plugs and no writes to any `.../portN/disable`. Every re-plug is done by the owner's hand: ask the orchestrator, who asks the owner, and wait.
- MANTACORE stays read-only (do not browse it). Its port stays enabled.
- GANDER1 is read only; clean ejects from the Media page are allowed.
- The owner's pads 1 and 2 stay as they are.
- **The owner uses the card between tests.** Start only when the orchestrator says the owner has handed it over, and record what you find on screen at the start.

Build J is installed in place. It changes seven things from build I (results: waves J1 and J4 to J9):
- the quit crash is fixed (J1);
- after an eject of the drive whose list is in the Tracks table, the table drops that drive's rows and ☰ opens at the top level (J4);
- after OPEN, BROWSE or the ping's LOAD, ☰ opens inside "DRIVE › rekordbox" with the edge on Tracks (J5);
- sorting a drive's list by any column, KEY included, never empties the table (J6);
- after a drive leaves and another is plugged in, each drive's lists show only that drive's tracks (J7);
- tracks with accented file names on a drive load (J8);
- Settings › Interface has a last row "Zoom" with + then −, which zooms both decks' main waveforms (J9, spec 2f).

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
4. **Drive lists (J6, J7, J8).** IXIAN is the owner's drive: read only, browse it only when the owner has plugged it in, and never eject it unless the orchestrator says so.
   - **Sort (J6):** IXIAN › Smarties › Jazz: tap every header, KEY included, twice each (up and down). The row count never drops to 0, and KEY's order follows This Pi's KEY order. Then put the list's sort back as found.
   - **Rows (J7):** with GANDER1 and IXIAN both plugged in, open a GANDER1 list, then an IXIAN list: each shows only its own drive's tracks (check the paths in the log on load). Then eject GANDER1 with no other change and open IXIAN's Sunny Day Vibes: it shows 42 rows (the export holds 42), none from GANDER1. Have the owner re-plug GANDER1 and check its list again.
   - **Accented names (J8):** in Sunny Day Vibes, load "Technicolor", "El Hijo De Mamá" and "Anbessa" to a deck one at a time: each loads and plays, with its title and artist readable. Unload them after.
5. **Zoom (J9).** Settings › INTERFACE › Zoom: tap + three times, then the Decks page: both main waveforms are zoomed in by the same steps. Tap − back to the starting zoom. Change it once more, wait 2 s, quit with Ctrl+Q and start Mixxx: both decks come back at the saved zoom. The Loop panel's − and + work as on build I. Put the zoom back as found. Make the pair `acceptance-J/pairs/m-settings-interface.png` (mockup on the left; the Zoom row is the spec 2f addition).
6. **Build I's items still hold:**
   - the header empty area;
   - the menu shadow pixels and the taps through it;
   - the Tracks row inside a drive;
   - IN USE timing, and the chip as on build I;
   - the ping over the Media page;
   - TITLE stays 160, and there is no start-up write;
   - the overview strip moves;
   - the ★ start works.
7. **Smoke:**
   - a setting and an effect each saved within 1 s;
   - two decks plus one effect for 2 minutes: the CPU readout and the underrun counter (build I: 4.08 %, 0);
   - `throttled=0x0`.

## Restore at the end
Put back what you found at the start (the owner may have changed it while playing): the decks' tracks, paused, SYNC as found, the screen as found, the owner's settings, pads and FX, GANDER1's and IXIAN's list sorts. Every USB port enabled.

## Report
Write `acceptance-J/ACCEPTANCE.md`. Reply with:
- the counts;
- each FAIL in one line;
- the 10 quit results;
- the CPU and underrun numbers;
- any owner activity;
- the final state.
