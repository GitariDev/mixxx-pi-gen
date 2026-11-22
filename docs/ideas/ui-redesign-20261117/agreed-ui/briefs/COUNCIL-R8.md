# MixPi UI redesign: council brief, round 8

You are one council seat scoring the MixPi UI redesign climb **alone**. Do not read the other seats' round 8 reports. Change no file except your own report. Never touch the Raspberry Pi, any USB drive or any Lima VM. Work read-only on the Mac.

Repo: `/Users/gitaritirima/Documents/Workspace/Personal Projects/mixxx-pi-gen`, branch `feat/pi-performance-target`, head `{HEAD}`. Build O (`7df3f7d`, 71 patches: build L plus waves J12-J15) is on the test card, installed in place on 2026-11-22 at 23:23-23:27. Build M (`158fecb`, J12 and J13) was installed and accepted before it; build N (J14 only) was built but never installed.

## The owner's words for this climb (verbatim, 2026-11-17 19:13)

"Okay let's do the thread migrate where we update the climb tuner plan with all these agreed items and climb to the new pi build. Same orchecstration, builders and reviewers as we have done in the recent past. Please don't deviate from UI we set and have the reviewers know what the app is supposed to look like so they judge against that not what they think is best."

## What the app is supposed to look like (read these first)

1. **The binding spec:** `docs/ideas/ui-redesign-20261117/agreed-ui/AGREED-UI-SPEC.md`. Read all of it, including the owner's later changes:
   - **Section 2a** (after build C): the fonts are build B's by the owner's decision, so a font that matches build B is not a finding. The Edit sources child rows and the shorter loop rows at 800×444 are the owner's choices.
   - **Section 2b** (after council round 2): three items accepted as they are, and the build E items.
   - **Section 2c** (after build E): RELOOP stays as it is, and one shared column setup.
   - **Section 2d** (after council round 3): the cut header letters and the disabled ★ are accepted. The menu shadow, the Tracks row in a drive, and the chip and ping timing are built as drawn.
   - **Section 2e** (after council round 4): the owner saw the mockup-against-card crops and **kept the Sources menu's capitals and build I's USB chip** (round 4's two caps), and the ping's 15 s. After an eject the stale table goes and ☰ opens at the top level; ☰ after OPEN opens **inside** the drive (this replaces 2b's top-level case).
   - **Section 2f** (during build J): the drive fixes J6-J8, and a **new Zoom row** in Settings › Interface (**Zoom [+] [−] 100%**, both decks, saved; the rows shorten with the top bar). It is the owner's design: judge the card against 2f's words. The Starlight zoom and the indicator were dropped by the owner.
   - **Section 2g** (after council round 5): **sideways scroll with many columns is accepted** (the owner's ten columns with Sources open); and the Folders eject case of 2e, built in J10.
   - **Section 2h** (after council round 7, the owner's build M to O items): **OPEN mounts an ejected drive again** (J12); **bigger main waveforms** without the ReplayGain (J13), then **at 0.80** by the owner's number (J15); **the header's 1 px line, option B** (J14); Debian updates on the card. Three-band colours are in a separate R&D thread and are **not** part of this build.
2. **The 12 mockups:** `docs/ideas/ui-redesign-20261117/agreed-ui/mockups/*.png` (800×480). View each one.
3. **The card next to each mockup:**
   - `deploy/ui-redesign-20261117/acceptance-E/pairs/*.png` has the mockup on the left and build E on the card on the right, one file per mockup.
   - Builds F to J changed the track tables' columns (spec 2c), the overview fix and the spec 2d-2f items. The newer pairs are in `acceptance-H/pairs/` (Tracks, Load sample), `acceptance-I/pairs/` (Sources top, Media, Tracks) and `acceptance-J/pairs/` (Sources inside a drive, Settings › Interface with the Zoom row). Build M and O shots: `acceptance-M/shots/`, `acceptance-O/shots/` (OPEN after an eject, the waveforms, the header line). Where a newer pair exists, it supersedes the older one.
   - The single shots are in `acceptance-E/conformance/`, `acceptance-G/shots/`, `acceptance-H/shots/`, `acceptance-I/shots/` and `acceptance-J/shots/`.
4. **The plan:** `docs/ideas/UI-REDESIGN-PLAN-20261117.md`.
   - Section 11 is the rubric, as amended by 12.3.
   - 12.1 is precedence. **12.5 to 12.16 (and spec 2g, 2h) hold the owner's decisions after builds C, E and F, from the build F session, after acceptance G, after council round 3, and after council round 4 and during build J.**
   - Section 7 is Starlight drivability.
5. **The owner's verbatim review notes:** `docs/ideas/UI-REVIEW-1-20261117.md`, sections 1 and 5-8.

## Evidence

- **Results:** `docs/ideas/UI-REDESIGN-RESULTS-20261117.md` has the gates, waves, builds C to O, acceptances C to O and council rounds 3 to 7. The newest section is "Owner items after round 7, waves J12-J15 and builds M, N, O".
- **Acceptances:** `deploy/ui-redesign-20261117/acceptance-{C,D,E,F,G,H,I,J,K,L,M,O}/ACCEPTANCE.md`.
- **The owner's own session on build F:** `deploy/ui-redesign-20261117/session-F/SESSION.md`, covering the Starlight items of plan section 7 and the power-off test. The overview freeze found there is analysed in `session-F/OVERVIEW-FREEZE-INVESTIGATION.md`.
- **Build kits:** `deploy/test-image-20261118{c,d,e,f}/`, `deploy/test-image-20261119{g,h}/`, `deploy/test-image-20261120i/` `deploy/test-image-20261121{j,k,l}/`, `deploy/test-image-20261122{m,n,o}/`, each with BUILD.md, UPDATE.md and logs. The update logs are in `build{C,D,E,F,G,H,I}-update/`; build J's update was run from its kit's `UPDATE.md` and checked in `acceptance-J/shots/00-…04-…`. The native gate logs are in `deploy/ui-redesign-20261117/gates/` (build J: `uiJ-int3-20261121--…`, 323/323, 0 skips; J10 on build K's exact tree: 329/329, 0 skips, `gates/uiJ10-nj10-20261121--…`; J11 on build L's exact tree: 334/334, 0 skips, `gates/uiJ11-nj11-20261121--…`; J12 343/343, J13 361/361, J14 361/361, J15 366/366 on build O's tree, all 0 skips, `gates/uiJ1{2,3,4,5}-…20261122--…`). The card updates to M and O: `buildM-update/UPDATE-LOG.md`, `buildO-update/UPDATE-LOG.md`; the card's Debian updates: `card-apt-20261122/`.
- **Earlier council reports:** `deploy/ui-redesign-20261117/council/round1-*.md` and `round2-*.md`. Check that their findings are repaired or covered by an owner decision.
- **Code:**
  - `git log --oneline ef0874d..{HEAD}`;
  - the patches in `stage3/01-install-packages/files/` (`MIXXX_PATCHES` in `01-run.sh`, 71 patches);
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
- **The Sources menu rows in Pioneered's capitals** ("TRACKS", playlist names in capitals), where the mockups draw mixed case (spec 2e; round 4 Sol's cap).
- **The USB chip as on build I:** with the Media page open, the lit fill and 2 px border, and READY `#7cc58a`, IN USE `#86c0d8` (spec 2e; round 4 Opus's cap).
- **The plug-in ping's 15 s from the plug-in**, not restarted by opening the Media page (spec 2e).
- **Sideways scroll in the narrowed table when the shared columns don't fit** (spec 2g; round 5 Sol's cap).
- **The ★ start on This Pi:** the owner asked to unstar MANTACORE; the edit page always keeps one ★, so it moved to This Pi (acceptance J).
- **The header's 1 px line (spec 2h):** the owner was shown A (no line) and B (the mockup's line) and chose B; built in J14.
- **The main waveforms' height (spec 2h):** 0.80 is the owner's number ("Let's set the gain to around .80"), so the loudest tracks stop about 20 % short of the edge. The owner also wrote "about 10% away"; 0.90 would give that and was reported back. Judge against 0.80.
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
4. **The header line is built** (J14, option B). Acceptance O: one line in the same pixel row, header height unchanged.
5. **The Starlight session and the power-off test are done** (`session-F/SESSION.md`): 20 of 21 items passed, and none failed. The one fault, the overview freeze (a stock Mixxx bug, upstream #9751), is fixed in build G.
6. **The build I quit crash is fixed** (J1). Acceptance J: 10 Ctrl+Q quits after two eject cycles and one reboot, all clean; acceptances K and L: 12 more. Judge it as delivered.
7. **Packages:** the card got the Debian updates on 2026-11-22 (28 packages, then 4 krb5 during the build O update); its package list equals image O's.
8. **CPU:** 4.17 % like for like on build O (M 4.00 %, L 4.08 %). With the owner's key lock on build K it was 48.9 % with 1 underrun while the owner's own setting (key lock on, the high-quality engine) is on. This is the owner's setting, not a build change; the owner has been told.
9. **Folders › Removable devices (after J11):**
   - A drive plugged in while the list is open appears only when the list is opened again. This is build B / stock behaviour: the list is read on entry.
   - A Media-page eject clears the open folder list until it is opened again. That comes from build B's `mixxx-media-selection.patch`.
   - Plain folders such as SD-BACKUP now always stay. Round 6's cause note was corrected in the results.
   - SD-BACKUP shows a › arrow after the first eject (acceptance L note). Cause: build B's folder-children check (`deferDirectoryProbes` in `mixxx-media-selection.patch`) stops probing after the first eject; not a J10/J11 change.
10. **OPEN after an eject (J12):** fixed. Acceptance M: 4 OPEN/EJECT cycles; Folders shows full tags after OPEN. Known, from build B and kept: after any failed OPEN, every OPEN on the page stays off until another open finishes; build B tracks one safe-to-remove drive at a time, so ejecting a second drive drops the first one's row.
11. **J8 fixes no fault seen on the card.** The garbled names were a test-harness artefact. The patch stays by the owner's word (spec 2f).
12. **J13/J15 and the pregain knob:** the skin has no on-screen gain control, so acceptance M could not turn it (BLOCKED); the native fixture checks that the main waveform's height follows the pregain. The Starlight's gain knob is the real control.
13. **Acceptance M's build L-vs-M perf pair** differs in colour and in deck 2's height partly because of the EQ positions during build L's run; J13 changes only the height gain, which the RGB renderer's colour does not use. The clean measure is acceptance M's and O's `70-wf-*`.
14. **Three-band colours** are explored in an R&D thread on branch `rnd/waveform-three-band-20261122` for the owner to choose; not part of this build and not a deviation.

## How to score

Score the delivered result and its evidence from 1 to 10 with the section 11 rubric as amended by 12.3. Mark each of the eight criteria pass, partial or fail, with the reason and a file:line or evidence path. Apply the hard limits.

Then list:
- **Deviations from the spec** you found that are not in the lists above, each with the spec line or mockup and the screenshot.
- **Blockers:** anything that keeps you below 9, each with the smallest fix that would lift it.
- **Minor defects:** at most a few.
- **Facts you checked** in code or evidence, and how.
- **Owner questions (no score effect).**

## Report

Write `deploy/ui-redesign-20261117/council/round7-{SEAT}.md`. Start it with `# Council round 8: {SEAT_LONG}, at {HEAD}`, and put `Score: N/10.` on the next line. Reply with the score and the blockers, one line each.
