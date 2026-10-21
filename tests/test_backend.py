"""Failure-path executor tests on Linux only; all disk commands are mocked."""
import sys
import unittest
from unittest.mock import patch
from pathlib import Path
import tempfile

@unittest.skipUnless(sys.platform == "linux", "Privileged Linux backend")
class BackendTests(unittest.TestCase):
    def installer(self):
        from arch_installer.backend import Installer
        from arch_installer.config import Config
        return Installer(Config(disk="/dev/vda", username="tester", fingerprint="old"), "secret123", "/dev/vda", lambda e: None)

    def test_replacement_blocks_disk(self):
        obj = self.installer()
        with patch("arch_installer.backend.disks", return_value=[]), self.assertRaises(RuntimeError):
            obj.check_disk()

    def test_no_command_if_confirmation_is_missing(self):
        obj = self.installer()
        obj.confirmation = ""
        with patch.object(obj, "run") as run, self.assertRaises(ValueError):
            obj.preflight()
        run.assert_not_called()

    def test_write_cannot_escape_target(self):
        obj = self.installer()
        with tempfile.TemporaryDirectory() as folder:
            with patch("arch_installer.backend.TARGET", Path(folder)), self.assertRaises(RuntimeError):
                obj.write("../escape.txt", "bad")

    def test_secret_never_appears_in_log(self):
        obj = self.installer()
        events = []
        obj.emit = events.append
        output = obj.run(["/usr/bin/cat"], input_text="secret123", secret=True)
        self.assertEqual(output, "secret123")
        self.assertNotIn("secret123", str(events))

    def test_command_failure_stops_execution(self):
        obj = self.installer()
        with self.assertRaises(RuntimeError):
            obj.run(["/usr/bin/false"])

    def test_systemd_boot_uses_target_and_host_namespace(self):
        obj = self.installer()
        obj.c.bootloader = "systemd-boot"
        commands = []
        def run(argv, **kwargs):
            commands.append(argv)
            return "aabb-1234\n" if argv[0] == "blkid" else ""
        with patch.object(obj, "run", side_effect=run), patch.object(obj, "write"):
            obj.bootloader()
        self.assertEqual(commands[0][0], "bootctl")
        self.assertIn("--variables=yes", commands[0])
        self.assertIn("--install-source=image", commands[0])

    def test_bios_grub_targets_entire_disk(self):
        obj = self.installer()
        obj.c.firmware = "bios"
        with patch.object(obj, "chroot") as chroot:
            obj.bootloader()
        self.assertEqual(chroot.call_args_list[0].args,
                         ("grub-install", "--target=i386-pc", "/dev/vda"))
        self.assertEqual(chroot.call_args_list[1].args,
                         ("grub-mkconfig", "-o", "/boot/grub/grub.cfg"))

    def test_pacstrap_failure_cleans_mounts_and_never_bootloads(self):
        obj = self.installer()
        obj.package_list = ["base", "linux"]
        commands, events = [], []
        obj.emit = events.append
        def run(argv, **kwargs):
            commands.append(argv)
            if argv[0] == "pacstrap":
                raise RuntimeError("test failure")
            return ""
        with tempfile.TemporaryDirectory() as folder:
            with patch("arch_installer.backend.TARGET", Path(folder)), \
                 patch("arch_installer.backend.open"), \
                 patch("arch_installer.backend.fcntl.flock"), \
                 patch("arch_installer.backend.signal.signal"), \
                 patch.object(obj, "preflight"), patch.object(obj, "check_disk"), \
                 patch.object(obj, "run", side_effect=run), patch.object(obj, "bootloader") as boot:
                with self.assertRaisesRegex(RuntimeError, "test failure"):
                    obj.execute()
        boot.assert_not_called()
        self.assertEqual(commands[-1][0], "umount")
        self.assertFalse(any(e["kind"] == "success" for e in events))
        self.assertEqual(obj.password, "")

    def test_unmount_failure_never_reports_success(self):
        obj = self.installer()
        obj.package_list = ["base", "linux"]
        events = []
        obj.emit = events.append
        def run(argv, **kwargs):
            if argv[0] == "umount":
                raise RuntimeError("busy target")
            return ""
        with tempfile.TemporaryDirectory() as folder:
            with patch("arch_installer.backend.TARGET", Path(folder)), \
                 patch("arch_installer.backend.open"), \
                 patch("arch_installer.backend.fcntl.flock"), \
                 patch("arch_installer.backend.signal.signal"), \
                 patch.object(obj, "preflight"), patch.object(obj, "check_disk"), \
                 patch.object(obj, "configure"), patch.object(obj, "bootloader"), \
                 patch.object(obj, "verify"), patch.object(obj, "run", side_effect=run):
                with self.assertRaisesRegex(RuntimeError, "busy target"):
                    obj.execute()
        self.assertFalse(any(e["kind"] == "success" for e in events))

if __name__ == "__main__":
    unittest.main()
