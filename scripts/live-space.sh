#!/usr/bin/env bash
# Sourced by install-live.sh. No operations are performed merely by sourcing it.

live_space_error() {
  printf '\nBŁĄD: %s\n' "$*" >&2
  return 1
}

live_mem_available_bytes() {
  awk '/^MemAvailable:/ {printf "%.0f\n", $2 * 1024; found=1} END {if (!found) exit 1}' /proc/meminfo
}

live_df_bytes() {
  LC_ALL=C df --block-size=1 --output="$2" -- "$1" | awk 'NR==2 {print $1}'
}

live_ensure_space() {
  local required=$1 cow=/run/archiso/cowspace
  local available memory used size target fs options
  [[ $required =~ ^[0-9]+$ ]] || return 1
  available=$(live_df_bytes / avail) || return 1
  [[ $available =~ ^[0-9]+$ ]] || return 1
  fs=$(findmnt --noheadings --raw --mountpoint "$cow" --output FSTYPE 2>/dev/null) || fs=
  options=$(findmnt --noheadings --raw --mountpoint / --output OPTIONS) || return 1

  # Only resize the real Archiso overlay backing tmpfs, never a physical disk
  # or a different filesystem that happens to be mounted under /run.
  if [[ $fs != tmpfs || $options != *"upperdir=$cow/"* ]]; then
    (( available >= required )) || live_space_error \
      "Warstwa Live ma za mało miejsca ($((available / 1024**2)) MiB wolne, potrzeba $((required / 1024**2)) MiB). Nie jest obsługiwanym tmpfs cowspace; nie zmieniam jej rozmiaru. Użyj przygotowanego ISO lub większej warstwy Live."
    return
  fi

  memory=$(live_mem_available_bytes) || return 1
  [[ $memory =~ ^[0-9]+$ ]] || return 1
  # Raising a tmpfs limit does not create RAM. Keep 1 GiB for the desktop,
  # package extraction and running processes. Do not count swap or target disks.
  if (( memory < required + 1024**3 )); then
    live_space_error "Za mało dostępnego RAM na paczki Live i pulpit: $((memory / 1024**2)) MiB dostępne; wymagane co najmniej $(((required + 1024**3) / 1024**2)) MiB. Zwiększ RAM maszyny (zwykle 6–8 GiB) albo użyj ISO z gotowymi zależnościami. Samo zwiększenie cowspace nie wystarczy."
    return 1
  fi
  if (( available >= required )); then
    return 0
  fi
  used=$(live_df_bytes "$cow" used) || return 1
  size=$(live_df_bytes "$cow" size) || return 1
  [[ $used =~ ^[0-9]+$ && $size =~ ^[0-9]+$ ]] || return 1
  target=$((used + required))
  (( target >= size )) || target=$size
  printf 'Powiększanie limitu warstwy Live cowspace do %s MiB (bez zmian na dyskach)…\n' "$(((target + 1024**2 - 1) / 1024**2))"
  mount -o "remount,size=$target" "$cow" || return 1
  available=$(live_df_bytes / avail) || return 1
  [[ $available =~ ^[0-9]+$ ]] || return 1
  (( available >= required )) || live_space_error 'Po zmianie cowspace nadal brakuje miejsca. Instalacja paczek została zatrzymana.'
}

live_installed_bytes() {
  # pacman -Si is localized; callers must set LC_ALL=C.
  LC_ALL=C awk -v expected="$1" '
    /^Installed Size[[:space:]]*:/ {
      sub(/^[^:]*:[[:space:]]*/, "")
      split($0, value, /[[:space:]]+/)
      unit=value[2]
      factor=0
      if (unit=="B") factor=1
      if (unit=="KiB") factor=1024
      if (unit=="MiB") factor=1024^2
      if (unit=="GiB") factor=1024^3
      if (unit=="TiB") factor=1024^4
      if (!factor || value[1] !~ /^[0-9]+([.][0-9]+)?$/) {bad=1; exit 1}
      total += value[1] * factor
      count++
    }
    END {if (bad || count != expected) exit 1; printf "%.0f\n", total}
  '
}
