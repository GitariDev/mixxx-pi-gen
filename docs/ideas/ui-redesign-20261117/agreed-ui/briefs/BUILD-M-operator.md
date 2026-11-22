# Build M operator brief (pi-gen run 14; the owner said on 2026-11-22: "You can take this in with the rest of the build items and get started.")

Read `BUILD-L-operator.md`, `BUILD-K-operator.md` and `BUILD-J-operator.md` (same folder) and build L's kit `deploy/test-image-20261121l/` (`BUILD.md`, `UPDATE.md`, `DEPLOY-FILES.txt`, `logs/`) first. Every rule there holds, and build L's kit is your method. Only these change:

- **One pi-gen run only, the 14th.** It ships build L plus two waves (spec 2h):
  - J12 `mixxx-open-remount.patch`: OPEN on an ejected (SAFE TO REMOVE) drive mounts it again and reads it, with no re-plug or restart;
  - J13 `mixxx-waveform-height.patch`: the decks' main waveforms take their height from the pregain knob only, without the ReplayGain.
  The export-only resume after the known loop-device race counts as the same run. Any other failure: stop and report.
- **Commit:** the one the orchestrator names.
- **Patches:** build L's 68 plus the two above (70), in `MIXXX_PATCHES` order.
- **No skin change:** the skin tools are byte-identical to build L's. Check that, and that the generated skin equals build L's (`skin.xml` `ef7bd369…`, `style.qss` `9e40ec45…`, 48 files).
- **Packages:** stage0's `dist-upgrade` takes the current Debian packages. List them (`pkg-diff`) against image L and against the card's list after today's updates: `deploy/ui-redesign-20261117/card-apt-20261122/dpkg-after.txt` (untracked, in the main checkout). The two should match apart from what changed upstream since 19:44 today; report any difference.
- **Names:**
  - workspace `/srv/uiM-<date>`;
  - image `mixpi-test-<date>m`;
  - kit `deploy/test-image-<date>m/`.
- **ccache:** copy build L's ccache (`/srv/uiL-20261121/src/.ccache`), read only.
- **Diffs:** image L → image M, and card → image M. The card is image L's Mixxx and skin, plus today's Debian updates on image I's base, plus `/etc/mixpi/media-eject`.
- **`UPDATE.md` for M:** build L's steps, adapted.
  - Only the `.deb`, the sidecar and the two new patches change.
  - Steps 5 and 7 only verify the skin, unless the diffs show a change.
  - Don't run apt; the card's packages were updated today. Report any remaining drift.
- **Same safety rules as L:**
  - VM b only through the durable SSH config (`~/.config/mixpi-lima-b/ssh.config`, host `lima-b-durable`); never `limactl`.
  - The Mac watcher with its 5 GiB stop; at least 20 GiB free on the Mac before you start (28 GiB at 21:00 today).
  - fstrim after cleanup. Remove `/srv/uiK-20261121` only after build M's kit is complete, if space needs it.
  - Never touch the Pi or any drive, and never switch a USB port off.
  - Open no window or app on the Mac.

## Final report (short)
As for build L.
