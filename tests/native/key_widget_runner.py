"""Compile shipping WKey with real extracted KeyUtils and labeled interface doubles."""
import argparse
import importlib.util
import os
from pathlib import Path
import platform
import re
import subprocess
import tempfile
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native.library_interface_runner import pinned_bytes, qt_flags, qt_environment, moc_path

ROOT = Path(__file__).resolve().parents[2]


def block(text, marker):
    start = text.index(marker)
    opening = text.index('{', start)
    depth = 1
    offset = opening + 1
    while depth:
        depth += (text[offset] == '{') - (text[offset] == '}')
        offset += 1
    return text[start:offset]


def run(output=None, baseline=False):
    def pinned(relative):
        return pinned_bytes(relative).decode()

    spec = importlib.util.spec_from_file_location(
        'library_reconstruction', ROOT / 'tests/native/library_interface_runner.py')
    reconstruction = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reconstruction)
    with tempfile.TemporaryDirectory(prefix='mixpi-key-widget-') as temporary:
        target = Path(temporary)
        reconstruction.reconstruct(target)
        if baseline:
            for name in ('wkey.cpp', 'wkey.h'):
                (target / 'src/widget' / name).write_text(pinned('src/widget/' + name))
        support = target / 'interfaces'
        for name in ('widget', 'control', 'library', 'skin/legacy', 'track'):
            (support / name).mkdir(parents=True)
        (support / 'widget/wlabel.h').write_text('''#pragma once
#include <QLabel>
#include <QDomNode>
class SkinContext;
class WLabel : public QLabel {
public:
    using QLabel::QLabel;
    virtual void onConnectedControlChanged(double, double) {}
    virtual void setup(const QDomNode&, const SkinContext&) {}
};
''')
        (support / 'control/controlproxy.h').write_text('''#pragma once
#include <QObject>
enum class ControlFlag { AllowMissingOrInvalid };
class ControlProxy {
public:
    static inline double cents = 0;
    template<class... Arguments> explicit ControlProxy(Arguments&&...) {}
    template<class... Arguments> void connectValueChanged(Arguments&&...) {}
    double get() const { return cents; }
};
''')
        (support / 'library/library_prefs.h').write_text('''#pragma once
namespace mixxx::library::prefs { inline constexpr int kKeyNotationConfigKey = 1; }
''')
        (support / 'skin/legacy/skincontext.h').write_text('''#pragma once
#include <QDomElement>
class SkinContext {
public:
    bool selectBool(const QDomNode& node, const QString& name, bool fallback) const {
        const auto child = node.firstChildElement(name);
        return child.isNull() ? fallback : child.text() == "true";
    }
};
''')
        header = pinned('src/track/keyutils.h')
        source = pinned('src/track/keyutils.cpp')
        schema = pinned('src/proto/keys.proto')
        enumeration = block(schema, 'enum ChromaticKey').replace(';', ',') + ';'
        notation = block(header, 'enum class KeyNotation') + ';'
        major = block(header, 'static inline bool keyIsMajor')
        declarations = '''#pragma once
#include <QMap>
#include <QMutex>
#include <QString>
namespace mixxx::track::io::key {
__ENUMERATION__
inline bool ChromaticKey_IsValid(int value) { return value >= 0 && value <= 24; }
}
using mixxx::track::io::key::ChromaticKey;
using mixxx::track::io::key::ChromaticKey_IsValid;
class KeyUtils {
public:
__NOTATION__
__MAJOR__
static QString keyToString(ChromaticKey key, KeyNotation notation = KeyNotation::Custom);
static ChromaticKey keyFromNumericValue(double value);
static ChromaticKey keyFromNumericValue(int value);
static QString keyDebugName(ChromaticKey key);
static int keyToOpenKeyNumber(ChromaticKey key);
static void setNotation(const QMap<ChromaticKey, QString>& notation);
private:
static QMutex s_notationMutex;
static QMap<ChromaticKey, QString> s_notation;
static QMap<QString, ChromaticKey> s_reverseNotation;
};
'''.replace('__ENUMERATION__', enumeration).replace('__NOTATION__', notation).replace('__MAJOR__', major)
        (support / 'track/keyutils.h').write_text(declarations)
        tables = '\n'.join(block(source, marker) + ';' for marker in (
            'const QString s_traditionalKeyNames[]', 'const std::array s_IDv3KeyNames'))
        functions = '\n'.join(block(source, marker) for marker in (
            'inline int openKeyNumberToLancelotNumber',
            'QString KeyUtils::keyDebugName', 'void KeyUtils::setNotation',
            'int KeyUtils::keyToOpenKeyNumber', 'QString KeyUtils::keyToString',
            'ChromaticKey KeyUtils::keyFromNumericValue(double',
            'ChromaticKey KeyUtils::keyFromNumericValue(int'))
        (target / 'keyutils_subset.cpp').write_text('''#include "track/keyutils.h"
#include <QMutexLocker>
#include <QtDebug>
#include <array>
static auto lockMutex(QMutex* mutex) { return QMutexLocker<QMutex>(mutex); }
QMutex KeyUtils::s_notationMutex;
QMap<ChromaticKey, QString> KeyUtils::s_notation;
QMap<QString, ChromaticKey> KeyUtils::s_reverseNotation;
''' + tables + '\n' + functions)
        command = [moc_path(), '-I' + str(support),
                   str(target / 'src/widget/wkey.h'), '-o', str(target / 'moc_wkey.cpp')]
        print('MOC', repr(command), flush=True)
        subprocess.run(command, check=True, timeout=30)
        command = ['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                   '-I' + str(support), '-I' + str(target / 'src'), '-I' + str(target)]
        command += [str(target / 'src/widget/wkey.cpp'),
                    str(target / 'keyutils_subset.cpp'),
                    str(ROOT / 'tests/native/key_widget_test.cpp'),
                    '-o', str(target / 'key-widget-test'),
                    *qt_flags(('QtCore', 'QtGui', 'QtWidgets', 'QtXml'))]
        print('COMPILE', repr(command), flush=True)
        subprocess.run(command, check=True, timeout=90)
        environment = qt_environment()
        arguments = [str(target / 'key-widget-test')]
        if output:
            output.mkdir(parents=True, exist_ok=True)
            arguments.append(str(output.resolve()))
        subprocess.run(arguments, check=True, timeout=30, env=environment)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--baseline', action='store_true')
    options = parser.parse_args()
    run(options.output, options.baseline)
