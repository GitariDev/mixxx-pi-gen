# MixPi UI redesign: council brief, round 12

You are one council seat scoring the MixPi UI redesign climb **alone**. Do not read the other seats' round 12 reports. Change no file except your own report. Never touch the Raspberry Pi, any USB drive or any Lima VM. Work read-only on the Mac. Start no subagents.

Repo: `/Users/gitaritirima/Documents/Workspace/Personal Projects/mixxx-pi-gen`, branch `feat/pi-performance-target`, head `{HEAD}`. **Build U is on the test card** (installed in place 2026-11-26 00:11-00:12 EAT). Round 11 scored `7827ce9` (build S on the card, build T built but never installed): Opus 9, Sol 8, Fable 7. Read `deploy/ui-redesign-20261117/council/round11-*.md` for what each seat found, and `COUNCIL-R11.md` (this folder) for the round 11 brief: everything it lists as accepted, listed or in scope stands unless changed below.

## What is new since round 11 (score the whole delivered result, with this new work)

`git log --oneline 7827ce9..{HEAD}`:
1. **Round 11 record fixes** (`dbcd98c`): results for J19 and build T, run numbering, HANDOFF status line, spec 2i.
2. **The owner corrected J19** (2026-11-25, verbatim): "I think you mis-understood my request. I want the small waveforms not to be half the height, but have the waveform cut in half like on a CDJ. Also for the 3 band colors, please used the colors from DiggaOS on the 3 bands." Then: "I'm not around so you can go through the whole process without me. I'll come back to it in the morning to test." Plan 12.22.
3. **Wave J20** (`b53133d`, `563b5d2`): the half strips are always filled so the tallest drawn bar reaches the top row (independent of `OverviewNormalized`); DiggaOS's dark deck colours (low #3d6bff, mid #ff4f9a, high #eef1ff, from the owner's DiggaOS app `/Users/gitaritirima/Documents/Workspace/Personal Projects/rature-ghedi/diggaos/apps/dome/src/styles/tokens.css`) on every 3-BAND view; the strips layer the bands as DiggaOS's overview does (`MixpiOverviewBandScale` "1,0.72,0.42", from `apps/dome/src/audio/Waveform.tsx`; the leader's call). Native gate `gates/uiJ20-b53133d.log` (407, 0 skips).
4. **Build U** (`deploy/test-image-20261125u/`), installed from build S (`buildU-update/UPDATE-LOG.md`); **acceptance U: 9 of 9** (`acceptance-U/ACCEPTANCE.md`). Build T is superseded and was never on the card.
5. Results: `docs/ideas/UI-REDESIGN-RESULTS-20261117.md` (sections after "Council round 11").

## What the app is supposed to look like

As in `COUNCIL-R11.md`, with the owner's newest decisions winning for the waveforms: plan 12.18-12.22, spec 2i, the three-band `HANDOFF.md` and `OWNER-DECISIONS.md`. **The owner's 12.22 words replace 12.21's design and its Pioneered colours.** Judge "cut in half like on a CDJ" and "not half the height" against the acceptance U evidence (shots and `halfstrip.py` numbers), and "the colors from DiggaOS" against the DiggaOS tokens.

## How to judge

As in `COUNCIL-R11.md` (conformance, not taste; an unlisted deviation caps at 6; preferences are not findings; usability/safety concerns go under "Owner questions (no score effect)").

## Listed deviations and open items

Round 11's items 1-7 stand (GL texture warnings, check 14 blocked, the switch delay and lower 3-BAND reading, the status text colour, Preferences' overview type replaced, package drift not applied, the eject before ☰). Item 8 (J19 without card evidence) is replaced by:

8. **J20's leader calls, for the owner's morning test:** DiggaOS's **dark deck** tokens were chosen (the Pi's decks are dark); the strips use DiggaOS's band scales 1 / 0.72 / 0.42 (the owner asked for the colours; the layering is the leader's reading of "the colors from DiggaOS on the 3 bands"), which puts the near-white highs as a floor at the bottom of each one-sided column; the fill scales to the tallest drawn bar, so the median bar is about half the strip on the two R&B tracks (0.56 / 0.48; p90 0.81) and the tallest tip is faint. A percentile scale is the named alternative. The main waveforms take colours only (Mixxx's renderer draws the highs on top).
9. **The main rows appear 340-376 ms after a switch** (acceptance R: 225-250 ms); measured once.

## How to score

As in `COUNCIL-R11.md`. Pay particular attention to: the J20 fill and clamp logic (it replaces Mixxx's peak with the tallest drawn bar: check it can't clip or divide by zero, resets on a new track or type switch, and leaves RGB/HSV/no-flag stock), the band-scale parsing and its fallback, the colour sourcing from DiggaOS, the tests' baselines, and whether the records match the evidence. Then list deviations, blockers (with the smallest fix), minor defects, facts checked, and owner questions.

## Report

Write `deploy/ui-redesign-20261117/council/round12-{SEAT}.md`. Start it with `# Council round 12: {SEAT_LONG}, at {HEAD}`, and put `Score: N/10.` on the next line. Reply with the score and the blockers, one line each.
