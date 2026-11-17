"""R-8 native part and R-9 step 3: build and run the sample_browser or the
source_groups fixture.

The actual Library methods are taken from the patched library.cpp; the actual
SidebarModel, TreeItemModel and libraryinterface.h are compiled as they are.
Substitutes: the features (named trees), the controls and the track list.
"""
import argparse
import hashlib
from pathlib import Path
import subprocess
import tempfile

from library_interface_runner import ROOT, reconstruct, populate_pinned, qt_flags, qt_environment, moc_path

SAMPLE_METHODS = ('void Library::setupSampleBrowser()',
                  'void Library::leaveSampleMode(',
                  'void Library::noteBrowsePlaceShown()',
                  'QModelIndex Library::sourceRow(',
                  'QList<QModelIndex> Library::driveRows()',
                  'LibraryInterface::BrowsePlace Library::sampleSourcePlace(',
                  'void Library::showBrowsePlace(')


def method(source, signature):
    start = source.index(signature)
    brace = source.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end] + '\n'


def stubs(target):
    stubs = target / 'stubs'
    for name in ('library', 'util', 'preferences', 'control', 'widget'):
        (stubs / name).mkdir(parents=True, exist_ok=True)
    (stubs / 'library/libraryfeature.h').write_text(
        (ROOT / 'tests/native/sample_browser_stubs.h').read_text())
    (stubs / 'control/controlobject.h').write_text(
        (ROOT / 'tests/native/sample_browser_controls.h').read_text())
    (stubs / 'util/assert.h').write_text(
        '#pragma once\n#include <cassert>\n'
        '#define DEBUG_ASSERT(value) assert(value)\n'
        '#define VERIFY_OR_DEBUG_ASSERT(value) if (!(value))\n')
    (stubs / 'util/cmdlineargs.h').write_text(
        '#pragma once\nstruct CmdlineArgs { static CmdlineArgs& Instance() '
        '{ static CmdlineArgs instance; return instance; } '
        'bool getDeveloper() const { return false; } };\n')
    (stubs / 'preferences/configobject.h').write_text(
        '#pragma once\n#include <QString>\nstruct ConfigKey {\n    QString key;\n'
        '    ConfigKey(QString group, QString name) : key(group + "/" + name) {}\n};\n')
    return stubs


def build(target, test, extra_methods=(), defines=()):
    """Compiles TEST with the actual sidebar model; returns the program."""
    populate_pinned(target, ['src/' + name for name in ('library/treeitem.h', 'library/treeitem.cpp',
                     'library/treeitemmodel.h', 'library/treeitemmodel.cpp',
                     'library/sidebarmodel.h', 'library/sidebarmodel.cpp',
                     'util/make_const_iterator.h')])
    include = stubs(target)
    library = (target / 'src/library/library.cpp').read_text()
    (target / 'library_sample_methods.h').write_text(
        '\n'.join(method(library, signature) for signature in SAMPLE_METHODS + tuple(extra_methods)))
    table = (target / 'src/widget/wtracktableview.cpp').read_text()
    start = table.index('    std::function<void()> loadToPad;\n')
    end = table.index('    m_pLibraryActions = LibraryInterface::actionsMenu(', start)
    (target / 'load_to_pad.inc').write_text(table[start:end])
    mocs = [(target / 'src/library/sidebarmodel.h', target / 'moc_sidebarmodel.cpp'),
            (target / 'src/library/treeitemmodel.h', target / 'src/library/moc_treeitemmodel.cpp'),
            (include / 'library/libraryfeature.h', target / 'moc_feature.cpp')]
    for header, output in mocs:
        subprocess.run([moc_path(), str(header), '-o', str(output)], check=True, timeout=20)
    # sidebarmodel.cpp includes its moc next to itself.
    (target / 'src/library/moc_sidebarmodel.cpp').write_bytes((target / 'moc_sidebarmodel.cpp').read_bytes())
    command = ['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror', *defines,
               '-I' + str(include), '-I' + str(target / 'src'), '-I' + str(target),
               str(test), str(target / 'src/library/sidebarmodel.cpp'),
               str(target / 'src/library/treeitem.cpp'), str(target / 'src/library/treeitemmodel.cpp'),
               str(target / 'moc_feature.cpp'), '-o', str(target / 'test')]
    for source in sorted(target.rglob('*')):
        if source.is_file() and source.suffix in ('.h', '.cpp', '.inc'):
            print('INPUT', source.relative_to(target), hashlib.sha256(source.read_bytes()).hexdigest(), flush=True)
    command += qt_flags(('QtCore', 'QtGui', 'QtWidgets', 'QtTest'))
    print('COMMAND', repr(command), flush=True)
    subprocess.run(command, check=True, timeout=120)
    return target / 'test'


def main():
    parser = argparse.ArgumentParser()
    # Evidence only: the same checks without mixxx-sample-browser.patch must fail to build.
    parser.add_argument('--without-sample-browser', action='store_true')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='mixpi-sample-browser-') as temporary:
        target = Path(temporary)
        reconstruct(target, exclude=('mixxx-sample-browser.patch',) if args.without_sample_browser else ())
        program = build(target, ROOT / 'tests/native/sample_browser_test.cpp')
        subprocess.run([str(program)], env=qt_environment(), check=True, timeout=60)


if __name__ == '__main__':
    main()
