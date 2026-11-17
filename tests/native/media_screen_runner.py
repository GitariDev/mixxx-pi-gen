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
# Acceptance B repairs (skin root parent, deferred open), after the source groups.
FIXES = 'mixxx-media-screen-fixes.patch'
# Council round 1: scrolling lists, no rebuild on an unchanged refresh.
LISTS = 'mixxx-media-lists.patch'
# Build C, wave C1 (U-10, U-8): the agreed Media page and [MixPi],drive_insert.
AGREED = 'mixxx-media-agreed.patch'
# Wave C2: the old Media section of pioneered-menus.qss is gone; the page's
# own stylesheet loads right after it, as on the image.
QSS = ':'.join(str(PATCH_DIR / name) for name in
               ('pioneered-menus.qss', 'mixpi-media-page.qss', 'pioneered-touch.qss',
                'mixpi-performance.qss'))
# The agreed page's own stylesheet loads right after pioneered-menus.qss.
AGREED_QSS = ':'.join(str(PATCH_DIR / name) for name in
                      ('pioneered-menus.qss', 'mixpi-media-page.qss', 'pioneered-touch.qss',
                       'mixpi-performance.qss'))
# The fonts Mixxx loads at start (res/fonts), for faithful offscreen renders.
FONTS = ['res/fonts/' + name for name in
         ('OpenSans-Regular.ttf', 'OpenSans-Semibold.ttf', 'OpenSans-Bold.ttf', 'Ubuntu-R.ttf', 'Ubuntu-B.ttf')]


def touched(name):
    return [line.split()[2][2:] for line in (PATCH_DIR / name).read_text().splitlines()
            if line.startswith('diff --git ')]


def patched_tree(target, upto=SCREEN):
    """Reconstruct the stack without the N3 patches, then apply them in order."""
    order = [SCREEN, HANDOVER, FIXES, LISTS, AGREED]
    ours = order[:order.index(upto) + 1]
    names, _ = reconstruct(target, exclude=tuple(order))
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


def build_fixes(target):
    """The Acceptance B repairs: the whole N3 stack, Qt only."""
    patched_tree(target, FIXES)
    binary = target / 'media-screen-fixes-test'
    command = ['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-I' + str(target / 'src'),
               str(ROOT / 'tests/native/media_screen_fixes_test.cpp'), '-o', str(binary),
               *qt_flags(('QtCore', 'QtGui', 'QtWidgets'))]
    print('COMPILE', repr(command), flush=True)
    subprocess.run(command, check=True, timeout=300)
    return binary


def build_lists(target):
    """The council round 1 list repairs: the whole N3 stack, with QtTest for touch drags."""
    patched_tree(target, LISTS)
    binary = target / 'media-screen-lists-test'
    command = ['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-I' + str(target / 'src'),
               str(ROOT / 'tests/native/media_screen_lists_test.cpp'), '-o', str(binary),
               *qt_flags(('QtCore', 'QtGui', 'QtWidgets', 'QtTest'))]
    print('COMPILE', repr(command), flush=True)
    subprocess.run(command, check=True, timeout=300)
    return binary


def build_agreed(target):
    """The agreed Media page (U-10) and the insert choice (U-8): the whole N3 stack, Qt only."""
    patched_tree(target, AGREED)
    populate_pinned(target, FONTS)
    binary = target / 'media-agreed-test'
    command = ['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-I' + str(target / 'src'),
               str(ROOT / 'tests/native/media_agreed_test.cpp'), '-o', str(binary),
               *qt_flags(('QtCore', 'QtGui', 'QtWidgets', 'QtTest'))]
    print('COMPILE', repr(command), flush=True)
    subprocess.run(command, check=True, timeout=300)
    return binary


def build_insert(target):
    """[MixPi],drive_insert with the shipped control framework and save on change.

    As save_on_change_runner.build: the registered stack with this patch on
    top, the pinned control and config sources, and its interface doubles.
    """
    from native import save_on_change_runner as save
    reconstruct(target, exclude=(AGREED,))
    for path in touched(AGREED):
        try:
            populate_pinned(target, [path])
        except subprocess.CalledProcessError:
            pass  # a new file of this patch
    subprocess.run(['git', 'apply', str(PATCH_DIR / AGREED)], cwd=target, check=True, timeout=15)
    populate_pinned(target, ['src/' + name for name in save.PINNED_FILES])
    support = target / 'interfaces'
    for name in save.DOUBLED:
        (support / name).parent.mkdir(parents=True, exist_ok=True)
        (support / name).write_text('#pragma once\n#include "save_on_change_doubles.h"\n')
    for name, text in save.DOUBLES.items():
        (support / name).parent.mkdir(parents=True, exist_ok=True)
        (support / name).write_text(text)
    includes = ['-I' + str(support), '-I' + str(target / 'src'), '-I' + str(ROOT / 'tests/native')]
    for header in ('control/control.h', 'control/controlobject.h', 'control/controlproxy.h',
                   'mixer/samplerbank.h'):
        path = target / 'src' / header
        subprocess.run([moc_path(), *includes, str(path), '-o', str(path.parent / ('moc_' + path.stem + '.cpp'))],
                       check=True, timeout=30)
    doubles_moc = target / 'moc_save_on_change_doubles.cpp'
    subprocess.run([moc_path(), *includes, str(ROOT / 'tests/native/save_on_change_doubles.h'),
                    '-o', str(doubles_moc)], check=True, timeout=30)
    sources = [target / 'src' / name for name in
               ('preferences/configobject.cpp', 'control/control.cpp', 'control/controlobject.cpp',
                'control/controlproxy.cpp', 'mixer/samplerbank.cpp')] + [doubles_moc]
    binary = target / 'media-insert-test'
    command = ['c++', '-std=c++20', '-Wall', '-Wextra', *includes, *[str(source) for source in sources],
               str(ROOT / 'tests/native/media_insert_test.cpp'), '-o', str(binary), '-pthread',
               *qt_flags(('QtCore', 'QtGui', 'QtWidgets', 'QtXml'))]
    print('COMPILE', repr(command), flush=True)
    subprocess.run(command, check=True, timeout=300)
    return binary


def run(binary, *arguments, qss=QSS, environment_extra=None):
    environment = qt_environment()
    environment['MIXPI_SKIN_QSS'] = qss
    environment.update(environment_extra or {})
    return subprocess.run([str(binary), *arguments], env=environment, capture_output=True, text=True,
                          timeout=120)
