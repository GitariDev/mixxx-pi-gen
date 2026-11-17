"""Build B acceptance fixes in the native settings (mixxx-settings-fixes.patch).

1. R-13: Settings > Playback > Tempo range was never saved: the handlers set
   each deck's rateRange but not [Controls],RateRangePercent, which Mixxx
   (DlgPrefDeck) reads at start. 8 % came back after a quit.
2. F-14: the first Show top bar after a start once raised "Top bar was not
   confirmed" although the bar was showing: mixpi-desktop-bar looks for the
   36 px reservation for only 0.8 s after starting Waybar, and a cold Waybar
   can take longer. Mixxx now looks again before it reports a failure.
Evidence: deploy/ui-redesign-20261117/acceptance-B/ACCEPTANCE.md.
"""
import importlib.util
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from native.library_interface_runner import (PATCH_DIR, moc_path, populate_pinned, qt_available,
                                             qt_environment, qt_flags, reconstruct, source_reference)

ROOT = Path(__file__).resolve().parents[1]
PATCH_NAME = 'mixxx-settings-fixes.patch'
PATCH = PATCH_DIR / PATCH_NAME
HEADER = 'src/widget/mixpiperformancesettings.h'

# Like the F-14 fake in test_performance_settings.py. "show" starts the bar,
# but the helper only confirms it on the LATE-th later status call; before
# that it fails as mixpi-desktop-bar does when the reservation lags.
FAKE_DESKTOP_BAR = '''#!/bin/sh
dir="$MIXPI_FAKE_BAR_DIR"
echo "$1" >> "$dir/calls"
state=$(cat "$dir/state" 2>/dev/null || echo hidden)
case "$1" in
    show) state=visible; echo "${MIXPI_FAKE_BAR_LATE:-0}" > "$dir/lag" ;;
    hide) state=hidden; echo 0 > "$dir/lag" ;;
esac
echo "$state" > "$dir/state"
lag=$(cat "$dir/lag" 2>/dev/null || echo 0)
if { [ -n "$MIXPI_FAKE_BAR_NEVER" ] && [ "$state" = visible ]; } || [ "$lag" -gt 0 ]; then
    [ "$lag" -gt 0 ] && echo $((lag - 1)) > "$dir/lag"
    echo '{"visible": null, "reserved_px": null, "error": "Waybar service and the 36px desktop reservation disagree; visibility is unconfirmed."}'
    exit 1
fi
if [ "$state" = visible ]; then
    echo '{"visible": true, "reserved_px": 36, "error": ""}'
else
    echo '{"visible": false, "reserved_px": 0, "error": ""}'
fi
'''
BAR_MODES = {
    'bar_normal': {},
    # The show and two re-checks fail; the 3rd re-check (of 4) confirms.
    'bar_late': {'MIXPI_FAKE_BAR_LATE': '3'},
    'bar_never': {'MIXPI_FAKE_BAR_NEVER': '1'},
}


def stage(target, with_fix=True):
    """The shipping header (with or without this patch) staged as the settings fixture stages it."""
    spec = importlib.util.spec_from_file_location(
        'prepare_performance_settings', ROOT / 'tests/native/prepare_performance_settings.py')
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(ROOT / 'tests/native'))
    spec.loader.exec_module(module)

    def stack(directory, exclude=()):
        names = reconstruct(directory, exclude=tuple(exclude) + (PATCH_NAME,))
        if with_fix:
            populate_pinned(directory, [HEADER])
            subprocess.run(['git', 'apply', str(PATCH)], cwd=directory, check=True, timeout=15)
        return names

    module.reconstruct = stack
    module.prepare(source_reference(), target)
    (target / 'settings_fixes_test.cpp').write_bytes(
        (ROOT / 'tests/native/settings_fixes_test.cpp').read_bytes())


def build(target, with_fix=True):
    stage(target, with_fix)
    for name in ('control', 'controlobject', 'controlproxy'):
        subprocess.run([moc_path(), str(target / f'production/control/{name}.h'),
                        '-o', str(target / f'production/control/moc_{name}.cpp')],
                       check=True, timeout=30)
    command = ['c++', '-std=c++20', '-I' + str(target), '-I' + str(target / 'doubles'),
               '-I' + str(target / 'production'), str(target / 'settings_fixes_test.cpp')]
    command += [str(target / f'production/control/{name}.cpp')
                for name in ('control', 'controlobject', 'controlproxy')]
    command += ['-o', str(target / 'settings-fixes-test'), *qt_flags()]
    subprocess.run(command, check=True, timeout=120)
    return target / 'settings-fixes-test'


def run(modes=('tempo', *BAR_MODES), with_fix=True):
    with tempfile.TemporaryDirectory(prefix='mixpi-settings-fixes-') as directory:
        target = Path(directory)
        binary = build(target / 'build', with_fix)
        results = {}
        for mode in modes:
            environment = qt_environment()
            if mode in BAR_MODES:
                fake = target / mode
                fake.mkdir()
                helper = fake / 'mixpi-desktop-bar'
                helper.write_text(FAKE_DESKTOP_BAR)
                helper.chmod(0o755)
                environment.update(BAR_MODES[mode], MIXPI_DESKTOP_BAR_HELPER=str(helper),
                                   MIXPI_FAKE_BAR_DIR=str(fake))
            results[mode] = subprocess.run([str(binary), mode], env=environment,
                                           capture_output=True, text=True, timeout=60)
            print('MODE', mode, results[mode].stdout, results[mode].stderr[-2000:], flush=True)
        return results


def added(text):
    return '\n'.join(line[1:] for line in text.splitlines()
                     if line.startswith('+') and not line.startswith('+++'))


class SettingsFixesPatchTests(unittest.TestCase):
    def test_patch_changes_only_the_settings_header(self):
        self.assertEqual(re.findall(r'^diff --git a/(\S+) ', PATCH.read_text(), re.MULTILINE), [HEADER])

    def test_tempo_range_writes_the_key_mixxx_reads_at_start(self):
        source = added(PATCH.read_text())
        self.assertIn('const ConfigKey rangeKey("[Controls]", "RateRangePercent");', source)
        # Before the decks, as DlgPrefDeck::slotApply does.
        text = PATCH.read_text()
        self.assertLess(text.index('+            m_settings->set(rangeKey'),
                        text.index(' range.set(v / 100.0);'))

    def test_pinned_mixxx_reads_that_key_at_start(self):
        if not source_reference_available():
            self.skipTest('MIXXX_TEST_SOURCE required')
        from native.library_interface_runner import pinned_bytes
        deck = pinned_bytes('src/preferences/dialog/dlgprefdeck.cpp').decode()
        self.assertIn('ConfigKey(kControlsGroup, QStringLiteral("RateRangePercent"))', deck)
        self.assertIn('const QString kControlsGroup = QStringLiteral("[Controls]");', deck)


def source_reference_available():
    try:
        source_reference()
        return True
    except (RuntimeError, subprocess.SubprocessError, OSError):
        return False


@unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
class NativeSettingsFixesTests(unittest.TestCase):
    EXPECTED = {
        'tempo': ['tempo_range_index 4 stores [Controls],RateRangePercent 10',
                  'tempo_range 16 stores 16 and moves the index to 5',
                  'at start tempo_range and tempo_range_index follow the decks',
                  'publishing the start values writes no config',
                  'when the decks refuse, the stored range is what they use'],
        'bar_normal': ['a show confirmed at once reads Hide top bar within 1 s',
                       'the normal show runs the helper once, no re-check'],
        'bar_late': ['a show confirmed late reads Hide top bar',
                     'a show confirmed late raises no Top bar was not confirmed',
                     'the button reads Checking top bar until the bar is confirmed'],
        'bar_never': ['a show that is never confirmed still reports once',
                      'the failure is reported within 6 s'],
    }

    def test_every_check_passes(self):
        for mode, result in run().items():
            with self.subTest(mode=mode):
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr[-3000:])
                for line in self.EXPECTED[mode]:
                    self.assertIn('PASS ' + line + '\n', result.stdout)

    def test_checks_fail_without_the_patch(self):
        # Holdout: build B's header loses the tempo range and raises the
        # dialog on a late confirmation.
        results = run(('tempo', 'bar_late'), with_fix=False)
        self.assertIn('FAIL tempo_range_index 4 stores [Controls],RateRangePercent 10',
                      results['tempo'].stdout)
        self.assertIn('FAIL a show confirmed late raises no Top bar was not confirmed',
                      results['bar_late'].stdout)


if __name__ == '__main__':
    unittest.main()
