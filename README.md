# Arch Linux Graphical Installer

Graficzny instalator w Pythonie/PySide6 z oddzielnym backendem roota.
**Wersja 0.1 jest pierwszym etapem projektu**, a nie implementacją całej docelowej
specyfikacji. Wykonuje rzeczywiste polecenia instalacji. Wymaga testów pełnego
cyklu w QEMU przed użyciem na sprzęcie z danymi. Instalacja na całym dysku usuwa
wszystkie znajdujące się na nim partycje.

## Architektura

`GUI (zwykły użytkownik) → plan i potwierdzenie → pkexec → backend (root)`.
Pełny opis plików i współpracy modułów: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
Kod dostarczony jest jako rzeczywiste pliki repozytorium, z rozdzieleniem GUI,
modelu konfiguracji, sprzętu, planowania i wykonania.

## Obsługiwany zakres

- Arch Linux Live ISO x86_64, 64-bitowe UEFI, wyłączony Secure Boot.
- Cały nieużywany dysk SATA/SCSI, NVMe lub virtio, minimum 32 GiB, bez flagi removable.
- GPT: 2 GiB EFI FAT32 pod `/boot`, reszta ext4 pod `/`.
- Jednocześnie linux, linux-lts, linux-zen i linux-hardened z nagłówkami.
- GRUB albo systemd-boot, wpisy dla wybranych kerneli.
- KDE Plasma, GNOME, XFCE, Cinnamon, i3 lub instalacja bez GUI.
- Locale PL/EN/DE, klawiatura pl/us/de, strefy z zoneinfo, hostname, użytkownik,
  sudo, Bash/Zsh/Fish. Root zablokowany, brak automatycznego logowania w systemie docelowym.
- Mesa, firmware, microcode CPU Intel/AMD, pakiety Vulkan Intel/AMD, PipeWire.
- NetworkManager, opcjonalny Bluetooth, zram i okresowy TRIM.
- Motyw jasny/ciemny, polski interfejs, logi, rzeczywisty progres etapów, dry-run.
- Konfiguracja sieci przez uruchamiany z GUI edytor NetworkManager.

Lista pakietów jest sprawdzana przez pacman przed operacjami dyskowymi. Nazwy
pakietów Arch mogą się zmieniać: brak pakietu blokuje instalację. Baza i desktop
są instalowane jedną transakcją pacstrap. Wykryte partycje i systemy plików są
widoczne w danych lsblk; aplikacja nie identyfikuje wiarygodnie nazw istniejących OS.

## Funkcje zablokowane lub niedostępne

Dual boot i ponowne użycie ESP, ręczny edytor partycji, zmniejszanie partycji,
Legacy BIOS/MBR, LUKS2, Btrfs/subwolumeny/Snapper, osobne `/home`, swapfile,
Hyprland, automatyczny dobór sterowników NVIDIA, multilib, własne mirrory,
firewall, autologowanie, hasło root, języki interfejsu inne niż polski.
NVIDIA jest blokowana na etapie preflight, zamiast instalowania przypadkowego
pakietu. Żadna opcja GUI nie deklaruje wsparcia dla tych scenariuszy.
Nie ma monitorowania sieci na żywo ani strumieniowego logu wyjścia pacstrap.
Nie ma przywracania partycji po błędzie ani gwarancji obsługi każdego modelu GPU.

## Dry-run i testy bez modyfikowania dysków

Python 3.11+; do samego dry-run i testów jednostkowych Qt nie jest potrzebne:

```bash
python main.py --dry-run examples/config.json
python -m unittest discover -s tests -v
python -m compileall -q arch_installer main.py helper.py
```

Dry-run nie wykonuje poleceń systemowych. Plik JSON nie zawiera haseł. Dla
rzeczywistej instalacji GUI pobiera aktualny fingerprint dysku, a helper sprawdza
go ponownie. Przykładowy JSON służy wyłącznie do planowania.

Do uruchomienia GUI w środowisku programistycznym:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
QT_QPA_PLATFORM=offscreen python tests/gui_smoke.py
```

Na Windows GUI można sprawdzić, ale instalacja pozostaje zablokowana. GUI
uruchamiaj jako zwykły użytkownik; backend wymaga zainstalowania w Live ISO.

## Działające oficjalne Live ISO

Po uruchomieniu oficjalnego Arch ISO skonfiguruj internet, a następnie jako root:

```bash
bash scripts/install-live.sh
useradd -m -s /bin/bash installer
passwd installer
passwd root
su - installer
startx /usr/bin/startxfce4
```

W sesji Xfce uruchom agenta polkit, jeśli nie wystartował automatycznie:

```bash
/usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1 &
arch-graphical-installer
```

Przycisk konfiguracji sieci otwiera `nm-connection-editor`; można wybrać Wi-Fi
i wprowadzić hasło poza procesem instalatora. Helper poprosi o uwierzytelnienie
polkit hasłem administratora Live. Te konta i hasła Live nie trafiają do systemu
docelowego. Live musi mieć zsynchronizowany czas i dostęp do repozytoriów HTTPS.

## Własny obraz ISO

Na hoście Arch Linux z wolnymi kilkunastoma GiB:

```bash
sudo bash scripts/build-iso.sh /var/tmp/arch-graphical-build
```

Skrypt kopiuje oficjalny profil releng z zainstalowanego archiso, dodaje pakiety,
hook użytkownika live, Xorg/Xfce, NetworkManager, autologowanie i autostart GUI,
po czym wywołuje mkarchiso. Katalog budowania musi być nowy.
Wynik: `/var/tmp/arch-graphical-build/out/*.iso`.

Konto `live` bez hasła i reguła polkit są przeznaczone wyłącznie dla tego ISO.
Reguła zezwala aktywnemu lokalnemu użytkownikowi live na uruchomienie konkretnej
kopii helpera. Nie kopiuj jej do zainstalowanego systemu.

Obraz ISO i start pulpitu wymagają weryfikacji na aktualnej wersji archiso.
Projekt dostarcza generator profilu, nie sprawdzony binarny obraz ISO.

## QEMU/KVM

Procedura, macierz testów pozytywnych i negatywnych oraz uruchomienie bez ISO:
[docs/VM-TESTS.md](docs/VM-TESTS.md). Skrypt
`tests/integration/verify-installed.sh` wykonuje asercje po uruchomieniu z dysku.

Stan walidacji dostawy zapisano w [docs/VALIDATION.md](docs/VALIDATION.md).
CI uruchamia testy jednostkowe na Linuksie; nie wykonuje instalacji w VM.

## Źródła techniczne

Polecenia i ograniczenia sprawdzono 2026-10-21 w dokumentacji oficjalnej.
W szczególności bootctl działa z hosta Live z `--root`, `--install-source=image`
i `--variables=yes`, aby uniknąć pominięcia NVRAM w przestrzeni PID arch-chroot.

- [Arch Installation guide](https://wiki.archlinux.org/title/Installation_guide)
- [GRUB](https://wiki.archlinux.org/title/GRUB)
- [systemd-boot](https://wiki.archlinux.org/title/Systemd-boot)
- [bootctl(1)](https://man.archlinux.org/man/bootctl.1.en)
- [Archiso](https://wiki.archlinux.org/title/Archiso)
- [Opis profilu archiso](https://github.com/archlinux/archiso/blob/master/docs/README.profile.rst)
- [NVIDIA i ograniczenia zgodności](https://wiki.archlinux.org/title/NVIDIA)
- [NetworkManager](https://wiki.archlinux.org/title/NetworkManager)
- [PySide6 w oficjalnym repozytorium](https://archlinux.org/packages/extra/x86_64/pyside6/)
- [pkexec(1)](https://man.archlinux.org/man/pkexec.1)

Licencja MIT dla kodu projektu; zależności zachowują własne licencje.
