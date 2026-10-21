#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 && -d /run/archiso ]] || { echo 'Run as root inside Arch Live ISO'; exit 1; }
src=$(cd -- "$(dirname -- "$0")/.." && pwd)
pacman -Syu --needed --noconfirm python pyside6 arch-install-scripts gptfdisk parted dosfstools e2fsprogs pciutils usbutils networkmanager nm-connection-editor polkit polkit-gnome xorg-server xorg-xinit xfce4 xfce4-terminal sudo
install -d -m 755 /usr/lib/arch-graphical-installer /usr/share/applications
cp -r -- "$src/arch_installer" /usr/lib/arch-graphical-installer/
install -m 644 "$src/helper.py" "$src/main.py" /usr/lib/arch-graphical-installer/
chown -R root:root /usr/lib/arch-graphical-installer
chmod -R go-w /usr/lib/arch-graphical-installer
install -m 755 "$src/scripts/arch-graphical-installer" /usr/bin/arch-graphical-installer
install -m 644 "$src/assets/arch-graphical-installer.desktop" /usr/share/applications/
systemctl start NetworkManager
echo 'Launch arch-graphical-installer from a regular user graphical session with a polkit authentication agent.'
