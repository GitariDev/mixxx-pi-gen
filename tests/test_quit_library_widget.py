"""Acceptance I, X2: Ctrl+Q with a deck or pad loaded from a drive must not
reach the skin's deleted WLibrary. mixxx-media-chip-ping.patch made every
deck and pad track change run MixpiMedia::refresh(), which finds the skin root
through Library::m_pLibraryWidget. Quit deletes the skin before the players,
so the players' unloads read the freed widget (a SIGSEGV on the card).
mixxx-quit-library-widget.patch holds the widget as a QPointer<WLibrary>."""
import os
from pathlib import Path
import re
import tempfile
import unittest

from native.library_interface_runner import PATCH_DIR, qt_available
from native import quit_library_widget_runner as runner

PATCH = PATCH_DIR / runner.PATCH
RUNS = 20


def function(text, signature):
    return text.split(signature, 1)[1].split('\n    }\n', 1)[0]


class QuitLibraryWidgetPatchTests(unittest.TestCase):
    def test_patch_changes_only_the_member_type(self):
        text = PATCH.read_text()
        self.assertEqual(re.findall(r'^diff --git a/(\S+) ', text, re.MULTILINE), ['src/library/library.h'])
        removed = [line[1:] for line in text.splitlines() if line[:1] == '-' and line[:3] != '---']
        added = [line[1:].strip() for line in text.splitlines() if line[:1] == '+' and line[:3] != '+++']
        self.assertEqual(removed, ['    WLibrary* m_pLibraryWidget;'])
        self.assertEqual([line for line in added if not line.startswith('//')],
                         ['QPointer<WLibrary> m_pLibraryWidget;'])


@unittest.skipUnless(os.environ.get('MIXXX_TEST_SOURCE'), 'MIXXX_TEST_SOURCE required')
class QuitLibraryWidgetSourceTests(unittest.TestCase):
    """The fixture's model of the quit path still matches the stack."""

    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='mixpi-quit-library-widget-src-')
        cls.target = Path(cls.temporary.name)
        runner.stack(cls.target, fix=True)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def read(self, path):
        return (self.target / path).read_text()

    def test_the_widget_is_a_guarded_pointer_and_the_lambda_returns_it(self):
        declared, _ = runner.member(self.target)
        self.assertEqual(declared, 'QPointer<WLibrary>')
        self.assertIn('#include <QPointer>', self.read('src/library/library.h'))

    def test_every_unload_reaches_the_lookup_through_the_widget(self):
        media = self.read('src/library/mixpimedia.h')
        hook = media.split('&PlayerInfo::trackChanged, this,', 1)[1].split('});', 1)[0]
        self.assertIn('refresh();', hook)
        refresh = function(media, '    void refresh() {')
        self.assertIn('mixpiSetNamedLabelText<WLabel>(window(), QStringLiteral("MixpiUsbName")', refresh)
        self.assertIn('if (m_page) {', refresh)
        self.assertIn('return mixpiSkinRoot(m_parent ? m_parent() : nullptr);',
                      function(media, '    QWidget* window() const {'))
        # The other widgets refresh() and the strip reach are guarded already.
        for member in ('QPointer<MixpiMediaPage> m_page;', 'QPointer<MixpiBottomStrip> m_strip;',
                       'QPointer<QDialog> m_dialog;'):
            self.assertIn(member, media)
        self.assertIn('if (!root) {\n        return 0;', self.read('src/library/mixpimediapage.h'))
        self.assertIn('QPointer<WLibrarySidebar> m_pSidebarWidget;', self.read('src/library/library.h'))

    def test_quit_deletes_the_skin_before_the_players(self):
        window = self.read('src/mixxxmainwindow.cpp')
        skin = window.index('"deleting skin"')
        self.assertIn('setCentralWidget(nullptr);', window[skin:skin + 200])
        core = self.read('src/coreservices.cpp')
        self.assertLess(core.index('CLEAR_AND_CHECK_DELETED(m_pPlayerManager);'),
                        core.index('CLEAR_AND_CHECK_DELETED(m_pLibrary);'))


@unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
class QuitLibraryWidgetNativeTests(unittest.TestCase):
    RUNNING = ('running: the lookup through the library widget finds the skin root',
               'running: a deck load sets the USB chip to GANDER1',
               'running: the Media page is open over the skin',
               'running: a ping shows on the bottom strip',
               'quit: the skin is deleted',
               'quit: the skin\'s WLibrary is deleted with it',
               'quit: the Media page and the strip go with the skin',
               'quit: each deck and pad unload ran refresh()')
    GUARDED = ('quit: no unload reached the deleted WLibrary',
               'quit: the lookup returns no widget once the skin is gone')

    def build(self, temporary, fix):
        binary, declared = runner.build(Path(temporary), fix=fix)
        self.assertEqual(declared, 'QPointer<WLibrary>' if fix else 'WLibrary*')
        return binary

    def test_quit_with_a_drive_loaded_does_not_reach_the_deleted_widget(self):
        with tempfile.TemporaryDirectory(prefix='mixpi-quit-library-widget-') as temporary:
            binary = self.build(temporary, fix=True)
            for mode in ('report', 'use'):
                for attempt in range(RUNS):
                    result = runner.run(binary, mode)
                    if attempt == 0:
                        print(mode, result.stdout, result.stderr[-2000:], flush=True)
                    self.assertEqual(result.returncode, 0, (mode, attempt, result.stdout, result.stderr[-2000:]))
                    self.assertIn('\n0 failures', result.stdout)
                    for name in self.RUNNING + self.GUARDED:
                        self.assertIn('PASS ' + name, result.stdout)
                    self.assertNotIn('USE-AFTER-FREE', result.stdout)

    def test_without_the_patch_quit_reaches_the_deleted_widget(self):
        # Build I: the raw WLibrary* still points at the deleted widget.
        with tempfile.TemporaryDirectory(prefix='mixpi-quit-library-widget-raw-') as temporary:
            binary = self.build(temporary, fix=False)
            for attempt in range(RUNS):
                result = runner.run(binary, 'report')
                if attempt == 0:
                    print('report', result.stdout, result.stderr[-2000:], flush=True)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertEqual(result.stdout.count('USE-AFTER-FREE refresh() reached the deleted WLibrary'), 4)
                for name in self.RUNNING:
                    self.assertIn('PASS ' + name, result.stdout)
                for name in self.GUARDED:
                    self.assertIn('FAIL ' + name, result.stdout)
            # Making the lookup as refresh() does faults on the freed widget.
            for attempt in range(RUNS):
                result = runner.run(binary, 'use')
                if attempt == 0:
                    print('use', result.returncode, result.stdout, result.stderr[-2000:], flush=True)
                self.assertLess(result.returncode, 0, (attempt, result.stdout))
                self.assertIn('UNLOADING', result.stdout)
                self.assertNotIn('failures', result.stdout)


if __name__ == '__main__':
    unittest.main()
