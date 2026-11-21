# Build K operator brief (pi-gen run 12; run only after the owner says yes)

Read `BUILD-J-operator.md` (same folder) and build J's kit `deploy/test-image-20261121j/` (`BUILD.md`, `UPDATE.md`, `DEPLOY-FILES.txt`, `logs/`) first. Every rule there holds, and build J's kit is your method. Only these change:

- **One pi-gen run only, the 12th**, after the owner's yes. It ships build J plus wave J10: `mixxx-eject-folders-view.patch`. After an eject or a pull, a drive's folder shown through Folders leaves the table and ☰ opens at the top level (spec 2e as 2g applies it). The export-only resume after the known loop-device race counts as the same run. Any other failure: stop and report.
- **Commit:** the one the orchestrator names.
- **Patches:** build J's 66 plus `mixxx-eject-folders-view.patch` (67).
- **No skin change:** the skin tools are byte-identical to build J's. Check that, and that the generated skin equals build J's (`skin.xml` `ef7bd369…`, `style.qss` `9e40ec45…`).
- **Names:**
  - workspace `/srv/uiK-<date>`;
  - image `mixpi-test-<date>k`;
  - kit `deploy/test-image-<date>k/`.
- **ccache:** copy build J's ccache, read only.
- **Diffs:** image J → image K, and card → image K. The card is image J's Mixxx and skin on image I's packages, plus `/etc/mixpi/media-eject`.
- **`UPDATE.md` for K:** build J's steps, adapted.
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
As for build J.
