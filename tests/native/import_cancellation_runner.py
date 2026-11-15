"""Exercise extracted production imports with real QtConcurrent, Kaitai and SQLite.

Reconstructs the current recipe outside the repository, and
injects deterministic scheduling barriers at (not instead of) checkpoints.
"""
import argparse
import os
from pathlib import Path
import platform
import re
import struct
import subprocess
import tempfile

from library_interface_runner import reconstruct, populate_pinned, source_pin, qt_flags, qt_environment

ROOT = Path(__file__).resolve().parents[2]
PATCH = ROOT / 'stage3/01-install-packages/files/mixxx-import-cancellation.patch'


def function(source, signature):
    start = source.index(signature)
    return source[start:source.index('\n}\n', start) + 3]


def fixture(directory):
    page_size = 4096
    header = bytearray(page_size)
    struct.pack_into('<7I', header, 0, 0, page_size, 3, 4, 0, 1, 0)
    track = bytearray(136)
    for offset, value in ((8, 44100), (16, 1024), (48, 1411), (52, 1),
                          (56, 12000), (72, 1)):
        struct.pack_into('<I', track, offset, value)
    struct.pack_into('<HHH', track, 80, 2026, 16, 30)
    for index in range(21):
        text = {14: '/analysis.DAT', 17: 'Cancellation fixture',
                19: 'fixture.wav', 20: '/fixture.wav'}.get(index, '').encode()
        struct.pack_into('<H', track, 94 + index * 2, len(track))
        track.extend(bytes([(len(text) + 1) * 2 + 1]) + text)
    name = b'Playlist'
    tree = struct.pack('<5I', 0, 0, 0, 1, 0) + bytes([(len(name) + 1) * 2 + 1]) + name
    pages = []
    for page_index, (kind, row) in enumerate(((0, track), (7, tree),
                                               (8, struct.pack('<3I', 1, 1, 1))), 1):
        struct.pack_into('<4I', header, 28 + (page_index - 1) * 16,
                         kind, 0, page_index, page_index)
        page = bytearray(page_size)
        struct.pack_into('<6I', page, 0, 0, page_index, kind, page_index + 1, 1, 0)
        page[24:27] = (1 | (1 << 13)).to_bytes(3, 'little')
        page[27] = 0x24
        page[40:40 + len(row)] = row
        struct.pack_into('<HHH', page, page_size - 6, 0, 1, 0)
        pages.append(page)
    destination = directory / 'PIONEER/rekordbox/export.pdb'
    destination.parent.mkdir(parents=True)
    destination.write_bytes(header + b''.join(pages))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', action='store_true')
    parser.add_argument('--holdout', action='store_true')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='mixpi-import-cancel-') as temporary:
        target = Path(temporary)
        names, _ = reconstruct(target)
        commit = source_pin()
        print('SOURCE_PIN', commit, 'BASE_PATCHES', len(names), flush=True)
        candidate = Path(os.environ.get('MIXXX_IMPORT_CANCELLATION_PATCH', PATCH)).resolve()
        if not args.baseline and candidate.name not in names:
            subprocess.run(['git', 'apply', '--check', str(candidate)], cwd=target, check=True)
            subprocess.run(['git', 'apply', str(candidate)], cwd=target, check=True)
        source = (target / 'src/library/rekordbox/rekordboxfeature.cpp').read_text()
        unit = (ROOT / 'tests/native/import_cancellation_test.cpp.in').read_text()
        if args.baseline:
            unit = '#define BASELINE 1\n' + unit
            (target / 'src/library/rekordbox/importoperation.h').write_text(
                'namespace mixxx::rekordbox { struct ImportOperation { void cancel() {} }; }')
        populate_pinned(target, ('src/library/treeitem.h', 'src/library/treeitem.cpp',
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
        definitions = source[source.index('enum class IDForColor'):source.index('struct memory_cue_loop_t')]
        definitions += source[source.index('bool createLibraryTable('):source.index('// This function is executed')]
        parser_body = source[source.index('template<typename Base, typename T>'):source.index('void setHotCue(')]
        for encoding in ('Le', 'Be'):
            parser_body = parser_body.replace(function(parser_body, 'QString fromUtf16' + encoding + 'String('), '')
        labels = ['start', 'transaction', 'before-parse', 'after-parse', 'table-order',
                  'table', 'before-page', 'after-page', 'row-group', 'row',
                  'precommit', 'tree', 'tree-child', 'tree-track']
        if not args.baseline:
            assert parser_body.count('operation->checkpoint();') == len(labels)
        for label in labels:
            parser_body = parser_body.replace('operation->checkpoint();',
                'testCheckpoint(operation, "' + label + '");', 1)
        methods = '\n'.join(function(source, signature) for signature in (
            'std::function<void()> RekordboxFeature::openRemovableDeviceAsync(',
            'void RekordboxFeature::activateChild(', 'void RekordboxFeature::onTracksFound(',
            'RekordboxFeature::~RekordboxFeature('))
        methods = methods.replace('return parseDeviceDB(pool, item, operation);',
            'auto result = parseDeviceDB(pool, item, operation); testBarrier("after-commit"); return result;')
        methods = methods.replace('return parseDeviceDB(pool, item);',
            'auto result = parseDeviceDB(pool, item); testBarrier("after-commit"); return result;')
        identity = (target / 'src/library/rekordbox/sourceidentity.h').read_text()
        cache = (target / 'src/library/rekordbox/sourcecache.h').read_text()
        matchers = function(identity, 'inline bool sameSourceRevision(')
        matchers += function(cache, 'inline bool matchesCachedSource(')
        matchers += function(cache, 'inline int cachedSourceRow(')
        unit = unit.replace('PRODUCTION_MATCHERS', matchers)
        unit = unit.replace('PRODUCTION_PARSER', definitions + parser_body)
        unit = unit.replace('PRODUCTION_METHODS', methods)
        (target / 'test.cpp').write_text(unit)
        fixture(target / 'A')
        fixture(target / 'B')
        runtime = target / 'kaitaistream.cpp'
        runtime.write_bytes((target / 'lib/kaitai/kaitai/kaitaistream.cpp').read_bytes())
        command = ['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                   '-Wno-unused-parameter', '-Wno-unused-variable',
                   '-Wno-unused-but-set-variable', '-Wno-pessimizing-move',
                   '-Wno-switch',
                   '-DKS_STR_ENCODING_ICONV', '-D__LINUX__']
        command += ['-I' + str(target / 'src'), '-I' + str(target / 'lib/rekordbox-metadata'),
                    '-I' + str(target / 'lib/kaitai'), str(target / 'test.cpp'),
                    str(target / 'src/library/treeitem.cpp'),
                    str(target / 'lib/rekordbox-metadata/rekordbox_pdb.cpp'),
                    str(runtime), '-o', str(target / 'test'),
                    *qt_flags(('QtCore', 'QtGui', 'QtSql', 'QtConcurrent'))]
        if platform.system() == 'Darwin':
            command += ['-liconv', '-Wno-unnecessary-virtual-specifier']
        print('COMPILE', repr(command), flush=True)
        subprocess.run(command, check=True, timeout=90)
        environment = qt_environment()
        subprocess.run([str(target / 'test'), str(target),
                        'holdout' if args.holdout else 'main'], env=environment,
                       check=True, timeout=90)


if __name__ == '__main__':
    main()
