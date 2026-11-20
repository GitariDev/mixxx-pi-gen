# Wave J8, builder N-J8 (native): drive tracks with accented file names load

Read `docs/ideas/ui-redesign-20261117/agreed-ui/BUILDER-RULES-C.md` first; it is part of this brief. Then read `AGREED-UI-SPEC.md` 2e.

**No design of your own; where the spec is silent, build B stays.** This wave changes no UI.

Base: `feat/pi-performance-target` at `5c96f5a` (64 patches; the last is `mixxx-drive-track-cache.patch`). You are the only builder running. Never edit an existing Mixxx patch. Make `mixxx-rekordbox-utf16-text.patch`, placed last in `MIXXX_PATCHES`, with any prerequisites it needs (for example `mixxx-drive-track-cache.patch` if you touch the same file).

## The fault (owner: "Build j8", 2026-11-20)
- Wave J7 parsed the owner's copied `export.pdb` (IXIAN, playlist "Sunny Day Vibes(Neo/RnB/Afro/Rap)", playlist id 5, 42 entries). Three entries store their strings as DeviceSQL long UTF-16 strings, because they hold accented characters: entry 15 "Technicolor", entry 21 "El Hijo De Mamá", entry 29 "Anbessa".
- Mixxx's rekordbox reader decodes those strings as garbage, so the path does not match the file on the drive, and the row will not load (and its title or artist may show garbled).
- **Find the cause first and write it in your report.** A likely one (check it): the reader in `src/library/rekordbox/` converts `device_sql_long_utf16le`/`utf16be` strings with the wrong byte order or length (rekordbox writes these as UTF-16 little-endian; the length field counts the header bytes too). Check every text field the reader takes from `export.pdb` (path, title, artist, album, genre, key, label, comment, playlist and folder names, file name), and any other place in the rekordbox code that converts DeviceSQL strings.

## Evidence (untracked, in the main checkout)
`deploy/ui-redesign-20261117/owner-ixian-20261120/`: `export.pdb`, `exportLibrary.db`, `mixxx.log`, `shots/`. **The export is the owner's private music data:** use it only on the Mac and on VM b, never commit it, never send it anywhere, and delete the copy from the VM when done. Committed tests must use a synthetic export or synthetic strings you build in the test.

## What to build
- Every DeviceSQL string kind (short ASCII, long ASCII, long UTF-16) decodes to the right text, accented and non-Latin characters included.
- The three entries' paths match the files on the drive, so the rows load; their titles and artists read correctly.
- ASCII-only tracks (all of GANDER1, most of IXIAN) decode exactly as before.
- Keep J7's cache rebuild, J6's sort, the clean eject, the ★ start, the Tracks row and the shared columns. Never write to a drive.

## Files you own
- the new patch;
- new tests `tests/test_rekordbox_utf16_text.py` and `tests/native/rekordbox_utf16_text_*`;
- in the Mixxx source: `src/library/rekordbox/*` (the reader and, if needed, its Kaitai-generated parser) and new files.

No skin files and no sidebar or media files. Do not edit the registries; give the orchestrator your registration lines.

## Checks
- **Native fixture:** a synthetic export (or synthetic DeviceSQL strings fed to the reader) with short ASCII, long ASCII and long UTF-16 strings, accented and non-Latin text included: every field decodes right. Show the fixture failing without your patch.
- **The owner's export (not committed):** on VM b, run the real import on the copied `export.pdb` and list the 42 Sunny Day Vibes entries with their decoded paths and titles. The three entries above read correctly and the other 39 are unchanged from J7's list.
- The Mac suite: `MIXXX_TEST_SOURCE=/tmp/mixpi-actions-routing-objects-20261115 PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests` (`test_chroot_runtime`'s 5 s timeout can trip under load; rerun it alone).
- The full native gate on VM `b`, 0 skips, with your registration lines applied:
  - run it with `~/.config/mixpi-lima-b/vm-native.sh uiJ8-nj8-20261120 <your worktree> gate`;
  - never use `limactl`. Keep at least 24 GB free in the VM, and run `fstrim` after cleanup.
- **Never touch the Raspberry Pi or any drive.**
- Give the orchestrator a Pi check with coordinates: IXIAN (read only) › Sunny Day Vibes › load each of the three tracks to a deck. Re-plugs are done by the owner's hand; never switch a USB port off.
