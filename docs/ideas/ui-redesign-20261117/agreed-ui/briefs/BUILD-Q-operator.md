# Build Q operator brief (pi-gen run 18; the owner's standing "Alright keep going!" for this round, 2026-11-22; the fix comes from council round 9, confirmed on the card)

Read `BUILD-P-operator.md` and `BUILD-O-operator.md` (same folder) and build P's kit `deploy/test-image-20261123p/` first. Every rule there holds, and build P's kit is your method. Only these change:

- **One pi-gen run only, the 18th.** It ships build P plus wave J17: `mixxx-menu-current-row.patch` (the Sources menu's edge stays on the list in view: a press or drag on the open menu keeps it; ☰ restores the row whose list is shown). The export-only resume after the known loop-device race counts as the same run. Any other failure: stop and report.
- **The card is on build P** (`deploy/ui-redesign-20261117/buildP-update/UPDATE-LOG.md`): `/usr/bin/mixxx` `de4d028e…`, sidecar `10f0f01e…`, 72 patches, style.qss `d10ee1c4…`.
- **Commit:** the one the orchestrator names.
- **Patches:** build P's 72, byte-equal, plus `mixxx-menu-current-row.patch` (73).
- **No skin change:** skin tools and generated skin byte-identical to build P's. Step 7 only verifies.
- **Names:** workspace `/srv/uiQ-<date>`, image `mixpi-test-<date>q`, kit `deploy/test-image-<date>q/`.
- **ccache:** copy build P's ccache read only.
- **Diffs:** image P → image Q, and card (build P) → image Q. Report any package drift; don't run apt in UPDATE.md.
- **`UPDATE.md` for Q:** build P's pattern (the `.deb`, the sidecar and the new patch; steps 5 and 7 only verify the skin). Mixxx quit with Ctrl+Q during the update and started last.
- **Same safety rules as P.** VM b only via `~/.config/mixpi-lima-b/ssh.config` host `lima-b-durable`, never `limactl`; the Mac watcher with its 5 GiB stop, started before the launch, at least 20 GiB free at the start; fstrim after cleanup; never touch the Pi or any drive; never switch a USB port off; open no window or app on the Mac; check VM b for other heavy jobs before the launch.

## Final report (short)
As for build P.
