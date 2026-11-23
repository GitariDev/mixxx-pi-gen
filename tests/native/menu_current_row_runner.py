"""Council round 9 (Opus), wave J17: build and run the menu current-row fixture.

As menu_place_fix_runner.py (wave J16): the actual Library methods from the
patched library.cpp, the real WLibrarySidebar, SidebarModel and TreeItemModel,
and the actual rekordbox playlist tree builder with the drive's Tracks row.
The stack is every patch in MIXXX_PATCHES, then mixxx-menu-current-row.patch
if it is not registered yet. --baseline leaves mixxx-menu-current-row.patch
out (J16 stays), to show the checks fail without it.
"""
import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sample_browser_runner as SAMPLE
import source_groups_runner as GROUPS
from library_interface_runner import ROOT, reconstruct, qt_flags, qt_environment

PATCH_NAME = 'mixxx-menu-current-row.patch'
PATCH_DIR = ROOT / 'stage3/01-install-packages/files'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', action='store_true')
    arguments = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='mixpi-menu-current-row-') as temporary:
        target = Path(temporary)
        names, _ = reconstruct(target, exclude=(PATCH_NAME,) if arguments.baseline else ())
        if not arguments.baseline and PATCH_NAME not in names:
            subprocess.run(['git', 'apply', str(PATCH_DIR / PATCH_NAME)], cwd=target, check=True)
        print('PATCHES', len(names), 'BASELINE' if arguments.baseline else PATCH_NAME, flush=True)
        GROUPS.rekordbox_tree(target)
        # The fixture also links QtSql (the tree builder's database).
        SAMPLE.qt_flags = lambda modules: qt_flags(tuple(modules) + ('QtSql',))
        program = SAMPLE.build(target, ROOT / 'tests/native/menu_current_row_test.cpp', GROUPS.METHODS,
                               sidebar=True)
        return subprocess.run([str(program)], env=qt_environment(), timeout=60).returncode


if __name__ == '__main__':
    raise SystemExit(main())
