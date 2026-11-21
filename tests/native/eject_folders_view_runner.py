"""Spec 2e, as 2g applies it (build J, wave J10): build and run the Folders eject fixture.

As source_groups_runner.py: the real WLibrarySidebar, SidebarModel and
TreeItemModel, and the actual Library methods from the patched library.cpp
(GROUP_METHODS, noteBrowsePlaceShown and, with the patch,
releaseGoneFolder). From the patched browsefeature.cpp: the actual
BrowseFeature::activateChild, refreshMediaLifecycle and
pruneRemovableDirectories and, with the patch, releaseGoneFolder with the
mount table helpers (mountPoints, mountOf); from browsetablemodel.h the
actual BrowseTableModel::releasePath; from mixpimedia.h the actual
MixpiMedia::tick and ejectFinished. The mount table those read
(/proc/self/mountinfo) is pointed at the fixture's file. --baseline leaves
mixxx-eject-folders-view.patch out, to show the checks fail without it.
"""
import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sample_browser_runner as SAMPLE
from library_interface_runner import ROOT, reconstruct, populate_pinned, qt_environment

PATCH_NAME = 'mixxx-eject-folders-view.patch'
FEATURE = 'src/library/browse/browsefeature.cpp'
TABLE = 'src/library/browse/browsetablemodel.h'
MEDIA = 'src/library/mixpimedia.h'
MOUNT_TABLE = 'const QString kMountTable = QStringLiteral("/proc/self/mountinfo");'


def inline_method(source, signature):
    """A method defined in its class (four spaces in), up to its closing brace."""
    start = source.index('    ' + signature)
    return source[start:source.index('\n    }\n', start) + 7]


def production(target, baseline):
    feature = (target / FEATURE).read_text()
    parts = []
    if not baseline:
        if MOUNT_TABLE not in feature:
            raise RuntimeError('Unexpected mount table in ' + FEATURE)
        parts.append('const QString& kMountTable = kFixtureMountTable;')
        parts.append(SAMPLE.method(feature, 'QStringList mountPoints()'))
        parts.append(SAMPLE.method(feature, 'QString mountOf('))
    for signature in ('void BrowseFeature::activateChild(', 'void BrowseFeature::refreshMediaLifecycle()',
                      'void BrowseFeature::pruneRemovableDirectories()'):
        parts.append(SAMPLE.method(feature, signature))
    if not baseline:
        parts.append(SAMPLE.method(feature, 'QString BrowseFeature::releaseGoneFolder()'))
    (target / 'browse_production.inc').write_text('\n'.join(parts) + '\n')
    # Without the patch no patch changes the table's header: the pinned one.
    populate_pinned(target, [TABLE])
    table = (target / TABLE).read_text()
    (target / 'browse_release.inc').write_text(
        inline_method(table, 'void releasePath() {') if not baseline else '\n')
    media = (target / MEDIA).read_text()
    tick = inline_method(media, 'void tick() {')
    if 'QStringLiteral("/proc/self/mountinfo")' not in tick:
        raise RuntimeError('Unexpected mount table in MixpiMedia::tick')
    tick = tick.replace('QStringLiteral("/proc/self/mountinfo")', 'kFixtureMountTable')
    finished = inline_method(media, 'void ejectFinished(bool ok, const QString& message) {')
    (target / 'media_production.inc').write_text(tick + '\n' + finished + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', action='store_true')
    arguments = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='mixpi-eject-folders-view-') as temporary:
        target = Path(temporary)
        names, _ = reconstruct(target, exclude=(PATCH_NAME,) if arguments.baseline else ())
        if not arguments.baseline and PATCH_NAME not in names:
            subprocess.run(['git', 'apply', str(ROOT / 'stage3/01-install-packages/files' / PATCH_NAME)],
                           cwd=target, check=True)
        print('PATCHES', len(names), 'BASELINE' if arguments.baseline else PATCH_NAME, flush=True)
        production(target, arguments.baseline)
        methods = SAMPLE.GROUP_METHODS + ('void Library::noteBrowsePlaceShown()',)
        if not arguments.baseline:
            methods += ('void Library::releaseGoneFolder()',)
        program = SAMPLE.build(target, ROOT / 'tests/native/eject_folders_view_test.cpp', methods,
                               defines=('-DBASELINE',) if arguments.baseline else (), sidebar=True)
        return subprocess.run([str(program)], env=qt_environment(), timeout=60).returncode


if __name__ == '__main__':
    raise SystemExit(main())
