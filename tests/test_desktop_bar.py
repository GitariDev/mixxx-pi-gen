"""Explicit process/IPC doubles only; never operate the real user session."""
import importlib.machinery
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
import json

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
