#!/usr/bin/env bash
set -euo pipefail
mode=${1:-}
disk=${2:-}
ovmf=${OVMF_CODE:-/usr/share/edk2/x64/OVMF_CODE.4m.fd}
vars_template=${OVMF_VARS:-/usr/share/edk2/x64/OVMF_VARS.4m.fd}
firmware=${FIRMWARE:-uefi}
[[ "$mode" == install || "$mode" == boot ]] || { echo 'Usage: qemu-test.sh install|boot disposable.qcow2 [installer.iso]'; exit 1; }
[[ "$disk" == *.qcow2 ]] || { echo 'Specify a disposable .qcow2 file'; exit 1; }
[[ "$firmware" == uefi || "$firmware" == bios ]] || { echo 'FIRMWARE must be uefi or bios'; exit 1; }
if [[ "$firmware" == uefi ]]; then
  [[ -f "$ovmf" && -f "$vars_template" ]] || { echo 'Set OVMF_CODE and OVMF_VARS to your firmware paths'; exit 1; }
fi
if [[ ! -e "$disk" ]]; then
  [[ "$mode" == install ]] || { echo 'No installed disk'; exit 1; }
  qemu-img create -f qcow2 "$disk" 48G
fi
args=(-enable-kvm -machine q35 -cpu host -m 6144 -smp 4
      -drive "file=$disk,format=qcow2,if=virtio"
      -nic user,model=virtio-net-pci -vga virtio -serial file:qemu-serial.log)
if [[ "$firmware" == uefi ]]; then
  vars="${disk%.qcow2}.vars.fd"
  [[ -f "$vars" ]] || cp "$vars_template" "$vars"
  args+=(-drive "if=pflash,format=raw,readonly=on,file=$ovmf"
         -drive "if=pflash,format=raw,file=$vars")
fi
if [[ "$mode" == install ]]; then
  [[ -f "${3:-}" ]] || { echo 'Specify installer ISO as third argument'; exit 1; }
  args+=(-cdrom "$3" -boot d)
fi
exec qemu-system-x86_64 "${args[@]}"
