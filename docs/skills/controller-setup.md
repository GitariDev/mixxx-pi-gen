# Configure a DJ controller

**Aliases:** Hercules, Starlight, controller, controller upgrade, MIDI, HID,
mapping, Serato controller

The Hercules DJControl Starlight is the current baseline, not a permanent
dependency. Apply the generic workflow to every replacement controller and use
the Starlight-specific mapping name only while that device is connected.

## Generic workflow

1. Connect the controller directly to the Pi before starting Mixxx. Add a powered hub only after the direct baseline passes.
2. Open full Preferences with the mouse. `Ctrl+P` remains a fallback; the skin's **SETTINGS** panel is not the full Preferences dialog.
3. Select **Controllers** and choose the detected MIDI/HID device.
4. Enable it and load the exact matching mapping. For the current device, choose **Hercules DJControl Starlight**.
5. Apply/OK. Restart Mixxx with the controller still connected if input is not immediate.
6. Verify, in order: browse/select, load left/right, play, cue, sync, jog wheels, tempo, channel levels, crossfader, filter/bass controls, pads, master, headphone level, and cue/master monitoring.
7. Record results in a controller-specific checklist before customizing anything.
8. Disconnect/reconnect and reboot once to confirm detection is not dependent on a lucky startup order or USB port.

## Detection checks

```sh
lsusb
aplay -l
```

- If it is absent from `lsusb`, check the cable, port, and power.
- If it appears in USB but not Controllers, restart Mixxx and inspect `/home/pi/.mixxx/mixxx.log`.
- This image installs Mixxx USB/HID udev access rules, including Hercules vendor access, so normal-user controller access is intended.

## Mapping strategy

- Preserve the core deck controls first; create a known-good baseline before custom layers.
- Use an auxiliary controller for system/view/library commands rather than overloading safety-critical play/cue controls.
- If customization grows beyond simple MIDI learn, Mixxx JavaScript mappings can implement shifted layers, multiple actions, LEDs, and contextual behavior.
- Keep each custom mapping in a device-named directory/file; do not replace a generic global mapping.
- Do not bind audio routing to a numeric ALSA card index. Verify the named main/headphone outputs after every hardware change.
- Keep mouse navigation functional even when the performance controller is disconnected.

See [`../setup/CONTROLLER-UPGRADE.md`](../setup/CONTROLLER-UPGRADE.md) before selecting or buying the replacement.
