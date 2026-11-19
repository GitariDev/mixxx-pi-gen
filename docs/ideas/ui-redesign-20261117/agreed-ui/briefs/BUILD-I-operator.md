# Build I operator brief (pi-gen run 10, approved by the owner on 2026-11-20)

Read `BUILD-C-operator.md` to `BUILD-H-operator.md` (same folder) first. Every rule there holds. Build H's kit is your method: `deploy/test-image-20261119h/` (`BUILD.md`, `UPDATE.md`, `DEPLOY-FILES.txt`, `logs/`, including `mac-space-watch.sh`). Only these change:

- **One pi-gen run only, the 10th.** The owner approved it after council round 3 (spec 2d, plan 12.9). If the run fails, stop and report; do not start another.
- **Commit:** the one the orchestrator names.
- **Patches:** 59. That is build H's 56 plus `mixxx-drive-tracks-row.patch`, `mixxx-media-chip-ping.patch` and `mixxx-sources-menu-shadow.patch`.
- **The skin changes this time:**
  - `pioneered-touch.qss` gains the header empty-area rule (wave H1);
  - the generator and stylesheets gain the menu shadow strip (wave I3).
  - The generated skin tree will differ from H's. List every changed file, check that the image's generated skin matches what the new tools produce from the originals, and check that no generated file goes stale.
- **Names:**
  - workspace `/srv/uiI-20261120`;
  - image `mixpi-test-20261120i`, with `IMG_DATE=2026-11-20`;
  - kit `deploy/test-image-20261120i/`.
- **Build settings:** controlled media stays OFF, with no `MIXPI_MEDIA_EJECT`. For ccache, copy `/srv/uiH-20261119/src/.ccache` (read only).
- **Diffs:** image H → image I, and card → image I. The card is image H plus `/etc/mixpi/media-eject`.
- **`UPDATE.md` for I:** build H's steps, adapted.
  - Copy the changed skin tools (step 5 now copies them, owner and mode as in the image).
  - Regenerate the skin from the originals (step 7) and check the tree against image I's.
  - MANTACORE's port rule stays lifted, and MANTACORE stays read-only.
- **VM b's Lima files were lost to the macOS `/tmp` cleanup** (memory: tmp-cleanup-breaks-lima-b).
  - Reach VM b only with `ssh -F ~/.config/mixpi-lima-b/ssh.config lima-b-durable`. Adapt every `limactl shell b` in build H's scripts to that.
  - Never run `limactl stop` or `limactl start`.
  - Copy files in and out with `scp -F ~/.config/mixpi-lima-b/ssh.config`, or with tar over ssh.
  - `LIMA_HOME` is not needed.
- **Disk:** at least 20 GiB free on the Mac before you start. Use the 15 s watcher with its 5 GiB stop. Trim after `work/` goes and again at the end, running `fstrim` twice if the disk file stays large.
- **The card:** the build itself never touches the Pi.

## Final report (short)
As for build H:
- the commit, the pi-gen exit and the duration;
- the `.deb` sha256 and the patch count;
- the checks;
- the two manifest diffs, including the skin files that changed;
- Mac space at the start, the lowest point and the end;
- any difference from build H's method, including the SSH change;
- the path of `UPDATE.md`.
