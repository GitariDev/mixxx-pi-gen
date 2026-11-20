# Build J acceptance on the test card (tester brief)

Read `ACCEPTANCE-H-tester.md` and `ACCEPTANCE-I-tester.md` (same folder) first. Their card rules, safety rules, tools, hit map and the save and restore of the owner's state hold:
- MANTACORE's port stays enabled, and MANTACORE is read-only (do not browse it);
- GANDER1 is read only; clean ejects and re-plugs by port toggle are allowed;
- the owner's pads 1 and 2 stay as they are.

Build J (60 patches) is installed in place. It changes three things from build I (results: waves J1-J3):
- the quit crash is fixed;
- the Sources menu rows are drawn in their own case;
- the USB chip's colours follow the mockups.

Write your evidence in `deploy/ui-redesign-20261117/acceptance-J/` (`ACCEPTANCE.md`, `shots/`, `logs/`, `pairs/`). You change no code and make no commits.

## Checks (PASS / FAIL / BLOCKED, with evidence)
1. **Clean quits** (council round 4: Fable and Opus).
   - **Set-up:** load a GANDER1 track on deck 1 and a GANDER1 sample on a free pad. Do at least 3 eject and re-plug cycles of GANDER1 from the Media page, then load the deck and pad from it again.
   - **Quit:** Ctrl+Q, then start Mixxx.
   - Do the whole cycle **10 times**, backing up the logs between starts. Each start keeps only 10 logs.
   - Every quit's log ends "Mixxx shutdown complete with code 0", and the journal has no `status=11/SEGV`.
   - **Then one reboot** (`sudo -n systemctl reboot`) with a drive track loaded. After the boot, the previous log ends cleanly, and the pads and settings are back. Reinstall `vtouch.py` after the boot.
   - Unload your test tracks and pads at the end.
2. **Menu case.** ☰ (772,72): the top-level rows read "This Pi", "GANDER1", "Samples" and "More", while BACK and EDIT stay in upper case.
   - Inside GANDER1 the rows read "Tracks" and the playlists in their own case. Inside This Pi they read "Tracks", "Playlists" and "Crates".
   - Edit sources is unchanged.
   - Make the pair `acceptance-J/pairs/m-sources-sub.png` (mockup on the left).
3. **USB chip colours.** The chip is centred at (527,24) and spans x 452-601.

   | State | Left border (452,24) | Top border (527,2) | Fill (453,24) and (590,40) | Word |
   |---|---|---|---|---|
   | At rest, NO USB | `#2c333d` | `#2c333d` | `#1d222a` | about `#949dab` |
   | READY | `#2c333d` | `#2c333d` | `#1d222a` | about `#5fae6e` |
   | IN USE | `#5aa4c4` | `#5aa4c4` | `#1d222a` | about `#5aa4c4` |
   | Media page open | `#a3c45e` | `#a3c45e` | `#1d222a` | the state's colour |

   Make the pair `acceptance-J/pairs/m-media.png`.
4. **Build I's items still hold:**
   - the header empty area;
   - the menu shadow pixels and the taps through it;
   - the Tracks row inside a drive;
   - IN USE timing;
   - the ping over the Media page (tap LOAD within 15 s);
   - TITLE stays 160, and there is no start-up write;
   - the overview strip moves;
   - OPEN and the ★ start work.
5. **Smoke:**
   - a setting and an effect each saved within 1 s;
   - two decks plus one effect for 2 minutes: the CPU readout and the underrun counter (build I: 4.08 %, 0);
   - `throttled=0x0`.

## Restore at the end
Do the same as acceptance I. Then:
- "Your Body" on deck 1 and "YOU'RE THE ONE" on deck 2, both paused, with deck 1 SYNC off;
- Mixxx on DECKS, with the top bar hidden;
- MANTACORE's port enabled;
- the owner's settings, pads and FX as they were;
- GANDER1's list sort as it was.

## Report
Write `acceptance-J/ACCEPTANCE.md`. Reply with:
- the counts;
- each FAIL in one line;
- the 10 quit results;
- the chip pixels;
- the CPU and underrun numbers;
- any owner activity;
- the final state.
