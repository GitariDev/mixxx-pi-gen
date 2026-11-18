# Build F operator brief (pi-gen run 7, approved by the owner on 2026-11-18)

Read `BUILD-C-operator.md`, `BUILD-D-operator.md` and `BUILD-E-operator.md` (same folder) first. Every rule there holds. Build E's kit is your method: `deploy/test-image-20261118f/` (`BUILD.md`, `UPDATE.md`, `DEPLOY-FILES.txt`, `logs/`, including `mac-space-watch.sh`). Only these change:

- **one pi-gen run only, the 7th.** The owner approved it after council round 2 ("do 2"; spec 2b, plan 12.6). If it fails, stop and report; do not start another.
- **Commit:** the one the orchestrator names. **Patches: 53**, build E's 52 plus `mixxx-shared-columns.patch`.
- **Names:** workspace `/srv/uiF-20261118`, image `mixpi-test-20261118f`, `IMG_DATE=2026-11-18`, kit `deploy/test-image-20261118f/`. Controlled media OFF, no `MIXPI_MEDIA_EJECT`. ccache: copy `/srv/uiE-20261118/src/.ccache` (read only).
- **Diffs:** image E → image F (`/srv/uiE-20261118/manifest-e.txt`, or whatever build E named it), and card → image F. The card is image E plus `/etc/mixpi/media-eject`.
- **Expected changes from E:** the one patch, the `.deb`, and nothing else (no skin tool changed since `c87fff8`). List anything else.
- **`UPDATE.md` for F:** build E's steps, adapted. Install the new patch and the `.deb`, and check every skin tool and the skin tree (they should already match). The backlight rule stays as it is.
- **Disk:** at least 20 GiB free on the Mac before you start. Use the 15 s watcher with its 5 GiB stop, and trim after `work/` goes and again at the end.

## Final report (short)
As for build D: the commit, the pi-gen exit and duration, the `.deb` sha256, the patch count, the checks, the two manifest diffs, Mac space at the start, lowest and end, any difference from build D's method, and the path of `UPDATE.md`.
