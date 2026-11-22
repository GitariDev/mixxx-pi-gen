"""Spec 2h (build M, wave J12): build and run the OPEN remount fixture.

The fixture compiles the shipped library/mixpimediapage.h (the Media page,
its rows, the eject engine, the strips), library/media/mediauseregistry.h
(the read generations) and, with the patch, library/mixpimediaremount.h
from the registered stack with mixxx-open-remount.patch on top. From
mixpimedia.h it takes the actual MixpiMedia methods the OPEN and eject paths
run: openVolume, findVolume, currentDrive, startEject, ejectFinished, tick,
driveGone, describe, under, refresh and mounts and, with the patch,
remountHooks, remountSafe, remountFinished and openRemounted. The mount
table they read (/proc/self/mountinfo) is the fixture's file, and udisks2
(/usr/bin/udisksctl) is the fixture's script, which logs its arguments and
adds or removes the drive's line in that table. --baseline leaves
mixxx-open-remount.patch out, to show the checks fail without it.
"""
import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from library_interface_runner import ROOT, PATCH_DIR, qt_environment, qt_flags, reconstruct

PATCH_NAME = 'mixxx-open-remount.patch'
MEDIA = 'src/library/mixpimedia.h'
REMOUNT = 'src/library/mixpimediaremount.h'
MOUNT_TABLE = 'QStringLiteral("/proc/self/mountinfo")'
UDISKSCTL = 'QStringLiteral("/usr/bin/udisksctl")'

METHODS = ('static QList<QPair<QString, QString>> mounts() {', 'const MixpiMediaDrive* currentDrive(',
           'void startEject(const QString& identity) {', 'void ejectFinished(bool ok, const QString& message) {',
           'void tick() {', 'static bool driveGone(', 'static bool under(',
           'MixpiMediaDrive describe(const QJsonObject& drive) const {', 'void refresh() {',
           'QJsonObject findVolume(', 'void openVolume(')
REMOUNT_METHODS = ('MixpiRemount::Hooks remountHooks() {', 'void remountSafe(const QString& identity) {',
                   'void remountFinished(const QString& identity, bool ok) {', 'void openRemounted() {')


def inline_method(source, signature):
    """A method defined in its class (four spaces in), up to its closing brace."""
    start = source.index('    ' + signature)
    return source[start:source.index('\n    }\n', start) + 7]


def production(target, baseline):
    media = (target / MEDIA).read_text()
    parts = []
    for signature in METHODS + (() if baseline else REMOUNT_METHODS):
        part = inline_method(media, signature)
        if signature.startswith(('static QList', 'void tick')):
            if part.count(MOUNT_TABLE) != 1:
                raise RuntimeError('Unexpected mount table in ' + signature)
            part = part.replace(MOUNT_TABLE, 'kFixtureMountTable')
        if MOUNT_TABLE in part:
            raise RuntimeError('Mount table read in ' + signature)
        parts.append(part)
    (target / 'open_remount_media.inc').write_text('\n'.join(parts) + '\n')
    if not baseline:
        remount = (target / REMOUNT).read_text()
        if remount.count(UDISKSCTL) != 1:
            raise RuntimeError('Unexpected udisksctl in ' + REMOUNT)
        (target / REMOUNT).write_text(remount.replace(UDISKSCTL, 'kFixtureUdisksctl'))


def build(target, baseline):
    names, _ = reconstruct(target, exclude=(PATCH_NAME,) if baseline else ())
    if not baseline and PATCH_NAME not in names:
        subprocess.run(['git', 'apply', str(PATCH_DIR / PATCH_NAME)], cwd=target, check=True, timeout=15)
    print('PATCHES', len(names), 'BASELINE' if baseline else PATCH_NAME, flush=True)
    production(target, baseline)
    binary = target / 'open-remount-test'
    command = ['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror', *(['-DBASELINE'] if baseline else []),
               '-I' + str(target), '-I' + str(target / 'src'), str(ROOT / 'tests/native/open_remount_test.cpp'),
               '-o', str(binary), *qt_flags(('QtCore', 'QtGui', 'QtWidgets', 'QtTest'))]
    print('COMPILE', repr(command), flush=True)
    subprocess.run(command, check=True, timeout=300)
    return binary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', action='store_true')
    arguments = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='mixpi-open-remount-') as temporary:
        program = build(Path(temporary), arguments.baseline)
        return subprocess.run([str(program)], env=qt_environment(), timeout=120).returncode


if __name__ == '__main__':
    raise SystemExit(main())
