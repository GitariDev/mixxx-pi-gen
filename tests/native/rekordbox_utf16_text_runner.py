"""Wave J8: build and run the rekordbox text fixture.

The actual rekordbox import (parseDeviceDB with Kaitai and SQLite, getText,
and the actual fromUtf16LeString with QTextCodec) reads a synthetic export.pdb
whose strings use every DeviceSQL kind: short ASCII, long ASCII and long
UTF-16LE, with accented and non-Latin text (see
rekordbox_utf16_text_test.cpp.in). One track's folder and file are stored
decomposed (NFD) on the fixture drive while the export holds them precomposed
(NFC), as rekordbox writes them.

--kaitai none builds the Kaitai runtime with the string mode Mixxx's
CMakeLists.txt gives it (KS_STR_ENCODING_NONE); --kaitai iconv builds it as
the other native fixtures do (KS_STR_ENCODING_ICONV). --baseline leaves
mixxx-rekordbox-utf16-text.patch out, to show the checks fail without it.

--export PATH --playlist NAME reads a real export.pdb instead and lists that
playlist's entries as Mixxx's import stores them; nothing is written to the
given file, and nothing of it is kept.
"""
import argparse
from pathlib import Path
import platform
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unicodedata

sys.path.insert(0, str(Path(__file__).resolve().parent))
from library_interface_runner import (reconstruct, populate_pinned, pinned_bytes, qt_flags, qt_environment,
                                      PATCH_DIR)

ROOT = Path(__file__).resolve().parents[2]
PATCH_NAME = 'mixxx-rekordbox-utf16-text.patch'
FEATURE = 'src/library/rekordbox/rekordboxfeature.cpp'
PAGE = 4096
LONG_TITLE = 'An Extended Instrumental Version Of A Very Long Song Title That Needs More Than One Hundred And Twenty Seven Bytes To Be Stored'
LONG_ARTIST = 'The Orchestra With A Name Long Enough To Need The Long ASCII Kind And The Far Name Offset In Its Artist Row Too, Written Out In Full'
LONG_ACCENTED = 'Ça va très bien, merci beaucoup, à bientôt — une chanson française au titre très, très long pour l’exemple'

# rb_id: (title, artist, album, genre, key, comment, path)
TRACKS = {
    1: ('Strawberry Letter 23', 'Shuggie Otis', 'Freedom Flight', 'R&B', 'Am', '',
        '/Contents/Shuggie Otis/Freedom Flight/Strawberry Letter 23.flac'),
    2: (LONG_TITLE, LONG_ARTIST, 'Long ASCII Album', 'Jazz', 'Dm', 'a plain comment',
        '/Contents/' + LONG_ARTIST + '/Long ASCII Album/' + LONG_TITLE + '.flac'),
    3: ('El Hijo De Mamá', 'Ralfi Pagan', 'Ralfi Pagán', 'Latinalainen musiikki', 'Cm', 'Mamá ✓',
        '/Contents/Ralfi Pagan/Ralfi Pagán/35 - El Hijo De Mamá.flac'),
    4: ('Technicolor', 'Sunni Colón', 'Satin Psicodelic', 'R&B', 'Am', '',
        '/Contents/Sunni Colón/Satin Psicodelic/05 - Technicolor.flac'),
    5: ('Anbessa', 'Akalé Wubé, Manu Dibango', 'Sost', 'African', 'Gm', '',
        '/Contents/Akalé Wubé, Manu Dibango/Sost/19 - Anbessa.flac'),
    6: ('東京の夜', 'Καλημέρα Ορχήστρα', 'Привет мир', 'አፍሪካ', 'F♯m', '🎧 ночь',
        '/Contents/Καλημέρα Ορχήστρα/Привет мир/01 - 東京の夜 🎧.flac'),
    7: (LONG_ACCENTED, 'Zaz', 'Français', 'Chanson', 'E', LONG_ACCENTED,
        '/Contents/Zaz/Français/' + LONG_ACCENTED + '.flac'),
    8: ('Gentleman', 'Fela Kuti', 'Gentleman', 'Afrobeat', 'Em', '',
        '/Contents/Fela Kuti/Gentleman/Gentleman.flac'),
    9: ('Ölümsüz Aşk', 'Barış Manço', 'Dönence', 'Anadolu Rock', 'Bm', '',
        '/Contents/Barış Manço/Dönence/Ölümsüz Aşk.mp3'),
}
# Stored decomposed on the drive (a Mac can store names so).
DECOMPOSED = {4}
# (id, parent, sort order, folder, name, track ids)
PLAYLISTS = [(1, 0, 0, True, 'Práctica Listas', []),
             (2, 1, 0, False, 'Día Soleado ☀', [3, 6, 9]),
             (3, 0, 1, False, 'Sunny Day Vibes(Neo/RnB/Afro/Rap)', [1, 2, 4, 5, 7, 8])]


def text(value):
    """A DeviceSQL string: short ASCII, long ASCII or long UTF-16LE, as rekordbox picks."""
    if value.isascii():
        data = value.encode('ascii')
        if len(data) <= 126:
            return bytes([(len(data) + 1) * 2 + 1]) + data
        return b'\x40' + struct.pack('<H', len(data) + 4) + b'\x00' + data
    data = value.encode('utf-16-le')
    return b'\x90' + struct.pack('<H', len(data) + 4) + b'\x00' + data


def kind(value):
    return text(value)[0]


def track_row(track_id, ids, strings):
    row = bytearray(136)
    for offset, value in ((8, 44100), (16, 1024), (48, 1411), (52, track_id), (56, 12000),
                          (32, ids['key']), (60, ids['genre']), (64, ids['album']),
                          (68, ids['artist']), (72, track_id)):
        struct.pack_into('<I', row, offset, value)
    struct.pack_into('<HHH', row, 80, 2026, 16, 30)
    for index in range(21):
        struct.pack_into('<H', row, 94 + index * 2, len(row))
        row.extend(text(strings.get(index, '')))
    return bytes(row)


def export(drive):
    """export.pdb with one row per page; the pages of a table are chained."""
    names = {column: {} for column in ('artist', 'album', 'genre', 'key')}
    for _, (title, artist, album, genre, key, comment, path) in sorted(TRACKS.items()):
        for column, value in (('artist', artist), ('album', album), ('genre', genre), ('key', key)):
            names[column].setdefault(value, len(names[column]) + 1)
    artists = []
    for value, number in names['artist'].items():
        if value == LONG_ARTIST:
            # A far name offset (subtype 0x64), as rekordbox writes long names.
            artists.append(struct.pack('<HHIBBH', 0x64, 0, number, 3, 0, 12) + text(value))
        else:
            artists.append(struct.pack('<HHIBB', 0x60, 0, number, 3, 10) + text(value))
    tracks = []
    for number, (title, artist, album, genre, key, comment, path) in sorted(TRACKS.items()):
        ids = {'artist': names['artist'][artist], 'album': names['album'][album],
               'genre': names['genre'][genre], 'key': names['key'][key]}
        strings = {14: f'/PIONEER/USBANLZ/P{number:03}/ANLZ0000.DAT', 16: comment, 17: title,
                   19: path.rsplit('/', 1)[1], 20: path}
        tracks.append(track_row(number, ids, strings))
    tables = [(0, tracks),
              (1, [struct.pack('<I', number) + text(value) for value, number in names['genre'].items()]),
              (2, artists),
              (3, [struct.pack('<HHIIIIBB', 0x80, 0, 0, 0, number, 0, 3, 22) + text(value)
                   for value, number in names['album'].items()]),
              (5, [struct.pack('<II', number, number) + text(value) for value, number in names['key'].items()]),
              (7, [struct.pack('<5I', parent, 0, order, list_id, int(folder)) + text(name)
                   for list_id, parent, order, folder, name, _ in PLAYLISTS]),
              (8, [struct.pack('<3I', entry, track_id, list_id)
                   for list_id, _, _, _, _, ids in PLAYLISTS
                   for entry, track_id in enumerate(ids, 1)])]
    total_rows = sum(len(rows) for _, rows in tables)
    header = bytearray(PAGE)
    struct.pack_into('<7I', header, 0, 0, PAGE, len(tables), total_rows + 1, 0, 1, 0)
    pages = []
    index = 1
    for table, (page_type, rows) in enumerate(tables):
        struct.pack_into('<4I', header, 28 + table * 16, page_type, 0, index, index + len(rows) - 1)
        for row in rows:
            assert len(row) < PAGE - 64
            page = bytearray(PAGE)
            struct.pack_into('<6I', page, 0, 0, index, page_type, index + 1, 1, 0)
            page[24:27] = (1 | (1 << 13)).to_bytes(3, 'little')
            page[27] = 0x24
            page[40:40 + len(row)] = row
            struct.pack_into('<HHH', page, PAGE - 6, 0, 1, 0)
            pages.append(page)
            index += 1
    destination = drive / 'PIONEER/rekordbox/export.pdb'
    destination.parent.mkdir(parents=True)
    destination.write_bytes(header + b''.join(pages))
    lines = []
    for number, values in sorted(TRACKS.items()):
        path = values[6]
        if number in DECOMPOSED:
            path = unicodedata.normalize('NFD', path)
            assert path != values[6]
            lines.append('\t'.join(('ONDRIVE', str(number), path)))
        audio = drive / path.lstrip('/')
        audio.parent.mkdir(parents=True, exist_ok=True)
        audio.write_bytes(b'RIFF')
        lines.append('\t'.join(('TRACK', str(number), *values)))
    paths = {}
    for list_id, parent, _, _, name, _ in PLAYLISTS:
        paths[list_id] = paths.get(parent, '') + '-->' + name
        lines.append('\t'.join(('PLAYLIST', paths[list_id])))
    # Every DeviceSQL kind is in the export.
    kinds = {kind(value) for values in TRACKS.values() for value in values}
    assert 0x40 in kinds and 0x90 in kinds and any(value & 1 for value in kinds), kinds
    return '\n'.join(lines) + '\n'


def kaitai_mode(target, choice):
    if choice == 'iconv':
        return 'KS_STR_ENCODING_ICONV'
    cmake = target / 'CMakeLists.txt'
    source = cmake.read_text() if cmake.exists() else pinned_bytes('CMakeLists.txt').decode()
    return re.search(r'target_compile_definitions\(Kaitai PRIVATE (KS_STR_ENCODING_\w+)\)', source)[1]


def unit(target, baseline, export_mode):
    source = (target / FEATURE).read_text()
    definitions = source[source.index('enum class IDForColor'):source.index('struct memory_cue_loop_t')]
    definitions += source[source.index('bool createLibraryTable('):source.index('// This function is executed')]
    parser = source[source.index('template<typename Base, typename T>'):source.index('void setHotCue(')]
    template = (ROOT / 'tests/native/rekordbox_utf16_text_test.cpp.in').read_text()
    template = template.replace('PRODUCTION_PARSER', definitions + parser)
    if baseline:
        template = '#define BASELINE 1\n' + template
    if export_mode:
        template = '#define EXPORT_MODE 1\n' + template
    return template


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', action='store_true')
    parser.add_argument('--kaitai', choices=('none', 'iconv'), default='none')
    parser.add_argument('--export', help='a real export.pdb to read')
    parser.add_argument('--playlist', default='Sunny Day Vibes(Neo/RnB/Afro/Rap)')
    arguments = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='mixpi-rekordbox-text-') as temporary:
        target = Path(temporary)
        names, _ = reconstruct(target, exclude=(PATCH_NAME,) if arguments.baseline else ())
        if not arguments.baseline and PATCH_NAME not in names:
            subprocess.run(['git', 'apply', str(PATCH_DIR / PATCH_NAME)], cwd=target, check=True)
        mode = kaitai_mode(target, arguments.kaitai)
        print('PATCHES', len(names), 'BASELINE' if arguments.baseline else PATCH_NAME, 'KAITAI', mode, flush=True)
        populate_pinned(target, ('src/library/treeitem.h', 'src/library/treeitem.cpp',
                                 'src/util/make_const_iterator.h', 'src/library/queryutil.h',
                                 'src/util/color/rgbcolor.h', 'src/util/optional.h',
                                 'src/library/rekordbox/importoperation.h',
                                 'lib/rekordbox-metadata/rekordbox_pdb.cpp',
                                 'lib/rekordbox-metadata/rekordbox_pdb.h',
                                 'lib/kaitai/kaitai/kaitaistream.h', 'lib/kaitai/kaitai/kaitaistruct.h',
                                 'lib/kaitai/kaitai/exceptions.h', 'lib/kaitai/kaitai/custom_decoder.h',
                                 'lib/kaitai/kaitai/kaitaistream.cpp'))
        (target / 'src/util/assert.h').write_text(
            '#pragma once\n#include <cassert>\n#define DEBUG_ASSERT(value) assert(value)\n'
            '#define VERIFY_OR_DEBUG_ASSERT(value) if (!(value))\n')
        (target / 'test.cpp').write_text(unit(target, arguments.baseline, bool(arguments.export)))
        if arguments.export:
            destination = target / 'media/IXIAN/PIONEER/rekordbox/export.pdb'
            destination.parent.mkdir(parents=True)
            shutil.copyfile(arguments.export, destination)
        else:
            (target / 'expected.tsv').write_text(export(target / 'media/ACCENTS'), encoding='utf-8')
        runtime = target / 'kaitaistream.cpp'
        runtime.write_bytes((target / 'lib/kaitai/kaitai/kaitaistream.cpp').read_bytes())
        command = ['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                   '-Wno-unused-parameter', '-Wno-unused-variable', '-Wno-unused-function',
                   '-Wno-unused-but-set-variable', '-Wno-pessimizing-move', '-Wno-switch',
                   '-D' + mode,
                   '-I' + str(target / 'src'), '-I' + str(target / 'lib/rekordbox-metadata'),
                   '-I' + str(target / 'lib/kaitai'), str(target / 'test.cpp'),
                   str(target / 'src/library/treeitem.cpp'),
                   str(target / 'lib/rekordbox-metadata/rekordbox_pdb.cpp'),
                   str(runtime), '-o', str(target / 'test'),
                   *qt_flags(('QtCore', 'QtGui', 'QtSql', 'QtCore5Compat'))]
        if platform.system() == 'Darwin':
            command += ['-liconv', '-Wno-unnecessary-virtual-specifier']
        print('COMPILE', repr(command), flush=True)
        subprocess.run(command, check=True, timeout=180)
        run = [str(target / 'test'), str(target)]
        if arguments.export:
            run.append(arguments.playlist)
        result = subprocess.run(run, env=qt_environment(), timeout=120)
        return result.returncode


if __name__ == '__main__':
    sys.exit(main())
