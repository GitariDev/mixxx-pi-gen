"""Build helpers for the media_screen and media_handover fixtures (R-2 to R-6).

The fixtures compile the shipped headers from the patched stack: every
registered patch, then mixxx-media-screen.patch and mixxx-media-handover.patch
on top (where the registration puts them), whether or not they are listed in
MIXXX_PATCHES yet.
"""
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native.library_interface_runner import (PATCH_DIR, moc_path, populate_pinned, qt_environment,
                                             qt_flags, reconstruct)

ROOT = Path(__file__).resolve().parents[2]
SCREEN = 'mixxx-media-screen.patch'
HANDOVER = 'mixxx-media-handover.patch'
QSS = ':'.join(str(PATCH_DIR / name) for name in
               ('pioneered-menus.qss', 'pioneered-touch.qss', 'mixpi-performance.qss'))


def touched(name):
    return [line.split()[2][2:] for line in (PATCH_DIR / name).read_text().splitlines()
            if line.startswith('diff --git ')]


def patched_tree(target, upto=SCREEN):
    """Reconstruct the stack without the N3 patches, then apply them in order."""
    ours = [SCREEN] if upto == SCREEN else [SCREEN, HANDOVER]
    names, _ = reconstruct(target, exclude=(SCREEN, HANDOVER))
    for name in ours:
        for path in touched(name):
            try:
                populate_pinned(target, [path])
            except subprocess.CalledProcessError:
                pass  # a new file of this patch
        subprocess.run(['git', 'apply', str(PATCH_DIR / name)], cwd=target, check=True, timeout=15)
    return names + ours


def build_screen(target):
    patched_tree(target, SCREEN)
    populate_pinned(target, ['src/widget/wlabel.h', 'src/widget/wlabel.cpp'])
    interfaces = target / 'interfaces'
    for name in ('widget/wbasewidget.h', 'skin/legacy/skincontext.h', 'widget/wskincolor.h'):
        (interfaces / name).parent.mkdir(parents=True, exist_ok=True)
        (interfaces / name).write_text('#pragma once\n#include "media_screen_doubles.h"\n')
    includes = ['-I' + str(interfaces), '-I' + str(target / 'src'), '-I' + str(ROOT / 'tests/native')]
    # wlabel.cpp includes its own moc output.
    subprocess.run([moc_path(), *includes, str(target / 'src/widget/wlabel.h'),
                    '-o', str(interfaces / 'moc_wlabel.cpp')], check=True, timeout=30)
    binary = target / 'media-screen-test'
    command = ['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror', *includes,
               str(target / 'src/widget/wlabel.cpp'), str(ROOT / 'tests/native/media_screen_test.cpp'),
               '-o', str(binary), *qt_flags(('QtCore', 'QtGui', 'QtWidgets', 'QtXml'))]
    print('COMPILE', repr(command), flush=True)
    subprocess.run(command, check=True, timeout=300)
    return binary


def run(binary, *arguments):
    environment = qt_environment()
    environment['MIXPI_SKIN_QSS'] = QSS
    return subprocess.run([str(binary), *arguments], env=environment, capture_output=True, text=True,
                          timeout=120)
