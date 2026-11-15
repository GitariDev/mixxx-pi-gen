#!/usr/bin/env python3
"""Read-only, finite preflight of an explicitly supplied, quiescent staged rootfs."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys


REPO = Path(__file__).resolve().parents[2]
INSTALLED = {
    '/opt/mixpi-skin-tools/mixpi-mount-broker.py': 'stage3/01-install-packages/files/mixpi-mount-broker.py',
    '/opt/mixpi-skin-tools/mixpi-media-inventory.py': 'stage3/01-install-packages/files/mixpi-media-inventory.py',
    '/usr/local/bin/mixpi-mount-control': 'stage3/02-desktop/files/bin/mixpi-mount-control',
    '/etc/systemd/system/mixpi-mount-broker.service': 'stage3/02-desktop/files/systemd/mixpi-mount-broker.service',
    '/etc/polkit-1/rules.d/49-mixpi-controlled-media.rules': 'stage3/02-desktop/files/49-mixpi-controlled-media.rules',
}
SOURCES = tuple(INSTALLED.values()) + (
    'stage3/02-desktop/06-run.sh',
    'stage3/01-install-packages/files/mixxx-media-selection.patch',
)
HELPERS = ('/usr/bin/udevil', '/bin/mount', '/bin/umount', '/usr/bin/fusermount',
           '/usr/bin/fusermount3', '/usr/bin/ntfs-3g', '/usr/sbin/mount.cifs')
RUNTIME = {
    'sysctls': 'Read effective user.max_user_namespaces and kernel.unprivileged_userns_clone; test namespace denial as pi.',
    'services': 'Inspect systemd loaded units, aliases, generators, transient units and effective broker properties; audit every enabled privileged service.',
    'polkit': 'Evaluate competing polkit rules and udisks mount actions as pi in active/inactive sessions; file order is not evaluation.',
    'namespaces': 'Verify broker/PID1/Mixxx/helper mount namespaces and namespace lifecycle across restart and peer death.',
    'writers': 'Audit external writers, privileged administrators, sockets, ACLs, packages and namespace creators; a file scan cannot prove exclusivity.',
    'recovery': 'Approve and rehearse independent offline recovery; confirm root remains locked and effective root SSH prohibition without exposing secrets.',
    'native': 'Rebuild/link every native consumer, integrate GUI, then explicitly authorize backed-up sacrificial-media runtime tests.',
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


class EvidenceError(Exception):
    pass


class Checker:
    def __init__(self, root):
        self.root = Path(root).absolute()
        self.findings = []
        self.entries = {}
        self.read_hashes = {}

    def add(self, status, path, impact):
        self.findings.append(dict(status=status, path=path, impact=impact))

    def resolve(self, name, authority=False, allow_aliases=True):
        pending = name.split('/')
        resolved = []
        links = 0
        while pending:
            part = pending.pop(0)
            if part in ('', '.'):
                continue
            if part == '..':
                if not resolved:
                    raise EvidenceError('symlink/path escapes staged root')
                resolved.pop()
                continue
            candidate = self.root.joinpath(*resolved, part)
            info = candidate.lstat()
            if stat.S_ISLNK(info.st_mode):
                if not allow_aliases:
                    raise EvidenceError('policy content alias refused; target content not read')
                if authority:
                    self.trusted(candidate.parent)
                    if info.st_uid != 0 or info.st_gid != 0:
                        self.add('FAIL', name, 'authority alias is not root:root')
                links += 1
                if links > 40:
                    raise EvidenceError('symlink cycle or excessive indirection')
                target = os.readlink(candidate)
                if target.startswith('/'):
                    resolved = []
                pending = target.split('/') + pending
            else:
                if pending and not allow_aliases:
                    if not stat.S_ISDIR(info.st_mode):
                        raise EvidenceError('policy parent is not a directory')
                    if not info.st_mode & 0o111:
                        raise EvidenceError('policy parent has no search permission')
                resolved.append(part)
        return self.root.joinpath(*resolved)

    def trusted(self, path):
        current = path
        while True:
            info = current.lstat()
            if info.st_uid != 0 or info.st_gid != 0 or info.st_mode & 0o022:
                self.add('FAIL', '/' + str(current.relative_to(self.root)),
                         'authority file or parent is not root:root/non-writable')
            if current == self.root:
                break
            current = current.parent

    def unavailable(self, name, error):
        if isinstance(error, FileNotFoundError):
            reason = 'required evidence missing'
        elif isinstance(error, PermissionError):
            reason = 'required evidence inaccessible: permission denied'
        elif isinstance(error, UnicodeError):
            reason = 'required evidence is not valid UTF-8'
        elif isinstance(error, EvidenceError):
            reason = str(error)
        else:
            reason = 'required evidence I/O failure (errno ' + str(error.errno) + ')'
        self.add('UNVERIFIED', name, reason)

    def read(self, name):
        try:
            path = self.resolve(name, authority=True, allow_aliases=False)
            self.trusted(path)
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode):
                raise EvidenceError('required evidence is not a regular policy file')
            if not info.st_mode & 0o444:
                raise EvidenceError('required evidence has no read permission')
            if info.st_size > 1024 * 1024:
                raise EvidenceError('required evidence exceeds the 1 MiB limit')
            if info.st_nlink != 1:
                raise EvidenceError('multiply linked policy content refused')
            data = path.read_bytes()
            text = data.decode('utf-8')
            self.read_hashes[name] = digest(data)
            return text
        except (OSError, UnicodeError, EvidenceError) as error:
            self.unavailable(name, error)
            return None

    def capability(self, name, optional=False):
        try:
            path = self.resolve(name, authority=True, allow_aliases=False)
            info = path.lstat()
        except (OSError, EvidenceError) as error:
            expected = str(self.root / name.lstrip('/'))
            if optional and isinstance(error, FileNotFoundError) and error.filename == expected:
                self.add('PASS', name, 'review gate absent: activation intentionally BLOCKED')
            else:
                if isinstance(error, EvidenceError) and 'alias refused' in str(error):
                    self.add('FAIL', name, 'capability path is aliased; direct regular-file evidence required')
                self.unavailable(name, error)
            return
        if not stat.S_ISREG(info.st_mode):
            self.add('FAIL', name, 'capability must be a regular file, never a symlink or special file')
            self.unavailable(name, EvidenceError('required evidence is not a regular policy file'))
        else:
            self.exact(name, 'v1\n')
        if optional:
            self.add('UNVERIFIED', name, 'gate present; independent authorization provenance required, never inferred from content')

    def exact(self, name, expected):
        actual = self.read(name)
        if actual is not None:
            self.add('PASS' if actual == expected else 'FAIL', name,
                     'matches bounded policy' if actual == expected else 'missing/stale or modified installed policy')

    def inventory(self):
        def failed(error):
            self.add('UNVERIFIED', '/' + os.path.relpath(error.filename, self.root), 'directory inventory unreadable')

        capabilities_supported = sys.platform.startswith('linux') and hasattr(os, 'listxattr')
        if not capabilities_supported:
            self.add('UNVERIFIED', '/', 'Linux capability/ACL xattrs cannot be qualified on this host; extraction may also discard them')
        for directory, directories, files in os.walk(self.root, followlinks=False, onerror=failed):
            directories.sort()
            for basename in sorted(directories + files):
                path = Path(directory) / basename
                name = '/' + str(path.relative_to(self.root))
                try:
                    info = path.lstat()
                    self.entries[name] = [info.st_mode, info.st_uid, info.st_gid, info.st_size]
                    if stat.S_ISLNK(info.st_mode):
                        self.entries[name].append(os.readlink(path))
                        if os.readlink(path) != '/dev/null':
                            try:
                                self.resolve(name)
                            except (OSError, EvidenceError):
                                self.add('UNVERIFIED', name, 'dangling, cyclic or escaping link; target not inspected')
                        continue
                    if stat.S_ISDIR(info.st_mode) and not info.st_mode & 0o444:
                        self.add('UNVERIFIED', name, 'directory lacks readable inventory permission')
                    if info.st_mode & 0o6000 and stat.S_ISREG(info.st_mode):
                        self.add('UNVERIFIED', name, 'set-ID helper requires explicit package/authority review')
                    if capabilities_supported:
                        attributes = os.listxattr(path, follow_symlinks=False)
                        if 'security.capability' in attributes:
                            self.add('UNVERIFIED', name, 'file capabilities may grant a competing privileged authority')
                        if any(attribute.startswith('system.posix_acl_') for attribute in attributes):
                            self.add('UNVERIFIED', name, 'ACL may grant access beyond mode bits; requires Linux ACL review')
                except OSError:
                    self.add('UNVERIFIED', name, 'metadata/xattr inventory unavailable')

    def units_and_policy(self):
        mask = self.entries.get('/etc/systemd/system/udisks2.service', [])
        self.add('PASS' if len(mask) == 5 and stat.S_ISLNK(mask[0]) and mask[4] == '/dev/null' and mask[1:3] == [0, 0] else 'FAIL',
                 '/etc/systemd/system/udisks2.service', 'udisks2 must be directly masked to /dev/null')
        enabled = '/etc/systemd/system/multi-user.target.wants/mixpi-mount-broker.service'
        try:
            if self.resolve(enabled, authority=True) != self.resolve('/etc/systemd/system/mixpi-mount-broker.service'):
                self.add('FAIL', enabled, 'broker enablement resolves to another service')
        except (OSError, EvidenceError):
            self.add('UNVERIFIED', enabled, 'conditional broker enablement missing or unsafe')
        for name in self.entries:
            if '/systemd/' in name and name.endswith(('.service', '.mount', '.automount', '.socket', '.conf')):
                if name in INSTALLED or name == '/etc/systemd/system/udisks2.service':
                    continue
                if stat.S_ISDIR(self.entries[name][0]):
                    continue
                self.add('UNVERIFIED', name, 'unit/alias/drop-in needs authority review; masks do not exclude alternate service names or custom mount commands')
            if ('/polkit-1/' in name and name.endswith(('.rules', '.pkla', '.policy'))) and name not in INSTALLED:
                self.add('UNVERIFIED', name, 'competing polkit grant/default; review in basename order (etc before vendor on ties)')
            if any(fragment in name for fragment in ('/init.d/', '/udev/rules.d/', '/autostart/', '/cron', '/auto.', '/system-generators/', '/user-generators/')):
                if not stat.S_ISDIR(self.entries[name][0]):
                    self.add('UNVERIFIED', name, 'startup/automount hook may introduce a competing writer or mount authority')
            if name.endswith(('/i3/config', '/sway/config', '/i3.conf', '/sway.conf')) or name == '/etc/rc.local':
                text = self.read(name)
                if text and re.search(r'udiskie|udisks|udevil|devmon|gvfs|\bmount\b', text):
                    self.add('UNVERIFIED', name, 'session startup contains potential automount authority')
        self.exact('/etc/sysctl.d/90-mixpi-controlled-media.conf', 'user.max_user_namespaces=0\n')
        for name in self.entries:
            if name == '/etc/sysctl.conf' or ('/sysctl.d/' in name and name.endswith('.conf')):
                text = self.read(name)
                if text and name != '/etc/sysctl.d/90-mixpi-controlled-media.conf' and re.search(r'user_namespaces|unprivileged_userns', text):
                    self.add('UNVERIFIED', name, 'competing namespace sysctl; resolve boot ordering and runtime value')
        fstab = self.read('/etc/fstab')
        if fstab is not None:
            for number, line in enumerate(fstab.splitlines(), 1):
                fields = line.split()
                if not fields or fields[0].startswith('#'):
                    continue
                if len(fields) < 4 or fields[1] not in ('/', '/boot', '/boot/firmware', '/proc'):
                    self.add('UNVERIFIED', f'/etc/fstab:{number}', 'non-baseline mount entry; verify backing device and authority (values withheld)')

    def accounts_and_helpers(self):
        passwd = self.read('/etc/passwd')
        group = self.read('/etc/group')
        if passwd is not None and group is not None:
            accounts = [line.split(':') for line in passwd.splitlines() if line]
            users = [fields for fields in accounts if len(fields) == 7 and fields[0] == 'pi']
            if len(users) != 1 or users[0][2] != '1000' or users[0][3] == '0':
                self.add('FAIL', '/etc/passwd', 'expected exactly one non-root pi account with UID 1000')
            for fields in accounts:
                if len(fields) != 7 or (fields[2] == '0' and fields[0] != 'root'):
                    self.add('FAIL', '/etc/passwd', 'malformed account or additional root authority')
            for line in group.splitlines():
                fields = line.split(':')
                if len(fields) != 4:
                    self.add('UNVERIFIED', '/etc/group', 'malformed group evidence')
                    continue
                member = 'pi' in fields[3].split(',') or (users and users[0][3] == fields[2])
                if member and fields[0] in ('root', 'sudo', 'disk', 'docker', 'lxd', 'incus', 'libvirt'):
                    self.add('FAIL', '/etc/group', 'pi belongs to privileged group ' + fields[0])
                elif member and fields[0] not in ('pi', 'adm', 'dialout', 'cdrom', 'audio', 'video', 'plugdev', 'games', 'users', 'input', 'render', 'netdev', 'gpio', 'i2c', 'spi'):
                    self.add('UNVERIFIED', '/etc/group', 'unreviewed pi group ' + fields[0])
        self.exact('/etc/sudoers.d/010_pi-nopasswd', 'pi ALL=(root) NOPASSWD: /usr/sbin/shutdown\n')
        self.read('/etc/sudoers')
        for name in self.entries:
            if name == '/etc/sudoers' or name.startswith('/etc/sudoers.d/'):
                if name != '/etc/sudoers.d/010_pi-nopasswd' and not stat.S_ISDIR(self.entries[name][0]):
                    self.add('UNVERIFIED', name, 'evaluate all sudo includes, aliases and group grants with visudo/sudo; do not infer denial from one drop-in')
        overrides = self.read('/var/lib/dpkg/statoverride')
        parsed = {}
        if overrides is not None:
            for line in overrides.splitlines():
                fields = line.split()
                if len(fields) != 4:
                    self.add('UNVERIFIED', '/var/lib/dpkg/statoverride', 'malformed override')
                    continue
                try:
                    resolved = str(self.resolve(fields[3]))
                    parsed.setdefault(resolved, []).append(fields[:3])
                except (OSError, EvidenceError):
                    self.add('UNVERIFIED', fields[3], 'override target unavailable; package updates may restore privilege')
        for name in HELPERS:
            try:
                path = self.resolve(name, authority=True)
                info = path.lstat()
                self.trusted(path)
                if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o6000:
                    self.add('FAIL', name, 'competing mount helper retains privilege or is not a regular file')
                values = parsed.get(str(path), [])
                if values not in ([['root', 'root', '0755']], [['root', 'root', '755']]):
                    self.add('FAIL', name, 'missing/conflicting persistent root:root 0755 statoverride, accounting for merged-/usr aliases')
            except FileNotFoundError:
                pass
            except (OSError, EvidenceError):
                self.add('UNVERIFIED', name, 'helper target cannot be safely inspected')
        package_paths = [name for name in self.entries if name.startswith('/var/lib/dpkg/info/') and name.endswith('.list')]
        if not package_paths:
            self.add('UNVERIFIED', '/var/lib/dpkg/info', 'package path inventory missing; cannot verify future override persistence')
        for name in package_paths:
            text = self.read(name)
            if text:
                for package_path in text.splitlines():
                    if Path(package_path).name in {Path(helper).name for helper in HELPERS}:
                        if overrides is None or not any(line.split()[3:] == [package_path] for line in overrides.splitlines()):
                            self.add('UNVERIFIED', name, 'package helper path lacks exact dpkg override spelling: ' + package_path)

    def run(self, build_receipt=None):
        if '..' in self.root.parts or self.root == Path('/') or self.root.is_symlink() or not self.root.is_dir():
            self.add('UNVERIFIED', str(self.root), 'explicit existing unmounted staged directory required; live root and root symlinks refused')
        else:
            self.trusted(self.root)
            self.inventory()
            for name, source in INSTALLED.items():
                self.exact(name, (REPO / source).read_text())
            self.capability('/etc/mixpi/controlled-media')
            self.capability('/etc/mixpi/eject-reviewed', optional=True)
            for name in ('/media/pi', '/run', '/opt/mixpi-skin-tools', '/etc/systemd/system'):
                try:
                    path = self.resolve(name, authority=True)
                    self.trusted(path)
                    if not path.is_dir():
                        raise EvidenceError('not a directory')
                except (OSError, EvidenceError):
                    self.add('UNVERIFIED', name, 'required authority/socket parent unavailable')
            self.units_and_policy()
            self.accounts_and_helpers()
        source_hashes = {source: digest((REPO / source).read_bytes()) for source in SOURCES}
        fingerprint = digest(json.dumps([self.entries, self.read_hashes], sort_keys=True).encode())
        candidate = 'UNVERIFIED'
        if build_receipt:
            try:
                receipt = json.loads(Path(build_receipt).read_text())
                if receipt.get('source_sha256') != source_hashes or receipt.get('rootfs_evidence_sha256') != fingerprint:
                    candidate = 'STALE_OR_MISMATCHED'
                    self.add('FAIL', 'build-receipt', 'candidate does not match current sources and inspected rootfs evidence')
                elif not re.fullmatch('[0-9a-f]{64}', receipt.get('image_sha256', '')) or not receipt.get('build_id'):
                    self.add('UNVERIFIED', 'build-receipt', 'missing build identity/image digest')
                else:
                    candidate = 'MATCHED_ATTESTATION_ONLY'
            except (OSError, ValueError, TypeError, AttributeError):
                self.add('UNVERIFIED', 'build-receipt', 'candidate receipt missing, unreadable or malformed')
        else:
            self.add('UNVERIFIED', 'build-receipt', 'no current image provenance supplied; fixtures/recipe are not an installed image')
        static_findings = list(self.findings)
        for name, impact in RUNTIME.items():
            self.add('UNVERIFIED', 'runtime/' + name, impact)
        return dict(schema=1, actual_image_qualification='UNVERIFIED', safe_to_eject=False,
                    static_result='FAIL' if any(item['status'] == 'FAIL' for item in static_findings) else 'UNVERIFIED' if any(item['status'] == 'UNVERIFIED' for item in static_findings) else 'PASS',
                    candidate=candidate, source_sha256=source_hashes, rootfs_evidence_sha256=fingerprint,
                    polkit_order=sorted((name for name in self.entries if name.endswith('.rules') and '/polkit-1/' in name), key=lambda name: (Path(name).name, not name.startswith('/etc/'), name)),
                    findings=self.findings)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rootfs', required=True, help='existing unmounted, quiescent staged image directory; never /')
    parser.add_argument('--build-receipt', help='optional external candidate provenance JSON; never generated as approval')
    args = parser.parse_args()
    report = Checker(args.rootfs).run(args.build_receipt)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if report['static_result'] == 'FAIL' else 2


if __name__ == '__main__':
    sys.exit(main())
