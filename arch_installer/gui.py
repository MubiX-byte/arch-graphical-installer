import json
import os
import sys
from pathlib import Path
from PySide6.QtCore import QProcess, QThread, Signal, Qt
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QFormLayout, QLabel, QPushButton, QComboBox, QLineEdit, QCheckBox, QTextEdit,
    QStackedWidget, QProgressBar, QMessageBox, QFileDialog, QGroupBox)
from .config import Config, DESKTOPS, KERNELS, LOCALES, validate_password
from .hardware import inspect, eligible, fingerprint
from .plan import summary, packages

class Probe(QThread):
    result = Signal(dict)
    def run(self):
        try:
            self.result.emit(inspect())
        except Exception as exc:
            self.result.emit({"error": str(exc), "disks": []})

class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Arch Linux • Instalator")
        self.resize(1040, 790)
        self.busy = False
        self.hardware = {"disks": []}
        self.process = None
        self.buffer = b""
        self.events = []
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        top = QHBoxLayout()
        title = QLabel("ARCH LINUX   /   Instalator 0.1")
        title.setStyleSheet("font-size:24px;font-weight:700")
        top.addWidget(title)
        top.addStretch()
        theme = QPushButton("Jasny / ciemny")
        self.dark = True
        theme.clicked.connect(self.toggle_theme)
        top.addWidget(theme)
        layout.addLayout(top)
        self.pages = QStackedWidget()
        layout.addWidget(self.pages)
        self.welcome_page()
        self.settings_page()
        self.review_page()
        self.progress_page()
        nav = QHBoxLayout()
        self.back = QPushButton("Wstecz")
        self.next = QPushButton("Rozpocznij instalację")
        self.back.clicked.connect(lambda: self.navigate(-1))
        self.next.clicked.connect(lambda: self.navigate(1))
        nav.addWidget(self.back)
        nav.addStretch()
        nav.addWidget(self.next)
        layout.addLayout(nav)
        self.apply_theme()
        self.probe = Probe(self)
        self.probe.result.connect(self.probed)
        self.probe.start()
        self.refresh_navigation()

    def page(self, heading):
        page = QWidget()
        layout = QVBoxLayout(page)
        label = QLabel(heading)
        label.setStyleSheet("font-size:22px;font-weight:600")
        layout.addWidget(label)
        self.pages.addWidget(page)
        return layout

    def welcome_page(self):
        layout = self.page("Witaj. Zainstaluj Arch Linux.")
        label = QLabel("Wersja etapowa: UEFI • GPT • cały dysk • ext4\n"
                       "Wybór dysku nie wprowadza zmian. Instalacja wymaga osobnego potwierdzenia.\n"
                       "Dual boot, ręczne partycjonowanie, LUKS, Btrfs, BIOS, Hyprland i NVIDIA\n"
                       "nie są jeszcze obsługiwane. Secure Boot musi być wyłączony.")
        label.setWordWrap(True)
        layout.addWidget(label)
        self.hardware_text = QTextEdit("Trwa wykrywanie sprzętu…")
        self.hardware_text.setReadOnly(True)
        layout.addWidget(self.hardware_text)
        network = QPushButton("Konfiguruj Ethernet / Wi-Fi")
        network.clicked.connect(self.network)
        layout.addWidget(network)

    def combo(self, values):
        widget = QComboBox()
        widget.addItems(values)
        return widget

    def settings_page(self):
        layout = self.page("Skonfiguruj system")
        form = QFormLayout()
        self.disk = QComboBox()
        form.addRow("Dysk — wszystkie dane zostaną usunięte", self.disk)
        self.locale = self.combo(LOCALES)
        self.keymap = self.combo(["pl", "us", "de"])
        self.timezone = QLineEdit("Europe/Warsaw")
        self.desktop = self.combo(DESKTOPS)
        self.bootloader = self.combo(["grub", "systemd-boot"])
        self.shell = self.combo(["bash", "zsh", "fish"])
        self.hostname = QLineEdit("archlinux")
        self.username = QLineEdit()
        self.password = QLineEdit()
        self.repeat = QLineEdit()
        for widget in (self.password, self.repeat):
            widget.setEchoMode(QLineEdit.EchoMode.Password)
        for name, widget in [("Locale / format dat i czasu", self.locale), ("Klawiatura", self.keymap),
                             ("Strefa czasowa", self.timezone), ("Środowisko", self.desktop),
                             ("Bootloader", self.bootloader), ("Powłoka", self.shell),
                             ("Nazwa komputera", self.hostname), ("Użytkownik (sudo)", self.username),
                             ("Hasło", self.password), ("Powtórz hasło", self.repeat)]:
            form.addRow(name, widget)
        self.extras = QLineEdit()
        form.addRow("Dodatkowe pakiety (spacje)", self.extras)
        layout.addLayout(form)
        kernels = QGroupBox("Kernele")
        row = QHBoxLayout(kernels)
        self.kernels = []
        for name in KERNELS:
            check = QCheckBox(name)
            check.setChecked(name == "linux")
            row.addWidget(check)
            self.kernels.append(check)
        layout.addWidget(kernels)
        row = QHBoxLayout()
        self.zram = QCheckBox("Zram")
        self.zram.setChecked(True)
        self.bluetooth = QCheckBox("Bluetooth")
        self.trim = QCheckBox("Okresowy TRIM")
        self.trim.setChecked(True)
        for widget in (self.zram, self.bluetooth, self.trim):
            row.addWidget(widget)
        layout.addLayout(row)
        layout.addWidget(QLabel("Root będzie zablokowany. Język interfejsu: polski. Sterowniki: Mesa + firmware; NVIDIA zablokowana."))

    def review_page(self):
        layout = self.page("Sprawdź plan przed instalacją")
        self.review = QTextEdit()
        self.review.setReadOnly(True)
        layout.addWidget(self.review)
        save = QPushButton("Zapisz plan dry-run (bez haseł)")
        save.clicked.connect(self.save_plan)
        layout.addWidget(save)
        self.consent = QCheckBox("Rozumiem, że instalacja bezpowrotnie usunie WSZYSTKIE dane z wybranego dysku.")
        layout.addWidget(self.consent)
        layout.addWidget(QLabel("Wpisz pełną nazwę dysku, np. /dev/nvme0n1:"))
        self.confirm = QLineEdit()
        layout.addWidget(self.confirm)

    def progress_page(self):
        layout = self.page("Instalacja systemu")
        self.status = QLabel("Oczekiwanie")
        self.progress = QProgressBar()
        self.finished_steps = QTextEdit()
        self.finished_steps.setReadOnly(True)
        self.logs = QTextEdit()
        self.logs.setReadOnly(True)
        self.logs.setVisible(False)
        toggle = QPushButton("Pokaż / ukryj logi")
        toggle.clicked.connect(lambda: self.logs.setVisible(not self.logs.isVisible()))
        save = QPushButton("Zapisz logi")
        save.clicked.connect(self.save_logs)
        for widget in (self.status, self.progress, self.finished_steps, toggle, self.logs, save):
            layout.addWidget(widget)

    def probed(self, hardware):
        self.hardware = hardware
        self.hardware_text.setPlainText(json.dumps(hardware, ensure_ascii=False, indent=2))
        for d in hardware["disks"]:
            if eligible(d):
                self.disk.addItem(f'{d["name"]} • {d.get("model", "")} • {int(d["size"])/1024**3:.1f} GiB', d)

    def network(self):
        if sys.platform != "linux":
            QMessageBox.information(self, "Sieć", "Konfiguracja dostępna w Arch Live ISO")
            return
        QProcess.startDetached("nm-connection-editor", [])

    def config(self):
        d = self.disk.currentData()
        if not d:
            raise ValueError("Brak nieużywanego dysku niewymiennego o pojemności co najmniej 32 GiB")
        c = Config(disk=d["name"], fingerprint=fingerprint(d), hostname=self.hostname.text(),
                   username=self.username.text(), locale=self.locale.currentText(), keymap=self.keymap.currentText(),
                   timezone=self.timezone.text(), desktop=self.desktop.currentText(),
                   kernels=[w.text() for w in self.kernels if w.isChecked()], bootloader=self.bootloader.currentText(),
                   shell=self.shell.currentText(), zram=self.zram.isChecked(), bluetooth=self.bluetooth.isChecked(),
                   trim=self.trim.isChecked(), extras=self.extras.text().split())
        c.validate()
        validate_password(self.password.text())
        if self.password.text() != self.repeat.text():
            raise ValueError("Hasła nie są jednakowe")
        return c

    def navigate(self, direction):
        current = self.pages.currentIndex()
        try:
            if direction > 0 and current == 1:
                self.approved_config = self.config()
                plan = summary(self.approved_config)
                plan["packages"] = packages(self.approved_config, self.hardware.get("cpu", ""), self.hardware.get("pci", ""))
                plan["remaining_stages"] = ["pacstrap", "fstab", "locale i konta", "usługi", "mkinitcpio", "bootloader", "weryfikacja", "odmontowanie"]
                self.review.setPlainText(json.dumps(plan, ensure_ascii=False, indent=2))
                self.consent.setChecked(False)
                self.confirm.clear()
            if direction > 0 and current == 2:
                if not self.consent.isChecked() or self.confirm.text() != self.approved_config.disk:
                    raise ValueError("Zatwierdź usunięcie danych i wpisz dokładną nazwę dysku")
                self.start_install()
                return
            self.pages.setCurrentIndex(current + direction)
            self.refresh_navigation()
        except Exception as exc:
            QMessageBox.warning(self, "Nie można kontynuować", str(exc))

    def refresh_navigation(self):
        index = self.pages.currentIndex()
        self.back.setEnabled(index in (1, 2) and not self.busy)
        self.next.setVisible(index != 3)
        self.next.setText(["Rozpocznij instalację", "Sprawdź plan", "Usuń dane i zainstaluj", ""][index])

    def start_install(self):
        if sys.platform != "linux" or not Path("/usr/lib/arch-graphical-installer/helper.py").is_file():
            raise RuntimeError("Zainstaluj aplikację w Arch Live ISO przez scripts/install-live.sh")
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        self.process.readyReadStandardOutput.connect(self.read_events)
        self.process.readyReadStandardError.connect(self.read_stderr)
        self.process.finished.connect(self.process_finished)
        self.process.errorOccurred.connect(lambda error: self.status.setText("Błąd procesu: " + self.process.errorString()))
        self.process.started.connect(self.send_request)
        self.busy = True
        self.succeeded = False
        self.pages.setCurrentIndex(3)
        self.refresh_navigation()
        self.status.setText("Oczekiwanie na autoryzację polkit…")
        self.process.start("/usr/bin/pkexec", ["/usr/bin/python", "-I", "/usr/lib/arch-graphical-installer/helper.py"])

    def send_request(self):
        request = {"config": self.approved_config.public(), "password": self.password.text(), "confirmation": self.confirm.text()}
        self.process.write((json.dumps(request) + "\n").encode())
        self.process.closeWriteChannel()
        self.password.clear()
        self.repeat.clear()
        request.clear()

    def read_events(self):
        self.buffer += bytes(self.process.readAllStandardOutput())
        while b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n", 1)
            try:
                event = json.loads(line)
            except (ValueError, UnicodeError):
                continue
            self.events.append(event)
            text, kind = event["text"], event["kind"]
            if kind == "log":
                self.logs.append(text)
            else:
                self.status.setText(text)
            if kind == "progress":
                self.progress.setValue(event["value"])
                self.finished_steps.append("✓ " + text)
            if kind == "success":
                self.succeeded = True
                self.progress.setValue(100)
            if kind == "error":
                self.finished_steps.append("BŁĄD: " + text)

    def read_stderr(self):
        text = bytes(self.process.readAllStandardError()).decode(errors="replace")
        self.logs.append(text)
        self.events.append({"kind": "stderr", "text": text})

    def process_finished(self, code, status):
        self.read_events()
        self.busy = False
        if code != 0 or not self.succeeded:
            self.status.setText("Instalacja nie została zakończona. Sprawdź i zapisz logi. Nie ponawiaj bez sprawdzenia stanu dysku.")

    def save_plan(self):
        name, _ = QFileDialog.getSaveFileName(self, "Zapisz konfigurację dry-run", "plan.json", "JSON (*.json)")
        if name:
            Path(name).write_text(json.dumps(self.approved_config.public(), indent=2), encoding="utf-8")

    def save_logs(self):
        name, _ = QFileDialog.getSaveFileName(self, "Zapisz logi", "installation.json", "JSON (*.json)")
        if name:
            Path(name).write_text(json.dumps(self.events, ensure_ascii=False, indent=2), encoding="utf-8")

    def toggle_theme(self):
        self.dark = not self.dark
        self.apply_theme()

    def apply_theme(self):
        bg, fg, panel = ("#111b29", "#eaf2ff", "#1d2e42") if self.dark else ("#edf3fa", "#142237", "#ffffff")
        self.setStyleSheet(f"QWidget{{background:{bg};color:{fg};font-size:13px}} QLineEdit,QComboBox,QTextEdit,QGroupBox{{background:{panel};border:1px solid #60809b;border-radius:6px;padding:6px}} QPushButton{{background:#1679ad;color:white;border:0;border-radius:6px;padding:10px 16px}} QPushButton:disabled{{background:#586574}} QProgressBar::chunk{{background:#1793d1}}")

    def closeEvent(self, event):
        if self.busy or self.probe.isRunning():
            QMessageBox.information(self, "Operacja trwa", "Poczekaj na zakończenie. Przerwanie może pozostawić niekompletny system.")
            event.ignore()
        else:
            event.accept()

def launch():
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        raise SystemExit("Uruchom GUI jako zwykły użytkownik; backend poprosi o uprawnienia przez polkit.")
    app = QApplication(sys.argv)
    window = Window()
    window.show()
    raise SystemExit(app.exec())
