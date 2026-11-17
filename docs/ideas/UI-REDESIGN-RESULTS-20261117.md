# UI redesign climb results, 2026-11-17 (tracked record)

Plan: `docs/ideas/UI-REDESIGN-PLAN-20261117.md` (owner answers in 10.1). Tuner record: `mixpi-ui-redesign-20261117`. Prototype: `docs/ideas/ui-redesign-20261117/prototype/` (published privately). Updated at each gate. Evidence folders under `deploy/` stay untracked.

## Gates

| When | Commit | Mac suite | Native gate (VM b) | Notes |
|---|---|---|---|---|
| Wave 0 baseline | `cdc5c1b` | exit 0 | 135/135, 0 skips | Held options `a8a86fa`, `72e98c4` cherry-picked as `6bda16f`, `cdc5c1b` |
| Wave 1 integrated | `9d9bf30` | 642 run, OK (133 platform skips) | 153/153, 0 skips | N1 save-on-change + stop unit, N2 Sources rail/edit + scan bar, S shell/pads/Load sample/Sources/icons |
| Wave 1 skin fix | `ec580e1` | builder: 619 OK | not needed (skin only) | Sampler layout, Choose pad stacking, Sources search, header Back removed, EDIT LIST → DONE |

## Wave 0 on the test card (build 2)

- Settings and logs backed up: `deploy/ui-redesign-20261117/stage0/backup/`.
- Before shots of every page: `deploy/ui-redesign-20261117/stage0/before-*.png`.
- Routing set to stereo at the owner's request (Q8): Master 1-2, Headphones 3-4 on the Starlight's USB audio (4 channels FL FR RL RR). Backup on the card: `~/.mixxx/soundconfig.xml.before-stereo-20261117`. After a reboot Mixxx kept it (`stage0/reboot-1.txt`).
- The card's journal is volatile, so the shutdown order of the previous boot cannot be read; R-14's Pi check uses Mixxx's own "shutdown complete" line.

## Wave 1 skin preview on build 2

`deploy/ui-redesign-20261117/wave1-preview/`: top bar, ☰/✕, ✎ Actions, 8 pads with Stop/Clear, full-screen Sources, Load sample render on today's Mixxx. Four skin defects found and fixed in `ec580e1` (see above); re-check after build A.

## Builds

| Build | Commit | State |
|---|---|---|
| A | `9d9bf30` (+ skin tools from `ec580e1`) | pi-gen exit 0 on VM b, 02:27-02:39Z; check, diff and update kit in progress (`deploy/test-image-20261117a/`) |
