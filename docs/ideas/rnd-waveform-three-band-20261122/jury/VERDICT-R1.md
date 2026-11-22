# Jury round 1 verdict (2026-11-22)

Gates (leader's check, confirmed by J2): A, B, C and D pass G1–G5. A passes G1 only with its fix (the main rows skip Filtered's ×2; stock Filtered with J15 has 18.7 % of a typical track's columns at the edge). C passes G3 only when drawn as uniform-colour passes (×1.19; ×3.03 with per-vertex colours). Stock types 24 and 25 fail G1 (and 24 fails G3).

Seats (each differs in model and persona; none produced the directions; jurors scored alone and did not see each other's reports):
- J1 working club DJ, Claude Opus 5.5 (default effort): images only, K1–K4. `J1-dj-opus.md`
- J2 Mixxx/GPU engineer, Claude Fable 5.2 (default effort): images, notes, simulator and Mixxx code. `J2-engineer-fable.md`
- J3 owner proxy, Claude Sonnet 5.5 (default effort): images, notes, casebook and spec 2h. `J3-owner-proxy-sonnet.md`
Strike check skipped: the casebook has no scored cases yet, so the case goes to the owner (appeal).

## Median per criterion (J1, J2, J3)

| | K1 sep. ×3 | K2 cues ×3 | K3 size ×2 | K4 fit ×1 | K5 cost ×1 | Weighted /10 | Spread over 2 |
|---|---|---|---|---|---|---|---|
| B Stack | 7 (5, 8, 7) | 7 (5, 7, 8) | 8 (8, 8, 9) | 7 (7, 7, 7) | 7 (–, 7, 7) | **7.2** | K1, K2: 3 |
| C Split | 7 (7, 8, 7) | 8 (7, 8, 8) | 5 (6, 5, 5) | 6 (6, 5, 6) | 6 (–, 5, 7) | **6.7** | – |
| D Lanes | 9 (9, 9, 9) | 5 (7, 5, 5) | 3 (5, 3, 3) | 5 (5, 4, 5) | 7 (–, 7, 7) | **6.0** | K3: 2 |
| A Overlay | 6 (6, 7, 6) | 6 (7, 6, 6) | 4 (5, 3, 4) | 8 (8, 9, 7) | 7 (–, 7, 7) | **5.9** | K3: 2 |
| Today | 2 (2, 3, 2) | 7 (4, 7, 7) | 8 (7, 8, 8) | 4 (4, 3, 4) | 10 (–, 10, 10) | 5.7 | K2: 3 |

Ranking: B, C, D, A. All four directions score above today; J2 and J3 see D and A level with today overall.

## Dissent, one line per seat
- J1 (DJ): D first, C second, B last: "B is today's brick painted in three colours"; kicks still lost on a loud master; D never hides a band. Would give D's bass lane 50 % of the row and the upper lanes their own gain.
- J2 (engineer): B first; B keeps J15 exactly, the slip view and today's cost; B's caveat: band thickness is a share of the outline, not a band level. C is the fallback if kicks read too softly.
- J3 (owner proxy): B first (C-0001, C-0002, C-0003); likely objection: the share-not-level caveat and deck 2's row being mostly deck 1's blue. Question: is blue / orange / white the right pairing given the deck badges?

## Errors J2 found, all fixed before J3 sat
"Type 26" is 25; the 19 % edge figure is the tallest band (79 % of edge columns across the library are the bass); slip mode unstated; the bench allocated per frame for A, B, D (re-run: A ×1.29, B ×1.22, D ×1.17); two numbers had no evidence file (now `42-…txt`, `40-…txt`); A's Loop panel height unstated (now: median 0.31, up to 1.19 on a boosted quiet master); B needs per-channel band maxima; the deck-colour pairing.

Decision: appeal to the owner (brief: the owner chooses). Shown: all four directions, today, and the jury's reasons (`deploy/rnd-waveform-three-band-20261122/50-owner-choice.png`).
