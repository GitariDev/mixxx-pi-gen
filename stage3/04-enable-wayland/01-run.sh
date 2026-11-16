# Sway is our Wayland session. Configure LightDM directly: raspi-config's
# desktop toggles configure Labwc/Wayfire and require the retired UI meta.
on_chroot << EOF
	systemctl enable lightdm.service
EOF

# Remove cups
on_chroot << EOF
    apt-get purge -y cups cups-common system-config-printer printer-driver-* pocketsphinx-* pi-printer-support
    apt-get autoremove -y
EOF

# Mask pipewire services
on_chroot << EOF
    systemctl mask pipewire
    systemctl mask pipewire-pulse
    systemctl mask wireplumber
    systemctl mask --global pipewire
    systemctl mask --global pipewire-pulse
    systemctl mask --global wireplumber
    mkdir -p /home/pi/.config/systemd/user/
    ln -sf /dev/null /home/pi/.config/systemd/user/pipewire.service
    ln -sf /dev/null /home/pi/.config/systemd/user/pipewire.socket
    ln -sf /dev/null /home/pi/.config/systemd/user/pipewire-pulse.service
    ln -sf /dev/null /home/pi/.config/systemd/user/pipewire-pulse.socket
    ln -sf /dev/null /home/pi/.config/systemd/user/wireplumber.service
    ln -sf /dev/null /home/pi/.config/systemd/user/pulseaudio.service
    ln -sf /dev/null /home/pi/.config/systemd/user/pulseaudio.socket
EOF

# The top bar starts hidden after boot (owner decision, F-14). The waybar
# package enables waybar.service for graphical-session.target; undo that.
# Settings > "Show top bar" starts it on demand (mixpi-desktop-bar).
on_chroot << EOF
    systemctl --global disable waybar.service
EOF

# Appliance quieting, Tier 1 (F-13). There is no modem. ModemManager comes in
# as a Recommends of network-manager (stage2/02-net-tweaks/00-packages); keeping
# it out would mean installing network-manager without its other Recommends
# (wpasupplicant, wireless-regdb), so mask the unit instead.
# Nothing uses footclient (Settings and $term run plain `foot`), so the
# foot-server socket and service the foot package enables are not needed.
on_chroot << EOF
    systemctl mask ModemManager.service
    systemctl --global disable foot-server.socket foot-server.service
EOF
