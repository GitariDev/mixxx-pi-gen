"""R-14: a reboot or power-off stops Mixxx before LightDM and the user manager.

Without this, the session (sway under LightDM) stops before pi's user manager
stops mixpi-mixxx.service; Mixxx then loses its Wayland connection and exits
without the File > Exit save (EV/owner-options/README.txt, confirmed on VM b).
mixpi-mixxx-stop.service is ordered after both, so systemd runs its stop first.
"""
import configparser
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / 'stage3/02-desktop'
UNIT = DESKTOP / 'files/systemd/mixpi-mixxx-stop.service'
HELPER = DESKTOP / 'files/sbin/mixpi-stop-mixxx'
MIXXX_UNIT = DESKTOP / 'files/systemd/user/mixpi-mixxx.service'
STAGE = DESKTOP / '02-run.sh'


def sections(text):
    parser = configparser.ConfigParser(strict=False, interpolation=None)
    parser.optionxform = str
    parser.read_string(text)
    return parser


def unit_problems(text):
    parser = sections(text)
    unit = parser['Unit'] if parser.has_section('Unit') else {}
    service = parser['Service'] if parser.has_section('Service') else {}
    install = parser['Install'] if parser.has_section('Install') else {}
    after = set(unit.get('After', '').split())
    problems = []
    for name in ('lightdm.service', 'user@1000.service'):
        if name not in after:
            problems.append('not ordered after ' + name)
    if unit.get('DefaultDependencies', 'yes') != 'yes':
        problems.append('no default dependencies: not stopped before shutdown.target')
    expected = {'Type': 'oneshot', 'RemainAfterExit': 'yes', 'ExecStart': '/bin/true',
                'ExecStop': '/usr/local/sbin/mixpi-stop-mixxx', 'TimeoutStopSec': '25'}
    for key, value in expected.items():
        if service.get(key) != value:
            problems.append(f'{key} is not {value}')
    if install.get('WantedBy') != 'multi-user.target':
        problems.append('not wanted by multi-user.target')
    return problems


def seconds(value):
    return int(re.fullmatch(r'(\d+)s?', value)[1])


class StopUnitTests(unittest.TestCase):
    def test_unit_stops_mixxx_before_lightdm_and_the_user_manager(self):
        self.assertEqual(unit_problems(UNIT.read_text()), [])

    def test_check_rejects_a_unit_without_the_order(self):
        text = re.sub(r'^After=.*\n', '', UNIT.read_text(), flags=re.MULTILINE)
        self.assertEqual(unit_problems(text), ['not ordered after lightdm.service',
                                               'not ordered after user@1000.service'])

    def test_stop_bound_covers_the_mixxx_sigkill_bound(self):
        mixxx = sections(MIXXX_UNIT.read_text())['Service']
        ours = sections(UNIT.read_text())['Service']
        self.assertLess(seconds(mixxx['TimeoutStopSec']), seconds(ours['TimeoutStopSec']))

    def test_helper_is_executable_by_root_only_and_names_one_unit(self):
        mode = stat.S_IMODE(HELPER.stat().st_mode)
        self.assertEqual(mode & 0o111, 0o111)
        self.assertEqual(mode & 0o022, 0)
        text = HELPER.read_text()
        self.assertTrue(text.startswith('#!/bin/sh\n'))
        self.assertEqual(re.findall(r'^UNIT=(.*)$', text, re.MULTILINE), ['mixpi-mixxx.service'])
        self.assertEqual(re.findall(r'^USER_NAME=(.*)$', text, re.MULTILINE), ['pi'])
        subprocess.run(['sh', '-n', str(HELPER)], check=True)


class StageInstallTests(unittest.TestCase):
    def run_stage(self, rootfs):
        # The real stage, with chroot paths redirected and ownership stubbed,
        # as tests/test_image_runtime.py runs it.
        harness = r'''
        chown() { :; }
        export -f chown
        on_chroot() {
            local commands
            commands=$(cat)
            commands=${commands//\/home\/pi/$ROOTFS_DIR\/home\/pi}
            bash -eu -c "$commands"
        }
        source "$1"
        '''
        subprocess.run(['bash', '-eu', '-c', harness, 'image-test', str(STAGE)],
                       cwd=STAGE.parent, env={**os.environ, 'ROOTFS_DIR': str(rootfs)},
                       check=True, capture_output=True)

    def test_stage_installs_and_enables_the_unit_and_helper(self):
        with tempfile.TemporaryDirectory() as directory:
            rootfs = Path(directory)
            (rootfs / 'home/pi/.config').mkdir(parents=True)
            for _ in range(2):  # a second run of the stage changes nothing
                self.run_stage(rootfs)
                helper = rootfs / 'usr/local/sbin/mixpi-stop-mixxx'
                unit = rootfs / 'etc/systemd/system/mixpi-mixxx-stop.service'
                link = rootfs / 'etc/systemd/system/multi-user.target.wants/mixpi-mixxx-stop.service'
                self.assertEqual(helper.read_bytes(), HELPER.read_bytes())
                self.assertEqual(stat.S_IMODE(helper.stat().st_mode), 0o755)
                self.assertEqual(unit.read_bytes(), UNIT.read_bytes())
                self.assertEqual(stat.S_IMODE(unit.stat().st_mode), 0o644)
                self.assertEqual(os.readlink(link), '/etc/systemd/system/mixpi-mixxx-stop.service')

    def test_stage_leaves_the_helper_owned_by_root(self):
        # pi-gen runs the stage as root; only home folders are handed to pi.
        for line in STAGE.read_text().splitlines():
            if 'chown' in line:
                self.assertNotRegex(line, r'/usr/local/sbin|/etc/systemd')


class HelperBehaviourTests(unittest.TestCase):
    """The shipped helper with systemctl, runuser and id replaced by recorders."""

    def setUp(self):
        self.directory = Path(tempfile.mkdtemp(prefix='mpstop-', dir='/tmp'))
        self.addCleanup(subprocess.run, ['rm', '-rf', str(self.directory)])
        self.log = self.directory / 'calls'
        self.state = self.directory / 'state'
        bin_dir = self.directory / 'bin'
        bin_dir.mkdir()
        self.stub(bin_dir / 'id', '[ "$1 $2" = "-u pi" ] && echo 1000 || exit 1\n')
        self.stub(bin_dir / 'sleep', ':\n')
        self.stub(bin_dir / 'runuser',
                  'echo "runuser $*" >> "$CALLS"\n'
                  '[ "$1 $2 $3" = "-u pi --" ] || exit 9\n'
                  'shift 3\nexec "$@"\n')
        # show: the next state from the state file (one per line, the last one
        # repeats); stop: replace the states with what the stop leads to.
        self.stub(bin_dir / 'systemctl',
                  'echo "systemctl XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR $*" >> "$CALLS"\n'
                  'case "$2" in\n'
                  'show) head -n 1 "$STATE"; [ "$(wc -l < "$STATE")" -gt 1 ] && '
                  'sed -i.bak 1d "$STATE"; exit 0 ;;\n'
                  'stop) cp "$AFTER_STOP" "$STATE"; exit 0 ;;\n'
                  'esac\nexit 3\n')
        self.runtime = self.directory / 'run'
        text = HELPER.read_text()
        text = text.replace('RUNTIME_BASE=/run/user', f'RUNTIME_BASE={self.runtime}')
        text = text.replace('SYSTEMCTL=/usr/bin/systemctl', f'SYSTEMCTL={bin_dir}/systemctl')
        text = text.replace('RUNUSER=/usr/sbin/runuser', f'RUNUSER={bin_dir}/runuser')
        text = text.replace('WAIT_SECONDS=22', 'WAIT_SECONDS=3')
        self.helper = self.directory / 'mixpi-stop-mixxx'
        self.helper.write_text(text)
        self.environment = {'PATH': f'{bin_dir}:/usr/bin:/bin', 'CALLS': str(self.log),
                            'STATE': str(self.state), 'AFTER_STOP': str(self.directory / 'after')}

    def stub(self, path, body):
        path.write_text('#!/bin/sh\n' + body)
        path.chmod(0o755)

    def user_manager(self):
        (self.runtime / '1000/systemd').mkdir(parents=True)
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(str(self.runtime / '1000/systemd/private'))
        self.addCleanup(listener.close)

    def run_helper(self, states, after_stop, *arguments):
        self.state.write_text(''.join(state + '\n' for state in states))
        (self.directory / 'after').write_text(''.join(state + '\n' for state in after_stop))
        result = subprocess.run(['sh', str(self.helper), *arguments], env=self.environment,
                                capture_output=True, text=True, timeout=30)
        calls = self.log.read_text().splitlines() if self.log.exists() else []
        return result, calls

    def stops(self, calls):
        return [call for call in calls if call.startswith('systemctl') and ' stop ' in call + ' ']

    def test_running_mixxx_is_stopped_as_pi_and_waited_for(self):
        self.user_manager()
        result, calls = self.run_helper(['active'], ['deactivating', 'deactivating', 'inactive'])
        self.assertEqual(result.returncode, 0, result.stderr)
        runtime = self.runtime / '1000'
        self.assertEqual(self.stops(calls),
                         [f'systemctl XDG_RUNTIME_DIR={runtime} --user stop mixpi-mixxx.service'])
        self.assertTrue(all(call.startswith('runuser -u pi -- env XDG_RUNTIME_DIR=')
                            for call in calls if call.startswith('runuser')))
        # It returned only after the unit was seen inactive.
        self.assertEqual(self.state.read_text(), 'inactive\n')
        self.assertIn('mixpi-mixxx.service is inactive', result.stdout)

    def test_named_unit_is_accepted(self):
        self.user_manager()
        result, calls = self.run_helper(['active'], ['inactive'], 'mixpi-mixxx.service')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.stops(calls)), 1)

    def test_nothing_happens_when_mixxx_is_not_running(self):
        self.user_manager()
        for state in ('inactive', 'failed'):
            with self.subTest(state=state):
                result, calls = self.run_helper([state], [state])
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.stops(calls), [])

    def test_nothing_happens_without_a_user_manager(self):
        result, calls = self.run_helper(['active'], ['inactive'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, [])

    def test_any_other_unit_is_refused(self):
        self.user_manager()
        for arguments in (['sway-session.service'], ['mixpi-mixxx.service', 'lightdm.service'],
                          ['mixpi-mixxx']):
            with self.subTest(arguments=arguments):
                result, calls = self.run_helper(['active'], ['inactive'], *arguments)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(calls, [])

    def test_a_stop_that_never_ends_returns_after_the_bound(self):
        self.user_manager()
        result, calls = self.run_helper(['active'], ['deactivating'])
        self.assertEqual(result.returncode, 1)
        self.assertIn('still not inactive', result.stderr)
        self.assertEqual(len(self.stops(calls)), 1)


if __name__ == '__main__':
    unittest.main()
