#!/bin/bash -e
# Shared package recipe. Both pi-gen and mixxx-deb.yml execute this file so
# patch order, dependency setup, cmake flags and packaging cannot drift.
MIXXX_PATCHES=(
    mixxx-gcc14-djinterop.patch
    mixxx-media-hotplug.patch
    mixxx-readahead.patch
    mixxx-removable-ram-cache.patch
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

## Build Mixxx in the image rootfs.
mkdir -p "${BASE_DIR}/.ccache/" "${ROOTFS_DIR}/ccache" "${ROOTFS_DIR}/opt/mixxx-patches"
mount --bind "${BASE_DIR}/.ccache" "${ROOTFS_DIR}/ccache"
for patch in "${MIXXX_PATCHES[@]}"; do
    install -m 644 "files/$patch" "${ROOTFS_DIR}/opt/mixxx-patches/$patch"
done
install -m 644 01-run.sh "${ROOTFS_DIR}/opt/mixpi-build-mixxx.sh"
on_chroot << EOF
    export MIXXX_REF="${MIXXX_REF}"
    export MIXXX_COMMIT="${MIXXX_COMMIT}"
    bash /opt/mixpi-build-mixxx.sh --mixxx-package /opt/mixxx-patches /code /ccache
EOF

unmount "${ROOTFS_DIR}/ccache"
mkdir -p "$DEPLOY_DIR"
cp "${ROOTFS_DIR}"/code/build/*.deb "$DEPLOY_DIR/"
rm -rf "${ROOTFS_DIR}/code/"
