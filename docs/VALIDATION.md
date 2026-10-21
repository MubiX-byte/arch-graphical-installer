# Stan walidacji — 2026-10-21

- Windows, Python 3.11+: testy walidacji/planu/CLI zakończone sukcesem.
- Testy uprzywilejowanego backendu są pomijane na Windows; uruchamia je Linux CI.
- Linux CI: 17 testów jednostkowych, compileall i sprawdzenie składni Bash przeszły.
  Pierwszy test GUI ujawnił brak biblioteki libEGL na runnerze; workflow uzupełniono
  o biblioteki runtime Qt.
- PySide6 6.12.0: test GUI offscreen przeszedł przez ekran powitalny, formularz,
  podsumowanie i zmianę motywu. Hasło nie pojawia się w podsumowaniu.
- Wszystkie moduły Pythona przeszły compileall.
- Lokalny Bash z Git for Windows jest blokowany przez sandbox, dlatego lokalnie
  nie potwierdzono składni skryptów. Sprawdza ją workflow GitHub Actions.
- WSL nie jest zainstalowany. QEMU/KVM i budowa archiso nie były dostępne.
- Nie wykonano pełnej instalacji, restartu VM ani testów fizycznego sprzętu.

Skrypty QEMU i asercje po restarcie dostarczono w repozytorium. Do czasu wykonania
macierzy z VM-TESTS.md wersja pozostaje eksperymentalnym pierwszym etapem.

## Poprawka startu Legacy BIOS

Usunięto wymóg UEFI z run.sh. Dodano wykrywanie firmware w GUI, walidację zgodności
planu z firmware, GPT/ef02 dla BIOS, GRUB i386-pc na całym dysku oraz weryfikację
plików BIOS GRUB. Testy obejmują plan BIOS bez formatowania partycji osadzania,
odrzucanie systemd-boot w BIOS, sprawdzanie EFI/Secure Boot oraz przejście GUI
w obu trybach. Rzeczywiste uruchomienie z dysku w BIOS pozostaje niezweryfikowane.

## Poprawka braku miejsca w Live ISO

Przed transakcją zależności skrypt sprawdza wolne miejsce oraz MemAvailable.
Wymagany budżet obejmuje pełny Installed Size wszystkich pakietów transakcji
(bez odejmowania poprzednich wersji na overlay), pobieranie oraz 512 MiB zapasu.
Na rozpoznanym tmpfs cowspace może zwiększyć limit, zachowując 1 GiB RAM dla
działających procesów. Trwałych systemów plików i partycji nie powiększa.
Testy symulują sondy systemowe i mount; rzeczywistego remount w Arch Live ISO
nie wykonano w środowisku Windows.
