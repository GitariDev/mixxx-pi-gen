import os
from pathlib import Path
import platform
import subprocess
import tempfile
import unittest

from native.library_interface_runner import qt_flags, reconstruct


ROOT = Path(__file__).resolve().parents[1]
CACHE = Path('/dev/shm/mixpi-track-cache')


@unittest.skipUnless(platform.system() == 'Linux', 'Linux inotify cache checks require Linux')
class RamCacheIdentityTests(unittest.TestCase):
    def setUp(self):
        self.assertFalse(CACHE.exists(), 'Refuse an existing production cache directory')
        running = subprocess.run(['pgrep', '-x', 'mixxx'], capture_output=True, timeout=10)
        self.assertEqual(running.returncode, 1, 'Run cache checks without a live Mixxx process')

    def tearDown(self):
        if CACHE.exists():
            CACHE.rmdir()

    def checked(self, command, environment, timeout=90):
        result = subprocess.run(command, cwd=ROOT, env=environment, text=True,
                                capture_output=True, timeout=timeout)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout + result.stderr

    def test_original_recipe_smoke(self):
        with tempfile.TemporaryDirectory(prefix='mixpi-cache-smoke-') as directory:
            environment = dict(os.environ, TMPDIR=directory)
            output = self.checked(['bash', str(ROOT / 'tools/performance/test-ram-cache.sh')], environment)
            self.assertIn('PASS: cache bytes', output)

    def test_notification_identity_and_descriptor_holdouts(self):
        with tempfile.TemporaryDirectory(prefix='mixpi-cache-proof-') as directory:
            work = Path(directory)
            source = work / 'source'
            source.mkdir()
            reconstruct(source)
            executable = work / 'cache-proof'
            environment = dict(os.environ, TMPDIR=directory)
            self.checked(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-pthread',
                          '-DQT_USE_QSTRINGBUILDER',
                          '-I' + str(source / 'src/sources'),
                          str(ROOT / 'tests/native/ram_cache_change_proof_test.cpp'),
                          *qt_flags(('QtCore',)), '-o', str(executable)], environment)
            output = self.checked([str(executable)], environment)
            self.assertIn('PASS: notification writes/moves/companions/overflow', output)
