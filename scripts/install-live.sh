#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 && -d /run/archiso ]] || { echo 'Run as root inside Arch Live ISO'; exit 1; }
src=$(cd -- "$(dirname -- "$0")/.." && pwd)
source "$src/scripts/live-space.sh"
packages=(python pyside6 arch-install-scripts gptfdisk parted dosfstools e2fsprogs
  pciutils usbutils networkmanager nm-connection-editor wpa_supplicant polkit polkit-gnome
  xorg-server xorg-xinit xfce4 xfce4-terminal lightdm lightdm-gtk-greeter mesa noto-fonts curl sudo)
# First reserve enough room for repository databases, then resolve the complete
# upgrade without installing anything. Keep pacman's own disk-space check enabled.
live_ensure_space $((128 * 1024**2))
LC_ALL=C pacman -Sy --noconfirm
transaction=$(LC_ALL=C pacman -Sup --needed --noconfirm --print-format '%r/%n %s' "${packages[@]}")
pending=()
download=0
while read -r package bytes extra; do
  [[ -n $package ]] || continue
  [[ $package =~ ^[a-zA-Z0-9_.+-]+/[a-zA-Z0-9@_.+-]+$ && $bytes =~ ^[0-9]+$ && -z $extra ]] || {
    live_space_error 'Nie można odczytać planu transakcji pacman; nie instaluję pakietów.'
    exit 1
  }
  pending+=("$package")
  download=$((download + bytes))
done <<< "$transaction"
required=$((64 * 1024**2))
if (( ${#pending[@]} )); then
  installed=$(LC_ALL=C pacman -Si -- "${pending[@]}" | live_installed_bytes "${#pending[@]}")
  # Full installed sizes (not net upgrade size) account for overlay copy-up.
  # Include downloads plus 512 MiB for databases, hooks and temporary files.
  required=$((installed + download + 512 * 1024**2))
fi
printf 'Plan Live: %s pakietów, %s MiB miejsca na transakcję.\n' "${#pending[@]}" "$(((required + 1024**2 - 1) / 1024**2))"
live_ensure_space "$required"
LC_ALL=C pacman -Su --needed --noconfirm "${packages[@]}"
install -d -m 755 /usr/lib/arch-graphical-installer /usr/share/applications
cp -r -- "$src/arch_installer" /usr/lib/arch-graphical-installer/
install -m 644 "$src/helper.py" "$src/main.py" /usr/lib/arch-graphical-installer/
chown -R root:root /usr/lib/arch-graphical-installer
chmod -R go-w /usr/lib/arch-graphical-installer
install -m 755 "$src/scripts/arch-graphical-installer" /usr/bin/arch-graphical-installer
install -m 644 "$src/assets/arch-graphical-installer.desktop" /usr/share/applications/
echo 'Dependencies installed. The run.sh entry point configures networking and starts the graphical session.'
