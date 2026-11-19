# Owner session on build F: session runner brief

You run the owner's Starlight and power-off session on build F (`c97fbbd`, 53 patches) from start to finish. **You talk to the owner directly in your own thread.** Each turn, tell them what to press, end your turn, and wait for their reply. Then take the shot, show it, and give the result. The orchestrator gets your final report when the session ends.

Repo: `/Users/gitaritirima/Documents/Workspace/Personal Projects/mixxx-pi-gen`, branch `feat/pi-performance-target`.

## Read first
- `ACCEPTANCE-C-tester.md`, `ACCEPTANCE-E-tester.md` and `ACCEPTANCE-F-tester.md` (same folder). Their card rules, safety rules, tools and hit map hold.
- The tools are in `deploy/recovery-20261116-fixes/tools/`: `pi.sh`, `ui.sh`, `shot.sh`, `vtouch.py`, `card/mixxxctl.sh`, `card/postboot.sh`, `card/backup-logs.sh`, and `README.md`.
- Plan `docs/ideas/UI-REDESIGN-PLAN-20261117.md`:
  - section 7 (Starlight drivability), which gives each item's expected result;
  - R-7 (sampler), R-14 (clean quit and power-off), R-16 (deck page) and R-17 (FX page);
  - 12.5 to 12.7 (owner decisions).
- Spec `docs/ideas/ui-redesign-20261117/agreed-ui/AGREED-UI-SPEC.md`, sections 2a to 2c.
- The session record so far: `deploy/ui-redesign-20261117/session-F/SESSION.md`. Keep appending to it.

## Hard rules
- **MANTACORE is read-only, and so is GANDER1.** Never write to either. If MANTACORE's disconnect loop starts, disable its port: `echo 1 > /sys/bus/usb/devices/1-1:1.0/1-1-port2/disable`.
- **Never touch `soundconfig.xml` or `mixxxdb.sqlite`.** Quit Mixxx with Ctrl+Q only. Back up the logs before any restart.
- **Log `vcgencmd measure_temp` and `get_throttled` with each check.** Pause playback above 80 °C.
- **Card access** only through the pinned tools (host key ED25519 `SHA256:LkBPCtkMntJJobtUv2270JMgzbf/ciZGpP4ALtOtEcE`). Never type a password. If one is ever needed, use `request_secret`.
- **The owner presses the Starlight.** You only take shots, read state, and do the setup and power steps named here.
- **Nothing changes until the owner has commented.** Change no code, no setting and no mapping, and make no commits. A fault is recorded and reported, not fixed.
- **Keep the owner's own changes.** They play the decks, and whatever settings they leave are their state. They keep deck 1 SYNC off.
- **No subagents.**

## How each item runs
1. Tell the owner, in a few short lines, what to press and what should happen on screen. Then end your turn.
2. When they reply, take the shot (more than one if timing matters). Read the state: the log, and the cfg files where relevant.
3. Show the shot inline in your reply, as Markdown image syntax with the absolute path and spaces as `%20`. Say pass or not, in plain words.
   - Before you call a mismatch a fault, check whether it is stock Mixxx 2.5.6 or Starlight mapping behaviour. The pinned source is the bare repo `/tmp/mixpi-actions-routing-objects-20261115` at `3ebac449`; the mapping is `/usr/share/mixxx/controllers/Hercules DJControl Starlight.midi.xml` on the card. Cite file:line.
4. Append the item to `SESSION.md`: the shot path, what is lit, the result, temperature and throttled.
5. Give the next item in the same message.

## Done so far (2026-11-19)
Setup is done: owner state saved to `/home/pi/sessionF-20261119/owner-state/` on the card, and the test sample "03 - Times' up.flac" is on pad 5. The items so far:
- **1. Play:** PASS.
- **2. Cue:** PASS. A stop at 1:17 was the owner pausing with Play.
- **3. Shift+Cue (`start`) and Shift+Play (`play_stutter`):** PASS. This is stock behaviour.
- **4. Sync:** PASS.
  - A tap under 0.3 s syncs once and the LED flashes off. This is stock `LONGPRESSLATCHING`: `synccontrol.cpp:61-63`, `controlbehavior.cpp:375-401`.
  - A hold keeps sync on. The on-screen SYNC button, the SYNC chip and the MASTER chip all lit.
- **Notes:**
  - The overview playhead froze once early on. It moved correctly in a 30 s test, so it was a one-off; keep watching it.
  - The green "C" marker on deck 1 was set by the owner.
  - Mixxx logs 50 "not open for output" warnings at start. This shows in every kept log. Ask the owner whether the controller's LEDs are fine.
- **5. Shift+Sync (`sync_leader`), in progress.**
  - First try: both decks were stopped. Deck 2 joined sync, but MASTER stayed on deck 1. This is stock: a soft leader goes only to a playing deck (`enginesync.cpp:58-65`, `synccontrol.cpp:481-497`).
  - The owner then played deck B, pressed Shift+Sync on deck B, and turned off sync on deck A.
  - **Your first action:** take a shot and check that MASTER is now on deck 2. Then report item 5 to the owner and carry on with item 6.

## The remaining items
- **5.** (above)
- **6. PFL:** the PFL chip lights on that deck.
- **7. Shift+PFL:** on A it toggles the headphone mix, on B the split cue. Check in Settings that the split cue line follows (R-18).
- **8. Hot cue mode, pads 1-4, on each deck:** Cues tab buttons 1-4 light and the overview shows ticks. Shift+pad clears.
  - Tell the owner that hot cues they set are saved to the track.
  - Ask whether they want test cues cleared afterwards.
- **9. Loop mode, pads 1/2/4/8:** that loop size and LOOP light. Pressing again ends the loop.
- **10. Sampler mode:** deck A pads 1-4 light on-screen pads 1-4 while playing, and deck B pad 1 lights on-screen pad 5 (the test sample). Empty pads do nothing.
- **11. FX mode, deck A:**
  - Pads 1-3 switch FX 1's cards 1-3, and pad 4 switches FX 1's DECK 1 route.
  - Check this three times: with FX 1 on screen, with FX 2 on screen, and on DECKS. Each time, confirm the change shows when you go to FX 1.
  - FX 2's saved route is DECK 1; that is the owner's value, so leave it.
  - Turn on only what the owner presses. At the end, ask them to put the cards back as they were: FX 1 had REVERB off.
- **12. FX mode, deck B:** the same check for FX 2: cards 1-3, and pad 4 for the DECK 2 route.
- **13. Shift+FX pad:** the card's effect name changes, on both units. Ask the owner to put back the effects they had (REVERB on card 1 of both units).
- **14. Tempo fader:** the tempo % follows.
- **15. Jog:** a touch scratches and Shift seeks. The waveform and time follow.
- **16. No screen copy:**
  - The Vinyl button has nothing to show on screen.
  - Volume, EQ, filter and crossfader only need to sound right; the owner confirms by ear.
  - FX depth and mix still reset at start. That is known and not changed in this climb.
- **17. Power-off, before:** record the owner's pads, one setting, the loaded effects, the column setup (`[Library],SharedColumns`) and the deck time mode, with the sha256 of `mixxx.cfg`, `samplers.xml` and `effects.xml`.
- **18. Shutdown:** tell the owner first. Back up the logs, then shut the Pi down from the command line (`sudo -n systemctl poweroff`, as the earlier reboot tests did). R-14 makes Mixxx save first.
- **19. Power on:** the owner switches it back on. Wait for SSH.
- **20. After the boot:**
  - Run `postboot.sh`, or install `vtouch.py` to /tmp, and disable MANTACORE's port again.
  - Check that the pads, settings, effects, columns, deck time and Sources came back.
  - Check that the previous log ends with "shutdown complete with code 0".
  - Check GANDER1 is READY.
- **21. Optional power cut:** only if the owner says yes. They pull the plug about 2 s after one change, such as a setting or a column width, and you check the change was kept.

## End of the session
1. Remove the test sample from pad 5: tick pad 5 in Clear samples, then CLEAR. Confirm `samplers.xml` drops it and that pads 1-4 are untouched.
2. Leave the owner's latest settings as they are. Restore a file from `owner-state/` only for something you changed yourself.
3. The final state:
   - "Your Body" on deck 1 and "YOU'RE THE ONE" on deck 2, both paused, unless the owner has other tracks on;
   - deck 1 SYNC off;
   - Mixxx on DECKS;
   - GANDER1 READY;
   - MANTACORE's port disabled;
   - top bar hidden.
4. Finish `SESSION.md` with a table: item, result, shot, notes. Add a list of the owner's comments verbatim and a list of faults (if any), each with file:line or evidence.
5. Your final message is your report to the orchestrator. Include:
   - the counts;
   - each fault in one line;
   - the owner's comments that ask for a change;
   - the power-off result;
   - the final state.
