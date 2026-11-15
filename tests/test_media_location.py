from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

from test_media_completion import function_text
from test_media_identity import added_header
from test_media_ownership import PATCH, ROOT, production_file


@unittest.skipUnless(shutil.which('c++'), 'C++ required')
class NativeLocationTests(unittest.TestCase):
    def test_production_location_and_cover_handoffs(self):
        override = os.environ.get('MEDIA_LOCATION_SOURCE')

        def source(path):
            candidate = Path(override) / path if override else None
            if candidate and candidate.exists():
                return candidate.read_text()
            return added_header(PATCH, path) if '/media/' in path else production_file(path)

        with tempfile.TemporaryDirectory(prefix='mixpi-location-') as directory:
            target = Path(directory)
            (target / 'mediauseregistry.h').write_text(source('src/library/media/mediauseregistry.h'))
            text = (ROOT / 'tests/native/media_location_test.cpp.in').read_text()
            methods = {
                'ACQUIRE': ('src/library/media/mediause.h', 'inline Lease acquirePath('),
                'PLAYER': ('src/mixer/playermanager.cpp', 'void PlayerManager::slotLoadLocationToPlayer('),
                'LIBRARY': ('src/library/library.cpp', 'void Library::slotLoadLocationToPlayer('),
                'INVOKE': ('src/library/trackloader.cpp', 'void TrackLoader::invokeSlotLoadTrack('),
                'LOAD': ('src/library/trackloader.cpp', 'void TrackLoader::slotLoadTrack('),
                'DAO': ('src/library/dao/trackdao.cpp', 'TrackPointer TrackDAO::getOrAddTrack('),
                'ADD_FILE': ('src/library/dao/trackdao.cpp', 'TrackPointer TrackDAO::addTracksAddFile('),
                'COVER': ('src/library/coverartutils.cpp', 'QFuture<void> guessTrackCoverInfoConcurrently('),
            }
            for marker, (path, signature) in methods.items():
                text = text.replace('PRODUCTION_' + marker, function_text(source(path), signature))
            binding = function_text(source('src/mixer/playermanager.cpp'), 'void PlayerManager::bindToLibrary(')
            for marker, signature in [('LOCATION_CALLBACK', '[pLibrary](const QString& location'),
                                      ('TRACK_CALLBACK', '[this](TrackPointer track')]:
                start = binding.index(signature)
                body = binding.index('{', start)
                depth = 1
                end = body + 1
                while depth:
                    depth += (binding[end] == '{') - (binding[end] == '}')
                    end += 1
                text = text.replace('PRODUCTION_' + marker, binding[start:end])
            unit = target / 'location.cpp'
            unit.write_text(text)
            executable = target / 'location'
            result = subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                                     '-pthread', '-I' + str(target), str(unit), '-o', str(executable)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(executable)], capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('PASS location', result.stdout)

    def test_direct_dao_admission_precedes_file_access(self):
        source = production_file('src/library/dao/trackdao.cpp')
        add = function_text(source, 'TrackPointer TrackDAO::addTracksAddFile(')
        self.assertLess(add.index('acquirePath'), add.index('mixxx::FileAccess('))
        lookup = function_text(source, 'TrackPointer TrackDAO::getTrackById(')
        self.assertLess(lookup.index('acquirePath'), lookup.index('mixxx::FileInfo(trackLocation)'))
        self.assertIn('RamCacheMode::Original, mediaUse', add)
        self.assertIn('RamCacheMode::Original, mediaUse', lookup)
        cover = function_text(source, 'void TrackDAO::detectCoverArtForTracksWithoutCover(')
        self.assertLess(cover.index('acquirePath'), cover.index('mixxx::FileInfo(track.trackLocation)'))
