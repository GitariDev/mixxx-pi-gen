# Field-fix climb results, 2026-11-16 (tracked record)

Plan: `docs/ideas/FIELD-FIX-PLAN-20261116.md`. Tuner record: `mixpi-field-fixes-20261116`. This file is the tracked results file that F-15 step 8 asked for (carried item C-4). It summarises evidence that stays untracked under `deploy/`.

## Builds

| Build | Commit | Image | Delivered to the test card | Evidence |
|---|---|---|---|---|
| 1 | `9ddbe89` | `mixpi-test-20261116` | Flash | `deploy/recovery-20261116-fixes/field-fix-acceptance/ACCEPTANCE.md` |
| 2 | `ac18cb2` | `mixpi-test-20261116b` | In-place update from a file-level diff | `deploy/test-image-20261116b/`, `deploy/recovery-20261116-fixes/field-fix-acceptance-b2/ACCEPTANCE.md` |
| 3 | not built | — | — | Round-1 repairs committed as `053c618`; native gate 128/128 (`deploy/recovery-20261116-fixes/build3-fixes/`) |

## Pi results on build 2 (from ACCEPTANCE.md, build 2)

| Item | Result |
|---|---|
| A. In-place update | PASS (`dpkg -V` clean, all section-A files at build-2 sha) |
| F-1, F-2, F-3, F-4 (86.5 px per beat), F-5, F-6, F-7, F-8, F-9, F-11, F-13, F-14 | PASS |
| F-10 dialog without a drive | PASS |
| F-10 with a drive | PENDING on build 2 (no spare drive). The owner's photos `IMG_0315`/`IMG_0316` show it on build 2. The round-1 wording repairs (`053c618`) ship in the redesign's build A; R-19 checks them |
| F-12 routing | PASS by meaning; the literal sha check fails because Mixxx rewrites `soundconfig.xml` at start with a different element order (finding 2) |
| Holdout (REC, Recordings load, pads, loop, FX, CPU) | PASS: two decks 3-4 % readout, `get_throttled` 0x0 |

## Council round 1 (at `ac18cb2`)

| Seat | Score | Main point |
|---|---|---|
| Claude Opus 5.5 xhigh | 8 | F-10 had no check with a drive |
| Claude Fable 5.2 high | 8 | F-10 verifiable only in part |
| GPT-6.1 Sol xhigh | 6 | F-6 drag could still activate; F-10 drive pending; sway crash open |

Reports: `deploy/recovery-20261116-fixes/council/round1-*.md`.

## Open findings and where they went

| Finding | Status |
|---|---|
| F-10 with a drive; the dead "Prepare selected disk" button | Explained in the redesign plan R-4 (the button can never act with controlled media off). The redesign replaces both dialogs with the Media screen (R-4); R-19 records the proof on build A first. |
| F-6 a drag can open a row | Fixed in `053c618` (C-1); checked again in R-19. |
| F-5 saved "both times" mode | Fixed in `053c618` (C-1); R-19. |
| F-9 a label tap does not toggle; no tick | Fixed in `053c618` (C-1); R-19. |
| Service stop is not a clean quit (b2 finding 1) | Fixed by `mixxx-clean-quit.patch` (`6bda16f`) and the stop unit (`669a5d7`); redesign R-14. |
| `soundconfig.xml` rewritten at start (b2 finding 2) | No change; checks compare routing by meaning. |
| MANTACORE disconnect loop (b2 finding 3) | Hardware (loose connector). The port is disabled during tests when it flaps. Owner allowed clean ejects of MANTACORE in the redesign tests. |
| Sources shows 3.75 rows (b2 finding 5) | Redesign R-9: Sources is full screen. |
| Decks empty after start (b2 finding 6) | Expected Mixxx behaviour; pads now also save within a second of a change (redesign R-13). |
| One-time sway crash after a USB storm (build 1) | Redesign R-20: pop-ups off (`72e98c4`, now `cdc5c1b`); storm re-test with clean ejects between port toggles. |
| A tracked results file | This file. |

The field-fix climb closed into the UI redesign climb (`docs/ideas/UI-REDESIGN-PLAN-20261117.md`, tuner record `mixpi-ui-redesign-20261117`) on 2026-11-17.
