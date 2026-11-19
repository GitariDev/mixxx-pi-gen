"""Wave I3 (S8): the Sources menu's shadow, a touch-transparent strip.

Builds tests/native/sources_menu_shadow_test.cpp against the patched
src/widget/wrightoverlaylayout.h with real Qt (offscreen), and gives it the
skin's #MixpiSourcesMenuShadow rule from mixpi-sources-menu.qss.

mixxx-sources-menu-shadow.patch is applied on top of the registered stack when
it is not registered yet, which is where the registration puts it.
--baseline leaves it out (the overlay layout as build H has it): the checks
must fail.
"""
import argparse
from pathlib import Path
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native.library_interface_runner import PATCH_DIR, ROOT, reconstruct, qt_flags, qt_environment

PATCH = 'mixxx-sources-menu-shadow.patch'
QSS = PATCH_DIR / 'mixpi-sources-menu.qss'


def shadow_rule(qss=QSS):
    match = re.search(r'^#MixpiSourcesMenuShadow \{.*?^\}', qss.read_text(), re.MULTILINE | re.DOTALL)
    if not match:
        raise RuntimeError('no #MixpiSourcesMenuShadow rule in ' + qss.name)
    return match.group(0)


def run(baseline=False):
    with tempfile.TemporaryDirectory(prefix='mixpi-menu-shadow-') as temporary:
        target = Path(temporary)
        reconstruct(target, exclude=(PATCH,))
        if not baseline:
            subprocess.run(['git', 'apply', str(PATCH_DIR / PATCH)], cwd=target, check=True, timeout=15)
        command = ['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-I' + str(target / 'src'),
                   str(ROOT / 'tests/native/sources_menu_shadow_test.cpp'), '-o', str(target / 'test'),
                   *qt_flags()]
        print('COMMAND', repr(command), flush=True)
        subprocess.run(command, check=True, timeout=120)
        return subprocess.run([str(target / 'test'), shadow_rule()], env=qt_environment(),
                              capture_output=True, text=True, timeout=30)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', action='store_true')
    args = parser.parse_args()
    result = run(baseline=args.baseline)
    print(result.stdout, result.stderr)
    raise SystemExit(result.returncode)
