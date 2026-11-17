"""Actual SidebarModel/TreeItemModel TUs; feature/config/app-shell substitutes only."""
import argparse
import hashlib
import os
from pathlib import Path
import platform
import re
import subprocess
import tempfile

from library_interface_runner import ROOT, reconstruct, populate_pinned, qt_flags, qt_environment, moc_path

def method(source, signature):
    start = source.index(signature)
    brace = source.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end] + '\n'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', action='store_true')
    parser.add_argument('--holdout', action='store_true')
    # Evidence only: the same checks without mixxx-source-tap.patch must fail.
    parser.add_argument('--without-source-tap', action='store_true')
    parser.add_argument('--without-bpm-lock-touch', action='store_true')
    parser.add_argument('--without-acceptance-fixes', action='store_true')
    parser.add_argument('--without-council-fixes', action='store_true')
    # R-9/R-10: only the Sources screen (rail, crumb, edit list) checks.
    parser.add_argument('--sources-screen', action='store_true')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='mixpi-source-model-') as temporary:
        target = Path(temporary)
        # mixxx-acceptance-fixes.patch applies on top of bpm-lock-touch, and
        # mixxx-council-fixes.patch on top of source-tap and acceptance-fixes.
        exclude = (('mixxx-source-tap.patch', 'mixxx-council-fixes.patch')
                   if args.without_source_tap else ()) + \
            (('mixxx-bpm-lock-touch.patch', 'mixxx-acceptance-fixes.patch', 'mixxx-council-fixes.patch')
             if args.without_bpm_lock_touch else ()) + \
            (('mixxx-acceptance-fixes.patch', 'mixxx-council-fixes.patch')
             if args.without_acceptance_fixes else ()) + \
            (('mixxx-council-fixes.patch',) if args.without_council_fixes else ())
        # mixxx-sources-screen.patch (R-9, R-10) applies on top of council-fixes.
        if 'mixxx-council-fixes.patch' in exclude:
            exclude += ('mixxx-sources-screen.patch',)
        names, _ = reconstruct(target, exclude=exclude)
        sources_screen = 'mixxx-sources-screen.patch' in names
        populate_pinned(target, ['src/' + name for name in ('library/treeitem.h', 'library/treeitem.cpp',
                     'library/treeitemmodel.h', 'library/treeitemmodel.cpp',
                     'util/make_const_iterator.h')])
        stubs = target / 'stubs'
        (stubs / 'library').mkdir(parents=True)
        (stubs / 'util').mkdir()
        (stubs / 'library/libraryfeature.h').write_text(
            (ROOT / 'tests/native/library_interface_sources_stubs.h').read_text())
        (stubs / 'util/assert.h').write_text(
            '#pragma once\n#include <cassert>\n'
            '#define DEBUG_ASSERT(value) assert(value)\n'
            '#define VERIFY_OR_DEBUG_ASSERT(value) if (!(value))\n')
        (stubs / 'util/cmdlineargs.h').write_text(
            '#pragma once\nstruct CmdlineArgs { static CmdlineArgs& Instance() '
            '{ static CmdlineArgs instance; return instance; } '
            'bool getDeveloper() const { return false; } };\n')
        for name in ('preferences', 'control', 'widget'):
            (stubs / name).mkdir(exist_ok=True)
        (stubs / 'preferences/configobject.h').write_text(
            '#pragma once\n#include <QString>\nstruct ConfigKey {\n    QString key;\n'
            '    ConfigKey(QString group, QString name) : key(group + "/" + name) {}\n};\n')
        # WLibrarySidebar's app-shell dependencies only.
        (stubs / 'control/controlobject.h').write_text('''#pragma once
#include <QHash>
#include <functional>
#include "preferences/configobject.h"
#include "util/assert.h"  // reached through control/control.h in the real header
enum class ControlFlag { None = 0, NoAssertIfMissing = 2, NoWarnIfMissing = 6 };
class ControlObject {
  public:
    static ControlObject* getControl(const ConfigKey& key, ControlFlag = ControlFlag::None) {
        static QHash<QString, ControlObject*> controls;
        auto*& control = controls[key.key];
        if (!control) { control = new ControlObject; }
        return control;
    }
    void set(double value) { m_value = value; ++writes; }
    double get() const { return m_value; }
    int writes = 0;
    template<typename Receiver, typename Slot>
    void connectValueChangeRequest(Receiver*, Slot slot) { m_request = slot; }
    void requestChange(double value) { if (m_request) { m_request(value); } }
  private:
    double m_value = 0;
    std::function<void(double)> m_request;
};
''')
        (stubs / 'widget/wbasewidget.h').write_text(
            '#pragma once\n#include <QWidget>\nstruct WBaseWidget {\n'
            '    explicit WBaseWidget(QWidget*) {}\n    virtual ~WBaseWidget() = default;\n'
            '    void updateTooltip() {}\n};\n')
        (stubs / 'util/dnd.h').write_text('''#pragma once
#include <QDropEvent>
#include <QList>
#include <QMimeData>
#include <QUrl>
namespace mixxx { class FileInfo {}; }
struct DragAndDropHelper {
    static QList<mixxx::FileInfo> supportedTracksFromUrls(const QList<QUrl>&, bool, bool) { return {}; }
};
''')
        populate_pinned(target, ['src/util/defs.h', 'src/widget/wlibrarysidebar.h',
                                 'src/widget/wlibrarysidebar.cpp', 'src/library/library_decl.h'])
        # The real BPM column delegate chain (bpm_lock check box).
        delegates = ['bpmdelegate', 'checkboxdelegate', 'tableitemdelegate', 'defaultdelegate']
        populate_pinned(target, ['src/util/painterscope.h', 'src/util/parented_ptr.h'] +
                        [f'src/library/tabledelegates/{name}.{suffix}'
                         for name in delegates for suffix in ('h', 'cpp')])
        (stubs / 'widget/wtracktableview.h').write_text('''#pragma once
#include <QColor>
#include <QTableView>
// Only what TableItemDelegate reads from the real WTrackTableView.
class WTrackTableView : public QTableView {
    Q_OBJECT
  public:
    QColor getFocusBorderColor() const { return {}; }
  signals:
    void focusBorderColorChanged(QColor color);
};
''')
        library = (target / 'src/library/library.cpp').read_text()
        signatures = ['void Library::applySidebarSourceOrder()',
                      'void Library::saveSidebarSourceOrder(',
                      'void Library::applySidebarSourceVisibility()',
                      'void Library::showSidebarSourcesMenu()',
                      'void Library::onSkinLoadFinished()']
        if sources_screen:
            signatures.append('void Library::refreshSidebarSourceEdit()')
        # mixxx-source-groups.patch: Sources edit lists tiles on a Sources screen.
        source_groups = 'mixxx-source-groups.patch' in names
        if source_groups:
            signatures += ['bool Library::groupedSources()', 'QStringList Library::sourceGroupOrder()',
                           'bool Library::sourceGroupVisible(', 'void Library::moveSourceGroup(']
        (target / 'library_order_methods.h').write_text(
            '\n'.join(method(library, signature) for signature in signatures))
        # The exact sidebar activation wiring from Library::bindSidebarWidget.
        start = library.index('    connect(pSidebarWidget,\n            &WLibrarySidebar::pressed,')
        end = library.index('&SidebarModel::clicked);\n', start) + len('&SidebarModel::clicked);\n')
        (target / 'sidebar_activation_wiring.inc').write_text(library[start:end])
        if args.baseline:
            preimage = ROOT / 'deploy/recovery-20261111/native-completion-slice/sources/stack-preimage'
            for name in ('sidebarmodel.h', 'sidebarmodel.cpp'):
                (target / 'src/library' / name).write_bytes(
                    (preimage / 'src/library' / name).read_bytes())
        command = ['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror']
        command += ['-I' + str(stubs), '-I' + str(target / 'src'), '-I' + str(target)]
        if args.baseline:
            command += ['-DSOURCE_ORDER_BASELINE']
        # The menu style block from the skin (R-10: the edit list rules).
        menus = target / 'pioneered-menus.qss'
        menus.write_bytes((ROOT / 'stage3/01-install-packages/files/pioneered-menus.qss').read_bytes())
        command += ['-DMIXPI_MENUS_QSS="' + str(menus) + '"']
        if sources_screen:
            command += ['-DMIXPI_SOURCES_SCREEN']
        if source_groups:
            command += ['-DMIXPI_SOURCE_GROUPS']
        mocs = [(target / 'src/library/sidebarmodel.h', target / 'src/library/moc_sidebarmodel.cpp'),
                (target / 'src/library/treeitemmodel.h', target / 'src/library/moc_treeitemmodel.cpp'),
                (stubs / 'library/libraryfeature.h', target / 'moc_feature.cpp')]
        if not args.baseline:
            mocs.append((target / 'src/widget/wlibrarysidebar.h',
                         target / 'src/widget/moc_wlibrarysidebar.cpp'))
            mocs.append((stubs / 'widget/wtracktableview.h', target / 'moc_wtracktableview.cpp'))
            for name in delegates:
                mocs.append((target / f'src/library/tabledelegates/{name}.h',
                             target / f'src/library/tabledelegates/moc_{name}.cpp'))
        for header, output in mocs:
            subprocess.run([moc_path(), str(header), '-o', str(output)],
                           check=True, timeout=20)
        command += [str(ROOT / 'tests/native/library_interface_sources_test.cpp'),
                    str(target / 'src/library/sidebarmodel.cpp'),
                    str(target / 'src/library/treeitem.cpp'),
                    str(target / 'src/library/treeitemmodel.cpp'),
                    str(target / 'moc_feature.cpp'), '-o', str(target / 'test')]
        if not args.baseline:
            command.insert(-2, str(target / 'src/widget/wlibrarysidebar.cpp'))
            command[-2:-2] = [str(target / 'moc_wtracktableview.cpp')] + [
                str(target / f'src/library/tabledelegates/{name}.cpp') for name in delegates]
        for source in sorted(target.rglob('*')):
            if source.is_file():
                print('INPUT', source.relative_to(target),
                      hashlib.sha256(source.read_bytes()).hexdigest(), flush=True)
        command += qt_flags(('QtCore', 'QtGui', 'QtWidgets', 'QtTest'))
        print('COMMAND', repr(command), flush=True)
        subprocess.run(command, check=True, timeout=90)
        environment = qt_environment()
        subprocess.run([str(target / 'test'), *(['holdout'] if args.holdout else []),
                        *(['sources-screen'] if args.sources_screen else [])],
                       env=environment, check=True, timeout=30)


if __name__ == '__main__':
    main()
