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
