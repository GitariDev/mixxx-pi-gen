# Controller upgrade and connection-agnostic design

## Status

- Current baseline: Hercules DJControl Starlight.
- Upgrade desired: yes.
- Replacement model: not selected.
- Mouse: connected and working; Preferences/settings issue resolved.

## Upgrade requirements

Use these as selection gates rather than choosing by brand alone:

- Existing, maintained Mixxx mapping for the installed Mixxx 2.5 version.
- Verified Linux support without a proprietary Windows/macOS-only driver.
- Class-compliant MIDI or well-supported HID behavior.
- Two dependable decks with play, cue, tempo, jog, channel faders, EQ, gain, crossfader, browse, load, Sync, loops, and at least four performance pads per deck.
- Dedicated headphone cue controls and a usable main/headphone USB audio interface, or an explicit plan for a separate interface.
- Controls and labels readable at the 7-inch-screen working distance.
- Power demand suitable for the Pi topology, preferably with its own supply when large or motorized.
- Physical size and cable exits compatible with the intended enclosure/stand.
- Mapping must expose the four-cue convention and essential loop/sample modes without touchscreen dependency.

## Preferred architecture

```text
Pi image and Mixxx configuration
├── display: DSI now; HDMI/other display allowed later
├── navigation: USB mouse now; keyboard/touch remain optional
├── primary DJ controller: Starlight now; replaceable MIDI/HID device later
├── audio: controller interface or separate named USB interface
├── storage: boot and music devices treated independently
└── auxiliary surface: optional, independently mapped utility controls
```

The core image should start and remain navigable with no DJ controller attached.
Connecting a supported controller should add capability, not change unrelated
display, storage, mouse, network, or system-control behavior.

## Connection rules

- Direct-connect a new controller for its first test.
- Use a powered USB hub when total device power or port count requires one; do not expect the Pi to power every future peripheral safely.
- Never encode `/dev/sdX`, ALSA `card N`, or a physical USB port as a permanent identity.
- Keep controller input mapping and audio-output selection as separate decisions.
- Retain the mouse and a recovery path to Preferences after every mapping change.
- Store mappings by device name and version; retain the previous known-good mapping.
- A missing optional device must not prevent Mixxx from launching.

## Evaluation checklist

1. Detect with `lsusb`; confirm MIDI/HID entry in Mixxx.
2. Confirm an exact mapping exists and loads without startup errors.
3. Test every physical input and LED/output feedback.
4. Test main and headphone outputs independently at safe gain.
5. Verify the four standard hot cues, loops, sampler access, library browse/load, and emergency exit workflow.
6. Reboot and reconnect in a different USB port.
7. Test with boot storage, music storage, mouse, display, and auxiliary surface connected.
8. Run the 30-minute two-deck performance test while watching power, USB resets, temperature, and audio stability.
9. Document unsupported controls, mapping changes, and rollback steps.

## Before choosing a model

Record the desired budget, portability/size limit, two versus four channels,
need for an integrated audio interface, number of pads/knobs, standalone power,
and whether the controller should replace the proposed auxiliary surface. Those
answers determine the shortlist; they are intentionally not assumed here.

