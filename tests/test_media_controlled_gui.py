from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from test_media_identity import added_header
from test_media_completion import function_text
from test_media_ownership import production_file
from test_library_interface import RUNNER

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / 'stage3/01-install-packages/files/mixxx-media-selection.patch'


def browse_refresh_fixture():
    browse = production_file('src/library/browse/browsefeature.cpp')
    model = production_file('src/library/browse/foldertreemodel.cpp')
    tree = production_file('src/library/treeitemmodel.cpp')
    template = (ROOT / 'tests/native/media_browse_refresh_test.h.in').read_text()
    replacements = {
        'PRODUCTION_MEDIA_REFRESH': function_text(browse, 'void BrowseFeature::refreshMediaLifecycle('),
        'PRODUCTION_DIRECTORY_PROBE': function_text(model, 'bool FolderTreeModel::directoryHasChildren('),
        'PRODUCTION_DEFER_PROBES': function_text(model, 'void FolderTreeModel::deferDirectoryProbes('),
        'PRODUCTION_REMEMBER_CHILDREN': function_text(model, 'void FolderTreeModel::rememberChildDirectories('),
        'PRODUCTION_REPAINT': function_text(tree, 'void TreeItemModel::triggerRepaint()').replace(
            'TreeItemModel::', 'FolderTreeModel::'),
    }
    for marker, method in replacements.items():
        template = template.replace(marker, method)
    return template


class ControlledGuiTests(unittest.TestCase):
    def test_production_qt_event_loop_and_dialog(self):
        if sys.platform != 'linux' or not shutil.which('pkg-config'):
            self.skipTest('Linux Qt6 scratch harness required; no real media used')
        flags = subprocess.run(['pkg-config', '--cflags', '--libs', 'Qt6Widgets'],
                               capture_output=True, text=True)
        if flags.returncode:
            self.skipTest('Qt6Widgets development files required')
        with tempfile.TemporaryDirectory(prefix='mixpi-controlled-gui-') as directory:
            target = Path(directory)
            RUNNER.reconstruct(target)
            (target / 'media_browse_refresh_test.h').write_text(browse_refresh_fixture())
            executable = target / 'gui-test'
            subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-I' + str(target), '-I' + str(target / 'src'),
                            str(ROOT / 'tests/native/media_controlled_gui_test.cpp'),
                            '-o', str(executable), *flags.stdout.split()], check=True,
                           capture_output=True, text=True)
            result = subprocess.run([str(executable)], env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
                                    capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('PASS production Qt', result.stdout)

    def test_success_refresh_uses_owner_scoped_completion(self):
        source = added_header(PATCH, 'src/library/mixpimedia.h')
        self.assertIn('m_controlled->setCompletionHandler(this, m_refreshSources)', source)
        self.assertNotIn('m_lastLifecycle', source)
        self.assertNotIn('lifecycleTimer', source)
        library = production_file('src/library/library.cpp')
        self.assertIn('m_pBrowseFeature->refreshMediaLifecycle()', library)
        self.assertNotIn('m_pBrowseFeature->slotRefreshDirectoryTree()', library)

    def test_media_refresh_invalidates_without_activating_or_enumerating(self):
        source = production_file('src/library/browse/browsefeature.cpp')
        refresh = function_text(source, 'void BrowseFeature::refreshMediaLifecycle(')
        self.assertLess(refresh.index('deferDirectoryProbes'), refresh.index('removeRows'))
        self.assertIn('QUICK_LINK_NODE', refresh)
        self.assertNotIn('m_lastRightClickedIndex', refresh)
        for forbidden in ('activate', 'onLazyChildExpandation', 'createRemovableDevices', 'FileAccess'):
            self.assertNotIn(forbidden, refresh)

    def test_directory_probes_defer_until_explicit_expansion(self):
        model = production_file('src/library/browse/foldertreemodel.cpp')
        probe = function_text(model, 'bool FolderTreeModel::directoryHasChildren(')
        self.assertLess(probe.index('m_directoryProbesDeferred'), probe.index('FileAccess'))
        defer = function_text(model, 'void FolderTreeModel::deferDirectoryProbes(')
        self.assertLess(defer.index('m_directoryProbesDeferred = true'), defer.index('m_directoryCache.clear'))
        browse = production_file('src/library/browse/browsefeature.cpp')
        expand = function_text(browse, 'void BrowseFeature::onLazyChildExpandation(')
        self.assertLess(expand.index('folders = getChildDirectoryItems(path)'),
                        expand.index('rememberChildDirectories(path, !folders.empty())'))
        self.assertLess(expand.index('rememberChildDirectories(path, !folders.empty())'),
                        expand.index('triggerRepaint(idx)'))

    def test_native_loader_keeps_volume_identity_separate(self):
        source = added_header(PATCH, 'src/library/mixpimedia.h')
        self.assertIn('showControlled(true)', source)
        self.assertIn('m_controlled->locked()', source)
        self.assertIn('const auto entry = resolve(snapshot, token, eject)', source)
        self.assertIn('const QString error = m_openSource(entry)', source)
        self.assertNotIn('waitForFinished', source)
        self.assertNotIn('waitForReadyRead', source)


if __name__ == '__main__':
    unittest.main()
