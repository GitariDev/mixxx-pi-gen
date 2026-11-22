# Build P operator brief (pi-gen run 17; the owner's standing "Alright keep going!" for this round, 2026-11-22; the fix comes from council round 8)

Read `BUILD-O-operator.md`, `BUILD-N-operator.md` and `BUILD-K-operator.md` (same folder) and build O's kit `deploy/test-image-20261122o/` first. Every rule there holds, and build O's kit is your method. Only these change:

- **One pi-gen run only, the 17th.** It ships build O plus wave J16: `mixxx-menu-place-fix.patch` (☰ after OPEN opens inside the drive with the edge on TRACKS, also for the first OPEN after a start). The export-only resume after the known loop-device race counts as the same run. Any other failure: stop and report.
- **The card is on build O** (`deploy/ui-redesign-20261117/buildO-update/UPDATE-LOG.md`): `/usr/bin/mixxx` `8de21527…`, sidecar `f422182b…`, 71 patches, style.qss `d10ee1c4…`.
- **Commit:** the one the orchestrator names.
- **Patches:** build O's 71, byte-equal, plus `mixxx-menu-place-fix.patch` (72).
- **No skin change:** the skin tools and the generated skin must be byte-identical to build O's (48 files, `skin.xml` `ef7bd369…`, `style.qss` `d10ee1c4…`). Step 7 only verifies.
- **Names:** workspace `/srv/uiP-<date>`, image `mixpi-test-<date>p`, kit `deploy/test-image-<date>p/`.
- **ccache:** copy build O's ccache read only.
- **Diffs:** image O → image P, and card (build O) → image P. Packages: report any drift against the card's list (image O's); don't run apt in UPDATE.md.
- **`UPDATE.md` for P:** build M's pattern (only the `.deb`, the sidecar and the new patch change; steps 5 and 7 only verify the skin). Mixxx quit with Ctrl+Q during the update and started last.
- **Same safety rules as O.** VM b only via `~/.config/mixpi-lima-b/ssh.config` host `lima-b-durable`, never `limactl`; the Mac watcher with its 5 GiB stop, started before the launch, at least 20 GiB free at the start; fstrim after cleanup; never touch the Pi or any drive; never switch a USB port off; open no window or app on the Mac; check VM b for other heavy jobs before the launch.

## Final report (short)
As for build O.
