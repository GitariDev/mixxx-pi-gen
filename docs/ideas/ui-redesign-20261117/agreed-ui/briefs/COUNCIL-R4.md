# MixPi UI redesign: council brief, round 4

You are one council seat scoring the MixPi UI redesign climb **alone**. Do not read the other seats' round 4 reports. Change no file except your own report. Never touch the Raspberry Pi, any USB drive or any Lima VM. Work read-only on the Mac.

Repo: `/Users/gitaritirima/Documents/Workspace/Personal Projects/mixxx-pi-gen`, branch `feat/pi-performance-target`, head `{HEAD}`. Build I (`defbda0`, 59 patches) is on the test card, installed in place.

## The owner's words for this climb (verbatim, 2026-11-17 19:13)

"Okay let's do the thread migrate where we update the climb tuner plan with all these agreed items and climb to the new pi build. Same orchecstration, builders and reviewers as we have done in the recent past. Please don't deviate from UI we set and have the reviewers know what the app is supposed to look like so they judge against that not what they think is best."

## What the app is supposed to look like (read these first)

1. **The binding spec:** `docs/ideas/ui-redesign-20261117/agreed-ui/AGREED-UI-SPEC.md`. Read all of it, including the owner's later changes:
   - **Section 2a** (after build C): the fonts are build B's by the owner's decision, so a font that matches build B is not a finding. The Edit sources child rows and the shorter loop rows at 800×444 are the owner's choices.
   - **Section 2b** (after council round 2): three items accepted as they are, and the build E items.
   - **Section 2c** (after build E): RELOOP stays as it is, and one shared column setup.
   - **Section 2d** (after council round 3): the cut header letters and the disabled ★ are accepted. The menu shadow, the Tracks row in a drive, and the chip and ping timing are built as drawn.
2. **The 12 mockups:** `docs/ideas/ui-redesign-20261117/agreed-ui/mockups/*.png` (800×480). View each one.
3. **The card next to each mockup:**
   - `deploy/ui-redesign-20261117/acceptance-E/pairs/*.png` has the mockup on the left and build E on the card on the right, one file per mockup.
   - Builds F to I changed the track tables' columns (spec 2c), the overview fix and the spec 2d items. The newer pairs are in `acceptance-H/pairs/` (Tracks, Load sample) and `acceptance-I/pairs/` (Sources top, Sources inside a drive, Media, Tracks). Where a newer pair exists, it supersedes the acceptance E pair.
   - The single shots are in `acceptance-E/conformance/`, `acceptance-G/shots/`, `acceptance-H/shots/` and `acceptance-I/shots/`.
4. **The plan:** `docs/ideas/UI-REDESIGN-PLAN-20261117.md`.
   - Section 11 is the rubric, as amended by 12.3.
   - 12.1 is precedence. **12.5 to 12.9 hold the owner's decisions after builds C, E and F, from the build F session, after acceptance G, and after council round 3.**
   - Section 7 is Starlight drivability.
5. **The owner's verbatim review notes:** `docs/ideas/UI-REVIEW-1-20261117.md`, sections 1 and 5-8.

## Evidence

- **Results:** `docs/ideas/UI-REDESIGN-RESULTS-20261117.md` has the gates, waves, builds C to I, and acceptances C to I.
- **Acceptances:** `deploy/ui-redesign-20261117/acceptance-{C,D,E,F,G,H,I}/ACCEPTANCE.md`.
- **The owner's own session on build F:** `deploy/ui-redesign-20261117/session-F/SESSION.md`, covering the Starlight items of plan section 7 and the power-off test. The overview freeze found there is analysed in `session-F/OVERVIEW-FREEZE-INVESTIGATION.md`.
- **Build kits:** `deploy/test-image-20261118{c,d,e,f}/`, `deploy/test-image-20261119{g,h}/` and `deploy/test-image-20261120i/`, each with BUILD.md, UPDATE.md and logs. The update logs are in `build{C,D,E,F,G,H,I}-update/`.
- **Earlier council reports:** `deploy/ui-redesign-20261117/council/round1-*.md` and `round2-*.md`. Check that their findings are repaired or covered by an owner decision.
- **Code:**
  - `git log --oneline ef0874d..{HEAD}`;
  - the patches in `stage3/01-install-packages/files/` (`MIXXX_PATCHES` in `01-run.sh`, 59 patches);
  - the generator `mixpi-performance.py`, the stylesheets, the system files and `tests/`.
  - The pinned Mixxx source is the bare repo `/tmp/mixpi-actions-routing-objects-20261115` at `3ebac449`.

## How to judge (from the owner and plan 12.3)

- **Judge conformance, not taste.** Score how well the delivered app matches the spec, the mockups and the owner's verbatim words, together with the section 11 rubric as amended by 12.3.
- **A deviation from the spec is a finding.** Cite the spec line or the mockup, and the screenshot that shows it.
- **A preference is not a finding** and must not change your score. That covers "it would look better if", other colours or layouts, and features the owner did not ask for.
- **Real usability or safety concerns** go under the heading **"Owner questions (no score effect)"**.
- **An unlisted deviation caps the seat at 6.** The deviations below are listed. A listed deviation is still a defect for the rubric, but it does not trigger the cap.
- **Owner-accepted items are not deviations** (spec 2b, 2c and plan 12.6-12.8).
- **Pixels may differ where Qt forces it.** The 48 px touch minimum is not a deviation, and neither are the 24 px scroll bars (spec section 1).

## Accepted by the owner (not findings)

- Edit sources is dragged only from a row's button or the bar, not from the row text.
- The narrowed Load sample table cuts its last header. This shows only with Sources open.
- Clear samples scrolls by its bar only.
- After OPEN from the top level, ☰ opens at the top level (spec 2b).
- RELOOP keeps build B's behaviour: no pressed look while a press starts the loop (spec 2c).
- The column setup is shared, so Load sample shows the shared columns and GANDER1's lists lost their own extra columns (spec 2c).
- With Sources open, any narrowed track table may cut a header's letters ("DURATIO", "BPI", "TITLI"; spec 2d).
- ★ on a switched-off row in Edit sources is drawn disabled (spec 2d).
- Stock Mixxx or Starlight behaviour, kept (plan 12.8):
  - a short Sync tap syncs once, and a hold latches;
  - Shift+Sync gives the leader only to a playing deck;
  - PFL does not take a deck off master.

## Listed deviations and open items (known; each with its reason)

1. **EJECTING** is rarely seen, because the unmount takes under 0.4 s.
2. **FX depth and mix reset at start.** This comes from the Starlight's stock script, and changing it was not requested (spec, the FX section).
3. **The Vinyl button has no screen copy:** it is script-internal state in the stock mapping (plan section 7).
4. **The empty part of the table header** takes the header colour but not the mockup's 1 px bottom line (`#2c333d`). A border on the header widget could change its height (wave H1).
5. **The Starlight session and the power-off test are done** (`session-F/SESSION.md`): 20 of 21 items passed, and none failed. The one fault, the overview freeze (a stock Mixxx bug, upstream #9751), is fixed in build G.
6. **Round 3's other listed items are now built** (spec 2d): the menu shadow, the Tracks row in a drive, IN USE only once something is loaded, the ping over the Media page, and the header strip. Judge them against the mockups; they are no longer excused.

## How to score

Score the delivered result and its evidence from 1 to 10 with the section 11 rubric as amended by 12.3. Mark each of the eight criteria pass, partial or fail, with the reason and a file:line or evidence path. Apply the hard limits.

Then list:
- **Deviations from the spec** you found that are not in the lists above, each with the spec line or mockup and the screenshot.
- **Blockers:** anything that keeps you below 9, each with the smallest fix that would lift it.
- **Minor defects:** at most a few.
- **Facts you checked** in code or evidence, and how.
- **Owner questions (no score effect).**

## Report

Write `deploy/ui-redesign-20261117/council/round4-{SEAT}.md`. Start it with `# Council round 4: {SEAT_LONG}, at {HEAD}`, and put `Score: N/10.` on the next line. Reply with the score and the blockers, one line each.
