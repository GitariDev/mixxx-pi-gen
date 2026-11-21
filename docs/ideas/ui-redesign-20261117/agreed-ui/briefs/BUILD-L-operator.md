# Build L operator brief (pi-gen run 13; the owner said yes on 2026-11-21: "do that last round fix have everything ready for the morning. Do all the proof")

Read `BUILD-K-operator.md`, `BUILD-J-operator.md` (same folder) and build K's kit `deploy/test-image-20261121k/` (`BUILD.md`, `UPDATE.md`, `DEPLOY-FILES.txt`, `logs/`) first. Every rule there holds, and build K's kit is your method. Only these change:

- **One pi-gen run only, the 13th**. It ships build K plus wave J11: `mixxx-removable-rows-fix.patch`. Folders › Removable Devices drops only a drive that has gone, never a plain folder such as `/media/SD-Backup` (council round 6). The export-only resume after the known loop-device race counts as the same run. Any other failure: stop and report.
- **Commit:** the one the orchestrator names.
- **Patches:** build K's 67 plus `mixxx-removable-rows-fix.patch` (68).
- **No skin change:** the skin tools are byte-identical to build K's (= J's). Check that, and that the generated skin equals build K's (`skin.xml` `ef7bd369…`, `style.qss` `9e40ec45…`).
- **Names:**
  - workspace `/srv/uiL-<date>`;
  - image `mixpi-test-<date>l`;
  - kit `deploy/test-image-<date>l/`.
- **ccache:** copy build K's ccache (`/srv/uiK-20261121`), read only.
- **Diffs:** image K → image L, and card → image L. The card is image K's Mixxx and skin on image I's packages, plus `/etc/mixpi/media-eject`.
- **`UPDATE.md` for L:** build K's steps, adapted.
  - Only the `.deb`, the sidecar and the new patch change.
  - Steps 5 and 7 only verify the skin, unless the diffs show a change.
  - Don't run apt; report the package drift as build J did.
- **Same safety rules as J:**
  - VM b only through the durable SSH config; never `limactl`.
  - The Mac watcher with its 5 GiB stop; at least 20 GiB free on the Mac before you start.
  - fstrim after cleanup.
  - Never touch the Pi or any drive, and never switch a USB port off.
  - Open no window or app on the Mac.

## Final report (short)
As for build K.
