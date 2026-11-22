# Build N operator brief (pi-gen run 15; the owner chose the header line on 2026-11-22: "this", pointing at "add the line (B)"; and said "Alright keep going!")

Read `BUILD-M-operator.md`, `BUILD-L-operator.md` and `BUILD-K-operator.md` (same folder) and build M's kit `deploy/test-image-20261122m/` first. Every rule there holds, and build M's kit is your method. Only these change:

- **One pi-gen run only, the 15th.** It ships build M plus wave J14: one new rule in `stage3/01-install-packages/files/pioneered-touch.qss` that runs the Tracks header's 1 px `#2c333d` bottom line under its empty part (spec 2h, B). The export-only resume after the known loop-device race counts as the same run. Any other failure: stop and report.
- **Commit:** the one the orchestrator names.
- **Patches:** build M's 70, each byte-equal. No Mixxx change: the `.deb` should be a rebuild of the same source (report whether `/usr/bin/mixxx` is byte-equal to build M's `03bf00fb…`; if not, say why, e.g. build-time stamps).
- **Skin change:** the skin tools differ from build M's in `pioneered-touch.qss` only (check that every other tool is byte-equal). The generated skin should differ from build M's in `style.qss` only (the new rule), with `skin.xml` `ef7bd369…` and the 48-file tree list unchanged. Report the new `style.qss` hash and the exact diff.
- **Names:** workspace `/srv/uiN-<date>`, image `mixpi-test-<date>n`, kit `deploy/test-image-<date>n/`.
- **ccache:** copy build M's ccache read only.
- **Diffs:** image M → image N, and card → image N. The card is image M as installed today (`deploy/ui-redesign-20261117/buildM-update/UPDATE-LOG.md`).
- **`UPDATE.md` for N:** build M's steps, adapted.
  - The `.deb` step only if the binary differs from the card's (otherwise verify only).
  - Install the new `pioneered-touch.qss` (and the sidecar if it changed).
  - **Step 7 now regenerates the skin**, using build K's step 7 method: restore the upstream originals, then run the two generators, then check the result equals image N's skin tree exactly (48 files; `style.qss` = image N's). Heed the K3/L3 warning: regenerating without restoring the originals gives a wrong `style.qss`.
  - Mixxx must be quit (Ctrl+Q) while the skin is replaced, and started after.
  - Don't run apt; report any package drift.
- **Same safety rules as M.** VM b only via `~/.config/mixpi-lima-b/ssh.config` host `lima-b-durable`, never `limactl`; the Mac watcher with its 5 GiB stop and at least 20 GiB free at the start; fstrim after cleanup; never touch the Pi or any drive; never switch a USB port off; open no window or app on the Mac.

## Final report (short)
As for build M, plus the skin diff and the new `style.qss` hash.
