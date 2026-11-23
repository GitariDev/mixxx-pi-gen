# Owner decisions on the three-band main waveforms

## 2026-11-23, Climb hub notes on round 1 (mixpi-waveform-three-band-20261122)
- **D1, the direction: A Overlay** (stock Mixxx Filtered: bass, mids and highs drawn over each other, height-matched so the main rows skip Filtered's ×2).
  - On `50-owner-choice.png` (oc-1): "I like image 2, where the base is blue, the mids are orange and the white. This is good!" Image 2 is A Overlay.
  - On `20-compare-scene1-decks-page.png` (oc-3): "I like A."
- **D2, the colours: Pioneered's own** low #004ee4, mid #c95a00, high #f6e9d3 (the skin's SignalLowColor, SignalMidColor and SignalHighColor).
  - On `30-stock-options-at-J15.png` (oc-2): "I like the last image here. Those are good colors." The last image there is A Overlay in Pioneered's colours, height-matched.
- **A setting** (oc-4, on round 1): "Additonally, this should be a setting, we can put it in the advanced settings menu or the interface settings menu if possible. Let me know."
- **Height** (main climb, fd1e940): "The loudest tracks should stop 10% from the edge": kMainWaveformGain is 0.90. At 0.90, A's tallest band reaches 0.90 at most on the library, with no column at the edge (`43-heights-on-library-gain-0.90.txt`).

## 2026-11-23, the owner's answers in the R&D thread (the setting)
Asked in the R&D thread; the owner chose from the options given:
- **Menu:** Settings › Advanced, a fourth row (beside Waveform FPS and Read ahead). Chosen: "Advanced (Recommended)".
- **Default after the next build:** three-band (A Overlay); RGB is one tap away. Chosen: "Three-band".
- **The Loop panel's waveform:** follows the setting, as Mixxx's waveform style covers every scrolling waveform; the overview strips stay as they are. Chosen: "Follow the setting".
- **Wording:** row "Waveform colours", choices RGB and 3-BAND. Chosen: "Waveform colours: RGB / 3-BAND".

## 2026-11-23, the owner's answers to the review questions (R&D thread)
Asked after the adversarial reviews (Sol, Fable); the owner chose from the options given:
- **The Loop panel's waveform height in 3-BAND:** the same height as RGB, not Mixxx's doubled Filtered height. Chosen: "Same height as RGB".
- **A third waveform type picked in Mixxx's Preferences:** the row keeps lighting RGB. Chosen: "Keep lighting RGB".
- **A start that cannot draw 3-BAND:** the 3-BAND choice looks unavailable (disabled). Chosen: "Show it unavailable".
