"""Apply the owned patch to pinned source and run its real Qt selector."""
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import unittest

from native.library_interface_runner import qt_available, qt_flags, qt_environment, moc_path
from native.library_interface_runner import reconstruct, populate_pinned

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / 'stage3/01-install-packages/files/mixxx-effect-placeholder.patch'


class EffectPlaceholderTests(unittest.TestCase):
    def test_patch_scopes_only_empty_text_and_reverses(self):
        with tempfile.TemporaryDirectory(prefix='mixpi-effect-patch-') as temporary:
            target = Path(temporary)
            reconstruct(target, exclude=(PATCH.name,))
            populate_pinned(target, ('src/widget/weffectselector.cpp',))
            destination = target / 'src/widget/weffectselector.cpp'
            before = destination.read_bytes()
            subprocess.run(['git', 'apply', str(PATCH)], cwd=target, check=True)
            self.assertIn('tr("Select effect…")', destination.read_text())
            subprocess.run(['git', 'apply', '-R', str(PATCH)], cwd=target, check=True)
            self.assertEqual(destination.read_bytes(), before)

    @unittest.skipUnless(qt_available(), 'retained Qt SDK required')
    def test_exact_native_selector(self):
        with tempfile.TemporaryDirectory(prefix='mixpi-effect-qt-') as temporary:
            target = Path(temporary)
            native = ROOT / 'tests/native'
            reconstruct(target, exclude=(PATCH.name,) if os.environ.get('MIXPI_EFFECT_BASELINE') else ())
            populate_pinned(target, ('src/widget/weffectselector.h', 'src/widget/weffectselector.cpp'))
            for name in ('effects/defs.h', 'effects/effectsmanager.h', 'effects/visibleeffectslist.h',
                         'widget/wbasewidget.h', 'widget/effectwidgetutils.h'):
                destination = target / 'doubles' / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text('#include "effect_selector_stubs.h"\n')
            subprocess.run([moc_path(), str(target / 'src/widget/weffectselector.h'),
                            '-o', str(target / 'src/widget/moc_weffectselector.cpp')], check=True)
            subprocess.run([moc_path(), '-feffect_selector_stubs.h', str(native / 'effect_selector_stubs.h'),
                            '-o', str(target / 'moc_effect_stubs.cpp')], check=True)
            command = ['c++', '-std=c++20',
                       '-I' + str(native), '-I' + str(target), '-I' + str(target / 'src'), '-I' + str(target / 'doubles')]
            command += [str(native / 'effect_selector_test.cpp'), str(target / 'moc_effect_stubs.cpp'),
                        str(target / 'src/widget/weffectselector.cpp'), '-o', str(target / 'test'),
                        *qt_flags(('QtCore', 'QtGui', 'QtWidgets', 'QtXml'))]
            subprocess.run(command, check=True, timeout=60)
            environment = qt_environment()
            style = os.environ.get('MIXPI_EFFECT_STYLE', str(ROOT / 'stage3/01-install-packages/files/mixpi-performance.qss'))
            arguments = [str(target / 'test'), style]
            if os.environ.get('MIXPI_EFFECT_EVIDENCE'):
                arguments.append(os.environ['MIXPI_EFFECT_EVIDENCE'])
            subprocess.run(arguments, env=environment, check=True, timeout=20)
