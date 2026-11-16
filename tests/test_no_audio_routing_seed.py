"""F-12, owner decision 2: the image seeds no audio routing.

Mixxx writes ~/.mixxx/soundconfig.xml itself; the owner sets routing in
Preferences > Sound Hardware. Nothing under stage*/ may write or ship it.
"""
import importlib.machinery
import importlib.util
from pathlib import Path
import re
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
STAGES = sorted(ROOT.glob('stage*'))
SEEDER = ROOT / 'stage3/02-desktop/files/bin/mixpi-touch-defaults'


def stage_files():
    for stage in STAGES:
        for path in sorted(stage.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts:
                yield path


class NoAudioRoutingSeedTests(unittest.TestCase):
    def test_no_stage_file_is_or_names_soundconfig(self):
        checked = 0
        for path in stage_files():
            relative = path.relative_to(ROOT)
            self.assertNotEqual(path.name.lower(), 'soundconfig.xml', relative)
            # Mixxx source patches change Mixxx itself, which owns soundconfig.xml;
            # every script, seeder, unit, skel and config file is checked.
            if path.suffix == '.patch':
                continue
            checked += 1
            with self.subTest(path=str(relative)):
                self.assertNotIn(b'soundconfig', path.read_bytes().lower())
        self.assertGreater(checked, 50)

    def test_seeder_never_writes_routing(self):
        source = SEEDER.read_text()
        for word in ('soundconfig', 'Soundcard', 'SoundManager'):
            self.assertNotIn(word, source)
        loader = importlib.machinery.SourceFileLoader('touch_defaults', str(SEEDER))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        seeder = importlib.util.module_from_spec(spec)
        loader.exec_module(seeder)
        for existing in (None, '[Config]\nResizableSkin Pioneered\n'):
            with self.subTest(existing=existing), tempfile.TemporaryDirectory() as folder:
                config = Path(folder) / '.mixxx/mixxx.cfg'
                if existing is not None:
                    config.parent.mkdir()
                    config.write_text(existing)
                seeder.seed(config)
                self.assertEqual(sorted(p.name for p in config.parent.iterdir()), ['mixxx.cfg'])
                self.assertNotIn('[Soundcard]', config.read_text())

    def test_unused_mixxx_cfg_template_is_not_installed(self):
        # stage3/02-desktop/files/mixxx.cfg has a [Soundcard] section; no stage
        # script may install it or any other file into ~/.mixxx.
        for script in sorted(ROOT.glob('stage*/**/*run.sh')):
            for number, line in enumerate(script.read_text().splitlines(), 1):
                code = line.split('#', 1)[0]
                with self.subTest(script=str(script.relative_to(ROOT)), line=number):
                    self.assertIsNone(re.search(r'mixxx\.cfg|/\.mixxx\b', code), line)


if __name__ == '__main__':
    unittest.main()
