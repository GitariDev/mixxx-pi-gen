from pathlib import Path
import os
import re
import shutil
import subprocess
import tempfile
import unittest

from test_media_identity import added_header


ROOT = Path(__file__).resolve().parents[1]
PATCHES = ROOT / 'stage3/01-install-packages/files'


def function_text(source, signature):
    start = source.index(signature)
    return source[start:source.index('\n}\n', start) + 3]


@unittest.skipUnless(shutil.which('c++') and shutil.which('git'), 'C++ and git required')
class NativeCompletionTests(unittest.TestCase):
    def test_transient_completion_failure_rebuilds_before_retry(self):
        reference = Path(os.environ.get('MIXXX_TEST_SOURCE', ROOT / 'deploy/mixxx-performance-source'))
        if not reference.is_dir():
            self.skipTest('set MIXXX_TEST_SOURCE to a local pinned Mixxx git checkout')
        commit = re.search(r'MIXXX_COMMIT:-([0-9a-f]{40})', (ROOT / 'source-versions').read_text())[1]
        relative = 'src/library/rekordbox/rekordboxfeature.cpp'
        pristine = subprocess.run(['git', '-C', str(reference), 'show', f'{commit}:{relative}'],
                                  check=True, capture_output=True, text=True).stdout
        with tempfile.TemporaryDirectory(prefix='mixpi-completion-') as directory:
            target = Path(directory)
            native = target / relative
            native.parent.mkdir(parents=True)
            native.write_text(pristine)
            names = subprocess.run(['bash', str(PATCHES.parent / '01-run.sh'), '--mixxx-print-patches'],
                                   check=True, capture_output=True, text=True).stdout.splitlines()
            override = os.environ.get('MIXXX_IMPORT_CANCELLATION_PATCH')
            if override and Path(override).name not in names:
                names.append(override)
            for name in names:
                subprocess.run(['git', 'apply', '--include=' + relative, str(PATCHES / name)],
                               cwd=target, check=True, capture_output=True, text=True)
            source = native.read_text()
            template = (ROOT / 'tests/native/media_completion_test.cpp.in').read_text()
            (target / 'importoperation.h').write_text(added_header(
                PATCHES / 'mixxx-import-cancellation.patch', 'src/library/rekordbox/importoperation.h'))
            registry = target / 'mediauseregistry.h'
            registry.write_text(added_header(PATCHES / 'mixxx-media-selection.patch',
                                            'src/library/media/mediauseregistry.h'))
            template = '#include "mediauseregistry.h"\n' + template
            cache = added_header(PATCHES / 'mixxx-media-selection.patch', 'src/library/rekordbox/sourcecache.h')
            identity = added_header(PATCHES / 'mixxx-media-selection.patch', 'src/library/rekordbox/sourceidentity.h')
            template = template.replace('PRODUCTION_CACHE_MATCHER', function_text(cache, 'inline bool matchesCachedSource('))
            template = template.replace('PRODUCTION_REVISION_MATCHER', function_text(identity, 'inline bool sameSourceRevision('))
            methods = '\n'.join(function_text(source, 'void RekordboxFeature::' + name + '(')
                                for name in ('activateChild', 'onRekordboxDevicesFound', 'onTracksFound'))
            template = template.replace('PRODUCTION_CANCEL_ENABLED',
                                        'true' if 'operation->cancelled()' in methods else 'false')
            unit = target / 'completion.cpp'
            unit.write_text(template.replace('PRODUCTION_METHODS', methods))
            executable = target / 'completion-test'
            subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', str(unit), '-o', str(executable)],
                           check=True, capture_output=True, text=True)
            result = subprocess.run([str(executable)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('PASS transient completion failure', result.stdout)
