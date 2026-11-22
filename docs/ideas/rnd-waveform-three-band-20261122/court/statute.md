# Statute: three-band main waveforms (R&D, 2026-11-22)

Drafted by the R&D leader from the brief in `../DIRECTIONS.md`. The owner ratifies or changes it when they rule; until then it binds the jury only.

## Gates (any fail = rejected, no score)
G1. Height keeps J13/J15: with m_gain = pregain × 0.80 on the owner's library, the median track has under 1 % of its columns at the edge, and the loudest track's 99th percentile stays at or under 0.90 of the space it draws into | evidence: `tools/performance/waveform-three-band-heights.py` (deploy `40-heights-on-library.txt`)
G2. Only the decks' main waveforms are the subject: the overview strips stay as they are, and any change to the Loop panel's waveform is stated | evidence: DIRECTIONS.md "What changes"
G3. Pi 4 cost: CPU per frame at most 3 × today's on the bench, GPU fill at most 3 × today's, and no offscreen buffer or legacy fixed-function GL path | evidence: `41-cpu-bench-mac.txt`, `40-heights-on-library.txt`, renderer code
G4. Buildable on pinned Mixxx 2.5.6 with config, skin or a MixPi patch, without changing the order of the waveform type list (saved preferences refer to it by number) | evidence: `src/waveform/widgets/waveformwidgettype.h`
G5. Privacy: no track named in any image or committed file; the owner's library data stays on the Mac | evidence: the images ("Track A", "Track B"), `git grep`

## Rules
R1. Colours come from `design/tokens.css` and nothing brighter | why: owner G5 "Mute the button colors a little ... don't go too far."
R2. Every image is a simulation drawn from the renderer's code and labelled so; the card stays with the main climb | why: brief; the card is in use
R3. The owner chooses; nothing ships from this thread without that choice | why: "put it on me"
