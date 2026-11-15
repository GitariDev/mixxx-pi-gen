"""Actual SidebarModel/TreeItemModel TUs; feature/config/app-shell substitutes only."""
import argparse
import hashlib
import os
from pathlib import Path
import platform
import re
import subprocess
import tempfile

from library_interface_runner import ROOT, reconstruct, populate_pinned, qt_flags, qt_environment, moc_path

def method(source, signature):
    start = source.index(signature)
    brace = source.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end] + '\n'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', action='store_true')
    parser.add_argument('--holdout', action='store_true')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='mixpi-source-model-') as temporary:
        target = Path(temporary)
        reconstruct(target)
        populate_pinned(target, ['src/' + name for name in ('library/treeitem.h', 'library/treeitem.cpp',
                     'library/treeitemmodel.h', 'library/treeitemmodel.cpp',
                     'util/make_const_iterator.h')])
        stubs = target / 'stubs'
        (stubs / 'library').mkdir(parents=True)
        (stubs / 'util').mkdir()
        (stubs / 'library/libraryfeature.h').write_text(
            (ROOT / 'tests/native/library_interface_sources_stubs.h').read_text())
        (stubs / 'util/assert.h').write_text(
            '#pragma once\n#include <cassert>\n'
            '#define DEBUG_ASSERT(value) assert(value)\n'
            '#define VERIFY_OR_DEBUG_ASSERT(value) if (!(value))\n')
        (stubs / 'util/cmdlineargs.h').write_text(
            '#pragma once\nstruct CmdlineArgs { static CmdlineArgs& Instance() '
            '{ static CmdlineArgs instance; return instance; } '
            'bool getDeveloper() const { return false; } };\n')
        library = (target / 'src/library/library.cpp').read_text()
        signatures = ['void Library::applySidebarSourceOrder()',
                      'void Library::saveSidebarSourceOrder(',
                      'void Library::applySidebarSourceVisibility()',
                      'void Library::showSidebarSourcesMenu()',
                      'void Library::onSkinLoadFinished()']
        (target / 'library_order_methods.h').write_text(
            '\n'.join(method(library, signature) for signature in signatures))
        if args.baseline:
            preimage = ROOT / 'deploy/recovery-20261111/native-completion-slice/sources/stack-preimage'
            for name in ('sidebarmodel.h', 'sidebarmodel.cpp'):
                (target / 'src/library' / name).write_bytes(
                    (preimage / 'src/library' / name).read_bytes())
        command = ['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror']
        command += ['-I' + str(stubs), '-I' + str(target / 'src'), '-I' + str(target)]
        if args.baseline:
            command += ['-DSOURCE_ORDER_BASELINE']
        for header, output in (
                (target / 'src/library/sidebarmodel.h', target / 'src/library/moc_sidebarmodel.cpp'),
                (target / 'src/library/treeitemmodel.h', target / 'src/library/moc_treeitemmodel.cpp'),
                (stubs / 'library/libraryfeature.h', target / 'moc_feature.cpp')):
            subprocess.run([moc_path(), str(header), '-o', str(output)],
                           check=True, timeout=20)
        command += [str(ROOT / 'tests/native/library_interface_sources_test.cpp'),
                    str(target / 'src/library/sidebarmodel.cpp'),
                    str(target / 'src/library/treeitem.cpp'),
                    str(target / 'src/library/treeitemmodel.cpp'),
                    str(target / 'moc_feature.cpp'), '-o', str(target / 'test')]
        for source in sorted(target.rglob('*')):
            if source.is_file():
                print('INPUT', source.relative_to(target),
                      hashlib.sha256(source.read_bytes()).hexdigest(), flush=True)
        command += qt_flags(('QtCore', 'QtGui', 'QtWidgets', 'QtTest'))
        print('COMMAND', repr(command), flush=True)
        subprocess.run(command, check=True, timeout=90)
        environment = qt_environment()
        subprocess.run([str(target / 'test'), *(['holdout'] if args.holdout else [])],
                       env=environment, check=True, timeout=30)


if __name__ == '__main__':
    main()
