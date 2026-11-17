"""R-14: a reboot or power-off waits until Mixxx has quit and saved.

Without this, the LightDM session scope (sway) and pi's mixpi-mixxx.service
stop together; Mixxx loses its Wayland connection and exits without the
File > Exit save. An After= cannot help: the scope's name is dynamic and the
stop jobs ran in parallel on the card (deploy/ui-redesign-20261117/buildA-checks/
r14-*.txt). mixpi-mixxx-stop.service holds a logind delay inhibitor; logind
emits PrepareForShutdown(true) and waits for it before it stops anything, and
the helper stops Mixxx and exits, which releases it.
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
LOGIND_DROPIN = DESKTOP / 'files/logind/50-mixpi-inhibit.conf'
INHIBIT = ('/usr/bin/systemd-inhibit --what=shutdown --mode=delay --who=MixPi '
           '"--why=Saving Mixxx settings" /usr/local/sbin/mixpi-stop-mixxx --wait-for-shutdown')
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
    for name in ('systemd-logind.service', 'lightdm.service', 'user@1000.service'):
        if name not in after:
            problems.append('not ordered after ' + name)
    if unit.get('DefaultDependencies', 'yes') != 'yes':
        problems.append('no default dependencies: not stopped before shutdown.target')
    if unit.get('StartLimitIntervalSec') != '0':
        problems.append('restarts can hit the start limit')
    expected = {'Type': 'simple', 'ExecStart': INHIBIT,
                'ExecStop': '/usr/local/sbin/mixpi-stop-mixxx', 'Restart': 'always',
                'TimeoutStopSec': '25'}
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
        self.assertEqual(unit_problems(text), ['not ordered after systemd-logind.service',
                                               'not ordered after lightdm.service',
                                               'not ordered after user@1000.service'])

    def test_check_rejects_the_build_a_unit(self):
        # Build A ran a oneshot with only an ExecStop; on the card the session
        # scope stopped at the same time and Mixxx did not save.
        text = UNIT.read_text().replace(INHIBIT, '/bin/true')
        self.assertIn('ExecStart is not ' + INHIBIT, unit_problems(text))

    def test_logind_waits_long_enough_for_the_quit(self):
        login = sections(LOGIND_DROPIN.read_text())['Login']
        self.assertEqual(dict(login), {'InhibitDelayMaxSec': '20'})
        # The inhibitor's own stop bound must not be shorter than logind's.
        mixxx = sections(MIXXX_UNIT.read_text())['Service']
        self.assertLessEqual(seconds(mixxx['TimeoutStopSec']), seconds(login['InhibitDelayMaxSec']))

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
                dropin = rootfs / 'etc/systemd/logind.conf.d/50-mixpi-inhibit.conf'
                self.assertEqual(dropin.read_bytes(), LOGIND_DROPIN.read_bytes())
                self.assertEqual(stat.S_IMODE(dropin.stat().st_mode), 0o644)

    def test_stage_leaves_the_helper_owned_by_root(self):
        # pi-gen runs the stage as root; only home folders are handed to pi.
        for line in STAGE.read_text().splitlines():
            if 'chown' in line:
                self.assertNotRegex(line, r'/usr/local/sbin|/etc/systemd')
        self.assertIn('install -m 644 files/logind/50-mixpi-inhibit.conf '
                      '${ROOTFS_DIR}/etc/systemd/logind.conf.d/\n', STAGE.read_text())


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
        # busctl wait: print the next signal from the signals file (one line
        # per wait, "fail" for a bus error); with none left, wait forever.
        self.signals = self.directory / 'signals'
        self.stub(bin_dir / 'busctl',
                  'echo "busctl $*" >> "$CALLS"\n'
                  'line=$(head -n 1 "$SIGNALS" 2>/dev/null)\n'
                  '[ -n "$line" ] || while :; do /bin/sleep 1; done\n'
                  'sed -i.bak 1d "$SIGNALS"\n'
                  '[ "$line" = fail ] && exit 1\n'
                  'echo "$line"\n')
        self.runtime = self.directory / 'run'
        text = HELPER.read_text()
        text = text.replace('RUNTIME_BASE=/run/user', f'RUNTIME_BASE={self.runtime}')
        text = text.replace('SYSTEMCTL=/usr/bin/systemctl', f'SYSTEMCTL={bin_dir}/systemctl')
        text = text.replace('RUNUSER=/usr/sbin/runuser', f'RUNUSER={bin_dir}/runuser')
        text = text.replace('BUSCTL=/usr/bin/busctl', f'BUSCTL={bin_dir}/busctl')
        text = text.replace('WAIT_SECONDS=22', 'WAIT_SECONDS=3')
        self.helper = self.directory / 'mixpi-stop-mixxx'
        self.helper.write_text(text)
        self.environment = {'PATH': f'{bin_dir}:/usr/bin:/bin', 'CALLS': str(self.log),
                            'STATE': str(self.state), 'AFTER_STOP': str(self.directory / 'after'),
                            'SIGNALS': str(self.signals)}

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
                          ['mixpi-mixxx'], ['--wait-for-shutdown', 'mixpi-mixxx.service'],
                          ['--wait'], ['--stop']):
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

    def run_waiting(self, signals, states=('active',), after_stop=('inactive',), timeout=20):
        self.signals.write_text(''.join(line + '\n' for line in signals))
        return self.run_helper(list(states), list(after_stop), '--wait-for-shutdown')

    def test_wait_mode_stops_mixxx_on_prepare_for_shutdown_and_exits(self):
        self.user_manager()
        result, calls = self.run_waiting(['b true'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.stops(calls)), 1)
        self.assertEqual(self.state.read_text(), 'inactive\n')
        waits = [call for call in calls if call.startswith('busctl')]
        self.assertEqual(waits, ['busctl --system wait org.freedesktop.login1 /org/freedesktop/login1 '
                                 'org.freedesktop.login1.Manager PrepareForShutdown'])
        # The stop happens after the signal, not before.
        self.assertLess(calls.index(waits[0]), calls.index(self.stops(calls)[0]))

    def test_wait_mode_keeps_holding_after_a_cancelled_shutdown_or_bus_error(self):
        self.user_manager()
        result, calls = self.run_waiting(['b false', 'fail', 'b true'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len([call for call in calls if call.startswith('busctl')]), 3)
        self.assertEqual(len(self.stops(calls)), 1)

    def test_wait_mode_never_stops_mixxx_without_the_signal(self):
        self.user_manager()
        self.signals.write_text('b false\n')
        self.state.write_text('active\n')
        (self.directory / 'after').write_text('inactive\n')
        process = subprocess.Popen(['sh', str(self.helper), '--wait-for-shutdown'],
                                   env=self.environment, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True)
        try:
            with self.assertRaises(subprocess.TimeoutExpired):
                process.wait(timeout=2)
        finally:
            # The stub busctl's sleep holds the pipes; end it first.
            subprocess.run(['pkill', '-f', str(self.directory)], check=False)
            process.kill()
            process.communicate(timeout=10)
        self.assertEqual(self.stops(self.log.read_text().splitlines()), [])

    def test_wait_mode_releases_the_inhibitor_even_when_the_stop_hangs(self):
        self.user_manager()
        result, _ = self.run_waiting(['b true'], after_stop=('deactivating',))
        self.assertEqual(result.returncode, 0)
        self.assertIn('still not inactive', result.stderr)


if __name__ == '__main__':
    unittest.main()
