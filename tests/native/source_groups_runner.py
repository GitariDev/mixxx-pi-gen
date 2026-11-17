"""Agreed UI s5: build and run the source_groups fixture.

As sample_browser_runner.py --source-groups (the actual Library methods from
the patched library.cpp, the real WLibrarySidebar, SidebarModel and
TreeItemModel), plus what mixxx-sources-menu-fixes.patch adds:
Library::showStartTile (★ on the drive row and on Samples), and the actual
rekordbox playlist tree builder (buildPlaylistTree with its table helpers,
from the patched rekordboxfeature.cpp) on an in-memory SQLite database, so
the drive's lists carry the counts the feature makes.
"""
from pathlib import Path
import re

import sample_browser_runner as SAMPLE
from library_interface_runner import ROOT, reconstruct, populate_pinned, qt_flags, qt_environment

METHODS = SAMPLE.GROUP_METHODS + ('bool Library::showStartTile(',)


def rekordbox_tree(target):
    """The production playlist tree builder and what it needs, as one include."""
    populate_pinned(target, ['src/library/queryutil.h', 'src/library/dao/playlistdao.h'])
    feature = (target / 'src/library/rekordbox/rekordboxfeature.cpp').read_text()
    query = (target / 'src/library/queryutil.h').read_text()
    dao = (target / 'src/library/dao/playlistdao.h').read_text()
    parts = ['#pragma once', '#include <QMap>', '#include <QSqlDatabase>', '#include <QSqlError>',
             '#include <QSqlQuery>', '#include <QSqlRecord>', '#include <QtDebug>', '#include <memory>',
             '#include "library/rekordbox/importoperation.h"', '#include "library/treeitem.h"']
    parts.append(re.search(r'^#define LOG_FAILED_QUERY.*\n.*\n', query, re.MULTILINE).group(0))
    parts.append(re.search(r'^constexpr int kInvalidPlaylistId = .*$', dao, re.MULTILINE).group(0))
    parts.append(re.search(r'^#define IS_NOT_RECORDBOX_DEVICE .*$', feature, re.MULTILINE).group(0))
    for name in ('kRekordboxLibraryTable', 'kRekordboxPlaylistsTable', 'kRekordboxPlaylistTracksTable',
                 'kPLaylistPathDelimiter'):
        parts.append(re.search(r'^const QString ' + name + ' = .*$', feature, re.MULTILINE).group(0))
    parts.append(SAMPLE.method(feature, 'bool createPlaylistsTable('))
    parts.append(SAMPLE.method(feature, 'bool createPlaylistTracksTable('))
    # The definition (the first match is its forward declaration).
    definition = feature.index('void buildPlaylistTree(', feature.index('void buildPlaylistTree(') + 1)
    parts.append(SAMPLE.method(feature[definition:], 'void buildPlaylistTree('))
    (target / 'rekordbox_playlist_tree.inc').write_text('\n'.join(parts) + '\n')


def main():
    import tempfile
    import subprocess
    with tempfile.TemporaryDirectory(prefix='mixpi-source-groups-') as temporary:
        target = Path(temporary)
        reconstruct(target)
        rekordbox_tree(target)
        # The fixture also links QtSql (the tree builder's database).
        SAMPLE.qt_flags = lambda modules: qt_flags(tuple(modules) + ('QtSql',))
        program = SAMPLE.build(target, ROOT / 'tests/native/source_groups_test.cpp', METHODS, sidebar=True)
        subprocess.run([str(program)], env=qt_environment(), check=True, timeout=60)


if __name__ == '__main__':
    main()
