#!/usr/bin/env python3
"""Tests for scripts/prepare-air.py."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import os
import pathlib
import tempfile
import unittest


_SCRIPT_PATH = (
    pathlib.Path(__file__).resolve().parent / "prepare-air.py"
)
_spec = importlib.util.spec_from_file_location("prepare_air", _SCRIPT_PATH)
prep = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prep)


class AirImporterTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name)
        self._orig_source_files = dict(prep.SOURCE_FILES)

    def tearDown(self):
        self._tmp.cleanup()
        prep.SOURCE_FILES = self._orig_source_files

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _write_counties_geojson(self, fips_list):
        """Write a minimal GeoJSON with the given FIPS codes."""
        features = [
            {
                "type": "Feature",
                "properties": {"fips": fips, "name": f"County {fips}"},
            }
            for fips in fips_list
        ]
        geo = {"type": "FeatureCollection", "features": features}
        path = self.root / "counties.geojson"
        path.write_text(json.dumps(geo), encoding="utf-8")
        return path

    def _write_annual_csv(self, rows):
        """Write a PM2.5 annual CSV with the given rows."""
        fieldnames = [
            "year",
            "statefips",
            "countyfips",
            "pop_mean",
            "area_mean",
            "days",
            "rows",
        ]
        path = self.root / "county-annual-2018-2022.csv"
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def _write_daily_csv(self, rows):
        """Write a PM2.5 daily sample CSV with the given rows."""
        fieldnames = [
            "year",
            "date",
            "statefips",
            "countyfips",
            "pm25_pop_pred",
            "pm25_mean_pred",
        ]
        path = self.root / "sample-daily-2020-2022.csv"
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def _write_query_urls(self):
        (self.root / "query-url.txt").write_text(
            "https://data.cdc.gov/resource/53mz-4zqd.csv", encoding="utf-8"
        )
        (self.root / "sample-daily-query-url.txt").write_text(
            "https://data.cdc.gov/resource/53mz-4zqd.csv", encoding="utf-8"
        )

    def _write_acquired_at(self, timestamp="2026-09-29T04:04:55Z"):
        path = self.root / "acquired-at.txt"
        path.write_text(timestamp, encoding="utf-8")
        return path

    def _prepare_synthetic(self, fips_list, annual_rows, daily_rows=None):
        """Set up synthetic files and call prepare.build()."""
        if daily_rows is None:
            daily_rows = []
        self._write_counties_geojson(fips_list)
        annual_path = self._write_annual_csv(annual_rows)
        daily_path = self._write_daily_csv(daily_rows)
        self._write_query_urls()
        self._write_acquired_at()

        # Override SOURCE_FILES with actual hashes
        prep.SOURCE_FILES = {
            "county-annual-2018-2022.csv": prep.sha256_file(annual_path),
            "sample-daily-2020-2022.csv": prep.sha256_file(daily_path),
        }

        return prep.build(str(self.root), str(self.root / "counties.geojson"))

    def _annual_row(self, year, fips_state, fips_county, pop_mean, area_mean, days, rows):
        return {
            "year": str(year),
            "statefips": str(fips_state),
            "countyfips": str(fips_county),
            "pop_mean": str(pop_mean) if pop_mean is not None else "",
            "area_mean": str(area_mean) if area_mean is not None else "",
            "days": str(days),
            "rows": str(rows),
        }

    def _daily_row(self, year, date, fips_state, fips_county, pm25_pop_pred, pm25_mean_pred):
        return {
            "year": str(year),
            "date": date,
            "statefips": str(fips_state),
            "countyfips": str(fips_county),
            "pm25_pop_pred": str(pm25_pop_pred) if pm25_pop_pred is not None else "",
            "pm25_mean_pred": str(pm25_mean_pred) if pm25_mean_pred is not None else "",
        }

    def _get_record(self, payload, fips):
        return payload["datasets"][0]["records"][fips]

    # ------------------------------------------------------------------
    # fixture tests - happy path
    # ------------------------------------------------------------------

    def test_happy_path_shape(self):
        annual = [
            self._annual_row(2020, 1, 1, 8.10, 10.0, 366, 366),
            self._annual_row(2021, 1, 1, 8.20, 10.0, 365, 365),
            self._annual_row(2022, 1, 1, 8.30, 10.0, 365, 365),
        ]
        payload, _ = self._prepare_synthetic(["01001"], annual)

        self.assertIsInstance(payload, dict)
        self.assertIn("datasets", payload)
        self.assertEqual(len(payload["datasets"]), 1)

        ds = payload["datasets"][0]
        self.assertIn("id", ds)
        self.assertEqual(ds["id"], "pm25-2020-2022")
        self.assertIn("records", ds)

        rec = self._get_record(payload, "01001")
        self.assertEqual(rec["status"], "available")
        self.assertEqual(rec["value"], 8.2)
        self.assertEqual(rec["annual"], {"2020": 8.1, "2021": 8.2, "2022": 8.3})
        self.assertIsNone(rec["reason"])

    def test_rounding_unrounded_mean(self):
        """Value = round(mean of UNROUNDED values), not round of rounded mean.

        Example: unrounded mean of (1.004, 1.004, 1.008) is 1.005333...
        which rounds to 1.01. But if rounded first to (1.00, 1.00, 1.01)
        then averaged, we get 1.00333... which rounds to 1.00.
        This test ensures we use the correct method (unrounded mean).
        """
        annual = [
            self._annual_row(2020, 1, 1, 1.004, 10.0, 366, 366),
            self._annual_row(2021, 1, 1, 1.004, 10.0, 365, 365),
            self._annual_row(2022, 1, 1, 1.008, 10.0, 365, 365),
        ]
        payload, _ = self._prepare_synthetic(["01001"], annual)

        rec = self._get_record(payload, "01001")
        # Correct: round(mean(1.004, 1.004, 1.008)) = round(1.00533...) = 1.01
        # Wrong (double rounding): round(mean(round(1.004), round(1.004), round(1.008)))
        #                        = round(mean(1.00, 1.00, 1.01)) = round(1.00333...) = 1.00
        self.assertEqual(rec["value"], 1.01,
                         "value must be computed from unrounded mean, not rounded mean")
        self.assertEqual(rec["annual"]["2020"], 1.00)
        self.assertEqual(rec["annual"]["2021"], 1.00)
        self.assertEqual(rec["annual"]["2022"], 1.01)

    # ------------------------------------------------------------------
    # fixture tests - unavailable
    # ------------------------------------------------------------------

    def test_no_rows_unavailable(self):
        payload, _ = self._prepare_synthetic(["01001"], [])

        rec = self._get_record(payload, "01001")
        self.assertEqual(rec["status"], "unavailable")
        self.assertIsNone(rec["value"])
        self.assertIn("no 2020", rec["reason"])

    def test_blank_pop_mean_unavailable(self):
        annual = [
            self._annual_row(2020, 1, 1, None, 10.0, 366, 366),
            self._annual_row(2021, 1, 1, 8.20, 10.0, 365, 365),
            self._annual_row(2022, 1, 1, 8.30, 10.0, 365, 365),
        ]
        payload, _ = self._prepare_synthetic(["01001"], annual)

        rec = self._get_record(payload, "01001")
        self.assertEqual(rec["status"], "unavailable")
        self.assertIsNone(rec["value"])
        self.assertIn("weighted to where people live", rec["reason"])

    def test_missing_year_blank_reason(self):
        annual = [
            self._annual_row(2020, 1, 1, 8.10, 10.0, 366, 366),
            self._annual_row(2021, 1, 1, 8.20, 10.0, 365, 365),
        ]
        payload, _ = self._prepare_synthetic(["01001"], annual)

        rec = self._get_record(payload, "01001")
        self.assertEqual(rec["status"], "unavailable")
        self.assertIn("weighted to where people live", rec["reason"])

    # ------------------------------------------------------------------
    # fixture tests - validation failures
    # ------------------------------------------------------------------

    def test_partial_days_fail(self):
        annual = [
            self._annual_row(2020, 1, 1, 8.10, 10.0, 365, 365),
            self._annual_row(2021, 1, 1, 8.20, 10.0, 365, 365),
            self._annual_row(2022, 1, 1, 8.30, 10.0, 365, 365),
        ]
        with self.assertRaises(ValueError) as ctx:
            self._prepare_synthetic(["01001"], annual)
        self.assertIn("invalid days", str(ctx.exception))

    def test_days_rows_mismatch_fail(self):
        annual = [
            self._annual_row(2020, 1, 1, 8.10, 10.0, 366, 365),
            self._annual_row(2021, 1, 1, 8.20, 10.0, 365, 365),
            self._annual_row(2022, 1, 1, 8.30, 10.0, 365, 365),
        ]
        with self.assertRaises(ValueError) as ctx:
            self._prepare_synthetic(["01001"], annual)
        self.assertIn("invalid days", str(ctx.exception))

    def test_wrong_sha256_fails_closed(self):
        annual = [
            self._annual_row(2020, 1, 1, 8.10, 10.0, 366, 366),
            self._annual_row(2021, 1, 1, 8.20, 10.0, 365, 365),
            self._annual_row(2022, 1, 1, 8.30, 10.0, 365, 365),
        ]
        self._write_counties_geojson(["01001"])
        annual_path = self._write_annual_csv(annual)
        daily_path = self._write_daily_csv([])
        self._write_query_urls()
        self._write_acquired_at()

        prep.SOURCE_FILES = {
            "county-annual-2018-2022.csv": "0" * 64,
            "sample-daily-2020-2022.csv": "0" * 64,
        }

        with self.assertRaises(ValueError) as ctx:
            prep.build(str(self.root), str(self.root / "counties.geojson"))
        self.assertIn("hash mismatch", str(ctx.exception))

    def test_duplicate_fail(self):
        annual = [
            self._annual_row(2020, 1, 1, 8.10, 10.0, 366, 366),
            self._annual_row(2020, 1, 1, 8.10, 10.0, 366, 366),
            self._annual_row(2021, 1, 1, 8.20, 10.0, 365, 365),
            self._annual_row(2022, 1, 1, 8.30, 10.0, 365, 365),
        ]
        with self.assertRaises(ValueError) as ctx:
            self._prepare_synthetic(["01001"], annual)
        self.assertIn("duplicate", str(ctx.exception))

    def test_sample_count_mismatch_fail(self):
        annual = [
            self._annual_row(2020, 1, 1, 8.10, 10.0, 1, 1),
            self._annual_row(2021, 1, 1, 8.20, 10.0, 365, 365),
            self._annual_row(2022, 1, 1, 8.30, 10.0, 365, 365),
        ]
        daily = [
            self._daily_row(2020, "2020-01-01", 1, 1, 8.10, 8.0),
            self._daily_row(2020, "2020-01-02", 1, 1, 8.10, 8.0),
        ]
        with self.assertRaises(ValueError) as ctx:
            self._prepare_synthetic(["01001"], annual, daily)
        self.assertIn("non-blank daily", str(ctx.exception))

    def test_sample_mean_mismatch_fail(self):
        annual = [
            self._annual_row(2020, 1, 1, 8.10, 10.0, 1, 1),
            self._annual_row(2021, 1, 1, 8.20, 10.0, 365, 365),
            self._annual_row(2022, 1, 1, 8.30, 10.0, 365, 365),
        ]
        daily = [
            self._daily_row(2020, "2020-01-01", 1, 1, 9.99, 8.0),
        ]
        with self.assertRaises(ValueError) as ctx:
            self._prepare_synthetic(["01001"], annual, daily)
        self.assertIn("daily mean", str(ctx.exception))

    # ------------------------------------------------------------------
    # fixture tests - output structure and unicode
    # ------------------------------------------------------------------

    def test_output_structure(self):
        annual = [
            self._annual_row(2020, 1, 1, 8.10, 10.0, 366, 366),
            self._annual_row(2021, 1, 1, 8.20, 10.0, 365, 365),
            self._annual_row(2022, 1, 1, 8.30, 10.0, 365, 365),
        ]
        payload, _ = self._prepare_synthetic(["01001"], annual)

        for key in (
            "source",
            "sourceUrl",
            "datasetUrl",
            "license",
            "receivedAt",
            "sourceFiles",
            "citation",
            "note",
            "datasets",
        ):
            self.assertIn(key, payload)

        ds = payload["datasets"][0]
        for key in (
            "id",
            "title",
            "unit",
            "period",
            "method",
            "direction",
            "category",
            "min",
            "max",
            "records",
        ):
            self.assertIn(key, ds)

    def test_no_mojibake(self):
        """No string in the output JSON contains U+FFFD (replacement character)."""
        annual = [
            self._annual_row(2020, 1, 1, 8.10, 10.0, 366, 366),
            self._annual_row(2021, 1, 1, 8.20, 10.0, 365, 365),
            self._annual_row(2022, 1, 1, 8.30, 10.0, 365, 365),
        ]
        payload, _ = self._prepare_synthetic(["01001"], annual)

        def has_replacement(obj, path=""):
            if isinstance(obj, str):
                if "�" in obj:
                    raise AssertionError(f"U+FFFD found at {path}: {obj!r}")
            elif isinstance(obj, dict):
                for k, v in obj.items():
                    has_replacement(v, f"{path}.{k}")
            elif isinstance(obj, list):
                for i, v in enumerate(obj):
                    has_replacement(v, f"{path}[{i}]")

        has_replacement(payload)

    def test_exact_unit_string(self):
        """Unit field must be exactly 'µg/m³, population-weighted annual mean'."""
        annual = [
            self._annual_row(2020, 1, 1, 8.10, 10.0, 366, 366),
            self._annual_row(2021, 1, 1, 8.20, 10.0, 365, 365),
            self._annual_row(2022, 1, 1, 8.30, 10.0, 365, 365),
        ]
        payload, _ = self._prepare_synthetic(["01001"], annual)

        ds = payload["datasets"][0]
        expected_unit = "µg/m³, population-weighted annual mean"
        self.assertEqual(ds["unit"], expected_unit,
                         f"unit mismatch: got {ds['unit']!r}, expected {expected_unit!r}")

    def test_exact_period_string(self):
        """Period field must be exactly '2020–2022 average'."""
        annual = [
            self._annual_row(2020, 1, 1, 8.10, 10.0, 366, 366),
            self._annual_row(2021, 1, 1, 8.20, 10.0, 365, 365),
            self._annual_row(2022, 1, 1, 8.30, 10.0, 365, 365),
        ]
        payload, _ = self._prepare_synthetic(["01001"], annual)

        ds = payload["datasets"][0]
        expected_period = "2020–2022 average"
        self.assertEqual(ds["period"], expected_period,
                         f"period mismatch: got {ds['period']!r}, expected {expected_period!r}")

    def test_reason_strings_have_endash(self):
        """Unavailable reason strings must contain '2020–2022' with en-dash."""
        self.assertIn("–", prep.REASON_NO_ROWS)
        self.assertIn("2020–2022", prep.REASON_NO_ROWS)
        self.assertIn("–", prep.REASON_BLANK)
        self.assertIn("2020–2022", prep.REASON_BLANK)

    def test_fips_padding(self):
        annual = [
            self._annual_row(2020, 6, 37, 8.10, 10.0, 366, 366),
            self._annual_row(2021, 6, 37, 8.20, 10.0, 365, 365),
            self._annual_row(2022, 6, 37, 8.30, 10.0, 365, 365),
        ]
        payload, _ = self._prepare_synthetic(["06037"], annual)

        self.assertIn("06037", payload["datasets"][0]["records"])
        rec = self._get_record(payload, "06037")
        self.assertEqual(rec["status"], "available")

    def test_existing_output_preserved_on_failure(self):
        out_path = self.root / "out.json"
        out_path.write_text(json.dumps({"test": True}), encoding="utf-8")

        annual = [
            self._annual_row(2020, 1, 1, 8.10, 10.0, 366, 366),
        ]
        self._write_counties_geojson(["01001"])
        annual_path = self._write_annual_csv(annual)
        daily_path = self._write_daily_csv([])
        self._write_query_urls()
        self._write_acquired_at()

        prep.SOURCE_FILES = {
            "county-annual-2018-2022.csv": "0" * 64,
            "sample-daily-2020-2022.csv": "0" * 64,
        }

        with self.assertRaises(ValueError):
            prep.build(str(self.root), str(self.root / "counties.geojson"))
            prep.atomic_write_json(str(out_path), {})

        existing = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertEqual(existing, {"test": True})

    # ------------------------------------------------------------------
    # real-source test
    # ------------------------------------------------------------------

    def test_real_source_matches_atlas_and_samples(self):
        repo_root = pathlib.Path(__file__).resolve().parent.parent
        source_dir = repo_root / "work" / "air-quality-source"
        atlas_path = repo_root / "dist" / "data" / "counties.geojson"

        if not source_dir.exists():
            self.skipTest("real source not available")
        if not atlas_path.exists():
            self.skipTest("atlas not available")

        payload, audit = prep.build(str(source_dir), str(atlas_path))

        self.assertEqual(len(payload["datasets"]), 1)
        records = payload["datasets"][0]["records"]
        self.assertEqual(len(records), 3107)

        available = sum(1 for r in records.values() if r["status"] == "available")
        unavailable = sum(1 for r in records.values() if r["status"] == "unavailable")

        self.assertEqual(available, 3053)
        self.assertEqual(unavailable, 54)

        # Verify specific unavailable cases
        no_rows = sum(
            1
            for r in records.values()
            if r["status"] == "unavailable" and "no 2020" in (r["reason"] or "")
        )
        blank = sum(
            1
            for r in records.values()
            if r["status"] == "unavailable" and "weighted to where people live" in (r["reason"] or "")
        )
        self.assertEqual(no_rows, 49)
        self.assertEqual(blank, 5)

        # Verify specific counties
        self.assertEqual(records["46102"]["status"], "unavailable")
        self.assertEqual(records["51678"]["status"], "unavailable")
        self.assertEqual(records["12129"]["status"], "unavailable")
        self.assertEqual(records["13183"]["status"], "unavailable")
        self.assertEqual(records["22023"]["status"], "unavailable")
        self.assertEqual(records["37095"]["status"], "unavailable")
        self.assertEqual(records["51115"]["status"], "unavailable")

    def test_every_available_county_recomputes_correctly(self):
        """Independently recompute EVERY available county's value from aggregate CSV.

        This catches any remaining double-rounding bugs across all counties.
        """
        repo_root = pathlib.Path(__file__).resolve().parent.parent
        source_dir = repo_root / "work" / "air-quality-source"
        atlas_path = repo_root / "dist" / "data" / "counties.geojson"

        if not source_dir.exists() or not atlas_path.exists():
            self.skipTest("real source or atlas not available")

        payload, _ = prep.build(str(source_dir), str(atlas_path))
        records = payload["datasets"][0]["records"]

        # Load the annual data to independently compute values
        annual = prep.load_annual(source_dir / "county-annual-2018-2022.csv")

        mismatches = []
        checked = 0
        for fips, rec in records.items():
            if rec["status"] != "available":
                continue
            checked += 1

            # Independently compute: round(mean of three unrounded pop_mean values)
            vals = []
            for y in ("2020", "2021", "2022"):
                if fips not in annual or y not in annual[fips]:
                    mismatches.append((fips, "missing year", y))
                    continue
                vals.append(float(annual[fips][y]["pop_mean"]))

            if len(vals) != 3:
                continue

            expected = round(sum(vals) / len(vals), 2)
            if rec["value"] != expected:
                mismatches.append((fips, rec["value"], expected))

        self.assertEqual(len(mismatches), 0,
                         f"Rounding mismatch in {len(mismatches)} counties (checked {checked}); "
                         f"first few: {mismatches[:5]}")

    def test_recompute_06037(self):
        repo_root = pathlib.Path(__file__).resolve().parent.parent
        source_dir = repo_root / "work" / "air-quality-source"
        atlas_path = repo_root / "dist" / "data" / "counties.geojson"

        if not source_dir.exists() or not atlas_path.exists():
            self.skipTest("real source or atlas not available")

        payload, _ = prep.build(str(source_dir), str(atlas_path))
        records = payload["datasets"][0]["records"]

        annual = prep.load_annual(source_dir / "county-annual-2018-2022.csv")
        rows = annual["06037"]
        # Compute expected: round(mean of UNROUNDED values)
        unrounded_vals = [float(rows[y]["pop_mean"]) for y in ("2020", "2021", "2022")]
        expected = round(sum(unrounded_vals) / 3, 2)
        # Annual values are rounded separately for display
        annual_vals = {y: round(float(rows[y]["pop_mean"]), 2) for y in ("2020", "2021", "2022")}

        rec = records["06037"]
        self.assertEqual(rec["status"], "available")
        self.assertEqual(rec["value"], expected)
        self.assertEqual(rec["annual"], annual_vals)

    def test_recompute_01001(self):
        repo_root = pathlib.Path(__file__).resolve().parent.parent
        source_dir = repo_root / "work" / "air-quality-source"
        atlas_path = repo_root / "dist" / "data" / "counties.geojson"

        if not source_dir.exists() or not atlas_path.exists():
            self.skipTest("real source or atlas not available")

        payload, _ = prep.build(str(source_dir), str(atlas_path))
        records = payload["datasets"][0]["records"]

        annual = prep.load_annual(source_dir / "county-annual-2018-2022.csv")
        rows = annual["01001"]
        # Compute expected: round(mean of UNROUNDED values)
        unrounded_vals = [float(rows[y]["pop_mean"]) for y in ("2020", "2021", "2022")]
        expected = round(sum(unrounded_vals) / 3, 2)
        # Annual values are rounded separately for display
        annual_vals = {y: round(float(rows[y]["pop_mean"]), 2) for y in ("2020", "2021", "2022")}

        rec = records["01001"]
        self.assertEqual(rec["status"], "available")
        self.assertEqual(rec["value"], expected)
        self.assertEqual(rec["annual"], annual_vals)


if __name__ == "__main__":
    unittest.main(verbosity=2)
