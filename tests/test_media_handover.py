"""R-5 handover and R-6 eject engine A and its gate (mixxx-media-handover.patch)."""
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tempfile
import unittest

from native.library_interface_runner import qt_available, qt_flags
from native import media_screen_runner as runner
from test_media_completion import function_text

ROOT = Path(__file__).resolve().parents[1]
PATCH = runner.PATCH_DIR / runner.HANDOVER
CACHE = Path('/dev/shm/mixpi-track-cache')


def new_text(path):
    text = PATCH.read_text()
    section = text.split('+++ b/' + path + '\n', 1)[1].split('\ndiff --git ', 1)[0]
    return '\n'.join(line[1:] for line in section.splitlines() if line[:1] in ('+', ' '))


class MediaHandoverPatchTests(unittest.TestCase):
    def test_patch_touches_only_n3_files(self):
        files = re.findall(r'^diff --git a/(\S+) ', PATCH.read_text(), re.MULTILINE)
        self.assertEqual(sorted(files), ['src/library/mixpimedia.h', 'src/library/mixpimediapage.h',
                                         'src/sources/removabletrackcache.h', 'src/sources/soundsourceproxy.cpp'])

    def test_copy_holds_copy_lease_and_fallback_keeps_drive_lease(self):
        proxy = new_text('src/sources/soundsourceproxy.cpp')
        self.assertIn('m_ramCache ? mixxx::media::Lease() : m_mediaUse', proxy)
        # Only the return line changes: the fallback retry above it (Original
        # mode, so no copy) keeps passing the drive lease.
        removed = [line for line in PATCH.read_text().split('+++ b/src/sources/soundsourceproxy.cpp', 1)[1]
                   .split('\ndiff --git ', 1)[0].splitlines() if line.startswith('-')]
        self.assertEqual(removed, ['-    return mixxx::AudioSourceTrackProxy::create(m_pTrack, m_pSoundSource, '
                                   'm_ramCache, m_mediaUse);'])

    def test_gate_is_read_once_from_the_root_file(self):
        media = new_text('src/library/mixpimedia.h')
        self.assertIn('ConfigKey("[MixPi]", "media_eject_available")', media)
        self.assertIn('m_ejectAvailable->setAndConfirm(mixpiEjectGateOpen() ? 1 : 0)', media)
        self.assertIn('m_ejectAvailable->setReadOnly()', media)
        page = new_text('src/library/mixpimediapage.h')
        self.assertIn('QStringLiteral("/etc/mixpi/media-eject"), uint owner = 0', page)
        start = media.split('    void startEject(const QString& identity) {', 1)[1]
        self.assertTrue(start.lstrip().startswith('if (!ejectAvailable() || m_engine->running())'))

    def test_on_pi_controls_and_udisks_unmount(self):
        media = new_text('src/library/mixpimedia.h')
        self.assertIn('QStringLiteral("mixpi_on_pi")', media)
        self.assertIn('QStringLiteral("[Sampler%1]").arg(pad)', media)
        self.assertIn('&PlayerInfo::trackChanged', media)
        self.assertIn('QStringLiteral("/usr/bin/udisksctl")', media)
        self.assertIn('QStringLiteral("--no-user-interaction")', media)
        self.assertIn('deadline->start(10000)', media)
        for forbidden in ('power-off', 'poweroff', 'umount -l', '--force'):
            self.assertNotIn(forbidden, media)


@unittest.skipUnless(platform.system() == 'Linux' and qt_available(), 'Linux /dev/shm and Qt6 required')
class MediaHandoverNativeTests(unittest.TestCase):
    def setUp(self):
        self.assertFalse(CACHE.exists(), 'Refuse an existing production cache directory')
        running = subprocess.run(['pgrep', '-x', 'mixxx'], capture_output=True, timeout=10)
        self.assertEqual(running.returncode, 1, 'Run cache checks without a live Mixxx process')

    def tearDown(self):
        shutil.rmtree(CACHE, ignore_errors=True)

    def test_handover_engine_gate_and_on_pi(self):
        with tempfile.TemporaryDirectory(prefix='mixpi-media-handover-') as temporary:
            target = Path(temporary) / 'tree'
            target.mkdir()
            runner.patched_tree(target, runner.HANDOVER)
            interfaces = target / 'interfaces'
            for name in ('sources/audiosourceproxy.h', 'library/media/mediause.h', 'track/track_decl.h'):
                (interfaces / name).parent.mkdir(parents=True, exist_ok=True)
                (interfaces / name).write_text('#pragma once\n')
            proxy = (target / 'src/sources/soundsourceproxy.cpp').read_text()
            template = (ROOT / 'tests/native/media_handover_test.cpp.in').read_text()
            replacements = {
                'PRODUCTION_ACQUIRE_PATH': function_text(
                    (target / 'src/library/media/mediause.h').read_text(), 'inline Lease acquirePath('),
                'PRODUCTION_CACHE_CONSTRUCTOR': function_text(
                    proxy, 'SoundSourceProxy::SoundSourceProxy(TrackPointer pTrack, RamCacheMode'),
                'PRODUCTION_AUDIO_OPEN': function_text(
                    proxy, 'mixxx::AudioSourcePointer SoundSourceProxy::openAudioSource('),
            }
            for marker, text in replacements.items():
                self.assertIn(marker, template)
                template = template.replace(marker, text)
            unit = target / 'media_handover_test.cpp'
            unit.write_text(template)
            binary = target / 'media-handover-test'
            command = ['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-pthread',
                       '-I' + str(interfaces), '-I' + str(target / 'src'), str(unit), '-o', str(binary),
                       *qt_flags(('QtCore', 'QtGui', 'QtWidgets'))]
            compiled = subprocess.run(command, capture_output=True, text=True, timeout=300)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            work = Path(temporary) / 'work'
            work.mkdir()
            environment = runner.qt_environment()
            environment.update(TMPDIR=str(work), MIXPI_RAM_CACHE_PREFIXES=str(work))
            result = subprocess.run([str(binary)], env=environment, capture_output=True, text=True, timeout=120)
            print(result.stdout, result.stderr, flush=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(' 0 failures', result.stdout)
            for name in ('copy: after the open the registry shows 0 users and a drain is idle',
                         'fallback: the registry shows 1 user and a drain is busy',
                         'copy: the copy keeps decoding without the original',
                         'copy: dropping the audio source deletes the copy',
                         'start-up: a stale track-* copy is deleted',
                         'engine: a drain busy for 10 s says still in use and never unmounts',
                         'on pi: the next load clears the flag and the copy is listed as cleaned out'):
                self.assertIn('PASS ' + name, result.stdout)


if __name__ == '__main__':
    unittest.main()
