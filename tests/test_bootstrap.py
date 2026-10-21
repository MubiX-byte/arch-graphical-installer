"""Exercise safe CLI paths; dependency installation is never invoked by tests."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

@unittest.skipUnless(sys.platform == "linux" and shutil.which("bash"), "Bash CLI on Linux")
class BootstrapTests(unittest.TestCase):
    def run_script(self, *args, env=None):
        return subprocess.run(["bash", str(ROOT / "run.sh"), *args], cwd=ROOT,
                              capture_output=True, text=True, timeout=10, env=env)

    def test_help_does_not_require_root_or_live_iso(self):
        result = self.run_script("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("bash run.sh", result.stdout)
        self.assertIn("Nie partycjonuje", result.stdout)

    def test_unknown_argument_rejected(self):
        result = self.run_script("--erase-everything")
        self.assertEqual(result.returncode, 2)

    def test_non_linux_platform_exits_before_installing_packages(self):
        with tempfile.TemporaryDirectory() as folder:
            fake_uname = Path(folder) / "uname"
            fake_uname.write_text("#!/bin/sh\nprintf 'NotLinux\\n'\n")
            fake_uname.chmod(0o755)
            sentinel = Path(folder) / "pacman-was-called"
            fake_pacman = Path(folder) / "pacman"
            fake_pacman.write_text(f"#!/bin/sh\ntouch '{sentinel}'\nexit 77\n")
            fake_pacman.chmod(0o755)
            env = os.environ | {"PATH": folder + os.pathsep + os.environ["PATH"]}
            result = self.run_script(env=env)
            self.assertEqual(result.returncode, 1)
            self.assertIn("Arch Linux Live ISO", result.stderr)
            self.assertFalse(sentinel.exists())

if __name__ == "__main__":
    unittest.main()
