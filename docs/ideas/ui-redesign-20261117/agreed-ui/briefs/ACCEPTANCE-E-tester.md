# Build E acceptance on the test card (tester brief)

Read `ACCEPTANCE-C-tester.md` and `ACCEPTANCE-D-tester.md` (same folder) first. Their card rules, safety rules, tools and hit map hold. Build E (`c87fff8`, 52 patches) is installed in place. Write your evidence in `deploy/ui-redesign-20261117/acceptance-E/` (report `ACCEPTANCE.md`, `shots/`, `logs/`) and on the card in `/home/pi/uiE-20261118/tester/`. You change no code and make no commits.

- **The owner may be playing on the card.** They said: "Don't let me interrupt. I'll stop you if i need too." Go ahead, but if decks are playing when you start, or a setting changes that you did not change, say so in the report. Keep the owner's settings as you find them; do not change them back to older values.
- Before you start, save the owner's state: copy `mixxx.cfg`, `samplers.xml` and `effects.xml` to `/home/pi/uiE-20261118/owner-state/` while Mixxx runs, and restore them at the end. Never touch `soundconfig.xml`.
- Owner decisions: spec `AGREED-UI-SPEC.md` sections 2a and 2b, plan 12.5 and 12.6. The owner accepted three items as they are: Edit sources drag on row text, the narrowed Samples table's last header, and Clear samples drag. Do not test them as FAILs.

## Checks (PASS / FAIL / BLOCKED, with evidence)

1. **The Sources edge after OPEN and BROWSE** (acceptance D repro 1). From This Pi › Tracks, use the Media page's OPEN (or BROWSE) from DECKS. Then ☰: the menu is inside "GANDER1 › rekordbox"; BACK puts the edge on the GANDER1 row only. Repeat from FX with BROWSE. `SidebarDefaultSource` stays `RekordboxFeature`.
2. **Clear samples: stop, then clear.** Load test samples to pads 3 and 4 (from the Samples folder). Play pad 3 and pad 4 (▶ TRIGGER). Tick pad 3 only, then CLEAR (1): pad 3 stops and goes "+ Empty · tap to load", pad 4 keeps playing and stays loaded, the popover closes, `samplers.xml` drops pad 3 within about 1 s, and the sample files' sha256 are unchanged. Then stop pad 4 and clear it too (tick, CLEAR (1)). Pads 1 and 2 (the owner's) are never touched.
3. **The REC dot** is red at rest; tap REC: WAIT, then ■ STOP as before; record 30 s, which gives WAV + CUE (delete your test files afterwards); a tap on the dot itself also starts recording.
4. **EXIT LOOP and RELOOP** stay at rest with a 4-beat loop on, show the pressed look while held, and work (EXIT LOOP ends the loop; RELOOP starts it again with no loop on).
5. **The table's row colours** on Tracks, Load sample and the narrowed table with Sources open: alternate rows `#161a20`, other rows `#000`, selected row `#263b51`, text `#e4e7ec`. Sample the pixels from your shots.
6. **Smoke:**
   - one settings change in `mixxx.cfg` within 1 s;
   - one effect change in `effects.xml` within 1 s;
   - ★ start: with GANDER1 in, Tracks opens on GANDER1 after a fresh start;
   - the child rows show in Edit sources;
   - OPEN switches to Tracks;
   - two decks plus one effect for 2 minutes: the CPU readout and Mixxx's underrun counter (build D: 4.33 %, 0);
   - `throttled=0x0`.

## Restore the owner's state at the end
Restore from `/home/pi/uiE-20261118/owner-state/` as build C's step 5 does, but keep the owner's current deck time and other settings exactly as saved there. Load "Your Body" (deck 1) and "YOU'RE THE ONE" (deck 2) from This Pi › Tracks, paused, deck 1 SYNC off. Leave Tracks on This Pi › Tracks, GANDER1 READY, MANTACORE's port disabled, top bar hidden, Mixxx on DECKS.

## Report
`acceptance-E/ACCEPTANCE.md`. Reply with the counts, each FAIL in one line, the CPU and underrun numbers, anything the owner changed while you worked, and the final state.
