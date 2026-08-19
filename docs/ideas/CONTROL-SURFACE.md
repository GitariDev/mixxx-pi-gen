# Auxiliary control surface — Stream Deck / F1 steering-wheel idea

## Goal

Add a compact, glanceable control layer for everything the primary DJ controller
and touchscreen do poorly: view changes, library movement, incoming-track handling,
effect selection, Preferences, and safe system actions.

The Starlight is the current baseline but may be replaced. Mixxx supports keyboard mappings, MIDI/HID input, and programmable JavaScript
controller mappings. This makes a generic macro pad, MIDI pad/knob device, or a
DIY USB controller viable. A real Stream Deck may need Linux-side software and
more maintenance than a class-compliant MIDI device.

## Recommended first prototype

Start with a class-compliant MIDI controller with buttons plus at least one
encoder. It is more naturally integrated with Mixxx, can support LEDs, and
avoids making keyboard focus part of every performance action. Use keyboard
macros only for Sway/system commands Mixxx cannot own.

Keep this auxiliary surface separate from the primary DJ-controller mapping so
either device can be replaced independently.

## Proposed pages

### 1. Library / incoming track

- Search focus; previous/next item; preview play/stop
- Load selected to deck 1/deck 2
- Add to current playlist or `INBOX - LIVE`
- Toggle maximize library
- One button to open the incoming-track checklist

### 2. Views / utility

- Toggle library, effects, samplers, waveforms, mixer
- Open full Preferences (`Ctrl+P`)
- Toggle on-screen keyboard and fullscreen
- Open Nautilus to removable media
- Return focus to Mixxx

### 3. Performance helpers

- Effect unit enable/focus and preset previous/next
- Dry/wet encoder with push-to-reset
- Loop size and beatjump controls
- Quantize/keylock toggles with explicit LED state
- Auto DJ enable, fade now, and skip—separated from common buttons to prevent accidents

### 4. System / safety

- Display brightness
- Audio graph (`qpwgraph`) and sound settings
- Network status
- Performance status/log shortcut
- Restart Mixxx
- Shutdown/reboot behind a hold or confirmation; never a single exposed tap

## Implementation phases

1. Inventory actions and assign each as Mixxx control, keyboard shortcut, or Sway command.
2. Prototype only library navigation, view switching, Preferences, and one effect reset.
3. Test focus behavior, reconnect behavior, and startup ordering on every boot.
4. Add labels/icons and state feedback; do not rely on memory for shifted layers.
5. Add performance controls only after the utility layer is stable.
6. Store mapping files and a printed control legend in this repository.

## Open decisions

- Stream Deck-style USB device versus generic MIDI pad/encoder versus DIY microcontroller.
- Required number of physical controls and whether stateful LEDs/displays matter.
- Whether the device must operate while Mixxx Preferences or Nautilus has focus.
- Whether “F1 steering wheel” means an actual wheel/button box to repurpose or a design metaphor for a dense, tactile command center.
