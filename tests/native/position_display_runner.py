"""Compile the shipping WNumberPos with the real control framework and press it.

Production: WNumberPos and WNumber (patched stack), mixxx::Duration,
ControlObject, ControlProxy and ControlDoublePrivate. Interface doubles: WLabel
(a plain QLabel), SkinContext, persistence, statistics and MIDI types. The
TrackTime enums are extracted from the pinned dlgprefdeck.h.
"""
import argparse
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native.library_interface_runner import (pinned_bytes, populate_pinned, qt_flags,
                                             qt_environment, moc_path)
from native.key_widget_runner import block

ROOT = Path(__file__).resolve().parents[2]
# Same production control framework as prepare_performance_settings.py.
CONTROL_FILES = [
    'control/control.cpp', 'control/control.h', 'control/controlobject.cpp',
    'control/controlobject.h', 'control/controlproxy.cpp', 'control/controlproxy.h',
    'control/controlbehavior.h', 'control/controlvalue.h', 'util/mutex.h',
    'util/thread_annotations.h', 'util/compatibility/qmutex.h', 'util/compatibility/qatomic.h',
]
WIDGET_FILES = ['widget/wnumber.h', 'widget/wnumber.cpp', 'widget/wnumberpos.h',
                'widget/wnumberpos.cpp', 'util/duration.h', 'util/duration.cpp',
                'util/fpclassify.h', 'util/fpclassify.cpp']

DOUBLES = {
    'widget/wlabel.h': '''#pragma once
#include <QDomNode>
#include <QLabel>
class SkinContext;
class WLabel : public QLabel {
  public:
    explicit WLabel(QWidget* parent = nullptr) : QLabel(parent) {}
    virtual void setup(const QDomNode&, const SkinContext&) {}
    virtual void onConnectedControlChanged(double, double) {}
  protected:
    QString m_skinText;
};
''',
    'skin/legacy/skincontext.h': '''#pragma once
#include <QDomNode>
class SkinContext {
  public:
    bool hasNodeSelectInt(const QDomNode&, const QString&, int*) const { return false; }
};
''',
    'preferences/usersettings.h': '''#pragma once
#include <QDebug>
#include <QHash>
#include <QSharedPointer>
#include <QString>
struct ConfigKey {
    QString group, item;
    ConfigKey() = default;
    ConfigKey(QString g, QString i) : group(g), item(i) {}
    bool isValid() const { return !group.isEmpty() && !item.isEmpty(); }
    bool operator==(const ConfigKey& other) const { return group == other.group && item == other.item; }
    bool operator!=(const ConfigKey& other) const { return !(*this == other); }
};
inline size_t qHash(const ConfigKey& k, size_t seed = 0) { return qHash(k.group + k.item, seed); }
inline QDebug operator<<(QDebug d, const ConfigKey& k) { return d << k.group << k.item; }
struct UserSettings {
    double getValue(const ConfigKey&, double fallback) const { return fallback; }
    void set(const ConfigKey&, const QString&) {}
};
using UserSettingsPointer = QSharedPointer<UserSettings>;
''',
    'controllers/midi/midimessage.h': '''#pragma once
enum class MidiOpCode { NoteOff, NoteOn, ControlChange };
''',
    'util/stat.h': '''#pragma once
#include <QString>
struct Stat {
    enum StatType { UNSPECIFIED };
    enum ComputeFlags { COUNT = 1, SUM = 2, AVERAGE = 4, SAMPLE_VARIANCE = 8, MIN = 16, MAX = 32 };
    static void track(const QString&, StatType, ComputeFlags, double) {}
};
''',
    'util/assert.h': '''#pragma once
#include <cassert>
#define DEBUG_ASSERT(x) assert(x)
#define VERIFY_OR_DEBUG_ASSERT(x) if (!(x))
''',
}


def run(baseline=False, without_council=False):
    spec = importlib.util.spec_from_file_location(
        'library_reconstruction', ROOT / 'tests/native/library_interface_runner.py')
    reconstruction = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reconstruction)
    with tempfile.TemporaryDirectory(prefix='mixpi-position-display-') as temporary:
        target = Path(temporary)
        reconstruction.reconstruct(
            target, exclude=('mixxx-council-fixes.patch',) if without_council else ())
        if baseline:
            (target / 'src/widget/wnumberpos.cpp').write_bytes(pinned_bytes('src/widget/wnumberpos.cpp'))
        populate_pinned(target, ['src/' + name for name in CONTROL_FILES + WIDGET_FILES])
        support = target / 'interfaces'
        for name, text in DOUBLES.items():
            (support / name).parent.mkdir(parents=True, exist_ok=True)
            (support / name).write_text(text)
        enums = block(pinned_bytes('src/preferences/dialog/dlgprefdeck.h').decode(), 'namespace TrackTime')
        (support / 'preferences/dialog').mkdir(parents=True, exist_ok=True)
        (support / 'preferences/dialog/dlgprefdeck.h').write_text('#pragma once\n' + enums + '\n')
        for header in ('control/control.h', 'control/controlobject.h', 'control/controlproxy.h',
                       'widget/wnumber.h', 'widget/wnumberpos.h'):
            path = target / 'src' / header
            command = [moc_path(), '-I' + str(support), '-I' + str(target / 'src'), str(path),
                       '-o', str(path.parent / ('moc_' + path.stem + '.cpp'))]
            subprocess.run(command, check=True, timeout=30)
        sources = [target / 'src' / name for name in
                   ('control/control.cpp', 'control/controlobject.cpp', 'control/controlproxy.cpp',
                    'widget/wnumber.cpp', 'widget/wnumberpos.cpp', 'util/duration.cpp',
                    'util/fpclassify.cpp')]
        command = ['c++', '-std=c++20', '-I' + str(support), '-I' + str(target / 'src')]
        command += [str(source) for source in sources]
        command += [str(ROOT / 'tests/native/position_display_test.cpp'),
                    '-o', str(target / 'position-display-test'),
                    *qt_flags(('QtCore', 'QtGui', 'QtWidgets', 'QtXml'))]
        print('COMPILE', repr(command), flush=True)
        subprocess.run(command, check=True, timeout=180)
        result = subprocess.run([str(target / 'position-display-test')], env=qt_environment(),
                                capture_output=True, text=True, timeout=30)
        print(result.stdout, result.stderr, flush=True)
        return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', action='store_true')
    parser.add_argument('--without-council-fixes', action='store_true')
    options = parser.parse_args()
    raise SystemExit(run(options.baseline, options.without_council_fixes).returncode)
