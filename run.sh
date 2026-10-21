#!/usr/bin/env bash
# One-command setup of the disposable Arch Live environment and graphical installer.
set -Eeuo pipefail
umask 022

usage() {
  cat <<'EOF'
Użycie: bash run.sh

Uruchom jako root w Arch Linux Live ISO, z działającym internetem.
Skrypt instaluje zależności, konfiguruje NetworkManager, Xorg, Xfce,
LightDM i polkit, a następnie otwiera graficzny instalator.
Nie partycjonuje ani nie formatuje dysków. Instalację zatwierdzasz w GUI.
EOF
}

if [[ ${1:-} == --help || ${1:-} == -h ]]; then
  usage
  exit 0
fi
if (( $# )); then
  usage >&2
  exit 2
fi

fail() { printf '\nBŁĄD: %s\n' "$*" >&2; exit 1; }
trap 'printf "\nPrzygotowanie przerwane (wiersz %s). Instalator nie został uruchomiony.\n" "$LINENO" >&2' ERR

[[ $(uname -s) == Linux && -f /etc/arch-release && -d /run/archiso ]] ||
  fail 'Ten skrypt uruchamiaj w Arch Linux Live ISO.'
[[ $EUID -eq 0 ]] || fail 'Uruchom: sudo bash run.sh (na oficjalnym ISO jesteś już rootem).'
[[ $(uname -m) == x86_64 ]] || fail 'Wymagana architektura x86_64.'
if [[ -d /sys/firmware/efi ]]; then
  printf 'Wykryto firmware: UEFI.\n'
else
  printf 'Wykryto firmware: Legacy BIOS — instalator wybierze GRUB i partycję BIOS Boot.\n'
fi
[[ -d /run/systemd/system ]] || fail 'Wymagana działająca sesja systemd Live ISO.'

src=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
for file in scripts/install-live.sh scripts/live-space.sh main.py helper.py arch_installer/gui.py assets/arch-graphical-installer.desktop iso/49-live-installer.rules; do
  [[ -f "$src/$file" ]] || fail "Brakuje pliku repozytorium: $file. Pobierz całe repozytorium."
done

live_user=agi-live
if id "$live_user" >/dev/null 2>&1; then
  [[ $(getent passwd "$live_user" | cut -d: -f5) == 'Arch Graphical Installer Live' ]] ||
    fail "Konto $live_user już istnieje i nie należy do tego skryptu."
fi

online() {
  curl --fail --silent --location --max-time 20 --output /dev/null \
    https://geo.mirror.pkgbuild.com/core/os/x86_64/core.db
}

printf '\n[1/5] Sprawdzanie połączenia i synchronizacja czasu…\n'
command -v curl >/dev/null || fail 'Brak curl; użyj aktualnego oficjalnego Arch ISO.'
timedatectl set-ntp true
online || fail 'Brak dostępu do repozytorium Arch. Podłącz Ethernet albo skonfiguruj Wi-Fi przez iwctl, a potem ponów bash run.sh.'

printf '\n[2/5] Aktualizacja Live ISO i instalacja wszystkich zależności…\n'
bash "$src/scripts/install-live.sh"
/usr/bin/python -I -c 'from PySide6.QtWidgets import QApplication'

printf '\n[3/5] Konfiguracja sieci NetworkManager…\n'
# The stock ISO uses networkd/iwd; do not leave competing network managers running.
for unit in systemd-networkd.service systemd-networkd.socket systemd-networkd-wait-online.service systemd-resolved.service iwd.service; do
  if systemctl cat "$unit" >/dev/null 2>&1; then
    systemctl mask --runtime --now "$unit"
  fi
done
install -d -m 755 /etc/NetworkManager/conf.d
cat > /etc/NetworkManager/conf.d/90-arch-installer.conf <<'EOF'
[main]
dns=default
[device]
wifi.backend=wpa_supplicant
EOF
ln -sfn /run/NetworkManager/resolv.conf /etc/resolv.conf
systemctl restart NetworkManager
nmcli networking on
nmcli radio wifi on || true
connected=false
for attempt in 1 2 3; do
  if online; then connected=true; break; fi
  sleep 2
done
if [[ $connected != true ]]; then
  printf '\nPo zmianie menedżera sieci połącz Wi-Fi ponownie. Otwieram wybór połączenia…\n'
  [[ -t 0 && -t 1 ]] || fail 'Uruchom nmtui-connect w terminalu, połącz sieć i ponów bash run.sh.'
  nmtui-connect
  online || fail 'Repozytorium nadal niedostępne. Sprawdź połączenie przez nmtui-connect.'
fi

printf '\n[4/5] Przygotowanie pulpitu Xfce, autologowania i uprawnień helpera…\n'
getent group autologin >/dev/null || groupadd --system autologin
if ! id "$live_user" >/dev/null 2>&1; then
  useradd --create-home --user-group --groups autologin --shell /bin/bash \
    --comment 'Arch Graphical Installer Live' "$live_user"
else
  usermod --append --groups autologin "$live_user"
fi
# This locked, dedicated live account is never copied to the installed OS.
install -d -m 755 /etc/lightdm/lightdm.conf.d /etc/xdg/autostart /etc/polkit-1/rules.d
cat > /etc/lightdm/lightdm.conf.d/90-arch-installer.conf <<'EOF'
[Seat:*]
greeter-session=lightdm-gtk-greeter
session-wrapper=/etc/lightdm/Xsession
user-session=xfce
autologin-user=agi-live
autologin-user-timeout=0
autologin-session=xfce
allow-guest=false
EOF
install -m 644 "$src/assets/arch-graphical-installer.desktop" \
  /etc/xdg/autostart/arch-graphical-installer.desktop
cat > /etc/xdg/autostart/arch-installer-polkit.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=Installer authentication agent
Exec=/usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1
OnlyShowIn=XFCE;
EOF
sed 's/subject.user === "live"/subject.user === "agi-live"/' \
  "$src/iso/49-live-installer.rules" > /etc/polkit-1/rules.d/49-arch-installer-live.rules
chmod 644 /etc/polkit-1/rules.d/49-arch-installer-live.rules
[[ -f /usr/share/xsessions/xfce.desktop && -x /etc/lightdm/Xsession ]] ||
  fail 'Brakuje sesji Xfce lub wrappera LightDM.'
systemctl start polkit

printf '\n[5/5] Uruchamianie pulpitu i instalatora…\n'
if systemctl is-active --quiet lightdm; then
  printf 'LightDM już działa. Otwórz „Zainstaluj Arch Linux” z menu pulpitu.\n'
else
  systemctl start lightdm
fi
systemctl is-active --quiet lightdm || fail 'LightDM nie wystartował. Sprawdź: journalctl -u lightdm -b'
printf '\nGotowe. Na pulpicie otworzy się instalator. Zmiany na dyskach wymagają zatwierdzenia w jego oknie.\n'
