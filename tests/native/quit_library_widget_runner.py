"""Build helpers for the quit_library_widget fixture (acceptance I, X2).

The fixture compiles the shipped widget/mixpipage.h and
library/mixpimediapage.h from the registered stack, with
mixxx-quit-library-widget.patch on top (fix=True) or without it (fix=False),
whether or not it is listed in MIXXX_PATCHES yet. Library's widget member and
the parent lambda it hands MixpiMedia are copied from that stack's
src/library/library.h and library.cpp into a generated header.
"""
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native.library_interface_runner import PATCH_DIR, qt_environment, qt_flags, reconstruct

ROOT = Path(__file__).resolve().parents[2]
PATCH = 'mixxx-quit-library-widget.patch'
# MixpiMedia's parent lambda in Library's constructor (mixxx-media-screen.patch).
LAMBDA = '[this]() -> QWidget* { return m_pLibraryWidget; }'


def stack(target, fix=True):
    names, _ = reconstruct(target, exclude=(PATCH,))
    if fix:
        subprocess.run(['git', 'apply', str(PATCH_DIR / PATCH)], cwd=target, check=True, timeout=15)
        names.append(PATCH)
    return names


def member(target):
    """Library's declaration of m_pLibraryWidget and the parent lambda, as built."""
    header = (target / 'src/library/library.h').read_text()
    declared = re.findall(r'^ {4}([^\n;/]*?)\s*\bm_pLibraryWidget;$', header, re.MULTILINE)
    if len(declared) != 1:
        raise RuntimeError('m_pLibraryWidget declaration not found once: ' + repr(declared))
    source = (target / 'src/library/library.cpp').read_text()
    if source.count('new MixpiMedia(this, ' + LAMBDA) != 1:
        raise RuntimeError('MixpiMedia parent lambda changed in library.cpp')
    return declared[0], LAMBDA


def build(target, fix=True):
    names = stack(target, fix)
    print('PATCHES', ' '.join(names), flush=True)
    declared, parent = member(target)
    print('MEMBER', declared, flush=True)
    generated = target / 'generated'
    generated.mkdir(exist_ok=True)
    (generated / 'quit_library_widget_member.h').write_text(
        '#pragma once\n#include <functional>\n#include <QPointer>\n'
        '// From src/library/library.h and library.cpp of the stack under test.\n'
        'struct LibraryWidgetHolder {\n'
        f'    {declared} m_pLibraryWidget = nullptr;\n'
        f'    std::function<QWidget*()> parent() {{\n        return {parent};\n    }}\n'
        '};\n')
    binary = target / 'quit-library-widget-test'
    command = ['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-I' + str(generated),
               '-I' + str(target / 'src'), str(ROOT / 'tests/native/quit_library_widget_test.cpp'),
               '-o', str(binary), *qt_flags(('QtCore', 'QtGui', 'QtWidgets'))]
    print('COMPILE', repr(command), flush=True)
    subprocess.run(command, check=True, timeout=300)
    return binary, declared


def run(binary, mode='report'):
    return subprocess.run([str(binary), mode], env=qt_environment(), capture_output=True, text=True,
                          timeout=60)
