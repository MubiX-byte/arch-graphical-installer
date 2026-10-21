import hashlib
import json
import platform
import subprocess
from pathlib import Path
from urllib.request import urlopen

def query(argv):
    return subprocess.run(argv, check=True, capture_output=True, text=True, timeout=30).stdout

def disks():
    data = json.loads(query(["lsblk", "--json", "--bytes", "--paths", "--output", "NAME,TYPE,SIZE,MODEL,SERIAL,WWN,RO,RM,ROTA,FSTYPE,MOUNTPOINTS,UUID"]))
    return [d for d in data["blockdevices"] if d["type"] == "disk"]

def fingerprint(d):
    return hashlib.sha256(json.dumps({k: d.get(k) for k in ("name", "size", "model", "serial", "wwn")}, sort_keys=True).encode()).hexdigest()

def descendants(d):
    yield d
    for child in d.get("children", []):
        yield from descendants(child)

def eligible(d):
    if d.get("ro") or d.get("rm") or int(d["size"]) < 32 * 1024**3:
        return False
    for node in descendants(d):
        if node.get("type") not in ("disk", "part") or any(node.get("mountpoints") or []):
            return False
        if list(Path("/sys/class/block", Path(node["name"]).name, "holders").glob("*")):
            return False
    return True

def internet():
    with urlopen("https://geo.mirror.pkgbuild.com/core/os/x86_64/core.db", timeout=20) as response:
        if response.status != 200 or not response.read(1024):
            raise RuntimeError("Repozytorium Arch Linux jest niedostępne")

def validate_firmware(mode, efi_root=Path("/sys/firmware/efi")):
    actual = "uefi" if efi_root.is_dir() else "bios"
    if mode != actual:
        raise RuntimeError("Tryb firmware nie zgadza się z zatwierdzonym planem. Utwórz plan ponownie.")
    if mode == "bios":
        return
    if not (efi_root / "efivars").is_dir():
        raise RuntimeError("UEFI wykryte, ale zmienne EFI są niedostępne; nie przełączam na BIOS")
    if (efi_root / "fw_platform_size").read_text().strip() != "64":
        raise RuntimeError("Wymagany 64-bitowy firmware UEFI")
    secure = list((efi_root / "efivars").glob("SecureBoot-*"))
    if not secure or secure[0].read_bytes()[4:5] != b"\x00":
        raise RuntimeError("Nie można potwierdzić wyłączenia Secure Boot")

def inspect():
    if platform.system() != "Linux":
        return {"error": "Instalacja wymaga Arch Linux Live ISO", "disks": []}
    memory = next(line for line in Path("/proc/meminfo").read_text().splitlines() if line.startswith("MemTotal:"))
    return {"architecture": platform.machine(), "uefi": Path("/sys/firmware/efi").exists(),
            "memory": memory, "cpu": query(["lscpu"]), "pci": query(["lspci", "-nnk"]),
            "usb": query(["lsusb"]), "disks": disks(),
            "network": query(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device"])}
