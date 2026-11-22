# Build O operator brief (pi-gen run 16; owner on 2026-11-22: "Let's set the gain to around .80", "See comments on loudness. Do a focused change there.", and "Alright keep going!")

Read `BUILD-N-operator.md`, `BUILD-M-operator.md` and `BUILD-K-operator.md` (same folder) and build N's kit `deploy/test-image-20261122n/` first. Every rule there holds, and build N's kit is your method. Only these change:

- **One pi-gen run only, the 16th.** It ships build N (J14, the header's 1 px line) plus wave J15: `mixxx-waveform-height-gain.patch`, the decks' main waveforms at 0.80 of J13's height. The export-only resume after the known loop-device race counts as the same run. Any other failure: stop and report.
- **Build N was never installed.** The card is on **build M** (`deploy/ui-redesign-20261117/buildM-update/UPDATE-LOG.md`): `/usr/bin/mixxx` `03bf00fb…`, sidecar `8b3f7c80…`, `pioneered-touch.qss` `51ba9c2f…`, style.qss `9e40ec45…`, 70 patches. `UPDATE.md` for O goes from build M's card state.
- **Commit:** the one the orchestrator names.
- **Patches:** build N's 70, byte-equal, plus `mixxx-waveform-height-gain.patch` (71).
- **Skin:** as build N's: only `pioneered-touch.qss` differs from build M's tools, and only `style.qss` differs in the generated skin (`d10ee1c4…`, skin.xml `ef7bd369…`, 48 files). Check that image O's skin equals image N's exactly.
- **Names:** workspace `/srv/uiO-<date>`, image `mixpi-test-<date>o`, kit `deploy/test-image-<date>o/`.
- **ccache:** copy build N's ccache read only.
- **Diffs:** image N → image O, image M → image O, and card (build M) → image O.
- **`UPDATE.md` for O:** build N's steps, from the build M card state: the `.deb`, the sidecar, the new patch, the new `pioneered-touch.qss`, and step 7's skin regeneration (restore the originals first, then the two generators; check the tree and `style.qss` `d10ee1c4…`). Mixxx is quit with Ctrl+Q for the whole update and started last. Don't run apt; report any drift.
- **Same safety rules as N.** VM b only via `~/.config/mixpi-lima-b/ssh.config` host `lima-b-durable`, never `limactl`; the Mac watcher with its 5 GiB stop and at least 20 GiB free at the start, started before the launch; fstrim after cleanup; never touch the Pi or any drive; never switch a USB port off; open no window or app on the Mac. VM b may also be used by an R&D thread: before you launch, check nothing heavy runs (`pgrep -af "[b]uild.sh|[n]inja|[c]make --build|[c]test"`) and wait if it does.

## Final report (short)
As for build N.
