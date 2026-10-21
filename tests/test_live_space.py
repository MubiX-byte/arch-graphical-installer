"""Archiso overlay regressions; all mount operations are simulated."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GIB, MIB = 1024**3, 1024**2

@unittest.skipUnless(shutil.which("bash"), "Bash required for simulated resource checks")
class LiveSpaceTests(unittest.TestCase):
    def budget(self, *, required=2*GIB, memory=6*GIB, available=200*MIB,
               backing="tmpfs", options=None, after=None):
        options = options or "rw,upperdir=/run/archiso/cowspace/persistent/upperdir,workdir=/run/archiso/cowspace/workdir"
        with tempfile.TemporaryDirectory() as folder:
            trace = Path(folder) / "mounts"
            env = os.environ | {"TRACE": str(trace), "MEMORY": str(memory),
                "AVAILABLE": str(available), "BACKING": backing, "OPTIONS": options,
                "AFTER": str(required if after is None else after), "REQUIRED": str(required)}
            fixture = r'''
source scripts/live-space.sh
live_mem_available_bytes() { printf '%s\n' "$MEMORY"; }
live_df_bytes() {
  case "$2" in
    avail) if [[ -f $TRACE ]]; then printf '%s\n' "$AFTER"; else printf '%s\n' "$AVAILABLE"; fi ;;
    used) printf '%s\n' 58720256 ;;
    size) printf '%s\n' 268435456 ;;
  esac
}
findmnt() {
  if [[ ${*: -1} == FSTYPE ]]; then printf '%s\n' "$BACKING";
  else printf '%s\n' "$OPTIONS"; fi
}
mount() { printf '%s\n' "$*" >> "$TRACE"; }
live_ensure_space "$REQUIRED"
'''
            result = subprocess.run(["bash", "-euo", "pipefail", "-c", fixture],
                                    cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=10)
            return result, trace.read_text() if trace.exists() else ""

    def test_default_small_overlay_is_enlarged(self):
        result, mounts = self.budget()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(mounts, f"-o remount,size={56*MIB + 2*GIB} /run/archiso/cowspace\n")

    def test_low_ram_stops_before_remount(self):
        result, mounts = self.budget(memory=2*GIB)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("RAM", result.stderr)
        self.assertEqual(mounts, "")

    def test_enough_capacity_does_not_remount(self):
        result, mounts = self.budget(available=3*GIB)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(mounts, "")

    def test_large_limit_cannot_replace_missing_ram(self):
        result, mounts = self.budget(available=8*GIB, memory=2*GIB)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(mounts, "")

    def test_persistent_backing_is_never_resized(self):
        result, mounts = self.budget(backing="ext4")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(mounts, "")
        result, mounts = self.budget(backing="ext4", available=3*GIB, memory=512*MIB)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(mounts, "")

    def test_unrelated_tmpfs_is_never_resized(self):
        result, mounts = self.budget(options="rw,upperdir=/other/upper,workdir=/other/work")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(mounts, "")

    def test_capacity_is_rechecked_after_remount(self):
        result, mounts = self.budget(after=200*MIB)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("nadal brakuje", result.stderr)
        self.assertTrue(mounts)

    def test_installed_sizes_and_incomplete_metadata(self):
        for expected, data, success in (
            (3, "Installed Size  : 1.50 MiB\nInstalled Size  : 2.00 KiB\nInstalled Size : 10 B\n", True),
            (2, "Installed Size : 1.00 MiB\n", False),
            (1, "Installed Size : 1.00 Unknown\n", False),
        ):
            script = f"source scripts/live-space.sh; live_installed_bytes {expected}"
            result = subprocess.run(["bash", "-euo", "pipefail", "-c", script], input=data,
                                    cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=10)
            if success:
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(int(result.stdout), int(1.5*MIB + 2*1024 + 10))
            else:
                self.assertNotEqual(result.returncode, 0)

if __name__ == "__main__":
    unittest.main()
