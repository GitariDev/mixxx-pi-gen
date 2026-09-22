#!/bin/bash -eu
set -o pipefail
# Copy fixed revisions without installing source repositories into the image.
skin_sources=$(mktemp -d)
trap 'rm -rf "$skin_sources"' EXIT

fetch_skin() {
    git init -q "$skin_sources/$1"
    git -C "$skin_sources/$1" fetch -q --depth 1 "$2" "$3"
    git -C "$skin_sources/$1" checkout -q --detach FETCH_HEAD
    test "$(git -C "$skin_sources/$1" rev-parse HEAD)" = "$3"
}

fetch_skin pi_dj https://github.com/dennisdebel/pi_dj.git "$PI_DJ_COMMIT"
cp -r "$skin_sources/pi_dj/mixxx/skin/." "${ROOTFS_DIR}/usr/share/mixxx/skins/"

fetch_skin Pioneered https://github.com/timewasternl/Pioneered.git "$PIONEERED_COMMIT"
mkdir -p "${ROOTFS_DIR}/usr/share/mixxx/skins/Pioneered"
git -C "$skin_sources/Pioneered" archive HEAD | tar -x -C "${ROOTFS_DIR}/usr/share/mixxx/skins/Pioneered"
install -d "${ROOTFS_DIR}/opt/mixpi-skin-tools"
install -m 644 files/pioneered-touch.py files/pioneered-touch.qss files/pioneered-menus.qss \
    "${ROOTFS_DIR}/opt/mixpi-skin-tools/"
on_chroot <<'EOF'
python3 /opt/mixpi-skin-tools/pioneered-touch.py /usr/share/mixxx/skins/Pioneered
EOF
printf '%s\n' "$PIONEERED_COMMIT" > "${ROOTFS_DIR}/opt/pioneered.version"
printf '%s\n' "$PI_DJ_COMMIT" > "${ROOTFS_DIR}/opt/pi-dj.version"
