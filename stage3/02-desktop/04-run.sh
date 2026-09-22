#!/bin/bash -eu
install -d "${ROOTFS_DIR}/usr/local/bin"
# Import-based host tests may leave __pycache__ beside the Python helpers.
# Install named helper files only, so generated directories never enter an image.
for helper in files/bin/mixpi-*; do
    [ -f "${helper}" ] || continue
    install -m 755 "${helper}" "${ROOTFS_DIR}/usr/local/bin/"
done
install -d "${ROOTFS_DIR}/usr/local/sbin" "${ROOTFS_DIR}/etc/ssh/sshd_config.d"
install -m 755 files/ssh/mixpi-import-ssh-key "${ROOTFS_DIR}/usr/local/sbin/"
install -m 644 files/ssh/20-mixpi-key-only.conf "${ROOTFS_DIR}/etc/ssh/sshd_config.d/"
install -m 644 files/ssh/mixpi-ssh-key.service "${ROOTFS_DIR}/etc/systemd/system/"

# These are directories on the existing SD root filesystem. rpi-resize keeps
# expanding rootfs into the card's free space; no live repartitioning is needed.
install -d -m 755 "${ROOTFS_DIR}/home/pi/Music/Backup" "${ROOTFS_DIR}/media/SD-Backup" "${ROOTFS_DIR}/media/pi"
ln -sfn /media/SD-Backup "${ROOTFS_DIR}/home/pi/Music/Rekordbox"
on_chroot <<'EOF'
    chown -R pi:pi /home/pi/Music /media/SD-Backup
    chown pi:pi /media/pi
    systemctl enable bluetooth.service hciuart.service avahi-daemon.service
    systemctl enable mixpi-ssh-key.service
EOF
