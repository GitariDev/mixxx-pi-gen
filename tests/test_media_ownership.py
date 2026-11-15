from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

from test_media_identity import added_header
from test_media_completion import function_text

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / 'stage3/01-install-packages/files/mixxx-media-selection.patch'


def production_file(relative):
    import os
    import re
    reference = Path(os.environ.get('MIXXX_TEST_SOURCE', ROOT / 'deploy/mixxx-performance-source'))
    if not reference.is_dir():
        raise unittest.SkipTest('MIXXX_TEST_SOURCE requires local pinned Mixxx checkout')
    commit = re.search(r'MIXXX_COMMIT:-([0-9a-f]{40})', (ROOT / 'source-versions').read_text())[1]
    source = subprocess.check_output(['git', '-C', str(reference), 'show', f'{commit}:{relative}'], text=True)
    with tempfile.TemporaryDirectory(prefix='mixpi-producer-') as directory:
        target = Path(directory)
        native = target / relative
        native.parent.mkdir(parents=True)
        native.write_text(source)
        recipe = ROOT / 'stage3/01-install-packages/01-run.sh'
        names = subprocess.check_output(['bash', str(recipe), '--mixxx-print-patches'], text=True).splitlines()
        for name in names:
            subprocess.run(['git', 'apply', '--include=' + relative, str(PATCH.parent / name)],
                           cwd=target, check=True, capture_output=True)
        return native.read_text()


@unittest.skipUnless(shutil.which('c++') and shutil.which('git'), 'C++ and git required')
class NativeOwnershipTests(unittest.TestCase):
    def test_cache_acquisition_failure_revalidates_original_fallback(self):
        with tempfile.TemporaryDirectory(prefix='mixpi-cache-fallback-') as directory:
            target = Path(directory)
            (target / 'mediauseregistry.h').write_text(added_header(PATCH, 'src/library/media/mediauseregistry.h'))
            template = (ROOT / 'tests/native/media_cache_fallback_test.cpp.in').read_text()
            proxy = production_file('src/sources/soundsourceproxy.cpp')
            template = template.replace('PRODUCTION_ACQUIRE_PATH', function_text(
                added_header(PATCH, 'src/library/media/mediause.h'), 'inline Lease acquirePath('))
            template = template.replace('PRODUCTION_CACHE_CONSTRUCTOR', function_text(
                proxy, 'SoundSourceProxy::SoundSourceProxy(TrackPointer pTrack, RamCacheMode'))
            template = template.replace('PRODUCTION_AUDIO_OPEN', function_text(
                proxy, 'mixxx::AudioSourcePointer SoundSourceProxy::openAudioSource('))
            unit = target / 'fallback.cpp'
            unit.write_text(template)
            executable = target / 'fallback-test'
            compiled = subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-pthread',
                '-I' + str(target), str(unit), '-o', str(executable)], capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run([str(executable)], capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('PASS production constructor', result.stdout)

    def test_real_worker_and_proxy_admission_order(self):
        reader = production_file('src/engine/cachingreader/cachingreaderworker.cpp')
        queue = function_text(reader, 'void CachingReaderWorker::newTrack(')
        load = function_text(reader, 'void CachingReaderWorker::loadTrack(')
        self.assertLess(queue.index('acquirePath'), queue.index('m_pNewTrack ='))
        self.assertNotIn('emit trackLoadFailed', queue)
        self.assertLess(load.index('if (!mediaUse)'), load.index('checkFileExists'))
        proxy = production_file('src/sources/soundsourceproxy.cpp')
        constructor = function_text(proxy, 'SoundSourceProxy::SoundSourceProxy(TrackPointer pTrack, RamCacheMode')
        self.assertLess(constructor.index('m_mediaUse('), constructor.index('RemovableTrackCache::acquire'))
        self.assertIn('m_mediaUse && m_pTrack', constructor)

    def test_registry_and_actual_producer_methods(self):
        with tempfile.TemporaryDirectory(prefix='mixpi-native-ownership-') as directory:
            target = Path(directory)
            (target / 'mediauseregistry.h').write_text(added_header(PATCH, 'src/library/media/mediauseregistry.h'))
            for folder in ('sources', 'track', 'library/media'):
                (target / folder).mkdir(parents=True)
            (target / 'library/media/mediause.h').write_text('#include "mediauseregistry.h"\n')
            (target / 'track/track_decl.h').write_text('#pragma once\n')
            (target / 'sources/removabletrackcache.h').write_text(
                '#pragma once\nnamespace mixxx { struct RemovableTrackCache { using Lease = std::shared_ptr<int>; }; }\n')
            (target / 'sources/audiosourceproxy.h').write_text('''#pragma once
namespace mixxx {
struct AudioSource { bool* destroyed = nullptr; explicit AudioSource(bool* flag = nullptr) : destroyed(flag) {}
struct OpenParams {}; int getStreamInfo() const { return 0; }
virtual ~AudioSource() { if (destroyed) *destroyed = true; } virtual void close() {} };
using AudioSourcePointer = std::shared_ptr<AudioSource>;
struct AudioSourceProxy : AudioSource { AudioSourcePointer source;
explicit AudioSourceProxy(AudioSourcePointer next) : source(std::move(next)) {} };
}
''')
            (target / 'sources/audiosourcetrackproxy.h').write_text(production_file('src/sources/audiosourcetrackproxy.h'))
            template = (ROOT / 'tests/native/media_ownership_test.cpp.in').read_text()
            template = template.replace('PRODUCTION_ACQUIRE_PATH', function_text(
                added_header(PATCH, 'src/library/media/mediause.h'), 'inline Lease acquirePath('))
            template = template.replace('PRODUCTION_NEW_TRACK', function_text(
                production_file('src/engine/cachingreader/cachingreaderworker.cpp'), 'void CachingReaderWorker::newTrack('))
            template = template.replace('PRODUCTION_ANALYSIS_SUBMIT', function_text(
                production_file('src/analyzer/analyzerthread.cpp'), 'bool AnalyzerThread::submitNextTrack('))
            template = template.replace('PRODUCTION_AUDIO_OPEN', function_text(
                production_file('src/sources/soundsourceproxy.cpp'), 'mixxx::AudioSourcePointer SoundSourceProxy::openAudioSource('))
            recording = production_file('src/engine/sidechain/enginerecord.cpp')
            for marker, signature in [('PRODUCTION_RECORD_OPEN', 'bool EngineRecord::openFile('),
                                      ('PRODUCTION_RECORD_CLOSE', 'void EngineRecord::closeFile('),
                                      ('PRODUCTION_CUE_CLOSE', 'void EngineRecord::closeCueFile(')]:
                template = template.replace(marker, function_text(recording, signature))
            template = template.replace('PRODUCTION_EXPORT_RUN', function_text(
                production_file('src/library/export/trackexportworker.cpp'), 'void TrackExportWorker::run('))
            unit = target / 'ownership.cpp'
            unit.write_text(template)
            export = os.environ.get('MEDIA_OWNERSHIP_TEST_EXPORT')
            if export:
                shutil.copytree(target, export, dirs_exist_ok=True)
            executable = target / 'ownership'
            compiled = subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-pthread',
                           '-I' + str(target), str(unit), '-o', str(executable)], capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run([str(executable)], capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('PASS production native registry', result.stdout)
            print(result.stdout, end='')
