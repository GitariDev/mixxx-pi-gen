import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native.library_interface_runner import reconstruct, populate_pinned, qt_flags
import platform

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--holdout', action='store_true')
    parser.add_argument('--emit-only', type=Path)
    arguments = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='mixpi-anlz-source-') as directory:
        target = Path(directory)
        reconstruct(target)
        populate_pinned(target, ('lib/kaitai/kaitai/kaitaistream.cpp',
                                'lib/rekordbox-metadata/rekordbox_anlz.cpp',
                                'lib/rekordbox-metadata/rekordbox_anlz.h',
                                'lib/kaitai/kaitai/kaitaistream.h',
                                'lib/kaitai/kaitai/kaitaistruct.h',
                                'lib/kaitai/kaitai/exceptions.h',
                                'lib/kaitai/kaitai/custom_decoder.h'))
        return run(target, arguments)


def run(source_target, arguments):
    source = (source_target / 'src/library/rekordbox/rekordboxfeature.cpp').read_text()
    start = source.index('void readAnalyze(')
    end = source.index('    const double sampleRateKhz', start)
    prefix = source[start:end]
    unit = (ROOT / 'tests/native/rekordbox_analysis_test.cpp.in').read_text()
    unit = unit.replace('PRODUCTION_PARSE_PREFIX', prefix)
    if arguments.emit_only:
        arguments.emit_only.write_text(unit)
        return
    with tempfile.TemporaryDirectory(prefix='mixpi-anlz-') as directory:
        target = Path(directory)
        (target / 'analysis.cpp').write_text(unit)
        runtime = target / 'kaitaistream.cpp'
        runtime.write_bytes((source_target / 'lib/kaitai/kaitai/kaitaistream.cpp').read_bytes())
        command = ['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                   '-Wno-unused-parameter', '-Wno-unused-variable',
                   '-Wno-unused-but-set-variable', '-Wno-pessimizing-move',
                   '-DKS_STR_ENCODING_ICONV',
                   '-I' + str(source_target / 'lib/rekordbox-metadata'),
                   '-I' + str(source_target / 'lib/kaitai'), str(target / 'analysis.cpp'),
                   str(source_target / 'lib/rekordbox-metadata/rekordbox_anlz.cpp'),
                   str(runtime), '-o', str(target / 'analysis-test'), *qt_flags(('QtCore',))]
        if platform.system() == 'Darwin':
            command += ['-liconv']
        print('COMPILE', repr(command), flush=True)
        subprocess.run(command, check=True, timeout=90)
        subprocess.run([str(target / 'analysis-test'), 'holdout' if arguments.holdout else 'main'],
                       check=True, timeout=35)


if __name__ == '__main__':
    main()
