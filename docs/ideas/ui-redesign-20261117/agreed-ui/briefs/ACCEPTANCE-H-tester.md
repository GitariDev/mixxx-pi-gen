# Build H acceptance on the test card (tester brief)

Read `ACCEPTANCE-F-tester.md` and `ACCEPTANCE-G-tester.md` (same folder) first. Their card rules, safety rules, tools, hit map and the save and restore of the owner's state hold. That includes **MANTACORE's port staying enabled and MANTACORE read-only** (do not browse it).

Build H (56 patches) is installed in place. Its only change from build G is `mixxx-shared-columns-stretch.patch`: TITLE's stretched width is never saved (acceptance G FAIL 1, wave G3 in `docs/ideas/UI-REDESIGN-RESULTS-20261117.md`).

Write your evidence in `deploy/ui-redesign-20261117/acceptance-H/` (`ACCEPTANCE.md`, `shots/`, `logs/`, `pairs/`) and on the card in `/home/pi/uiH-20261119/tester/`. You change no code and make no commits.

## Checks (PASS / FAIL / BLOCKED, with evidence)
1. **Repro 1 from acceptance G.** Start from the owner's line, which has `title hidden=0 width=160`.
   - TRACKS (126,24) › This Pi › Tracks at full width.
   - ✎ (716,72) › Arrange columns (650,217): untick Key (177,220), wait 1.5 s, tick Key (177,220), then Close (588,405).
   - Expected: `SharedColumns` has `title hidden=0 width=160` and `key hidden=0 width=50`. Tracks still draws TITLE stretched, with edges at 424/628/725/775.
2. **A drag.** Move the ARTIST/BPM edge from (627,108) to (687,108). Expected: `artist 260`, and `title` stays 160.
3. **Load sample and a folder.** SAMPLER (288,24) › + LOAD SAMPLE (88,72) › SAMPLES (70,124), then Folders › SAMPLES.
   - FILENAME, TITLE, ARTIST, BPM and KEY are all on screen, with no sideways bar and TITLE 160 px wide.
   - With ARTIST at 260: FILENAME 0-~204, TITLE ~204-364, ARTIST 364-628, BPM and KEY at 628/725/775.
4. **A drag of TITLE's own edge** on This Pi › Tracks causes no write, and `title` stays 160.
5. **The fixes kept from G.** Recheck these:
   - G repro A: KEY comes back at 50 px and BPM at 100 px.
   - There is no write at start: Ctrl+Q, start, and watch for 15 s. The layouts from checks 1-3 stay the same after the restart.
   - The overview strip: three shots 10 s apart on each deck during plain playback, stepping about 400 px × 10 s ÷ the track length.
6. **Smoke:**
   - a setting and an effect each saved within 1 s;
   - OPEN switches to Tracks;
   - the ★ start opens GANDER1;
   - two decks plus one effect for 2 minutes: the CPU readout and the underrun counter (build G: 4.08 %, 0);
   - `throttled=0x0`.
7. **Pairs for the council.** Make the two mockup-against-card pairs: build H's This Pi › Tracks against `mockups/m-tracks.png`, and Load sample › SAMPLES against `mockups/m-loadsample.png`, both with the owner's restored setup.
   - Use the side-by-side tool at `/private/tmp/claude-501/-Users-gitaritirima-Documents-Workspace-Personal-Projects-mixxx-pi-gen/01eef82b-7712-44de-b076-2782a69dc643/scratchpad/pair`: `pair LEFT RIGHT OUT "mockup" "build H"`.
   - Save them as `acceptance-H/pairs/m-tracks.png` and `m-loadsample.png`.

## Restore at the end
Do the same as acceptance G: undo your changes, restore the owner's files, and check that the `SharedColumns` line equals the saved one. Then:
- "Your Body" on deck 1 and "YOU'RE THE ONE" on deck 2, both paused, with deck 1 SYNC off;
- Mixxx on DECKS, with the top bar hidden;
- MANTACORE's port enabled.

## Report
Write `acceptance-H/ACCEPTANCE.md`. Reply with:
- the counts;
- each FAIL in one line;
- the `title` value after each check;
- the overview steps;
- the CPU and underrun numbers;
- any owner activity;
- the final state.
