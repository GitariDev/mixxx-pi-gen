# Build E operator brief (pi-gen run 6, approved by the owner on 2026-11-18)

Read `BUILD-C-operator.md` and `BUILD-D-operator.md` (same folder) first. Every rule there holds. Build D's kit is your method: `deploy/test-image-20261118d/` (`BUILD.md`, `UPDATE.md`, `DEPLOY-FILES.txt`, `logs/`, including `mac-space-watch.sh`). Only these change:

- **One pi-gen run only, the 6th.** The owner approved it after council round 2 ("do 2"; spec 2b, plan 12.6). If it fails, stop and report; do not start another.
- **Commit:** the one the orchestrator names. **Patches: 52**, build D's 50 plus `mixxx-sources-open-edge.patch` and `mixxx-sampler-clear-playing.patch`.
- **Names:** workspace `/srv/uiE-20261118`, image `mixpi-test-20261118e`, `IMG_DATE=2026-11-18`, kit `deploy/test-image-20261118e/`. Controlled media OFF, no `MIXPI_MEDIA_EJECT`. ccache: copy `/srv/uiD-20261118/src/.ccache` (read only).
- **Diffs:**
  - image D → image E (`/srv/uiD-20261118/manifest-d.txt`, or whatever build D named it);
  - card → image E. The card is image D, plus `/etc/mixpi/media-eject`, plus the in-place skin-tool installs. Those are `mixpi-performance.py`, `mixpi-performance.qss` and `pioneered-touch.qss`, from `2eedc8f` and then `ee024dd`; their skin was regenerated. They should already equal image E's.
- **Expected changes from D:**
  - the two patches;
  - the `.deb`;
  - the skin tools `mixpi-performance.py`, `mixpi-performance.qss` and `pioneered-touch.qss`;
  - the generated skin.
  - List anything else.
- **`UPDATE.md` for E:** build D's steps, adapted. Install the two new patches and the skin tools; for tools the card already has at the right bytes, the step checks them and moves on. Regenerate the skin from the upstream originals, and check on a copy whether any generated file goes stale. The backlight rule stays as it is.
- **Disk:** at least 20 GiB free on the Mac before you start. Use the 15 s watcher with its 5 GiB stop, and trim after `work/` goes and again at the end.

## Final report (short)
As for build D: the commit, the pi-gen exit and duration, the `.deb` sha256, the patch count, the checks, the two manifest diffs, Mac space at the start, lowest and end, any difference from build D's method, and the path of `UPDATE.md`.
