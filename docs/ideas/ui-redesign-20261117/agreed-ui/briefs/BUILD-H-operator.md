# Build H operator brief (pi-gen run 9, approved by the owner on 2026-11-19)

Read `BUILD-C-operator.md` to `BUILD-G-operator.md` (same folder) first. Every rule there holds. Build G's kit is your method: `deploy/test-image-20261119g/` (`BUILD.md`, `UPDATE.md`, `DEPLOY-FILES.txt`, `logs/`, including `mac-space-watch.sh`). Only these change:

- **One pi-gen run only, the 9th.** The owner approved it after acceptance G ("Yes, build H first"). If the run fails, stop and report; do not start another.
- **Commit:** the one the orchestrator names.
- **Patches:** 56. That is build G's 55 plus `mixxx-shared-columns-stretch.patch`.
- **Names:**
  - workspace `/srv/uiH-20261119`;
  - image `mixpi-test-20261119h`, with `IMG_DATE=2026-11-19`;
  - kit `deploy/test-image-20261119h/`.
- **Build settings:** controlled media stays OFF, with no `MIXPI_MEDIA_EJECT`. For ccache, copy `/srv/uiG-20261119/src/.ccache` (read only).
- **Diffs:** image G → image H, and card → image H. The card is image G plus `/etc/mixpi/media-eject`.
- **Expected changes from G:** the one patch, the `.deb` and its sidecar, and nothing else; no skin tool has changed since `9a0d09e`. List anything else.
- **`UPDATE.md` for H:** build G's steps, adapted.
  - MANTACORE's port rule stays lifted (plan 12.8). Never disable its hub port. MANTACORE stays read-only.
- **Disk:** at least 20 GiB free on the Mac before you start. Use the 15 s watcher with its 5 GiB stop. Trim after `work/` goes and again at the end, running `fstrim` twice if the disk file stays large, as build G did.
- **The card:** the build itself never touches the Pi.

## Final report (short)
As for build G:
- the commit, the pi-gen exit and the duration;
- the `.deb` sha256 and the patch count;
- the checks;
- the two manifest diffs;
- Mac space at the start, the lowest point and the end;
- any difference from build G's method;
- the path of `UPDATE.md`.
