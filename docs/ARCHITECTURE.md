# Architektura i odpowiedzialność plików

Przepływ: `main.py → gui.py → JSON przez stdin → pkexec → helper.py → backend.py`.
GUI działa jako zwykły użytkownik, backend jako root. GUI nie wykonuje poleceń
partycjonowania. Root uruchamia wyłącznie zainstalowaną kopię helpera w katalogu
`/usr/lib/arch-graphical-installer`, którego pliki należą do roota.

| Plik | Odpowiedzialność i współpraca |
| --- | --- |
| main.py | Start GUI lub czysty plan dry-run, bez importowania Qt/backendu w dry-run. |
| run.sh | Jednopoleceniowe przygotowanie oficjalnego Live ISO: zależności, NetworkManager, konto agi-live, LightDM/Xfce, polkit i autostart GUI. Nie dotyka partycji. |
| helper.py | Izolowany punkt wejścia do backendu, odczyt pojedynczego żądania. |
| arch_installer/config.py | Model konfiguracji, walidacja list dozwolonych wartości i haseł, definicje desktopów. |
| arch_installer/hardware.py | Odczyt lsblk/lscpu/lspci/lsusb/nmcli, fingerprint dysku, sprawdzenie repozytorium HTTPS. |
| arch_installer/plan.py | Deterministyczny plan GPT/ext4, lista pakietów i publiczne podsumowanie. |
| arch_installer/backend.py | Powtórna walidacja, blokada procesu, preflight, polecenia, konfiguracja systemu, bootloader, weryfikacja i cleanup. |
| arch_installer/gui.py | Cztery ekrany, QThread do wykrywania sprzętu, asynchroniczny QProcess, progres ze zdarzeń backendu, eksport planu/logów. |
| scripts/install-live.sh | Wewnętrzny etap run.sh: instalacja zależności oraz kopii aplikacji należącej do roota w działającym Live ISO. |
| scripts/build-iso.sh | Rozszerzenie profilu releng z archiso, hook tworzący użytkownika live, autologowanie i Xfce. |
| scripts/arch-graphical-installer | Launcher zainstalowanej kopii. |
| scripts/qemu-test.sh | Osobne uruchomienie instalacyjnego ISO i uruchomienie zainstalowanego dysku bez ISO. |
| iso/packages.extra | Pakiety dodawane do profilu releng. |
| iso/customize.fragment.sh | Hook tworzący wyłącznie w obrazie live konto live bez hasła. |
| iso/49-live-installer.rules | Reguła polkit dla konkretnego helpera i lokalnego aktywnego użytkownika live. |
| assets/arch-graphical-installer.desktop | Launcher i autostart aplikacji w ISO. |
| tests/test_safety.py | Walidacja, dry-run bez poleceń, zajęte dyski, zmiana tożsamości i macierz pakietów. |
| tests/test_backend.py | Testy backendu na Linuksie: brak potwierdzenia, wymiana dysku, ograniczenia ścieżek, hasła, błędy poleceń i bootctl. |
| tests/gui_smoke.py | Test przejścia przez formularz i plan w Qt offscreen. |
| tests/test_bootstrap.py | Sprawdzenie pomocy, błędnych argumentów i odrzucenia niewłaściwego systemu przed uruchomieniem pacman. |
| tests/integration/verify-installed.sh | Asercje na systemie uruchomionym z dysku VM. |
| .github/workflows/tests.yml | Automatyczne testy bez uprzywilejowanych operacji dyskowych. |
| examples/config.json | Jawna przykładowa konfiguracja bez haseł. |
| pyproject.toml / requirements.txt | Metadane Pythona i zależność Qt. |

## Kolejność wykonania

Preflight → ponowny odczyt dysku → GPT → FAT32/ext4 → mount → sprawdzone
pakiety z pacstrap → genfstab → locale, czas, konta i sudo → usługi → mkinitcpio
→ bootloader → sprawdzenie plików → sync → umount → komunikat sukcesu.
Pacstrap instaluje bazę, kernele i desktop w jednej transakcji.

Postęp odpowiada zakończonym etapom, nie liczbie pobranych bajtów. Wyjście
polecenia trafia do logu po jego zakończeniu; długie pacstrap może pozostawać na
jednym etapie. Stan sieci jest wykrywany na wejściu i sprawdzany przed instalacją,
nie jest monitorowany stale. Przy zerwaniu pobierania polecenie zgłasza błąd.

Hasło przechodzi wyłącznie przez stdin, do chpasswd również przez stdin. Logi
chpasswd są pomijane. Python nie gwarantuje wyzerowania kopii pamięci haseł;
aplikacja skraca ich czas życia, lecz nie deklaruje odporności na odczyt RAM roota.

Błąd zatrzymuje dalsze etapy i próbuje odmontować system. Nie ma rollbacku
tablicy partycji ani przywracania danych. Nie ma automatycznego wznowienia.
Uruchomienie aplikacji i dry-run nie zmieniają dysków.
