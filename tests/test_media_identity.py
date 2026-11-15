from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PATCHES = ROOT / 'stage3/01-install-packages/files'


def added_header(patch, name):
    result = []
    active = False
    for line in patch.read_text().splitlines(keepends=True):
        if line.startswith('diff --git '):
            active = line.rstrip() == f'diff --git a/{name} b/{name}'
        elif active and line.startswith('+') and not line.startswith('+++'):
            result.append(line[1:])
    if not result:
        raise AssertionError(name)
    return ''.join(result)


@unittest.skipUnless(shutil.which('c++'), 'C++ compiler required')
class NativeIdentityTests(unittest.TestCase):
    def test_production_generation_and_descriptor_identity(self):
        with tempfile.TemporaryDirectory(prefix='mixpi-native-identity-') as directory:
            root = Path(directory)
            for patch, header in [('mixxx-media-selection.patch', 'sourceidentity.h'),
                                  ('mixxx-media-hotplug.patch', 'removablemounts.h')]:
                (root / header).write_text(added_header(PATCHES / patch,
                    'src/library/rekordbox/' + header))
            executable = root / 'identity-test'
            subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-I' + str(root), str(ROOT / 'tests/native/media_identity_test.cpp'),
                            '-o', str(executable)], check=True, capture_output=True, text=True)
            result = subprocess.run([str(executable)],
                                    check=True, capture_output=True, text=True)
            self.assertIn('PASS native production identity', result.stdout)
            print(result.stdout, end='')
