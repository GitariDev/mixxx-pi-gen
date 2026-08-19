# Open Mixxx Preferences from the touchscreen

**Aliases:** preferences, settings, skin settings, fullscreen, on-screen
keyboard, controller settings

**Current status:** resolved. A USB mouse now provides reliable settings access;
this page remains as a fallback/recovery runbook.

The **SETTINGS** control beside `ON AIR` in the Pioneered skin changes the skin
layout (samplers, waveforms, mixer, and similar panels). It is not the full
Mixxx Preferences dialog.

## Reliable path

1. With the mouse, leave fullscreen or use the normal Mixxx menu and open **Options → Preferences**.
2. If the menu is unavailable, tap the keyboard icon in the top Waybar. The image includes `wvkbd` and wires this icon to toggle it.
3. On the on-screen keyboard, tap `Ctrl`, then `P`.
4. Select **Controllers**, **Sound Hardware**, or the needed full settings page.
5. Close the keyboard when it obstructs the dialog.

## Alternatives

- `Super+F` toggles fullscreen for the focused window.
- The Sway configuration uses `popup_during_fullscreen leave_fullscreen`, and a helper exits fullscreen when a new dialog opens, specifically so Mixxx dialogs are not hidden.
- If Mixxx loses focus, tap the headphone/Mixxx icon in Waybar.

## If the dialog is hidden

- Tap the Mixxx window, then retry `Ctrl+P`.
- Toggle fullscreen with `Super+F` and retry.
- Use `Super+Enter`, run `mixxx`, and inspect `/home/pi/.mixxx/mixxx.log` if the application is not responding.
