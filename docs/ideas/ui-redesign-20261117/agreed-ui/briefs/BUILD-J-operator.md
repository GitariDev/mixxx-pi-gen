# Build J operator brief (pi-gen run 11; run only after the owner says yes)

Read `BUILD-C-operator.md` to `BUILD-I-operator.md` (same folder) first. Every rule there holds. Build I's kit is your method: `deploy/test-image-20261120i/` (`BUILD.md`, `UPDATE.md`, `DEPLOY-FILES.txt`, `logs/`, including `mac-space-watch.sh`). Only these change:

- **One pi-gen run only, the 11th**, and only after the owner's yes. It ships the quit-crash fix (wave J1), the eject and ☰-after-OPEN fixes (waves J4-J5), the drive-list sort fix (J6), the drive-rows cache fix (J7), the rekordbox text fix (J8) and the Zoom row in Settings › Interface (J9, spec 2f). The owner said no to the J2 and J3 skin changes (spec 2e); they are reverted. If the run fails in the export step with the loop-device race build I hit, finish it with an export-only resume through pi-gen's `SKIP` files. That counts as the same run. Any other failure: stop and report.
- **Commit:** the one the orchestrator names.
- **Patches:** build I's 59 plus `mixxx-quit-library-widget.patch`, `mixxx-eject-top-menu.patch`, `mixxx-media-open-inside.patch`, `mixxx-external-sort.patch`, `mixxx-drive-track-cache.patch` `mixxx-rekordbox-utf16-text.patch` and `mixxx-zoom-setting.patch` (66). The orchestrator names the commit and confirms the count.
- **One skin change this time (J9):** the skin's only change from build I is the Zoom row on the Interface settings page (and any rule J9 names). Check that the image's generated skin differs from build I's only there.
- **Names:**
  - workspace `/srv/uiJ-<date>`;
  - image `mixpi-test-<date>j`, with `IMG_DATE` set to the build day;
  - kit `deploy/test-image-<date>j/`.
- **Build settings:** controlled media stays OFF, with no `MIXPI_MEDIA_EJECT`. For ccache, copy `/srv/uiI-20261120/src/.ccache` (read only).
- **Diffs:** image I → image J, and card → image J. The card is image I plus `/etc/mixpi/media-eject`.
- **`UPDATE.md` for J:** build I's steps, adapted.
  - The skin changes (J9), so steps 5 and 7 copy and regenerate it as build I did.
  - MANTACORE's port rule stays lifted, and MANTACORE stays read-only.
- **VM b's Lima files were lost to the macOS `/tmp` cleanup** (memory: tmp-cleanup-breaks-lima-b).
  - Reach VM b only with `ssh -F ~/.config/mixpi-lima-b/ssh.config lima-b-durable`. Build I's scripts already do this.
  - Never run `limactl stop` or `limactl start`.
  - Copy files in and out with `scp -F ~/.config/mixpi-lima-b/ssh.config`, or with tar over ssh.
  - `LIMA_HOME` is not needed.
- **Disk:** at least 20 GiB free on the Mac before you start. Use the 15 s watcher with its 5 GiB stop. Trim after `work/` goes and again at the end, running `fstrim` twice if the disk file stays large.
- **The card:** the build itself never touches the Pi. The owner is playing on it.
- **USB ports are never switched off** (spec 2e), in `UPDATE.md` or anywhere else.

## Final report (short)
As for build I:
- the commit, the pi-gen exit and the duration;
- the `.deb` sha256 and the patch count;
- the checks;
- the two manifest diffs, including the skin files that changed;
- Mac space at the start, the lowest point and the end;
- any difference from build I's method;
- the path of `UPDATE.md`.
