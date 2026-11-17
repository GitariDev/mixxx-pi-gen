#!/bin/bash -eu
if [[ -n "${!MIXPI_ARTIFACT_*}" ]]; then
    set -euo pipefail
    python3 "${BASE_DIR}/tools/performance/accepted-artifact.py" desktop
fi
install -m 644 ../01-install-packages/files/mixpi-mount-broker.py "${ROOTFS_DIR}/opt/mixpi-skin-tools/"
install -m 755 files/bin/mixpi-mount-control "${ROOTFS_DIR}/usr/local/bin/"
install -m 644 files/systemd/mixpi-mount-broker.service "${ROOTFS_DIR}/etc/systemd/system/"
if [ "${MIXPI_CONTROLLED_MEDIA:-0}" = 1 ]; then
    install -d -m 755 "${ROOTFS_DIR}/etc/mixpi" "${ROOTFS_DIR}/etc/polkit-1/rules.d"
    printf 'v1\n' > "${ROOTFS_DIR}/etc/mixpi/controlled-media"
    install -m 644 files/49-mixpi-controlled-media.rules "${ROOTFS_DIR}/etc/polkit-1/rules.d/"
    printf 'user.max_user_namespaces=0\n' > "${ROOTFS_DIR}/etc/sysctl.d/90-mixpi-controlled-media.conf"
    printf 'pi ALL=(root) NOPASSWD: /usr/sbin/shutdown\n' > "${ROOTFS_DIR}/etc/sudoers.d/010_pi-nopasswd"
    chmod 440 "${ROOTFS_DIR}/etc/sudoers.d/010_pi-nopasswd"
    on_chroot <<'EOF'
systemctl mask udisks2.service
chown root:root /media/pi
chmod 0755 /media/pi
gpasswd -d pi sudo || test "$(id -nG pi | tr ' ' '\n' | grep -cx sudo)" = 0
if id -nG pi | tr ' ' '\n' | grep -qx disk; then gpasswd -d pi disk; fi
for executable in /usr/bin/udevil /bin/mount /bin/umount /usr/bin/fusermount /usr/bin/fusermount3 /usr/bin/ntfs-3g /usr/sbin/mount.cifs; do
    if [ -e "$executable" ]; then
        dpkg-statoverride --add root root 0755 "$executable"
        chmod 0755 "$executable"
    fi
done
systemctl enable mixpi-mount-broker.service
EOF
fi
# R-6: the eject gate (engine A, system eject through udisks2). Mixxx enables
# EJECT only when this root-owned, mode 644 file holds v1. Never by default.
if [ "${MIXPI_MEDIA_EJECT:-0}" = 1 ]; then
    install -d -m 755 "${ROOTFS_DIR}/etc/mixpi"
    printf 'v1\n' > "${ROOTFS_DIR}/etc/mixpi/media-eject"
    chmod 644 "${ROOTFS_DIR}/etc/mixpi/media-eject"
    if [ "$(id -u)" = 0 ]; then
        chown root:root "${ROOTFS_DIR}/etc/mixpi/media-eject"
    fi
    echo "media eject ON"
else
    rm -f "${ROOTFS_DIR}/etc/mixpi/media-eject"
    echo "media eject OFF"
fi
