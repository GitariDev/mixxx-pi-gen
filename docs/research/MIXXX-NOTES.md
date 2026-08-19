# Mixxx research notes

Research refreshed 2026-08-19. Official documentation is the authority for
behavior; community posts are included as workflow signals, not guarantees.

## What the software makes possible

- Mixxx 2.5 supports MIDI/HID controllers, keyboard mappings, JavaScript mapping logic, playlists, crates, Auto DJ, samplers, recording, multiple effect units, and custom effect chains.
- Playlists preserve order; crates are unordered multi-membership collections. A playlist can be queued into Auto DJ, while crates can be selected as random Auto DJ sources.
- The programmable mapping engine can make one input perform several actions, create shifted layers, adapt value curves, and drive controller feedback. This is the foundation for the proposed auxiliary surface.
- Mixxx 2.5 added mapping settings inside Preferences for mappings that declare JavaScript settings, a hidden-menu option, new effects, and `--start-autodj`.

## What this repository adds

- Builds the Mixxx `2.5` branch on Raspberry Pi OS Trixie.
- Sway session with Mixxx autostart/fullscreen and a touch Waybar.
- On-screen keyboard, display configuration, Nautilus, USB automount tooling, PipeWire/`qpwgraph`, controller udev access, and small-screen skins.
- Performance-oriented kernel/CPU configuration described in the project README.
- Important caveat: the checked-in `mixxx.cfg` is not currently installed by the build script, so it must not be treated as the live Pi configuration.

## Community takeaways

- A common controller setup sequence is: connect before launch, open Preferences → Controllers, enable the detected device, load its mapping, then restart Mixxx if required.
- Community users do supplement small DJ controllers with generic MIDI devices for effects, levels, and shifted functions; this supports the control-surface idea.
- Raspberry Pi + Mixxx is widely discussed as feasible, but reliable power, controller compatibility, audio routing, and a deliberately limited interface matter more than headline capability.

## Sources

- [Mixxx 2.5 manual](https://manual.mixxx.org/)
- [Mixxx Library: playlists, crates, and Auto DJ](https://manual.mixxx.org/2.5/en_gb/chapters/library)
- [Default keyboard mapping](https://manual.mixxx.org/2.5/en_gb/chapters/appendix/keyboard_mapping_table)
- [Mixxx Controls reference](https://manual.mixxx.org/2.5/en/chapters/appendix/mixxx_controls.html)
- [Mixxx feature overview and programmable mappings](https://mixxx.org/features/)
- [Mixxx 2.5 release notes](https://mixxx.org/news/2024-12-24-mixxx-2_5-released/)
- [Hercules controller configuration and Starlight index](https://github.com/mixxxdj/mixxx/wiki/Hercules)
- [Community controller setup example](https://www.reddit.com/r/Beatmatch/comments/1jvhnx0/)
- [Community generic-controller mapping example](https://www.reddit.com/r/Beatmatch/comments/dipvp1/)
- [mixxx-pi-gen project](https://github.com/fayaaz/mixxx-pi-gen)

