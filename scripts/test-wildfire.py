#!/usr/bin/env python3
"""Tests for scripts/prepare-wildfire.py against the real Wildfire Risk to Communities workbook."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE = REPO_ROOT / "work/wildfire-source/wrc_download_20260415.xlsx"
PREPARE = REPO_ROOT / "scripts" / "prepare-wildfire.py"

CT_FIPS = {"09001", "09003", "09005", "09007", "09009", "09011", "09013", "09015"}

SPOT_VALUES = {
    "06037": {"risk-to-homes": 98.5, "likelihood": 96.7},
    "16001": {"risk-to-homes": 98.5, "likelihood": 99.1},
    "30063": {"risk-to-homes": 96.1, "likelihood": 95.8},
    "36061": {"risk-to-homes": 14.5, "likelihood": 14.5},
}


def run_importer(*args):
    return subprocess.run(
        [sys.executable, str(PREPARE), *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )


SOURCE_MISSING_MSG = f"source workbook not found at {SOURCE}"


@unittest.skipUnless(SOURCE.is_file(), SOURCE_MISSING_MSG)
class TestWildfireOutput(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp(prefix="wildfire-test-")
        cls.out_path = Path(cls.tmpdir) / "wildfire.json"
        proc = run_importer("--out", str(cls.out_path))
        if proc.returncode != 0:
            raise RuntimeError(
                "prepare-wildfire.py failed\n"
                f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
            )
        cls.data = json.loads(cls.out_path.read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_dataset_ids_and_order(self):
        ids = [d["id"] for d in self.data["datasets"]]
        self.assertEqual(ids, ["risk-to-homes", "likelihood"])

    def test_record_counts(self):
        for ds in self.data["datasets"]:
            records = ds["records"]
            self.assertEqual(len(records), 3107, ds["id"])
            available = [r for r in records.values() if r["status"] == "available"]
            unavailable = [r for r in records.values() if r["status"] == "unavailable"]
            self.assertEqual(len(available), 3099, ds["id"])
            self.assertEqual(len(unavailable), 8, ds["id"])
            self.assertEqual(
                {fips for fips, r in records.items() if r["status"] == "unavailable"},
                CT_FIPS,
                ds["id"],
            )

    def test_available_values_in_range(self):
        for ds in self.data["datasets"]:
            for fips, rec in ds["records"].items():
                if rec["status"] == "available":
                    self.assertIsInstance(rec["value"], (int, float))
                    self.assertGreaterEqual(rec["value"], 0.0, fips)
                    self.assertLessEqual(rec["value"], 100.0, fips)

    def test_spot_values(self):
        by_id = {d["id"]: d["records"] for d in self.data["datasets"]}
        for fips, expected in SPOT_VALUES.items():
            for dataset_id, value in expected.items():
                rec = by_id[dataset_id][fips]
                self.assertEqual(rec["status"], "available", f"{dataset_id} {fips}")
                self.assertAlmostEqual(rec["value"], value, places=6,
                                       msg=f"{dataset_id} {fips}")


@unittest.skipUnless(SOURCE.is_file(), SOURCE_MISSING_MSG)
class TestWrongShaAborts(unittest.TestCase):
    def test_wrong_sha_aborts_without_output(self):
        with tempfile.TemporaryDirectory(prefix="wildfire-sha-test-") as tmpdir:
            bad_source = Path(tmpdir) / "bad.xlsx"
            shutil.copyfile(SOURCE, bad_source)
            with open(bad_source, "ab") as f:
                f.write(b"\x00")

            out_path = Path(tmpdir) / "wildfire.json"
            proc = run_importer(
                "--source", str(bad_source),
                "--out", str(out_path),
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertFalse(out_path.exists(), "output must not be written on SHA mismatch")


if __name__ == "__main__":
    unittest.main()
