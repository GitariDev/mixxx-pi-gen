import importlib.util
import os
import re
from pathlib import Path
import subprocess
import tempfile
import unittest

from native.library_interface_runner import qt_available

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'library_interface_runner', ROOT / 'tests/native/library_interface_runner.py')
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class LibraryInterfacePatchTests(unittest.TestCase):
    @unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
    def test_native_actions_active_view_routing(self):
        subprocess.run(['python3', str(ROOT / 'tests/native/library_actions_routing_runner.py')],
                       check=True, timeout=150)

    @unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
    def test_native_actions_view_churn_holdout(self):
        subprocess.run(['python3', str(ROOT / 'tests/native/library_actions_routing_runner.py'),
                        '--holdout'], check=True, timeout=150)

    @unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
    def test_native_sources_model_and_persistence(self):
        subprocess.run(['python3', str(ROOT / 'tests/native/library_interface_sources_runner.py')],
                       check=True, timeout=150)

    @unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
    def test_native_sources_churn_serialization_index_holdout(self):
        subprocess.run(['python3', str(ROOT / 'tests/native/library_interface_sources_runner.py'),
                        '--holdout'], check=True, timeout=150)

    @unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
    def test_native_sources_touch_checks_fail_without_source_tap(self):
        # F-6: the same fixture on the stack without mixxx-source-tap.patch
        # must fail its touch checks (the drag moves the highlight, a held
        # press opens a source), so the checks detect the field fault.
        result = subprocess.run(['python3', str(ROOT / 'tests/native/library_interface_sources_runner.py'),
                                 '--without-source-tap'], capture_output=True, text=True, timeout=150)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('FAIL touch slow drag keeps the highlight on the shown source', result.stdout)
        self.assertIn('FAIL a held press released on another row opens nothing', result.stdout)
        self.assertIn('PASS actual skin-load hidden default uses visible fallback and retains preference',
                      result.stdout)

    @unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
    def test_native_bpm_lock_checks_fail_without_bpm_lock_touch(self):
        # F-7 follow-up: without mixxx-bpm-lock-touch.patch a tap on the BPM
        # lock in the touch skin flips bpm_lock, and the checks say so.
        result = subprocess.run(['python3', str(ROOT / 'tests/native/library_interface_sources_runner.py'),
                                 '--without-bpm-lock-touch'], capture_output=True, text=True, timeout=150)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('PASS BPM desktop: a click on the lock still toggles bpm_lock', result.stdout)
        self.assertIn('FAIL BPM touch: taps at the old lock position, the cell centre, a double tap '
                      'and Space leave bpm_lock unchanged', result.stdout)
        self.assertIn('FAIL BPM touch: no lock check box is drawn', result.stdout)

    @unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
    def test_native_sources_width_checks_fail_without_acceptance_fixes(self):
        # F-6 (acceptance finding 6): without mixxx-acceptance-fixes.patch the
        # touch Sources list shows a horizontal scroll bar for a long name.
        result = subprocess.run(['python3', str(ROOT / 'tests/native/library_interface_sources_runner.py'),
                                 '--without-acceptance-fixes'], capture_output=True, text=True, timeout=150)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('FAIL touch Sources list has no horizontal scroll bar', result.stdout)
        self.assertIn('PASS desktop Sources list keeps the pinned horizontal scrolling for a long name',
                      result.stdout)
        self.assertIn('PASS touch Sources list keeps its vertical scroll bar', result.stdout)

    @unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
    def test_native_sources_drag_checks_fail_without_council_fixes(self):
        # F-6 (council round 1): without mixxx-council-fixes.patch a drag that
        # ends on the row it started on still opens that source.
        result = subprocess.run(['python3', str(ROOT / 'tests/native/library_interface_sources_runner.py'),
                                 '--without-council-fixes'], capture_output=True, text=True, timeout=150)
        self.assertNotEqual(result.returncode, 0)
        for failure in ('touch horizontal drag that ends on the pressed row opens nothing',
                        'touch out-and-back drag released on the pressed row opens nothing',
                        'a move of exactly the drag distance and back opens nothing',
                        'synthetic touch horizontal drag along one row opens nothing'):
            self.assertIn('FAIL ' + failure, result.stdout)
        # Later counts cascade once a drag has opened a source; these do not.
        for kept in ('the horizontal drag fixture stays on one row',
                     'touch slow drag from row 1 to row 4 opens no source',
                     'keyboard/controller Down opens the next source once through pressed()',
                     'synthetic touch drag over three rows opens nothing'):
            self.assertIn('PASS ' + kept, result.stdout)

    @unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
    def test_arrange_label_check_fails_without_the_item_background(self):
        # F-9 (acceptance check 10): the menu style without the item
        # background (as in build 1) paints unselected labels under the box.
        # The style geometry cannot see it; the grab check must.
        style = (RUNNER.PATCH_DIR / 'pioneered-menus.qss').read_text()
        rule = re.search(r'#MixpiColumnArrangement QListWidget::item \{[^}]*\}', style)[0]
        self.assertIn('background-color: #161a20;', rule)  # --mx-surface
        with tempfile.TemporaryDirectory(prefix='mixpi-menus-qss-') as temporary:
            build1 = Path(temporary) / 'pioneered-menus.qss'
            build1.write_text(style.replace(rule, rule.replace('    background-color: #161a20;\n', '')))
            result = subprocess.run(['python3', str(ROOT / 'tests/native/library_interface_runner.py'),
                                     '--menus-qss', str(build1)],
                                    capture_output=True, text=True, timeout=150)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('PASS style geometry: every Arrange label starts right of its check box',
                      result.stdout)
        self.assertIn('FAIL painted pixels: no Arrange check box covers its label, checked or not',
                      result.stdout)

    @unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
    def test_arrange_label_tap_check_fails_without_council_fixes(self):
        # F-9 (council round 1): without mixxx-council-fixes.patch a tap on
        # an Arrange label only selects the row.
        result = subprocess.run(['python3', str(ROOT / 'tests/native/library_interface_runner.py'),
                                 '--without-council-fixes'], capture_output=True, text=True, timeout=150)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('FAIL a tap on the label text toggles the row\'s column', result.stdout)
        for kept in ('a tap on the check box toggles it once', 'Space on the current row still toggles it',
                     'a checked box shows an ink tick on the accent',
                     'painted pixels: no Arrange check box covers its label, checked or not'):
            self.assertIn('PASS ' + kept, result.stdout)

    @unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
    def test_arrange_tick_check_fails_with_the_build2_box(self):
        # F-9 (council round 1): the build-2 checked box (white fill, no
        # image) has no tick, and the grab check says so.
        style = (RUNNER.PATCH_DIR / 'pioneered-menus.qss').read_text()
        rule = re.search(r'#MixpiColumnArrangement QListWidget::indicator:checked \{[^}]*\}', style)[0]
        self.assertIn('image: url(skin:/mixpi-icon-tick.svg);', rule)
        build2 = ('#MixpiColumnArrangement QListWidget::indicator:checked {\n    background-color: #ffffff;\n'
                  '    border: 2px solid #68baff;\n    border-radius: 3px;\n}')
        with tempfile.TemporaryDirectory(prefix='mixpi-menus-qss-') as temporary:
            old = Path(temporary) / 'pioneered-menus.qss'
            old.write_text(style.replace(rule, build2))
            result = subprocess.run(['python3', str(ROOT / 'tests/native/library_interface_runner.py'),
                                     '--menus-qss', str(old)],
                                    capture_output=True, text=True, timeout=150)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('FAIL a checked box shows an ink tick on the accent', result.stdout)
        self.assertIn('PASS a tap on the label text toggles the row\'s column', result.stdout)

    def test_bpm_lock_patch_is_small_and_gated_on_touch_navigation(self):
        patch = (RUNNER.PATCH_DIR / 'mixxx-bpm-lock-touch.patch').read_text()
        self.assertEqual(re.findall(r'^diff --git a/(\S+) b/\S+$', patch, re.MULTILINE),
                         ['src/library/tabledelegates/bpmdelegate.cpp',
                          'src/library/tabledelegates/bpmdelegate.h',
                          'src/widget/wlibrarysidebar.cpp'])
        added = '\n'.join(line[1:] for line in patch.splitlines()
                          if line.startswith('+') and not line.startswith('+++'))
        # Both delegate overrides fall back to the pinned behaviour unless the
        # skin enabled touch navigation; the track menu is not touched.
        self.assertEqual(added.count('if (touchSkin())'), 2)
        self.assertIn('return CheckboxDelegate::editorEvent(event, model, option, index);', added)
        self.assertIn('setProperty("mixpiTouchNavigation", true)', added)
        self.assertNotIn('wtrackmenu', patch)

    def test_full_stack_apply_reverse_restores_pinned_bytes(self):
        with tempfile.TemporaryDirectory(prefix='mixpi-library-interface-stack-') as temporary:
            target = Path(temporary)
            names, baseline = RUNNER.reconstruct(target)
            for name in reversed(names):
                subprocess.run(['git', 'apply', '--reverse', '--check',
                                str(RUNNER.PATCH_DIR / name)], cwd=target, check=True)
                subprocess.run(['git', 'apply', '--reverse',
                                str(RUNNER.PATCH_DIR / name)], cwd=target, check=True)
            restored = {str(path.relative_to(target)): path.read_bytes()
                        for path in target.rglob('*') if path.is_file()}
            self.assertEqual(baseline, restored)


if __name__ == '__main__':
    unittest.main()
