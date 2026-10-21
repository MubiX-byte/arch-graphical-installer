#!/usr/bin/env bash
# Run inside the installed, rebooted VM. Does not modify storage.
set -euo pipefail
[[ -d /sys/firmware/efi ]] || { echo 'Not UEFI'; exit 1; }
[[ $(findmnt -n -o FSTYPE /) == ext4 ]] || { echo 'Root is not ext4'; exit 1; }
[[ $(findmnt -n -o FSTYPE /boot) == vfat ]] || { echo 'Missing mounted ESP'; exit 1; }
systemctl is-enabled NetworkManager
systemctl is-active NetworkManager
test -s /etc/locale.conf
test -s /etc/hostname
test -L /etc/localtime
grep -q '^UUID=' /etc/fstab
user=${1:-tester}
id "$user"
id -nG "$user" | tr ' ' '\n' | grep -qx wheel
sudo visudo -cf /etc/sudoers
sudo passwd -S root | grep -q ' L '
ls /boot/vmlinuz-* >/dev/null
echo 'Installed-system verification PASS. Also test desktop login, sudo, audio and DNS interactively.'
