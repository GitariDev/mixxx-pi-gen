# Pi 4 touchscreen build and test

Branch: `codex/pi-touch-bluetooth-build`. Keep the original boot card as rollback.

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

The top bar has **Desktop**, **Mixxx**, **Settings**, Bluetooth and keyboard
buttons. Desktop switches to workspace 2 while Mixxx keeps playing. Mixxx
returns to the existing window. Settings opens buttons for Bluetooth, Wi-Fi,
SD music, display settings and a terminal. Mixxx starts without forced
fullscreen. If you enter fullscreen manually, the bar overlays its top edge;
tap Mixxx to leave fullscreen and restore the usable layout.

Desktop utilities share a tabbed workspace: each gets the full screen width,
and the 32 px tabs below the top bar switch between open apps. This avoids
splitting Bluetooth, files and network settings into narrow columns at 800 px.
The Settings launcher remains a floating panel; Mixxx keeps its own workspace.

On first boot choose **Options → Preferences → Interface → Pioneered**.
The image does not preseed a historical Mixxx database/config or change
controller/audio device choices. Pioneered's own SETTINGS panel controls its
layout; **Ctrl+P** opens full Mixxx preferences using the touch keyboard.

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
These validate scripts, SSH provisioning and window switching, not rendering.

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

## Music stored on the SD card

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

Mixxx 2.5.6's Linux source scans folders directly under `/media`, `/media/$USER`
and `/run/media/$USER` for `PIONEER/rekordbox/export.pdb`. This is why the SD
export directory uses `/media/SD-Backup`; an arbitrary Music subfolder would
not be discovered. A Device Library Plus-only export is not that legacy PDB
format. Use the compatible rekordbox Export mode library. Copying only audio
does not preserve rekordbox playlists/cues.

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
- While two tracks play, tap Desktop → Settings → Bluetooth, then Mixxx.
  Audio must continue and there must still be only one Mixxx process.
- Pair/trust/connect a keyboard and mouse using touch alone. Reboot and test
  reconnect. Verify Preferences, display and network dialogs remain reachable.
- Copy a small complete rekordbox export to SD-Backup. Eject USB and load both
  decks from SD, confirming playlist, cues and beatgrid on representative tracks.
- Run a 30-minute two-deck/controller test. Check `vcgencmd get_throttled`,
  temperature, audio dropouts and `/home/pi/.mixxx/mixxx.log`.

## Verified build

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

## On-device checks

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
