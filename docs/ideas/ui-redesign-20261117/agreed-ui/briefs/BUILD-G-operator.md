# Build G operator brief (pi-gen run 8, approved by the owner on 2026-11-19)

Read `BUILD-C-operator.md`, `BUILD-D-operator.md`, `BUILD-E-operator.md` and `BUILD-F-operator.md` (same folder) first. Every rule there holds. Build F's kit is your method: `deploy/test-image-20261118f/` (`BUILD.md`, `UPDATE.md`, `DEPLOY-FILES.txt`, `logs/`, including `mac-space-watch.sh`). Only these change:

- **One pi-gen run only, the 8th.** The owner approved it in the build F session: "Please Fix" for the overview strip, and "Fix both" for the column width (plan 12.8). If the run fails, stop and report; do not start another.
- **Commit:** the one the orchestrator names.
- **Patches:** 55. That is build F's 53, plus `mixxx-overview-playposition.patch` and `mixxx-shared-columns-width.patch`.
- **Names:**
  - workspace `/srv/uiG-20261119`;
  - image `mixpi-test-20261119g`, with `IMG_DATE=2026-11-19`;
  - kit `deploy/test-image-20261119g/`.
- **Build settings:** controlled media stays OFF, with no `MIXPI_MEDIA_EJECT`. For ccache, copy `/srv/uiF-20261118/src/.ccache` (read only).
- **Diffs:** image F → image G, and card → image G. The card is image F plus `/etc/mixpi/media-eject`.
- **Expected changes from F:** the two patches, the `.deb` and its sidecar, and nothing else; no skin tool has changed since `c97fbbd`. List anything else.
- **`UPDATE.md` for G:** build F's steps, adapted.
  - Install the two new patches and the `.deb`, and check every skin tool and the skin tree; they should already match.
  - **MANTACORE's port rule is lifted** (plan 12.8). Do not disable its hub port after a boot. MANTACORE stays read-only: never write, move or delete anything there.
- **Disk:** at least 20 GiB free on the Mac before you start. Use the 15 s watcher with its 5 GiB stop, and trim after `work/` goes and again at the end.
- **The card:** the build itself never touches the Pi. The orchestrator runs the in-place update afterwards.

## Final report (short)
As for build D:
- the commit, the pi-gen exit and the duration;
- the `.deb` sha256 and the patch count;
- the checks;
- the two manifest diffs;
- Mac space at the start, the lowest point and the end;
- any difference from build F's method;
- the path of `UPDATE.md`.
