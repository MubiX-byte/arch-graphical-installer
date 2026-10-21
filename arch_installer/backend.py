"""Privileged executor. No shell evaluation, no credentials in argv or logs."""
import fcntl
import json
import os
import platform
import shutil
import signal
import subprocess
from pathlib import Path
from .config import Config, DESKTOPS, validate_password
from .hardware import disks, eligible, fingerprint, internet, query
from .plan import storage_plan, packages, partition

TARGET = Path("/mnt/arch-graphical-installer")

class Installer:
    def __init__(self, config, password, confirmation, emit):
        self.c = config
        self.password = password
        self.confirmation = confirmation
        self.emit = emit
        self.mounted = False
        self.completed = 0
        self.log = []

    def event(self, kind, text, **extra):
        record = {"kind": kind, "text": text, **extra}
        self.log.append(record)
        self.emit(record)

    def run(self, argv, *, input_text=None, secret=False, timeout=7200):
        self.event("log", "Przekazanie danych konta przez stdin" if secret else " ".join(argv))
        # Sanitized environment and fixed PATH prevent caller-controlled executables.
        env = {"PATH": "/usr/bin:/usr/sbin", "LANG": "C.UTF-8", "HOME": "/root"}
        try:
            process = subprocess.Popen(argv, stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
                                       text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       env=env, start_new_session=True)
            try:
                output, _ = process.communicate(input_text, timeout=timeout)
            except BaseException:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.communicate()
                raise
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Przekroczono limit czasu: {argv[0]}") from None
        if output and not secret:
            self.event("log", output[-65536:])
        if process.returncode:
            raise RuntimeError(f"Polecenie {argv[0]} zakończyło się kodem {process.returncode}")
        return output

    def chroot(self, *argv, **kwargs):
        return self.run(["arch-chroot", str(TARGET), *argv], **kwargs)

    def write(self, relative, text, mode=0o644):
        path = TARGET / relative
        if not path.resolve().is_relative_to(TARGET.resolve()):
            raise RuntimeError("Ścieżka opuszcza system docelowy")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        path.chmod(mode)

    def preflight(self):
        self.c.validate()
        validate_password(self.password)
        if self.confirmation != self.c.disk:
            raise ValueError("Brak potwierdzenia usunięcia dysku")
        if platform.system() != "Linux" or platform.machine() != "x86_64" or os.geteuid() != 0:
            raise RuntimeError("Wymagany root i Arch Linux x86_64")
        if not Path("/run/archiso").is_dir() or not Path("/etc/arch-release").exists():
            raise RuntimeError("Instalacja dozwolona tylko w Arch Live ISO")
        if not Path("/sys/firmware/efi/efivars").is_dir():
            raise RuntimeError("Wymagany start w UEFI; Legacy BIOS zablokowany")
        if Path("/sys/firmware/efi/fw_platform_size").read_text().strip() != "64":
            raise RuntimeError("Wymagany 64-bitowy firmware UEFI")
        ram = next(line.split()[1] for line in Path("/proc/meminfo").read_text().splitlines() if line.startswith("MemTotal:"))
        if int(ram) < 2 * 1024**2:
            raise RuntimeError("Wymagane co najmniej 2 GiB RAM; dla GUI zalecane 6 GiB")
        secure = list(Path("/sys/firmware/efi/efivars").glob("SecureBoot-*"))
        if not secure or secure[0].read_bytes()[4:5] != b"\x00":
            raise RuntimeError("Nie można potwierdzić wyłączenia Secure Boot")
        for program in ("sgdisk", "partprobe", "udevadm", "mkfs.fat", "mkfs.ext4", "mount", "umount", "pacstrap", "arch-chroot", "genfstab", "pacman", "lsblk", "lspci", "lsusb", "timedatectl"):
            if not shutil.which(program):
                raise RuntimeError(f"Brak narzędzia: {program}")
        timezone = Path("/usr/share/zoneinfo") / self.c.timezone
        if not timezone.is_file() or not timezone.resolve().is_relative_to(Path("/usr/share/zoneinfo")):
            raise ValueError("Nieistniejąca strefa czasowa")
        if TARGET.is_symlink() or (TARGET.exists() and any(TARGET.iterdir())):
            raise RuntimeError("Punkt montowania nie jest pustym katalogiem")
        pci = query(["lspci", "-nn"])
        if any("NVIDIA" in line and any(t in line for t in ("VGA", "3D", "Display")) for line in pci.splitlines()):
            raise RuntimeError("NVIDIA: ta wersja blokuje instalację do czasu wdrożenia tabeli zgodności sterowników")
        internet()
        self.run(["timedatectl", "set-ntp", "true"])
        if self.run(["timedatectl", "show", "-p", "NTPSynchronized", "--value"]).strip() != "yes":
            raise RuntimeError("Zegar nie jest zsynchronizowany; spróbuj ponownie za chwilę")
        self.package_list = packages(self.c, query(["lscpu"]), pci)
        self.run(["pacman", "-Sy", "--noconfirm"])
        self.run(["pacman", "-Sp", "--noconfirm", "--print-format", "%n", "--", *self.package_list])
        self.check_disk()

    def check_disk(self):
        selected = next((d for d in disks() if d["name"] == self.c.disk), None)
        if selected is None or fingerprint(selected) != self.c.fingerprint or not eligible(selected):
            raise RuntimeError("Dysk zmienił się, jest używany, wymienny lub ma mniej niż 32 GiB")

    def configure(self):
        c = self.c
        fstab = self.run(["genfstab", "-U", str(TARGET)])
        if "UUID=" not in fstab:
            raise RuntimeError("genfstab nie wygenerował UUID")
        self.write("etc/fstab", fstab)
        self.write("etc/locale.gen", c.locale + " UTF-8\n")
        self.write("etc/locale.conf", f"LANG={c.locale}\n")
        self.write("etc/vconsole.conf", f"KEYMAP={c.keymap}\n")
        self.write("etc/hostname", c.hostname + "\n")
        self.write("etc/hosts", f"127.0.0.1 localhost\n::1 localhost\n127.0.1.1 {c.hostname}.localdomain {c.hostname}\n")
        self.write("etc/X11/xorg.conf.d/00-keyboard.conf", 'Section "InputClass"\n Identifier "keyboard"\n MatchIsKeyboard "on"\n Option "XkbLayout" "' + c.keymap + '"\nEndSection\n')
        self.chroot("ln", "-sf", "/usr/share/zoneinfo/" + c.timezone, "/etc/localtime")
        self.chroot("locale-gen")
        self.chroot("hwclock", "--systohc")
        self.chroot("useradd", "-m", "-G", "wheel", "-s", "/bin/" + c.shell, c.username)
        self.chroot("chpasswd", input_text=c.username + ":" + self.password + "\n", secret=True)
        self.password = ""
        self.chroot("passwd", "-l", "root")
        self.write("etc/sudoers.d/10-wheel", "%wheel ALL=(ALL:ALL) ALL\n", 0o440)
        self.chroot("visudo", "-cf", "/etc/sudoers")
        if c.zram:
            self.write("etc/systemd/zram-generator.conf", "[zram0]\nzram-size = min(ram / 2, 4096)\ncompression-algorithm = zstd\n")
        services = ["NetworkManager"]
        if c.bluetooth:
            services += ["bluetooth"]
        if c.trim:
            services += ["fstrim.timer"]
        if DESKTOPS[c.desktop][1]:
            services += [DESKTOPS[c.desktop][1]]
        self.chroot("systemctl", "enable", *services)
        self.chroot("mkinitcpio", "-P")

    def bootloader(self):
        if self.c.bootloader == "grub":
            self.chroot("grub-install", "--target=x86_64-efi", "--efi-directory=/boot", "--bootloader-id=ArchGraphical")
            self.chroot("grub-mkconfig", "-o", "/boot/grub/grub.cfg")
        else:
            # Run from the live host: bootctl inside arch-chroot's PID namespace
            # skips NVRAM writes. Use target systemd's EFI binary explicitly.
            self.run(["bootctl", "--root=" + str(TARGET), "--esp-path=/boot", "--variables=yes",
                      "--efi-boot-option-description=Arch Graphical Installer",
                      "--install-source=image", "install"])
            uuid = self.run(["blkid", "-s", "UUID", "-o", "value", partition(self.c.disk, 2)]).strip()
            if not uuid or any(c not in "0123456789abcdefABCDEF-" for c in uuid):
                raise RuntimeError("Nieprawidłowy UUID root")
            self.write("boot/loader/loader.conf", f"default arch-{self.c.kernels[0]}.conf\ntimeout 5\neditor no\n")
            for kernel in self.c.kernels:
                microcode = "".join(f"initrd /{p}.img\n" for p in ("intel-ucode", "amd-ucode") if (TARGET / "boot" / (p + ".img")).exists())
                self.write(f"boot/loader/entries/arch-{kernel}.conf", f"title Arch Linux ({kernel})\nlinux /vmlinuz-{kernel}\n{microcode}initrd /initramfs-{kernel}.img\noptions root=UUID={uuid} rw\n")

    def verify(self):
        required = ["etc/fstab", "etc/passwd", "usr/bin/sudo"]
        required += [f"boot/vmlinuz-{k}" for k in self.c.kernels]
        required += [f"boot/initramfs-{k}.img" for k in self.c.kernels]
        required += ["boot/EFI/ArchGraphical/grubx64.efi", "boot/grub/grub.cfg"] if self.c.bootloader == "grub" else ["boot/EFI/systemd/systemd-bootx64.efi"]
        if any(not (TARGET / p).is_file() or not (TARGET / p).stat().st_size for p in required):
            raise RuntimeError("Brakuje wymaganych plików zainstalowanego systemu")
        self.chroot("systemctl", "is-enabled", "NetworkManager")

    def execute(self):
        def interrupted(signum, frame):
            raise RuntimeError("Przerwano instalację; dysk może zawierać niekompletny system")
        signal.signal(signal.SIGTERM, interrupted)
        signal.signal(signal.SIGINT, interrupted)
        lock = open("/run/arch-graphical-installer.lock", "w")
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            self.preflight()
            TARGET.mkdir(parents=True, exist_ok=True)
            steps = storage_plan(self.c)
            total = len(steps) + 5
            self.check_disk()  # Last read-only check immediately before destroying the table.
            for step in steps:
                self.event("stage", step.label)
                self.run(list(step.argv))
                if step.argv[0] == "mount":
                    self.mounted = True
                self.completed += 1
                self.event("progress", step.label, value=int(self.completed / total * 100))
            actions = [("Instalowanie pakietów", lambda: self.run(["pacstrap", "-K", str(TARGET), *self.package_list])),
                       ("Konfiguracja systemu", self.configure), ("Bootloader", self.bootloader), ("Weryfikacja", self.verify)]
            for label, action in actions:
                self.event("stage", label)
                action()
                self.completed += 1
                self.event("progress", label, value=int(self.completed / total * 100))
            self.run(["sync"])
            self.run(["umount", "-R", str(TARGET)])
            self.mounted = False
            self.event("success", "Instalacja zakończona. Możesz uruchomić komputer ponownie.", value=100)
        except BaseException:
            self.password = ""
            if self.mounted:
                try:
                    self.run(["umount", "-R", str(TARGET)])
                    self.mounted = False
                except Exception:
                    self.event("log", "Nie udało się odmontować systemu. Nie wyjmuj dysku; sprawdź mount w Live ISO.")
            raise
        finally:
            self.password = ""
            lock.close()

def helper_main():
    def emit(event):
        print(json.dumps(event, ensure_ascii=False), flush=True)
    try:
        raw = __import__("sys").stdin.buffer.readline(65537)
        if len(raw) > 65536:
            raise ValueError("Zbyt duże żądanie")
        request = json.loads(raw)
        installer = Installer(Config(**request["config"]), request["password"], request["confirmation"], emit)
        request.clear()
        installer.execute()
    except BaseException as exc:
        # Exceptions never include request bodies or stdin secrets.
        emit({"kind": "error", "text": str(exc)})
        return 1
    return 0
