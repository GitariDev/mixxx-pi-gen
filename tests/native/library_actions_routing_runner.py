"""Real Qt + exact pinned/patched WLibrary TU and Library wiring.

Minimal labeled doubles replace unrelated app shell, track model/menu/deck backend,
LibraryControl and skin setup. This verifies routing, not full Mixxx acceptance.
"""
import argparse
import hashlib
from pathlib import Path
import re
import subprocess
import tempfile
from library_interface_runner import (ROOT, reconstruct, populate_pinned, qt_flags,
                                      qt_environment, moc_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--holdout', action='store_true')
    parser.add_argument('--baseline', action='store_true')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='mixpi-actions-routing-') as temporary:
        target = Path(temporary)
        names, _ = reconstruct(target)
        populate_pinned(target, ['src/widget/wlibrary.cpp', 'src/widget/wlibrary.h'])
        if args.baseline:
            preimage = ROOT / 'deploy/recovery-20261115/actions-routing/preimages/stage3/01-install-packages/files/mixxx-library-interface.patch'
            patch_dir = ROOT / 'stage3/01-install-packages/files'
            for name in reversed(names):
                subprocess.run(['git', 'apply', '--reverse', str(patch_dir / name)], cwd=target, check=True)
            for name in names:
                patch = preimage if name == 'mixxx-library-interface.patch' else patch_dir / name
                subprocess.run(['git', 'apply', str(patch)], cwd=target, check=True)
        stubs = target / 'stubs'
        for name in ['library', 'skin/legacy', 'util/compatibility', 'widget', 'util']:
            (stubs / name).mkdir(parents=True, exist_ok=True)
        (stubs / 'library/library_decl.h').write_text('enum class FocusWidget { Sidebar };\n')
        (stubs / 'library/libraryview.h').write_text('''#pragma once
#include <QString>
class LibraryView { public: virtual ~LibraryView() = default;
virtual void onShow() {} virtual void pasteFromSidebar() {} virtual void onSearch(const QString&) {}
virtual void saveCurrentViewState() {} virtual bool restoreCurrentViewState() { return true; } };
''')
        (stubs / 'skin/legacy/skincontext.h').write_text('''#pragma once
#include <QString>
class QDomNode {};
class SkinContext { public: bool selectBool(const QDomNode&, const char*, bool v) const { return v; }
double selectDouble(const QDomNode&, const char*, double v) const { return v; } };
''')
        (stubs / 'util/compatibility/qmutex.h').write_text('''#pragma once
#include <QRecursiveMutex>
#include <QMutexLocker>
#define QT_RECURSIVE_MUTEX QRecursiveMutex
#define QT_RECURSIVE_MUTEX_INIT
inline auto lockMutex(QRecursiveMutex* mutex) { return QMutexLocker<QRecursiveMutex>(mutex); }
''')
        (stubs / 'widget/wbasewidget.h').write_text('''#pragma once
#include <QWidget>
struct WBaseWidget { explicit WBaseWidget(QWidget*) {} void updateTooltip() {} };
''')
        (stubs / 'util/math.h').write_text('''#pragma once
#include <algorithm>
#define math_clamp(v,a,b) std::clamp(v,a,b)
#define VERIFY_OR_DEBUG_ASSERT(v) if (!(v))
''')
        (stubs / 'widget/wtracktableview.h').write_bytes((ROOT / 'tests/native/library_actions_routing_doubles.h').read_bytes())
        library = (target / 'src/library/library.cpp').read_text()
        start = library.index('    connect(m_pLibraryControl,\n            &LibraryControl::showHideTrackMenu,')
        end = library.index('\n\n', start)
        (target / 'routing_wiring.inc').write_text(library[start:end])
        for header, output in [(target / 'src/widget/wlibrary.h', target / 'src/widget/moc_wlibrary.cpp'),
                               (stubs / 'widget/wtracktableview.h', target / 'moc_doubles.cpp')]:
            subprocess.run([moc_path(), '-I' + str(stubs), '-I' + str(target / 'src'), str(header), '-o', str(output)], check=True, timeout=20)
        command = ['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                   '-I' + str(stubs), '-I' + str(target / 'src'), '-I' + str(target),
                   str(ROOT / 'tests/native/library_actions_routing_test.cpp'),
                   str(target / 'src/widget/wlibrary.cpp'), str(target / 'moc_doubles.cpp'),
                   '-o', str(target / 'test'), *qt_flags()]
        for path in [target / 'src/widget/wlibrary.cpp', target / 'src/widget/wlibrary.h', target / 'routing_wiring.inc']:
            print('PRODUCTION_INPUT', path.name, hashlib.sha256(path.read_bytes()).hexdigest(), flush=True)
        subprocess.run(command, check=True, timeout=90)
        subprocess.run([str(target / 'test'), *(['holdout'] if args.holdout else [])], env=qt_environment(), check=True, timeout=30)


if __name__ == '__main__':
    main()
