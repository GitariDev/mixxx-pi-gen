#!/usr/bin/env python3
"""Verify stripped package bytes using quiescent inputs and a pinned strip tool."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def verify(staged, packaged, strip_tool, expected_strip_sha256):
    if not re.fullmatch(r'[0-9a-f]{64}', expected_strip_sha256):
        raise ValueError('Expected strip SHA-256 must be 64 lowercase hex characters')
    staged = Path(staged).resolve(strict=True)
    packaged = Path(packaged).resolve(strict=True)
    strip_tool = Path(strip_tool).resolve(strict=True)
    before = {path: digest(path) for path in (staged, packaged, strip_tool)}
    if before[strip_tool] != expected_strip_sha256:
        raise ValueError('Strip tool does not match the frozen digest')
    with tempfile.TemporaryDirectory(prefix='mixpi-strip-check-') as temporary:
        output = Path(temporary) / 'stripped'
        subprocess.run([str(strip_tool), '-o', str(output), str(staged)],
                       check=True, capture_output=True, timeout=60)
        stripped_sha256 = digest(output)
    if any(digest(path) != value for path, value in before.items()):
        raise ValueError('An input changed during verification')
    if stripped_sha256 != before[packaged]:
        raise ValueError('Packaged executable differs from independently stripped stage')
    return {'strip_equivalence': 'PASS', 'strip_tool': str(strip_tool),
            'strip_sha256': before[strip_tool], 'staged_sha256': before[staged],
            'packaged_sha256': before[packaged], 'application_executed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--staged', required=True, type=Path)
    parser.add_argument('--packaged', required=True, type=Path)
    parser.add_argument('--strip-tool', required=True, type=Path)
    parser.add_argument('--strip-sha256', required=True)
    args = parser.parse_args()
    try:
        receipt = verify(args.staged, args.packaged, args.strip_tool, args.strip_sha256)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(json.dumps({'strip_equivalence': 'FAIL', 'error': str(error)}))
        return 1
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
