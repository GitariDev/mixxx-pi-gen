"""Compile exact production helpers from the pinned, patched source with real Qt."""
import argparse
import importlib.util
import os
from pathlib import Path
import platform
import re
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
PATCH_DIR = ROOT / 'stage3/01-install-packages/files'


def source_pin():
    return re.search(r'MIXXX_COMMIT:-([0-9a-f]{40})',
                     (ROOT / 'source-versions').read_text())[1]


def source_reference():
    value = os.environ.get('MIXXX_TEST_SOURCE')
    if not value:
        raise RuntimeError('MIXXX_TEST_SOURCE must name a local Git source containing the source-versions commit')
    reference = Path(value).resolve()
    subprocess.run(['git', '-C', str(reference), 'cat-file', '-e', source_pin() + '^{commit}'],
                   check=True, capture_output=True, timeout=15)
    return reference


def pinned_bytes(relative):
    return subprocess.check_output(['git', '-C', str(source_reference()), 'show',
                                    source_pin() + ':' + relative], timeout=15)


def populate_pinned(target, paths):
    for relative in paths:
        destination = target / relative
        if not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(pinned_bytes(relative))


def qt_flags(modules=('QtCore', 'QtGui', 'QtWidgets')):
    if platform.system() == 'Darwin':
        value = os.environ.get('QT_SDK_PATH')
        if not value:
            raise RuntimeError('QT_SDK_PATH is required on macOS')
        sdk = Path(value).resolve()
        flags = ['-DQT_USE_QSTRINGBUILDER', '-F' + str(sdk / 'lib'), '-Wl,-rpath,' + str(sdk / 'lib')]
        if platform.machine() == 'arm64':
            flags += ['-include', 'arm_acle.h']
        for module in modules:
            headers = sdk / 'lib' / (module + '.framework/Headers')
            if not headers.is_dir():
                raise RuntimeError('Missing Qt framework: ' + str(headers))
            flags += ['-I' + str(headers), '-framework', module]
        return flags
    if platform.system() != 'Linux':
        raise RuntimeError('Native Qt tests support Linux and macOS only')
    return ['-DQT_USE_QSTRINGBUILDER', '-fPIC', *shlex.split(subprocess.check_output(
        ['pkg-config', '--cflags', '--libs', *[module.replace('Qt', 'Qt6', 1) for module in modules]],
        text=True, timeout=15))]


def qt_available():
    try:
        qt_flags(('QtCore',))
        return True
    except (OSError, RuntimeError, subprocess.SubprocessError):
        return False


def moc_path():
    if platform.system() == 'Darwin':
        candidate = Path(os.environ['QT_SDK_PATH']).resolve() / 'libexec/moc'
    else:
        directory = subprocess.check_output(
            ['pkg-config', '--variable=libexecdir', 'Qt6Core'], text=True, timeout=15).strip()
        candidate = Path(directory) / 'moc'
    if not candidate.is_file() or not os.access(candidate, os.X_OK):
        raise RuntimeError('Qt6 moc unavailable: ' + str(candidate))
    return str(candidate)


def rcc_path():
    candidate = Path(moc_path()).with_name('rcc')
    if not candidate.is_file() or not os.access(candidate, os.X_OK):
        raise RuntimeError('Qt6 rcc unavailable: ' + str(candidate))
    return str(candidate)


def mixxx_images_rcc(target, images):
    """A resource file with the pinned Mixxx images, at the paths res/mixxx.qrc gives them."""
    listed = set(re.findall(r'<file>([^<]+)</file>', pinned_bytes('res/mixxx.qrc').decode()))
    lines = ['<!DOCTYPE RCC>', '<RCC version="1.0">', '    <qresource prefix="/">']
    for image in images:
        if image not in listed:
            raise RuntimeError('Not a Mixxx resource: ' + image)
        destination = target / 'res' / image
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(pinned_bytes('res/' + image))
        lines.append(f'        <file>{image}</file>')
    lines += ['    </qresource>', '</RCC>', '']
    (target / 'res/mixpi-test.qrc').write_text('\n'.join(lines))
    output = target / 'mixxx-images.rcc'
    subprocess.run([rcc_path(), '-binary', str(target / 'res/mixpi-test.qrc'), '-o', str(output)],
                   check=True, timeout=30)
    return output


def qt_environment():
    environment = dict(os.environ, QT_QPA_PLATFORM='offscreen')
    if platform.system() == 'Darwin':
        sdk = Path(os.environ['QT_SDK_PATH']).resolve()
        environment.update(QT_PLUGIN_PATH=str(sdk / 'plugins'),
                           QT_QPA_PLATFORM_PLUGIN_PATH=str(sdk / 'plugins/platforms'))
    return environment


def sndfile_flags():
    if platform.system() == 'Linux':
        return shlex.split(subprocess.check_output(
            ['pkg-config', '--cflags', '--libs', 'sndfile'], text=True, timeout=15))
    dependency = Path(os.environ.get('SNDFILE_ROOT', ROOT / 'deploy/recovery-20261111/native-completion-slice/recording/dependency')).resolve()
    header = dependency / 'libsndfile-1.2.2/include'
    library = dependency / 'libsndfile.a'
    if not library.is_file() or not (header / 'sndfile.h').is_file():
        raise RuntimeError('Real libsndfile unavailable; no encoder substitution')
    return ['-I' + str(header), str(library)]


def reconstruct(target, include_interface=True, exclude=()):
    reference = source_reference()
    commit = source_pin()
    names = subprocess.check_output(
        ['bash', str(ROOT / 'stage3/01-install-packages/01-run.sh'),
         '--mixxx-print-patches'], text=True).split()
    names = [name for name in names
             if name not in exclude and (include_interface or name != 'mixxx-library-interface.patch')]
    # A patch leaves with its prerequisites (PREREQUISITES in
    # tests/test_mixxx_patches.py); they come earlier in the list.
    spec = importlib.util.spec_from_file_location('mixpi_patch_prerequisites',
                                                  ROOT / 'tests/test_mixxx_patches.py')
    listed = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(listed)
    kept = []
    for name in names:
        if all(prerequisite in kept for prerequisite in listed.PREREQUISITES.get(name, [])):
            kept.append(name)
    names = kept
    paths = set()
    for name in names:
        paths.update(re.findall(r'^diff --git a/(\S+) b/\S+$',
                               (PATCH_DIR / name).read_text(), re.MULTILINE))
    available = set(subprocess.check_output(
        ['git', '-C', str(reference), 'ls-tree', '-r', '--name-only', commit],
        text=True).splitlines())
    baseline = {}
    for name in sorted(paths & available):
        content = subprocess.check_output(
            ['git', '-C', str(reference), 'show', f'{commit}:{name}'])
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        baseline[name] = content
    for name in names:
        subprocess.run(['git', 'apply', '--check', str(PATCH_DIR / name)],
                       cwd=target, check=True, timeout=15)
        subprocess.run(['git', 'apply', str(PATCH_DIR / name)],
                       cwd=target, check=True, timeout=15)
    return names, baseline


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', action='store_true')
    parser.add_argument('--holdout', action='store_true')
    # Evidence only: run the dialog checks with another menu style sheet.
    parser.add_argument('--menus-qss', type=Path, default=PATCH_DIR / 'pioneered-menus.qss')
    # Evidence only: the same checks without mixxx-council-fixes.patch must fail.
    parser.add_argument('--without-council-fixes', action='store_true')
    parser.add_argument('--grab-dir', type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='mixpi-library-interface-test-') as temporary:
        target = Path(temporary)
        reconstruct(target, exclude=('mixxx-council-fixes.patch',) if args.without_council_fixes else ())
        command = ['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror']
        command += ['-I' + str(target / 'src'),
                    str(ROOT / 'tests/native/library_interface_test.cpp'),
                    '-o', str(target / 'test'), *qt_flags()]
        print('COMMAND', repr(command), flush=True)
        subprocess.run(command, check=True, timeout=90)
        environment = qt_environment()
        # F-9: the native dialog checks load the real installed menu style.
        environment['MIXPI_MENUS_QSS'] = str(args.menus_qss)
        # F-9: Mixxx's compiled-in images that the menu style names with
        # url(:/...), and always the tick, which the program always has.
        images = sorted(set(re.findall(r'url\(:/([^)]+)\)', args.menus_qss.read_text())) |
                        {'images/ic_checkmark.svg'})
        environment['MIXPI_MIXXX_RCC'] = str(mixxx_images_rcc(target, images))
        if args.grab_dir:
            environment['MIXPI_ARRANGE_GRAB_DIR'] = str(args.grab_dir)
        mode = ['baseline'] if args.baseline else ['holdout'] if args.holdout else []
        subprocess.run([str(target / 'test'), *mode], env=environment,
                       check=True, timeout=30)


if __name__ == '__main__':
    main()
