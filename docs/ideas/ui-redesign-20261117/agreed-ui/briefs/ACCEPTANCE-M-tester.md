# Build M acceptance on the test card (tester brief)

Read `ACCEPTANCE-L-tester.md` and acceptance L's `deploy/ui-redesign-20261117/acceptance-L/ACCEPTANCE.md` first. Their card rules, safety rules and tools hold. Then read `AGREED-UI-SPEC.md` **2h** (the owner's words for this build) and the wave briefs `J12-NJ-open-remount.md` and `J13-NJ-waveform-height.md`. Build M is build L plus waves J12 and J13, installed in place (`deploy/ui-redesign-20261117/buildM-update/UPDATE-LOG.md`). The owner said "Alright keep going!".

Write your evidence in `deploy/ui-redesign-20261117/acceptance-M/`. Record what is on screen and which drives are mounted at the start, and restore it at the end.

## Card access and safety
- Card access only with `deploy/recovery-20261116-fixes/tools/pi.sh` (pinned key SHA256:LkBPCtkM…EcE). The older `deploy/recovery-20261116/pi-review/tools/pi.sh` has a stale key: never use it, and never override a host-key warning.
- **Never switch a USB port off.** No physical re-plugs: the owner's hands are not needed for this build, because J12 brings an ejected drive back with OPEN.
- Unmount only through the Media page's clean eject, or with `udisksctl unmount` where a check says so. Never write to a drive. IXIAN is never ejected.
- Back up Mixxx's logs before every quit and start (each start keeps only 10).
- Open no window or app on the Mac.

## Checks (PASS / FAIL / BLOCKED)
1. **J12, OPEN mounts an ejected drive again** (spec 2h). GANDER1 must be mounted at the start of the check (mount it with `udisksctl mount` if it is not).
   - Media page › GANDER1 › EJECT › clean eject (DONE). The row reads **SAFE TO REMOVE**, and OPEN can be tapped. Shoot it.
   - Tap **OPEN**. Within a few seconds the row reads **READY**, Tracks opens with GANDER1's tracks, and the button reads BROWSE afterwards. Shoot each. The log has "MixPi open: mount".
   - Load a GANDER1 track to deck 1: it loads and plays, and the chip reads IN USE.
   - ☰ › Folders › REMOVABLE DEVICES › GANDER1 › a folder: rows show **full tags** (artist, BPM), not file names only (acceptance L saw "thin tags" after a software remount).
   - Unload deck 1, then EJECT again: a clean eject, SAFE TO REMOVE, and reads refused again.
   - **Second cycle:** OPEN again works the same way.
   - IXIAN's row and reads never change. SD-BACKUP stays in Removable devices throughout.
2. **J13, bigger main waveforms** (spec 2h).
   - Find in the card's library (read only) a loudly mastered track with a ReplayGain of about 0.25 or lower, and a quiet one at 0.7 or higher, on the Pi or a mounted drive. Load the loud one to deck 1 and the quiet one to deck 2, play both, and shoot the Decks page several times.
   - Measure from the shots: each main waveform's peak extent against its row (deck 1 about y 48-176, deck 2 about y 176-304). Expected: the loud track reaches the top and bottom edges often, sitting flat on them; the quiet one fills most of its row with few or no columns at the edge. Compare with build L's shots of loaded decks in earlier acceptance folders (acceptance J/K/L), and with the simulation `deploy/ui-redesign-20261117/wave-J13/simulation-before-after.png`.
   - The Loop panel's waveform strip and the overview strips look as in build L (compare with earlier shots).
   - If the skin has an on-screen gain (pregain) control, turn it down and up and shoot: the main waveform's height follows it. If there is none on screen, mark this part BLOCKED; do not set controls another way.
3. **J10, J11 and J4 still hold** (short): a Folders view of GANDER1 then a Media-page eject empties the table and ☰ opens at the top level; SD-BACKUP stays listed; a rekordbox GANDER1 › Tracks view then an eject drops its rows. Use OPEN to bring GANDER1 back between checks instead of udisksctl.
4. **Clean quits:** 3 Ctrl+Q quits with a GANDER1 track on deck 1. Each log ends "shutdown complete with code 0", with no SEGV.
5. **Smoke:**
   - Zoom: + then − back to the value found, each saved within 1 s.
   - `throttled=0x0`, temperature.
   - Two decks plus one effect for 2 minutes with key lock off (like for like with acceptance L). Report the CPU and underruns.
   - The header line is unchanged from build L (the owner has not chosen yet).

## Restore
Put back the state you found at the start: the same drives mounted (use OPEN to bring GANDER1 back if needed), decks empty, the zoom value found, the ★ where it was. Every USB port enabled (all `disable` flags 0).

## Report
The counts, each FAIL in one line, the J13 measurements, the quit results, the CPU numbers and the final state. Mark at most five shots as the main proof, each with one sentence of what it shows.
