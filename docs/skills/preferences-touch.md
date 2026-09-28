# Open Mixxx Preferences from the touchscreen

**Aliases:** preferences, settings, skin settings, fullscreen, on-screen
keyboard, controller settings

**Current status (2026-09-22):** the live Pi has larger Pioneered Browse rows,
menus and horizontal/vertical scrollbars. Select a track and tap **Actions**
beside Search to open its context menu. This was verified through the native
Wayland session, and the user confirmed the hands-on check worked. Header/sidebar long-press menus
remain open in the [GIG-03 action plan](../ideas/POST-GIG-PLAN.md#gig-03--context-menus-without-a-mouse).
These skin changes do not replace the full Preferences dialog.

The **SETTINGS** control beside `ON AIR` in the Pioneered skin changes the skin
layout (samplers, waveforms, mixer, and similar panels). It is not the full
Mixxx Preferences dialog.

## Reliable path

Tap **Settings** in the top bar, then **Mixxx preferences** under Playback.
Select **Sound Hardware** for DJ routing or **Controllers** for mappings.
For Spotify/phone output and volume, use **Settings → Speaker mode** instead.

Keyboard/menu fallback:

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
