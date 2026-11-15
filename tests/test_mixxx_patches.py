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
        ])
        subprocess.run(["bash", "-n", str(RECIPE)], check=True)
        for name in patch_names():
            self.assertTrue((PATCH_DIR / name).is_file(), name)


@unittest.skipUnless(shutil.which("git"), "git required")
class PinnedMixxxPatchTests(unittest.TestCase):
    def check_local_patch_stack(self, reference):
        commit = re.search(r'MIXXX_COMMIT:-([0-9a-f]{40})', (ROOT / 'source-versions').read_text())[1]
        files = set(subprocess.check_output(['git', '-C', str(reference), 'ls-tree', '-r',
                                            '--name-only', commit], text=True).splitlines())
        names = patch_names()
        touched = set()
        for name in names:
            touched.update(re.findall(r'^diff --git a/(\S+) b/\S+$',
                                      (PATCH_DIR / name).read_text(), re.MULTILINE))
        with tempfile.TemporaryDirectory(prefix='mixpi-patch-fixture-') as directory:
            target = Path(directory)
            baseline = {}
            for name in sorted(touched & files):
                data = subprocess.check_output(['git', '-C', str(reference), 'show', f'{commit}:{name}'])
                path = target / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                baseline[name] = data
            for name in names:
                for options in (['--check'], []):
                    result = subprocess.run(['git', 'apply', *options, str(PATCH_DIR / name)],
                                            cwd=target, capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
            for name in reversed(names):
                for options in (['--check'], []):
                    result = subprocess.run(['git', 'apply', '--reverse', *options, str(PATCH_DIR / name)],
                                            cwd=target, capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
            restored = {str(path.relative_to(target)): path.read_bytes()
                        for path in target.rglob('*') if path.is_file()}
            self.assertEqual(restored, baseline)

    def test_patch_stack_applies_to_pinned_source(self):
        reference = os.environ.get('MIXXX_TEST_SOURCE')
        if reference:
            self.check_local_patch_stack(Path(reference))
            return
        try:
            probe = subprocess.run(
                ["git", "ls-remote", UPSTREAM, "HEAD"],
                capture_output=True, text=True, timeout=30,
            )
        except subprocess.TimeoutExpired:
            self.skipTest("upstream network probe timed out")
        if probe.returncode:
            self.skipTest("upstream unavailable (offline): " + probe.stderr.strip())

        versions = (ROOT / "source-versions").read_text()
        ref = re.search(r'MIXXX_REF:-([^}]+)', versions)[1]
        commit = re.search(r'MIXXX_COMMIT:-([0-9a-f]{40})', versions)[1]
        with tempfile.TemporaryDirectory(prefix="mixpi-patches-") as directory:
            source = Path(directory) / "mixxx"
            clone = subprocess.run(
                ["git", "clone", "--depth", "1", "--branch", ref, UPSTREAM, str(source)],
                capture_output=True, text=True, timeout=180,
            )
            self.assertEqual(clone.returncode, 0, clone.stderr)

            def git(*args):
                result = subprocess.run(
                    ["git", "-C", str(source), *args],
                    capture_output=True, text=True, timeout=30,
                )
                self.assertEqual(result.returncode, 0,
                                 f"git {' '.join(args)}\n{result.stdout}{result.stderr}")
                return result.stdout.strip()

            self.assertEqual(git("rev-parse", "HEAD"), commit)
            names = patch_names()
            for name in names:
                patch = str(PATCH_DIR / name)
                with self.subTest(patch=name):
                    git("apply", "--check", patch)
                    git("apply", patch)
            git("diff", "--check")
            # Verify full reversal, then independent patches and explicit prerequisites.
            for name in reversed(names):
                git("apply", "--reverse", str(PATCH_DIR / name))
            for name in names[2:]:
                if name in {"mixxx-media-selection.patch", "mixxx-library-interface.patch",
                            "mixxx-recording-lifecycle.patch", "mixxx-import-cancellation.patch",
                            "mixxx-transfer-reporting.patch", "mixxx-transfer-display.patch"}:
                    continue
                if name == "mixxx-touch-source-navigation.patch":
                    git("apply", str(PATCH_DIR / "mixxx-sidebar-sources.patch"))
                if name == "mixxx-performance-settings.patch":
                    git("apply", str(PATCH_DIR / "mixxx-readahead.patch"))
                with self.subTest(independent_patch=name):
                    git("apply", "--check", str(PATCH_DIR / name))
            for name in ("mixxx-readahead.patch", "mixxx-sidebar-sources.patch"):
                git("apply", "--reverse", str(PATCH_DIR / name))
            for name in names[1:]:
                git("apply", "--check", str(PATCH_DIR / name))
                git("apply", str(PATCH_DIR / name))


if __name__ == "__main__":
    unittest.main()
