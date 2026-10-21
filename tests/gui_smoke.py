"""Run after installing PySide6: QT_QPA_PLATFORM=offscreen python tests/gui_smoke.py."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from arch_installer.gui import Window

app = QApplication([])
window = Window()
window.probe.wait(120000)
app.processEvents()
assert window.pages.count() == 4
window.navigate(1)
assert window.pages.currentIndex() == 1
window.probed({"disks": [{"name": "/dev/vda", "type": "disk", "size": 48 * 1024**3, "serial": "test"}], "cpu": "GenuineIntel"})
window.username.setText("tester")
window.password.setText("safe-test-password")
window.repeat.setText("safe-test-password")
window.navigate(1)
assert window.pages.currentIndex() == 2
assert "safe-test-password" not in window.review.toPlainText()
assert "sgdisk" in window.review.toPlainText()
window.toggle_theme()
window.pages.setCurrentIndex(1)
window.disk.clear()
window.probed({"uefi": False, "disks": [{"name": "/dev/vda", "type": "disk", "size": 48 * 1024**3, "serial": "bios-test"}]})
assert window.bootloader.count() == 1
assert window.bootloader.currentText() == "grub"
window.navigate(1)
assert window.approved_config.firmware == "bios"
assert "ef02" in window.review.toPlainText()
assert "mkfs.fat" not in window.review.toPlainText()
window.close()
print("GUI smoke: PASS")
