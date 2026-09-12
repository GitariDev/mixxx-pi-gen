# Enable ssh.
# touch ${ROOTFS_DIR}/boot/ssh

# Boot to graphical by default
on_chroot << EOF
	systemctl set-default graphical.target
EOF

# LightDM handles graphical autologin in stage3/04-enable-wayland.
# There is no files/autologin.conf; a tty override is unnecessary here.

# Set up sudoers.d for user patch
rm -f ${ROOTFS_DIR}/etc/sudoers.d/010_pi-nopasswd
install -m 440 files/010_pi-nopasswd ${ROOTFS_DIR}/etc/sudoers.d/

echo pi - memlock unlimited >> ${ROOTFS_DIR}/etc/security/limits.conf
echo pi - rtprio 99 >> ${ROOTFS_DIR}/etc/security/limits.conf
