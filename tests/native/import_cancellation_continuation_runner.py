"""Apply the optional cancellation delta before the existing continuation fixture."""
import os
from pathlib import Path
import subprocess

import media_continuation_runner

original_reconstruct = media_continuation_runner.reconstruct


def reconstruct(target):
    names, baseline = original_reconstruct(target)
    override = os.environ.get('MIXXX_IMPORT_CANCELLATION_PATCH')
    if override and Path(override).name not in names:
        subprocess.run(['git', 'apply', '--check', str(Path(override).resolve())], cwd=target, check=True)
        subprocess.run(['git', 'apply', str(Path(override).resolve())], cwd=target, check=True)
    return names, baseline


if __name__ == '__main__':
    media_continuation_runner.reconstruct = reconstruct
    media_continuation_runner.main()
