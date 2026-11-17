"""U-7: the loaded effects are saved within a second of a change (spec s8).

Owner: "we can save the FX loaded and chosen for a future sessions, like how
we save settings - means the FX are there after a restart or shutdown".
Stock Mixxx writes effects.xml only at a clean quit; the new patch writes the
same bytes within a second of a change, atomically, from a worker thread.
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
PATCH_NAME = 'mixxx-effects-save.patch'
PATCH = ROOT / 'stage3/01-install-packages/files' / PATCH_NAME
PATCHED_FILES = ['src/coreservices.cpp', 'src/coreservices.h', 'src/effects/effectsautosave.h',
                 'src/effects/effectsmanager.cpp']


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


def wiring_problems(source):
    """What is missing for effects.xml to be saved on change and last at quit."""
    def read(relative):
        path = source / relative
        return path.read_text() if path.exists() else ''
    manager = read('src/effects/effectsmanager.cpp')
    autosave = read('src/effects/effectsautosave.h')
    core = read('src/coreservices.cpp')
    if 'class EffectsAutosave' not in autosave or 'QByteArray effectsXml(' not in manager:
        return ['EffectsAutosave missing']
    problems = []
    save = body(manager, 'void EffectsManager::saveEffectsXml()')
    if 'mixxx::effectsXml(*this)' not in save:
        problems.append('the quit-time save and the autosave do not share effectsXml()')
    if 'mixxx::writeFileAtomically(' not in save or 'QIODevice::Truncate' in manager:
        problems.append('effects.xml is not written atomically')
    snapshot = body(manager, 'QByteArray effectsXml(const EffectsManager& manager)')
    for needed in ('getChainPresetManager()->saveEffectsXml(&doc,',
                   'getVisibleEffectsList()->saveEffectsXml(&doc,',
                   'return doc.toString().toUtf8();'):
        if needed not in snapshot:
            problems.append('effectsXml() lacks ' + needed)
    if 'saveEffectsXml();' not in body(manager, 'EffectsManager::~EffectsManager()'):
        problems.append('the quit-time save is gone')
    poll = body(autosave, 'void poll()')
    if 'm_pWorker->start(' not in poll or 'writeFileAtomically(filePath, snapshot)' not in poll:
        problems.append('the write does not run on the worker thread')
    if 'm_timing.quietMs' not in poll or 'm_timing.maxDelayMs' not in poll:
        problems.append('bursts are not coalesced')
    initialize = body(core, 'void CoreServices::initialize(QApplication* pApp)')
    created = initialize.find('m_pEffectsAutosave = std::make_unique<EffectsAutosave>(')
    started = initialize.find('m_pEffectsAutosave->start();')
    if not (initialize.find('m_pEffectsManager->setup();') < created < started <
            initialize.find('m_isInitialized = true;')):
        problems.append('the effects autosave does not start at the end of start-up')
    if 'return effectsXml(*pEffectsManager);' not in initialize[created:started]:
        problems.append('the effects autosave does not write effectsXml()')
    finalize = body(core, 'void CoreServices::finalize()')
    if not 0 <= finalize.find('m_pEffectsAutosave.reset();') < \
            finalize.find('CLEAR_AND_CHECK_DELETED(m_pEffectsManager);'):
        problems.append('the effects autosave is not stopped before the quit-time save')
    return problems


class EffectsSavePatchTests(unittest.TestCase):
    def test_patch_changes_only_the_owned_files(self):
        self.assertEqual(re.findall(r'^diff --git a/(\S+) ', PATCH.read_text(), re.MULTILINE),
                         PATCHED_FILES)

    def test_timing_keeps_a_single_change_under_a_second(self):
        text = PATCH.read_text()
        poll = int(re.search(r'int pollMs = (\d+);', text)[1])
        quiet = int(re.search(r'int quietMs = (\d+);', text)[1])
        # Seen within one poll, written after quietMs, checked at the next poll.
        self.assertLess(poll + quiet + poll, 1000)
        self.assertGreaterEqual(quiet, poll)


@unittest.skipUnless(os.environ.get('MIXXX_TEST_SOURCE'), 'MIXXX_TEST_SOURCE required')
class EffectsSaveWiringTests(unittest.TestCase):
    def reconstructed(self, directory, patched=True):
        directory.mkdir(parents=True, exist_ok=True)
        reconstruct(directory, exclude=runner().PATCHES)
        populate_pinned(directory, [path for path in PATCHED_FILES if 'effectsautosave' not in path])
        if patched:
            subprocess.run(['git', 'apply', str(PATCH)], cwd=directory, check=True, timeout=15)
        return directory

    def test_patched_source_saves_effects_on_change_and_last_at_quit(self):
        with tempfile.TemporaryDirectory(prefix='mixpi-effects-save-wiring-') as directory:
            self.assertEqual(wiring_problems(self.reconstructed(Path(directory))), [])

    def test_wiring_check_fails_without_the_patch(self):
        with tempfile.TemporaryDirectory(prefix='mixpi-effects-save-pinned-') as directory:
            source = self.reconstructed(Path(directory), patched=False)
            self.assertEqual(wiring_problems(source), ['EffectsAutosave missing'])


@unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
class NativeEffectsSaveTests(unittest.TestCase):
    EXPECTED = {
        'effects-save': [
            'no effects write while nothing changes',
            'a loaded effect change is on disk in under 1 s',
            'one effects write for one change',
            'the effects state is read on the GUI thread only',
            'the last of ten changes is on disk',
            'ten effect changes in 1 s give one write',
            'under constant change at most one effects write per 3 s',
            'the end of constant change is on disk',
            'no effects write in 2 s of idle',
            'a failed effects write leaves the old file byte-identical',
            'the failed effects write logs a warning',
            'the effects write is retried after a failure',
            'no effects write after stop'],
        'effects-kill': [
            'the process was killed with SIGKILL 1 s after the change',
            'the next load has the effect changed 1 s before the kill'],
    }

    def test_every_check_passes(self):
        if hasattr(os, 'geteuid') and os.geteuid() == 0:
            self.fail('the read-only directory check needs a non-root user')
        modes = tuple(self.EXPECTED)
        for mode, result in zip(modes, runner().run(modes)):
            with self.subTest(mode=mode):
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr[-4000:])
                for line in self.EXPECTED[mode]:
                    self.assertIn('PASS ' + line + '\n', result.stdout)
                self.assertNotIn('FAIL ', result.stdout)


if __name__ == '__main__':
    unittest.main()
