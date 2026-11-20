"""Spec 2e (build J, wave J4): build and run the eject fixture.

The actual RekordboxFeature::onRekordboxDevicesFound (with the actual table
helpers and clearDeviceTables) removes a drive that went away; with
mixxx-eject-top-menu.patch, the actual releaseRemovedDrives, showsDriveList
and RekordboxPlaylistModel::releasePlaylist empty the table when the list it
shows is that drive's. They run on stand-ins for the sidebar model, the
table model and the track collection (tests/native/eject_top_menu_test.cpp.in).
--baseline leaves mixxx-eject-top-menu.patch (and what needs it) out, to show
the checks fail without it.
"""
import argparse
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from library_interface_runner import reconstruct, populate_pinned, qt_flags, qt_environment

ROOT = Path(__file__).resolve().parents[2]
PATCH_NAME = 'mixxx-eject-top-menu.patch'
FEATURE = 'src/library/rekordbox/rekordboxfeature.cpp'
HEADER = 'src/library/rekordbox/rekordboxfeature.h'


def function(source, signature):
    start = source.index(signature)
    return source[start:source.index('\n}\n', start) + 3]


def inline_method(source, signature):
    """A method defined in its class (four spaces in), up to its closing brace."""
    start = source.index('    ' + signature)
    return source[start:source.index('\n    }\n', start) + 7]


def unit(target, baseline):
    source = (target / FEATURE).read_text()
    header = (target / HEADER).read_text()
    helpers = ['bool createLibraryTable(', 'bool createPlaylistsTable(', 'bool createPlaylistTracksTable(',
               'bool dropTable(', 'void clearDeviceTables(']
    methods = ['void RekordboxFeature::onRekordboxDevicesFound(']
    release = ''
    if not baseline:
        helpers.append('bool showsDriveList(')
        methods.append('void RekordboxFeature::releaseRemovedDrives(')
        release = inline_method(header, 'void releasePlaylist() {')
    template = (ROOT / 'tests/native/eject_top_menu_test.cpp.in').read_text()
    template = template.replace('PRODUCTION_HELPERS', '\n'.join(function(source, name) for name in helpers))
    template = template.replace('PRODUCTION_METHODS', '\n'.join(function(source, name) for name in methods))
    template = template.replace('PRODUCTION_RELEASE', release)
    if baseline:
        template = '#define BASELINE 1\n' + template
    return template


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', action='store_true')
    arguments = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='mixpi-eject-top-menu-') as temporary:
        target = Path(temporary)
        names, _ = reconstruct(target, exclude=(PATCH_NAME,) if arguments.baseline else ())
        if not arguments.baseline and PATCH_NAME not in names:
            subprocess.run(['git', 'apply', str(ROOT / 'stage3/01-install-packages/files' / PATCH_NAME)],
                           cwd=target, check=True)
        print('PATCHES', len(names), 'BASELINE' if arguments.baseline else PATCH_NAME, flush=True)
        populate_pinned(target, ('src/library/treeitem.h', 'src/library/treeitem.cpp',
                                 'src/util/make_const_iterator.h', 'src/library/queryutil.h'))
        (target / 'src/util/assert.h').write_text(
            '#pragma once\n#include <cassert>\n#define DEBUG_ASSERT(value) assert(value)\n'
            '#define VERIFY_OR_DEBUG_ASSERT(value) if (!(value))\n')
        (target / 'test.cpp').write_text(unit(target, arguments.baseline))
        command = ['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter',
                   '-Wno-unused-function', '-Wno-unused-variable', '-Wno-unused-but-set-variable',
                   '-I' + str(target / 'src'), str(target / 'test.cpp'),
                   str(target / 'src/library/treeitem.cpp'), '-o', str(target / 'test'),
                   *qt_flags(('QtCore', 'QtGui', 'QtSql'))]
        if platform.system() == 'Darwin':
            command += ['-Wno-unnecessary-virtual-specifier']
        print('COMPILE', repr(command), flush=True)
        subprocess.run(command, check=True, timeout=120)
        result = subprocess.run([str(target / 'test')], env=qt_environment(), timeout=60)
        return result.returncode


if __name__ == '__main__':
    sys.exit(main())
