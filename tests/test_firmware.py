from pathlib import Path
import tempfile
import unittest
from arch_installer.hardware import validate_firmware

class FirmwareTests(unittest.TestCase):
    def test_bios_needs_no_efi_variables(self):
        with tempfile.TemporaryDirectory() as folder:
            validate_firmware("bios", Path(folder) / "missing-efi")

    def test_firmware_change_invalidates_plan(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(RuntimeError, "zatwierdzonym planem"):
                validate_firmware("uefi", Path(folder) / "missing-efi")
            with self.assertRaisesRegex(RuntimeError, "zatwierdzonym planem"):
                validate_firmware("bios", Path(folder))

    def test_uefi_without_variables_is_not_treated_as_bios(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(RuntimeError, "zmienne EFI"):
                validate_firmware("uefi", Path(folder))

    def test_uefi_secure_boot_checks_remain_enforced(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "efivars").mkdir()
            (root / "fw_platform_size").write_text("64\n")
            flag = root / "efivars/SecureBoot-test"
            flag.write_bytes(b"\x07\x00\x00\x00\x00")
            validate_firmware("uefi", root)
            flag.write_bytes(b"\x07\x00\x00\x00\x01")
            with self.assertRaisesRegex(RuntimeError, "Secure Boot"):
                validate_firmware("uefi", root)
