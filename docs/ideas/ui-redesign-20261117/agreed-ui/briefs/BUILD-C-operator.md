# Build C operator brief (pi-gen run 4, approved by the owner)

You are the build operator (Claude Opus 5.5, medium effort) for build C of the MixPi UI redesign. The orchestrator (Claude Opus 5.5 xhigh) installs the result on the test card. **You never touch the Raspberry Pi, the test card, EOS, MANTACORE or any USB drive.**

The owner approved exactly one pi-gen run for build C (plan section 12.4). A second run needs the owner's yes, so if the run fails, stop and report; do not start another.

## What to build

- Branch `feat/pi-performance-target` at the commit the orchestrator names in your prompt. Use `git archive <commit>` into `src/` and again into `ref-<short>/`, as build B did.
- Follow build B's method exactly: `deploy/test-image-20261117b/BUILD.md` and its `logs/` (`run-build.sh`, `build.env`, `assembly.config`, `finish-image.sh`, `manifest.py`, `manifest-diff.py`, `bash-env.sh`, `service-policy.py`). Copy those scripts into the new workspace and change only the names (`uiB`→`uiC`, `20261117b`→`20261118c`, the commit).
- Workspace: a new `/srv/uiC-20261118` on Lima VM `b` (`export LIMA_HOME=/tmp/mq1110-1943`). Never change or delete any other `/srv` folder. Never touch the VMs `colima-mixpi-ui` or `colima-synthetic`.
- Image name `mixpi-test-20261118c`, `IMG_DATE=2026-11-18`, `MIXPI_CONTROLLED_MEDIA=0`, and **no** `MIXPI_MEDIA_EJECT` (the build log must print `controlled media OFF` and `media eject OFF`).
- ccache: copy build B's `/srv/uiB-20261117/src/.ccache` with `cp -a` (read the source only).
- A new first-user password, made as build B made it, kept only in `/srv/uiC-20261118/private/first-user.env` (mode 600). Never print or copy it.

## Disk safety (the Mac filled once during build B)

- VM `b`'s disk file is `/tmp/mq1110-1943/b/disk` on the Mac and grows about 15 GB during a build.
- Before you start: `df -h /System/Volumes/Data` must show at least 20 GiB free, and VM `b` at least 24 GB free inside. If not, stop and report.
- During the build, log the Mac's free space every 15 s to `logs/mac-space.log`, as build B did. If it drops under 5 GiB, stop the build cleanly and report.
- Never copy the image to the Mac. The `.deb` and its sidecar do go to the Mac kit.
- After the checks: unmount, check that the raw image sha256 is unchanged, delete the raw image, `work/` and any scratch folders in your workspace, then `sudo fstrim -v /` in the VM. Log the Mac's free space and the disk file's size at the end.

## Checks after the build

- `mixxx-candidate.py verify` rc 0, and the sidecar's patch list equals `bash stage3/01-install-packages/01-run.sh --mixxx-print-patches` at the commit, in order.
- `finish-image.sh check` with build B's checks plus these, all on a read-only mount (`ro,noload`):
  - the new patches are present and byte-equal: `mixxx-sources-menu.patch`, `mixxx-media-agreed.patch`, `mixxx-effects-save.patch`, `mixxx-save-within-second.patch`, `mixxx-agreed-controls.patch`, `mixxx-sources-menu-fixes.patch`;
  - `/opt/mixpi-skin-tools` holds exactly the files `stage3/01-install-packages/02-run.sh` installs (now nine, with `mixpi-sources-menu.qss` and `mixpi-media-page.qss`), each byte-equal;
  - the generated `style.qss` contains all five installed stylesheets;
  - `/etc/udev/rules.d/99-mixpi-backlight.rules` (or wherever `stage3/02-desktop/03-run.sh` installs it) is byte-equal to the repo file, 644 root:root;
  - `pi` is in the `video` group;
  - everything build B checked still holds (stop unit, logind drop-in, udiskie `--no-notify`, controlled media OFF, media eject OFF, no soundconfig.xml in /home/pi or /etc/skel).
- The manifest with build B's `manifest.py`, then the two diffs with `manifest-diff.py`:
  1. image B → image C (`/srv/uiB-20261117/manifest-b.txt`);
  2. card → image C. The card is image B plus what was changed on it since: `/etc/mixpi/media-eject` (the eject gate the owner approved, opened in place after build B), and a Pioneered skin that the orchestrator regenerates during the update. List any other difference.
- `.deb` diff against build B's (`dpkg-deb -R` + `diff -rq`).
- Skin: reproduce, on a copy in the VM, the exact skin tree that step 7 of the update will produce on the card (from a clean Pioneered checkout plus the commit's tools; build B's `logs/skin-experiments.sh` shows how). Put its sha256 list and the generated `skin.xml` and `style.qss` in `deploy-files/expected-skin/`, with the upstream originals' list.

## The kit for the in-place update (what you deliver)

A new folder `deploy/test-image-20261118c/` in the main checkout (`/Users/gitaritirima/Documents/Workspace/Personal Projects/mixxx-pi-gen`), laid out like `deploy/test-image-20261117b/`:
- `BUILD.md` (identities, inputs, steps and timings, check output, deviations), `DEPLOY-FILES.txt` (method and the A-list of files to put on the card, with sha256, mode and owner), `SHA256SUMS`, `logs/`, `deploy-files/` (the `.deb`, its sidecar, every changed or new file, `expected-final.sha256`, `expected-patches.sha256`, `expected-skin/`, its own `SHA256SUMS`).
- `UPDATE.md`: build B's steps 0-9 adapted to build C. Keep every safety step (preflight, staged-byte check, backups before anything changes, Ctrl+Q quit, the skin regenerated from the upstream originals, every sha256 checked, Mixxx started last, the rollback paragraph). Add the new files: the two stylesheets in `/opt/mixpi-skin-tools`, the six patches in `/opt/mixxx-patches`, and the udev rule, then `sudo udevadm control --reload` and `sudo udevadm trigger --subsystem-match=backlight --action=add`, then check that `/sys/class/backlight/*/brightness` is group `video` with group write. Do not touch `/etc/mixpi/media-eject`, `mixxx.cfg`, `soundconfig.xml`, `samplers.xml`, `effects.xml` or the music.
- Do not commit anything: `deploy/` is untracked evidence. Only write in `deploy/test-image-20261118c/`.

## Final report (short)

Commit built, pi-gen exit code and duration, the `.deb` sha256, patch count, check results (each item above), the two manifest diffs in a few lines, Mac free space at the start, lowest and end, VM free space at the end, anything that differs from build B's method, and the path of `UPDATE.md`.
