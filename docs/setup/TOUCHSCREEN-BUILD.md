# Pi 4 touchscreen build and test

Branch: `codex/pi-touch-bluetooth-build`. Keep the original boot card as rollback.

**2026-09-23 status:** commits `22aa918` and `bb47200` add the post-gig touch
changes, removable-export discovery, USB-to-Pi copying and direct top-bar
shortcut described below. The corrected image build, download verification,
62 GB card write and full read-back verification **passed**. The user has
booted the new card and reports successful UI and Copy to Pi tests. SSH
access is now provisioned and remote inspection passed: correct build/card,
expanded root filesystem, installed touch changes and a fully verified
613-file internal export. Starlight MIDI/headphone setup and older music
still need selective restoration without replacing the user's new library.
The successful older builds and
hardware checks later in this document describe the September 12 image; they
do not establish acceptance of these additions.

The first attempt compiled Mixxx and generated its ARM64 package successfully,
then failed when desktop assembly encountered a test-generated `__pycache__`
directory. The installer now selects regular named helper files; a regression
test executes that stage with generated junk present. The corrected
[build 35761701616](https://github.com/GitariDev/mixxx-pi-gen/actions/runs/35761701616)
passed all stages and includes the top-bar shortcut directly, with no separate overlay required.
Its image artifact is `10710887081` (1,774,013,140 bytes); outer SHA-256 is
`80438de39379843070ac4614e0d6c84c21c27c97bd1cb156daa77a77866e85bd`.

Local verified outputs are in `deploy/touchscreen-35761701616/`. The compressed
image SHA-256 is
`2052320ad1ce7cb62a3081209188e8739d887d99a06a20169b303d9f1965342a`;
the package SHA-256 is
`57683306ff60574966219defd6aa4b49eec72354f8c503e1de83f0144ff20a09`.
The raw image is **6,345,981,952 bytes**, with a valid MBR signature and FAT32
boot/Linux root partition bounds that fit both the image and the 62 GB card.
`BUILD-VERIFICATION.json` records these checks. Raspberry Pi Imager 2.0.11.1
wrote the reidentified 62,226,694,144-byte external USB SD Drive (`disk8` at
write time) and passed read-back verification without skipping it.
`imager-write-complete.png` records the successful result. Imager auto-ejected
the card despite its disabled auto-eject preference. The user subsequently
booted the card, tested the UI/copier and installed the dedicated public key
through the Pi terminal. Ordinary SSH now works. Inspection confirmed the
expanded root has 45.6 GiB free; all 613 copied files (2,072,726,997 bytes)
match both their receipt and USB source. Mixxx's database check passed and
all recorded track paths exist. See `deploy/new-install-20260923/RESULTS.md`.

The new profile currently assigns Starlight master output only; MIDI mapping
and headphone cue channels need restoring. The old SD music directory is
empty, and 39 of the old backup's 41 audio files are absent from the new
export. Preserve the new profile/library and copy receipts before selective
restoration; the whole-profile replacement recipe below is for a fresh,
unused profile and must not overwrite these new user changes.

The new Mixxx package is installed on the current Pi. Silent tests confirmed
automatic export alias add/remove and real MANTACORE unmount/remount while
SD-Backup stayed selected. Detection was visible at the 5–6 second checks.
Starlight MIDI reopened; the touch skin remained intact. These tests used
one physical USB plus SD and do not certify two-USB playback handover.

## Decisions reviewed on 2026-09-12

- The [linked DSI screen](https://shop.ivyliam.com/product/7-inch-capacitive-touch-screen/)
  is 800×480 at 60 Hz. Keep scale 1 initially. Pioneered declares a 480×420 minimum;
  a 36 px bar leaves 444 px, or about 420 px with the Mixxx menu visible.
- Upstream MixxxPi's latest named stable image is v1.2 (2025-09-12). Its latest
  nightly found during this review was published 2026-09-09 and uses commits
  after Mixxx 2.5.6. The only upstream main change missing from this fork was a
  README correction. The image-generation code was already current.
- Build [Mixxx 2.5.6 stable](https://mixxx.org/download/) and the reviewed Pioneered
  revision, recorded in `source-versions`. Package repositories remain live:
  this pins application/skin sources, not every Debian package.
- The application uses Release mode without benchmark/unit-test binaries for
  the 16 GB card. Host regression checks still run. GCC 14's stringop-overflow
  diagnostic in libdjinterop's bundled date.h is kept as a warning in that
  dependency; its bounded unsigned conversion fits 10 digits into 11 slots.
  The exact build-only patch is retained at `/opt/mixxx-gcc14-djinterop.patch`.
- Current Trixie no longer provides `raspberrypi-ui-mods`. Sway and LightDM
  are installed explicitly with `lightdm-gtk-greeter`, and LightDM is enabled
  directly instead of using the Labwc/Wayfire toggles in raspi-config.
- Pioneered styles QMenu items but misses QCheckBox widgets in the library
  column selector. Mixxx's `WTrackTableViewHeader` uses `WMenuCheckBox` inside
  QWidgetAction. The added QSS covers white text, hover, disabled and checked
  states while preserving the skin's deck layout.
- Pi 4B includes Bluetooth 5.0. BlueZ, Pi UART integration, Blueman and a
  PolicyKit agent provide pairing and authentication in Sway. Bluetooth audio
  is a separate task; this image retains its existing audio service policy.
- Use SD folders for backup music, with the existing root partition expanding
  on first boot. A second partition would reserve space but is unnecessary for
  this goal and would complicate first-boot resize. Reflashing the whole card
  erases its music too: maintain the USB/computer copy.

## Touch navigation

The top bar has **Desktop**, **Mixxx**, **Settings**, **USB → Pi**, Bluetooth
and keyboard buttons. **USB → Pi** opens the music copier directly on the
desktop workspace. Desktop switches to workspace 2 while Mixxx keeps playing. Mixxx
returns to the existing window. Settings opens buttons for Bluetooth, Wi-Fi,
SD music, **USB → Pi**, display settings and a terminal. Mixxx starts without forced
fullscreen. If you enter fullscreen manually, the bar overlays its top edge;
tap Mixxx to leave fullscreen and restore the usable layout.

Desktop utilities share a tabbed workspace: each gets the full screen width,
and the 32 px tabs below the top bar switch between open apps. This avoids
splitting Bluetooth, files and network settings into narrow columns at 800 px.
The Settings launcher remains a floating panel; Mixxx keeps its own workspace.

Before starting a new Mixxx process, `mixpi-touch-defaults` selects **Pioneered**
only when no Mixxx configuration exists. It adds missing library preferences
for **34 px rows** and a **17 px font**, retaining any saved values and skin
choice. It refuses to write while Mixxx is running. The image does not install
the old repository `mixxx.cfg` or a historical database, and does not choose
controller/audio devices. Pioneered's own SETTINGS panel controls its layout;
**Ctrl+P** opens full Mixxx preferences using the touch keyboard.

The updated Pioneered Browse page has larger headers, sidebar rows, menu
entries and column-menu checkboxes. Its horizontal and vertical scrollbars
are **26 px** wide/high, with contrasting handles; the horizontal bar appears
when columns overflow. Decks and the Overview/Samples layout retain their
existing sizes. Select a track and tap the new **Actions** button beside
Show/Hide to open its context menu. This covers track actions; touchscreen
long-press for sidebar and column-header menus is still outstanding.

The build applies `pioneered-touch.py` to the pinned skin and retains the helper
and its styles under `/opt/mixpi-skin-tools`. Its first originals are saved in
the skin's `.mixpi-touch-original/` directory. For a live trial, apply it to a
separate user-skin copy; optional `--config PATH` explicitly sets the row/font
preferences and saves `PATH.before-mixpi-touch`. Stop Mixxx before that option.
Changing the selected skin and restarting Mixxx remain separate steps.

Pair devices: Bluetooth button → power adapter on if needed → put keyboard
or mouse into pairing mode → Search → select device → Pair → Trust → Connect.
For a keyboard PIN, type the displayed code on that keyboard and press Enter.
Verify reconnect after reboot. The touch keyboard remains available throughout.

## Build and flash the NEW card

The **Touchscreen test image** Actions workflow builds this branch on an ARM64
Linux runner and uploads an image, Debian package, versions, checksums and log.
It does not publish a release. Local Linux builds can use `sudo ./build.sh` in
a checkout whose path contains no spaces. Allow ample disk space (at least
40 GB recommended); the builder retains multiple root filesystems and compiler
dependencies. This Mac had only about 11 GB free during planning. A temporary
Colima VM was removed when direct Pi testing was chosen. The Docker, Colima
and Lima command-line tools installed for that attempt remain on the Mac.

Run host checks with `python3 -m unittest discover -s tests -v`.
These validate scripts, SSH provisioning, window switching, repeatable skin
patching, media discovery helpers and transfer safeguards. They do not replace
Mixxx compilation, rendering or playback checks.

1. Download the successful build artifact and verify its `SHA256SUMS`.
2. Identify the **new** SD card by model/capacity before writing anything.
3. Flash the image using Raspberry Pi Imager's **Use custom** image option.
4. Before first boot, put this Mac's dedicated **public** key on its boot
   partition, named `mixpi-authorized-key.pub`:

   ```sh
   cp ~/.ssh/mixpi_ed25519.pub /Volumes/bootfs/mixpi-authorized-key.pub
   ```

   Confirm the actual boot volume path first. Never copy the private key.
   The first-boot service validates and imports the public key, then removes
   that provisioning file. SSH password login is disabled; the upstream
   `pi` / `mixxx` local login is not an SSH credential in this build.
5. Boot the Pi, allow the filesystem resize/reboot to complete, then join home
   Wi-Fi using the network tray icon. Ethernet also works for initial access.
6. From this Mac connect with:

   ```sh
   ssh -i ~/.ssh/mixpi_ed25519 pi@mixxxpi.local
   ```

   If mDNS fails, use the Pi's address shown in network settings/router.
   No internet tunnel or router port forwarding is necessary on the same LAN.
   On another computer, generate an Ed25519 key and provision its `.pub` instead.

## Moving to the larger card with limited Mac space

On **2026-09-22**, the Mac-attached replacement card reported
**62,226,694,144 bytes** and was then `disk8`. That identifier is temporary:
recheck model, external/removable status and exact capacity immediately before
writing. The Pi's running card was about **14.8 GiB**; retain it as rollback.
The separate **MANTACORE** USB export on the Pi was about **2.1 GB** and must
remain untouched. These observations identify different devices, not aliases
for the flashing target.

The Mac had roughly **4.6 GB** free. Budget for the compressed image (about
1.6 GB, subject to the new artifact size), saved music and Mixxx profile. Do
not expand the approximately 6.3 GB raw image locally, or keep both GitHub's
outer artifact ZIP and an extracted copy of its inner image ZIP.

1. **Back up the current rig before swapping cards.** Music can be copied
   separately; quit Mixxx before taking the final `.mixxx` archive so its
   database and saved configuration agree. Confirm no `mixxx` process remains.
   Stream archives to a private Mac backup directory, using temporary names
   until SSH/tar completes successfully:

   ```sh
   ssh -i ~/.ssh/mixpi_ed25519 pi@mixxxpi.local \
     'tar --one-file-system -C / -czf - home/pi/Music media/SD-Backup' \
     > music.tar.gz.partial
   # Run this second command only after quitting Mixxx:
   ssh -i ~/.ssh/mixpi_ed25519 pi@mixxxpi.local \
     'if pgrep -u "$(id -u)" -x mixxx >/dev/null; then exit 1; fi; tar -C /home/pi -czf - .mixxx' \
     > mixxx-profile.tar.gz.partial
   ```

   After each successful command, check the archive with `tar -tzf`, rename it
   without `.partial`, and record its SHA-256. Do not use tar's `-h` option:
   `~/Music/Rekordbox` is a symlink to `/media/SD-Backup`, which is included
   once by its real path. That SD copy contains **1,075,207,881 bytes** from the
   earlier verified transfer. Include any additional completed local
   `/media/pi/MixPi-*` export directories explicitly if present; do not archive
   all of `/media` or follow mounted USB drives. A separate `.config` backup
   is useful for reference, but restoring it wholesale would replace the new
   Sway settings. Measure archive sizes against free Mac space before download.

2. **Wait for the new build to succeed, then stream the outer artifact.** Use
   the image artifact ID from that successful run, not the historical IDs
   below. macOS's `tar` is bsdtar and can extract the outer ZIP from a pipe:

   ```sh
   artifact_id=REPLACE_WITH_SUCCESSFUL_IMAGE_ARTIFACT_ID
   mkdir -p output/post-gig-image
   set -o pipefail
   gh api "repos/GitariDev/mixxx-pi-gen/actions/artifacts/${artifact_id}/zip" |
     tar -xf - -C output/post-gig-image
   (cd output/post-gig-image && shasum -a 256 -c SHA256SUMS)
   ```

   Confirm extraction and checksums succeed before using the inner image ZIP.
   This saves the compressed image, package and metadata without a second
   outer ZIP. Keep the backups outside this output directory.

3. **Flash and verify only the reidentified replacement card.** Raspberry Pi
   Imager **v2.0.11.1**, installed on this Mac at inspection, accepts the inner
   ZIP directly. Use its custom-image UI or the equivalent command below,
   replacing both placeholders with the verified paths:

   ```sh
   "/Applications/Raspberry Pi Imager.app/Contents/MacOS/rpi-imager" \
     --cli --disable-eject /absolute/path/to/INNER-IMAGE.zip /dev/diskN
   ```

   Verification is enabled by default. `--disable-eject` leaves the card
   available for the public-key provisioning step above. Do not pass the
   outer GitHub artifact ZIP to Imager. Confirm the mounted boot partition
   belongs to the replacement card, provision the `.pub` key, then eject it.

4. **Boot and reconnect.** Shut down the Pi before the physical card swap.
   Let resize/reboot complete, then join Wi-Fi using the on-screen network
   applet or connect Ethernet. Wi-Fi profiles are not automatically carried
   across by this image. If profiles were backed up separately, restore the
   selected NetworkManager connection files after initial access, with
   root ownership and mode `600`, then reload NetworkManager. Keep credentials
   out of logs and the repository; no extra first-boot bootstrap is required.
   The new image also regenerates SSH host keys. Verify the new fingerprint
   on the Pi before replacing the old known-host entry on the Mac.

5. **Restore while Mixxx is stopped on the new card.** It starts automatically
   with the desktop, so quit it again and confirm the process has exited.
   Move the fresh `/home/pi/.mixxx` directory aside as a backup before restoring;
   do not merge it with the saved profile. The actual archives in
   `deploy/migration-20260922/` are `settings.tar.gz` and uncompressed `music.tar`.
   Stream them over SSH without extracting another Mac copy. For settings, run
   `sudo tar -xzf - -C / home/pi/.mixxx` on the Pi, selecting only that directory
   so reference Sway settings and rollback files are not restored. For music,
   run `sudo tar -xf - -C /`. Both archives contain paths relative to `/`,
   including `home/pi/...`; do not extract them relative to `/home/pi`. Ensure
   `/home/pi/.mixxx`, `/home/pi/Music` and `/media/SD-Backup` belong to `pi:pi`.
   Preserve the `Music/Rekordbox` symlink and verify restored file checksums,
   library/playlists, saved Starlight mapping and audio routing before use.
   Run the acceptance checks below. Keep the original Pi card unchanged until
   the replacement passes; do not copy a newer database back onto it.

## Music stored on the SD card

- Tap **USB → Pi** in the top bar (also available in **Settings**) to open
  the local touch copier. Select a mounted
  drive, review the file count, space and destination, then tap **Copy to Pi**.
  It copies a compatible Rekordbox export's complete `PIONEER` and `Contents`
  trees together to a new `/media/pi/MixPi-<label>-<fingerprint>/` directory.
  Ordinary files go into a new folder under `~/Music/Backup`. This version
  copies whole exports rather than selecting individual Rekordbox playlists.
  It leaves source files and `/media/SD-Backup` intact, verifies copied bytes,
  and publishes only a complete copy. Repeating a transfer verifies the
  existing backup. Space checking retains a **512 MiB minimum reserve**;
  leave more headroom for normal use and copy outside a performance.
- The same helper supports `mixpi-media list`,
  `mixpi-media plan --source /actual/mount/path`, and
  `mixpi-media copy --source /actual/mount/path` over SSH. The source must be
  one of the mounted removable drives reported by `list`. No browser/server
  is needed for this first version. A verified copy still needs to be opened
  in Mixxx; it does not directly edit the running Mixxx database.
- Plain audio backup: `~/Music/Backup`. Copy audio from the USB drive with
  **Settings → SD music**, then add the folder in Mixxx Preferences → Library.
- Complete rekordbox export: `/media/SD-Backup`, also reachable through
  `~/Music/Rekordbox`. Copy the USB export's **PIONEER** and **Contents** folders
  directly inside it. Preserve their folder structure. Refresh the Rekordbox
  source in Mixxx; it should show **SD-Backup** even after ejecting the USB.
  This is an ordinary directory on the SD root filesystem, not another disk.
- Wi-Fi transfer example, from the Mac:

  ```sh
  scp -i ~/.ssh/mixpi_ed25519 -r /path/to/music/. pi@mixxxpi.local:Music/Backup/
  ```

  Replace the source path with your actual files. For a complete export, copy
  `PIONEER` and `Contents` to `/media/SD-Backup/` instead. Copy while not DJing,
  and leave several GB free for updates, logs and analysis.

The new Mixxx patch probes Linux removable mount points and local export
directories every **two seconds** on a worker thread. It retains directories
directly under `/media`, `/media/$USER` and `/run/media/$USER`, including
`/media/SD-Backup` and copies made by USB → Pi, and looks for
`PIONEER/rekordbox/export.pdb`. Unchanged probes leave the sidebar alone;
device removal is deferred while an import holds its tree item. An arbitrary
Music subfolder is not an export-discovery root.

This automates compatible **Rekordbox device discovery**, with playlist
metadata imported when a device is opened. It does not automatically index
plain-audio drives or run BPM/key/waveform analysis on insertion. A Device
Library Plus-only export is not the supported legacy PDB format. Use the
compatible rekordbox Export mode library; copying only audio does not preserve
rekordbox playlists/cues. On the earlier unpatched image, use the Rekordbox
source's refresh link after mounting or copying an export.

References: [Mixxx external library manual](https://manual.mixxx.org/2.5/en/chapters/library#using-the-rekordbox-library),
[2.5.6 scanner source](https://github.com/mixxxdj/mixxx/blob/2.5.6/src/library/rekordbox/rekordboxfeature.cpp).

## Direct testing over SSH

SSH does not mirror the screen by itself. `mixpi-session` connects commands to
the already-running desktop user's Sway/Wayland session:

```sh
cat /opt/mixxx.tag /opt/mixxx.version /opt/pioneered.version
mixpi-session swaymsg -t get_outputs
mixpi-session swaymsg -t get_tree
mixpi-session grim /tmp/mixpi-screen.png
systemctl status bluetooth hciuart ssh --no-pager
bluetoothctl show
/usr/sbin/rfkill list
df -h / /media/SD-Backup
lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINTS
```

Fetch a screenshot on the Mac with
`scp -i ~/.ssh/mixpi_ed25519 pi@mixxxpi.local:/tmp/mixpi-screen.png ./mixpi-screen.png`.
After editing the desktop config, `mixpi-session swaymsg reload` reloads Sway;
Waybar config/style changes require `systemctl --user restart waybar`.
Restart Mixxx after changing the skin stylesheet, once playback has stopped.

## Acceptance checks on the new card

- Confirm native 800×480 at scale 1. Check all bar buttons and the bottom of
  Pioneered's Browse/Overview/Samples pages, including with the keyboard open.
- Open the library column selector. Check white labels, distinct checked and
  unchecked boxes, hover/focus, scrolling to the last entries, and toggling
  several columns without the menu unexpectedly closing.
- In Browse, select adjacent enlarged rows, drag both scrollbars, reach the
  last column, and tap **Actions** for the selected track. Dismiss the menu by
  touch; test long menus and the sidebar without clipping required controls.
  Confirm saved row/font choices survive restart.
- With two drives, insert B while browsing/playing from A, then unload/eject A,
  reinsert it, and swap in another source. Confirm automatic Rekordbox discovery
  leaves unaffected selection/playback intact and SD copies remain available.
  Test removal during import; MIDI reconnect and audio routing are separate
  checks, not guarantees provided by the media patch.
- While two tracks play, tap Desktop → Settings → Bluetooth, then Mixxx.
  Audio must continue and there must still be only one Mixxx process.
- Pair/trust/connect a keyboard and mouse using touch alone. Reboot and test
  reconnect. Verify Preferences, display and network dialogs remain reachable.
- Copy a small complete rekordbox export to SD-Backup. Eject USB and load both
  decks from SD, confirming playlist, cues and beatgrid on representative tracks.
- Use **USB → Pi** to copy a small export and ordinary files. Verify checksums,
  retry the same copy, cancel a transfer, and test insufficient-space handling.
  Load the finished SD copy in Mixxx with USB removed. This is additional to
  the older direct-copy check above.
- Run a 30-minute two-deck/controller test. Check `vcgencmd get_throttled`,
  temperature, audio dropouts and `/home/pi/.mixxx/mixxx.log`.

## Verified September 12 build

[GitHub run 34699646629](https://github.com/GitariDev/mixxx-pi-gen/actions/runs/34699646629)
succeeded on 2026-09-12 at commit `5aeaa9cd04f864590388355b194a97ef7c173589`.
All 10 host checks passed; Mixxx compilation, SD image creation, checksums and
artifact upload completed. The compiler cache and full build log were saved.
The [image artifact](https://github.com/GitariDev/mixxx-pi-gen/actions/runs/34699646629/artifacts/10299888151)
is 1,772,607,772 bytes and is retained until 2026-09-26. This is an outer ZIP
containing the compressed disk image, Debian package and build metadata.

Outer artifact SHA-256:
`ced9b1e8fd4fedc6cba47f7d8faeb5c96da765635ef1a05ae7c6433bb6acaf0c`

The downloaded artifact and its inner checksums were verified locally.
`image_2026-09-12-mixxx-pi.zip` expands to a 6,341,787,648-byte image with
a 512 MiB FAT boot partition and an ext4 root partition; it fits the new
15,931,539,456-byte card. Every runtime dependency named by the generated
ARM64 package appears in the image's installed-package manifest.

Compressed image SHA-256:
`9c07d735072b56b84e0a24a1ca5b025630b3df8d8b4d969d4bbb8e3a11ef66cf`

Raw image SHA-256:
`cbaf169c10bce0383d48ca125a63f96437860bc818e278a7d3160b23360a6873`

## September 12 on-device checks

The image above was flashed to the new card and passed Raspberry Pi Imager's
readback verification. On-device testing confirmed Debian 13, the pinned Mixxx
and Pioneered versions, native DSI 800×480 at scale 1, automatic root expansion,
and successful first-boot SSH public-key import. SSH password and root login
are disabled. System and desktop services had no failed units.

The Pioneered column menu was inspected on the actual screen: white labels,
filled/empty checkbox states, hover highlighting, and toggling without closing
the menu all worked. The user also confirmed the menu and Bluetooth mouse work;
the MX Master 3 is paired, trusted, connected and registered with Sway.

Opening multiple desktop utilities exposed a width problem in the original
image: they tiled into 400 px columns. The tabbed-layout follow-up in this
branch was validated by Sway and applied over SSH. Bluetooth, Music and Network
Connections then each occupied the full 800 px width, with 32 px touch tabs.
Mixxx retained its 800×444 window and original process throughout these checks.
This layout follow-up is newer than image run 34699646629.

The follow-up [image build 34706423257](https://github.com/GitariDev/mixxx-pi-gen/actions/runs/34706423257)
succeeded at commit `f68ad9422c064dce6251776874f909354b691ba2`, including all
10 host checks, compilation, image creation, checksums and artifact upload.
Its [image artifact](https://github.com/GitariDev/mixxx-pi-gen/actions/runs/34706423257/artifacts/10301951842)
is available until 2026-09-26. GitHub reports an archive size of 1,772,519,564 bytes
and SHA-256 `d9d7d0d84c4af7c93cfbd7e0ae3aaa22ad79cd4a02ddcae016df1314ee4b8bfc`.
This second image has not been downloaded or flashed locally; the running Pi
already received the identical Sway configuration over SSH. No reflash is
needed to use the tested layout on the current card.

The attached export was copied to `/media/SD-Backup`: 320 files totaling
1,075,207,881 bytes. A checksum-based rsync dry run reported no differences;
about 7.3 GiB remained available on the root filesystem. Mixxx discovered
**SD-Backup**, parsed its playlists, loaded a track into Deck 1, and rendered
its waveform and cue markers. The open audio file was confirmed under
`/media/SD-Backup/Contents/`. The USB source remains unchanged and mounted.

To refresh exports in Pioneered, tap **Show**, activate **Rekordbox**, then
expand its devices. If needed, hide the sidebar and use the refresh link at
the bottom of the Rekordbox information page. Activate **SD-Backup** to parse
its playlists, then hide the sidebar to see the tracks.

One upstream Pioneered limitation was observed: its QSS makes the time value
transparent when the display is set to combined elapsed/remaining mode
(`PositionDisplay=2`). Clicking the time readout cycles to elapsed or remaining
mode. This was diagnosed from the pinned skin and Mixxx widget source; no
playback interruption or additional time-display patch was applied.

Keyboard pairing/reconnect, restart persistence, audible playback and a test
with USB disconnected still need user acceptance. Roll back by shutting down
and restoring the original card; do not copy a newer Mixxx database over it.

`wtype` was installed on the running Pi as a small keyboard-navigation test
utility. It is not required for Bluetooth pairing and is not part of the image.
