"""Exercise the image/package boundary without mounts or an ARM compiler."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / 'stage3/01-install-packages'


class IsolatedPackageStageTests(unittest.TestCase):
    def run_stage(self, fail=False):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        base = Path(temp.name)
        runtime = base / 'rootfs'
        runtime.mkdir()
        (runtime / 'runtime-marker').write_text('original')
        # Functions stub only mount/chroot/copy operations. The actual stage
        # script performs directory selection, transfers and failure cleanup.
        script = r'''
set -e
mount() { printf 'mount %s\n' "$*" >> "$AUDIT"; }
unmount() { printf 'unmount %s\n' "$1" >> "$AUDIT"; }
rsync() {
    local source="${@: -2:1}" destination="${@: -1}"
    cp -R "$source/." "$destination/"
}
on_chroot() {
    local commands
    commands=$(cat)
    printf 'chroot %s\n' "$ROOTFS_DIR" >> "$AUDIT"
    if [ "$ROOTFS_DIR" != "$RUNTIME" ]; then
        [ "$FAIL_BUILD" = 0 ] || return 23
        mkdir -p "$ROOTFS_DIR/code/build" "$ROOTFS_DIR/usr/bin"
        echo build-only > "$ROOTFS_DIR/usr/bin/compiler-marker"
        echo package > "$ROOTFS_DIR/code/build/mixxx-test.deb"
        echo revision > "$ROOTFS_DIR/opt/mixxx.version"
        echo 2.5.6 > "$ROOTFS_DIR/opt/mixxx.tag"
        test -f "$ROOTFS_DIR/runtime-marker"
    else
        test -f "$ROOTFS_DIR/opt/mixxx-package/mixxx-test.deb"
        test ! -f "$ROOTFS_DIR/usr/bin/compiler-marker"
        printf '%s\n' "$commands" > "$ROOTFS_DIR/runtime-install-script"
        rm -r "$ROOTFS_DIR/opt/mixxx-package"
    fi
}
source ./01-run.sh
'''
        result = subprocess.run(['bash', '-c', script], cwd=STAGE,
            env={**os.environ, 'BASE_DIR': str(base), 'STAGE_WORK_DIR': str(base),
                 'ROOTFS_DIR': str(runtime), 'RUNTIME': str(runtime),
                 'DEPLOY_DIR': str(base / 'deploy'), 'AUDIT': str(base / 'audit'),
                 'MIXXX_REF': '2.5.6', 'MIXXX_COMMIT': 'pinned',
                 'FAIL_BUILD': '1' if fail else '0'}, capture_output=True, text=True)
        return base, runtime, result

    def test_only_package_and_provenance_reach_runtime(self):
        base, runtime, result = self.run_stage()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(list(base.glob('mixxx-build.*')))
        self.assertFalse((runtime / 'usr/bin/compiler-marker').exists())
        self.assertFalse((runtime / 'code').exists())
        self.assertFalse((runtime / 'ccache').exists())
        self.assertEqual((base / 'deploy/mixxx-test.deb').read_text(), 'package\n')
        self.assertEqual((runtime / 'opt/mixxx.version').read_text(), 'revision\n')
        install = (runtime / 'runtime-install-script').read_text()
        self.assertIn('apt-get install -y --no-install-recommends /opt/mixxx-package/*.deb', install)
        self.assertIn('dpkg-query -S /usr/bin/mixxx', install)
        calls = (base / 'audit').read_text().splitlines()
        self.assertEqual(sum(line.startswith('chroot ') for line in calls), 2)
        self.assertTrue(calls[-1].startswith('unmount '))

    def test_failed_build_unmounts_and_never_installs_runtime(self):
        base, runtime, result = self.run_stage(fail=True)
        self.assertEqual(result.returncode, 23)
        self.assertFalse((runtime / 'runtime-install-script').exists())
        self.assertEqual((runtime / 'runtime-marker').read_text(), 'original')
        self.assertFalse((base / 'deploy').exists())
        self.assertTrue((base / 'audit').read_text().splitlines()[-1].startswith('unmount '))
