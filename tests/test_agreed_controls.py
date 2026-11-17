"""Wave C2 native controls for the agreed UI.

- U-5 Clear samples (spec s6): [MixPi],sampler_clear_open, _tick1-8, _count
  and sampler_clear. "The pads go empty. The files stay where they are."
- U-9 Brightness, Night dim and CPU readout (spec s12): [MixPi],backlight,
  backlight_available, night_dim and show_cpu, and the udev rule that lets
  the video group write the backlight level.
- The empty effect selector (spec s8): the dynamic property mixpiEmpty.
- "Every change saves within a second." (spec s11): mixxx.cfg on disk in
  under a second after a single change, one write for a burst.
"""
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

from native.library_interface_runner import populate_pinned, qt_available, reconstruct

ROOT = Path(__file__).resolve().parents[1]
FILES = ROOT / 'stage3/01-install-packages/files'
CONTROLS = FILES / 'mixxx-agreed-controls.patch'
TIMING = FILES / 'mixxx-save-within-second.patch'
CONTROLS_FILES = ['src/coreservices.cpp', 'src/coreservices.h', 'src/mixer/mixpisamplerclear.h',
                  'src/util/mixpidisplaycontrols.h', 'src/widget/weffectselector.cpp']
RULE = ROOT / 'stage3/02-desktop/files/udev/99-mixpi-backlight.rules'
DESKTOP = ROOT / 'stage3/02-desktop'


def runner():
    spec = importlib.util.spec_from_file_location(
        'agreed_controls_runner', ROOT / 'tests/native/agreed_controls_runner.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def body(text, signature):
    start = text.index(signature)
    opening = text.index('{', start)
    depth = 0
    for index in range(opening, len(text)):
        depth += {'{': 1, '}': -1}.get(text[index], 0)
        if depth == 0:
            return text[opening:index + 1]
    raise ValueError(signature)


class AgreedControlsPatchTests(unittest.TestCase):
    def test_patches_change_only_the_owned_files(self):
        self.assertEqual(re.findall(r'^diff --git a/(\S+) ', CONTROLS.read_text(), re.MULTILINE),
                         CONTROLS_FILES)
        self.assertEqual(re.findall(r'^diff --git a/(\S+) ', TIMING.read_text(), re.MULTILINE),
                         ['src/preferences/configobject.h'])

    def test_control_names_are_the_ones_the_skin_binds(self):
        text = CONTROLS.read_text()
        for name in ('sampler_clear_open', 'sampler_clear_count', 'sampler_clear"',
                     'sampler_clear_tick%1', '"backlight"', 'backlight_available', 'night_dim',
                     'show_cpu', '"mixpiEmpty"'):
            self.assertIn(name, text)

    def test_night_dim_level_is_one_named_constant(self):
        text = CONTROLS.read_text()
        self.assertEqual(re.findall(r'kNightDimPercent = (\d+);', text), ['10'])

    def test_settings_timing_keeps_a_single_change_under_a_second(self):
        text = TIMING.read_text()
        poll = int(re.search(r'^\+    int pollMs = (\d+);', text, re.MULTILINE)[1])
        quiet = int(re.search(r'^\+    int quietMs = (\d+);', text, re.MULTILINE)[1])
        self.assertLess(poll + quiet + poll, 1000)
        # Unchanged: under constant change at most one write per 5 s.
        self.assertNotIn('maxDelayMs', ''.join(line for line in text.splitlines(True)
                                               if line.startswith(('+', '-'))
                                               and not line.startswith(('+++', '---'))))

    def test_clear_never_deletes_or_moves_a_file(self):
        header = CONTROLS.read_text().split('+++ b/src/mixer/mixpisamplerclear.h')[1].split('diff --git')[0]
        for forbidden in ('remove(', 'rename(', 'unlink', 'QFile', 'QDir'):
            self.assertNotIn(forbidden, header)
        self.assertIn('padKey(pad, "eject")', header)


class BacklightRuleTests(unittest.TestCase):
    def rules(self):
        return [line for line in RULE.read_text().splitlines()
                if line.strip() and not line.lstrip().startswith('#')]

    def test_rule_grants_the_video_group_write_to_brightness_only(self):
        [rule] = self.rules()
        keys = [part.strip() for part in rule.split(',')]
        self.assertEqual(keys[:2], ['ACTION=="add"', 'SUBSYSTEM=="backlight"'])
        commands = [re.fullmatch(r'RUN\+="([^"]+)"', key)[1] for key in keys[2:]]
        self.assertEqual(commands, ['/bin/chgrp video %S%p/brightness',
                                    '/bin/chmod g+w %S%p/brightness'])
        for word in ('MODE', 'OWNER', 'GROUP=', 'max_brightness', 'bl_power', '777', 'o+w'):
            self.assertNotIn(word, rule)

    def test_rule_is_installed_once(self):
        installs = []
        for script in sorted(DESKTOP.glob('0*-run.sh')):
            for line in script.read_text().splitlines():
                if '99-mixpi-backlight.rules' in line:
                    installs.append((script.name, line.strip()))
        self.assertEqual(installs, [(
            '03-run.sh',
            'install -m 644 files/udev/99-mixpi-backlight.rules '
            '${ROOTFS_DIR}/etc/udev/rules.d/99-mixpi-backlight.rules')])

    def test_pi_is_in_the_video_group(self):
        text = (ROOT / 'stage2/01-sys-tweaks/01-run.sh').read_text()
        adding = [match.split() for match in re.findall(r'for GRP in ([^;]+);\s*do\s*\n\s*adduser', text)]
        self.assertEqual(len(adding), 1)
        self.assertIn('video', adding[0])

    @unittest.skipUnless(subprocess.run(['which', 'udevadm'], capture_output=True).returncode == 0,
                         'udevadm required')
    def test_rule_parses(self):
        result = subprocess.run(['udevadm', 'verify', str(RULE)], capture_output=True, text=True)
        if 'Unknown command' in result.stderr or 'unknown' in result.stderr.lower() and 'verify' in result.stderr:
            self.skipTest('udevadm verify unavailable')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


@unittest.skipUnless(os.environ.get('MIXXX_TEST_SOURCE'), 'MIXXX_TEST_SOURCE required')
class AgreedControlsWiringTests(unittest.TestCase):
    def test_core_services_create_the_controls_before_the_skin(self):
        with tempfile.TemporaryDirectory(prefix='mixpi-agreed-controls-wiring-') as directory:
            target = Path(directory)
            runner().stack(target)
            core = (target / 'src/coreservices.cpp').read_text()
            initialize = body(core, 'void CoreServices::initialize(QApplication* pApp)')
            loaded = initialize.find('m_pPlayerManager->loadSamplers();')
            clear = initialize.find('m_pSamplerClear = std::make_unique<MixpiSamplerClear>();')
            display = initialize.find('m_pDisplayControls = std::make_unique<MixpiDisplayControls>(pConfig);')
            self.assertTrue(0 < loaded < clear < initialize.find('m_isInitialized = true;'))
            self.assertTrue(0 < display < initialize.find('m_isInitialized = true;'))
            finalize = body(core, 'void CoreServices::finalize()')
            self.assertIn('m_pSamplerClear.reset();', finalize)
            self.assertIn('m_pDisplayControls.reset();', finalize)
            header = (target / 'src/preferences/configobject.h').read_text()
            self.assertIn('int pollMs = 100;', header)
            self.assertIn('int quietMs = 500;', header)


@unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
class NativeAgreedControlsTests(unittest.TestCase):
    EXPECTED = {
        'settings-fast': [
            'a single settings change is on disk in under 1 s',
            'one write for one change',
            'the last of a burst is on disk',
            'fifty sets in 1 s give one write',
            'no write in 3 s of idle'],
        'clear': [
            'the popover starts closed with nothing counted',
            'opening the popover clears every tick',
            'a ticked loaded pad counts',
            'the count is the ticked pads that hold a sample',
            'a tick takes only 0 or 1',
            'the count is read-only',
            'the count follows a ticked pad that empties',
            'the count follows a ticked pad that loads',
            'the count follows an unticked pad',
            'CLEAR empties the ticked pads that hold a sample',
            'CLEAR leaves an unticked pad loaded',
            'CLEAR never ejects an empty ticked pad (which would reload a sample)',
            'a playing ticked pad keeps its sample and keeps playing, as in build B',
            'CLEAR clears the ticks',
            'CLEAR closes the popover',
            'after CLEAR the count and the trigger read 0',
            'every sample file stays where it was, byte-identical',
            'CLEAR with nothing ticked empties nothing'],
        'backlight': [
            'backlight_available is 1 for a writable panel',
            "with no saved value the slider starts from the panel's level (128 of 255 = 50 %)",
            'nothing is written at start without a saved value',
            'show_cpu defaults to 1',
            'night_dim defaults to 0',
            '80 % writes round(80 × 255 / 100) = 204',
            'the brightness is in mixxx.cfg in under 1 s',
            'only the first panel is written',
            "the slider's top end is 100 % = max_brightness",
            "the slider's bottom end is 5 % = 13",
            'the brightness never goes below 5 %',
            'Night dim on puts the panel at 10 % of max (26)',
            'a brightness change during Night dim is kept, the panel stays dim',
            'night_dim takes only 0 or 1',
            'Night dim off returns the panel to the brightness (60 % = 153)',
            'show_cpu can be turned off',
            'show_cpu takes only 0 or 1',
            'backlight_available is read-only',
            'Brightness, Night dim and CPU readout are saved in mixxx.cfg'],
        'backlight-readonly': [
            'backlight_available is 0 for a read-only brightness file',
            'a read-only panel is left as it is',
            'the value is kept and the slider stays unavailable'],
        'backlight-saved': [
            'saved values are read back at start',
            'the saved brightness is applied at start (30 % = 77)',
            'a saved Night dim is read back at start',
            'a saved Night dim is applied at start'],
        'backlight-none': [
            'no panel: backlight_available is 0',
            'no panel: changes write nothing'],
        'selector': [
            'mixpiEmpty is true for an empty slot',
            'the [mixpiEmpty="true"] rule applies to an empty selector',
            'mixpiEmpty is false once an effect is loaded',
            'the selector is re-polished: the dim rule no longer applies',
            'the selector shows the loaded effect',
            'mixpiEmpty is true again after the effect is unloaded',
            'the dim rule applies again after the unload',
            'an empty selector reads Select effect…',
            'choosing an effect in the selector clears mixpiEmpty',
            'a list refresh keeps mixpiEmpty false for a loaded slot'],
    }

    def test_every_check_passes(self):
        if hasattr(os, 'geteuid') and os.geteuid() == 0:
            self.fail('the read-only checks need a non-root user')
        modes = tuple(self.EXPECTED)
        for mode, result in zip(modes, runner().run(modes)):
            with self.subTest(mode=mode):
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr[-4000:])
                for line in self.EXPECTED[mode]:
                    self.assertIn('PASS ' + line + '\n', result.stdout)
                self.assertNotIn('FAIL ', result.stdout)


if __name__ == '__main__':
    unittest.main()
