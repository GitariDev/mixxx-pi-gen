#!/usr/bin/env python3
"""Fail-closed importer for the single reviewed 2026-11-10 candidate.

The manifest is an approval input, not a trust claim made by hashing a download.
No archive extraction API is used. Package installation remains apt's job.
"""

import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import posixpath
import re
import stat
import sys
import tarfile


REPO = Path(__file__).resolve().parents[2]
MANIFEST = Path(__file__).with_name('accepted-artifact-20261110.json')
MODE = 'accepted-20261110'
CONFIG = {'MIXPI_ARTIFACT_MODE', 'MIXPI_ARTIFACT_DIR', 'MIXPI_ARTIFACT_MANIFEST_SHA256'}
SKIN = 'usr/share/mixxx/skins/Pioneered'
TOOLS = 'opt/mixpi-skin-tools'
STATE = '.mixpi-accepted'
MAX_ARTIFACT = 32 * 1024 * 1024
MAX_TAR = 96 * 1024 * 1024
DESKTOP = {
    TOOLS + '/mixpi-mount-broker.py': 'stage3/01-install-packages/files/mixpi-mount-broker.py',
    'usr/local/bin/mixpi-mount-control': 'stage3/02-desktop/files/bin/mixpi-mount-control',
    'etc/systemd/system/mixpi-mount-broker.service': 'stage3/02-desktop/files/systemd/mixpi-mount-broker.service',
}
DESKTOP_PREINSTALLED = {'usr/local/bin/mixpi-mount-control'}
PACKAGE_DIRECTORIES = ('usr/share/mixxx', 'usr/share/mixxx/udev', 'usr/share/mixxx/udev/rules.d')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def regular(path, limit=MAX_ARTIFACT):
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_mode & 0o444,
            f'not a readable single regular file: {path}')
    with open(path, 'rb', opener=lambda name, flags: os.open(name, flags | os.O_NOFOLLOW | os.O_NONBLOCK)) as stream:
        info = os.fstat(stream.fileno())
        require((before.st_dev, before.st_ino) == (info.st_dev, info.st_ino), f'file replaced: {path}')
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, f'not a single regular file: {path}')
        require(info.st_size <= limit, f'oversized file: {path}')
        data = stream.read(limit + 1)
        require(len(data) == info.st_size and len(data) <= limit, f'file changed/oversized: {path}')
        after = os.fstat(stream.fileno())
        require((after.st_size, after.st_mtime_ns, after.st_ctime_ns, after.st_ino) ==
                (info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_ino), f'file changed while reading: {path}')
    return data


def safe_path(root, relative, absent=False):
    require(not root.is_symlink() and root.is_dir(), f'unsafe root: {root}')
    info = root.stat()
    require(info.st_uid == os.geteuid() and not info.st_mode & 0o022 and info.st_mode & 0o500 == 0o500,
            f'unsafe root owner/mode: {root}')
    parts = Path(relative).parts
    require(relative and not Path(relative).is_absolute() and '..' not in parts, 'unsafe destination')
    current = root
    for index, part in enumerate(parts):
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError:
            return root / relative
        require(not stat.S_ISLNK(info.st_mode), f'aliased destination: {current}')
        if index < len(parts) - 1:
            require(stat.S_ISDIR(info.st_mode) and info.st_mode & 0o500 == 0o500,
                    f'unsafe/inaccessible parent: {current}')
        require(info.st_uid == os.geteuid() and not info.st_mode & 0o022,
                f'unsafe owner/mode: {current}')
    require(not absent, f'existing destination: {current}')
    return current


def exclusive(root, name, data, mode=0o644):
    target = safe_path(root, name, absent=True)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    safe_path(root, name, absent=True)
    with target.open('xb') as stream:
        stream.write(data)
    target.chmod(mode)


def tar_inventory(data, overlay=False):
    limit = 2 * 1024 * 1024 if overlay else MAX_TAR
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as compressed:
        raw = compressed.read(limit + 1)
    require(len(raw) <= limit, 'expanded archive too large')
    records, contents = {}, {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
        for member in archive:
            require(len(records) < (80 if overlay else 4096), 'too many archive entries')
            name = member.name
            if name.startswith('./'):
                name = name[2:]
            if name == '.':
                name = ''
            require(len(name) <= 240 and not name.startswith('/') and
                    (not name or all(part not in ('', '.', '..') for part in name.split('/'))),
                    f'unsafe archive path: {member.name}')
            require(name not in records, f'duplicate archive path: {name}')
            require(member.isfile() or member.isdir(), f'archive link/special entry: {name}')
            require(not member.pax_headers and not member.linkname, f'extended archive entry: {name}')
            require(member.mode in ((0o755, 0o775) if member.isdir() else (0o644, 0o664, 0o755)),
                    f'unsafe archive mode: {name}')
            require((member.uid, member.gid) == ((1000, 1000) if overlay else (0, 0)),
                    f'unexpected archive ownership: {name}')
            if overlay:
                require(name in ('', 'usr', 'usr/share', 'usr/share/mixxx',
                                 'usr/share/mixxx/skins', 'opt', TOOLS, 'opt/pioneered.version') or
                        name == SKIN or name.startswith(SKIN + '/') or name.startswith(TOOLS + '/'),
                        f'unexpected overlay path: {name}')
            require(0 <= member.size <= (1024 * 1024 if overlay else 32 * 1024 * 1024),
                    f'oversized archive member: {name}')
            record = {'type': 'dir' if member.isdir() else 'file', 'mode': member.mode,
                      'uid': member.uid, 'gid': member.gid, 'size': member.size}
            if member.isfile():
                content = archive.extractfile(member).read(member.size + 1)
                require(len(content) == member.size, f'truncated member: {name}')
                record['sha256'] = digest(content)
                contents[name] = content
            records[name] = record
    for name in records:
        for parent in Path(name).parents:
            key = '' if str(parent) == '.' else str(parent)
            if key in records:
                require(records[key]['type'] == 'dir', f'non-directory archive parent: {name}')
    return records, contents


def deb_inventory(data):
    require(data[:8] == b'!<arch>\n', 'not a Debian ar archive')
    position, members = 8, {}
    for expected in ('debian-binary', 'control.tar.gz', 'data.tar.gz'):
        header = data[position:position + 60]
        require(len(header) == 60 and header[58:] == b'`\n', 'invalid ar header')
        require(header[:16].decode('ascii').strip() == expected, 'unexpected Debian member')
        size = int(header[48:58])
        require(0 <= size <= MAX_ARTIFACT, 'oversized Debian member')
        position += 60
        members[expected] = data[position:position + size]
        require(len(members[expected]) == size, 'truncated Debian member')
        position += size + size % 2
    require(position == len(data) and members['debian-binary'] == b'2.0\n', 'invalid Debian envelope')
    control_records, control_files = tar_inventory(members['control.tar.gz'])
    require(set(control_files) == {'control', 'md5sums'}, 'unexpected maintainer scripts/control files')
    control = control_files['control'].decode('utf-8')
    metadata = {}
    for name in ('Package', 'Version', 'Architecture', 'Depends'):
        matches = re.findall(r'^' + name + r': (.+)$', control, re.M)
        require(len(matches) == 1, f'missing/duplicate Debian field: {name}')
        metadata[name] = matches[0]
    payload, files = tar_inventory(members['data.tar.gz'])
    return {'metadata': metadata, 'control': control_records, 'payload': payload}, files


def configuration():
    found = {name for name in os.environ if name.startswith('MIXPI_ARTIFACT_')}
    require(found == CONFIG, 'partial or unknown artifact configuration')
    require(os.environ['MIXPI_ARTIFACT_MODE'] == MODE, 'unknown artifact mode')
    require(os.environ.get('MIXPI_CONTROLLED_MEDIA') == '0', 'artifact mode requires explicit controlled profile OFF')
    require(os.environ.get('MIXPI_MEDIA_EJECT', '0') == '0', 'artifact mode requires media eject OFF')
    require(os.environ.get('ARCH') == 'arm64', 'artifact image requires ARCH=arm64')
    directory = Path(os.environ['MIXPI_ARTIFACT_DIR'])
    require(directory.is_absolute() and str(directory) == str(directory.resolve()) and directory.is_dir(),
            'artifact directory must be absolute, existing and unaliased')
    approval = os.environ['MIXPI_ARTIFACT_MANIFEST_SHA256']
    require(re.fullmatch('[0-9a-f]{64}', approval), 'explicit approved manifest SHA256 required')
    raw = regular(MANIFEST, 2 * 1024 * 1024)
    require(digest(raw) == approval, 'approved manifest digest mismatch')
    manifest = json.loads(raw)
    require(manifest['schema'] == 1 and manifest['mode'] == MODE, 'unknown manifest')
    require(manifest['deb']['metadata']['Architecture'] == 'arm64', 'manifest architecture mismatch')
    for name, expected in manifest['refs'].items():
        require(os.environ.get(name) == expected, f'source ref mismatch: {name}')
    for name, expected in manifest['sources'].items():
        require(digest(regular(REPO / name)) == expected, f'source input mismatch: {name}')
    script = regular(REPO / 'stage3/01-install-packages/01-run.sh').decode()
    patches = re.search(r'MIXXX_PATCHES=\((.*?)\)', script, re.S)
    require(patches and patches.group(1).split() == manifest['patch_order'], 'patch order mismatch')
    return manifest, raw


def inspect_artifacts(directory, manifest):
    result = {}
    for key in ('deb', 'overlay'):
        expected = manifest[key]
        data = regular(directory / expected['name'])
        require(len(data) == expected['size'] and digest(data) == expected['sha256'], f'{key} digest/size mismatch')
        if key == 'deb':
            inventory, files = deb_inventory(data)
            require(inventory == {name: expected[name] for name in ('metadata', 'control', 'payload')},
                    'Debian payload/metadata manifest mismatch')
            require(digest(files['usr/bin/mixxx']) == manifest['binary_sha256'], 'packaged binary mismatch')
        else:
            inventory, files = tar_inventory(data, overlay=True)
            require(inventory == expected['payload'], 'overlay payload manifest mismatch')
        result[key] = (data, files)
    return result


def integration_identity():
    paths = [REPO / 'build.sh', REPO / 'tools/performance/accepted-artifact.py', MANIFEST]
    paths.extend(path for path in (REPO / 'stage3').rglob('*')
                 if '__pycache__' not in path.parts and (path.is_file() or path.is_symlink()))
    return {str(path.relative_to(REPO)): digest(regular(path)) for path in sorted(paths)}


def work_path():
    work = Path(os.environ['WORK_DIR'])
    require(work.is_absolute() and str(work) == str(work.resolve()), 'WORK_DIR must be absolute and unaliased')
    return work


def complete_stages():
    def failed_walk(error):
        raise error

    for stage in ('stage0', 'stage1', 'stage2', 'stage3'):
        directory = REPO / stage
        require(not directory.is_symlink(), f'aliased required stage: {stage}')
        for parent, directories, files in os.walk(directory, followlinks=False, onerror=failed_walk):
            require('SKIP' not in directories + files, f'artifact mode cannot skip a recipe in {stage}')
            info = Path(parent).lstat()
            require(stat.S_ISDIR(info.st_mode) and info.st_mode & 0o500 == 0o500,
                    f'inaccessible required stage: {parent}')
            for name in directories:
                require(not (Path(parent) / name).is_symlink(), f'aliased stage directory: {parent}/{name}')


def initialize():
    manifest, raw = configuration()
    work = work_path()
    require(not os.path.lexists(work), 'artifact mode requires a fresh dedicated WORK_DIR (no resume)')
    require(os.environ.get('USE_QCOW2', '0') == '0', 'artifact mode does not support reused QCOW2 roots')
    require(not os.environ.get('STAGE_LIST'), 'artifact mode requires the complete default stage list')
    require(not os.environ.get('CLEAN'), 'artifact mode must not clean/reuse old evidence')
    complete_stages()
    artifacts = inspect_artifacts(Path(os.environ['MIXPI_ARTIFACT_DIR']), manifest)
    identity = integration_identity()
    work.mkdir(parents=True, mode=0o755)
    sealed = work / STATE
    sealed.mkdir(mode=0o700)
    for key, (data, _) in artifacts.items():
        exclusive(sealed, manifest[key]['name'], data, 0o444)
    exclusive(sealed, 'manifest.json', raw, 0o444)
    exclusive(sealed, 'seal.json', encoded({'manifest': digest(raw), 'integration': identity,
                                          'work': str(work), 'artifact_dir': os.environ['MIXPI_ARTIFACT_DIR']}), 0o444)
    load()


def load():
    manifest, raw = configuration()
    complete_stages()
    work = work_path()
    sealed = safe_path(work, STATE)
    seal = json.loads(regular(safe_path(sealed, 'seal.json')))
    require(seal['work'] == str(work) and seal['artifact_dir'] == os.environ['MIXPI_ARTIFACT_DIR'], 'seal context mismatch')
    require(seal['manifest'] == digest(raw) and regular(safe_path(sealed, 'manifest.json')) == raw,
            'sealed manifest mismatch')
    require(seal['integration'] == integration_identity(), 'integration/source changed after preflight')
    artifacts = inspect_artifacts(sealed, manifest)
    return manifest, artifacts, sealed


def unit_target(root, relative):
    for _ in range(16):
        safe_path(root, str(Path(relative).parent))
        path = root / relative
        info = path.lstat()
        if not stat.S_ISLNK(info.st_mode):
            return regular(safe_path(root, relative), 1024 * 1024)
        target = os.readlink(path)
        require(not any(word in target for word in ('mixpi-mount', 'controlled-media', 'eject-reviewed')),
                f'inherited systemd authority/mask: {relative}')
        if target == '/dev/null':
            require(Path(relative).name != 'udisks2.service', 'inherited systemd authority/mask: udisks2')
            return b''
        relative = posixpath.normpath(target.lstrip('/') if target.startswith('/') else
                                      posixpath.join(posixpath.dirname(relative), target))
        if relative.startswith('lib/systemd/'):
            alias = root / 'lib'
            require(alias.is_symlink() and os.readlink(alias) in ('usr/lib', '/usr/lib'), 'uncertain systemd library alias')
            relative = 'usr/' + relative
        require(relative.startswith(('etc/systemd/', 'usr/lib/systemd/')), 'uncertain systemd alias target')
    raise ValueError('systemd alias cycle/depth exceeded')


def profile_off(root):
    # R-6: the media eject gate is OFF in every artifact image.
    require(os.environ.get('MIXPI_MEDIA_EJECT', '0') == '0', 'artifact mode requires media eject OFF')
    for name in ('etc/mixpi/controlled-media', 'etc/mixpi/eject-reviewed', 'etc/mixpi/media-eject',
                 'etc/polkit-1/rules.d/49-mixpi-controlled-media.rules',
                 'etc/sysctl.d/90-mixpi-controlled-media.conf'):
        safe_path(root, name, absent=True)
    for name in ('etc/sysctl.conf', 'etc/sudoers', 'var/lib/dpkg/statoverride'):
        path = safe_path(root, name)
        if path.exists():
            reject_profile_policy(regular(path, 1024 * 1024), name)
    checked, total = 0, 0
    for folder in ('etc/polkit-1', 'usr/share/polkit-1/rules.d',
                   'etc/sysctl.d', 'run/sysctl.d', 'usr/local/lib/sysctl.d', 'usr/lib/sysctl.d',
                   'lib/sysctl.d', 'etc/sudoers.d', 'etc/systemd/system', 'etc/systemd/user',
                   'usr/lib/systemd/system', 'usr/lib/systemd/user'):
        if folder == 'lib/sysctl.d' and (root / 'lib').is_symlink():
            require(os.readlink(root / 'lib') in ('usr/lib', '/usr/lib'), 'uncertain sysctl library alias')
            continue
        directory = safe_path(root, folder)
        if not directory.exists():
            continue
        require(directory.is_dir() and directory.stat().st_mode & 0o500 == 0o500, 'inaccessible policy directory')
        for parent, directories, files in os.walk(directory, followlinks=False):
            for name in directories + files:
                checked += 1
                require(checked <= 8192, 'policy inventory too large')
                path = Path(parent) / name
                relative = str(path.relative_to(root))
                if relative == 'etc/systemd/system/mixpi-mount-broker.service':
                    continue
                require('mixpi-mount-broker' not in name and 'controlled-media' not in name and
                        'eject-reviewed' not in name, f'inherited profile/enablement: {relative}')
                if path.is_symlink() and 'systemd/' in folder and name in files:
                    data = unit_target(root, relative)
                    require(not any(word in data for word in (b'mixpi-mount', b'controlled-media', b'eject-reviewed')),
                            f'inherited profile policy through unit alias: {relative}')
                    continue
                safe_path(root, relative)
                if path.is_file():
                    data = regular(path, 1024 * 1024)
                    total += len(data)
                    require(total <= 32 * 1024 * 1024, 'policy content too large')
                    reject_profile_policy(data, relative)


def reject_profile_policy(data, name):
    require(not any(word in data for word in (b'mixpi-mount', b'controlled-media', b'eject-reviewed')),
            f'inherited profile policy: {name}')
    if name.endswith('.rules'):
        policy = regular(REPO / 'stage3/02-desktop/files/49-mixpi-controlled-media.rules')
        normalized = re.sub(rb'\s+', b'', policy)
        require(normalized and normalized not in re.sub(rb'\s+', b'', data),
                f'inherited profile polkit policy: {name}')
    for line in data.splitlines():
        assignment = re.split(rb'[#;]', line, maxsplit=1)[0].strip().partition(b'=')
        key = assignment[0].lstrip(b'-').strip().replace(b'/', b'.')
        require(not (assignment[1] and key == b'user.max_user_namespaces' and assignment[2].strip() == b'0'),
                f'inherited profile namespace policy: {name}')
    require(not re.search(rb'NOPASSWD:\s*/usr/sbin/shutdown\b', data), f'inherited profile sudo policy: {name}')
    if name == 'var/lib/dpkg/statoverride':
        controlled = {b'/usr/bin/udevil', b'/usr/bin/mount', b'/usr/bin/umount', b'/usr/bin/fusermount',
                      b'/usr/bin/fusermount3', b'/usr/bin/ntfs-3g', b'/usr/sbin/mount.cifs'}
        for line in data.splitlines():
            fields = line.split()
            if fields:
                executable = posixpath.normpath(fields[-1])
                if executable.startswith((b'/bin/', b'/sbin/')):
                    executable = b'/usr' + executable
                require(executable not in controlled, 'inherited profile dpkg overrides')


def root_path():
    root = Path(os.environ['ROOTFS_DIR'])
    require(root == work_path() / 'stage3/rootfs', 'artifact stages require dedicated stage3 rootfs')
    require(root.is_dir() and str(root) == str(root.resolve()), 'missing/aliased rootfs')
    profile_off(root)
    return root


def fresh_payload(root, payload):
    for name, record in payload.items():
        if name:
            target = safe_path(root, name, absent=record['type'] == 'file')
            if target.exists():
                require(target.is_dir(), f'not a directory: {target}')


def verify_payload(root, payload):
    for name, record in payload.items():
        if name in PACKAGE_DIRECTORIES:
            target = safe_path(root, name)
            require(target.is_dir() and stat.S_IMODE(target.stat().st_mode) == 0o755,
                    f'installed package directory mode mismatch: {name}')
        if record['type'] == 'file':
            target = safe_path(root, name)
            require(digest(regular(target)) == record['sha256'], f'installed payload mismatch: {name}')
            mode = 0o755 if record['mode'] == 0o755 else 0o644
            require(stat.S_IMODE(target.stat().st_mode) == mode, f'installed mode mismatch: {name}')


def normalize_package_directories(root, payload):
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK
    descriptors = []
    try:
        descriptors.append(os.open(safe_path(root, 'usr/share'), flags))
        for name in PACKAGE_DIRECTORIES:
            require(payload.get(name) == {'type': 'dir', 'mode': 0o775, 'uid': 0, 'gid': 0, 'size': 0},
                    f'unexpected package directory manifest: {name}')
            descriptor = os.open(Path(name).name, flags, dir_fd=descriptors[-1])
            descriptors.append(descriptor)
            info = os.fstat(descriptor)
            require(info.st_uid == os.geteuid() and info.st_gid == os.getegid() and
                    stat.S_IMODE(info.st_mode) in (0o755, 0o775),
                    f'unexpected package directory owner/mode: {name}')
        for descriptor in descriptors[1:]:
            os.fchmod(descriptor, 0o755)
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def phase(sealed, name):
    require(regular(safe_path(sealed, name)) == b'complete\n', f'incomplete phase: {name}')


def prepare():
    manifest, artifacts, sealed = load()
    root = root_path()
    for name in ('opt/mixxx-package', 'opt/mixxx-patches', 'opt/mixxx.version', 'opt/mixxx.tag',
                 'opt/mixpi-accepted-artifact', SKIN, TOOLS, 'opt/pioneered.version', 'opt/pi-dj.version'):
        safe_path(root, name, absent=True)
    safe_path(sealed, 'prepared', absent=True)
    status = safe_path(root, 'var/lib/dpkg/status')
    if status.exists():
        require(not re.search(rb'^Package: mixxx$', regular(status, 32 * 1024 * 1024), re.M),
                'preexisting Mixxx dpkg state')
    information = safe_path(root, 'var/lib/dpkg/info')
    if information.exists():
        require(not any(information.glob('mixxx.*')) and not any(information.glob('mixxx:*')),
                'stale Mixxx dpkg metadata')
    fresh_payload(root, manifest['deb']['payload'])
    fresh_payload(root, manifest['overlay']['payload'])
    for name in DESKTOP:
        safe_path(root, name, absent=True)
    exclusive(root, 'opt/mixxx-package/candidate.deb', artifacts['deb'][0])
    exclusive(root, 'opt/mixxx.version', (manifest['refs']['MIXXX_COMMIT'] + '\n').encode())
    exclusive(root, 'opt/mixxx.tag', (manifest['refs']['MIXXX_REF'] + '\n').encode())
    for name in manifest['patch_order']:
        exclusive(root, 'opt/mixxx-patches/' + name, regular(REPO / 'stage3/01-install-packages/files' / name))
    exclusive(root, 'opt/mixpi-accepted-artifact/manifest.json', regular(MANIFEST))
    exclusive(root, 'opt/mixpi-accepted-artifact/seal.json', regular(sealed / 'seal.json'))
    load()
    exclusive(sealed, 'prepared', b'complete\n', 0o444)


def installed():
    manifest, _, sealed = load()
    phase(sealed, 'prepared')
    root = root_path()
    require(digest(regular(safe_path(root, 'opt/mixxx-package/candidate.deb'))) == manifest['deb']['sha256'],
            'installed package source changed')
    normalize_package_directories(root, manifest['deb']['payload'])
    verify_payload(root, manifest['deb']['payload'])
    exclusive(sealed, 'installed', b'complete\n', 0o444)


def copy_pi_dj(source):
    manifest, _, sealed = load()
    phase(sealed, 'installed')
    root = root_path()
    verify_payload(root, manifest['deb']['payload'])
    safe_path(root, SKIN, absent=True)
    safe_path(root, TOOLS, absent=True)
    require(source.is_dir() and not source.is_symlink(), 'unsafe pi_dj source')
    files = {}
    for path in sorted(source.rglob('*')):
        require(not path.is_symlink(), 'pi_dj contains a link')
        name = 'usr/share/mixxx/skins/' + str(path.relative_to(source))
        require(name != SKIN and not name.startswith(SKIN + '/'), 'pi_dj overlaps accepted overlay')
        require(path.is_file() or path.is_dir(), 'pi_dj special entry')
        safe_path(root, name, absent=path.is_file())
        if path.is_file():
            files[name] = regular(path, 8 * 1024 * 1024)
        require(len(files) <= 4096 and sum(map(len, files.values())) <= 64 * 1024 * 1024, 'pi_dj too large')
    for name, data in files.items():
        exclusive(root, name, data)
    exclusive(root, 'opt/pi-dj.version', (manifest['refs']['PI_DJ_COMMIT'] + '\n').encode())
    load()
    exclusive(sealed, 'pi-dj', b'complete\n', 0o444)


def overlay():
    manifest, artifacts, sealed = load()
    phase(sealed, 'pi-dj')
    root = root_path()
    verify_payload(root, manifest['deb']['payload'])
    safe_path(root, SKIN, absent=True)
    safe_path(root, TOOLS, absent=True)
    fresh_payload(root, manifest['overlay']['payload'])
    for name, data in artifacts['overlay'][1].items():
        record = manifest['overlay']['payload'][name]
        exclusive(root, name, data, 0o755 if record['mode'] == 0o755 else 0o644)
    verify_payload(root, manifest['overlay']['payload'])
    load()
    exclusive(sealed, 'overlay', b'complete\n', 0o444)


def verify(final=False):
    manifest, _, sealed = load()
    phase(sealed, 'overlay')
    root = root_path()
    verify_payload(root, manifest['deb']['payload'])
    verify_payload(root, manifest['overlay']['payload'])
    for folder in (SKIN, TOOLS):
        expected = {name for name in manifest['overlay']['payload'] if name.startswith(folder + '/')}
        if final and folder == TOOLS:
            expected.add(TOOLS + '/mixpi-mount-broker.py')
        actual = {str(path.relative_to(root)) for path in (root / folder).rglob('*')}
        require(actual == expected, f'unexpected overlay entries: {folder}')
    for destination, source in DESKTOP.items():
        if final or destination in DESKTOP_PREINSTALLED:
            target = safe_path(root, destination)
            require(regular(target) == regular(REPO / source), f'desktop helper mismatch: {destination}')
            require(stat.S_IMODE(target.stat().st_mode) == (0o755 if destination.endswith('control') else 0o644),
                    f'desktop helper mode mismatch: {destination}')
        else:
            safe_path(root, destination, absent=True)
    require(regular(safe_path(root, 'opt/mixpi-accepted-artifact/manifest.json')) == regular(MANIFEST), 'lineage manifest changed')
    require(regular(safe_path(root, 'opt/mixpi-accepted-artifact/seal.json')) == regular(sealed / 'seal.json'),
            'lineage seal changed')
    require(digest(regular(safe_path(root, 'opt/mixxx-package/candidate.deb'))) == manifest['deb']['sha256'],
            'retained package changed')
    for name, reference in (('mixxx.version', 'MIXXX_COMMIT'), ('mixxx.tag', 'MIXXX_REF'), ('pi-dj.version', 'PI_DJ_COMMIT')):
        require(regular(safe_path(root, 'opt/' + name)) == (manifest['refs'][reference] + '\n').encode(),
                f'lineage ref changed: {name}')
    for name in manifest['patch_order']:
        expected = manifest['sources']['stage3/01-install-packages/files/' + name]
        require(digest(regular(safe_path(root, 'opt/mixxx-patches/' + name))) == expected, 'lineage patch changed')
    if final:
        load()
        receipt = {'status': 'assembled-not-image-qualified', 'manifest_sha256': digest(regular(MANIFEST)),
                   'binary_sha256': manifest['binary_sha256'], 'controlled_media': 'OFF',
                   'eject_reviewed': False, 'media_eject': 'OFF',
                   'package_directory_modes': {name: '0755' for name in PACKAGE_DIRECTORIES}}
        exclusive(root, 'opt/mixpi-accepted-artifact/integration.json', encoded(receipt))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('validate', 'initialize', 'prepare', 'installed', 'pi-dj', 'overlay', 'desktop', 'final'))
    parser.add_argument('source', nargs='?', type=Path)
    args = parser.parse_args()
    if args.action == 'validate':
        manifest, _ = configuration()
        inspect_artifacts(Path(os.environ['MIXPI_ARTIFACT_DIR']), manifest)
    elif args.action == 'pi-dj':
        require(args.source is not None, 'pi_dj directory required')
        copy_pi_dj(args.source)
    elif args.action in ('desktop', 'final'):
        verify(final=args.action == 'final')
        print('accepted-artifact: media eject OFF')
    else:
        globals()[args.action]()
    print('accepted-artifact: ' + args.action + ' PASS (not image qualification)')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, tarfile.TarError, UnicodeError) as error:
        sys.exit('accepted-artifact: REFUSED: ' + str(error))
