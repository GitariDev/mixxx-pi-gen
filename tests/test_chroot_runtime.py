"""Check recipe mount permissions and fail-fast invocation without image work."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ChrootRuntimeTests(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name).resolve()
        rootfs = base / 'rootfs'
        for name in ('proc', 'dev/pts', 'sys', 'run', 'tmp'):
            (rootfs / name).mkdir(parents=True, exist_ok=True)
        return base, rootfs

    def run_mount_fixture(self, failure=False):
        base, rootfs = self.fixture()
        script = r'''
set -e
source "$COMMON"
mount() {
    test "$#" -gt 0 || return 0
    printf '%s\n' "$*" >> "$AUDIT"
    if test "${@: -1}" = "$ROOTFS_DIR/run" && test "$FAIL_RUN" = 1; then
        return 23
    fi
}
capsh() { printf 'CAPSH\n' >> "$AUDIT"; }
on_chroot
'''
        result = subprocess.run(['bash', '-c', script], capture_output=True, text=True,
                                env={**os.environ, 'COMMON': str(ROOT / 'scripts/common'),
                                     'ROOTFS_DIR': str(rootfs), 'AUDIT': str(base / 'audit'),
                                     'FAIL_RUN': '1' if failure else '0'})
        return rootfs, (base / 'audit').read_text().splitlines(), result

    def test_run_is_private_and_tmp_keeps_default_semantics(self):
        rootfs, calls, result = self.run_mount_fixture()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f'-t tmpfs -o mode=0755 tmpfs {rootfs}/run', calls)
        self.assertIn(f'-t tmpfs tmpfs {rootfs}/tmp', calls)
        self.assertEqual(calls[-1], 'CAPSH')

    def test_failed_run_mount_prevents_chroot(self):
        rootfs, calls, result = self.run_mount_fixture(failure=True)
        self.assertEqual(result.returncode, 23, result.stderr)
        self.assertNotIn('CAPSH', calls)

    def test_plain_bash_build_stops_at_first_sourced_failure(self):
        base, rootfs = self.fixture()
        shutil.copy2(ROOT / 'build.sh', base / 'build.sh')
        (base / 'source-versions').write_text('printf before > before\nfalse\nprintf after > after\nexit 0\n')
        binary = base / 'bin'
        binary.mkdir()
        identity = binary / 'id'
        identity.write_text('#!/bin/sh\nprintf "0\\n"\n')
        identity.chmod(0o755)
        environment = {**os.environ, 'PATH': str(binary) + os.pathsep + os.environ['PATH']}
        environment.pop('BASH_ENV', None)
        result = subprocess.run(['bash', './build.sh'], cwd=base, env=environment,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertTrue((base / 'before').exists())
        self.assertFalse((base / 'after').exists())

    def run_final_validation_fixture(self, failure=False, direct=False):
        base, rootfs = self.fixture()
        build = (ROOT / 'build.sh').read_text()
        final = build[build.index('if [[ -n "${!MIXPI_ARTIFACT_*}" ]]; then\n\ton_chroot'):
                      build.index('\nCLEAN=1\nfor EXPORT_DIR')]
        script = r'''
set -e
source "$COMMON"
: > "$MOUNTS"
mount() {
    if test "$#" -eq 0; then
        while IFS= read -r target; do
            printf 'fixture on %s type fixture (rw)\n' "$target"
        done < "$MOUNTS"
    else
        printf '%s\n' "${@: -1}" >> "$MOUNTS"
    fi
}
umount() {
    printf '%s\n' "$1" >> "$AUDIT"
    if test "$FAIL_UNMOUNT" = 1; then
        return 23
    fi
    awk -v target="$1" '$0 != target' "$MOUNTS" > "$MOUNTS.next"
    mv "$MOUNTS.next" "$MOUNTS"
}
capsh() { cat > /dev/null; printf 'CHROOT\n' >> "$AUDIT"; }
python3() { printf 'FINAL\n' >> "$AUDIT"; }
MIXPI_ARTIFACT_MODE=accepted
'''
        if direct:
            script += '\non_chroot\nunmount "$ROOTFS_DIR" || exit $?\n'
        else:
            script += '\n' + final + '\n'
        script += 'test ! -s "$MOUNTS"\nprintf "EXPORT\\n" >> "$AUDIT"\n'
        result = subprocess.run(['bash', '-c', script], capture_output=True, text=True,
                                timeout=5,
                                env={**os.environ, 'COMMON': str(ROOT / 'scripts/common'),
                                     'ROOTFS_DIR': str(rootfs), 'BASE_DIR': str(ROOT),
                                     'MOUNTS': str(base / 'mounts'), 'AUDIT': str(base / 'audit'),
                                     'FAIL_UNMOUNT': '1' if failure else '0'})
        return rootfs, (base / 'audit').read_text().splitlines(), result

    def test_final_validation_unmounts_before_export(self):
        rootfs, calls, result = self.run_final_validation_fixture()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls[:2], ['CHROOT', 'FINAL'])
        self.assertEqual(set(calls[2:-1]),
                         {str(rootfs / name) for name in
                          ('proc', 'dev', 'dev/pts', 'sys', 'run', 'tmp')})
        self.assertLess(calls.index(str(rootfs / 'dev/pts')), calls.index(str(rootfs / 'dev')))
        self.assertEqual(calls[-1], 'EXPORT')

    def test_final_unmount_failure_prevents_export(self):
        rootfs, calls, result = self.run_final_validation_fixture(failure=True)
        self.assertEqual(result.returncode, 23, result.stderr)
        self.assertNotIn('EXPORT', calls)

    def test_conditional_unmount_preserves_first_failure(self):
        rootfs, calls, result = self.run_final_validation_fixture(failure=True, direct=True)
        self.assertEqual(result.returncode, 23, result.stderr)
        self.assertEqual(len(calls), 2)
        self.assertNotIn('EXPORT', calls)

    @unittest.skipUnless(sys.platform == 'linux' and os.geteuid() == 0 and
                         os.environ.get('MIXPI_TEST_REAL_TMPFS') == '1',
                         'requires explicitly authorized root Linux mount namespace')
    def test_real_final_validation_releases_virtual_mounts(self):
        base, rootfs = self.fixture()
        build = (ROOT / 'build.sh').read_text()
        final = build[build.index('if [[ -n "${!MIXPI_ARTIFACT_*}" ]]; then\n\ton_chroot'):
                      build.index('\nCLEAN=1\nfor EXPORT_DIR')]
        script = r'''
set -e
source "$COMMON"
capsh() { cat > /dev/null; }
python3() {
    for name in proc dev dev/pts sys run tmp; do
        mountpoint -q "$ROOTFS_DIR/$name"
    done
}
MIXPI_ARTIFACT_MODE=accepted
trap 'unmount "$ROOTFS_DIR"' EXIT
'''
        script += '\n' + final + r'''
for name in proc dev dev/pts sys run tmp; do
    if mountpoint -q "$ROOTFS_DIR/$name"; then
        exit 31
    fi
done
unmount "$ROOTFS_DIR"
'''
        result = subprocess.run(['unshare', '--mount', '--propagation', 'private', '--fork',
                                 'bash', '-c', script], capture_output=True, text=True, timeout=15,
                                env={**os.environ, 'COMMON': str(ROOT / 'scripts/common'),
                                     'ROOTFS_DIR': str(rootfs), 'BASE_DIR': str(ROOT)})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(sys.platform == 'linux' and os.geteuid() == 0 and
                         os.environ.get('MIXPI_TEST_REAL_TMPFS') == '1',
                         'requires explicitly authorized root Linux mount namespace')
    def test_real_tmpfs_permissions_and_artifact_path(self):
        base, rootfs = self.fixture()
        script = r'''
set -e
source "$COMMON"
mount() {
    if test "$#" -eq 0; then
        for name in proc dev dev/pts sys; do
            printf 'fixture on %s/%s type fixture\n' "$ROOTFS_DIR" "$name"
        done
        command mount
    else
        command mount "$@"
    fi
}
capsh() {
    test "$(stat -c '%u:%g:%a' "$ROOTFS_DIR/run")" = '0:0:755'
    test "$(stat -c '%u:%g:%a' "$ROOTFS_DIR/tmp")" = '0:0:1777'
    python3 - "$IMPORTER" "$ROOTFS_DIR" <<'PY'
import importlib.util
from pathlib import Path
import sys
spec = importlib.util.spec_from_file_location('ingest', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.safe_path(Path(sys.argv[2]), 'run/sysctl.d')
PY
}
trap 'umount "$ROOTFS_DIR/tmp"; umount "$ROOTFS_DIR/run"' EXIT
on_chroot
'''
        result = subprocess.run(['unshare', '--mount', '--propagation', 'private', '--fork',
                                 'bash', '-c', script], capture_output=True, text=True,
                                env={**os.environ, 'COMMON': str(ROOT / 'scripts/common'),
                                     'IMPORTER': str(ROOT / 'tools/performance/accepted-artifact.py'),
                                     'ROOTFS_DIR': str(rootfs), 'PYTHONDONTWRITEBYTECODE': '1'})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
