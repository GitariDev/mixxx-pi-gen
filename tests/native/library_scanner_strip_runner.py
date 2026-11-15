"""Real Qt + exact pinned/patched LibraryScannerDlg and LibraryScanner wiring.

A labeled LibraryScanner/TrackDAO double carries the real constructor wiring
text; a fake clock replaces PerformanceTimer. No scan, database or skin runs.
"""
import hashlib
from pathlib import Path
import subprocess
import tempfile
from library_interface_runner import (ROOT, reconstruct, populate_pinned, qt_flags,
                                      qt_environment, moc_path)

SCANNER = 'src/library/scanner/libraryscanner.cpp'


def main():
    with tempfile.TemporaryDirectory(prefix='mixpi-scanner-strip-') as temporary:
        target = Path(temporary)
        reconstruct(target)
        populate_pinned(target, [SCANNER, 'src/library/scanner/libraryscannerdlg.cpp',
                                 'src/library/scanner/libraryscannerdlg.h'])
        stubs = target / 'stubs'
        (stubs / 'util').mkdir(parents=True)
        (stubs / 'util/performancetimer.h').write_text('''#pragma once
#include <chrono>
extern std::chrono::milliseconds g_fakeNow;
namespace mixxx { struct Duration {
    std::chrono::milliseconds value;
    static Duration fromSeconds(int seconds) { return {std::chrono::seconds(seconds)}; }
    bool operator>(const Duration& other) const { return value > other.value; } }; }
class PerformanceTimer { public:
    void start() { m_start = g_fakeNow; }
    mixxx::Duration elapsed() const { return {g_fakeNow - m_start}; }
  private: std::chrono::milliseconds m_start{0}; };
''')
        scanner = (target / SCANNER).read_text()
        start = scanner.index('    m_pProgressDlg.reset(new LibraryScannerDlg());')
        end = scanner.index('\n}\n', start)
        (target / 'scanner_wiring.inc').write_text(scanner[start:end])
        dialog = target / 'src/library/scanner/libraryscannerdlg.h'
        doubles = stubs / 'library_scanner_strip_doubles.h'
        doubles.write_bytes((ROOT / 'tests/native/library_scanner_strip_doubles.h').read_bytes())
        includes = ['-I' + str(stubs), '-I' + str(target / 'src'), '-I' + str(target)]
        for header, output in [(dialog, dialog.with_name('moc_libraryscannerdlg.cpp')),
                               (doubles, target / 'moc_doubles.cpp')]:
            subprocess.run([moc_path(), *includes, str(header), '-o', str(output)],
                           check=True, timeout=20)
        command = ['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                   '-DQT_WIDGETS_LIB', '-DQT_GUI_LIB', *includes,
                   str(ROOT / 'tests/native/library_scanner_strip_test.cpp'),
                   str(target / 'src/library/scanner/libraryscannerdlg.cpp'),
                   str(target / 'moc_doubles.cpp'),
                   '-o', str(target / 'test'),
                   *qt_flags(('QtCore', 'QtGui', 'QtWidgets', 'QtTest'))]
        for path in [target / 'src/library/scanner/libraryscannerdlg.cpp', dialog,
                     target / 'scanner_wiring.inc']:
            print('PRODUCTION_INPUT', path.name, hashlib.sha256(path.read_bytes()).hexdigest(), flush=True)
        subprocess.run(command, check=True, timeout=120)
        subprocess.run([str(target / 'test')], env=qt_environment(), check=True, timeout=30)


if __name__ == '__main__':
    main()
