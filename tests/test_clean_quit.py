"""Option A: a stop/reboot SIGTERM quits Mixxx as File > Exit does, so it saves.

Field evidence: deploy/recovery-20261116-fixes/field-fix-acceptance-b2
finding 1 (a service stop lost mixxx.cfg and samplers.xml).
"""
import configparser
import importlib.util
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import unittest

from native.library_interface_runner import qt_available

ROOT = Path(__file__).resolve().parents[1]
PATCH_NAME = 'mixxx-clean-quit.patch'
PATCH = ROOT / 'stage3/01-install-packages/files' / PATCH_NAME
UNIT = ROOT / 'stage3/02-desktop/files/systemd/user/mixpi-mixxx.service'
# The pinned systemd user manager stops units after DefaultTimeoutStopSec
# (90 s); the Mixxx bound must sit well inside it.
STOP_BOUND_SECONDS = 20


def runner():
    spec = importlib.util.spec_from_file_location(
        'clean_quit_runner', ROOT / 'tests/native/clean_quit_runner.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def service_problems(text):
    parser = configparser.ConfigParser(strict=False, interpolation=None)
    parser.optionxform = str
    parser.read_string(text)
    service = parser['Service'] if parser.has_section('Service') else {}
    problems = []
    if service.get('ExecStart') != '/usr/bin/mixxx':
        problems.append('Mixxx is not the main process')
    if service.get('KillSignal') != 'SIGTERM':
        problems.append('KillSignal is not SIGTERM')
    if service.get('KillMode') not in ('control-group', 'mixed'):
        problems.append('KillMode does not signal the main process first')
    if service.get('SendSIGKILL', 'yes') != 'yes':
        problems.append('no SIGKILL after the bound')
    if 'ExecStop' in service:
        problems.append('an ExecStop would bypass the SIGTERM quit')
    if service.get('TimeoutStopSec') != f'{STOP_BOUND_SECONDS}s':
        problems.append(f'TimeoutStopSec is not the stated {STOP_BOUND_SECONDS} s bound')
    return problems


def body(text, signature):
    start = text.index(signature)
    opening = text.index('{', start)
    depth = 0
    for index in range(opening, len(text)):
        depth += {'{': 1, '}': -1}.get(text[index], 0)
        if depth == 0:
            return text[opening:index + 1]
    raise ValueError(signature)


def wiring_problems(source):
    """What is missing for SIGTERM/SIGHUP to reach the File > Exit quit path."""
    def read(relative):
        path = source / relative
        return path.read_text() if path.exists() else ''
    main = read('src/main.cpp')
    window = read('src/mixxxmainwindow.cpp')
    header = read('src/mixxxmainwindow.h')
    helper = read('src/util/unixsignalquit.h')
    problems = []
    if not helper:
        return ['src/util/unixsignalquit.h missing']
    handler = re.sub(r'//[^\n]*', '', body(helper, 'static void handle(int signalNumber)'))
    calls = set(re.findall(r'([A-Za-z_:]+)\s*\(', handler)) - {'handle'}
    if calls != {'::write'}:
        problems.append('handler calls more than write(2): ' + repr(sorted(calls)))
    for needed in ('::socketpair(AF_UNIX', 'O_NONBLOCK', 'QSocketNotifier::Read',
                   'SIGTERM, SIGHUP', 'previous.sa_handler == SIG_IGN', 'if (m_quitRequested)'):
        if needed not in helper:
            problems.append('helper lacks ' + needed)
    run = body(main, 'int runMixxx(') if 'int runMixxx(' in main else ''
    order = ['mixxx::UnixSignalQuit signalQuit;', 'std::make_shared<mixxx::CoreServices>',
             'MixxxMainWindow mainWindow(', 'signalQuit.setQuitFunction(',
             'mainWindow.closeWithoutConfirmation();', 'mainWindow.show();',
             'signalQuit.enable();', 'exitCode = pApp->exec();', 'signalQuit.finish();']
    positions, cursor = [], 0
    for item in order:  # each after the previous one
        cursor = run.find(item, cursor)
        positions.append(cursor)
        if cursor < 0:
            break
    if -1 in positions:
        problems.append('runMixxx order wrong: ' + repr(dict(zip(order, positions))))
    if '#include "util/unixsignalquit.h"' not in main:
        problems.append('main.cpp does not include the helper')
    if 'void closeWithoutConfirmation();' not in header or 'bool m_exitConfirmed = false;' not in header:
        problems.append('MixxxMainWindow lacks closeWithoutConfirmation/m_exitConfirmed')
    if 'void MixxxMainWindow::closeWithoutConfirmation()' in window:
        quit = body(window, 'void MixxxMainWindow::closeWithoutConfirmation()')
        if 'm_exitConfirmed = true;' not in quit or 'close()' not in quit:
            problems.append('closeWithoutConfirmation does not close the main window')
    else:
        problems.append('closeWithoutConfirmation missing')
    close_event = body(window, 'void MixxxMainWindow::closeEvent(QCloseEvent *event)')
    if 'if (!m_exitConfirmed && !confirmExit())' not in close_event:
        problems.append('closeEvent still always asks confirmExit')
    # Ctrl+Q / File > Exit must still be close(): both requests share closeEvent.
    if not re.search(r'&WMainMenuBar::quit,\s*this,\s*&MixxxMainWindow::close,', window):
        problems.append('the menu quit no longer calls MixxxMainWindow::close')
    return problems


def quit_saves(source):
    """The pinned shutdown that close() leads to saves both files."""
    core = (source / 'src/coreservices.cpp').read_text()
    players = (source / 'src/mixer/playermanager.cpp').read_text()
    finalize = body(core, 'void CoreServices::finalize()')
    return ('m_pSettingsManager->save();' in finalize and
            'saveSamplerBankToPath(getDefaultSamplerPath(m_pConfig))' in
            body(players, 'PlayerManager::~PlayerManager()'))


class CleanQuitServiceTests(unittest.TestCase):
    def test_unit_gives_mixxx_a_bounded_sigterm_quit(self):
        self.assertEqual(service_problems(UNIT.read_text()), [])

    def test_unit_check_rejects_the_previous_unit(self):
        # The pre-option unit (no stop settings) must fail the same check.
        previous = re.sub(r'^(KillMode|KillSignal|SendSIGKILL|TimeoutStopSec)=.*\n', '',
                          UNIT.read_text(), flags=re.MULTILINE)
        self.assertIn('TimeoutStopSec is not the stated 20 s bound', service_problems(previous))
        self.assertIn('KillSignal is not SIGTERM', service_problems(previous))

    def test_patch_is_last_and_adds_only_the_quit_files(self):
        names = subprocess.run(['bash', str(ROOT / 'stage3/01-install-packages/01-run.sh'),
                                '--mixxx-print-patches'], capture_output=True, text=True,
                               check=True).stdout.split()
        self.assertEqual(names[-1], PATCH_NAME)
        self.assertEqual(re.findall(r'^diff --git a/(\S+) ', PATCH.read_text(), re.MULTILINE),
                         ['src/main.cpp', 'src/mixxxmainwindow.cpp', 'src/mixxxmainwindow.h',
                          'src/util/unixsignalquit.h'])


@unittest.skipUnless(os.environ.get('MIXXX_TEST_SOURCE'), 'MIXXX_TEST_SOURCE required')
class CleanQuitWiringTests(unittest.TestCase):
    def reconstructed(self, directory, without=False):
        module = runner().reconstruction()
        directory.mkdir(parents=True, exist_ok=True)
        module.reconstruct(directory, exclude=(PATCH_NAME,) if without else ())
        module.populate_pinned(directory, ['src/main.cpp', 'src/mixxxmainwindow.cpp',
                                           'src/mixxxmainwindow.h', 'src/coreservices.cpp',
                                           'src/mixer/playermanager.cpp'])
        return directory

    def test_patched_source_wires_signals_into_the_menu_quit_path(self):
        with tempfile.TemporaryDirectory(prefix='mixpi-clean-quit-wiring-') as directory:
            source = self.reconstructed(Path(directory))
            self.assertEqual(wiring_problems(source), [])
            self.assertTrue(quit_saves(source))

    def test_wiring_check_fails_without_the_patch(self):
        with tempfile.TemporaryDirectory(prefix='mixpi-clean-quit-unwired-') as directory:
            source = self.reconstructed(Path(directory) / 'without', without=True)
            self.assertEqual(wiring_problems(source), ['src/util/unixsignalquit.h missing'])
            # The helper alone is not enough: main.cpp and the window must use it.
            patched = self.reconstructed(Path(directory) / 'with')
            (source / 'src/util').mkdir(parents=True, exist_ok=True)
            (source / 'src/util/unixsignalquit.h').write_bytes(
                (patched / 'src/util/unixsignalquit.h').read_bytes())
            problems = wiring_problems(source)
            self.assertIn('main.cpp does not include the helper', problems)
            self.assertIn('closeEvent still always asks confirmExit', problems)
            self.assertTrue(quit_saves(source))


@unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
class NativeCleanQuitTests(unittest.TestCase):
    def test_signals_reach_the_quit_function_exactly_once(self):
        for mode, result in zip(runner().MODES, runner().run()):
            with self.subTest(mode=mode):
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('PASS the quit function ran exactly once', result.stdout)
                self.assertIn('PASS a second SIGTERM and a SIGHUP during shutdown do nothing',
                              result.stdout)
                self.assertIn('FAILURES 0', result.stdout)

    def test_pinned_app_is_killed_by_the_same_signals(self):
        for mode, result in zip(runner().MODES, runner().run(without_clean_quit=True)):
            with self.subTest(mode=mode):
                expected = signal.SIGHUP if mode == 'hup' else signal.SIGTERM
                self.assertEqual(result.returncode, -expected, result.stdout + result.stderr)
                self.assertNotIn('the quit function ran exactly once', result.stdout)


if __name__ == '__main__':
    unittest.main()
