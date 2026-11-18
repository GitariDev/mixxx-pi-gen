"""Build F: one column setup for every track table (spec 2c, plan 12.7).

Compiles the shipped WTrackTableViewHeader, MixpiSharedColumns, MixpiTableFit,
ProxyTrackModel, BrowseTableModel, SettingsDAO, ConfigObject/ConfigAutosave and
the control framework from the patched stack, with real Qt. The view code is
copied verbatim from the patched wtracktableview.cpp: the store set up in the
constructor, its constants, and the header swap of loadTrackModel with its
build F lines. Doubles replace only the track object, the player/recording
singletons, the browse thread, the clipboard, the Library (it hands out the
track collection) and the resources ConfigObject reads.

mixxx-shared-columns.patch is applied on top of the registered stack when it
is not registered yet, which is where the registration puts it.

Modes: checks (one process), then kill (a change, SIGKILL 2 s later) and
after-kill (a new process reads the setup the killed one left).

--without-show-fit builds MixpiTableFit without its show hook (a diagnostic:
on Qt 6 offscreen the hidden close paths pass without it too, so it does not
reproduce acceptance E's report on its own).
"""
import argparse
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from library_interface_runner import (PATCH_DIR, ROOT, reconstruct, populate_pinned, qt_flags,
                                      qt_environment, moc_path)
from table_columns_runner import STUBS as TABLE_STUBS

PATCH = 'mixxx-shared-columns.patch'
KILL_AFTER_SECONDS = 2

CONFIG_FILES = [
    'preferences/configobject.h', 'preferences/configobject.cpp', 'preferences/usersettings.h',
    'control/control.cpp', 'control/control.h', 'control/controlobject.cpp',
    'control/controlobject.h', 'control/controlproxy.cpp', 'control/controlproxy.h',
    'control/controlbehavior.h', 'control/controlvalue.h', 'util/mutex.h',
    'util/thread_annotations.h', 'util/compatibility/qmutex.h', 'util/compatibility/qatomic.h',
    'util/compatibility/qhash.h', 'util/color/rgbcolor.h', 'util/optional.h',
]
CONFIG_DOUBLES = {
    'widget/wwidget.h': '#pragma once\n',
    'util/debug.h': '''#pragma once
#include <QString>
#include <QtDebug>
inline void reportFatalErrorAndQuit(const QString& message) { qFatal("%s", qPrintable(message)); }
inline void reportCriticalErrorAndQuit(const QString& message) { qFatal("%s", qPrintable(message)); }
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
    'util/cmdlineargs.h': '''#pragma once
#include <QString>
class CmdlineArgs {
  public:
    static CmdlineArgs& Instance() { static CmdlineArgs args; return args; }
    QString getResourcePath() const { return QStringLiteral("/nonexistent-mixpi-resources/"); }
};
''',
    'util/xml.h': '''#pragma once
#include <QDomNode>
#include <QString>
class XmlParse {
  public:
    static QString selectNodeQString(const QDomNode&, const QString&) { return QString(); }
};
''',
}


def between(source, start, end):
    first = source.index(start)
    last = source.index(end, first) + len(end)
    return source[first:last]


def build(target, without_show_fit=False):
    names, _ = reconstruct(target)
    if PATCH not in names:
        touched = [line.split()[2][2:] for line in (PATCH_DIR / PATCH).read_text().splitlines()
                   if line.startswith('diff --git ')]
        for path in touched:
            try:
                populate_pinned(target, [path])
            except subprocess.CalledProcessError:
                pass  # a new file of this patch
        subprocess.run(['git', 'apply', str(PATCH_DIR / PATCH)], cwd=target, check=True, timeout=15)
        names.append(PATCH)
    print('PATCHES', ' '.join(names), flush=True)
    if without_show_fit:
        fit = target / 'src/widget/mixpitablefit.h'
        hook = '            m_view->installEventFilter(m_showFilter);\n'
        text = fit.read_text()
        if hook not in text:
            raise SystemExit('show hook not found')
        fit.write_text(text.replace(hook, ''))
    populate_pinned(target, ['src/library/proxytrackmodel.cpp', 'src/library/proxytrackmodel.h',
                             'src/library/browse/browsetablemodel.cpp',
                             'src/library/browse/browsetablemodel.h', 'src/library/trackmodel.h',
                             'src/library/dao/settingsdao.h', 'src/library/dao/settingsdao.cpp',
                             'src/proto/headers.proto', 'src/util/assert.h', 'src/util/math.h',
                             'src/util/parented_ptr.h', 'src/widget/wmenucheckbox.h',
                             'src/widget/wmenucheckbox.cpp', 'src/widget/wtracktableviewheader.h',
                             'src/widget/wtracktableviewheader.cpp', 'src/widget/wtracktableview.cpp',
                             'src/widget/libraryinterface.h', 'src/library/media/mediause.h',
                             'src/library/media/mediauseregistry.h',
                             'src/library/rekordbox/sourceidentity.h',
                             'src/library/rekordbox/removablemounts.h'])
    populate_pinned(target, ['src/' + name for name in CONFIG_FILES])
    stubs = target / 'stubs'
    for name, text in {**TABLE_STUBS, **CONFIG_DOUBLES}.items():
        (stubs / name).parent.mkdir(parents=True, exist_ok=True)
        (stubs / name).write_text(text)
    view = (target / 'src/widget/wtracktableview.cpp').read_text()
    (target / 'store_constants.inc').write_text(between(
        view, '// Build F (spec 2c): the one column setup',
        'const QString kTracksHeaderSetting = QStringLiteral("mixxx.db.model.library.header_state_pb");\n'))
    (target / 'store_block.inc').write_text(between(
        view, '    if (m_pConfig && !WTrackTableViewHeader::hasSharedStore()) {', '        });\n    }\n'))
    (target / 'header_swap.inc').write_text(between(
        view, "    // Save the previous track model's header state",
        '        m_columnFit.refit();\n    });\n'))
    generated = target / 'generated'
    (generated / 'proto').mkdir(parents=True)
    subprocess.run(['protoc', '--proto_path=' + str(target / 'src/proto'),
                    '--cpp_out=' + str(generated / 'proto'),
                    str(target / 'src/proto/headers.proto')], check=True, timeout=30)
    includes = ['-I' + str(stubs), '-I' + str(target / 'src'), '-I' + str(generated), '-I' + str(target)]
    mocs = []
    for header in ('widget/wtracktableviewheader.h', 'widget/wmenucheckbox.h', 'library/proxytrackmodel.h',
                   'library/browse/browsetablemodel.h', 'control/control.h', 'control/controlobject.h',
                   'control/controlproxy.h'):
        path = target / 'src' / header
        output = path.parent / ('moc_' + path.stem + '.cpp')
        subprocess.run([moc_path(), *includes, str(path), '-o', str(output)], check=True, timeout=20)
    for header, output in ((stubs / 'library/browse/browsethread.h', target / 'moc_browsethread.cpp'),
                           (stubs / 'mixer/playerinfo.h', target / 'moc_playerinfo.cpp'),
                           (stubs / 'widget/wlibrarytableview.h', target / 'moc_wlibrarytableview.cpp')):
        subprocess.run([moc_path(), *includes, str(header), '-o', str(output)], check=True, timeout=20)
        mocs.append(output)
    sources = [ROOT / 'tests/native/shared_columns_test.cpp',
               *[target / 'src' / name for name in (
                   'widget/wtracktableviewheader.cpp', 'widget/wmenucheckbox.cpp',
                   'library/proxytrackmodel.cpp', 'library/browse/browsetablemodel.cpp',
                   'library/dao/settingsdao.cpp', 'preferences/configobject.cpp',
                   'control/control.cpp', 'control/controlobject.cpp', 'control/controlproxy.cpp')],
               generated / 'proto/headers.pb.cc', *mocs]
    binary = target / 'shared-columns-test'
    command = ['c++', '-std=c++20', '-Wall', '-Wextra', '-Werror', '-Wno-deprecated-declarations',
               '-DMIXXX_DEBUG_ASSERTIONS_ENABLED', *includes, *map(str, sources), '-o', str(binary),
               '-pthread', *qt_flags(('QtCore', 'QtGui', 'QtWidgets', 'QtSql', 'QtXml', 'QtTest')),
               *shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'protobuf'],
                                                    text=True, timeout=15))]
    print('COMMAND', repr(command), flush=True)
    subprocess.run(command, check=True, timeout=400)
    return binary


def run_kill(binary, directory):
    """A change, SIGKILL 2 s later, then a new process reads what is left."""
    process = subprocess.Popen([str(binary), 'kill', str(directory)], env=qt_environment(),
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    changed = ''
    for line in process.stdout:
        if line.startswith('CHANGED '):
            changed = line.split(None, 1)[1].strip()
            break
    if not changed:
        process.kill()
        print('FAIL kill: the change was made', flush=True)
        return 1
    time.sleep(KILL_AFTER_SECONDS)
    process.send_signal(signal.SIGKILL)
    process.communicate(timeout=10)
    after = subprocess.run([str(binary), 'after-kill', str(directory)], env=qt_environment(),
                           capture_output=True, text=True, timeout=60)
    restored = ''
    for line in after.stdout.splitlines():
        if line.startswith('RESTORED '):
            restored = line.split(None, 1)[1].strip()
    print('OBSERVE kill: changed', changed, 'restored', restored, flush=True)
    ok = process.returncode == -signal.SIGKILL and restored == changed and changed.startswith('150 key,')
    print(('PASS' if ok else 'FAIL') +
          ' kill: the setup changed 2 s before a SIGKILL is there after a restart', flush=True)
    return 0 if ok else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--without-show-fit', action='store_true')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='mixpi-shared-columns-') as temporary:
        target = Path(temporary)
        binary = build(target / 'build', args.without_show_fit)
        status = 0
        for mode in ('checks',) if args.without_show_fit else ('checks', 'kill'):
            directory = target / 'run' / mode
            directory.mkdir(parents=True)
            if mode == 'kill':
                status |= run_kill(binary, directory)
                continue
            result = subprocess.run([str(binary), mode, str(directory)], env=qt_environment(),
                                    capture_output=True, text=True, timeout=180)
            print(result.stdout, result.stderr[-6000:], flush=True)
            status |= 1 if result.returncode else 0
        print('SHARED_COLUMNS_EXIT', status, flush=True)
        raise SystemExit(status)


if __name__ == '__main__':
    main()
