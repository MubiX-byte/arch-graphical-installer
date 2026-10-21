from dataclasses import dataclass
from .config import DESKTOPS

@dataclass(frozen=True)
class Step:
    label: str
    argv: tuple[str, ...]

def partition(disk, number):
    return f"{disk}{'p' if disk[-1].isdigit() else ''}{number}"

def packages(c, cpu="", pci=""):
    result = ["base", "linux-firmware", "e2fsprogs", "networkmanager", "sudo", "mesa", c.shell]
    result += c.kernels + [k + "-headers" for k in c.kernels]
    result += DESKTOPS[c.desktop][0]
    if c.desktop != "Minimal":
        result += ["pipewire", "pipewire-alsa", "pipewire-pulse", "wireplumber", "polkit", "firefox", "noto-fonts"]
    if "GenuineIntel" in cpu:
        result += ["intel-ucode", "vulkan-intel", "intel-media-driver"]
    elif "AuthenticAMD" in cpu:
        result += ["amd-ucode"]
    if "[1002:" in pci:
        result += ["vulkan-radeon", "libva-mesa-driver"]
    if c.bootloader == "grub":
        result += ["grub", "efibootmgr"]
    if c.zram:
        result += ["zram-generator"]
    if c.bluetooth:
        result += ["bluez", "bluez-utils"]
    return list(dict.fromkeys(result + c.extras))

def storage_plan(c, target="/mnt/arch-graphical-installer"):
    c.validate()
    esp, root = partition(c.disk, 1), partition(c.disk, 2)
    return [Step("Usunięcie tablicy partycji", ("sgdisk", "--zap-all", c.disk)),
            Step("GPT: EFI 2 GiB + root", ("sgdisk", "--clear", "--new=1:0:+2G", "--typecode=1:ef00", "--new=2:0:0", "--typecode=2:8300", c.disk)),
            Step("Odczyt nowej tablicy", ("partprobe", c.disk)),
            Step("Oczekiwanie na urządzenia", ("udevadm", "settle")),
            Step("Formatowanie EFI FAT32", ("mkfs.fat", "-F", "32", esp)),
            Step("Formatowanie root ext4", ("mkfs.ext4", "-F", root)),
            Step("Montowanie root", ("mount", root, target)),
            Step("Montowanie EFI", ("mount", "--mkdir", esp, target + "/boot"))]

def summary(c):
    c.validate()
    return {"warning": "WSZYSTKIE DANE NA WYBRANYM DYSKU ZOSTANĄ USUNIĘTE", "configuration": c.public(),
            "operations": [{"stage": s.label, "argv": list(s.argv)} for s in storage_plan(c)],
            "packages": packages(c), "root": "Konto root zablokowane; użytkownik ma sudo", "filesystem": "ext4"}
