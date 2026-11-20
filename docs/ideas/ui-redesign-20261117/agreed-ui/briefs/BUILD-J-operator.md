# Build J operator brief (pi-gen run 11; run only after the owner says yes)

Read `BUILD-C-operator.md` to `BUILD-I-operator.md` (same folder) first. Every rule there holds. Build I's kit is your method: `deploy/test-image-20261120i/` (`BUILD.md`, `UPDATE.md`, `DEPLOY-FILES.txt`, `logs/`, including `mac-space-watch.sh`). Only these change:

- **One pi-gen run only, the 11th**, and only after the owner's yes. It ships the quit-crash fix and the two council round 4 skin repairs (results: waves J1-J3). If the run fails in the export step with the loop-device race build I hit, finish it with an export-only resume through pi-gen's `SKIP` files. That counts as the same run. Any other failure: stop and report.
- **Commit:** the one the orchestrator names.
- **Patches:** 60. That is build I's 59 plus `mixxx-quit-library-widget.patch`.
- **The skin changes this time:**
  - `mixpi-sources-menu.qss` gains `text-transform: none` (wave J2);
  - `mixpi-performance.qss` changes the USB chip's colours (wave J3);
  - `mixpi-performance.py` changes only a comment.
  - List every changed generated skin file, check that the image's skin matches what the new tools produce from the originals, and check that no generated file goes stale.
- **Names:**
  - workspace `/srv/uiJ-<date>`;
  - image `mixpi-test-<date>j`, with `IMG_DATE` set to the build day;
  - kit `deploy/test-image-<date>j/`.
- **Build settings:** controlled media stays OFF, with no `MIXPI_MEDIA_EJECT`. For ccache, copy `/srv/uiI-20261120/src/.ccache` (read only).
- **Diffs:** image I → image J, and card → image J. The card is image I plus `/etc/mixpi/media-eject`.
- **`UPDATE.md` for J:** build I's steps, adapted.
  - Copy the changed skin tools (step 5 now copies them, owner and mode as in the image).
  - Regenerate the skin from the originals (step 7) and check the tree against image I's.
  - MANTACORE's port rule stays lifted, and MANTACORE stays read-only.
- **VM b's Lima files were lost to the macOS `/tmp` cleanup** (memory: tmp-cleanup-breaks-lima-b).
  - Reach VM b only with `ssh -F ~/.config/mixpi-lima-b/ssh.config lima-b-durable`. Build I's scripts already do this.
  - Never run `limactl stop` or `limactl start`.
  - Copy files in and out with `scp -F ~/.config/mixpi-lima-b/ssh.config`, or with tar over ssh.
  - `LIMA_HOME` is not needed.
- **Disk:** at least 20 GiB free on the Mac before you start. Use the 15 s watcher with its 5 GiB stop. Trim after `work/` goes and again at the end, running `fstrim` twice if the disk file stays large.
- **The card:** the build itself never touches the Pi.

## Final report (short)
As for build I:
- the commit, the pi-gen exit and the duration;
- the `.deb` sha256 and the patch count;
- the checks;
- the two manifest diffs, including the skin files that changed;
- Mac space at the start, the lowest point and the end;
- any difference from build I's method;
- the path of `UPDATE.md`.
