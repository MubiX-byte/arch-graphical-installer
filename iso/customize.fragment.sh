#!/usr/bin/env bash
set -euo pipefail
# Arch Graphical Installer live desktop account; never copied to installed system.
useradd -m -s /bin/bash live
passwd -d live
chown -R root:root /usr/lib/arch-graphical-installer
chmod -R go-w /usr/lib/arch-graphical-installer
systemctl enable NetworkManager
