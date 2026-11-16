"""Explicit process/IPC doubles only; never operate the real user session."""
import importlib.machinery
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
import json
import configparser

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('desktop_bar', str(
    ROOT / 'stage3/02-desktop/files/bin/mixpi-desktop-bar'))
spec = importlib.util.spec_from_loader(loader.name, loader)
BAR = importlib.util.module_from_spec(spec)
loader.exec_module(BAR)


class DesktopBarTests(unittest.TestCase):
    def observation(self, visible, inset=None):
        return [
            'LoadState=loaded\nActiveState=' + ('active\nSubState=running\nMainPID=91' if visible
                                              else 'inactive\nSubState=dead\nMainPID=0'),
            json.dumps([{'focused': True, 'output': 'panel', 'rect': {'y':
                        (36 if visible else 0) if inset is None else inset}}]),
            json.dumps([{'name': 'panel', 'active': True, 'rect': {'y': 0}}])]

    def test_show_hide_restore_and_fixed_arguments(self):
        responses = self.observation(True) + [''] + self.observation(False)
        responses += self.observation(False) + [''] + self.observation(True)
        calls = []
        def run(arguments, **options):
            calls.append(arguments)
            self.assertNotIn('shell', options)
            return subprocess.CompletedProcess(arguments, 0, responses.pop(0), '')
        with patch.object(BAR.subprocess, 'run', side_effect=run):
            self.assertEqual(BAR.change('hide')['reserved_px'], 0)
            self.assertEqual(BAR.change('show')['reserved_px'], 36)
        self.assertIn(['/usr/bin/systemctl', '--user', 'stop', 'waybar.service'], calls)
        self.assertIn(['/usr/bin/systemctl', '--user', 'start', 'waybar.service'], calls)
        self.assertFalse(responses)

    def test_service_error_is_not_visibility_success(self):
        responses = self.observation(True)
        def run(arguments, **options):
            if responses:
                return subprocess.CompletedProcess(arguments, 0, responses.pop(0), '')
            return subprocess.CompletedProcess(arguments, 1, '', 'permission denied')
        with patch.object(BAR.subprocess, 'run', side_effect=run):
            with self.assertRaisesRegex(BAR.BarError, 'permission denied'):
                BAR.change('hide')

    def test_reserved_geometry_disagreement_and_malformed_ipc(self):
        for responses in (self.observation(True, 0), ['LoadState=not-found'],
                          self.observation(False, 36),
                          [self.observation(True)[0], 'not JSON', '[]']):
            with self.subTest(responses=responses), patch.object(BAR, 'command', side_effect=responses):
                with self.assertRaises(BAR.BarError):
                    BAR.observe()

    def test_noop_does_not_restart_service(self):
        with patch.object(BAR, 'command', side_effect=self.observation(True)) as command:
            self.assertTrue(BAR.change('show')['visible'])
            self.assertEqual(command.call_count, 3)

    def test_timeout_is_explicit_failure(self):
        with patch.object(BAR.subprocess, 'run', side_effect=subprocess.TimeoutExpired('double', 3)):
            with self.assertRaisesRegex(BAR.BarError, 'unavailable'):
                BAR.observe()

    def test_root_and_missing_session_refused_before_commands(self):
        with patch.object(BAR.subprocess, 'run') as run, patch.object(BAR.os, 'geteuid', return_value=0):
            self.assertEqual(BAR.main(['hide']), 1)
            run.assert_not_called()

    def test_arbitrary_arguments_rejected(self):
        with patch.object(BAR.subprocess, 'run') as run:
            with self.assertRaises(SystemExit):
                BAR.main(['hide; reboot'])
            run.assert_not_called()

    def test_unconfirmed_transition_never_reports_success(self):
        responses = self.observation(True) + [''] + self.observation(True) * 8
        with patch.object(BAR, 'command', side_effect=responses), patch.object(BAR.time, 'sleep'):
            with self.assertRaisesRegex(BAR.BarError, 'not confirmed'):
                BAR.change('hide')

    def test_failed_service_and_invalid_pid_are_not_hidden_or_shown(self):
        for state in ('LoadState=loaded\nActiveState=failed\nSubState=failed\nMainPID=0',
                      'LoadState=loaded\nActiveState=active\nSubState=running\nMainPID=oops'):
            with self.subTest(state=state), patch.object(BAR, 'command', return_value=state):
                with self.assertRaises(BAR.BarError):
                    BAR.observe()

    def test_missing_session_and_internal_unknown_action_fail_closed(self):
        with patch.object(BAR.os, 'geteuid', return_value=1000), patch.dict(BAR.os.environ, {}, clear=True), \
                patch.object(BAR.subprocess, 'run') as run:
            self.assertEqual(BAR.main(['show']), 1)
            run.assert_not_called()
        with patch.object(BAR, 'command') as command:
            with self.assertRaises(BAR.BarError):
                BAR.change('restart')
            command.assert_not_called()

    def test_holdout_negative_output_origin_and_ambiguous_focus(self):
        responses = self.observation(True)
        responses[1] = json.dumps([{'focused': True, 'output': 'panel', 'rect': {'y': -164}}])
        responses[2] = json.dumps([{'name': 'panel', 'active': True, 'rect': {'y': -200}}])
        with patch.object(BAR, 'command', side_effect=responses):
            self.assertEqual(BAR.observe()['reserved_px'], 36)
        responses = self.observation(False)
        responses[1] = json.dumps([{'focused': True}, {'focused': True}])
        with patch.object(BAR, 'command', side_effect=responses):
            with self.assertRaisesRegex(BAR.BarError, 'unique focused'):
                BAR.observe()


class DesktopBarStateReportingTests(unittest.TestCase):
    """A bar that is failed or restarting is never reported as shown, hidden or available."""

    def test_failed_and_restarting_report_unavailable(self):
        for state in ('LoadState=loaded\nActiveState=activating\nSubState=start\nMainPID=0',
                      'LoadState=loaded\nActiveState=activating\nSubState=auto-restart\nMainPID=0',
                      'LoadState=loaded\nActiveState=failed\nSubState=failed\nMainPID=0',
                      'LoadState=loaded\nActiveState=deactivating\nSubState=stop-sigterm\nMainPID=7'):
            with self.subTest(state=state), patch.object(BAR, 'command', return_value=state), \
                    patch.object(BAR.os, 'geteuid', return_value=1000), \
                    patch.dict(BAR.os.environ, {'XDG_RUNTIME_DIR': '/run/user/1000',
                                                'SWAYSOCK': '/run/user/1000/sway.sock'}), \
                    patch.object(BAR.os, 'getuid', return_value=1000), \
                    patch('builtins.print') as printed:
                self.assertEqual(BAR.main(['status']), 1)
                report = json.loads(printed.call_args.args[0])
                self.assertIsNone(report['visible'])
                self.assertTrue(report['error'])

    def test_bar_never_started_after_boot_reports_hidden_and_showable(self):
        state = 'LoadState=loaded\nActiveState=inactive\nSubState=dead\nMainPID=0'
        geometry = [json.dumps([{'focused': True, 'output': 'DSI-1', 'rect': {'y': 0}}]),
                    json.dumps([{'name': 'DSI-1', 'active': True, 'rect': {'y': 0}}])]
        with patch.object(BAR, 'command', side_effect=[state] + geometry):
            self.assertEqual(BAR.change('status'), {'visible': False, 'reserved_px': 0, 'error': ''})


def code_lines(path):
    return [line.strip() for line in path.read_text().splitlines()
            if line.strip() and not line.strip().startswith('#')]


class SessionStartStageTests(unittest.TestCase):
    """F-14: one ordered session start, the bar hidden after boot, no wlr portal."""

    def test_one_ordered_start_line_and_no_waybar_autostart(self):
        lines = code_lines(ROOT / 'stage3/02-desktop/files/i3.conf')
        starts = [line for line in lines if 'sway-session' in line]
        self.assertEqual(starts, [
            "exec --no-startup-id sh -c 'dbus-update-activation-environment --systemd "
            "WAYLAND_DISPLAY XDG_CURRENT_DESKTOP XDG_SESSION_TYPE SWAYSOCK; "
            "exec systemctl --user start sway-session.service'"])
        self.assertEqual([line for line in lines if 'dbus-update-activation-environment' in line], starts)
        self.assertEqual([line for line in lines if 'waybar' in line], [])

    def test_image_disables_the_waybar_package_autostart(self):
        lines = code_lines(ROOT / 'stage3/04-enable-wayland/01-run.sh')
        self.assertIn('systemctl --global disable waybar.service', lines)
        # Only the Settings helper (mixpi-desktop-bar) starts the bar.
        session = list(ROOT.glob('stage*/**/*run.sh')) + list(ROOT.glob('stage*/**/systemd/**/*'))
        session.append(ROOT / 'stage3/02-desktop/files/i3.conf')
        for path in session:
            if path.is_file():
                with self.subTest(path=str(path.relative_to(ROOT))):
                    self.assertNotRegex(path.read_text(),
                                        r'(?m)^[^#\n]*(enable|start)[^\n]*waybar')

    def test_wlr_portal_removed_from_packages_and_portal_config(self):
        packages = (ROOT / 'stage3/01-install-packages/00-packages').read_text().split()
        self.assertIn('xdg-desktop-portal', packages)
        self.assertIn('xdg-desktop-portal-gtk', packages)
        self.assertNotIn('xdg-desktop-portal-wlr', packages)
        for path in ROOT.glob('stage*/**/*'):
            if path.is_file() and path.suffix != '.patch' and '__pycache__' not in path.parts:
                with self.subTest(path=str(path.relative_to(ROOT))):
                    self.assertNotIn('xdg-desktop-portal-wlr', path.read_text(errors='replace'))
        portal = configparser.ConfigParser()
        portal.optionxform = str
        portal.read(ROOT / 'stage3/02-desktop/files/xdg-desktop-portal-sway.conf')
        self.assertEqual(dict(portal['preferred']), {'default': 'gtk'})


class SettingsButtonStateTests(unittest.TestCase):
    """Acceptance finding 5 (F-14): after Show top bar, Hide top bar stayed grey.

    The skin binds the button's enabled state to [MixPi],desktop_bar_available
    and its label to [MixPi],desktop_bar. Before mixxx-acceptance-fixes.patch
    every 5 s status poll set desktop_bar_available to 0 while the label kept
    "Hide top bar". The native check is the desktop_bar scenario in
    tests/test_performance_settings.py; this one pins the text of both sides.
    """

    def added_lines(self):
        patch = (ROOT / 'stage3/01-install-packages/files/mixxx-acceptance-fixes.patch').read_text()
        section = patch[patch.index('diff --git a/src/widget/mixpiperformancesettings.h'):]
        end = section.find('\ndiff --git', 1)
        section = section if end < 0 else section[:end]
        return section, [line[1:] for line in section.splitlines()
                         if line.startswith('+') and not line.startswith('+++')]

    def test_status_poll_no_longer_lowers_availability(self):
        section, added = self.added_lines()
        removed = [line[1:].strip() for line in section.splitlines()
                   if line.startswith('-') and not line.startswith('---')]
        self.assertIn('m_barAvailable->set(0);', removed)
        text = '\n'.join(added)
        self.assertIn('if (changing) {\n            m_barAvailable->set(0);\n'
                      '            m_bar->setAndConfirm(2);\n        }', text)
        # A tap during a poll is kept and run when the poll ends.
        self.assertIn('m_barRequested = true;', text)
        self.assertIn('if (requested && valid) {', text)

    def test_skin_binds_label_and_enabled_state_to_the_two_controls(self):
        generator = (ROOT / 'stage3/01-install-packages/files/mixpi-performance.py').read_text()
        self.assertIn("connection(bar, '[MixPi],desktop_bar_available', bind='enabled')", generator)
        self.assertIn("state_labels=('Show top bar', 'Hide top bar', 'Checking top bar…',", generator)
