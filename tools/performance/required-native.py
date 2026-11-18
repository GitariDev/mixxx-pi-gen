#!/usr/bin/env python3
"""Required current-recipe Linux Qt/IPC gate; missing inputs and skips fail."""
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests'))
from native.library_interface_runner import source_reference, source_pin, qt_flags, moc_path, sndfile_flags

REQUIRED_TESTS = (
    'test_native_harness',
    'test_ram_cache_identity',
    'test_import_cancellation',
    'test_media_transfer_reporting',
    'test_media_copy_ipc',
    'test_media_transfer_display',
    'test_media_activity',
    'test_media_controlled_gui',
    'test_media_continuation',
    'test_rekordbox_analysis',
    'test_library_interface',
    'test_recording_lifecycle',
    'test_key_widget',
    'test_position_display',
    'test_initial_library.InitialLibraryNativeTests',
    'test_effect_placeholder',
    'test_runtime_selection_probe',
    'test_performance_settings.NativePerformanceSettingsTests',
    'test_table_columns',
    'test_clean_quit',
    'test_save_on_change',
    'test_quiet_scan',
    'test_scan_progress',
    'test_sources_screen',
    'test_media_screen',
    'test_media_handover',
    'test_media_agreed',
    'test_effects_save',
    'test_agreed_controls',
    'test_sample_browser',
    'test_source_groups',
    'test_settings_fixes',
    'test_shared_columns',
)
FORBIDDEN_OVERRIDES = (
    'TRANSFER_REPORTING_BASELINE', 'RECORDING_LIFECYCLE_BASELINE',
    'MEDIA_ACTIVITY_BASELINE', 'MEDIA_ACTIVITY_SOURCE', 'MIXPI_EFFECT_BASELINE',
    'MIXXX_IMPORT_CANCELLATION_PATCH',
)


def prerequisites():
    if platform.system() != 'Linux':
        raise RuntimeError('Required Linux native/peer-pidfd gate cannot run on ' + platform.system())
    for tool in ('git', 'c++', 'pkg-config'):
        if not shutil.which(tool):
            raise RuntimeError('Required native tool missing: ' + tool)
    for name in FORBIDDEN_OVERRIDES:
        if name in os.environ:
            raise RuntimeError('Current-recipe gate refuses override: ' + name)
    if not hasattr(os, 'pidfd_open'):
        raise RuntimeError('Python/kernel peer-pidfd support is required')
    descriptor = os.pidfd_open(os.getpid())
    os.close(descriptor)
    reference = source_reference()
    qt_flags(('QtCore', 'QtGui', 'QtWidgets', 'QtXml', 'QtTest', 'QtSql', 'QtConcurrent'))
    moc_path()
    sndfile_flags()
    os.environ['MIXXX_TEST_SOURCE'] = str(reference)
    print('SOURCE', reference, 'PIN', source_pin(), flush=True)


def required_suite(loader=None):
    loader = loader or unittest.defaultTestLoader
    suite = unittest.TestSuite()
    for name in REQUIRED_TESTS:
        tests = loader.loadTestsFromName(name)
        if tests.countTestCases() == 0:
            raise RuntimeError('Required native check is empty: ' + name)
        suite.addTests(tests)
    return suite


def run_required(suite, stream=None):
    if suite.countTestCases() == 0:
        raise RuntimeError('Required native suite is empty')
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    if result.skipped:
        print('Required native checks refuse skips:', result.skipped, file=sys.stderr)
    return result.wasSuccessful() and not result.skipped and not result.expectedFailures


def main():
    try:
        prerequisites()
        for runner in ('library_interface_runner.py', 'run_right_overlay.py'):
            for options in ([], ['--holdout']):
                subprocess.run([sys.executable, '-B', str(ROOT / 'tests/native' / runner), *options],
                               cwd=ROOT, check=True, timeout=180)
        suite = required_suite()
        return 0 if run_required(suite) else 1
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print('REQUIRED NATIVE FAILED:', error, file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
