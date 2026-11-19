"""Spec 2d: build and run the drive Tracks row fixture.

The actual rekordbox import (parseDeviceDB with Kaitai and SQLite) reads a
fake export.pdb on a fake drive: seven tracks, three of them in no playlist.
The actual RekordboxFeature methods (activateChild, onTracksFound,
onRekordboxDevicesFound, and the new addDriveTracksRows and
selectShownDriveTracks) run on stand-ins for the sidebar model, the track
table model and the track collection. --baseline leaves
mixxx-drive-tracks-row.patch out, to show the checks fail without it.
"""
import argparse
from pathlib import Path
import platform
import re
import struct
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from library_interface_runner import (reconstruct, populate_pinned, qt_flags, qt_environment,
                                      mixxx_images_rcc, PATCH_DIR)

ROOT = Path(__file__).resolve().parents[2]
PATCH_NAME = 'mixxx-drive-tracks-row.patch'
TRACKS_ICON = 'images/library/ic_library_tracks.svg'
PAGE = 4096

# id, file. Tracks 5, 6 and 7 are in no playlist.
TRACKS = [(index, f'/Contents/Artist {index}/track {index}.wav') for index in range(1, 8)]
# id, parent, sort order, folder, name, track ids
LISTS = [(1, 0, 0, False, 'Warm-up', [1, 2, 3]),
         (2, 0, 1, True, 'Sets', []),
         (3, 2, 0, False, 'Peak time', [3, 4])]


def function(source, signature):
    start = source.index(signature)
    return source[start:source.index('\n}\n', start) + 3]


def text(value):
    data = value.encode()
    return bytes([(len(data) + 1) * 2 + 1]) + data


def track_row(track_id, path):
    row = bytearray(136)
    for offset, value in ((8, 44100), (16, 1024), (48, 1411), (52, track_id),
                          (56, 12000), (72, track_id)):
        struct.pack_into('<I', row, offset, value)
    struct.pack_into('<HHH', row, 80, 2026, 16, 30)
    strings = {14: f'/PIONEER/USBANLZ/P{track_id:03}/ANLZ0000.DAT', 17: f'Track {track_id}',
               19: path.rsplit('/', 1)[1], 20: path}
    for index in range(21):
        struct.pack_into('<H', row, 94 + index * 2, len(row))
        row.extend(text(strings.get(index, '')))
    return bytes(row)


def export(drive):
    """export.pdb with one row per page; the pages of a table are chained."""
    tables = [(0, [track_row(track_id, path) for track_id, path in TRACKS]),
              (7, [struct.pack('<5I', parent, 0, order, list_id, int(folder)) + text(name)
                   for list_id, parent, order, folder, name, _ in LISTS]),
              (8, [struct.pack('<3I', entry, track_id, list_id)
                   for list_id, _, _, _, _, tracks in LISTS
                   for entry, track_id in enumerate(tracks, 1)])]
    total = sum(len(rows) for _, rows in tables)
    header = bytearray(PAGE)
    struct.pack_into('<7I', header, 0, 0, PAGE, len(tables), total + 1, 0, 1, 0)
    pages = []
    index = 1
    for table, (kind, rows) in enumerate(tables):
        struct.pack_into('<4I', header, 28 + table * 16, kind, 0, index, index + len(rows) - 1)
        for row in rows:
            page = bytearray(PAGE)
            struct.pack_into('<6I', page, 0, 0, index, kind, index + 1, 1, 0)
            page[24:27] = (1 | (1 << 13)).to_bytes(3, 'little')
            page[27] = 0x24
            page[40:40 + len(row)] = row
            struct.pack_into('<HHH', page, PAGE - 6, 0, 1, 0)
            pages.append(page)
            index += 1
    destination = drive / 'PIONEER/rekordbox/export.pdb'
    destination.parent.mkdir(parents=True)
    destination.write_bytes(header + b''.join(pages))
    for _, path in TRACKS:
        audio = drive / path.lstrip('/')
        audio.parent.mkdir(parents=True, exist_ok=True)
        audio.write_bytes(b'RIFF')


def unit(target, baseline):
    source = (target / 'src/library/rekordbox/rekordboxfeature.cpp').read_text()
    definitions = source[source.index('enum class IDForColor'):source.index('struct memory_cue_loop_t')]
    definitions += source[source.index('bool createLibraryTable('):source.index('// This function is executed')]
    parser = source[source.index('template<typename Base, typename T>'):source.index('void setHotCue(')]
    for encoding in ('Le', 'Be'):
        parser = parser.replace(function(parser, 'QString fromUtf16' + encoding + 'String('), '')
    helpers = ''
    methods = ['void RekordboxFeature::activateChild(', 'void RekordboxFeature::onTracksFound(',
               'void RekordboxFeature::onRekordboxDevicesFound(']
    if not baseline:
        helpers = function(source, 'bool isDriveTracksRow(') + function(
            source, 'std::unique_ptr<TreeItem> driveTracksRow(')
        methods += ['void RekordboxFeature::addDriveTracksRows(',
                    'void RekordboxFeature::selectShownDriveTracks(']
    template = (ROOT / 'tests/native/drive_tracks_row_test.cpp.in').read_text()
    feature = (target / 'src/library/libraryfeature.cpp').read_text()
    template = template.replace('PRODUCTION_ICON_PATH', re.search(
        r'^const QString kIconPath = (.*);$', feature, re.MULTILINE).group(1))
    identity = (target / 'src/library/rekordbox/sourceidentity.h').read_text()
    cache = (target / 'src/library/rekordbox/sourcecache.h').read_text()
    template = template.replace('PRODUCTION_MATCHERS', function(identity, 'inline bool sameSourceRevision(') +
                                function(cache, 'inline bool matchesCachedSource('))
    template = template.replace('PRODUCTION_PARSER', definitions + parser + helpers)
    template = template.replace('PRODUCTION_METHODS', '\n'.join(function(source, name) for name in methods))
    if baseline:
        template = '#define BASELINE 1\n' + template
    return template


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', action='store_true')
    arguments = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='mixpi-drive-tracks-') as temporary:
        target = Path(temporary)
        names, _ = reconstruct(target, exclude=(PATCH_NAME,) if arguments.baseline else ())
        if not arguments.baseline and PATCH_NAME not in names:
            subprocess.run(['git', 'apply', str(PATCH_DIR / PATCH_NAME)], cwd=target, check=True)
        print('PATCHES', len(names), 'BASELINE' if arguments.baseline else PATCH_NAME, flush=True)
        populate_pinned(target, ('src/library/treeitem.h', 'src/library/treeitem.cpp',
                                 'src/library/libraryfeature.cpp',
                                 'src/util/make_const_iterator.h', 'src/library/queryutil.h',
                                 'src/util/color/rgbcolor.h', 'src/util/optional.h',
                                 'lib/rekordbox-metadata/rekordbox_pdb.cpp',
                                 'lib/rekordbox-metadata/rekordbox_pdb.h',
                                 'lib/kaitai/kaitai/kaitaistream.h', 'lib/kaitai/kaitai/kaitaistruct.h',
                                 'lib/kaitai/kaitai/exceptions.h', 'lib/kaitai/kaitai/custom_decoder.h',
                                 'lib/kaitai/kaitai/kaitaistream.cpp'))
        (target / 'src/util/assert.h').write_text(
            '#pragma once\n#include <cassert>\n#define DEBUG_ASSERT(value) assert(value)\n'
            '#define VERIFY_OR_DEBUG_ASSERT(value) if (!(value))\n')
        (target / 'test.cpp').write_text(unit(target, arguments.baseline))
        export(target / 'media/GANDER1')
        runtime = target / 'kaitaistream.cpp'
        runtime.write_bytes((target / 'lib/kaitai/kaitai/kaitaistream.cpp').read_bytes())
        command = ['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                   '-Wno-unused-parameter', '-Wno-unused-variable', '-Wno-unused-function',
                   '-Wno-unused-but-set-variable', '-Wno-pessimizing-move', '-Wno-switch',
                   '-DKS_STR_ENCODING_ICONV', '-D__LINUX__',
                   '-I' + str(target / 'src'), '-I' + str(target / 'lib/rekordbox-metadata'),
                   '-I' + str(target / 'lib/kaitai'), str(target / 'test.cpp'),
                   str(target / 'src/library/treeitem.cpp'),
                   str(target / 'lib/rekordbox-metadata/rekordbox_pdb.cpp'),
                   str(runtime), '-o', str(target / 'test'),
                   *qt_flags(('QtCore', 'QtGui', 'QtSql', 'QtConcurrent'))]
        if platform.system() == 'Darwin':
            command += ['-liconv', '-Wno-unnecessary-virtual-specifier']
        print('COMPILE', repr(command), flush=True)
        subprocess.run(command, check=True, timeout=120)
        environment = qt_environment()
        environment['MIXPI_MIXXX_RCC'] = str(mixxx_images_rcc(target, [TRACKS_ICON]))
        result = subprocess.run([str(target / 'test'), str(target)], env=environment, timeout=90)
        return result.returncode


if __name__ == '__main__':
    sys.exit(main())
