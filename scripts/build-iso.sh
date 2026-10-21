#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 && -f /etc/arch-release ]] || { echo 'Build on Arch Linux as root'; exit 1; }
src=$(cd -- "$(dirname -- "$0")/.." && pwd)
build=${1:-/var/tmp/arch-graphical-build}
[[ ! -e "$build" ]] || { echo 'Build directory must not exist'; exit 1; }
pacman -S --needed --noconfirm archiso
mkdir -p "$build"
cp -a /usr/share/archiso/configs/releng "$build/profile"
profile="$build/profile"
cat "$src/iso/packages.extra" >> "$profile/packages.x86_64"
sort -u -o "$profile/packages.x86_64" "$profile/packages.x86_64"
app="$profile/airootfs/usr/lib/arch-graphical-installer"
mkdir -p "$app" "$profile/airootfs/usr/bin" "$profile/airootfs/usr/share/applications" "$profile/airootfs/etc/skel/.config/autostart" "$profile/airootfs/etc/polkit-1/rules.d"
cp -r "$src/arch_installer" "$app/"
cp "$src/main.py" "$src/helper.py" "$app/"
install -m 755 "$src/scripts/arch-graphical-installer" "$profile/airootfs/usr/bin/arch-graphical-installer"
cp "$src/assets/arch-graphical-installer.desktop" "$profile/airootfs/usr/share/applications/"
cp "$src/assets/arch-graphical-installer.desktop" "$profile/airootfs/etc/skel/.config/autostart/"
cp "$src/iso/49-live-installer.rules" "$profile/airootfs/etc/polkit-1/rules.d/"
mkdir -p "$profile/airootfs/etc/pacman.d/hooks" "$profile/airootfs/usr/local/bin"
install -m 755 "$src/iso/customize.fragment.sh" "$profile/airootfs/usr/local/bin/prepare-installer-live"
cat > "$profile/airootfs/etc/pacman.d/hooks/20-installer-live.hook" <<'EOF'
[Trigger]
Operation = Install
Type = Package
Target = base
[Action]
Description = Preparing graphical installer live user
When = PostTransaction
Depends = shadow
Exec = /usr/local/bin/prepare-installer-live
EOF
mkdir -p "$profile/airootfs/etc/systemd/system/multi-user.target.wants"
ln -sf /usr/lib/systemd/system/NetworkManager.service "$profile/airootfs/etc/systemd/system/multi-user.target.wants/NetworkManager.service"
# Releng may enable conflicting network daemons; prevent competing DHCP clients.
for unit in systemd-networkd.service systemd-networkd.socket systemd-resolved.service iwd.service; do
  ln -sf /dev/null "$profile/airootfs/etc/systemd/system/$unit"
done
ln -sf /run/NetworkManager/resolv.conf "$profile/airootfs/etc/resolv.conf"
mkdir -p "$profile/airootfs/etc/systemd/system/getty@tty1.service.d"
cat > "$profile/airootfs/etc/systemd/system/getty@tty1.service.d/autologin.conf" <<'EOF'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin live --noclear %I $TERM
EOF
cat > "$profile/airootfs/etc/skel/.bash_profile" <<'EOF'
if [[ -z ${DISPLAY:-} && $(tty) == /dev/tty1 ]]; then
  exec startx
fi
EOF
cat > "$profile/airootfs/etc/skel/.xinitrc" <<'EOF'
#!/bin/sh
/usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1 &
exec startxfce4
EOF
# Archiso enforces file modes from profiledef.sh.
cat >> "$profile/profiledef.sh" <<'EOF'
file_permissions+=(
  ["/usr/bin/arch-graphical-installer"]="0:0:755"
  ["/etc/skel/.xinitrc"]="0:0:755"
  ["/usr/local/bin/prepare-installer-live"]="0:0:755"
)
EOF
mkarchiso -v -w "$build/work" -o "$build/out" "$profile"
echo "ISO: $build/out"
