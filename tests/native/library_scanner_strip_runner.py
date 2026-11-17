"""Real Qt + exact pinned/patched LibraryScannerDlg and LibraryScanner wiring.

A labeled LibraryScanner/TrackDAO double carries the real constructor wiring
text; a fake clock replaces PerformanceTimer. No scan, database or skin runs.
"""
import argparse
import hashlib
from pathlib import Path
import subprocess
import tempfile
from library_interface_runner import (ROOT, reconstruct, populate_pinned, qt_flags,
                                      qt_environment, moc_path)

SCANNER = 'src/library/scanner/libraryscanner.cpp'


def main():
    parser = argparse.ArgumentParser()
    # Evidence only (R-12): the status label as before mixxx-scan-progress.patch
    # painted no background of its own; the repaint check must then fail.
    parser.add_argument('--label-without-background', action='store_true')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='mixpi-scanner-strip-') as temporary:
        target = Path(temporary)
        reconstruct(target)
        if args.label_without_background:
            dialog_source = target / 'src/library/scanner/libraryscannerdlg.cpp'
            text = dialog_source.read_text()
            fill = '        painter.fillRect(rect(), kStripBackground);\n'
            assert fill in text
            dialog_source.write_text(text.replace(fill, ''))
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
        # mixxx.cfg and the control registry: only what the strip uses.
        for name in ('preferences', 'control'):
            (stubs / name).mkdir()
        (stubs / 'preferences/usersettings.h').write_text('''#pragma once
#include <QMap>
#include <QSharedPointer>
#include <QString>
struct ConfigKey {
    QString group, item;
    ConfigKey(QString g, QString i) : group(std::move(g)), item(std::move(i)) {}
    QString text() const { return group + "," + item; }
};
class UserSettings {
  public:
    QMap<QString, int> values;
    int writes = 0;
    int getValue(const ConfigKey& key, int fallback) const { return values.value(key.text(), fallback); }
    void setValue(const ConfigKey& key, int value) { values[key.text()] = value; ++writes; }
};
typedef QSharedPointer<UserSettings> UserSettingsPointer;
''')
        (stubs / 'control/controlobject.h').write_text('''#pragma once
#include <QHash>
#include <QList>
#include <functional>
#include "preferences/usersettings.h"
enum class ControlFlag { None = 0, NoAssertIfMissing = 2, NoWarnIfMissing = 6 };
class ControlObject {
  public:
    explicit ControlObject(const ConfigKey& key) : m_key(key.text()) { registry()[m_key] = this; }
    ~ControlObject() { registry().remove(m_key); }
    static QHash<QString, ControlObject*>& registry() { static QHash<QString, ControlObject*> r; return r; }
    static bool exists(const ConfigKey& key) { return registry().contains(key.text()); }
    static ControlObject* getControl(const ConfigKey& key, ControlFlag = ControlFlag::None) {
        return registry().value(key.text());
    }
    double get() const { return m_value; }
    // A write from outside (skin, controller): the owner's request handler decides.
    void set(double value) { if (m_request) { m_request(value); } else { setAndConfirm(value); } }
    void setAndConfirm(double value) { m_value = value; history.append(value); }
    template<typename Receiver, typename Slot>
    void connectValueChangeRequest(Receiver*, Slot slot) { m_request = slot; }
    QList<double> history;
  private:
    QString m_key;
    double m_value = 0;
    std::function<void(double)> m_request;
};
''')
        scanner = (target / SCANNER).read_text()
        start = scanner.index('    m_pProgressDlg.reset(new LibraryScannerDlg(pConfig));')
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
