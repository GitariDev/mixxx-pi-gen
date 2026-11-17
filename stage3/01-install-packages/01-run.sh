#!/bin/bash -e
# Shared package recipe. Both pi-gen and mixxx-deb.yml execute this file so
# patch order, dependency setup, cmake flags and packaging cannot drift.
MIXXX_PATCHES=(
    mixxx-gcc14-djinterop.patch
    mixxx-media-hotplug.patch
    mixxx-readahead.patch
    mixxx-removable-ram-cache.patch
    mixxx-sidebar-sources.patch
    mixxx-touch-source-navigation.patch
    mixxx-performance-settings.patch
    mixxx-effect-placeholder.patch
    mixxx-right-overlay.patch
    mixxx-media-selection.patch
    mixxx-library-interface.patch
    mixxx-recording-lifecycle.patch
    mixxx-initial-library.patch
    mixxx-media-continuation.patch
    mixxx-analysis-safety.patch
    mixxx-media-activity.patch
    mixxx-import-cancellation.patch
    mixxx-transfer-reporting.patch
    mixxx-transfer-display.patch
    mixxx-quiet-scan.patch
    mixxx-preferences-entry.patch
    mixxx-position-display.patch
    mixxx-dialog-wording.patch
    mixxx-source-tap.patch
    mixxx-table-columns.patch
    mixxx-touch-dialogs.patch
    mixxx-bpm-lock-touch.patch
    mixxx-acceptance-fixes.patch
    mixxx-council-fixes.patch
    mixxx-clean-quit.patch
    mixxx-save-on-change.patch
    mixxx-sources-screen.patch
    mixxx-scan-progress.patch
)
MIXXX_CMAKE_FLAGS=(
    -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF -DBUILD_BENCH=OFF
    -DKEYFINDER=ON -DFFMPEG=ON -DMAD=ON -DMODPLUG=ON -DWAVPACK=ON -DBULK=ON
    -DCMAKE_INSTALL_PREFIX=/usr/
)

# Also consumed by the patch-application unittest.
if [ "${1:-}" = --mixxx-print-patches ]; then
    printf '%s\n' "${MIXXX_PATCHES[@]}"
    exit 0
fi

if [[ -n "${!MIXPI_ARTIFACT_*}" ]]; then
    set -euo pipefail
    test -z "${1:-}" || { echo 'Artifact image mode cannot build a package' >&2; exit 1; }
    artifact_helper="${BASE_DIR}/tools/performance/accepted-artifact.py"
    python3 "$artifact_helper" prepare
    on_chroot <<'EOF'
    set -eu
    test "$(dpkg --print-architecture)" = arm64
    if dpkg-query -W -f='${db:Status-Status}' mixxx 2>/dev/null; then
        echo 'Refusing preexisting Mixxx package state' >&2
        exit 1
    fi
    apt-get update
    apt-get install -y --no-install-recommends /opt/mixxx-package/candidate.deb
    test "$(dpkg-query -W -f='${Status} ${Architecture} ${Version}' mixxx)" = 'install ok installed arm64 2.5.6+rmodified-1'
    test "$(dpkg-query -S /usr/bin/mixxx)" = 'mixxx: /usr/bin/mixxx'
    test -z "$(dpkg --audit)"
    apt-get check
EOF
    python3 "$artifact_helper" installed
    exit 0
fi

set -euo pipefail
recipe_path="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
recipe_root="$(cd "$(dirname "$recipe_path")/../.." && pwd)"
candidate_helper="$recipe_root/tools/performance/mixxx-candidate.py"
test -r "$candidate_helper" || { echo "Missing candidate helper: $candidate_helper" >&2; exit 1; }
test -r "$recipe_root/source-versions" || { echo 'Missing source-versions input' >&2; exit 1; }
resource_environment="$(python3 "$candidate_helper" resources)"
eval "$resource_environment"

if [ "${1:-}" = --mixxx-package ]; then
    set -euo pipefail
    patch_dir="${2:?patch directory required}"
    source_dir="${3:-/code}"
    export CCACHE_DIR="${4:-/ccache}"
    : "${MIXXX_REF:?source-versions must be sourced}"
    : "${MIXXX_COMMIT:?source-versions must be sourced}"
    patch_dir="$(cd "$patch_dir" && pwd)"
    source_dir="$(python3 -c 'import os, sys; print(os.path.abspath(sys.argv[1]))' "$source_dir")"
    for patch in "${MIXXX_PATCHES[@]}"; do
        test -r "$patch_dir/$patch"
    done
    git clone --depth 1 --branch "$MIXXX_REF" https://github.com/mixxxdj/mixxx.git "$source_dir"
    cd "$source_dir"
    test "$(git rev-parse HEAD)" = "$MIXXX_COMMIT"
    for patch in "${MIXXX_PATCHES[@]}"; do
        git apply --check "$patch_dir/$patch"
        git apply "$patch_dir/$patch"
    done
    # The pinned upstream setup script references this under nounset.
    export FONTS_UBUNTU_AVAILABLE=false
    tools/debian_buildenv.sh setup
    if [ -n "${MIXXX_CACHE_SMOKE_SCRIPT:-}" ]; then
        bash "$MIXXX_CACHE_SMOKE_SCRIPT"
    fi
    if [ -n "${MIXXX_TOUCH_SMOKE_SCRIPT:-}" ]; then
        bash "$MIXXX_TOUCH_SMOKE_SCRIPT"
    fi
    git rev-parse HEAD > /opt/mixxx.version
    git describe --tags --always > /opt/mixxx.tag
    ccache -M "$CCACHE_MAXSIZE"
    ccache -o "compression=$MIXXX_CCACHE_COMPRESSION" -o "compression_level=$CCACHE_COMPRESSLEVEL"
    ccache -o hard_link=false -o file_clone=false
    export PATH="$HOME/.local/bin:$PATH"
    export GTEST_COLOR=1
    export CTEST_OUTPUT_ON_FAILURE=1
    export QT_QPA_PLATFORM=offscreen
    candidate_arguments=(prepare --source "$source_dir" --recipe "$recipe_path"
        --source-versions "$recipe_root/source-versions" --ref "$MIXXX_REF" --commit "$MIXXX_COMMIT")
    for patch in "${MIXXX_PATCHES[@]}"; do
        candidate_arguments+=(--patch "$patch_dir/$patch")
    done
    for flag in "${MIXXX_CMAKE_FLAGS[@]}"; do
        candidate_arguments+=("--cmake-flag=$flag")
    done
    python3 "$candidate_helper" "${candidate_arguments[@]}"
    cmake "${MIXXX_CMAKE_FLAGS[@]}" -S "$source_dir" -B "$source_dir/build"
    python3 "$candidate_helper" configured --output-dir "$source_dir/build"
    cmake --build "$source_dir/build" --target install
    ccache -s
    cd "$source_dir/build"
    cpack -G DEB
    python3 "$candidate_helper" emit --output-dir "$source_dir/build"
    python3 "$candidate_helper" verify --output-dir "$source_dir/build"
    exit 0
fi

# Compile in a disposable copy. Build dependencies and the unowned CMake
# installation must never enter the runtime image.
for output_dir in "$DEPLOY_DIR" "${ROOTFS_DIR}/opt/mixxx-package"; do
    test ! -L "$output_dir"
    for output in "$output_dir"/*.deb "$output_dir"/*.candidate.json; do
        if [ -e "$output" ] || [ -L "$output" ]; then
            echo "Refusing stale package output: $output" >&2
            exit 1
        fi
    done
done
test ! -e "${ROOTFS_DIR}/opt/mixxx.candidate.json"
test ! -L "${ROOTFS_DIR}/opt/mixxx.candidate.json"
build_root=$(mktemp -d "${STAGE_WORK_DIR}/mixxx-build.XXXXXX")
cleanup_build() {
    unmount "$build_root"
}
trap cleanup_build EXIT
rsync -aHAXx --exclude '/dev/*' --exclude '/proc/*' --exclude '/sys/*' \
    --exclude '/run/*' --exclude '/tmp/*' --exclude '/ccache/*' \
    --exclude '/var/cache/apt/archives/*' "${ROOTFS_DIR}/" "$build_root/"
mkdir -p "${BASE_DIR}/.ccache/" "$build_root/ccache" "$build_root/opt/mixxx-patches"
mount --bind "${BASE_DIR}/.ccache" "$build_root/ccache"
for patch in "${MIXXX_PATCHES[@]}"; do
    install -m 644 "files/$patch" "$build_root/opt/mixxx-patches/$patch"
done
build_inputs="$build_root/opt/mixpi-build-inputs"
install -d "$build_inputs/stage3/01-install-packages" "$build_inputs/tools/performance"
install -m 644 "$recipe_path" "$build_inputs/stage3/01-install-packages/01-run.sh"
install -m 644 "$candidate_helper" "$build_inputs/tools/performance/mixxx-candidate.py"
install -m 644 "$recipe_root/source-versions" "$build_inputs/source-versions"
ROOTFS_DIR="$build_root" on_chroot << EOF
    export MIXXX_REF="${MIXXX_REF}"
    export MIXXX_COMMIT="${MIXXX_COMMIT}"
    $resource_environment
    bash /opt/mixpi-build-inputs/stage3/01-install-packages/01-run.sh --mixxx-package /opt/mixxx-patches /code /ccache
EOF

mkdir -p "$DEPLOY_DIR" "${ROOTFS_DIR}/opt/mixxx-package" "${ROOTFS_DIR}/opt/mixxx-patches"
cp "$build_root"/code/build/*.deb "$DEPLOY_DIR/"
cp "$build_root"/code/build/*.deb "${ROOTFS_DIR}/opt/mixxx-package/"
cp "$build_root"/code/build/*.deb.candidate.json "$DEPLOY_DIR/"
cp "$build_root"/code/build/*.deb.candidate.json "${ROOTFS_DIR}/opt/mixxx-package/"
python3 "$candidate_helper" verify --output-dir "$DEPLOY_DIR"
install -m 644 "$candidate_helper" "${ROOTFS_DIR}/opt/mixxx-package/mixxx-candidate.py"
cp "$build_root"/opt/mixxx.version "$build_root"/opt/mixxx.tag "${ROOTFS_DIR}/opt/"
cp "$build_root"/opt/mixxx-patches/*.patch "${ROOTFS_DIR}/opt/mixxx-patches/"
# apt installs the package's runtime dependencies and gives dpkg ownership of
# /usr/bin/mixxx. /opt is used because on_chroot mounts a fresh tmpfs on /tmp.
on_chroot <<'EOF'
    set -eu
    python3 /opt/mixxx-package/mixxx-candidate.py verify --output-dir /opt/mixxx-package
    apt-get update
    apt-get install -y --no-install-recommends /opt/mixxx-package/*.deb
    dpkg-query -S /usr/bin/mixxx
    python3 /opt/mixxx-package/mixxx-candidate.py verify --output-dir /opt/mixxx-package --installed /usr/bin/mixxx
    cp /opt/mixxx-package/*.deb.candidate.json /opt/mixxx.candidate.json
    rm -rf /opt/mixxx-package
EOF
cleanup_build
trap - EXIT
rm -rf "$build_root"
