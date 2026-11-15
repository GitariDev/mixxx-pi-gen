import argparse
import os
from pathlib import Path
import platform
import subprocess
import tempfile

from library_interface_runner import reconstruct, qt_flags, qt_environment

ROOT = Path(__file__).resolve().parents[2]


def function(source, signature):
    start = source.index(signature)
    return source[start:source.index('\n}\n', start) + 3]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--holdout', action='store_true')
    parser.add_argument('--screenshots', type=Path)
    parser.add_argument('--emit-only', type=Path)
    arguments = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='mixpi-media-qt-') as temporary:
        target = Path(temporary)
        reconstruct(target)
        source = (target / 'src/library/rekordbox/rekordboxfeature.cpp').read_text()
        cache = (target / 'src/library/rekordbox/sourcecache.h').read_text()
        identity = (target / 'src/library/rekordbox/sourceidentity.h').read_text()
        unit = (ROOT / 'tests/native/media_continuation_test.cpp.in').read_text()
        unit = unit.replace('PRODUCTION_METHODS', '\n'.join(function(source, signature) for signature in (
            'QString RekordboxFeature::openRemovableDevice(',
            'std::function<void()> RekordboxFeature::openRemovableDeviceAsync(',
            'void RekordboxFeature::requestDeviceRefresh(',
            'void RekordboxFeature::finishDeviceRefresh(')))
        unit = unit.replace('PRODUCTION_CACHE', '\n'.join(function(cache, signature) for signature in (
            'inline bool matchesCachedSource(', 'inline int cachedSourceRow(')))
        unit = unit.replace('PRODUCTION_REVISION', function(identity, 'inline bool sameSourceRevision('))
        if arguments.emit_only:
            arguments.emit_only.write_text(unit)
            return
        source_file = target / 'media-test.cpp'
        source_file.write_text(unit)
        command = ['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror']
        command += ['-I' + str(target / 'src'), str(source_file), '-o', str(target / 'media-test'), *qt_flags()]
        print('COMPILE', repr(command), flush=True)
        subprocess.run(command, check=True, timeout=90)
        environment = qt_environment()
        if arguments.screenshots:
            arguments.screenshots.mkdir(parents=True, exist_ok=True)
            environment['MIXXX_MEDIA_TEST_SCREENSHOTS'] = str(arguments.screenshots.resolve())
        subprocess.run([str(target / 'media-test'), 'holdout' if arguments.holdout else 'main'],
                       env=environment, check=True, timeout=40)


if __name__ == '__main__':
    main()
