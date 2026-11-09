"""Apply the complete image patch stack to the real, pinned upstream source.

No Qt installation is required. This checks patch compatibility, not C++ build
or runtime behaviour. Offline runs skip the network check explicitly.
"""
from pathlib import Path
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
        ])
        subprocess.run(["bash", "-n", str(RECIPE)], check=True)
        for name in patch_names():
            self.assertTrue((PATCH_DIR / name).is_file(), name)


@unittest.skipUnless(shutil.which("git"), "git required")
class PinnedMixxxPatchTests(unittest.TestCase):
    def test_patch_stack_applies_to_pinned_source(self):
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
            # Both new patches must also be usable independently of each other.
            for name in reversed(names):
                git("apply", "--reverse", str(PATCH_DIR / name))
            for name in names[-2:]:
                with self.subTest(independent_patch=name):
                    git("apply", "--check", str(PATCH_DIR / name))


if __name__ == "__main__":
    unittest.main()
