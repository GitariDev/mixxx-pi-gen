#!/bin/bash -eu
# Pin the official ARM64 go-librespot release. mixpi-spotify.service runs it
# only while Speaker mode is active; its control API backs the Speaker screen's
# Spotify controls.
on_chroot <<'EOF'
    set -eu
    package=/tmp/mixpi-go-librespot.tar.gz
    curl -fL --retry 3 'https://github.com/devgianlu/go-librespot/releases/download/v0.10.3/go-librespot_linux_arm64.tar.gz' -o "$package"
    echo 'fdab3c06f3a776a3f696afb26aa59fbdea63557e24d3c39f2df2830ab1851a42  /tmp/mixpi-go-librespot.tar.gz' | sha256sum -c -
    tar -xzf "$package" -C /usr/local/bin --no-same-owner go-librespot
    chmod 755 /usr/local/bin/go-librespot
    rm "$package"
EOF
