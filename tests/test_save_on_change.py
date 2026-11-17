"""R-13 save on change: mixxx.cfg and the sampler bank are saved shortly
after each change, atomically, so a power cut or a killed Mixxx loses at
most the last second.

Owner: "We control the codebase, why can't we just save on settings change?"
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
PATCH_NAME = 'mixxx-save-on-change.patch'
PATCH = ROOT / 'stage3/01-install-packages/files' / PATCH_NAME
PATCHED_FILES = [
    'src/coreservices.cpp', 'src/coreservices.h', 'src/mixer/playermanager.cpp',
    'src/mixer/samplerbank.cpp', 'src/mixer/samplerbank.h',
    'src/preferences/configobject.cpp', 'src/preferences/configobject.h',
]


def runner():
    spec = importlib.util.spec_from_file_location(
        'save_on_change_runner', ROOT / 'tests/native/save_on_change_runner.py')
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
    """What is missing for the autosave to run in Mixxx and stop before the quit save."""
    def read(relative):
        path = source / relative
        return path.read_text() if path.exists() else ''
    core = read('src/coreservices.cpp')
    players = read('src/mixer/playermanager.cpp')
    config = read('src/preferences/configobject.cpp')
    problems = []
    if 'class ConfigAutosave' not in read('src/preferences/configobject.h'):
        return ['ConfigAutosave missing']
    initialize = body(core, 'void CoreServices::initialize(QApplication* pApp)')
    created = initialize.find('m_pConfigAutosave = std::make_unique<ConfigAutosave>(pConfig);')
    players_created = initialize.find('m_pPlayerManager = std::make_shared<PlayerManager>(')
    started = initialize.find('m_pConfigAutosave->start();')
    if not 0 <= created < players_created:
        problems.append('the autosave ([MixPi],saved) is not created before the players')
    if not (started > initialize.find('m_pPlayerManager->loadSamplers();') > 0 and
            started < initialize.find('m_isInitialized = true;')):
        problems.append('the autosave does not start at the end of start-up')
    finalize = body(core, 'void CoreServices::finalize()')
    stopped = finalize.find('m_pConfigAutosave->stop();')
    if not 0 <= stopped < finalize.find('m_pSettingsManager->save();'):
        problems.append('the autosave is not stopped before the quit-time save')
    if 'm_pSettingsManager->save();' not in body(core, 'CoreServices::~CoreServices()'):
        problems.append('the final quit-time save is gone')
    if 'loadSamplerBankAndAutosave(getDefaultSamplerPath(m_pConfig))' not in \
            body(players, 'void PlayerManager::loadSamplers()'):
        problems.append('loadSamplers does not start the bank autosave')
    if 'm_pSamplerBank->watchSampler(pSampler);' not in \
            body(players, 'void PlayerManager::addSamplerInner()'):
        problems.append('new samplers are not watched')
    if 'saveSamplerBankToPath(getDefaultSamplerPath(m_pConfig))' not in \
            body(players, 'PlayerManager::~PlayerManager()'):
        problems.append('the quit-time bank save is gone')
    save = body(config, 'bool ConfigObject<ValueType>::save()')
    if '.remove()' in save or 'rename(' in save:
        problems.append('save() still removes or renames by hand')
    helper = body(config, 'bool writeFileAtomically(const QString& filePath, const QByteArray& contents)')
    for needed in ('QSaveFile file(filePath);', 'file.setDirectWriteFallback(false);',
                   '::fsync(file.handle())', 'file.commit()', 'O_DIRECTORY', '::fsync(directory)'):
        if needed not in helper:
            problems.append('writeFileAtomically lacks ' + needed)
    if 'mixxx::writeFileAtomically(samplerBankPath, document)' not in read('src/mixer/samplerbank.cpp'):
        problems.append('the sampler bank is not written atomically')
    return problems


class SaveOnChangePatchTests(unittest.TestCase):
    def test_patch_changes_only_the_owned_files(self):
        self.assertEqual(re.findall(r'^diff --git a/(\S+) ', PATCH.read_text(), re.MULTILINE),
                         PATCHED_FILES)

    def test_settings_screen_signal_is_the_saved_control(self):
        # Wave 2 binds "Saved" to [MixPi],saved; the patch must create it.
        text = PATCH.read_text()
        self.assertIn('kMixPiGroup = QStringLiteral("[MixPi]")', text)
        self.assertIn('kSavedItem = QStringLiteral("saved")', text)
        self.assertIn('int savedPulseMs = 2000;', text)


@unittest.skipUnless(os.environ.get('MIXXX_TEST_SOURCE'), 'MIXXX_TEST_SOURCE required')
class SaveOnChangeWiringTests(unittest.TestCase):
    def reconstructed(self, directory, pinned=False):
        directory.mkdir(parents=True, exist_ok=True)
        reconstruct(directory, exclude=(PATCH_NAME,))
        populate_pinned(directory, PATCHED_FILES)
        if not pinned:
            subprocess.run(['git', 'apply', str(PATCH)], cwd=directory, check=True, timeout=15)
        return directory

    def test_patched_source_saves_on_change_and_stops_before_quit(self):
        with tempfile.TemporaryDirectory(prefix='mixpi-save-on-change-wiring-') as directory:
            self.assertEqual(wiring_problems(self.reconstructed(Path(directory))), [])

    def test_wiring_check_fails_without_the_patch(self):
        with tempfile.TemporaryDirectory(prefix='mixpi-save-on-change-pinned-') as directory:
            source = self.reconstructed(Path(directory), pinned=True)
            self.assertEqual(wiring_problems(source), ['ConfigAutosave missing'])


@unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
class NativeSaveOnChangeTests(unittest.TestCase):
    EXPECTED = {
        'debounce': ['the file is unchanged 0.5 s after a change', 'the file holds the value by 2.5 s',
                     'one write for one change', '[MixPi],saved is 1 after the write',
                     '[MixPi],saved returns to 0 about 2 s after the write',
                     'setting a key to its current value writes nothing'],
        'burst': ['fifty sets in 1 s give one write'],
        'constant': ['under constant change at most one write per 5 s'],
        'idle': ['no write in 10 s of idle'],
        'kill': ['after SIGKILL 3 s after a change the file parses and holds the value'],
        'readonly': ['the old file is byte-identical after a failed save',
                     'the failed save logs a warning'],
        'persist': ['a persist control changed at run time is in the file after the autosave',
                    'the autosave has the same keys and values as the quit-time save of that state'],
        'never-missing': ['the config path is never missing during a save'],
        'bank': ['no bank write before the start-up load',
                 'samplers.xml holds a sample loaded to sampler 1 within 3 s'],
        'bank-unchanged': ['loading the bank at start-up does not rewrite it'],
        'bank-slow': ['no bank write before the slow start-up load ends',
                      'the bank is intact after the slow load'],
    }

    def test_every_check_passes(self):
        if hasattr(os, 'geteuid') and os.geteuid() == 0:
            self.fail('the read-only directory check needs a non-root user')
        modes = runner().MODES
        self.assertEqual(sorted(modes), sorted(self.EXPECTED))
        for mode, result in zip(modes, runner().run(modes)):
            with self.subTest(mode=mode):
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr[-4000:])
                for line in self.EXPECTED[mode]:
                    self.assertIn('PASS ' + line + '\n', result.stdout)
                self.assertNotIn('FAIL ', result.stdout)

    def test_pinned_save_leaves_the_config_path_missing(self):
        # Holdout: the pinned save removes mixxx.cfg before the rename.
        [result] = runner().run(('never-missing',), pinned=True)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr[-4000:])
        self.assertIn('FAIL the config path is never missing during a save', result.stdout)
        self.assertIn('PASS 400 saves succeed', result.stdout)


if __name__ == '__main__':
    unittest.main()
