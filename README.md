# Arch Linux Graphical Installer

Graficzny instalator w Pythonie/PySide6 z oddzielnym backendem roota.
**Wersja 0.1 jest pierwszym etapem projektu**, a nie implementacją całej docelowej
specyfikacji. Wykonuje rzeczywiste polecenia instalacji. Wymaga testów pełnego
cyklu w QEMU przed użyciem na sprzęcie z danymi. Instalacja na całym dysku usuwa
wszystkie znajdujące się na nim partycje.

## Jeden skrypt: paczki, pulpit i instalator

Uruchom oficjalne Arch Linux Live ISO w trybie UEFI albo Legacy BIOS i połącz internet. Pobierz
repozytorium, a w jego katalogu uruchom jako root:

```bash
bash run.sh
```

To jedyne polecenie potrzebne do przygotowania i uruchomienia aplikacji.
`run.sh` instaluje pakiety Pythona/PySide6 oraz wszystkie narzędzia instalacyjne,
NetworkManager, Xorg, Xfce, LightDM i polkit. Tworzy dedykowane konto `agi-live`,
ustawia autologowanie do pulpitu Live i automatycznie otwiera GUI. Nie trzeba
ręcznie tworzyć kont, ustawiać haseł Live ani wywoływać startx.

Przy pierwszym pobieraniu projektu możesz użyć:

```bash
pacman -Sy --needed --noconfirm git
git clone https://github.com/MubiX-byte/arch-graphical-installer.git
cd arch-graphical-installer
bash run.sh
```

Skrypt następnie wykonuje pełne `pacman -Syu` wraz z instalacją zależności.
Przed instalacją wylicza miejsce na pełne rozpakowane pakiety, pobieranie i zapas.
Na standardowym Live ISO automatycznie zwiększa limit tmpfs
`/run/archiso/cowspace`, jeżeli RAM pozwala obsłużyć transakcję i zachować 1 GiB
dla pulpitu. Nie powiększa partycji dysku i nie wyłącza kontroli miejsca pacmana.
Przy niedostatecznej pamięci zatrzymuje się z informacją o wymaganym RAM;
dla pobierania całego GUI zalecane jest zwykle 6–8 GiB RAM maszyny wirtualnej.
Zwiększenie rozmiaru wirtualnego dysku nie powiększa warstwy Live w RAM.
Wymagany jest działający internet do pierwszego pobrania pakietów. Jeśli po
przełączeniu z iwd/networkd na NetworkManager zniknie Wi-Fi, skrypt otworzy
`nmtui-connect`, aby ponownie wybrać sieć. Hasła Wi-Fi nie trafiają do logu.

Przygotowanie nie wykonuje partycjonowania ani formatowania. Właściwą instalację
systemu zatwierdzasz dopiero w GUI. Konto Live i jego autologowanie nie są
kopiowane do systemu docelowego. Skrypt jest przeznaczony dla konsoli Live ISO;
nie uruchamiaj go na zainstalowanym Arch Linux. Ponowne wywołanie nie restartuje
aktywnego LightDM: aplikację można wtedy otworzyć z menu pulpitu.

## Architektura

`GUI (zwykły użytkownik) → plan i potwierdzenie → pkexec → backend (root)`.
Pełny opis plików i współpracy modułów: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
Kod dostarczony jest jako rzeczywiste pliki repozytorium, z rozdzieleniem GUI,
modelu konfiguracji, sprzętu, planowania i wykonania.

## Obsługiwany zakres

- Arch Linux Live ISO x86_64: Legacy BIOS albo 64-bitowe UEFI z wyłączonym Secure Boot.
- Cały nieużywany dysk SATA/SCSI, NVMe lub virtio, minimum 32 GiB, bez flagi removable.
- UEFI/GPT: 2 GiB EFI FAT32 pod `/boot`, reszta ext4 pod `/`.
- BIOS/GPT: 2 MiB nieformatowanej partycji BIOS Boot (ef02), reszta ext4 pod `/`, katalog `/boot` na root.
- Jednocześnie linux, linux-lts, linux-zen i linux-hardened z nagłówkami.
- GRUB dla BIOS (`i386-pc`) i UEFI; systemd-boot wyłącznie dla UEFI. Wpisy dla wybranych kerneli.
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
Tablica partycji MBR (BIOS używa GPT), LUKS2, Btrfs/subwolumeny/Snapper, osobne `/home`, swapfile,
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

## Składniki uruchomienia Live

`run.sh` jest głównym punktem wejścia. Wykorzystuje `scripts/install-live.sh`
do instalowania pakietów i umieszczania kopii aplikacji należącej do roota w
`/usr/lib/arch-graphical-installer`. Samodzielne wywołanie skryptu wewnętrznego
instaluje zależności, ale nie uruchamia pulpitu — do pełnego startu używaj `run.sh`.

Przycisk sieci w GUI otwiera `nm-connection-editor`. Reguła polkit dotyczy
wyłącznie konkretnego helpera i lokalnego aktywnego konta `agi-live`. Nie nadaje
temu kontu ogólnych uprawnień sudo.

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
