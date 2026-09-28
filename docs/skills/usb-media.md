# Find music on a USB drive

**Aliases:** USB missing, flash drive, thumb drive, removable media, mount,
Computer folder

**Installed and tested (2026-09-22):** the live Pi automatically discovers
compatible Rekordbox exports. A temporary export and the idle MANTACORE USB
appeared/disappeared without Refresh; the SD-Backup selection stayed intact.
Opening a device still performs its metadata import. Plain-audio automatic
indexing, two-physical-drive acceptance and safe DJ handovers are tracked in
[`GIG-01`](../ideas/POST-GIG-PLAN.md#gig-01--automatic-removable-media-discovery-and-scanning).
Use the Computer paths below for ordinary folders or as a manual fallback.

## Copy USB music onto the Pi

Tap **USB → Pi** in the top bar (also available in Settings), choose a mounted drive and review the copy size
and available space. The screen separates **From / USB drive**, **To / this Pi’s
SD card**, and the current transfer state. Tap **Copy to Pi**; wait for
**Copy complete · Verified** before using the copy. **Open copy** opens the
completed folder. **Cancel transfer** stops safely and clears unfinished staging.
**Refresh USB** starts a fresh check after an error or drive change. A compatible export copies `PIONEER` and `Contents`
together into a new named internal source under `/media/pi/MixPi-…`. Ordinary
folders go under `~/Music/Backup`. The original USB files are preserved.

Transfers use private staging, SHA-256 verification and a receipt. Existing
destinations are never overwritten; repeating the same copy verifies it
instead of duplicating it. Cancellation removes incomplete staging. Leave the
USB inserted until completion, then check the copied playlists and audio in
Mixxx before relying on the internal copy. Individual-playlist selection and
browser uploads are not part of this first version.

## Touch-first path

1. Insert the music USB and wait a few seconds.
2. In Mixxx Library, open **Computer** and look for the mounted device.
3. If it is not obvious, open Nautilus from the app launcher (`Alt+D`, then type `nautilus`) and select the removable drive in the sidebar.
4. Common mount paths are `/media/pi/<LABEL>` or `/run/media/pi/<LABEL>`.
5. Load a test track. If this is durable library music, copy it to the Pi's music folder and rescan instead of relying on the USB forever.

For a compatible **Rekordbox export**, use Pioneered **Browse → Show →
Rekordbox**, refresh the attached devices if needed, then select the device and
playlist. Hide the sidebar to see its tracks. The internal export is named
**SD-Backup**; see the [tested export workflow](../setup/TOUCHSCREEN-BUILD.md#music-stored-on-the-sd-card).

## Diagnose from a terminal

Open a terminal with `Super+Enter`, then run:

```sh
lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINTS,MODEL
findmnt --real
```

- Device absent from `lsblk`: reseat it, try another Pi USB port, remove an unpowered hub, and inspect power quality.
- Device present with no mount point: open it in Nautilus to trigger mounting, or inspect `udiskie`/`udevil` behavior before attempting a manual mount.
- Device mounted but absent in Mixxx: browse to its mount point through **Computer**, then rescan/add a library directory only if it is intended to remain available.

## Repository-specific detail

This image includes `udevil`, `udiskie`, Nautilus, and a systemd udev override
with `PrivateMounts=no`, so removable media is intended to be visible outside
the udev service namespace. Do not assume `/media` alone; confirm the actual
mount point with `lsblk`. New startup config launches `udiskie` only; the
redundant live `devmon` was stopped during the 2026-09-22 test. Mounting via
UDisks may require execution from the active desktop session; importing its
Wayland environment into an SSH process does not itself grant PolicyKit rights.

## Safety

- Keep boot storage and music storage clearly labelled.
- Eject/unmount a drive before removing it.
- Never reformat a missing drive as the first troubleshooting step.
- A USB disconnect during flashing or playback can indicate a loose device, weak power, or a failing drive.
