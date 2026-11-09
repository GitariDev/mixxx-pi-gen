#!/bin/bash
set -euo pipefail
# Runs the exact Qt tree-navigation helper from the patch in an offscreen
# process. It has no audio, profile, USB or production-cache access.
root=$(cd "$(dirname "$0")/../.." && pwd)
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT
python3 - "$root/stage3/01-install-packages/files/mixxx-touch-source-navigation.patch" "$scratch/touchsourcenavigation.h" <<'PY'
import pathlib, sys
active = False
lines = []
for line in pathlib.Path(sys.argv[1]).read_text().splitlines():
    if line.startswith('diff --git '):
        active = line.endswith(' b/src/widget/touchsourcenavigation.h')
    elif active and line.startswith('+') and not line.startswith('+++'):
        lines.append(line[1:])
assert lines, 'Missing actual navigation helper in patch'
pathlib.Path(sys.argv[2]).write_text('\n'.join(lines) + '\n')
PY
c++ -std=c++17 -Wall -Wextra -Werror -fPIC -I"$scratch" \
    "$root/tools/performance/source-navigation-smoke.cpp" $(pkg-config --cflags --libs Qt6Widgets) \
    -o "$scratch/source-navigation-smoke"
QT_QPA_PLATFORM=offscreen "$scratch/source-navigation-smoke"
