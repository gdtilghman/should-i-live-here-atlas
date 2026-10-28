#!/usr/bin/env python3
"""Tests for the traffic safety data importer."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = REPO_ROOT / "work" / "traffic-source"
PREPARE = REPO_ROOT / "scripts" / "prepare-traffic.py"
CT_FIPS = {"09001", "09003", "09005", "09007", "09009", "09011", "09013", "09015"}


class TestTraffic(unittest.TestCase):
    @unittest.skipUnless(SOURCE_DIR.exists(), f"missing {SOURCE_DIR}")
    def test_import(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "traffic.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(PREPARE),
                    "--source-dir",
                    str(SOURCE_DIR),
                    "--out",
                    str(out),
                ],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
            )
            if proc.returncode != 0:
                self.fail(
                    f"importer failed:\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
                )
            self.assertTrue(out.is_file())

            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(len(data["datasets"]), 1)
            ds = data["datasets"][0]
            records = ds["records"]

            self.assertEqual(len(records), 3107)

            available = {k: v for k, v in records.items() if v["status"] == "available"}
            unavailable = {k: v for k, v in records.items() if v["status"] == "unavailable"}

            self.assertEqual(len(available), 3099)
            self.assertEqual(len(unavailable), 8)
            self.assertEqual(set(unavailable.keys()), CT_FIPS)

            zero_count = sum(1 for v in available.values() if v["value"] == 0.0)
            self.assertEqual(zero_count, 18)

            self.assertEqual(data["unknownCountyDeaths"], 10)

            def check(fips, deaths, population, value):
                rec = records[fips]
                self.assertEqual(rec["deaths"], deaths)
                self.assertEqual(rec["population"], population)
                self.assertEqual(rec["value"], value)

            check("06037", 4033, 9848406, 8.2)
            check("36061", 182, 1627788, 2.2)
            check("17031", 1900, 5185812, 7.3)
            check("12086", 1596, 2685296, 11.9)
            check("48301", 21, 54, 7777.8)

            self.assertGreaterEqual(records["46102"]["deaths"], 30)

    @unittest.skipUnless(SOURCE_DIR.exists(), f"missing {SOURCE_DIR}")
    def test_corrupted_source_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            corrupt_dir = tmp / "source"
            shutil.copytree(SOURCE_DIR, corrupt_dir)

            acs = corrupt_dir / "acsdt5y2023-b01003.dat"
            with open(acs, "ab") as f:
                f.write(b"x")

            out = tmp / "out.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(PREPARE),
                    "--source-dir",
                    str(corrupt_dir),
                    "--out",
                    str(out),
                ],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
