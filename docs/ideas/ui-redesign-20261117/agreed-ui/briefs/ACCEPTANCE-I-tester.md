# Build I acceptance on the test card (tester brief)

Read `ACCEPTANCE-G-tester.md` and `ACCEPTANCE-H-tester.md` (same folder) first. Their card rules, safety rules, tools, hit map and the save and restore of the owner's state hold. That includes MANTACORE's port staying enabled and MANTACORE read-only (do not browse it), and GANDER1 read only (clean ejects and re-plugs by port toggle are allowed).

Build I (59 patches) is installed in place. Spec 2d lists what it changes from build H:
- the table header's empty area;
- the Sources menu shadow;
- a Tracks row inside a rekordbox drive;
- the USB chip's IN USE timing and the plug-in ping on the Media page.

The builders' Pi checks are in `docs/ideas/UI-REDESIGN-RESULTS-20261117.md` (waves H1 and I1-I3) and in the brief folder.

Write your evidence in `deploy/ui-redesign-20261117/acceptance-I/` (`ACCEPTANCE.md`, `shots/`, `logs/`, `pairs/`) and on the card in `/home/pi/uiI-20261120/tester/`. You change no code and make no commits.

## Checks (PASS / FAIL / BLOCKED, with evidence)
1. **Header empty area.** On This Pi › Tracks, drag TITLE's edge from (424,108) to (364,108).
   - The header's right end (about x 715-775) is `#1d222a`, not `#efefef`.
   - Nothing is saved: `title` stays 160 and the `mixxx.cfg` mtime is unchanged.
   - Drag it back.
2. **Menu shadow.** ☰ (772,72) on This Pi › Tracks. On a `#1d222a` row near y 110, left of the menu edge, sample:
   - about `#14181d` at x 479, `#161a21` at 472, `#191e25` at 464 and `#1b2028` at 456;
   - no change at x ≤ 420 or from x 480 rightwards.
   - Check the same inside a source.
   - A tap on a table row at about (470,186) still selects it, and the table's scroll bar under the strip still drags.
   - Close the menu: the strip is gone.
3. **Tracks row inside a drive.** TRACKS › ☰ › GANDER1. The header reads "GANDER1 › rekordbox" and the first row is "Tracks": music-note icon, no › and no count. The drive's real playlists and folders follow, as on build H.
   - Tap Tracks: the table lists every track in the export, more than any single playlist.
   - Sort by a column, LOAD 1, and load a sample to a pad from ✎. Then unload both, so the owner's pads stay as they were.
   - Reopen ☰: the edge is on Tracks.
   - OPEN from the Media page, then ☰: the edge is on Tracks.
   - The narrowed table fits.
   - Eject GANDER1 with the Tracks list showing: a clean eject, and the menu goes back to This Pi. Re-plug it by port toggle.
4. **IN USE timing.**
   - With decks and pads holding nothing from GANDER1, OPEN it: the chip reads **READY**, also after browsing a playlist.
   - Load a GANDER1 track to a deck: **IN USE** within about 1 s, and the Media page row and the IN USE filter agree.
   - Load a This Pi track over it: **READY**.
   - Load a GANDER1 sample to a free pad: **IN USE**. Clear that pad (tick only it): **READY**.
5. **Ping on the Media page.**
   - With Settings › MEDIA › "Plugging in a drive" on ASK, open the Media page and re-plug GANDER1 by port toggle. The ping (LOAD and DISMISS) shows at y 424-480 over the page, and the page's GANDER1 row appears, READY.
   - DISMISS leaves the page.
   - Re-plug again and LOAD: the drive opens on Tracks.
   - With the ping up and the page closed, open the page: the ping stays on top.
   - Leave the setting as the owner had it. If you change it to AUTO LOAD to check that case, set it back.
6. **The earlier fixes still hold:**
   - acceptance H checks 1-4 (TITLE stays 160, Load sample and folders fit, no start-up write);
   - a re-shown column keeps its width;
   - the overview strip moves on both decks;
   - OPEN switches to Tracks, and the ★ start opens GANDER1.
7. **Smoke:**
   - a setting and an effect each saved within 1 s;
   - two decks plus one effect for 2 minutes: the CPU readout and the underrun counter (build H: 4.00 %, 0);
   - `throttled=0x0`.
8. **Pairs for the council:** mockup on the left, build I on the right. Use the side-by-side tool at `/private/tmp/claude-501/-Users-gitaritirima-Documents-Workspace-Personal-Projects-mixxx-pi-gen/01eef82b-7712-44de-b076-2782a69dc643/scratchpad/pair`: `pair LEFT RIGHT OUT "mockup" "build I"`. Make the pairs for:
   - `m-sources-top.png`: ☰ on This Pi › Tracks;
   - `m-sources-sub.png`: inside GANDER1 › rekordbox;
   - `m-media.png`: the Media page;
   - `m-tracks.png`.

   Save them in `acceptance-I/pairs/`.

## Restore at the end
Do the same as acceptance H. Then:
- "Your Body" on deck 1 and "YOU'RE THE ONE" on deck 2, both paused, with deck 1 SYNC off;
- Mixxx on DECKS, with the top bar hidden;
- MANTACORE's port enabled;
- the owner's settings, pads and FX as they were.

## Report
Write `acceptance-I/ACCEPTANCE.md`. Reply with:
- the counts;
- each FAIL in one line;
- the sampled shadow pixels;
- the chip states at each step;
- the CPU and underrun numbers;
- any owner activity;
- the final state.
