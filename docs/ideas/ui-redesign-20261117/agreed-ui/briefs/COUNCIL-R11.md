# MixPi UI redesign: council brief, round 11

You are one council seat scoring the MixPi UI redesign climb **alone**. Do not read the other seats' round 11 reports. Change no file except your own report. Never touch the Raspberry Pi, any USB drive or any Lima VM. Work read-only on the Mac. Start no subagents.

Repo: `/Users/gitaritirima/Documents/Workspace/Personal Projects/mixxx-pi-gen`, branch `feat/pi-performance-target`, head `{HEAD}`. Round 10 scored `03a7095` (build Q on the card): every seat 9. Read `deploy/ui-redesign-20261117/council/round10-*.md` for what each seat found then.

## What is new since round 10 (score this)

`git log --oneline 03a7095..{HEAD}`. In order:
1. **Waveform gain 0.90** (`fd1e940`, plan 12.18): the owner's "The loudest tracks should stop 10% from the edge". One constant in `mixxx-waveform-height-gain.patch`, 0.80 → 0.90.
2. **Three-band main waveforms** (R&D branch `rnd/waveform-three-band-20261122`, fast-forwarded at `a16e093` by the owner's yes, plan 12.19). The R&D thread had its own directions, jury and reviews (`docs/ideas/rnd-waveform-three-band-20261122/`: `DIRECTIONS.md`, `jury/`, `court/`, `climb/`). **The owner's choices are in `OWNER-DECISIONS.md`; the design and the 14-step card checklist are in `HANDOFF.md`.** Settings › Advanced gets a row "Waveform colours: RGB / 3-BAND" (`[MixPi],waveform_colours`); 3-BAND is Mixxx's all-shader Filtered type 19 in Pioneered's colours (low #004ee4, mid #c95a00, high #f6e9d3), on by default once (`ThreeBandDefault`); the Loop panel follows at the RGB height. New patch `mixxx-waveform-three-band.patch` (the 74th).
3. **Build R** (`deploy/test-image-20261124r/`, 19th pi-gen run; run 1 stopped by the Mac-space guard, `RUN1-STOPPED.md`), installed on the card (`buildR-update/UPDATE-LOG.md`), **acceptance R: 12 PASS, 1 FAIL, 1 BLOCKED** (`acceptance-R/ACCEPTANCE.md`).
4. **Wave J18** (`08196b8`, plan 12.20): the overview strips follow the row (Filtered overview in the three colours with 3-BAND; RGB with RGB); `MixpiStatusTextColor` keeps the status text #007de1. **Build S** (`deploy/test-image-20261124s/`), installed (`buildS-update/`), **acceptance S: 7 of 7** (`acceptance-S/ACCEPTANCE.md`).
5. **Wave J19** (`7c933e3`, plan 12.21): in 3-BAND the overview strips draw one-sided ("half") from the bottom edge, opt-in by the skin property `MixpiOverviewHalf`. Native gate `gates/uiJ19-7c933e3.log` (404, 0 skips). **Build T** (`deploy/test-image-20261125t/BUILD.md`): exit 0, `woverview.cpp` compiled clean. **Build T is not on the card yet:** the card was unreachable on 2026-11-25 (the Mac was on another network; `buildT-update/UPDATE-LOG.md`), so J19 has no card evidence. Judge J19 on its source, native tests, gate and build; listed item 8 below.
6. Results and plan records: `docs/ideas/UI-REDESIGN-RESULTS-20261117.md` (sections after "Council round 10"), plan 12.18-12.21.

## The owner's words for this climb (verbatim, 2026-11-17 19:13)

"Okay let's do the thread migrate where we update the climb tuner plan with all these agreed items and climb to the new pi build. Same orchecstration, builders and reviewers as we have done in the recent past. Please don't deviate from UI we set and have the reviewers know what the app is supposed to look like so they judge against that not what they think is best."

And for this round's items, verbatim:
- 2026-11-23 (plan 12.18): "The loudest tracks should stop 10% from the edge, can we bump it up a little bit more?"
- 2026-11-24 (plan 12.20): "So the smaller bottom bar currently isn't 3 band. Please update that quickly for me to come back and review."
- 2026-11-25 (plan 12.21): "Let's try the half waveform on the smaller views, that should help with the blending as well as clearer peaks and trophs. Similar to how it was on the original mixxx but keeping the 3 band."

## What the app is supposed to look like

1. **The binding spec:** `docs/ideas/ui-redesign-20261117/agreed-ui/AGREED-UI-SPEC.md` with sections 2a-2h (see the round 10 brief `COUNCIL-R10.md` in this folder for what each holds). Spec 2h said three-band was **not** part of the build then; the owner has since merged it (plan 12.19). **For the waveforms, the owner's later decisions win:** plan 12.18-12.21 and the R&D `OWNER-DECISIONS.md` / `HANDOFF.md`.
2. **The 12 mockups** `docs/ideas/ui-redesign-20261117/agreed-ui/mockups/*.png` and the card pairs listed in `COUNCIL-R10.md`. The rest of the UI is unchanged since build Q: check that claim (skin diffs in build R and S kits: `logs/skin-diff.txt`).
3. **The plan:** `docs/ideas/UI-REDESIGN-PLAN-20261117.md`; section 11 is the rubric, as amended by 12.3; 12.1 precedence.

## Evidence

- Build kits: `deploy/test-image-20261124r/`, `deploy/test-image-20261124s/`, `deploy/test-image-20261125t/` (BUILD.md, UPDATE.md, logs). Card updates: `deploy/ui-redesign-20261117/build{R,S}-update/UPDATE-LOG.md`; T: not run.
- Acceptances: `deploy/ui-redesign-20261117/acceptance-{R,S}/ACCEPTANCE.md` with shots and logs.
- Gates: `deploy/ui-redesign-20261117/gates/mac-suite-a16e093-20261124.log`, `uiJ18-08196b8.log`, `uiJ19-7c933e3.log`; the R&D native gate is recorded in the HANDOFF.
- Code: the patches in `stage3/01-install-packages/files/` (`MIXXX_PATCHES` in `01-run.sh`, 74), `mixpi-performance.py`, `tests/` (Mac suite: `MIXXX_TEST_SOURCE="$PWD/deploy/mixxx-native-source" python3 -m unittest discover -s tests`, run it on a `git archive` copy in your scratchpad, not the main checkout). Pinned Mixxx source: `deploy/mixxx-native-source` (git) and the bare repo `/tmp/mixpi-actions-routing-objects-20261115` at `3ebac449`.

## How to judge (from the owner and plan 12.3)

- **Judge conformance, not taste.** Score how well the delivered app matches the spec, the owner's later decisions and words, with the section 11 rubric as amended by 12.3.
- **A deviation from the spec or the owner's decisions is a finding.** Cite the line and the screenshot or code.
- **A preference is not a finding** and must not change your score (other colours, other band orders, features not asked for).
- **Real usability or safety concerns** go under **"Owner questions (no score effect)"**.
- **An unlisted deviation caps the seat at 6.** The items below are listed: still defects for the rubric where they are faults, but they do not trigger the cap.
- Everything accepted in `COUNCIL-R10.md` stays accepted, except that the main-waveform gain is now **0.90** by the owner's word (plan 12.18), replacing the 0.80 item.

## Listed deviations and open items (known; each with its reason)

Items 1-13 of `COUNCIL-R10.md` stand. Item 14 there (three-band in R&D) is replaced by:

1. **Acceptance R check 8 FAIL:** Qt "QOpenGLTexturePrivate::destroy() called without a current context" warnings on each RGB ↔ 3-BAND switch (R: 2 per switch with a loop set; S: 1-2 per switch, also without a loop). No audio, memory or paint effect measured. Open; no fix planned until the owner's review.
2. **Acceptance R check 14 BLOCKED:** a controller write to `[MixPi],waveform_colours` needs a mapping change; not done.
3. **For the owner to judge on the Pi:** the rows are unpainted about 0.2 s after a switch; 3-BAND reads lower than RGB on most music (by design: each band peaks below the full signal).
4. **Overview status text** keeps #007de1 in both styles (`MixpiStatusTextColor`): the leader's call while the owner was away (plan 12.20).
5. **An overview type picked in Mixxx's own Preferences is replaced** at the next sync of the row (plan 12.20).
6. **Package drift not applied:** image R/S/T have newer `bluez-firmware`, `rpi-eeprom` (and T `libzstd1`, `zstd`) than the card; the updates run no apt; the owner has not decided.
7. **The eject before ☰ was ever shown** (plan 12.18): shown to the owner; no fix until the owner decides.
8. **J19 has no card evidence yet** (card unreachable 2026-11-25). Build T is built and its update kit is ready. The half overview's look, the bottom axis, the live switch on the card and the RGB strip equality are unproven on the card. The overlay band order is the leader's choice (plan 12.21 names two alternatives if cream still dominates).

## How to score

Score the delivered result and its evidence from 1 to 10 with the section 11 rubric as amended by 12.3. Mark each of the eight criteria pass, partial or fail, with the reason and a file:line or evidence path. Apply the hard limits. Pay particular attention to: whether the three-band, J18 and J19 code is correct and safe (GUI thread, config writes, read-only control force-set, stock behaviour without the skin flags, RGB unchanged), whether the tests prove what they claim (baseline modes fail for the real reason), and whether the records (results, plan, kits, acceptances) match the evidence.

Then list:
- **Deviations from the spec** you found that are not in the lists above, each with the line and the evidence.
- **Blockers:** anything that keeps you below 9, each with the smallest fix that would lift it.
- **Minor defects:** at most a few.
- **Facts you checked** in code or evidence, and how.
- **Owner questions (no score effect).**

## Report

Write `deploy/ui-redesign-20261117/council/round11-{SEAT}.md`. Start it with `# Council round 11: {SEAT_LONG}, at {HEAD}`, and put `Score: N/10.` on the next line. Reply with the score and the blockers, one line each.
