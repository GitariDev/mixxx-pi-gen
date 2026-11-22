"""Apply the complete image patch stack to the real, pinned upstream source.

No Qt installation is required. This checks patch compatibility, not C++ build
or runtime behaviour. Offline runs skip the network check explicitly.
"""
from pathlib import Path
import os
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "stage3/01-install-packages/01-run.sh"
PATCH_DIR = RECIPE.parent / "files"
UPSTREAM = "https://github.com/mixxxdj/mixxx.git"


def patch_names():
    return subprocess.run(
        ["bash", str(RECIPE), "--mixxx-print-patches"],
        capture_output=True, text=True, check=True,
    ).stdout.splitlines()


class PackageRecipeTests(unittest.TestCase):
    def test_patch_order_and_shell_syntax(self):
        self.assertEqual(patch_names(), [
            "mixxx-gcc14-djinterop.patch",
            "mixxx-media-hotplug.patch",
            "mixxx-readahead.patch",
            "mixxx-removable-ram-cache.patch",
            "mixxx-sidebar-sources.patch",
            "mixxx-touch-source-navigation.patch",
            "mixxx-performance-settings.patch",
            "mixxx-effect-placeholder.patch",
            "mixxx-right-overlay.patch",
            "mixxx-media-selection.patch",
            "mixxx-library-interface.patch",
            "mixxx-recording-lifecycle.patch",
            "mixxx-initial-library.patch",
            "mixxx-media-continuation.patch",
            "mixxx-analysis-safety.patch",
            "mixxx-media-activity.patch",
            "mixxx-import-cancellation.patch",
            "mixxx-transfer-reporting.patch",
            "mixxx-transfer-display.patch",
            "mixxx-quiet-scan.patch",
            "mixxx-preferences-entry.patch",
            "mixxx-position-display.patch",
            "mixxx-dialog-wording.patch",
            "mixxx-source-tap.patch",
            "mixxx-table-columns.patch",
            "mixxx-touch-dialogs.patch",
            "mixxx-bpm-lock-touch.patch",
            "mixxx-acceptance-fixes.patch",
            "mixxx-council-fixes.patch",
            "mixxx-clean-quit.patch",
            "mixxx-save-on-change.patch",
            "mixxx-sources-screen.patch",
            "mixxx-scan-progress.patch",
            "mixxx-media-screen.patch",
            "mixxx-media-handover.patch",
            "mixxx-sample-browser.patch",
            "mixxx-source-groups.patch",
            "mixxx-media-screen-fixes.patch",
            "mixxx-settings-fixes.patch",
            "mixxx-scan-strip-fixes.patch",
            "mixxx-sources-edit-done.patch",
            "mixxx-media-lists.patch",
            "mixxx-sources-menu.patch",
            "mixxx-media-agreed.patch",
            "mixxx-effects-save.patch",
            "mixxx-save-within-second.patch",
            "mixxx-agreed-controls.patch",
            "mixxx-sources-menu-fixes.patch",
            "mixxx-sources-start-rows.patch",
            "mixxx-table-fit-media-open.patch",
            "mixxx-sources-open-edge.patch",
            "mixxx-sampler-clear-playing.patch",
            "mixxx-shared-columns.patch",
            "mixxx-overview-playposition.patch",
            "mixxx-shared-columns-width.patch",
            "mixxx-shared-columns-stretch.patch",
            "mixxx-drive-tracks-row.patch",
            "mixxx-media-chip-ping.patch",
            "mixxx-sources-menu-shadow.patch",
            "mixxx-quit-library-widget.patch",
            "mixxx-eject-top-menu.patch",
            "mixxx-media-open-inside.patch",
            "mixxx-external-sort.patch",
            "mixxx-drive-track-cache.patch",
            "mixxx-rekordbox-utf16-text.patch",
            "mixxx-zoom-setting.patch",
            "mixxx-eject-folders-view.patch",
            "mixxx-removable-rows-fix.patch",
            "mixxx-open-remount.patch",
            "mixxx-waveform-height.patch",
            "mixxx-waveform-height-gain.patch",
            "mixxx-menu-place-fix.patch",
        ])
        subprocess.run(["bash", "-n", str(RECIPE)], check=True)
        for name in patch_names():
            self.assertTrue((PATCH_DIR / name).is_file(), name)


# Patches that need earlier patches of the stack (direct prerequisites; the
# check expands them). Every other patch must apply to pristine upstream on
# its own, and every listed patch must actually need its prerequisites.
PREREQUISITES = {
    "mixxx-media-lists.patch": ["mixxx-media-handover.patch"],
    "mixxx-sources-menu.patch": ["mixxx-sources-edit-done.patch"],
    "mixxx-media-agreed.patch": ["mixxx-media-screen-fixes.patch", "mixxx-media-lists.patch"],
    "mixxx-effects-save.patch": ["mixxx-save-on-change.patch"],
    "mixxx-save-within-second.patch": ["mixxx-save-on-change.patch"],
    "mixxx-agreed-controls.patch": ["mixxx-effects-save.patch"],
    "mixxx-sources-menu-fixes.patch": ["mixxx-sources-menu.patch", "mixxx-media-agreed.patch"],
    "mixxx-sources-start-rows.patch": ["mixxx-sources-menu-fixes.patch"],
    "mixxx-table-fit-media-open.patch": ["mixxx-sources-menu-fixes.patch"],
    "mixxx-sources-open-edge.patch": ["mixxx-sources-start-rows.patch"],
    "mixxx-sampler-clear-playing.patch": ["mixxx-agreed-controls.patch"],
    "mixxx-shared-columns.patch": ["mixxx-table-fit-media-open.patch"],
    "mixxx-shared-columns-width.patch": ["mixxx-shared-columns.patch"],
    "mixxx-shared-columns-stretch.patch": ["mixxx-shared-columns-width.patch"],
    "mixxx-drive-tracks-row.patch": ["mixxx-media-continuation.patch"],
    "mixxx-media-chip-ping.patch": ["mixxx-media-agreed.patch"],
    "mixxx-sources-menu-shadow.patch": ["mixxx-right-overlay.patch"],
    "mixxx-eject-top-menu.patch": ["mixxx-sources-open-edge.patch", "mixxx-drive-tracks-row.patch"],
    "mixxx-media-open-inside.patch": ["mixxx-eject-top-menu.patch"],
    "mixxx-drive-track-cache.patch": ["mixxx-drive-tracks-row.patch"],
    "mixxx-zoom-setting.patch": ["mixxx-agreed-controls.patch"],
    "mixxx-eject-folders-view.patch": ["mixxx-media-open-inside.patch"],
    "mixxx-removable-rows-fix.patch": ["mixxx-eject-folders-view.patch"],
    "mixxx-open-remount.patch": ["mixxx-removable-rows-fix.patch", "mixxx-media-chip-ping.patch",
                                 "mixxx-table-fit-media-open.patch"],
    "mixxx-waveform-height-gain.patch": ["mixxx-waveform-height.patch"],
    "mixxx-menu-place-fix.patch": ["mixxx-sources-open-edge.patch", "mixxx-media-open-inside.patch",
                                   "mixxx-eject-folders-view.patch"],
    "mixxx-scan-strip-fixes.patch": ["mixxx-scan-progress.patch"],
    "mixxx-sources-edit-done.patch": ["mixxx-source-groups.patch"],
    "mixxx-settings-fixes.patch": ["mixxx-performance-settings.patch", "mixxx-acceptance-fixes.patch"],
    "mixxx-media-screen-fixes.patch": ["mixxx-media-screen.patch"],
    "mixxx-sample-browser.patch": ["mixxx-sources-screen.patch"],
    "mixxx-source-groups.patch": ["mixxx-sample-browser.patch"],
    "mixxx-media-screen.patch": ["mixxx-council-fixes.patch"],
    "mixxx-media-handover.patch": ["mixxx-media-screen.patch", "mixxx-removable-ram-cache.patch"],
    "mixxx-sources-screen.patch": ["mixxx-council-fixes.patch"],
    "mixxx-scan-progress.patch": ["mixxx-quiet-scan.patch", "mixxx-media-selection.patch"],
    "mixxx-touch-source-navigation.patch": ["mixxx-sidebar-sources.patch"],
    "mixxx-performance-settings.patch": ["mixxx-readahead.patch"],
    "mixxx-media-selection.patch": ["mixxx-media-hotplug.patch", "mixxx-removable-ram-cache.patch",
                                    "mixxx-sidebar-sources.patch"],
    "mixxx-library-interface.patch": ["mixxx-media-selection.patch",
                                      "mixxx-touch-source-navigation.patch"],
    "mixxx-recording-lifecycle.patch": ["mixxx-media-selection.patch"],
    "mixxx-media-continuation.patch": ["mixxx-library-interface.patch"],
    "mixxx-analysis-safety.patch": ["mixxx-media-hotplug.patch"],
    "mixxx-media-activity.patch": ["mixxx-media-continuation.patch"],
    "mixxx-import-cancellation.patch": ["mixxx-media-continuation.patch"],
    "mixxx-transfer-reporting.patch": ["mixxx-media-selection.patch"],
    "mixxx-transfer-display.patch": ["mixxx-media-activity.patch"],
    "mixxx-preferences-entry.patch": ["mixxx-performance-settings.patch"],
    "mixxx-dialog-wording.patch": ["mixxx-transfer-display.patch", "mixxx-media-selection.patch"],
    "mixxx-source-tap.patch": ["mixxx-touch-source-navigation.patch"],
    "mixxx-table-columns.patch": ["mixxx-library-interface.patch"],
    "mixxx-touch-dialogs.patch": ["mixxx-library-interface.patch"],
    "mixxx-bpm-lock-touch.patch": ["mixxx-touch-source-navigation.patch"],
    "mixxx-acceptance-fixes.patch": ["mixxx-table-columns.patch", "mixxx-bpm-lock-touch.patch",
                                     "mixxx-preferences-entry.patch", "mixxx-dialog-wording.patch"],
    "mixxx-council-fixes.patch": ["mixxx-acceptance-fixes.patch", "mixxx-source-tap.patch",
                                  "mixxx-touch-dialogs.patch", "mixxx-position-display.patch"],
    # mixxx-clean-quit.patch applies to pristine upstream on its own (its
    # mixxxmainwindow.cpp hunks are far from performance-settings').
}


def prerequisites(name, names):
    needed, pending = set(), list(PREREQUISITES.get(name, []))
    while pending:
        prerequisite = pending.pop()
        if prerequisite not in needed:
            needed.add(prerequisite)
            pending.extend(PREREQUISITES.get(prerequisite, []))
    return [candidate for candidate in names if candidate in needed]


@unittest.skipUnless(shutil.which("git"), "git required")
class PinnedMixxxPatchTests(unittest.TestCase):
    def pinned_reference(self, directory):
        """MIXXX_TEST_SOURCE, or a fresh clone of the pinned tag.

        Both paths then run the same checks on the same pinned commit.
        """
        reference = os.environ.get("MIXXX_TEST_SOURCE")
        if reference:
            return Path(reference)
        try:
            probe = subprocess.run(
                ["git", "ls-remote", UPSTREAM, "HEAD"],
                capture_output=True, text=True, timeout=30,
            )
        except subprocess.TimeoutExpired:
            self.skipTest("upstream network probe timed out")
        if probe.returncode:
            self.skipTest("upstream unavailable (offline): " + probe.stderr.strip())
        ref = re.search(r'MIXXX_REF:-([^}]+)', (ROOT / "source-versions").read_text())[1]
        source = directory / "mixxx"
        clone = subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", ref, UPSTREAM, str(source)],
            capture_output=True, text=True, timeout=180,
        )
        self.assertEqual(clone.returncode, 0, clone.stderr)
        commit = re.search(r'MIXXX_COMMIT:-([0-9a-f]{40})', (ROOT / "source-versions").read_text())[1]
        head = subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"],
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(head.stdout.strip(), commit, head.stderr)
        return source

    def check_patch_stack(self, reference):
        commit = re.search(r'MIXXX_COMMIT:-([0-9a-f]{40})', (ROOT / 'source-versions').read_text())[1]
        self.assertEqual(subprocess.run(['git', '-C', str(reference), 'cat-file', '-e', commit + '^{commit}'],
                                        capture_output=True).returncode, 0, 'pinned commit missing')
        files = set(subprocess.check_output(['git', '-C', str(reference), 'ls-tree', '-r',
                                            '--name-only', commit], text=True).splitlines())
        names = patch_names()
        for name, needed in PREREQUISITES.items():
            self.assertIn(name, names)
            for prerequisite in needed:
                self.assertLess(names.index(prerequisite), names.index(name), name)
        touched = set()
        for name in names:
            touched.update(re.findall(r'^diff --git a/(\S+) b/\S+$',
                                      (PATCH_DIR / name).read_text(), re.MULTILINE))
        baseline = {name: subprocess.check_output(['git', '-C', str(reference), 'show', f'{commit}:{name}'])
                    for name in sorted(touched & files)}

        def fixture(directory):
            target = Path(directory)
            for name, data in baseline.items():
                path = target / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            return target

        def apply(target, name, *options):
            return subprocess.run(['git', 'apply', *options, str(PATCH_DIR / name)],
                                  cwd=target, capture_output=True, text=True)

        def require(target, name, *options):
            result = apply(target, name, *options)
            self.assertEqual(result.returncode, 0, f'{name} {options}\n{result.stderr}')

        # Full stack in order, whitespace, then full reversal to pinned bytes.
        with tempfile.TemporaryDirectory(prefix='mixpi-patch-fixture-') as directory:
            target = fixture(directory)
            subprocess.run(['git', 'init', '-q'], cwd=target, check=True)
            subprocess.run(['git', 'add', '-A'], cwd=target, check=True)
            for name in names:
                with self.subTest(patch=name):
                    require(target, name, '--check')
                    require(target, name)
            check = subprocess.run(['git', 'diff', '--check'], cwd=target, capture_output=True, text=True)
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
            for name in reversed(names):
                require(target, name, '--reverse', '--check')
                require(target, name, '--reverse')
            restored = {str(path.relative_to(target)): path.read_bytes()
                        for path in target.rglob('*')
                        if path.is_file() and '.git' not in path.relative_to(target).parts}
            self.assertEqual(restored, baseline)

        # Each patch alone, or on exactly its declared prerequisites.
        for name in names:
            needed = prerequisites(name, names)
            with self.subTest(independent_patch=name), \
                    tempfile.TemporaryDirectory(prefix='mixpi-patch-alone-') as directory:
                target = fixture(directory)
                if needed:
                    self.assertNotEqual(apply(target, name, '--check').returncode, 0,
                                        f'{name} no longer needs {needed}')
                for prerequisite in needed:
                    require(target, prerequisite)
                require(target, name, '--check')

        # The GCC 14 build fix stays optional.
        with tempfile.TemporaryDirectory(prefix='mixpi-patch-optional-') as directory:
            target = fixture(directory)
            for name in names[1:]:
                require(target, name, '--check')
                require(target, name)

    def test_patch_stack_applies_to_pinned_source(self):
        with tempfile.TemporaryDirectory(prefix="mixpi-patches-") as directory:
            self.check_patch_stack(self.pinned_reference(Path(directory)))


if __name__ == "__main__":
    unittest.main()
