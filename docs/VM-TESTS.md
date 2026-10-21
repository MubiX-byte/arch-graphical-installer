# Integracja QEMU/KVM

Status dostawy: scenariusze i skrypty przygotowane; **pełna instalacja i reboot
w QEMU nie zostały wykonane w środowisku Windows tej sesji**. Wynik testów
jednostkowych nie jest dowodem bootowalności ISO ani instalacji. Przed wydaniem
produkcyjnym wykonaj całą macierz i dołącz logi, wersję ISO, wersje pakietów oraz
commit aplikacji. Nie podłączaj do QEMU fizycznych dysków hosta.

Na hoście Arch z KVM:

```bash
sudo pacman -S qemu-desktop edk2-ovmf
sudo bash scripts/build-iso.sh /var/tmp/agi-test-build
bash scripts/qemu-test.sh install test-grub.qcow2 /var/tmp/agi-test-build/out/ARCH.iso
```

Wybierz rzeczywistą nazwę wygenerowanego pliku ISO. Jeśli firmware znajduje się
gdzie indziej, ustaw `OVMF_CODE` i `OVMF_VARS`. Domyślne ścieżki zakładają edk2
z obrazami 4 MiB. Firmware musi mieć Secure Boot wyłączony.

W VM przejdź formularz (konto `tester`), zapisz plan i sprawdź wskazanie
`/dev/vda`. Potwierdź usunięcie tego dysku. Zapisz log instalacji. Zamknij VM
po sukcesie. Uruchom **bez ISO**, zachowując dysk i plik NVRAM:

```bash
bash scripts/qemu-test.sh boot test-grub.qcow2
```

Zaloguj się hasłem podanym w GUI. Przenieś skrypt weryfikacji do VM i wykonaj:

```bash
bash tests/integration/verify-installed.sh tester
```

Sprawdź dodatkowo `uname -r`, `locale`, `timedatectl`, `getent hosts archlinux.org`,
`sudo -v`, logowanie desktopu, dźwięk PipeWire i poprawne wyłączenie systemu.

| Przypadek | Oczekiwany wynik |
| --- | --- |
| GRUB + KDE + linux/linux-lts | Boot bez ISO, oba kernele w menu, działające logowanie. |
| systemd-boot + GNOME | Wpis NVRAM, działające menu i sesja GNOME. |
| XFCE / Cinnamon / i3 / Minimal | Każdy profil na świeżym qcow2, właściwy login manager lub TTY. |
| linux-zen / linux-hardened | Initramfs istnieje, wybrany kernel uruchamia system. |
| Brak sieci przed potwierdzeniem | Błąd preflight, niezmieniona tablica partycji. |
| Utrata sieci podczas pacstrap | Błąd, brak sukcesu i brak bootloadera z kolejnych etapów. |
| Zła nazwa potwierdzanego dysku | Brak uruchomienia helpera. |
| Zamontowana partycja / aktywny swap | Dysk niedostępny albo odrzucony przy ostatniej walidacji. |
| Zmiana dysku po podsumowaniu | Fingerprint nie pasuje, instalacja zatrzymana. |
| BIOS + GPT + GRUB | Start skryptu bez EFI, BIOS Boot ef02 bez formatowania, GRUB i boot z dysku bez ISO. |
| BIOS + systemd-boot | Niedostępny wybór w GUI i odrzucenie konfiguracji przez backend. |
| Secure Boot / NVIDIA | Jawna blokada przed partycjonowaniem. |
| Drugi dysk z danymi | Zapisz hash drugiego qcow2; po instalacji hash ma pozostać taki sam. |
| Przerwanie helpera | Procesy potomne zakończone, próba odmontowania, brak deklaracji sukcesu. |

Test drugiego dysku wykonuj wyłącznie na obrazach testowych. Skrypt qemu-test
domyślnie podłącza jeden dysk. Testy błędów i bootu powtarzaj dla nowych wersji
archiso, systemd, pacstrap oraz pakietów desktopowych.

## Legacy BIOS

Do niezależnego testu SeaBIOS użyj nowego obrazu dysku. Nie są potrzebne obrazy OVMF:

```bash
FIRMWARE=bios bash scripts/qemu-test.sh install test-bios.qcow2 /ścieżka/installer.iso
# Po zakończeniu instalacji zamknij VM i uruchom bez ISO:
FIRMWARE=bios bash scripts/qemu-test.sh boot test-bios.qcow2
# W uruchomionym systemie docelowym:
FIRMWARE=bios bash tests/integration/verify-installed.sh tester
```

W podsumowaniu GUI powinno być `firmware: bios`, partycja BIOS Boot 2 MiB
(bez mkfs) i root ext4. Dla błędu „Uruchom pendrive w trybie UEFI” wystarczy
zaktualizować repozytorium przez `git pull --ff-only` i ponowić `bash run.sh`.
Test bootu BIOS i UEFI w QEMU nadal wymaga wykonania; testy jednostkowe
i test GUI sprawdzają plan i polecenia, a nie rzeczywisty start systemu.
