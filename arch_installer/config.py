from dataclasses import dataclass, field, asdict
import re

DESKTOPS = {
    "Minimal": ([], None),
    "KDE Plasma": (["plasma-desktop", "konsole", "dolphin", "sddm", "xdg-desktop-portal-kde"], "sddm"),
    "GNOME": (["gnome-shell", "gnome-session", "gnome-control-center", "nautilus", "gnome-terminal", "gdm", "xdg-desktop-portal-gnome"], "gdm"),
    "XFCE": (["xfce4", "xfce4-terminal", "lightdm", "lightdm-gtk-greeter", "xorg-server"], "lightdm"),
    "Cinnamon": (["cinnamon", "nemo", "lightdm", "lightdm-gtk-greeter", "xorg-server"], "lightdm"),
    "i3": (["i3-wm", "i3status", "dmenu", "xterm", "lightdm", "lightdm-gtk-greeter", "xorg-server"], "lightdm"),
}
KERNELS = ("linux", "linux-lts", "linux-zen", "linux-hardened")
LOCALES = ("pl_PL.UTF-8", "en_US.UTF-8", "de_DE.UTF-8")

@dataclass
class Config:
    disk: str = ""
    fingerprint: str = ""
    hostname: str = "archlinux"
    username: str = ""
    locale: str = "pl_PL.UTF-8"
    keymap: str = "pl"
    timezone: str = "Europe/Warsaw"
    desktop: str = "KDE Plasma"
    kernels: list[str] = field(default_factory=lambda: ["linux"])
    bootloader: str = "grub"
    firmware: str = "uefi"
    shell: str = "bash"
    zram: bool = True
    bluetooth: bool = False
    trim: bool = True
    extras: list[str] = field(default_factory=list)

    def validate(self):
        if not re.fullmatch(r"/dev/(sd[a-z]+|vd[a-z]+|nvme\d+n\d+)", self.disk):
            raise ValueError("Nieobsługiwane urządzenie dyskowe")
        if not re.fullmatch(r"[a-z_][a-z0-9_-]{0,30}", self.username) or self.username in ("root", "nobody"):
            raise ValueError("Niepoprawna nazwa użytkownika")
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", self.hostname):
            raise ValueError("Niepoprawna nazwa komputera")
        if self.locale not in LOCALES or self.keymap not in ("pl", "us", "de"):
            raise ValueError("Nieobsługiwane locale lub klawiatura")
        if not re.fullmatch(r"[A-Za-z_+-]+(?:/[A-Za-z_+-]+){1,2}", self.timezone):
            raise ValueError("Niepoprawna strefa czasowa")
        if self.desktop not in DESKTOPS or self.shell not in ("bash", "zsh", "fish"):
            raise ValueError("Nieobsługiwane środowisko lub powłoka")
        if not self.kernels or len(set(self.kernels)) != len(self.kernels) or any(k not in KERNELS for k in self.kernels):
            raise ValueError("Niepoprawny wybór kernela")
        if self.bootloader not in ("grub", "systemd-boot"):
            raise ValueError("Nieobsługiwany bootloader")
        if self.firmware not in ("uefi", "bios"):
            raise ValueError("Nieobsługiwany tryb firmware")
        if self.firmware == "bios" and self.bootloader != "grub":
            raise ValueError("Legacy BIOS wymaga GRUB; systemd-boot obsługuje wyłącznie UEFI")
        if len(self.extras) > 100 or any(not re.fullmatch(r"[a-z0-9][a-z0-9@+_.-]*", p) for p in self.extras):
            raise ValueError("Niepoprawne nazwy dodatkowych pakietów")
        for name in ("zram", "bluetooth", "trim"):
            if type(getattr(self, name)) is not bool:
                raise ValueError("Niepoprawna opcja logiczna")

    def public(self):
        return asdict(self)

def validate_password(value):
    if not isinstance(value, str) or not 8 <= len(value) <= 1024 or any(c in value for c in "\r\n\x00:"):
        raise ValueError("Hasło: 8–1024 znaków, bez dwukropka i znaków sterujących")
