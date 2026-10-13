# Song Dex design system

A music catalog terminal: PS1 graphite hardware surrounds a Ruby/Sapphire-era
Pokédex screen. Original disc and cursor art, stable entry numbers, inset panels,
and purposeful controls establish the character. No game sprites or logos.

## Sources
- https://github.com/nexu-io/open-design/blob/main/skills/frontend-design/SKILL.md
- https://github.com/nexu-io/open-design/blob/main/craft/typography.md
- https://github.com/nexu-io/open-design/blob/main/craft/color.md

## Tokens and typography
Graphite #242830 shell, #F1F0DE screen, #222730 ink, #D8DDCE secondary
surfaces, #176B63 teal action. Colors are semantic CSS variables. Pixelify Sans
is for short 24px headings; IBM Plex Sans handles 14/16px metadata and controls.
Fonts ship locally via Fontsource. Use tabular numerals for indices and timing.
Four-pixel spacing rhythm; 2px structural borders; 0–4px corners; hard shadows.
Body contrast at least 4.5:1, control/focus contrast at least 3:1.

## Layout and interaction
Navigation rail → searchable list → selected entry. Detail becomes a separate
view below 1100px. Show meaningful loading, empty, unavailable, error and partial
success states. No decorative dashboard statistics or invented match percentages.
A triangle and background identify selection. All controls have visible keyboard
focus. Button presses shift 1px. Short transitions respect reduced motion.

Album art stays clear. Dither is confined to the outer housing. No boot delay,
CRT overlays, flashing, or sound. Explicit words accompany semantic colors.
The primary action describes its effect. Applying changes always requires review.
