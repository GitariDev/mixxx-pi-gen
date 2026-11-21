# Build L acceptance on the test card (tester brief)

Read `ACCEPTANCE-K-tester.md` and acceptance K's `deploy/ui-redesign-20261117/acceptance-K/ACCEPTANCE.md` first. Their card rules, safety rules and tools hold. Build L is build K plus wave J11 only, installed in place. The owner is asleep and has handed over the card for the night ("Do all the proof").

Write your evidence in `deploy/ui-redesign-20261117/acceptance-L/`. Record what is on screen at the start, and restore it at the end.

## No re-plugs and no port switching
- **Never switch a USB port off.** The owner's port-toggle permission covered acceptance K only.
- No physical re-plugs are possible tonight.
- To make a drive "come back" after a clean eject, mount it in software with `udisksctl mount -b /dev/sdX1`, as user pi. This changes the mount table, the same signal J10 and J11 react to, without cutting port power.
- Unmount only through the Media page's clean eject, or for GANDER1 with `udisksctl unmount` (clean, no port cut) where a check says so.
- IXIAN stays mounted and is never ejected.

## Checks (PASS / FAIL / BLOCKED)
1. **J11, the plain folder stays.**
   - **Start:** open ☰ › Folders › REMOVABLE DEVICES. It lists SD-BACKUP plus the mounted drives; shoot it.
   - **Pull (J11's main case):** mount GANDER1 with udisksctl, open Removable Devices again (it lists SD-BACKUP and GANDER1), and leave it open. Then unmount GANDER1 with `udisksctl unmount -b /dev/sdX1`. That is a clean unmount with no port cut, and it stands in for a pull. Within 3 s the open list reads SD-BACKUP and IXIAN: **SD-BACKUP stays**. Build K dropped it.
   - **Media-page eject:** mount GANDER1 again, then eject it cleanly from the Media page.
     - The eject clears the whole open list. That is build B's behaviour from `mixxx-media-selection.patch`, so it isn't a finding.
     - Open Removable Devices again: it lists SD-BACKUP and IXIAN, with no GANDER1.
     - Wait 5 s with it open: SD-BACKUP stays.
   - **List open during a mount:** with the list open, mount GANDER1. It doesn't appear until the list is opened again; that is build B's behaviour, so record it but don't count it as a finding.
   - Compare with acceptance K's shot `70-now.png`.
2. **J10 still holds.**
   - **Setup:** mount GANDER1, then open Folders › REMOVABLE DEVICES › GANDER1 › Contents › "21 Savage Metro Boomin Drake" › SAVAGE MODE II.
   - **Eject:** eject GANDER1 cleanly.
   - **Expect:** the table empties, ☰ opens at the top level, and SD-BACKUP is still listed.
3. **J4 still holds.**
   - **Setup:** mount GANDER1, then open GANDER1 › Tracks (rekordbox).
   - **Eject:** eject GANDER1.
   - **Expect:** its rows go, and ☰ opens at the top level.
4. **Clean quits:** 3 Ctrl+Q quits with a GANDER1 track on deck 1 (GANDER1 mounted with udisksctl). Each log ends "shutdown complete with code 0", with no SEGV.
5. **Smoke:**
   - Zoom: + then − back to the value found, each saved within 1 s.
   - `throttled=0x0`.
   - Two decks plus one effect for 2 minutes with key lock off (like for like). Report the CPU and underruns.

## Restore
Put back the state you found at the start, including which drives are mounted. GANDER1 was ejected but still attached, so leave it ejected. Every USB port enabled.

## Report
The counts, each FAIL in one line, the quit results, the CPU numbers and the final state.
