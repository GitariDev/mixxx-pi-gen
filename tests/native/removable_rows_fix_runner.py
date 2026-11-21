"""Council round 6 (wave J11): build and run the Removable Devices rows fixture.

As eject_folders_view_runner.py (J10): the real WLibrarySidebar,
SidebarModel and TreeItemModel, the actual Library methods from the patched
library.cpp (GROUP_METHODS, noteBrowsePlaceShown, releaseGoneFolder), from
the patched browsefeature.cpp the actual BrowseFeature::activateChild,
refreshMediaLifecycle, pruneRemovableDirectories and releaseGoneFolder with
the mount table helpers, from browsetablemodel.h the actual
BrowseTableModel::releasePath, and from mixpimedia.h the actual
MixpiMedia::tick and ejectFinished, the mount table they read pointed at the
fixture's file. --baseline leaves mixxx-removable-rows-fix.patch out (J10's
mixxx-eject-folders-view.patch stays), to show the checks fail without it.
"""
import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eject_folders_view_runner as J10
import sample_browser_runner as SAMPLE
from library_interface_runner import ROOT, reconstruct, qt_environment

PATCH_NAME = 'mixxx-removable-rows-fix.patch'
PATCH_DIR = ROOT / 'stage3/01-install-packages/files'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', action='store_true')
    arguments = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='mixpi-removable-rows-fix-') as temporary:
        target = Path(temporary)
        names, _ = reconstruct(target, exclude=(PATCH_NAME,) if arguments.baseline else ())
        # Not registered yet: J10's patch, then this one, after the stack.
        for name in (J10.PATCH_NAME,) + (() if arguments.baseline else (PATCH_NAME,)):
            if name not in names:
                subprocess.run(['git', 'apply', str(PATCH_DIR / name)], cwd=target, check=True)
        print('PATCHES', len(names), 'BASELINE' if arguments.baseline else PATCH_NAME, flush=True)
        J10.production(target, baseline=False)
        methods = SAMPLE.GROUP_METHODS + ('void Library::noteBrowsePlaceShown()', 'void Library::releaseGoneFolder()')
        program = SAMPLE.build(target, ROOT / 'tests/native/removable_rows_fix_test.cpp', methods, sidebar=True)
        return subprocess.run([str(program)], env=qt_environment(), timeout=60).returncode


if __name__ == '__main__':
    raise SystemExit(main())
