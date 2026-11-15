#!/usr/bin/env python3
"""Bounded build settings and exact candidate provenance, never owner approval.

Only the explicitly supplied fresh source tree, declared recipe inputs, build
configuration and direct package outputs are inspected. No package is installed
and no application binary is executed by this tool.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import stat
import struct
import subprocess
import sys
import tarfile


SCHEMA = 'mixpi-candidate-v1'
RESOURCE_KEYS = ('CMAKE_BUILD_PARALLEL_LEVEL', 'CTEST_PARALLEL_LEVEL',
                 'CCACHE_MAXSIZE', 'CCACHE_COMPRESS', 'CCACHE_COMPRESSLEVEL')
BUILD_ENV = RESOURCE_KEYS + ('CCACHE_NOCOMPRESS', 'MIXXX_CCACHE_COMPRESSION',
    'CCACHE_NOHARDLINK', 'CCACHE_NOFILECLONE', 'CCACHE_DIR', 'CC', 'CXX', 'CFLAGS', 'CXXFLAGS',
    'CPPFLAGS', 'LDFLAGS', 'CMAKE_GENERATOR', 'SOURCE_DATE_EPOCH',
    'CMAKE_PREFIX_PATH', 'CMAKE_TOOLCHAIN_FILE', 'PKG_CONFIG_PATH', 'PKG_CONFIG_LIBDIR',
    'PKG_CONFIG_SYSROOT_DIR', 'CPATH', 'C_INCLUDE_PATH', 'CPLUS_INCLUDE_PATH', 'LIBRARY_PATH',
    'FONTS_UBUNTU_AVAILABLE', 'QT_QPA_PLATFORM', 'GTEST_COLOR', 'CTEST_OUTPUT_ON_FAILURE')
ELF_ARCH = {'arm64': (2, 183), 'amd64': (2, 62), 'armhf': (1, 40), 'i386': (1, 3)}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def file_record(path, allow_hardlinks=False):
    path = Path(path)
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and (allow_hardlinks or before.st_nlink == 1),
            f'unsafe regular file: {path}')
    digest = hashlib.sha256()
    with open(path, 'rb', opener=lambda name, flags: os.open(name, flags | os.O_NOFOLLOW | os.O_NONBLOCK)) as stream:
        opened = os.fstat(stream.fileno())
        require((opened.st_dev, opened.st_ino) == (before.st_dev, before.st_ino), f'file replaced: {path}')
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    after = path.lstat()
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns),
            f'file changed while hashing: {path}')
    return {'sha256': digest.hexdigest(), 'size': before.st_size,
            'mode': stat.S_IMODE(before.st_mode)}


def command(arguments):
    return subprocess.check_output([str(argument) for argument in arguments], text=True).strip()


def resource_settings(environment):
    settings = {}
    for key in RESOURCE_KEYS[:2]:
        value = environment.get(key, '2')
        require(re.fullmatch(r'[1-9][0-9]*', value) and int(value) <= 64,
                f'{key} must be an integer in 1..64')
        settings[key] = value
    maximum = environment.get('CCACHE_MAXSIZE', '1G')
    match = re.fullmatch(r'([1-9][0-9]*)([MG])', maximum)
    require(match is not None, 'CCACHE_MAXSIZE must use integral M or G units')
    megabytes = int(match[1]) * (1024 if match[2] == 'G' else 1)
    require(16 <= megabytes <= 4096, 'CCACHE_MAXSIZE must be 16M..4G')
    settings['CCACHE_MAXSIZE'] = maximum
    compression = environment.get('MIXXX_CCACHE_COMPRESSION', environment.get('CCACHE_COMPRESS', 'true'))
    require(compression in ('true', 'false'), 'CCACHE_COMPRESS must be true or false')
    require('MIXXX_CCACHE_COMPRESSION' not in environment or 'CCACHE_COMPRESS' not in environment
            or compression == environment['CCACHE_COMPRESS'], 'conflicting compression settings')
    if 'CCACHE_NOCOMPRESS' in environment:
        legacy = environment['CCACHE_NOCOMPRESS']
        require(legacy in ('true', 'false'), 'CCACHE_NOCOMPRESS must be true or false')
        normalized = 'false' if legacy == 'true' else 'true'
        require(not {'CCACHE_COMPRESS', 'MIXXX_CCACHE_COMPRESSION'}.intersection(environment)
                or compression == normalized,
                'conflicting compression settings')
        compression = normalized
    settings['CCACHE_COMPRESS'] = compression
    level = environment.get('CCACHE_COMPRESSLEVEL', '1')
    require(re.fullmatch(r'-?[0-9]+', level) and -5 <= int(level) <= 19,
            'CCACHE_COMPRESSLEVEL must be -5..19')
    settings['CCACHE_COMPRESSLEVEL'] = level
    return settings


def source_path(source, name):
    relative = PurePosixPath(name)
    require(name and not relative.is_absolute() and '..' not in relative.parts,
            f'unsafe source path: {name}')
    require(relative.parts[0] not in ('.git', 'build'), f'excluded source path: {name}')
    parent = source
    for part in relative.parts[:-1]:
        parent = parent / part
        require(not parent.is_symlink(), f'aliased source parent: {name}')
    return source / name


def source_identity(source, commit, patches):
    source = Path(source)
    require(source.is_dir() and not source.is_symlink(), 'unsafe source root')
    actual = command(['git', '-C', source, 'rev-parse', 'HEAD'])
    require(re.fullmatch('[0-9a-f]{40}', commit) and actual == commit, 'upstream pin mismatch')
    names = set(subprocess.check_output(['git', '-C', str(source), 'ls-files',
        '--cached', '--others', '--exclude-standard', '-z']).decode().split('\0')) - {''}
    for patch_path in patches:
        changes = subprocess.check_output(['git', '-C', str(source), 'apply', '--numstat',
                                          '-z', str(Path(patch_path).resolve())]).decode().split('\0')
        for change in filter(None, changes):
            fields = change.split('\t', 2)
            require(len(fields) == 3 and fields[2], 'unsupported patch path/rename')
            names.add(fields[2])
    records = []
    for name in sorted(names):
        if PurePosixPath(name).parts[0] in ('.git', 'build'):
            continue
        path = source_path(source, name)
        if path.is_symlink():
            target = os.readlink(path)
            require(not os.path.isabs(target) and path.resolve().is_relative_to(source.resolve()),
                    f'escaping source symlink: {name}')
            resolved = path.resolve()
            require(resolved.relative_to(source.resolve()).parts[0] not in ('.git', 'build'),
                    f'source symlink into excluded tree: {name}')
            record = {'kind': 'symlink', 'target': target, 'sha256': sha256(target.encode()),
                      'target_file': file_record(resolved)}
        elif not path.exists():
            record = {'kind': 'deleted'}
        else:
            record = {'kind': 'file', **file_record(path)}
        records.append({'path': name, **record})
    return {'upstream_commit': actual,
            'upstream_tree': command(['git', '-C', source, 'rev-parse', 'HEAD^{tree}']),
            'sha256': sha256(encoded(records)), 'files': records,
            'scope': 'git tracked + nonignored untracked + every patch path; excludes root build/ and .git/'}


def elf_identity(data):
    require(len(data) >= 52 and data[:4] == b'\x7fELF' and data[4] in (1, 2)
            and data[5] in (1, 2), 'packaged mixxx is not a supported ELF binary')
    endian = '<' if data[5] == 1 else '>'
    wide = data[4] == 2
    layout = endian + ('HHIQQQIHHHHHH' if wide else 'HHIIIIIHHHHHH')
    header = struct.unpack_from(layout, data, 16)
    elf_type, machine, version, entry, phoff, shoff, flags, ehsize, phsize, phcount, *_ = header
    expected_size = 56 if wide else 32
    require(elf_type in (2, 3) and version == 1 and phsize == expected_size and
            0 < phcount < 4096 and phoff + phsize * phcount <= len(data), 'invalid ELF headers')
    segments = []
    interpreter = None
    build_ids = []
    dynamic = []
    for index in range(phcount):
        values = struct.unpack_from(endian + ('IIQQQQQQ' if wide else 'IIIIIIII'),
                                    data, phoff + index * phsize)
        if wide:
            kind, permissions, offset, address, physical, size, memory_size, alignment = values
        else:
            kind, offset, address, physical, size, memory_size, permissions, alignment = values
        require(offset + size <= len(data), 'ELF segment outside binary')
        segments.append((kind, offset, address, size))
        if kind == 3:
            require(interpreter is None and size > 1 and data[offset + size - 1] == 0,
                    'invalid ELF interpreter')
            interpreter = data[offset:offset + size - 1].decode('utf-8')
        if kind == 4:
            cursor = offset
            while cursor + 12 <= offset + size:
                name_size, value_size, note_type = struct.unpack_from(endian + 'III', data, cursor)
                cursor += 12
                note_name = data[cursor:cursor + name_size]
                cursor += (name_size + 3) & ~3
                require(cursor + value_size <= offset + size, 'invalid ELF note')
                if note_name == b'GNU\0' and note_type == 3:
                    build_ids.append(data[cursor:cursor + value_size].hex())
                cursor += (value_size + 3) & ~3
        if kind == 2:
            stride = 16 if wide else 8
            require(size % stride == 0, 'invalid ELF dynamic segment')
            for cursor in range(offset, offset + size, stride):
                tag, value = struct.unpack_from(endian + ('qQ' if wide else 'iI'), data, cursor)
                if tag == 0:
                    break
                dynamic.append((tag, value))
    strings = {}
    if dynamic:
        addresses = [value for tag, value in dynamic if tag == 5]
        sizes = [value for tag, value in dynamic if tag == 10]
        require(len(addresses) == len(sizes) == 1, 'missing ELF dynamic string table')
        tables = [offset + addresses[0] - address for kind, offset, address, size in segments
                  if kind == 1 and address <= addresses[0] and addresses[0] + sizes[0] <= address + size]
        require(len(tables) == 1, 'invalid ELF dynamic string table')
        table = data[tables[0]:tables[0] + sizes[0]]
        for tag, value in dynamic:
            if tag in (1, 14, 15, 29):
                require(value < len(table) and b'\0' in table[value:], 'invalid ELF dynamic string')
                strings.setdefault(str(tag), []).append(table[value:].split(b'\0', 1)[0].decode())
    return {'class': 64 if wide else 32, 'data': 'little' if endian == '<' else 'big',
            'machine': machine, 'type': elf_type, 'flags': flags, 'interpreter': interpreter,
            'gnu_build_ids': build_ids, 'needed': strings.get('1', []),
            'soname': strings.get('14', []), 'rpath': strings.get('15', []),
            'runpath': strings.get('29', [])}


def packaged_identity(package, architecture):
    record = file_record(package)
    metadata = {key: command(['dpkg-deb', '--field', package, key])
                for key in ('Package', 'Version', 'Architecture')}
    require(metadata['Package'] == 'mixxx' and metadata['Version'] and
            metadata['Architecture'] == architecture and architecture in ELF_ARCH,
            'package name/version/architecture mismatch')
    binary = None
    with subprocess.Popen(['dpkg-deb', '--fsys-tarfile', str(package)], stdout=subprocess.PIPE) as process:
        try:
            with tarfile.open(fileobj=process.stdout, mode='r|') as archive:
                for member in archive:
                    name = member.name
                    while name.startswith('./'):
                        name = name[2:]
                    relative = PurePosixPath(name)
                    require(not relative.is_absolute() and '..' not in relative.parts,
                            'unsafe package payload path')
                    name = str(relative)
                    if name in ('usr', 'usr/bin'):
                        require(member.isdir(), 'aliased binary parent in package')
                    if name == 'usr/bin/mixxx':
                        require(binary is None and member.isfile() and not member.islnk()
                                and member.mode & 0o111 and 0 < member.size <= 256 * 1024 * 1024,
                                'unsafe/duplicate packaged binary')
                        data = archive.extractfile(member).read()
                        require(len(data) == member.size, 'truncated packaged binary')
                        elf = elf_identity(data)
                        require((data[4], elf['machine']) == ELF_ARCH[architecture] and data[5] == 1,
                                'packaged binary architecture mismatch')
                        binary = {'path': '/usr/bin/mixxx', 'sha256': sha256(data),
                                  'size': len(data), 'mode': member.mode, 'elf': elf}
            require(process.wait() == 0, 'dpkg-deb extraction failed')
        except BaseException:
            process.kill()
            process.wait()
            raise
    require(binary is not None, 'missing packaged /usr/bin/mixxx')
    require(file_record(package) == record, 'package changed while inspecting')
    return {'name': Path(package).name, **record, 'metadata': metadata, 'binary': binary}


def package_output(directory, sidecar=False):
    directory = Path(directory)
    require(directory.is_dir() and not directory.is_symlink(), 'unsafe output directory')
    packages = sorted(directory.glob('*.deb'))
    require(len(packages) == 1, 'expected exactly one fresh mixxx DEB output')
    package = packages[0]
    file_record(package)
    manifests = sorted(directory.glob('*.candidate.json'))
    expected = [package.with_name(package.name + '.candidate.json')] if sidecar else []
    require(manifests == expected, 'stale, absent or extra candidate sidecars')
    if sidecar:
        file_record(manifests[0])
    return package


def write_new(path, value):
    path = Path(path)
    with path.open('xb') as stream:
        stream.write(encoded(value))


def input_records(args):
    records = {'recipe': {'path': str(args.recipe), **file_record(args.recipe)},
               'candidate_helper': {'path': str(Path(__file__).resolve()), **file_record(Path(__file__).resolve())},
               'source_versions': {'path': str(args.source_versions), **file_record(args.source_versions)}}
    for key in ('MIXXX_CACHE_SMOKE_SCRIPT', 'MIXXX_TOUCH_SMOKE_SCRIPT'):
        if os.environ.get(key):
            records[key] = {'path': os.environ[key], **file_record(Path(os.environ[key]))}
            companion = {'MIXXX_CACHE_SMOKE_SCRIPT': ('test-ram-cache.sh', 'ram-cache-smoke.cpp'),
                         'MIXXX_TOUCH_SMOKE_SCRIPT': ('test-source-navigation.sh', 'source-navigation-smoke.cpp')}[key]
            script = Path(os.environ[key])
            if script.name == companion[0]:
                path = script.with_name(companion[1])
                records[key + '_fixture'] = {'path': str(path), **file_record(path)}
    if os.environ.get('CMAKE_TOOLCHAIN_FILE'):
        path = Path(os.environ['CMAKE_TOOLCHAIN_FILE'])
        require(path.is_absolute(), 'CMAKE_TOOLCHAIN_FILE must be absolute for provenance')
        records['toolchain_file'] = {'path': str(path), **file_record(path)}
    return records


def tool_identity(name):
    executable_path = shutil.which(name)
    require(executable_path is not None, f'missing build tool: {name}')
    path = Path(executable_path).resolve()
    return {'path': str(path), **file_record(path, allow_hardlinks=True), 'version': command([path, '--version'])}


def prepare(args):
    source = args.source.resolve()
    require(not (source / 'build').exists(), 'stale build directory')
    resource_settings(os.environ)
    inputs = input_records(args)
    patches = [{'name': path.name, 'path': str(path.resolve()), **file_record(path)} for path in args.patch]
    require(patches and len({entry['name'] for entry in patches}) == len(patches), 'missing/duplicate patches')
    state = {'schema': SCHEMA, 'approval': False, 'upstream': {'ref': args.ref, 'commit': args.commit},
             'source_directory': str(source), 'inputs': inputs, 'patches': patches,
             'source': source_identity(source, args.commit, args.patch),
             'settings': {key: os.environ[key] for key in BUILD_ENV if key in os.environ},
             'cmake_flags': args.cmake_flag,
             'architecture': command(['dpkg', '--print-architecture']),
             'tools': {name: tool_identity(name) for name in ('cmake', 'cpack', 'ccache', 'git', 'dpkg-deb')}}
    require(state['architecture'] in ELF_ARCH, 'unsupported build architecture')
    (source / 'build').mkdir()
    write_new(source / 'build/mixxx-candidate-inputs.json', state)


def configuration_identity(directory):
    configuration = {name: file_record(directory / name) for name in ('CMakeCache.txt', 'CPackConfig.cmake')}
    cache = (directory / 'CMakeCache.txt').read_text()
    compilers = {}
    for language in ('C', 'CXX'):
        match = re.search(r'^CMAKE_' + language + r'_COMPILER:(?:FILEPATH|STRING)=(.+)$', cache, re.M)
        require(match is not None, f'missing configured {language} compiler')
        compilers[language] = tool_identity(match[1])
    tools = {}
    for name in ('LINKER', 'AR', 'RANLIB', 'STRIP', 'NM', 'OBJCOPY', 'MAKE_PROGRAM'):
        match = re.search(r'^CMAKE_' + name + r':(?:FILEPATH|STRING)=(.+)$', cache, re.M)
        if match and not match[1].endswith('-NOTFOUND'):
            tools[name] = tool_identity(match[1])
    return {'files': configuration, 'compilers': compilers, 'tools': tools}


def configured(args):
    require(not list(args.output_dir.glob('*.deb')) and not list(args.output_dir.glob('*.candidate.json')),
            'stale package output before compilation')
    write_new(args.output_dir / 'mixxx-candidate-configuration.json', configuration_identity(args.output_dir))


def emit(args):
    directory = args.output_dir
    state_path = directory / 'mixxx-candidate-inputs.json'
    file_record(state_path)
    state = json.loads(state_path.read_text())
    require(state['schema'] == SCHEMA and state['approval'] is False, 'not candidate build inputs')
    require(directory.resolve() == Path(state['source_directory']) / 'build', 'build location changed')
    for entry in list(state['inputs'].values()) + state['patches']:
        current = file_record(Path(entry['path']))
        require(all(current[key] == entry[key] for key in ('sha256', 'size', 'mode')),
                f'build input changed: {entry["path"]}')
    source = source_identity(Path(state['source_directory']), state['upstream']['commit'],
                             [Path(entry['path']) for entry in state['patches']])
    require(source == state['source'], 'composed source changed during build')
    require(state['settings'] == {key: os.environ[key] for key in BUILD_ENV if key in os.environ},
            'build settings changed')
    require(state['tools'] == {name: tool_identity(name) for name in state['tools']}, 'build tool changed')
    configuration_path = directory / 'mixxx-candidate-configuration.json'
    file_record(configuration_path)
    configuration = json.loads(configuration_path.read_text())
    require(configuration == configuration_identity(directory), 'configured build inputs changed')
    package = package_output(directory)
    state.update({'configuration': configuration,
                  'deb': packaged_identity(package, state['architecture'])})
    state['candidate_id'] = sha256(encoded(state))
    write_new(package.with_name(package.name + '.candidate.json'), state)


def verify(args):
    package = package_output(args.output_dir, sidecar=True)
    manifest_path = package.with_name(package.name + '.candidate.json')
    manifest = json.loads(manifest_path.read_text())
    require(manifest.get('schema') == SCHEMA and manifest.get('approval') is False,
            'not a candidate manifest (no acceptance is granted)')
    candidate_id = manifest.pop('candidate_id')
    require(sha256(encoded(manifest)) == candidate_id, 'candidate manifest digest mismatch')
    require(manifest['deb'] == packaged_identity(package, manifest['architecture']), 'DEB/manifest mismatch')
    if args.installed:
        installed = file_record(args.installed)
        expected = manifest['deb']['binary']
        require(all(installed[key] == expected[key] for key in ('sha256', 'size', 'mode')),
                'installed /usr/bin/mixxx does not match packaged binary')
        metadata = manifest['deb']['metadata']
        require(command(['dpkg', '--print-architecture']) == metadata['Architecture'],
                'installed architecture mismatch')
        require(command(['dpkg-query', '-W', '-f=${Status} ${Package} ${Architecture} ${Version}', 'mixxx']) ==
                'install ok installed ' + ' '.join(metadata[key] for key in ('Package', 'Architecture', 'Version')),
                'installed package metadata mismatch')
        require(command(['dpkg-query', '-S', '/usr/bin/mixxx']) == 'mixxx: /usr/bin/mixxx',
                'installed binary ownership mismatch')
    print(candidate_id)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    commands.add_parser('resources')
    build = commands.add_parser('prepare')
    for name in ('source', 'recipe', 'source-versions'):
        build.add_argument('--' + name, type=Path, required=True)
    build.add_argument('--ref', required=True)
    build.add_argument('--commit', required=True)
    build.add_argument('--patch', type=Path, action='append', required=True)
    build.add_argument('--cmake-flag', action='append', default=[])
    finish = commands.add_parser('emit')
    finish.add_argument('--output-dir', type=Path, required=True)
    configuration = commands.add_parser('configured')
    configuration.add_argument('--output-dir', type=Path, required=True)
    check = commands.add_parser('verify')
    check.add_argument('--output-dir', type=Path, required=True)
    check.add_argument('--installed', type=Path)
    args = parser.parse_args()
    try:
        if args.action == 'resources':
            settings = resource_settings(os.environ)
            print('unset CCACHE_COMPRESS CCACHE_NOCOMPRESS CCACHE_HARDLINK CCACHE_FILECLONE')
            print('export CCACHE_NOHARDLINK=true CCACHE_NOFILECLONE=true')
            compression = settings.pop('CCACHE_COMPRESS')
            print(f'export MIXXX_CCACHE_COMPRESSION={compression}')
            print('export ' + ('CCACHE_COMPRESS' if compression == 'true' else 'CCACHE_NOCOMPRESS') + '=true')
            for key, value in settings.items():
                print(f'export {key}={shlex.quote(value)}')
        else:
            globals()[args.action](args)
    except (OSError, ValueError, KeyError, UnicodeError, struct.error,
            tarfile.TarError, subprocess.SubprocessError) as error:
        print(f'candidate provenance refused: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
