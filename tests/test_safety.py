import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
from arch_installer.config import Config, validate_password, DESKTOPS, KERNELS
from arch_installer.hardware import eligible, fingerprint
from arch_installer.plan import storage_plan, packages, partition, summary

class SafetyTests(unittest.TestCase):
    def config(self, **kwargs):
        return Config(**({"disk": "/dev/nvme0n1", "username": "tester"} | kwargs))

    def test_disk_device_injection_rejected(self):
        for disk in ("/dev/sda;reboot", "/dev/sda1", "--help", "/dev/mapper/root", "/tmp/disk", "/dev/../dev/sda"):
            with self.subTest(disk=disk), self.assertRaises(ValueError):
                self.config(disk=disk).validate()

    def test_configuration_injection_rejected(self):
        for data in ({"username": "root"}, {"hostname": "a\nb"}, {"timezone": "../../etc"},
                     {"extras": ["--overwrite=*"]}, {"extras": ["x;reboot"]},
                     {"kernels": ["linux", "linux"]}, {"kernels": []},
                     {"desktop": "Hyprland"}, {"bootloader": "bios"}, {"zram": "false"}):
            with self.subTest(data=data), self.assertRaises(ValueError):
                self.config(**data).validate()

    def test_password_protocol(self):
        validate_password("zażółć Test 123!")
        for value in ("short", "a" * 7 + "\n", "password:root", "bad\x00value"):
            with self.assertRaises(ValueError):
                validate_password(value)

    def test_nvme_and_sata_partition_names(self):
        self.assertEqual(partition("/dev/nvme0n1", 2), "/dev/nvme0n1p2")
        self.assertEqual(partition("/dev/sda", 2), "/dev/sda2")

    def test_bios_plan_reserves_unformatted_embedding_partition(self):
        c = self.config(firmware="bios")
        steps = storage_plan(c)
        table = next(s.argv for s in steps if "--clear" in s.argv)
        self.assertIn("--typecode=1:ef02", table)
        self.assertIn("--new=1:0:+2M", table)
        self.assertFalse(any(s.argv[0] == "mkfs.fat" for s in steps))
        formatting = [s.argv for s in steps if s.argv[0].startswith("mkfs")]
        self.assertEqual(formatting, [("mkfs.ext4", "-F", "/dev/nvme0n1p2")])
        self.assertEqual([s.argv for s in steps if s.argv[0] == "mount"],
                         [("mount", "/dev/nvme0n1p2", "/mnt/arch-graphical-installer")])
        self.assertIn("grub", packages(c))
        self.assertNotIn("efibootmgr", packages(c))

    def test_systemd_boot_is_rejected_on_bios(self):
        with self.assertRaisesRegex(ValueError, "Legacy BIOS wymaga GRUB"):
            storage_plan(self.config(firmware="bios", bootloader="systemd-boot"))

    def test_no_commands_during_plan(self):
        with patch("subprocess.run", side_effect=AssertionError("side effect")):
            result = summary(self.config())
        commands = result["operations"]
        self.assertEqual(commands[0]["argv"], ["sgdisk", "--zap-all", "/dev/nvme0n1"])
        self.assertEqual(len([x for x in commands if x["argv"][0].startswith("mkfs")]), 2)
        self.assertNotIn("password", json.dumps(result))

    def test_busy_child_and_device_mapper_rejected(self):
        d = {"name": "/dev/vda", "size": 48 * 1024**3, "type": "disk", "children": [
            {"name": "/dev/vda1", "type": "part", "mountpoints": ["/"]}]}
        self.assertFalse(eligible(d))
        d["children"][0]["mountpoints"] = []
        d["children"][0]["type"] = "crypt"
        self.assertFalse(eligible(d))
        d["children"][0]["type"] = "part"
        d["rm"] = True
        self.assertFalse(eligible(d))

    def test_disk_identity_tracks_replacement(self):
        a = {"name": "/dev/vda", "size": 123, "serial": "first"}
        self.assertNotEqual(fingerprint(a), fingerprint(a | {"serial": "second"}))

    def test_all_desktops_and_kernels_have_packages(self):
        for desktop in DESKTOPS:
            for kernel in KERNELS:
                c = self.config(desktop=desktop, kernels=[kernel])
                c.validate()
                result = packages(c, "GenuineIntel")
                self.assertIn(kernel, result)
                self.assertIn(kernel + "-headers", result)
                self.assertIn("intel-ucode", result)
                self.assertIn("networkmanager", result)

    def test_dry_run_cli_works_without_qt_or_linux(self):
        result = subprocess.run([sys.executable, "main.py", "--dry-run", "examples/config.json"],
                                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("operations", json.loads(result.stdout))

if __name__ == "__main__":
    unittest.main()
