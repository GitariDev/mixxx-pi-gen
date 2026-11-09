# Add i3/sway config file
mkdir -p -m 755 ${ROOTFS_DIR}/home/pi/.config/sway/
install -m 644 files/i3.conf ${ROOTFS_DIR}/home/pi/.config/sway/config
mkdir -p -m 755 ${ROOTFS_DIR}/home/pi/.config/xdg-desktop-portal/
install -m 644 files/xdg-desktop-portal-sway.conf ${ROOTFS_DIR}/home/pi/.config/xdg-desktop-portal/sway-portals.conf
mkdir -p -m 755 ${ROOTFS_DIR}/home/pi/.config/systemd/user/
install -m 644 files/systemd/user/sway-session.service ${ROOTFS_DIR}/home/pi/.config/systemd/user/
install -m 644 files/systemd/user/sway-session.target ${ROOTFS_DIR}/home/pi/.config/systemd/user/
# Remove masks left by an earlier run of this stage, preserving real units.
for backend in gtk wlr; do
    unit="${ROOTFS_DIR}/home/pi/.config/systemd/user/xdg-desktop-portal-${backend}.service"
    if [ -L "$unit" ] && [ "$(readlink "$unit")" = /dev/null ]; then
        rm "$unit"
    fi
done
mkdir -p -m 755 ${ROOTFS_DIR}/home/pi/.config/sway/scripts/
install -m 755 files/sway/scripts/auto_exit_fullscreen.sh ${ROOTFS_DIR}/home/pi/.config/sway/scripts/
install -m 644 files/systemd/user/mixpi-* ${ROOTFS_DIR}/home/pi/.config/systemd/user/
cp -r files/wallpaper ${ROOTFS_DIR}/home/pi/
cp -r files/i3blocks ${ROOTFS_DIR}/home/pi/.config/
cp -r files/waybar  ${ROOTFS_DIR}/home/pi/.config/
on_chroot << EOF
    chown -R pi:root /home/pi/.config/
    chown -R pi:root /home/pi/wallpaper/
EOF
