#!/bin/bash -eu
# Pin the official ARM64 Raspotify package; the desktop uses its librespot
# binary through mixpi-spotify.service, only while Speaker mode is active.
on_chroot <<'EOF'
    set -eu
    package=/tmp/mixpi-raspotify.deb
    curl -fL --retry 3 'https://github.com/dtcooper/raspotify/releases/download/0.48.3/raspotify_0.48.3.librespot.v0.8.0-939dc5e_arm64.deb' -o "$package"
    echo '2097b3994824cf17163ecc47c6f6a5a695202987e2ab0b650f50d663291c63f2  /tmp/mixpi-raspotify.deb' | sha256sum -c -
    ln -sf /dev/null /etc/systemd/system/raspotify.service
    apt-get install -y "$package"
    rm "$package"
EOF
