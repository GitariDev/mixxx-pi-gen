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
