#!/bin/bash
set -euo pipefail
# Run on Linux with g++, pkg-config, Qt6Core development files and python3.
# Never share the fixed production cache directory with a live Mixxx process.
root=$(cd "$(dirname "$0")/../.." && pwd)
test "$(uname -s)" = Linux
if pgrep -x mixxx >/dev/null || [ -e /dev/shm/mixpi-track-cache ]; then
    echo 'Stop Mixxx and use a host without an existing track cache for this test.' >&2
    exit 1
fi
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"; rmdir /dev/shm/mixpi-track-cache 2>/dev/null || true' EXIT
python3 - "$root/stage3/01-install-packages/files/mixxx-removable-ram-cache.patch" "$scratch/removabletrackcache.h" <<'PY'
import pathlib,sys
patch=pathlib.Path(sys.argv[1]).read_text()
section=patch.split('+++ b/src/sources/removabletrackcache.h\n',1)[1]
lines=section.splitlines()[1:]
assert all(line.startswith('+') for line in lines)
pathlib.Path(sys.argv[2]).write_text('\n'.join(line[1:] for line in lines)+'\n')
PY
g++ -std=c++17 -Wall -Wextra -Werror -pthread -fPIC -I"$scratch" \
    "$root/tools/performance/ram-cache-smoke.cpp" $(pkg-config --cflags --libs Qt6Core) \
    -o "$scratch/cache-smoke"
"$scratch/cache-smoke"
