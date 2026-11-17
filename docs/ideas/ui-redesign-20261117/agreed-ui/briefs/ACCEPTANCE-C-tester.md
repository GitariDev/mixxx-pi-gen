# Build C acceptance on the test card (tester brief)

You are the **acceptance tester** (Claude Opus 5.5, medium effort). Build C (`135a4bf`, 48 patches) is already installed in place on the 64 GB test card; the orchestrator did that and its spec-conformance shots (`deploy/ui-redesign-20261117/acceptance-C/conformance/`). You run the functional checks and write the evidence. **You change no code and no repo file** except your evidence folder `deploy/ui-redesign-20261117/acceptance-C/` (untracked). No commits.

Repo: `/Users/gitaritirima/Documents/Workspace/Personal Projects/mixxx-pi-gen`. Spec: `docs/ideas/ui-redesign-20261117/agreed-ui/AGREED-UI-SPEC.md` (read sections 0-2). Plan: `docs/ideas/UI-REDESIGN-PLAN-20261117.md` (R-items, section 10.1, section 12). Build B's acceptance, for method and the old FAIL list: `deploy/ui-redesign-20261117/acceptance-B/ACCEPTANCE.md`.

## Card, tools and safety

- Pi at 192.168.68.56, **test card only**. Tools: `deploy/recovery-20261116-fixes/tools/` — `pi.sh` (pinned SSH), `ui.sh OUT.png 'tap X Y' 'drag X1 Y1 X2 Y2' 'hold X Y S' 'sleep S'`, `shot.sh OUT.png`, `card/mixxxctl.sh` (start: `./pi.sh 'bash -s -- start' < card/mixxxctl.sh`). Screen 800×480, origin top-left. **Confirm coordinates on a shot before each tap.** After every boot: `./pi.sh 'cat > /tmp/vtouch.py && chmod +x /tmp/vtouch.py' < vtouch.py`.
- Quit Mixxx with Ctrl+Q: `WAYLAND_DISPLAY=wayland-1 XDG_RUNTIME_DIR=/run/user/1000 wtype -M ctrl q`, then wait until `pgrep -x mixxx` is empty. Back up `~/.mixxx/mixxx.log*` to `/home/pi/uiC-20261118/tester/logs/<tag>/` before each restart (Mixxx keeps only 10).
- Thermal: the fan is unplugged. Log `vcgencmd measure_temp` and `vcgencmd get_throttled` at least every 15 min to `acceptance-C/thermal-log.txt`. Pause playback above 80 °C.
- **MANTACORE** (`/media/pi/MANTACORE`, hub port 2) stays off: its port is disabled (`/sys/bus/usb/devices/1-1:1.0/1-1-port2/disable` = 1). After every boot write 1 there again (`echo 1 | sudo -n tee …`). Never enable it.
- **GANDER1** is the owner's spare stick for the drive checks: 3.8 GB FAT, a rekordbox export (196 tracks), on hub **port 1** (`1-1-port1`), mounted read-write at `/media/pi/GANDER1`. **Never write, move or delete a file on it** (open, browse and play only). Clean ejects through the Media page are allowed. To plug it back in after a clean eject (only when it is not mounted), toggle its port: `echo 1 | sudo -n tee /sys/bus/usb/devices/1-1:1.0/1-1-port1/disable; sleep 2; echo 0 | sudo -n tee …/1-1-port1/disable`. Never toggle a port while a drive on it is mounted. Never touch port 3 (the Starlight).
- Controlled media (`/etc/mixpi/controlled-media`) stays absent. The eject gate `/etc/mixpi/media-eject` stays as it is.
- The owner's state was saved before you start: `/home/pi/uiC-20261118/owner-state/` (`mixxx.cfg`, `samplers.xml`, `effects.xml`, `soundconfig.xml`). Never touch `soundconfig.xml` (stereo: Master 1-2, Headphones 3-4).
- Never type a password; `sudo -n` works.

## Hit map on build C (centres, 800×480)

- **Top bar (y 24):** DECKS 42, TRACKS 126, FX 204, SAMPLER 288, USB chip 527, REC 649, gear 717.
- **Decks transport (y 452):** KEY 24, Q 72, SYNC 126, LOOP 186, CUE 254, ▶ 346; deck 2 is +400.
- **Tool panel:** LOOP (180,72), JUMP (276,72), CUES (372,72), CUES-tab CLEAR (695,72), ✕ (772,72). Loop sizes x 67/200/333/467/600/733 at y 124 (1/32…1) and y 176 (2…64). ½ (200,228), ×2 (600,228), EXIT LOOP (200,280), RELOOP (600,280). Jump buttons x 177/290/403/516/629/742 at y 134 and 196. Cue tiles x 106/302/498/694 at y 141 and 217.
- **Tracks:** search (344,72), ✎ (716,72), ☰ (772,72). Rows from y 149, 34 px apart. Bottom row: LOAD 1 (42,452), CUE (298,452), ▶ (366,452); LOAD 2 (442,452), CUE (698,452), ▶ (766,452).
- **Sources menu** (x 480-800 under the header): ✕ (772,72). Top level: BACK (533,122), EDIT (629,122), rows x 640 at y 174, 226, 278, 330, 382, 434 (52 px). Inside a source: BACK (533,122) and the place name. **Edit sources** (full screen): DONE (692,74), ✕ (772,74); rows y 126 + 52·n; ★ x 40, ON/OFF x 553, UP x 645, DOWN x 741.
- **Sampler:** + LOAD SAMPLE (88,72), CLEAR SAMPLES… (255,72). Pad k spans x 200(k-1)…200k; ▶ TRIGGER at +51, ■ STOP at +149, y 172 (A1-A4) and y 276 (B1-B4). An empty pad opens Load sample for that pad. **Clear samples popover:** ✕ (607,156), first row's tick box (190,206), CANCEL (439,322), CLEAR (n) (567,322). Known: only the tick box toggles, and the list shows one row at a time with a scroll bar.
- **Load sample:** search (527,72), ✕ (772,72), SAMPLES (70,124), SOURCES… (202,124), rows from y 205, LOAD TO PAD… (667,448). **Choose pad:** ✕ (728,92), tiles x ≈140/314/487/660 at y 176 and 280.
- **FX:** FX 1 (106,76), FX 2 (302,76); routes DECK 1 · PAD 4 (116,132), DECK 2 (236,132), MASTER (356,132); effect selectors x ≈90/357/624 at y 218; ON/OFF (224,218), (491,218), (758,218); effect sliders y 266.
- **Settings:** ✕ (772,72); rail PLAYBACK (100,122), INTERFACE (100,174), MEDIA (100,226), ADVANCED (100,278). Media: Scan bar SHOW (462,129) / HIDE (557,129); RAM cache OFF (462,195) / 512 (558,195) / 1024 (654,195); Eject (indicator, not pressable); ASK (462,327) / AUTO LOAD (562,327). Interface: SHOW TOP BAR (507,132); ELAPSED (466,198) / REMAINING (566,198); Brightness slider x 420-732 at y 264 (readout 772); Night dim OFF (466,330) / ON (562,330); CPU readout SHOW (466,396) / HIDE (562,396).
- **Media page:** chip (527,24) opens it. ALL (176,74), READY (244,74), IN USE (315,74), ✕ (772,74). Row 1: OPEN (159,205), EJECT (327,205). Eject sheet: CANCEL (391,353), EJECT (569,353). Insert ping: DISMISS (594,455), LOAD (730,455). Safe strip OK ≈ (747,452).
- **Scan bar** (y 376-424): HIDE (648,400), CANCEL (752,400).

## Checks (PASS / FAIL / BLOCKED, with the evidence file for each)

### 1. Build B's five FAILs, re-run
1. R-2: the Media page opened from DECKS has no waveform drawn over it.
2. R-4: the Media page is styled (dark, as `m-media.png`).
3. R-13: Settings › Playback › Tempo range 10%: `RateRangePercent 10` in `mixxx.cfg` within 1 s; `pkill -KILL -x mixxx`; start; still 10%. Restore 8%.
4. R-10: ☰ → EDIT → Edit sources shows DONE and ✕; switch one source off (the row dims), move one row UP once, DONE returns to the menu; Ctrl+Q and start: both kept. Then restore the order and switches exactly (shots before and after).
5. F-14: three fresh starts; each time Settings › Interface › SHOW TOP BAR once: never "Top bar was not confirmed". With the bar shown (800×444), open the loop panel and shoot it (owner question: the last row may be cut). Hide the bar again.

### 2. Build B's six BLOCKED (drive), now on GANDER1
1. R-4: chip states (READY; IN USE while a deck plays a GANDER1 track; EJECTING; SAFE TO REMOVE); Media page row; OPEN reads the drive and switches to Tracks, then the row reads BROWSE.
2. R-5 and the **Q3 10 % gate**: Settings › Media › RAM cache 1024, restart, two decks playing GANDER1 tracks for 5 min; then RAM cache OFF, restart, the same 5 min. Sample the CPU readout (`[MixPi],audio_load_percent`, the top-right number) every 10 s and count underruns (the log, or Mixxx's counter). **Pass if the RAM-copy average ≤ 1.10 × the OFF average.** Restore RAM cache to the owner's value (1024). Then: eject GANDER1 while deck 1 plays a GANDER1 track → deck 1 keeps playing; the footer reads "1 track playing from Pi memory" (or N); load another track on deck 1 → the copy goes (`ls /dev/shm/mixpi-track-cache`).
3. R-6: eject with nothing loaded → the green Safe to remove strip → no I/O error in `dmesg`; port toggle → READY again.
4. R-9: GANDER1's row in Sources; inside it: "GANDER1 › rekordbox", BACK, lists with counts (check one count against the list's length).
5. R-15: no udiskie pop-up on insert.
6. R-20 storm: five cycles of eject (clean, through the Media page) then port toggle; sway and Mixxx survive; `journalctl` shows no sway crash.
7. U-8: with ASK, re-plug → the bottom ping "GANDER1 plugged in" with LOAD and DISMISS (DISMISS once, LOAD once); with AUTO LOAD (Settings › Media), re-plug → the drive opens with no ping. `drive_insert` in `mixxx.cfg` within 1 s. Restore ASK.
8. U-10: filters ALL, READY, IN USE with GANDER1 READY and IN USE; one row per drive; no COPY TO PI; the footer only while tracks play from Pi memory.

### 3. The agreed UI, functional (U-1 to U-10)
- U-2: ½ halves the chosen loop size, ×2 doubles it, EXIT LOOP exits, RELOOP re-enters.
- U-3: ▶ on the Tracks bottom row plays and pauses each deck.
- U-4: ☰ becomes the red ✕ in the same spot; BACK at the top level closes the menu; a long list shows the 24 px bar and scrolls by drag without opening a row; a leaf pick shows its tracks; from Load sample → SOURCES… → a list → back on Load sample. **Known defect to document:** no row in Edit sources shows ★ with the owner's saved start (`SidebarDefaultSource RekordboxFeature`), and the menu's accent edge sits on This Pi. Record what you see; then try ★ on Samples → restart → Tracks starts at Samples; ★ on the GANDER1 row → restart with GANDER1 in → Tracks opens GANDER1. Restore at the end (step 5 below).
- U-5: ▶ TRIGGER plays a pad (lit while it plays), ■ STOP stops it. Load test samples to pads 3 and 4 from the Samples folder. **Samples over a reboot:** `sudo systemctl reboot` with pads 3-4 loaded → after boot they are still loaded (and pads 1-2), and the previous Mixxx log ends with "shutdown complete with code 0" (R-14). Then CLEAR SAMPLES… → tick pads 3 and 4 → CLEAR (2) → pads 3-4 empty, pads 1-2 untouched, `samplers.xml` updated, and the sample files byte-identical (sha256 before and after). Also: a ticked pad that is playing is not cleared (Mixxx refuses) — record what the screen shows. Power-off (full shutdown) needs the owner to power the Pi on again: leave it for the owner session.
- U-6: Load sample shows SAMPLES and SOURCES… only.
- U-7: ON/OFF lights ON and turns the effect on; slider fills full height; **effects saved within a second**: load ECHO in FX 1 effect 2, wait 1 s, `pkill -KILL -x mixxx`, check `~/.mixxx/effects.xml` holds it, start, effect 2 is still ECHO. Ten effect changes while two decks play: 0 new underruns.
- U-9: the Brightness slider changes `/sys/class/backlight/10-0045/brightness` (log the values) and the % readout; saved as `Backlight` in `mixxx.cfg`; Night dim ON → 26, OFF → back to the slider level; CPU readout HIDE hides the top-right CPU %, SHOW brings it back. All within 1 s in `mixxx.cfg`.
- Settings save timing: three changes, each in `mixxx.cfg` within 1 s (mtime).

### 4. Holdout and performance (R-22 step 6)
30 s REC gives WAV + CUE; F-1, F-2, F-3, F-4 (86 ± 2 px per beat at 102 BPM, fresh start, paused shot), F-5, F-7, F-8, F-9, F-11; two pads load and trigger; a 4-beat loop set and exited; one effect on; CPU readout and underruns with both decks playing plus one effect, against build 2 (3-4 %, 0); `get_throttled` 0x0.

### 5. Restore the owner's state at the end
Ctrl+Q. Copy back `mixxx.cfg`, `samplers.xml` and `effects.xml` from `/home/pi/uiC-20261118/owner-state/` (never `soundconfig.xml`), check their sha256, and start Mixxx. Then set the panel to 255 (Brightness 100 %), Night dim OFF, CPU SHOW, top bar hidden. Load "Your Body" (Biscits) to deck 1 and "YOU'RE THE ONE" (KAYTRANADA / Syd) to deck 2 from This Pi › Tracks, both paused, deck 1 SYNC off, deck time REMAINING. GANDER1 plugged in and READY, MANTACORE's port disabled. Mixxx on DECKS. Shoot the final state.

## Report
`deploy/ui-redesign-20261117/acceptance-C/ACCEPTANCE.md`: one table per section with PASS / FAIL / BLOCKED and the evidence file. For each FAIL, an exact repro: the taps with coordinates, what was expected, and what was seen. Shots go in `acceptance-C/shots/`, logs in `acceptance-C/logs/`. Reply with the counts, each FAIL in one line, the Q3 gate numbers (both averages, the ratio and the underruns), and the final state.
