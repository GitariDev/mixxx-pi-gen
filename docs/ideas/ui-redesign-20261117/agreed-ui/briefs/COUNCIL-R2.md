# MixPi UI redesign: council brief, round 2

You are one council seat scoring the MixPi UI redesign climb **alone**. Do not read the other seats' round 2 reports. Change no file except your own report. Never touch the Raspberry Pi, any USB drive or any Lima VM. Work read-only on the Mac.

Repo: `/Users/gitaritirima/Documents/Workspace/Personal Projects/mixxx-pi-gen`, branch `feat/pi-performance-target`, head `{HEAD}`. Build D (`ce2186c`) is on the test card, plus one in-place stylesheet repair (`2eedc8f`, the FX selector text).

## The owner's words for this climb (verbatim, 2026-11-17 19:13)

"Okay let's do the thread migrate where we update the climb tuner plan with all these agreed items and climb to the new pi build. Same orchecstration, builders and reviewers as we have done in the recent past. Please don't deviate from UI we set and have the reviewers know what the app is supposed to look like so they judge against that not what they think is best."

## What the app is supposed to look like (read these first)

1. **The binding spec:** `docs/ideas/ui-redesign-20261117/agreed-ui/AGREED-UI-SPEC.md`. Read all of it, including **section 2a (owner changes after build C, 2026-11-18)**. Under 2a, the fonts are build B's by the owner's decision, and the Edit sources child rows and the shorter loop rows at 800×444 are the owner's choices.
2. **The 12 mockups:** `docs/ideas/ui-redesign-20261117/agreed-ui/mockups/*.png` (800×480). View each one.
3. **The card next to each mockup:** `deploy/ui-redesign-20261117/acceptance-D/pairs/*.png` shows the mockup on the left and build D on the card on the right, one file per mockup. The single shots are in `acceptance-D/conformance/d*.png`, and FX after the repair is `buildD-inplace-1/e01-fx.png`. Build C's shots are in `acceptance-C/conformance/k*.png`.
4. **Plan:** `docs/ideas/UI-REDESIGN-PLAN-20261117.md`.
   - **Section 11** is the rubric, as amended by **12.3**.
   - 12.1 is precedence, and 12.5 holds the owner's decisions after build C.
   - 10.1 holds the owner's earlier answers. The R-items give each item's detail.
5. **The owner's verbatim review notes:** `docs/ideas/UI-REVIEW-1-20261117.md`, sections 1 and 5-8.

## Evidence

- `docs/ideas/UI-REDESIGN-RESULTS-20261117.md`: gates, waves, builds C and D, the conformance passes, and acceptance C and D.
- `deploy/ui-redesign-20261117/acceptance-C/ACCEPTANCE.md` (45 checks, with the drive checks on the owner's spare stick GANDER1 and the Q3 gate) and `acceptance-D/ACCEPTANCE.md` (31 checks).
- The build kits `deploy/test-image-20261118c/` and `deploy/test-image-20261118d/` (BUILD.md, UPDATE.md, logs), and the update logs in `buildC-update/` and `buildD-update/`.
- Round 1 reports: `deploy/ui-redesign-20261117/council/round1-*.md`. Check that their findings are repaired.
- Code: `git log --oneline ef0874d..{HEAD}`, the patches in `stage3/01-install-packages/files/` (`MIXXX_PATCHES` in `01-run.sh`, 50 patches), the generator `mixpi-performance.py`, the stylesheets, the system files and `tests/`. The pinned Mixxx source is the bare repo `/tmp/mixpi-actions-routing-objects-20261115` at `3ebac449`.

## How to judge (from the owner and plan 12.3)

- **Judge conformance, not taste.** Score how well the delivered app matches the spec, the mockups and the owner's verbatim words, together with the section 11 rubric as amended by 12.3.
- **A deviation from the spec is a finding.** Cite the spec line or the mockup, and the screenshot that shows it.
- **A preference is not a finding** and must not change your score. That covers "it would look better if", other colours or layouts, and features the owner did not ask for.
- **Real usability or safety concerns** go under the heading **"Owner questions (no score effect)"**.
- **An unlisted deviation caps the seat at 6.** The deviations below are listed. A listed deviation is still a defect for the rubric, but it does not trigger the cap.
- Pixels may differ where Qt forces it. The 48 px touch minimum is not a deviation, and neither are the 24 px scroll bars (spec section 1).

## Listed deviations and open items (known; each with its reason)

1. **The accent edge after OPEN or BROWSE** (acceptance D, FAIL 1). After a drive is opened from the Media page, the Sources menu reopens inside This Pi with the edge there, not on the drive. Native; needs another build, which needs the owner's yes.
2. **The narrowed Load sample table** (acceptance D, FAIL 2). With Sources open over Load sample, the Samples table's last header is cut to "DURATIO" by its scroll bar. Native, as in 1.
3. **★ on a switched-off row** in Edit sources is drawn disabled: Mixxx cannot start Tracks at a source that is off. The mockup draws it enabled.
4. **The Sources side menu has no drop shadow:** Qt graphics effects are costly on the Pi.
5. **The Clear samples list** scrolls by its bar only, past five loaded pads: a skin scroll area has no drag scrolling.
6. **Inside a rekordbox drive there is no "Tracks" row:** Mixxx's rekordbox reader lists playlists and folders only. The mockup's rows are example data.
7. **The USB chip** reads IN USE once a drive is opened, before anything plays.
8. **EJECTING** is rarely seen, because the unmount takes under 0.4 s.
9. **The plug-in ping** does not show while the Media page is open: the page already shows the drive.
10. **Not run yet, by the owner's choice or because the owner must be present:** the interactive Starlight session (owner: "Later"), and the samples power-off test (someone must power the Pi on again). A reboot test and a kill -9 test passed.

## How to score

Score the delivered result and its evidence from 1 to 10 with the section 11 rubric as amended by 12.3. Mark each of the eight criteria pass, partial or fail, with the reason and a file:line or evidence path. Apply the hard limits.

Then list:
- **Deviations from the spec** you found that are not in the list above, each with the spec line or mockup and the screenshot.
- **Blockers:** anything that keeps you below 9, each with the smallest fix that would lift it.
- **Minor defects:** at most a few.
- **Facts you checked** in code or evidence, and how.
- **Owner questions (no score effect).**

## Report

Write `deploy/ui-redesign-20261117/council/round2-{SEAT}.md`. Start it with `# Council round 2: {SEAT_LONG}, at {HEAD}`, and put `Score: N/10.` on the next line. Reply with the score and the blockers, one line each.
