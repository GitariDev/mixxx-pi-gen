"""Recipe-level guards for the native settings patch, not audio acceptance."""
from pathlib import Path
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import unittest
from native.library_interface_runner import (qt_available, qt_flags, qt_environment, moc_path, source_reference,
                                             pinned_bytes)

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / 'stage3/01-install-packages/files/mixxx-performance-settings.patch'


def added_source(path, patch=PATCH):
    active = False
    lines = []
    for line in patch.read_text().splitlines():
        if line.startswith('diff --git '):
            active = line.endswith(' b/' + path)
        elif active and line.startswith('+') and not line.startswith('+++'):
            lines.append(line[1:])
    return '\n'.join(lines)


class PerformanceSettingsTests(unittest.TestCase):
    def setUp(self):
        self.header = added_source('src/widget/mixpiperformancesettings.h')

    def test_native_capability_is_published_after_initial_refresh(self):
        self.assertIn('new MixpiPerformanceSettings(this, pConfig,',
                      added_source('src/mixxxmainwindow.cpp'))
        self.assertIn('refresh();\n        control("settings_available")->set(1);', self.header)

    def test_buffer_requires_idle_players_and_confirmation(self):
        self.assertIn('"[Recording]", "status"', self.header)
        for player in ('Channel', 'Sampler', 'PreviewDeck'):
            self.assertIn(f'QStringLiteral("{player}")', self.header)
        self.assertIn('m_changing || !supportsBuffer() || !playersStopped()', self.header)
        self.assertIn('confirm.setDefaultButton(QMessageBox::Cancel)', self.header)
        self.assertIn('if (confirm.exec() == QMessageBox::Ok)', self.header)
        self.assertIn('if (!playersStopped() || m_sound->getConfig().getAPI()', self.header)
        self.assertIn('m_sound->setConfig(previous)', self.header)

    def test_buffer_conversion_uses_native_frame_calculation(self):
        self.assertIn('candidate.getFramesPerBuffer()', self.header)
        self.assertIn('m_buffer->setAndConfirm(cfg.getFramesPerBuffer())', self.header)
        self.assertNotIn('firstFrames', self.header)

    def test_next_launch_settings_and_explicit_overrides_are_kept(self):
        core = added_source('src/coreservices.cpp')
        for environment in ('MIXPI_READAHEAD_CHUNKS', 'MIXPI_RAM_CACHE_MAX_MB'):
            self.assertIn(f'if (!qEnvironmentVariableIsSet("{environment}"))', core)
        self.assertIn('"ReadAheadChunks", "MIXPI_READAHEAD_CHUNKS"', self.header)
        self.assertIn('"RamCacheMB", "MIXPI_RAM_CACHE_MAX_MB"', self.header)
        self.assertIn('v < 0 || v > 1024', self.header)

    def test_read_ahead_is_initialized_before_audio_callbacks(self):
        source = added_source('src/engine/readaheadmanager.cpp')
        self.assertIn('static const int chunksAtStartup', source)
        self.assertEqual(source.count('m_readAheadChunks(readAheadChunks())'), 2)
        self.assertIn('m_readAheadChunks * CachingReaderChunk::kFrames', source)


class PreferencesEntryTests(unittest.TestCase):
    def test_preferences_request_queues_the_main_window_slot(self):
        source = added_source('src/widget/mixpiperformancesettings.h',
                              ROOT / 'stage3/01-install-packages/files/mixxx-preferences-entry.patch')
        self.assertIn('control("show_preferences")', source)
        self.assertIn('std::isfinite(v) && v > 0 && m_window && !m_preferencesQueued', source)
        self.assertIn('}, Qt::QueuedConnection);', source)
        self.assertIn('QMetaObject::invokeMethod(m_window, "slotOptionsPreferences",', source)
        self.assertIn('preferences->setAndConfirm(0);', source)


# Prints what mixpi-desktop-bar prints; "status" can be slow, as on the Pi.
FAKE_DESKTOP_BAR = '''#!/bin/sh
echo "$1" >> "$MIXPI_FAKE_BAR_DIR/calls"
state=$(cat "$MIXPI_FAKE_BAR_DIR/state" 2>/dev/null || echo hidden)
case "$1" in
    show) state=visible ;;
    hide) state=hidden ;;
    status) sleep "${MIXPI_FAKE_BAR_DELAY:-0}" ;;
esac
echo "$state" > "$MIXPI_FAKE_BAR_DIR/state"
if [ "$state" = visible ]; then
    echo '{"visible": true, "reserved_px": 36, "error": ""}'
else
    echo '{"visible": false, "reserved_px": 0, "error": ""}'
fi
'''


class NativePerformanceSettingsTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('MIXXX_TEST_SOURCE'), 'pinned source required')
    def test_pinned_main_window_preferences_slot_is_public(self):
        # The patch invokes this slot by name; moc only exposes declared slots.
        header = pinned_bytes('src/mixxxmainwindow.h').decode()
        self.assertIn('class MixxxMainWindow : public QMainWindow {\n    Q_OBJECT', header)
        slots = header.index('  public slots:')
        self.assertLess(slots, header.index('    void slotOptionsPreferences();'))
        self.assertNotIn('  private', header[slots:header.index('    void slotOptionsPreferences();')])
        self.assertNotIn('  protected', header[slots:header.index('    void slotOptionsPreferences();')])


    def test_real_qt_control_requests_and_publication(self):
        if not qt_available():
            self.skipTest('native Qt6 development dependencies required')
        self.run_framework_tests()

    def run_framework_tests(self):
        source = source_reference()
        with tempfile.TemporaryDirectory(prefix='mixpi-settings-framework-') as directory:
            target = Path(directory)
            subprocess.run([sys.executable, str(ROOT / 'tests/native/prepare_performance_settings.py'),
                            '--source', str(source), '--output', str(target)],
                           check=True, timeout=30)
            for name in ('control', 'controlobject', 'controlproxy'):
                subprocess.run([moc_path(),
                                str(target / f'production/control/{name}.h'),
                                '-o', str(target / f'production/control/moc_{name}.cpp')],
                               check=True, timeout=30)
            subprocess.run([moc_path(), str(target / 'performance_settings_window.h'),
                            '-o', str(target / 'moc_performance_settings_window.cpp')],
                           check=True, timeout=30)
            command = ['c++', '-std=c++20', '-I' + str(target),
                       '-I' + str(target / 'doubles'), '-I' + str(target / 'production')]
            command += [str(target / 'performance_settings_test.cpp'),
                        str(target / 'moc_performance_settings_window.cpp')]
            command += [str(target / f'production/control/{name}.cpp')
                        for name in ('control', 'controlobject', 'controlproxy')]
            command += ['-o', str(target / 'settings-test'), *qt_flags()]
            subprocess.run(command, check=True, timeout=90)
            environment = qt_environment()
            for scenario in ('initial', 'periodic', 'requests', 'invalid', 'buffer',
                             'buffer_mapping', 'semantics', 'startup', 'preferences'):
                result = subprocess.run([str(target / 'settings-test'), scenario], env=environment,
                                        capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                print(result.stdout.strip())
            # F-14: Show/Hide top bar against a fake helper (process double only).
            fake = target / 'fake-bar'
            fake.mkdir()
            helper = fake / 'mixpi-desktop-bar'
            helper.write_text(FAKE_DESKTOP_BAR)
            helper.chmod(0o755)
            result = subprocess.run([str(target / 'settings-test'), 'desktop_bar'],
                                    env=dict(environment, MIXPI_DESKTOP_BAR_HELPER=str(helper),
                                             MIXPI_FAKE_BAR_DIR=str(fake)),
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('PASS desktop_bar', result.stdout)
            print(result.stdout.strip())


if __name__ == '__main__':
    unittest.main()
