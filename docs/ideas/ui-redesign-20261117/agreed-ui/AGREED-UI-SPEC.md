# MixPi agreed UI: binding spec for build C, 2026-11-17

The owner reviewed every screen in the private review page "MixPi UI review" over five rounds on 2026-11-17 and agreed every item. Round 5 (version 5) is final. The owner then said: "Okay let's do the thread migrate where we update the climb tuner plan with all these agreed items and climb to the new pi build ... Please don't deviate from UI we set and have the reviewers know what the app is supposed to look like so they judge against that not what they think is best."

This file says what the app must look like and do. Builders build to it, and reviewers score against it.

- **Owner's words, verbatim:** `docs/ideas/UI-REVIEW-1-20261117.md`, sections 1 and 5-8.
- **Plan:** `docs/ideas/UI-REDESIGN-PLAN-20261117.md`. Section 12 maps this spec to the R-items.
- **Tuner record:** `mixpi-ui-redesign-20261117`.

## 0. How to use this spec

**What is binding:**
- **The mockups** in `mockups/` show the agreed layout, order, labels, roles and colours. They are 800×480 renders of the review page's version 5.
- **Exact UI copy:** every label in a mockup is exact copy, except track names, artist names, playlist names, counts, times and sizes, which are only examples.
- **The design files** in `design/` give the values (tokens, primitives, layout):
  - `design/all-mockups.html` holds all 12 screens.
  - `design/component-guide.html` is the component guide the owner reviewed.

**Rules for builders:**
- Build what this spec says. Mixxx skins are Qt, not HTML, so match the mockup in structure, order, labels, roles, colours and states. Pixels can differ where Qt layout forces it.
- Do not add, remove, rename, reorder or restyle anything the spec doesn't ask for.
- Where the spec and the mockups say nothing, today's build B UI stays as it is.
- Do not add any design of your own.

**Rules for reviewers:**
- Score conformance to this spec and the owner's verbatim words, together with the plan rubric (section 11, as amended in plan section 12).
- **A deviation from this spec is a finding.** Cite the spec line or mockup, and the screenshot that shows the deviation.
- **Your own preference is not a finding and must not lower a score.** That covers "it would look better if", other colours or layouts, and features the owner didn't ask for.
- If you think the agreed design has a real usability or safety problem, report it under a separate heading "Owner questions (no score effect)". The orchestrator passes those to the owner and does not change the UI on its own.

**Touch targets:** the native minimum of 48 px stays as `tests/` enforces it. The mockups draw some buttons 44 px tall. The native build may make those 48 px, and that is not a deviation.

## 1. Rules for every screen

| Rule | Spec | Owner source |
|---|---|---|
| Close on the right | Every full-screen view, side menu and sheet closes with a control at the right end of its header: tool panel, Sources (☰ becomes ✕), Sources edit, Load sample, Choose pad, Settings, Media, the Clear samples popover. | G2 "X for menus should be on the right not the left - e.g. The close x for number 11." |
| Close control | A 44×44 (48 native) square, `--mx-surface-2` background, with a **red ✕** drawn in `--mx-danger-text` #ec7f74 (two 20×2.5 px strokes). **No outline at rest.** Pressed: `--mx-danger-surface` with a `--mx-danger` border. | Item 2 "a square with a red X"; comment "Remove outline at rest."; s5 "The x is the wrong color too." |
| Roles | Every control has one role (below). EJECT is Caution, never green. CLEAR (n) and delete are Danger, always behind a confirm step. The close ✕ is Danger but needs no confirm. | G3 |
| Radius | Buttons, segments, fields and panels use **3 px** (`--mx-radius`); slider thumbs use 2 px. **Chips (not pressable) are pills**, at radius 999 px. | G4 "Reduce the button radius to be 2 or 3"; comment on chips "This is what can still have a larger radius" |
| Muted palette | Use the colours in `design/tokens.css` and nothing brighter. | G5 "Mute the button colors a little ... don't go too far." |
| Lit / chosen state | A **see-through tint** of the role colour at 26% (`--mx-lit-alpha`) over what is behind it. The border is 2 px in the role colour (1 px border plus a 1 px inset). The text is the light role colour (`--mx-*-lit`). Never a flat solid fill. | s2 "keep the transparency on the buttons when active not completly flat" |
| Ticked rows | The tick and a slight background change, `--mx-surface-2`. **No left edge.** | Comment "We don't need the left border. Just the tick and background slight change it good." |
| Current menu row (no tick) | `--mx-surface-2` background, a 4 px accent edge on the left, and semibold text. | Round 1 guide, agreed |
| Indicators | SYNC and MASTER chips, drive-state chips (READY, IN USE, EJECTING, SAFE TO REMOVE) and the USB chip's scan % are pills and can't be pressed. | g4 note; noted only |
| Fonts | **Build B's fonts** (family, size and weight) for every element. A new element uses the build B font of the element with the same role (a button, a title, a hint, a list row, a number). The mockups draw the round 1 fonts (Ubuntu Condensed, Open Sans, Ubuntu Mono); the font is the one place where they no longer bind. Exact copy, colours, sizes of controls and layout still follow the mockups. | Owner, 2026-11-18, after seeing build C: revert the font, "All fonts back to build B". Replaces the round 1 guide's font rule. |
| Scroll bars | Every list longer than its space shows a scroll bar at its right edge, so it can be scrolled by drag and by the bar (rubric 8: a 24 px bar natively). | s5 "make sure the scroll bar is present if a list is longer than the viewspace"; item 14 |

### Roles and colours (`design/tokens.css`)

| Role | Meaning | Examples | At rest | Lit / pressed |
|---|---|---|---|---|
| Navigate | Moves you around; changes nothing | tabs, BACK, menu rows, ☰, Sources items | neutral `--mx-surface-2` with a `--mx-line-strong` border; text `--mx-text` | current tab: accent underline; current row: accent edge |
| Choose | Picks one setting or mode | segments, FX 1/FX 2, routes, loop sizes, filters | neutral | lit tint of accent #a3c45e, 2 px accent border, text #bcd88a |
| Confirm | Does the thing you came for | LOAD SAMPLE, LOAD TO PAD…, DONE | solid muted accent #a3c45e, dark text #0d1014 | pressed #8fad50 |
| Sound | Changes what is heard now | ▶, CUE, TRIGGER, SYNC, KEY, Q, LOOP, RELOOP, effect ON/OFF | border at 60% of the tone, text in tone: info #5aa4c4, deck 1 #5b95d4, deck 2 #d6784a, play #5fae6e, cue #cbb551 | lit tint of the tone |
| Caution | Takes something away, but it can be redone | EJECT, pad ■ STOP | dark amber #30260e with an amber #dfa33a border and amber text #e8b65c | solid amber only while pressed |
| Danger | Can't be undone | CLEAR SAMPLES…, CLEAR (n), EXIT LOOP, the close ✕ | dark red #34191b with a red #d0574d border and red text #ec7f74 | solid red only while pressed |

Surfaces: bg #0d1014, surface #161a20, surface-2 #1d222a, line #2c333d, line-strong #3a424e. Text: #e4e7ec, dim #949dab.

## 2. Screens

### s1 Decks: `mockups/m-loop.png` (bottom half) and `m-sampler.png`
- No change, except the deck row (see s6): title and artist side by side, the artist dimmer and after the title.

### s2 Tool panel: Loop · Jump · Cues (`mockups/m-loop.png`)
- **Header:** the deck badge, "Deck 1", then the LOOP / JUMP / CUES segments, and the **close ✕ at the right end**.
- **Loop sizes:** 1/32, 1/16, 1/8, 1/4, 1/2, 1, 2, 4, 8, 16, 32, 64 in two rows of six. The chosen size uses the Choose lit state.
- **Next row:** ½ and ×2. Each is a neutral button with a **green border**, the accent at 60% (`color-mix(accent 60%, surface-2)`), because they halve or double the chosen size. Owner: "The 1/2 and 2x can have a different coloured border to help identify it."
- **Own row below that:**
  - **EXIT LOOP** is Danger (red). Owner: "Say 'exit loop' on the exit button", and "destructive coloring on the exit".
  - **RELOOP** is Sound (blue, info). Owner: "blue coloring on the re-loop".
- The deck rows, the waveforms (the focused one with − and +) and the transport row stay as they are today.
- **JUMP and CUES:** no layout change. The rules in section 1 apply.

### s3 Tracks (`mockups/m-tracks.png`)
- **Header, left to right:** search (fills the space), then ✎ actions, then ☰ Sources at the right end. Owner item 3.
- **Bottom row for each deck:** LOAD n · track name · CUE · ▶. The ▶ is back, right of CUE, on both decks.

### s4 ✎ actions
- No change.

### s5 Sources (`mockups/m-sources-top.png`, `m-sources-sub.png`, `m-sources-edit.png`)
- **Sources is a side menu.** It opens on the **right**, under ☰, over the right part of the Tracks screen. Owner, round 5: "Keep it on the right."
  - The table sits to its left, with its own scroll bar.
  - The menu covers deck 2's half of the strip and load row while it is open.
- **While the menu is open, the ☰ becomes the standard close control** (section 1: red ✕, no outline) in the same spot at the right end of the header. The header still reads search, ✎, ✕.
- **Top level:**
  - The menu header has **[‹ BACK] [✎ EDIT]**. Each has an icon beside its label: a ‹ chevron, and a pencil-on-list icon that is not the ✎ actions pencil.
  - Then the source rows: icon, title, small subtitle, and › when the row can be entered.
  - The current source has the accent edge.
- **Inside a source** (for example MANTACORE › rekordbox): the header has **[‹ BACK]** and the place name. Then that source's rows, with counts on the right.
- **Scroll bar:** a scroll bar shows at the menu's right edge when its list is longer than the panel.
- **EDIT opens the full-screen edit list** (`m-sources-edit.png`):
  - The header has the title "Edit sources", the hint "Switch sources on or off, set the order, ★ where Tracks starts.", then **DONE** (Confirm) and the close ✕ at the right.
  - Each row has ★ (start here), icon, title and subtitle, an ON/OFF toggle, ▲ UP and ▼ DOWN.
  - The row that is switched off is dimmed. UP is disabled on the first row, and DOWN on the last.
- Owner item 5: "I only wanted the edit sources to be full screen ... When at the top most menu [Back][Edit] /br [Source list items] ... When in a menu like tracks or rekordbox [Back] /br [Source list items]".

### s6 Sampler (`mockups/m-sampler.png`, `m-sampler-clear.png`)
- **Header:**
  - **+ LOAD SAMPLE** (Confirm).
  - **CLEAR SAMPLES…** (Danger).
  - The hint "Starlight SAMPLER mode: deck A pads 1-4 · deck B pads 5-8".
- **Pads:** eight pads, A1-A4 (deck 1 badge) and B1-B4 (deck 2 badge). Each loaded pad shows its number, label, duration and name, and has two buttons:
  - **▶ TRIGGER** (Sound; lit while it plays);
  - **■ STOP** (Caution).
- **Empty pad:** "+ Empty · tap to load".
- **CLEAR SAMPLES…** opens a popover titled "Clear samples", with the close ✕ at the right:
  - It lists the loaded pads, and each row has a tick, the pad number, label, name and duration. Ticked rows follow the section 1 rule, with no left edge.
  - The note "The pads go empty. The files stay where they are."
  - **CANCEL** and **CLEAR (n)** (Danger), where n is the number of ticked pads.
  - Several pads can be cleared at once.
- **Deck row, on every screen:**
  - Title and artist sit side by side, the artist dimmer and after the title.
  - When SYNC or MASTER chips show, the artist is shortened with "…" first, then the title.
- **Samples on the Pi stay over restarts and shutdowns.** Build B already does this. Build C keeps it, and the acceptance adds a full shutdown test.

### s7 Load sample (`mockups/m-loadsample.png`)
- **Header:** "Load sample", the hint "Pick a sound, then a pad", search, and the close ✕ at the right.
- **Source buttons:** SAMPLES and SOURCES… only. This Pi and Recordings are reached through SOURCES…. A hint follows: "Or a list picked in Sources."
- **Table:** Filename, BPM, Key, Duration.
- **Footer:** the hint "Tap a sound, then load it to a pad.", then **LOAD TO PAD…** (Confirm) at the right.

### s8 FX 1 and FX 2 (`mockups/m-fx.png`)
- **Mode segments:** FX 1 · DECK A PADS / FX 2 · DECK B PADS, with the hint "Starlight FX pads: 1-3 effects · 4 send to deck".
- **Route:** the DECK 1 · PAD 4 / DECK 2 / MASTER segments, then the Mix slider.
- **Three effect boxes.** Each has:
  - "Effect n" and "deck A FX pad n";
  - the effect selector ("Select effect…" when empty);
  - an **ON/OFF button**, Sound, lit and reading ON when on, reading OFF at rest. Not a switch. Owner: "Only change should be that the on off should be a button not a switch."
  - its slider.
- **Sliders:** the green fill (`--mx-slider-fill` #5d7238) fills the **full height** of the track up to the handle. This applies to Mix and every effect slider.
- **Saving effects:** the loaded effects are saved within a second of a change (like settings), so they survive a power cut. Stock Mixxx saves them only at a clean quit.
- **Depth and mix still reset at start** because of the Starlight's stock script. That is not changed in this climb (Starlight study option D was not requested).

### s10 Settings › Playback
- No change.
- The tempo range is saved: this is the build C repair.

### s11 Settings › Media (`mockups/m-settings-media.png`)
- **Header:** "Settings", the hint "Every change saves within a second.", and the close ✕ at the right.
- **Rail:** PLAYBACK, INTERFACE, MEDIA, ADVANCED.
- **Rows:**
  - Scan bar: SHOW / HIDE.
  - RAM cache: OFF / 512 / 1024.
  - Eject: ON/OFF toggle, "Safe eject on this card".
  - **New row "Plugging in a drive": ASK / AUTO LOAD, default ASK.** The subtext reads "ASK shows a small strip with LOAD and DISMISS. AUTO LOAD opens the drive at once."
    - ASK is today's bottom ping with LOAD and DISMISS.
    - AUTO LOAD opens the drive at once, with no ping.

### s12 Settings › Interface (`mockups/m-settings-interface.png`), with the "later" items the owner moved in
- **Rows:**
  - Desktop bar: the button "Show top bar".
  - Deck time: ELAPSED / REMAINING.
  - **Brightness:** a slider with a % readout, driving the screen backlight. On the test card that is `/sys/class/backlight/10-0045`, 0-255.
  - **Night dim:** OFF / ON. It drops the screen to a low level for dark rooms.
  - **CPU readout:** SHOW / HIDE. It shows or hides the CPU % at the top right.
- Advanced: no change.
- **Not in this build (owner: "at a later date"):** light mode, colour schemes, larger text, waveform colour style.

### s13 Media page (`mockups/m-media.png`)
- **Header:**
  - The title "USB & Media";
  - next to it, the filter segments **ALL** (default), **READY** and **IN USE**;
  - the close ✕ at the right.
- **One row per drive:**
  - the USB icon, the name, the size, and a state chip (READY, IN USE or EJECTING);
  - **OPEN** with the browse (list) icon, neutral;
  - **EJECT** with the eject (⏏) icon, Caution.
  - Owner: "Keep the eject logo on the buttons. I liked it." and "browse logo too on the open too".
- **Scrolling:** the list scrolls when several drives are in, and its scroll bar shows.
- **Removed:**
  - no deck or song lines, and no explanatory paragraph;
  - **no COPY TO PI** (the copy to Pi memory on load is automatic, owner Q3).
- **Footer:** one short line, "**N tracks** playing from Pi memory", shown when any tracks are.
- **What OPEN does:** it reads the drive, which is the same as LOAD on the plug-in strip: its rekordbox export, or its folders if it has none. It then switches to Tracks. After that the button reads **BROWSE**.

## 2a. Owner changes after build C (2026-11-18)

The owner saw build C on the test card and changed four things. They win over everything above. They go into build D (the owner approved a 5th pi-gen run for them).

- **Fonts:** all fonts go back to build B (section 1, Fonts). The owner's words: "I want you to fold in reverting the font as you continue", then the choice "All fonts back to build B".
- **Edit sources, child rows (s5):** This Pi's own lists (Tracks, Playlists, Crates, Auto DJ) and More's (for example iTunes, Serato) come back as **indented rows under their source**, each with only an **ON/OFF** toggle, in the agreed row style. Build B had them; the mockup shows only the top rows. Owner's choice: "Bring the rows back".
- **Loop panel with the desktop top bar shown (s2):** while the top bar is shown (the Mixxx window is 800×444), the loop panel's rows get shorter so that all four rows (two rows of sizes, ½ and ×2, EXIT LOOP and RELOOP) fit. This is below the 48 px touch minimum, by the owner's choice ("Shorter rows then"). At 800×480 nothing changes.
- **Build D** fixes three build C deviations that need app code, by the owner's yes:
  - ★ shows the saved start in Edit sources, and the Sources menu's current-row edge follows the source in view (the owner's saved start, `RekordboxFeature`, showed no ★, and Tracks opened on Mixxx's Rekordbox info page).
  - With Sources open, the narrowed table fits its columns (TITLE, ARTIST, BPM, KEY) in its width, as `m-sources-top.png` draws it: no sideways scroll bar.
  - OPEN on the Media page switches to Tracks (s13).

## 2b. Owner decisions after council round 2 (2026-11-18)

The owner read council round 2 (all three seats at 6) and decided the following. These decisions win over everything above.

- **Accepted as they are (not deviations from now on):**
  - **Edit sources scrolls by its 24 px bar, and by a drag that starts on a row's button.** A drag that starts on a row's text does not scroll. Owner: "1 is not necessary".
  - **With Sources open over Load sample, the narrowed Samples table may cut its last header** ("DURATIO"). Owner: "3 is not necessary".
  - **The Clear samples list scrolls by its bar only.** Owner: "4 is not necessary".
- **Build E (the 6th pi-gen run), for:**
  - **The accent edge after OPEN or BROWSE.** After a drive is opened from the Media page, the Sources menu's current-row edge (and the place inside it) is on that drive. Owner: "do 2".
  - **Clearing a playing pad.** CLEAR (n) **stops a ticked pad that is playing, then empties it**, so every ticked pad goes empty. Owner's choice: "Stop it, then clear".
- **Skin repairs from council round 2,** each to match the mockups:
  - the REC dot drawn red;
  - EXIT LOOP and RELOOP at rest while a loop is on, as `m-loop.png` draws them;
  - the table's alternate rows in the agreed surface colours, as `m-tracks.png` and `m-loadsample.png` draw them.
- **The owner session** (the Starlight session and the samples power-off test) runs after build E is on the card.

## 2c. Owner decisions after build E (2026-11-18)

- **RELOOP** starts the loop at once and is then disabled while the loop runs, so it never shows its pressed look. This is build B's behaviour, and it stays. Owner: "that is correct".
- **One column setup for every source** (build F, the 7th pi-gen run, approved by the owner). Owner: "I want to keep the column setup across the different source menus and have it be saved after edit like the settings."
  - Which columns show, their order and their widths are shared by every track table: This Pi, playlists and crates, each drive's rekordbox lists, folders, History, and the Samples table in Load sample. A column a source does not have is skipped there.
  - Sorting stays per list, as now.
  - A change (show or hide a column, move it, resize it) is saved within one second, like the settings, and is kept over `kill -9` and a power cut.
  - The narrowed table with Sources open still fits its columns (spec 2a). Fitted widths are never saved; closing Sources or Edit sources always brings back the shared full widths.
- **The FX pads** already follow the owner's model, so nothing changes: deck A's FX pads drive FX 1 and deck B's drive FX 2, whichever unit the screen shows. Each unit has its own DECK 1 / DECK 2 / MASTER route on screen.
- **Order of work:** build F, then the owner's Starlight and power-off session on build F, then council round 3.

## 2d. Owner decisions after council round 3 (2026-11-20)

- **Accepted as they are:**
  - **Narrowed tables may cut header letters.** With Sources open, any narrowed track table may cut a header's letters (for example "BPI" under a sort arrow, "TITLI"). Owner: "I'm okay with the cut columns." This extends 2b's "DURATIO" item to every narrowed table.
  - **★ on a switched-off row** in Edit sources is drawn disabled, because Mixxx cannot start Tracks at a source that is off.
- **Built as the mockups draw them** (build I, the 10th pi-gen run, approved by the owner):
  - **The Sources side menu's shadow** (`m-sources-top.png`, `m-sources-sub.png`). It is painted as a plain gradient, not Qt's costly blur effect. The orchestrator first expected this to be skin only. Builder S8 found that a skin widget over the table would block taps on its rows and scroll bar, because the skin cannot make a widget pass touches through. So build I adds a small native piece: a touch-transparent strip placed against the menu's left edge. The skin paints it with the mockup's values (`box-shadow: -8px 0 24px rgba(0,0,0,.5)`, about 40 px wide).
  - **A "Tracks" row inside a rekordbox drive** (`m-sources-sub.png`). It lists every track in the drive's export, next to the playlists and folders that Mixxx's reader already lists.
  - **USB chip and ping timing:**
    - A drive reads **IN USE** only once a track or sample from it is loaded on a deck or pad (the eject rule's "loaded means in use"). After OPEN or BROWSE alone, it still reads **READY**.
    - The plug-in ping (ASK: LOAD and DISMISS) also shows while the Media page is open.
- **Also fixed** (skin, all three seats): the table header's empty area takes the agreed header colour, so a TITLE edge dragged narrower no longer shows a light-grey strip.

## 2e. Owner decisions after council round 4 (2026-11-20)

- **Kept as they are on the card** (the owner saw the mockup-against-card crops and said no to changing them):
  - **The Sources menu rows** stay in Pioneered's capitals ("TRACKS", playlist names in capitals). The mockups' mixed case is not built.
  - **The USB chip** keeps build I's look: the lit fill and 2 px border while the Media page is open, and READY `#7cc58a`, IN USE `#86c0d8`.
  - **The plug-in ping** keeps its 15 s from the plug-in. Opening the Media page does not restart it. Owner: "Keep as is."
- **Build J (the 11th pi-gen run), for:**
  - **The quit crash** (wave J1). Owner: "Fix this only" (of the three build J items first proposed).
  - **After an eject, the stale table goes.** The Tracks table stops showing the ejected drive's rows, and ☰ opens at the top level. Owner: "Let just land on the top menu instead" (instead of This Pi › Tracks).
  - **☰ after OPEN opens inside the drive,** with the current-row edge on Tracks, as `m-sources-sub.png` draws it. Owner: "Open the drive." This replaces 2b's top-level case.
- **USB ports are never switched off** by tests or tools. Re-plugs in tests are done by hand.

## 3. Not part of build C

- **G5 extras:** the owner suggested an outline in the fill colour when active and thinner outlines on inactive buttons, then said "What we have now is acceptable". This is noted only.
- **Later:** light mode, colour schemes, larger text, waveform colour style.
- **Starlight study option D** (FX depth and mix over a restart).
