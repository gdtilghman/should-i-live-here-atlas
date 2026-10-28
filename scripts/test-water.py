#!/usr/bin/env python3
"""Unit tests for scripts/prepare-water.py."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TEST_DIR)
IMPORTER = os.path.join(TEST_DIR, "prepare-water.py")
ZIP_PATH = os.path.join(REPO_ROOT, "work", "water-source", "SDWA_latest_downloads.zip")
GEO_PATH = os.path.join(REPO_ROOT, "dist", "data", "counties.geojson")


def load_importer():
    spec = importlib.util.spec_from_file_location("prepare_water", IMPORTER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


prepare_water = load_importer()


class PureFunctionTests(unittest.TestCase):
    def test_normalize_dona_ana(self):
        self.assertEqual(
            prepare_water.normalize_county_name("Doña Ana"),
            prepare_water.normalize_county_name("Doña Ana County"),
        )

    def test_normalize_st_louis(self):
        self.assertEqual(
            prepare_water.normalize_county_name("St. Louis"),
            "st louis",
        )

    def test_richmond_city_vs_county(self):
        self.assertNotEqual(
            prepare_water.normalize_county_name("Richmond city"),
            prepare_water.normalize_county_name("Richmond County"),
        )

    def test_lasalle_alias(self):
        self.assertEqual(
            prepare_water.normalize_county_name("La Salle", "LA"),
            prepare_water.normalize_county_name("LaSalle Parish", "LA"),
        )

    def test_shannon_alias(self):
        self.assertEqual(
            prepare_water.normalize_county_name("Shannon", "SD"),
            prepare_water.normalize_county_name("Oglala Lakota County", "SD"),
        )

    def test_overlap_rule(self):
        self.assertTrue(
            prepare_water.violation_overlaps_window("12/01/2022", "01/31/2023")
        )
        self.assertFalse(
            prepare_water.violation_overlaps_window("01/01/2022", "12/31/2022")
        )
        self.assertTrue(
            prepare_water.violation_overlaps_window("01/01/2020", "--->")
        )
        self.assertFalse(
            prepare_water.violation_overlaps_window("01/01/2026", "01/01/2027")
        )


class SlowImportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(ZIP_PATH):
            raise unittest.SkipTest(f"source zip not present: {ZIP_PATH}")
        if not os.path.exists(GEO_PATH):
            raise unittest.SkipTest(f"counties geojson not present: {GEO_PATH}")

        cls.tmpdir = tempfile.mkdtemp()
        cls.out_path = os.path.join(cls.tmpdir, "water.json")
        cmd = [
            sys.executable,
            IMPORTER,
            "--source",
            ZIP_PATH,
            "--geo",
            GEO_PATH,
            "--out",
            cls.out_path,
        ]
        subprocess.run(cmd, check=True, cwd=REPO_ROOT)

        with open(cls.out_path, encoding="utf-8") as f:
            cls.data = json.load(f)
        cls.records = cls.data["datasets"][0]["records"]

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "tmpdir"):
            shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_record_counts(self):
        self.assertEqual(len(self.records), 3107)

        available = [r for r in self.records.values() if r["status"] == "available"]
        unavailable = [r for r in self.records.values() if r["status"] == "unavailable"]

        self.assertEqual(len(available), 3057)
        self.assertEqual(len(unavailable), 50)

        zero_count = sum(1 for r in available if r["value"] == 0.0)
        self.assertEqual(zero_count, 958)

    def test_spot_records(self):
        spots = {
            "17031": (4.1, 5221530, 213274),
            "48201": (52.2, 5897137, 3080296),
            "36061": (100.0, 8271000, 8271000),
            "22059": (55.1, 19338, 10646),
            "01001": (0.0, 71034, 0),
            "46102": (0.0, 1398, 0),
        }
        for fips, (val, pop, pop_v) in spots.items():
            r = self.records[fips]
            self.assertEqual(r["status"], "available")
            self.assertEqual(r["value"], val)
            self.assertEqual(r["populationServed"], pop)
            self.assertEqual(r["populationWithViolation"], pop_v)

    def test_connecticut_counties_available(self):
        for fips in [
            "09001", "09003", "09005", "09007",
            "09009", "09011", "09013", "09015",
        ]:
            self.assertEqual(self.records[fips]["status"], "available")


if __name__ == "__main__":
    unittest.main()
