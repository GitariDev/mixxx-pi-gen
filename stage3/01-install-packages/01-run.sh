#!/bin/bash -e
# Shared package recipe. Both pi-gen and mixxx-deb.yml execute this file so
# patch order, dependency setup, cmake flags and packaging cannot drift.
MIXXX_PATCHES=(
    mixxx-gcc14-djinterop.patch
    mixxx-media-hotplug.patch
    mixxx-readahead.patch
    mixxx-removable-ram-cache.patch
    mixxx-sidebar-sources.patch
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

if [ "${1:-}" = --mixxx-package ]; then
    set -euo pipefail
    patch_dir="${2:?patch directory required}"
    source_dir="${3:-/code}"
    export CCACHE_DIR="${4:-/ccache}"
    : "${MIXXX_REF:?source-versions must be sourced}"
    : "${MIXXX_COMMIT:?source-versions must be sourced}"
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
    git rev-parse HEAD > /opt/mixxx.version
    git describe --tags --always > /opt/mixxx.tag
    ccache -M 10G
    export CCACHE_NOCOMPRESS=true
    export CTEST_PARALLEL_LEVEL="$(nproc)"
    export CMAKE_BUILD_PARALLEL_LEVEL="$(nproc)"
    export PATH="$HOME/.local/bin:$PATH"
    export GTEST_COLOR=1
    export CTEST_OUTPUT_ON_FAILURE=1
    export QT_QPA_PLATFORM=offscreen
    cmake "${MIXXX_CMAKE_FLAGS[@]}" -S "$source_dir" -B "$source_dir/build"
    cmake --build "$source_dir/build" --target install
    ccache -s
    cd "$source_dir/build"
    cpack -G DEB
    exit 0
fi

# Compile in a disposable copy. Build dependencies and the unowned CMake
# installation must never enter the runtime image.
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
install -m 644 01-run.sh "$build_root/opt/mixpi-build-mixxx.sh"
ROOTFS_DIR="$build_root" on_chroot << EOF
    export MIXXX_REF="${MIXXX_REF}"
    export MIXXX_COMMIT="${MIXXX_COMMIT}"
    bash /opt/mixpi-build-mixxx.sh --mixxx-package /opt/mixxx-patches /code /ccache
EOF

mkdir -p "$DEPLOY_DIR" "${ROOTFS_DIR}/opt/mixxx-package" "${ROOTFS_DIR}/opt/mixxx-patches"
cp "$build_root"/code/build/*.deb "$DEPLOY_DIR/"
cp "$build_root"/code/build/*.deb "${ROOTFS_DIR}/opt/mixxx-package/"
cp "$build_root"/opt/mixxx.version "$build_root"/opt/mixxx.tag "${ROOTFS_DIR}/opt/"
cp "$build_root"/opt/mixxx-patches/*.patch "${ROOTFS_DIR}/opt/mixxx-patches/"
# apt installs the package's runtime dependencies and gives dpkg ownership of
# /usr/bin/mixxx. /opt is used because on_chroot mounts a fresh tmpfs on /tmp.
on_chroot <<'EOF'
    apt-get update
    apt-get install -y --no-install-recommends /opt/mixxx-package/*.deb
    dpkg-query -S /usr/bin/mixxx
    rm -rf /opt/mixxx-package
EOF
cleanup_build
trap - EXIT
rm -rf "$build_root"
