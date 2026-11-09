# Performance, strip-down and CDJ-style media plan

Researched **2026-11-08**. Sources: live SSH inspection, a Codex OS review,
Codex upstream and OS research, a Claude Mixxx UI/CDJ review, and live playback
tests. **Unconfirmed** marks anything not measured. The walkthrough version
with mock-ups is the artifact
[Mix Pi Performance Plan](https://claude.ai/artifact/BxEN6L5tA7rFMSX7BTusDV)
(private to the owner).

## Performance trial accepted (2026-11-09)

The arm64 package at `ccbf91b` compiled successfully and runs extracted on the
Pi with a separate profile. The user confirmed stable selected tabs and working
Browse → Actions, then passed the master/headphone/controller/loops/FX smoke
test and reported noticeably better performance. Both internal-export tracks
loaded into RAM; V3D renders the waveforms. Audio remains at 44.1 kHz / 1024
frames. Post-test: 48.2°C, no throttle flags, no swap use. This is subjective
playback acceptance plus startup evidence, not a controlled performance
benchmark or endurance test. Original installation and profile remain intact.

The package workflow also passed at image-isolation commit `249da45`. A full
image build is the next packaging validation. Native Sources/full target UI,
eject interlock, appliance stripping and the same-card preservation gate remain.
See [same-card checkpoint](../setup/SAME-CARD-UPGRADE.md).

## Recovery status (2026-11-08)

The failed conversation was recovered into the main workspace. The two original
worktrees remain intact. No push, ARM build or Pi deployment was performed.

- Recovered GPU image hook, supervised maintenance pause/restore, and Pioneered
  Beat FX/track-number fixes.
- Recovered experimental read-ahead and removable-track RAM-cache patches plus
  the shared image/package recipe and manually dispatched arm64 package workflow.
- Host validation: 146 tests ran, 119 passed, 27 explicitly skipped (native
  GTK/PipeWire/Linux checks and optional pinned skin fixture). The full patch
  stack applied to pinned Mixxx 2.5.6. This is not a C++ compilation/runtime test.
- Interactive proposal: [`pioneer-prototype`](../../tools/pioneer-prototype/index.html).
  Local simulated controls only; it is not an installed Mixxx skin. The revised preview follows
  Claude’s original HTML and actual Pi captures: 36 px Waybar, top tabs, two
  stacked RGB waveforms, blue deck title strips, white tempo boxes, overview
  strips and 48 px deck buttons. Settings replace only the waveform area;
  Browse uses the compact deck layout. It has one media LOAD/EJECT pair, source
  selection, three FX slots with exclusive routing and buffer confirmation.
  Per-deck LOOP panels offer 1/32–64 beat intervals, half/double, exit and reloop.
  Key labels use Camelot(musical key). Browse keeps the full-width table by
  default. Its right-hand source pane extends from the search toolbar through
  the right deck title strip, with full-row folder/playlist navigation and Back.
  The Show/Hide control stays fixed; source visibility/default preferences remain
  available at the root.
  See its [reference and validation notes](../../tools/pioneer-prototype/README.md).
- **Correction to the earlier eject promise:** the recovered RAM cache falls
  back to original media on copy/decoder failure. There is no integrated eject
  guard yet. Do not treat the cache patch or the demo's RAM-ready label as proof
  that a real USB can be removed. Eject must refuse while any player/analyzer
  still depends on the device or a copy/load is pending. Cached-file leases,
  fallback behavior, hotplug races and decoder lifetime require runtime tests.
- Read-ahead is currently a bounded startup environment setting (2–24 chunks,
  default 8); the touch selector is only proposed. Source filtering and the
  full tab/settings layout are also prototype behavior, not Mixxx features yet.

Next: review the proposed touch layout; compile the ARM package; exercise
cache success/failure and safe eject with removable media; test supervised
startup/exit and speaker handoff on the Pi. Keep the current live audio setup
until these checks pass.

## Continuation branch (2026-11-08)

Current branch: `feat/pi-performance-target`. The accepted HTML interaction work
is recorded in `tools/pioneer-prototype/`; the prototype does not modify the Pi.
The final continuation request ended at “with the”, and no separate document
named “climb to target” was located. The remaining work in this recovered plan is:

1. Translate the accepted view into the pinned native Pioneered/Mixxx skin:
   stable tabs, shared media controls, FX routing, settings, touch loop controls,
   paired Camelot/musical keys, and the right-hand source navigation.
2. Add native library source filtering/default persistence and folder navigation;
   the current HTML source settings are simulated.
3. Complete media-use accounting and an eject interlock that covers cache
   failure, pending loads, analyzers and device removal. Then integrate skin
   status lights and hold-to-eject. The cache alone does not make eject safe.
4. Compile the recovered patches using the arm64 package workflow; host patch
   application checks do not establish C++ compilation or playback behavior.
5. Validate on the Pi: GPU startup, maintenance restoration including crashes,
   Speaker handoff, FX routing, USB playback and failure cases, then buffer soak.
6. Finish the appliance-image work in section B. Keep listening-dependent
   keylock choices and the later greetd/upstream trials as separate decisions.

## Live test results (2026-11-08)

The user clarified that the problem is lag and audio cutting out **during
playback** from the SD card or USB, not during copying. Two decks played from
the SD card (`busstop.flac`, `Let It Happen (Soulwax Remix).mp3`) on the
Overview tab, 45 s per run, with the Starlight PCM muted. Evidence and scripts:
`deploy/gpu-test-20261108/` (git-ignored).

| Setup | Mixxx CPU (% of one core) | GUI thread | Audio thread | Whole Pi | Max °C |
| --- | --- | --- | --- | --- | --- |
| llvmpipe (before) | 120.4 | 41.5 | 12.8 | 34.5 | 67.2 |
| V3D (**installed live**) | 36.2 | 18.2 | 11.9 | 12.0 | 64.3 |
| + SoundTouch (tested, reverted) | 28.7 | 17.4 | 5.9 | 10.2 | 60.9 |
| + 30 fps (tested, reverted) | 22.9 | 12.4 | 5.8 | 7.9 | 60.9 |

- **GPU fix live:** `/etc/X11/Xsession.d/80mixpi-gpu-render-node` exports
  `WLR_RENDER_DRM_DEVICE=/dev/dri/renderD128`. After `systemctl restart
  lightdm`, Mixxx logs `renderer "V3D 4.2.14.0"`. Screen, touch, Waybar and
  waveforms look normal, and the Xwayland "no render node" error is gone.
  Sway uses 7–8 % CPU during playback. **Not in the image yet.**
- **No dropouts reproduced from SD.** The worst ALSA buffer fill was 1,065 of
  2,048 frames. With a 600 MB SD write the iowait rose to 14–20 %, still with
  no underflow. Mixxx `--developer` counters showed **zero cache misses**, even
  with the page cache dropped, 1.2 GB written and 12 files read at once
  (iowait 43 %).
- **Read-ahead is only 0.37 s** (`readaheadmanager.cpp:229`: 2 × 8192
  frames). A storage pause longer than that plays silence while ALSA stays
  healthy. USB playback is the main untested suspect: the stick was not
  plugged in.
- **Worst audio callback:** 35–43 ms against a 46 ms buffer (2 × 1024 frames),
  with an average of 1.2 ms. It also occurred with the decks idle, so it is
  probably a start-up one-off (**Unconfirmed**).
- **Audio thread** runs SCHED_FIFO priority 1; the SD card IRQ thread runs at 50.
- **Pioneered tabs toggle:** tapping the active tab switches to another tab.
- **The "61 s library scan" was not a scan.** It is the scanner thread's
  lifetime, idle for the whole session.
- **Side effect:** about ten Mixxx restarts rotated out every Mixxx log older
  than this session (2026-10-14 to 11-06). The test logs are in
  `~/.local/state/mixpi-backups/gpu-test-20261108-131033/test-logs/` on the Pi.

## What the Pi is doing now

- **Pi 4B 4 GB** (3.8 GiB usable), Trixie, kernel 6.18.50 (already fully
  preemptible), performance governor at 1.5 GHz, **68 °C at idle**, `throttled=0x0`.
- **RAM is not the bottleneck.** Mixxx RSS is about 500 MB, MemAvailable about
  3.0 GiB, and the 2 GiB zram swap is unused. No knob gives Mixxx "more RAM";
  Linux already lets it use the free memory.
- **Mixxx renders in software.** The log reports `renderer "llvmpipe"`, and
  Mixxx runs four `llvmpipe-N` threads. Sway advertises `card1` (vc4,
  display-only) as its main dmabuf device, so every Wayland client finds no
  render node. Xwayland logs "Main linux-dmabuf device has no render node".
  An EGL probe gets `V3D 4.2.14.0` through the surfaceless platform. A
  headless Sway with `WLR_RENDER_DRM_DEVICE=/dev/dri/renderD128` gives clients
  V3D. Raspberry Pi's wlroots patch (rpt4 and rpt5) advertises the display
  device deliberately, to keep direct scanout. Forcing the render node may add
  a buffer copy (**Unconfirmed** cost).
- **The library depends on the USB stick.** Of 202 tracks, 150 point at
  `/media/pi/MANTACORE` (the only watched folder), 51 at the `MixPi-MANTACORE-*`
  copies on the SD card, and 1 at `~/Music`.
- **Costly Mixxx settings:** keylock on both decks with RubberBand R2
  (`keylock_engine 1`). Waveform type 17 (all-shader RGB) at the default 60 fps.
  16 samplers, each with a reader thread. All external library sidebars enabled.
- **Upstream freezes:** Mixxx still does file checks and metadata writes on the
  GUI thread ([#17213](https://github.com/mixxxdj/mixxx/issues/17213)). The fixes
  (#17202, #17208–#17210, #17088 WAL) are open PRs, so upgrading does not cure
  them yet.
- **SD writeback:** `dirty_ratio 20` / `dirty_background_ratio 10` lets about
  660 MB of unwritten data build up while copying. A SQLite commit on Mixxx's
  GUI thread then waits behind it. The USB copier (`mixpi-media:366`) writes
  unpaced.

## Second round (2026-11-08)

| Topic | Decision or result |
| --- | --- |
| Audio buffer | 23 / 11.6 / 5.8 ms: 0 underruns each, two decks plus SD write, 75 s. Audio thread 12.8 / 14.9 / 19.1 %. Next: a 30-minute soak at 11.6 ms, then make it the default. Put it in the ⚙ panel behind a confirm, because audio restarts |
| Power | The Pi is fed from a hub port, and the hub carries no data (only the Pi's internal VIA hub enumerates). Recommend the official 5.1 V 3 A supply straight into the Pi |
| Read-ahead | Agreed. Built as `MIXPI_READAHEAD_CHUNKS` to find the limit. The ceiling is 80 cached chunks (about 15 s) per player |
| Keep playing after eject | Patch: copy tracks from `/media/…` to `/dev/shm` on load and play the copy, as a CDJ does. Eject then waits only while a stick track is still loading or being analysed |
| Media LOAD/EJECT | One per view, not per deck. LOAD opens the stick's Rekordbox library; EJECT is press-and-hold |
| Library | Rekordbox source by default. The Sources menu sets which sources show, the default, and a view limited to one, several or all |
| In-Mixxx media slot | Phase 2: `[MediaSlotN]` controls for skin lights, true hold-to-eject, controller mapping and an exact in-use check. About 400–600 lines of C++ |
| Waveforms | Keep the detailed RGB waveforms at 60 fps |
| Agreed | Maintenance pause; ⚙ panel; FX tab with the Beat FX fixes; Trixie stripped; greetd later |

## Likely causes of lag and audio cut-outs during playback, ranked

Revised after the live tests:

1. **Software GL (fixed live).** The GUI and four llvmpipe threads used about
   1.1 cores. This is the screen and controller lag.
2. **USB stick reads longer than the 0.37 s read-ahead.** That deck plays
   silence. The stick shares the USB 2 hub with the Starlight, and the gig hub
   was unpowered. Next test: the same run from MANTACORE under `--developer`,
   then fixes (blue USB 3 port, powered hub, read-ahead 2 → 8 chunks, copy to SD).
3. **Tracks that fail to decode.** Earlier logs listed MANTACORE's Jealousy,
   TAMALE, Morning Dew (Donk) and Lady. All 19 `.mp3` files on the SD card are
   real MP3 (ffprobe).
4. **A 35–43 ms worst audio callback** against 46 ms of buffer, probably at
   start-up (**Unconfirmed**).
5. **Ruled out:** SD read stalls (zero cache misses under heavy load) and RAM.

## Paths

### A. Tune what we have (config only, reversible, no rebuild)

| Step | Change | Check |
| --- | --- | --- |
| A1 GPU | `WLR_RENDER_DRM_DEVICE=/dev/dri/renderD128` in the Sway session environment. **Done live 2026-11-08; add to the image.** | V3D renderer confirmed; Mixxx 120 % → 36 %. Speaker mode not re-checked after the change |
| A2 Keylock | `[App],keylock_engine 0` (SoundTouch) only if it doesn't sound worse. **2026-11-08:** user wants a listening test on two sets of songs at the high and low ends of the range | Blind [Key Lock Ear Test](https://claude.ai/artifact/FjGjPQxjZtVzmBuHBK6bTY): 4 tracks × −8/+8 %, rendered with the Pi's RubberBand 3.3.0 R2 real-time and SoundTouch 2.4.0 quick-seek, level-matched within pairs. Tooling: `deploy/keylock-ear-test-20261108/` |
| A3 Waveforms | **Decided 2026-11-08: keep 60 fps.** No change | — |
| A4 Sidebar | **Decided 2026-11-08:** a touch **Sources** menu with multi-select, like the column menu. It is a Mixxx patch: the new control `[Library],show_sidebar_sources_menu` opens checkable entries for every top-level sidebar feature. Unticking hides the row live (`QTreeView::setRowHidden`) and saves the choice. For the five external libraries it also writes `Show…Library 0` so they are not built at start-up (`library.cpp:175-206`). The same list goes on the touch settings page. Drag re-ordering comes next | Hide and show live, no restart; the choice survives restart |
| A5 SD writes | **On hold 2026-11-08.** The USB copier stays at full speed; it never runs during a set. The dirty-bytes cap only matters for mid-set writes (analysis saves on first load, WAV recording at about 10 MB/min, play counts). 1.2 GB written during playback had no effect | Revisit if recording mid-set causes hiccups |
| A6 Set hygiene | Pause the apt-daily, apt-daily-upgrade, man-db, dpkg-db-backup, logrotate, fstrim, e2scrub_all, rpi-zram-writeback and tmpfiles-clean timers during sets | Restore them afterwards |
| A7 Cooling | Fit the fans in [`COOLING-PLAN.md`](COOLING-PLAN.md) (see also `HARDWARE.md`) | Stays under 75 °C over 30 minutes of two-deck play |
| A8 Prep | Analyse tracks before a set; repair the M4A-as-MP3 files | No analysis during play |

### B. Appliance image (rebuild)

- Build Mixxx in a throwaway stage or root and install only its `.deb`. Today
  `01-run.sh:33` installs straight into the image, `/usr/bin/mixxx` has no dpkg
  owner, and the toolchain, 359 MiB of `*-dev` packages and the Qt5 dev
  leftovers ship in the image.
- Remove Firefox (283 MiB), Syncthing, ModemManager, qpwgraph and
  `xserver-xorg`. Replace Nautilus where `mixpi-media:1074` opens folders.
  Later, replace LightDM with greetd.
- Add a `mixpi-performance.target`. While Mixxx is in front, it stops blueman
  (about 100 MB), nm-applet, swaync, gvfs, the portals, foot-server, at-spi and
  the maintenance timers. It restores them for Speaker mode and the desktop.
  Keep avahi (`mixxxpi.local`, Spotify zeroconf), udisks2/udiskie, Bluetooth and
  NetworkManager.
- Fix: drop the ignored `preempt=full` (`03-kernel-setup/00-run.sh:3`). Fix the
  portal backend masking (`02-desktop/02-run.sh:9`) and the recursive 755
  chmod (`02-desktop/02-run.sh:19`, `04-enable-wayland/02-run.sh:6`). Trial
  `threadirqs` with the xHCI IRQ thread at FIFO 70 (**Unconfirmed** benefit).

### C. Own the Pioneer view (skin)

The Pioneered skin ignores the `[Skin] show_*` keys. Its real costs are the
two scrolling waveforms and keylock. Replace the runtime patch with a
repo-owned skin:

```
[PERFORM][BROWSE][FX]            REC○  CPU▮▮▯  ⚙
D1 scrolling waveform (simple, 30 fps)
D2 scrolling waveform
DECK1 Title – Artist           │DECK2 Title – Artist
-03:12 124.0 ±8 +1.2% Am       │-01:05 126.0 ±8 0.0% 8A
overview + cues                │overview + cues
[KEY][Q][SYNC] [LOAD][EJECT]   │[KEY][Q][SYNC] [LOAD][EJECT]
```

- **LOAD/EJECT per deck.** `LoadSelectedTrack` and `eject` already exist.
  Load lock (`LoadWhenDeckPlaying 0`) and instant doubles are already on.
  Eject refuses while playing, but a second tap within 500 ms reloads the
  previous track, so the button needs a guard.
- **CPU lamp** from `[App],audio_latency_usage` and `audio_latency_overload`.
  A REC button. Beat FX moves to an FX tab. Samplers drop to 4 or 8.
- **⚙ PERF panel** for live controls: keylock, keylock engine, quantize,
  sync, tempo range, split cue, recording. A GTK "Performance settings" page
  handles restart-only items (waveform type, audio buffer, load lock,
  controller) and applies only while no track is loaded.
- **Skin bugs:**
  - `effect.xml:49` is missing `[` in the master-enable key, so Beat FX
    probably reaches Deck 1 only.
  - `effect.xml:52-55` sets the meta knob on toggle.
  - `deck.xml:103` uses `track_number`; it should be `trackNumber`.
  - `sampler.xml:21-24` needs a right-click to stop or cue a sample.
  - The Q/keylock buttons are 30 px, under the 48 px target.

### D. CDJ-style media slots

CDJ-3000 manual: SOURCE lists the devices. USB STOP is held until the
indicator stops blinking. The SD card is released after its indicator stops.
LOAD LOCK blocks loading onto a playing deck.

- **Recommended: a Waybar media chip per inserted USB or SD card** in place of
  the static USB ⇄ Pi button.
  - The script waits on mountinfo change events, so it doesn't poll.
  - Tap opens Copy to Pi or Eject.
  - Eject is tap-to-arm then tap-to-confirm, standing in for hold-to-eject.
  - Eject is refused, naming the track, while Mixxx has a file open under the
    mount. This needs a mount-prefix match; `files_in_use` at
    `mixpi-media:430` checks only one folder level.
  - Otherwise it runs `udisksctl unmount` and then `power-off`.
  - States: READY → ARMED → EJECTING → REMOVE.
- **Later:** an in-Mixxx `[MediaSlotN]` ControlObject patch (about 400–600
  lines of C++) for in-skin lights.
- **Library model to decide:** either treat sticks as Rekordbox sources, as a
  CDJ does, or copy to the Pi before the set. Today, ejecting MANTACORE hides
  150 library tracks.

### E. Upstream Mixxx

- **Stay on 2.5.6**, which is the latest stable release; 2.5.7 is unreleased.
  2.6 is still in beta since May 2025, and `main` is 2.7 with experimental QML
  that isn't touch-ready.
- Cherry-pick candidates: `.PIONEER` support
  [#16895](https://github.com/mixxxdj/mixxx/pull/16895), analysis shutdown
  #16064, and the Starlight superknob
  [#14126](https://github.com/mixxxdj/mixxx/pull/14126).
- Trial 2.6 on a spare card later: GLES build (`-DQGLES2=ON`, with fixes
  #15797 and #17280) and RubberBand R3 short-window. Both local patches would
  need a rebase.
- Neither skin repo has commits beyond our pins (Pioneered last changed
  2024-11-21).

## Recommended order

1. A1 live GPU test, with measured before/after CPU during two-deck playback.
2. A2–A8.
3. C and D together on a branch.
4. B in the next image.
5. E trial later, on a spare card.
