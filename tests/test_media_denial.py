from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from test_media_completion import function_text
from test_media_identity import added_header
from test_media_ownership import PATCH, ROOT, production_file


@unittest.skipUnless(shutil.which('c++'), 'C++ required')
class MediaDenialTests(unittest.TestCase):
    def test_eviction_persistence_and_export_refusal(self):
        collection = production_file('src/library/trackcollectionmanager.cpp')
        engine = production_file('src/library/export/engineprimeexportjob.cpp')
        worker = function_text(engine, 'void EnginePrimeExportJob::run()')
        handoff = worker[worker.index('    for (const auto& trackRef'):]
        handoff = handoff[:handoff.index('        qInfo() << "Exporting track"')]
        substitutions = {
            'PRODUCTION_SAVE': function_text(collection,
                'TrackCollectionManager::SaveTrackResult TrackCollectionManager::saveTrack(\n        Track*'),
            'PRODUCTION_EVICTION': function_text(collection,
                'void TrackCollectionManager::saveEvictedTrack('),
            'PRODUCTION_LOAD': function_text(engine, 'void EnginePrimeExportJob::loadTrack('),
            'PRODUCTION_HANDOFF': handoff + '        ++exports;\n    }\n',
            'PRODUCTION_ACQUIRE': function_text(added_header(PATCH,
                'src/library/media/mediause.h'), 'inline Lease acquirePath('),
        }
        template = (ROOT / 'tests/native/media_denial_test.cpp.in').read_text()
        for marker, method in substitutions.items():
            template = template.replace(marker, method)
        with tempfile.TemporaryDirectory(prefix='mixpi-denial-') as directory:
            target = Path(directory)
            (target / 'mediauseregistry.h').write_text(added_header(PATCH,
                'src/library/media/mediauseregistry.h'))
            unit = target / 'denial.cpp'
            unit.write_text(template)
            executable = target / 'denial'
            compiled = subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra',
                '-Werror', '-pthread', '-fsanitize=undefined',
                '-fno-sanitize-recover=undefined', '-I' + str(target), str(unit),
                '-o', str(executable)], capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            for scenario in ('eviction', 'export'):
                with self.subTest(scenario=scenario):
                    result = subprocess.run([str(executable), scenario], capture_output=True,
                        text=True, timeout=20)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn('PASS ' + scenario, result.stdout)
