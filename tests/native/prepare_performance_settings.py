"""Stage real pinned controls and the shipping header for a standalone Qt regression.

Only audio, waveform, persistence, dialogs, and unused telemetry/MIDI dependencies
are doubles. ControlObject, ControlProxy, ControlDoublePrivate, atomic values,
mutexes, and Qt signal delivery are the unmodified production implementation.
"""
import argparse
from pathlib import Path
import subprocess
import os
import tempfile

from library_interface_runner import reconstruct, populate_pinned

FILES = [
    'control/control.cpp', 'control/control.h', 'control/controlobject.cpp',
    'control/controlobject.h', 'control/controlproxy.cpp', 'control/controlproxy.h',
    'control/controlbehavior.h', 'control/controlvalue.h', 'util/mutex.h',
    'util/thread_annotations.h', 'util/compatibility/qmutex.h', 'util/compatibility/qatomic.h',
]


def prepare(source, output):
    output.mkdir(parents=True, exist_ok=True)
    os.environ['MIXXX_TEST_SOURCE'] = str(source.resolve())
    with tempfile.TemporaryDirectory(prefix='mixpi-settings-source-') as temporary:
        current = Path(temporary)
        reconstruct(current)
        populate_pinned(current, ['src/' + name for name in FILES])
        for name in FILES:
            target = output / 'production' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((current / 'src' / name).read_bytes())
        (output / 'mixpiperformancesettings.h').write_bytes(
            (current / 'src/widget/mixpiperformancesettings.h').read_bytes())
    here = Path(__file__).resolve().parent
    for name in ('performance_settings_stubs.h', 'performance_settings_test.cpp',
                 'performance_settings_window.h'):
        (output / name).write_bytes((here / name).read_bytes())
    for name in ('preferences/usersettings.h', 'controllers/midi/midimessage.h', 'util/stat.h',
                 'engine/enginebuffer.h', 'soundio/soundmanager.h',
                 'waveform/waveformwidgetfactory.h', 'QMessageBox'):
        target = output / 'doubles' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('#include "performance_settings_stubs.h"\n')
    (output / 'doubles/util/assert.h').write_text(
        '#include <cassert>\n#define DEBUG_ASSERT(x) assert(x)\n'
        '#define VERIFY_OR_DEBUG_ASSERT(x) if (!(x))\n')
    (output / 'CMakeLists.txt').write_text('''cmake_minimum_required(VERSION 3.16)
project(performance_settings_regression LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_AUTOMOC ON)
find_package(Qt6 REQUIRED COMPONENTS Core Widgets)
add_executable(settings-test performance_settings_test.cpp performance_settings_window.h
    production/control/control.cpp production/control/controlobject.cpp
    production/control/controlproxy.cpp)
target_include_directories(settings-test PRIVATE . doubles production)
target_link_libraries(settings-test PRIVATE Qt6::Core Qt6::Widgets)
enable_testing()
foreach(scenario initial periodic requests invalid buffer buffer_mapping semantics startup
        preferences)
    add_test(NAME ${scenario} COMMAND settings-test ${scenario})
endforeach()
''')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.source, args.output)
