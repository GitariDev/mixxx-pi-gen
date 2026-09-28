# First-gig feedback and action plan

Logged and inspected: **2026-09-22**. After the initial planning pass, the user
authorized implementation/testing and a build for a replacement **62 GB card**.
The first EthioJazz set was enjoyable. Its exact date was not supplied.

## Implementation and test status

The user subsequently connected the Starlight and MANTACORE USB and confirmed
the Pi still uses the **same hub arrangement as the gig**. The approved build
branch contains commits `22aa918` and `bb47200`:

| Item | Delivered or observed | Remaining acceptance work |
| --- | --- | --- |
| Power baseline | Starlight audio configured for master 1–2 and headphones 3–4, 44.1 kHz; saved MIDI mapping opens after restart. User confirmed the brief playing/controller test worked, then requested stop. About three minutes of telemetry stayed at `throttled=0x0`; peak 76.4 °C during concurrent backup. | Complete 30-minute test and two-drive insertion; compare dedicated supply and extender. Clear voltage flags alone do not prove reliable power. |
| Larger touch UI | Live Pi has 17 px library text, 34 px rows, larger menu targets, 26 px scrollbars in Browse, and a 96×40 Actions button. Screenshots confirm fit at 800×444; user confirmed the hands-on check worked. Layout and Starlight settings survived application restart, and horizontal paging revealed right-side columns. New images seed defaults without overriding existing preferences. | Detailed finger dragging, long-menu reachability and full-system reboot checks. |
| Touch context menu | Select a track → **Actions** opens its context menu; verified on the live Wayland session. | General long-press/right-click behavior for headers and sidebar remains open. |
| Column filtering | Requested on 2026-09-23: be able to filter columns in the Pioneered folder/browser view. Requirement recorded; not implemented. | Define visible-column selection versus filtering tracks by column values, then provide touch-accessible controls. |
| Removable media | Version-pinned Mixxx patch probes compatible Rekordbox exports every two seconds and updates individual device nodes without changing the active view. Parser/SQL tests, ARM64 build and image assembly pass. Live alias add/remove and idle MANTACORE unmount/remount appeared automatically within the 5–6 second checks while SD-Backup stayed selected. | Physical unplug/reinsert, two-USB playback handover and new-card acceptance. Opening a device imports metadata; plain-audio auto-indexing and safe-eject UI are not implemented. |
| Controller | Existing Starlight mapping is enabled and MIDI ports open after restarting Mixxx with it connected. | General live MIDI discovery/mapping is deferred; upstream enumeration is startup-oriented. |
| Transfer | **USB → Pi** in the top bar or Settings copies a complete compatible export or ordinary folders to internal storage, verifies SHA-256, preserves USB files, and prevents overwrite. Fixture copy/repeat/cancel checks pass. On the new card, all 613 files / 2.073 GB match receipt and USB hashes; 77 internal audio paths exist in Mixxx and logs show internal-copy loading. | Test internal-copy loading after physically removing USB. Browser uploads and individual-playlist selection remain planned. |

The user accepted copying playlists/music from the plugged-in flash drive as
the first transfer workflow. A Rekordbox export is copied with both `PIONEER`
and `Contents` so its playlists and referenced audio stay together. The real
USB export contains **613 files / 2,072,726,997 bytes**; the approximately 15 GB
whole drive tree includes unrelated OS folders and trash and is not the copy
scope.

**2026-09-23 follow-up:** the user reports booting the newly flashed card and
successfully testing the UI changes and Copy to Pi. Public-key access was
completed through the Pi terminal. Inspection confirms the correct build,
expanded 62 GB card (45.6 GiB available), touch defaults and a fully verified
613-file internal export. Database checks pass with no missing track paths.
Remaining migration: enable Starlight MIDI mapping, assign headphone cue
channels, and restore the older music (39 audio files are absent from the
new export). Preserve the user's new library/settings during that work.
Evidence: `deploy/new-install-20260923/RESULTS.md`.

The Mac-attached replacement card was identified as an external USB SD Drive,
**62,226,694,144 bytes** (then `disk8`). This is distinct from the Pi's MANTACORE
music USB and current 14.8 GiB boot card. Reidentify the target immediately
before flashing. Keep the current card as rollback and preserve its library,
settings and `/media/SD-Backup` before migration. See the
[build and migration runbook](../setup/TOUCHSCREEN-BUILD.md).

The detailed requirements below retain the original plan; this status table
distinguishes implemented milestones from the full acceptance criteria.

## Feedback to retain

| Area | Observation or request |
| --- | --- |
| Power | Powered USB hub used without its separate supply connected; adding peripherals caused cutouts and the Starlight did not fully power up. Improve the supply and make USB-C unplugging accessible at the case, rather than requiring disconnection at the source. Exact wiring is unconfirmed. |
| Audio | Starlight audio output worked better. Internal Pi audio could be much louder; gain/routing differences have not been measured. |
| USB extension | USB 3 extender was unreliable. Excess power draw/impedance is a suspected explanation; distinguish voltage drop, connector problems and signal integrity in testing. |
| Removable music | Automatically add/discover and scan connected media, including simultaneous devices and DJs swapping drives. |
| Touch browsing | Slightly larger library and menu items in Pioneered, plus a horizontal scrollbar specifically in the Pioneered **Browse** page. |
| Context menus | Access right-click menus using the capacitive touchscreen without a mouse. |
| File transfer | Initially plan a simple preparation-computer web app. Later request accepts copying playlists/music from an attached flash drive as the first implemented workflow. |
| MIDI — stretch | Detect connected controllers and select the correct Mixxx mapping automatically where possible. |
| Stems — long term | Permanently install stems tooling on the Pi. Exact software and CDJ/USB format are not yet identified; playback and stem generation need separate evaluation. |

## Initial baseline — before the live changes

The initial read-only SSH inspection of `pi@mixxxpi.local` found:

- Raspberry Pi 4 Model B **Rev 1.1**, Debian 13.7/Trixie, SD boot/root storage.
- Mixxx **2.5.6**, commit `3ebac449e7e5fe2a0186596657696e87ce8b0e56`;
  Pioneered commit `b1b61860d0ee06e4460df599b1d39619fbc1db1e`.
- Sway **1.10.1**, native Wayland Mixxx (`xdg_shell`), 800×480 at scale 1.
  The top bar leaves an **800×444** Mixxx window. Touch input is
  `0:0:10-0038_generic_ft5x06_(00)`.
- Both **devmon and udiskie 2.5.7** were running. Automount tooling already
  exists; mounting a filesystem and refreshing Mixxx are separate operations.
- Saved configuration selects Pioneered, enables the Rekordbox source and has
  `RescanOnStartup 0`. The Starlight mapping is saved and enabled. Saved settings
  may lag unsaved runtime changes; reconnect behavior has not been tested.
- `/media/SD-Backup` contains `PIONEER` and `Contents`;
  `~/Music/Backup` and `~/Music/Rekordbox` exist. About **5.8 GiB** is free on root.
- The original Pioneered `style.qss:252` set the library horizontal scrollbar's
  height and width to **0**; its vertical scrollbar was **4 px** wide. The
  previous menu/checkbox contrast fix is present.
- At inspection: `throttled=0x0`, temperature **54.5 °C**, no matching
  current-boot kernel undervoltage/overcurrent/USB-reset messages. No music USB
  or Starlight was attached. This does **not** establish power reliability with
  the gig's full load or rule out failures during earlier boots.

## Order of work

| Order | Item | Deliverable | Main dependency |
| --- | --- | --- | --- |
| 0 | Power baseline | Stable full-rig power and accessible case connection | Inspect hub, supply, cables and actual wiring |
| 1 | GIG-02: larger touch UI | Pioneered Browse rows/menus and usable horizontal scrollbar | Skin override and physical touch review |
| 2 | GIG-03: context menus | Touch-accessible track actions, then remaining right-click menus | Reuse the same skin work; validate native Wayland touch |
| 3 | GIG-01: removable media | Automatic device discovery/refresh and tested two-DJ handover | Stable power; prove Mixxx integration before building a watcher |
| 4 | GIG-04: transfer app | Small authenticated upload page with clear completion status | Destination and media-refresh behavior established |
| Later | MIDI / stems | Separate feasibility prototypes | Hardware/mapping and software/format identification |

### Power baseline

Start with a dedicated Pi supply and an independently powered peripheral hub.
Raspberry Pi recommends a 3 A USB-C supply for Pi 4; its USB ports share a
1.2 A peripheral budget. Cable voltage loss matters at the Pi end.
[Official power guidance](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#power-supply),
[cable-loss guidance](https://www.raspberrypi.com/documentation/computers/getting-started.html#power-supply).

1. Record the hub/supply models and draw the actual connections. Establish
   whether the current arrangement uses a hub charging port, power pass-through,
   or back-powering; the notes alone do not establish which.
2. Prefer positioning the Pi's USB-C socket at an accessible case opening. If
   an internal extension/panel connector is essential, use the shortest suitable
   assembly and validate the complete path under load. Confirm supply/cable
   compatibility with this Rev 1.1 board before choosing parts.
3. Compare direct USB connections against the extender, changing one component
   at a time. Test the Starlight, display, cooling and two music drives together.
4. Run at least 30 minutes of two-deck playback while inserting another drive.
   Pass only with no cutouts, controller resets, audio dropouts or new power
   warnings. Keep Starlight master/cue routing as the performance baseline and
   compare levels at matched settings. Shut down before unplugging power.

### GIG-01 — automatic removable-media discovery and scanning

**Outcome:** insert a drive and see a named source without restarting Mixxx or
manually finding its mount path. Two drives remain independently usable during
a handover. Discovery/metadata indexing happens automatically; expensive
BPM/key/waveform analysis is queued separately so it does not stall playback.

Mixxx 2.5 documents opening the Rekordbox source or using its refresh link to
discover exports. General library rescanning and rescan-on-startup do not by
themselves provide insertion-triggered scanning. Rescans can mark absent files
missing, so adding every guest drive as a permanent watched directory is a
poor default. [Mixxx library manual](https://manual.mixxx.org/2.5/en/chapters/library).

1. **Prove the mount path.** With actual drives, observe mount/unmount events
   and permissions. Consolidate mounting under udiskie/UDisks after checking
   why both automounters are active; two running processes alone do not prove
   a conflict. Use filesystem UUID plus partition identity, with the volume
   label for display. Handle duplicate labels and exclude boot/root storage.
2. **Prove the Mixxx entry point.** Investigate the pinned Rekordbox device
   discovery code and native library scanner. A udiskie mount event can notify
   a helper, but a helper cannot be assumed to have a supported command that
   refreshes Mixxx. First demonstrate an existing callable integration; if none
   meets the requirement, implement a small version-pinned Mixxx change using
   mount notifications and its own library APIs. Avoid focus-dependent clicks
   or direct writes to the running Mixxx database.
3. **Handle both media types.** Recognize compatible Rekordbox exports through
   `PIONEER/rekordbox/export.pdb` and preserve playlists/cues/grids. Give ordinary
   audio folders a named browsable source with automatic metadata indexing.
   Do not bulk-copy guest music to SD or permanently add guest roots by default.
   Normal Mixxx caching/import of played tracks may still retain track metadata.
   Keep the existing SD backup as a separate source.
4. **Manage device changes.** Debounce repeated events; wait for a completed
   mount; serialize indexing; show preparing/ready/error status. Refresh one
   device without clearing another's view or changing the playing decks.
   Cancel pending work when a drive disappears; retain cached cues for reuse.
5. **Provide safe removal.** Before offering eject, check loaded decks,
   preview/samplers, queued work and file handles. Explain when tracks must be
   unloaded first. A forced unplug must produce a clear unavailable state;
   playback of an affected track cannot be guaranteed.

**Pass checks:** two drives present together; insert B while playing from A;
eject/unload A while playing from B; reinsert A; swap in C; repeat with plain
audio and compatible Rekordbox exports. Include duplicate labels, spaces and
Unicode, read-only media, failed mounts, removal during indexing, and restart
with drives attached. Verify playlists/cues and SD backup access survive, no
bulk duplicates appear, and unaffected playback remains clean. Log detection
and scan times against a documented track count before setting speed targets.

Relevant code: [pinned Rekordbox discovery](https://github.com/mixxxdj/mixxx/blob/2.5.6/src/library/rekordbox/rekordboxfeature.cpp),
[pinned library integration](https://github.com/mixxxdj/mixxx/blob/2.5.6/src/library/library.cpp),
[udiskie](https://github.com/coldfix/udiskie).

### GIG-02 — larger Pioneered library/menu targets and horizontal scrolling

**Outcome:** easier selection and menu use at the current screen resolution,
with a finger-draggable horizontal scrollbar in Pioneered's **Browse tab**.
This refers to the skin's Browse page, including its library/Rekordbox tables,
not only Mixxx's filesystem-browsing source.

1. Start with a reversible user-skin copy. Use Mixxx's library font/row-height
   settings where available, then scoped QSS/XML changes. Initial trial sizes:
   **16–18 px text, 32–36 px rows, 36–40 px menu targets**. These are tuning
   proposals, not verified fit. Keep display scale 1 to preserve usable space.
2. Replace the zero-sized horizontal scrollbar rule in the Browse library
   wrapper. Trial a **24–28 px** track with a contrasting, easily grabbed thumb;
   remove the width-zero constraint. Show it when columns overflow and verify
   the underlying Qt scrollbar policy if styling alone is insufficient.
   Increase the 4 px vertical handle to a usable touch width as part of testing.
3. Size column headers, sidebar items, popup entries and embedded column-menu
   checkboxes together. Preserve the existing readable checked/disabled states.
   Mixxx library font/row preferences may apply across library sources; keep
   deck sizing and the horizontal scrollbar change scoped to the intended view.
4. Preserve useful track rows, the search field, Show/Hide and deck summaries
   within 800×444. Package the final override alongside the existing
   `stage3/01-install-packages/files/pioneered-menus.qss` build customization.

**Pass checks:** select adjacent rows accurately; drag horizontally to the last
column and back; open long menus and reach their last entry; test Show/Hide,
Rekordbox playlists, ordinary files, Overview/Sampler and the touch keyboard.
No clipped required controls, accidental track loads, or lost scroll position.
Verify persistence after restart. Review actual screenshots and finger use.

The pinned code already supports horizontal pixel scrolling and explicit row
height, so a skin/settings change is the first implementation candidate.
[Library table source](https://github.com/mixxxdj/mixxx/blob/2.5.6/src/widget/wlibrarytableview.cpp),
[Pioneered revision](https://github.com/timewasternl/Pioneered/tree/b1b61860d0ee06e4460df599b1d39619fbc1db1e).

#### Follow-up requirement — column filtering in the folder/browser view

**Requested 2026-09-23:** “I'd like to be able to filter the columns in the
Pioneered folder.” Record this as a new requirement, not part of the already
delivered scrollbar or track Actions work.

Provide touch-accessible column filtering in Pioneered's folder/Browse view.
Before implementation, resolve whether the desired interaction is choosing
which columns are visible, filtering tracks by values in individual columns
(for example artist, BPM or key), or both. Proposed acceptance checks: usable
without a mouse, clear active selections, an easy reset, and sensible
persistence when changing folders or restarting Mixxx.

### GIG-03 — context menus without a mouse

**Outcome:** select a track, open its actions and dismiss the menu using touch;
also reach column-header and sidebar menus where they offer needed actions.

1. Add a clearly labelled **Actions** button to the Pioneered Browse page,
   wired to Mixxx's existing `[Library],show_track_menu` control. This opens the
   menu for the selected track(s) and provides a straightforward first step.
   It does not automatically cover sidebar or column-header menus.
   [Mixxx controls](https://manual.mixxx.org/2.5/en/chapters/appendix/mixxx_controls#library-show-track-menu).
2. Test existing press-and-hold and keyboard context-menu behavior on the
   actual native Wayland session. Do not assume X11 right-click utilities or
   touchpad tap settings solve touchscreen behavior.
3. For remaining menus, prototype a **600–800 ms hold** with movement
   cancellation, preferably inside the relevant Mixxx widgets. Cancel on
   dragging/scrolling, a second finger or leaving the target, and suppress any
   resulting extra click/double-click. If reliable hold recognition needs a
   core patch, explicit touch buttons for the remaining menus are the fallback.

**Pass checks:** track actions, column selector and sidebar menus work without
a mouse; the intended row/item receives the action; a normal tap still selects;
scrolling never opens a menu; holding never loads a track or moves a deck
control. Menus remain on-screen and can be dismissed by touch. Verify existing
mouse behavior and persistence after reboot. An Actions button alone passes
the track-menu milestone, not the complete right-click requirement.

### GIG-04 — simple file-transfer web app (planned)

**Proposed first version:** open a local browser page on the Mac, choose/drop
files or a folder, select **Music backup** or **Rekordbox export**, and press
**Transfer**. Show Pi connection, available space, per-file progress, completion
and retryable errors. Use a small Mac-side service and the existing SSH/SFTP
connection; the SSH key stays with that service, never in browser JavaScript.
Bind the web service to loopback and protect write requests against cross-site
requests. A Pi-hosted LAN upload page can follow if access from other people's
computers/phones becomes a requirement.

- Plain audio goes into a new named folder under `~/Music/Backup`.
- A complete Rekordbox export preserves both `PIONEER` and `Contents` and all
  relative paths. Upload into staging outside Mixxx's discovery roots; verify
  completeness before publishing to a separate named directory under `/media`.
  Preserve `/media/SD-Backup` unless replacement is explicitly selected.
- Keep paths within approved destinations, reject traversal/symlink escapes,
  stream large files, check free space with reserve, and never silently replace
  existing files. Interrupted transfers remain visibly incomplete and retryable.
- Separate **Transferred** from **Available in Mixxx**. Invoke the verified
  GIG-01 refresh path when it exists; otherwise give the tested manual refresh
  instruction. Initial scope excludes deleting music and editing Mixxx's DB.

**Pass checks:** transfer an audio folder and a small complete export; verify
file sizes/checksums and load transferred tracks in Mixxx. Test duplicate names,
Unicode, low disk space and a dropped network connection without damaging
existing music. A partial export must never appear as ready.

## Later work

- **Automatic MIDI mapping:** the Starlight mapping is already saved/enabled.
  First test reconnecting it while Mixxx runs and after reboot. Then evaluate
  exact device-identity matching for known mappings and explicit selection for
  ambiguous/unknown devices. Preserve manual choices and treat audio-device
  routing separately. The later connected-device test opened the saved
  Starlight mapping after restarting Mixxx; generic MIDI hotplug is deferred.
- **Stems:** identify the named software/file format and desired workflow first.
  Evaluate prepared-stem playback separately from on-Pi separation, including
  installed Mixxx compatibility, ARM64 dependencies, controls, storage and
  sustained performance. Permanent local installation is the goal; neither
  CDJ compatibility nor real-time separation on this Pi is established.

## Delivery and rollback

Before implementation, back up the skin/config and take a consistent Mixxx
database backup while the application is stopped. Develop and test one item
at a time; retain the current skin and original card as recovery options.
Do not overwrite active configuration or change source versions implicitly.
Put any accepted changes in the image builder as well as the live test rig,
with pinned patches where core changes are needed. Complete the touch and
two-drive checks, then repeat the full-rig 30-minute playback test before the
next gig. The initial inspection changed documentation only; the later live
test installed the touch/helper changes with backups under
`~/.local/state/mixpi-backups/2026-09-22/`. The new Mixxx package is also
installed and its silent media checks passed on the existing Pi. The
replacement image is downloaded, written to the 62 GB card and verified by
Imager's full read-back check. The user has completed the physical swap and
reports successful UI/copy tests. SSH provisioning and independent new-card
inspection are complete; selective restoration of controller/cue settings and
older music remains. Preserve the current library during that work. Keep
full-rig acceptance distinct from these completed tests.
