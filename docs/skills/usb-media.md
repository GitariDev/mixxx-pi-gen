# Find music on a USB drive

**Aliases:** USB missing, flash drive, thumb drive, removable media, mount,
Computer folder

## Touch-first path

1. Insert the music USB and wait a few seconds.
2. In Mixxx Library, open **Computer** and look for the mounted device.
3. If it is not obvious, open Nautilus from the app launcher (`Alt+D`, then type `nautilus`) and select the removable drive in the sidebar.
4. Common mount paths are `/media/pi/<LABEL>` or `/run/media/pi/<LABEL>`.
5. Load a test track. If this is durable library music, copy it to the Pi's music folder and rescan instead of relying on the USB forever.

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
mount point with `lsblk`.

## Safety

- Keep boot storage and music storage clearly labelled.
- Eject/unmount a drive before removing it.
- Never reformat a missing drive as the first troubleshooting step.
- A USB disconnect during flashing or playback can indicate a loose device, weak power, or a failing drive.

