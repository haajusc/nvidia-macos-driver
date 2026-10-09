#!/usr/bin/env python3
"""Regression tests for legacy FAT32 1401 recovery without touching real disks."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "app/Resources/nullmoth-setup.sh").read_text()
START = SOURCE.index("remount_recorded_fat32() {")
END = SOURCE.index("\nowned_amfi_from_prior_record()", START)
FUNCTION = SOURCE[START:END]


class LegacyFat32Recovery(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.one = self.root / "usb1"
        self.two = self.root / "usb2"
        for d in (self.one, self.two):
            (d / "EFI/OC").mkdir(parents=True)
            (d / "EFI/OC/config.plist").write_text("valid")
            (d / "EFI/OC/config.plist.nullmoth-original").write_text("backup")

    def run_probe(self, candidates="disk2s1", missing_backup=False, label="1401"):
        if missing_backup:
            (self.one / "EFI/OC/config.plist.nullmoth-original").unlink()
        shell = r"""
CONFIG_PATH=/Volumes/1401/EFI/OC/config.plist
OCREL=EFI/OC
CONFIG_BACKUP_REL=EFI/OC/config.plist.nullmoth-original
MOUNT_POINT=''
note() { :; }
diskutil() {
  if [ "$1" = list ]; then
    for d in $CANDIDATES; do echo "1: DOS_FAT_32 1401 17GB $d"; done
  elif [ "$1" = info ]; then
    echo "Volume Name: $LABEL"
  fi
}
mount_efi() {
  if [ "$1" = disk2s1 ]; then MOUNT_POINT="$TEST_USB1";
  else MOUNT_POINT="$TEST_USB2"; fi
}
plutil() { [ "$1" = -lint ] && [ -f "$2" ]; }
""" + FUNCTION + """
remount_recorded_fat32
rc=$?
printf 'RESULT:%s:%s\n' "$rc" "${C:-unset}"
exit "$rc"
"""
        env = dict(os.environ, CANDIDATES=candidates, LABEL=label,
                   TEST_USB1=str(self.one), TEST_USB2=str(self.two))
        return subprocess.run(["bash", "-c", shell], env=env,
                              capture_output=True, text=True)

    def test_single_matching_usb(self):
        result = self.run_probe()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(self.one / "EFI/OC/config.plist"), result.stdout)

    def test_missing_original_backup_fails_closed(self):
        self.assertNotEqual(self.run_probe(missing_backup=True).returncode, 0)

    def test_ambiguous_matching_usb_fails_closed(self):
        self.assertNotEqual(self.run_probe(candidates="disk2s1 disk3s1").returncode, 0)

    def test_different_volume_label_fails_closed(self):
        self.assertNotEqual(self.run_probe(label="OTHER").returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
