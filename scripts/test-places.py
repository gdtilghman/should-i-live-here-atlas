#!/usr/bin/env python3
"""Tests for scripts/prepare-places.py."""

import csv
import hashlib
import importlib.util
import json
import pathlib
import tempfile
import unittest


_SCRIPT_PATH = (
    pathlib.Path(__file__).resolve().parent.parent / "scripts" / "prepare-places.py"
)
_spec = importlib.util.spec_from_file_location("prepare_places", _SCRIPT_PATH)
prep = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prep)


class PlacesImporterTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

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

    def _write_csv(self, rows):
        """Write a PLACES-format CSV with the given rows."""
        fieldnames = [
            "Year", "StateAbbr", "StateDesc", "LocationName", "DataSource",
            "Category", "Measure", "Data_Value_Unit", "Data_Value_Type",
            "Data_Value", "Data_Value_Footnote_Symbol", "Data_Value_Footnote",
            "Low_Confidence_Limit", "High_Confidence_Limit", "TotalPopulation",
            "TotalPop18plus", "LocationID", "CategoryID", "MeasureId",
            "DataValueTypeID", "Short_Question_Text", "Geolocation",
        ]
        path = self.root / "places-county-2024.csv"
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def _write_acquired_at(self, timestamp="2026-09-28T12:00:00Z"):
        path = self.root / "acquired-at.txt"
        path.write_text(timestamp, encoding="utf-8")
        return path

    def _write_sha256(self, csv_path):
        digest = hashlib.sha256(csv_path.read_bytes()).hexdigest()
        path = self.root / "sha256.txt"
        path.write_text(digest, encoding="utf-8")
        return path

    def _prepare_synthetic(self, fips_list, csv_rows, timestamp="2026-09-28T12:00:00Z"):
        """Set up synthetic files and call prepare_places.build()."""
        self._write_counties_geojson(fips_list)
        csv_path = self._write_csv(csv_rows)
        self._write_acquired_at(timestamp)
        self._write_sha256(csv_path)
        return prep.build(
            str(self.root),
            str(self.root / "counties.geojson"),
        )

    def _row(
        self,
        fips,
        measure_id,
        dtype,
        value,
        low,
        high,
        year=2022,
        footnote="",
        footnote_symbol="",
        location_name="Autauga",
        state_abbr="AL",
        state_desc="Alabama",
    ):
        def fmt(x):
            return "" if x is None else str(x)

        return {
            "Year": str(year),
            "StateAbbr": state_abbr,
            "StateDesc": state_desc,
            "LocationName": location_name,
            "DataSource": "BRFSS",
            "Category": "Health",
            "Measure": "Test measure",
            "Data_Value_Unit": "%",
            "Data_Value_Type": (
                "Age-adjusted prevalence" if dtype == "AgeAdjPrv" else "Crude prevalence"
            ),
            "Data_Value": fmt(value),
            "Data_Value_Footnote_Symbol": footnote_symbol,
            "Data_Value_Footnote": footnote,
            "Low_Confidence_Limit": fmt(low),
            "High_Confidence_Limit": fmt(high),
            "TotalPopulation": "50000",
            "TotalPop18plus": "40000",
            "LocationID": fips,
            "CategoryID": "HLTH",
            "MeasureId": measure_id,
            "DataValueTypeID": dtype,
            "Short_Question_Text": "Test",
            "Geolocation": "(32.5, -86.5)",
        }

    def _all_measure_rows(
        self,
        fips,
        values=None,
        state_abbr="AL",
        state_desc="Alabama",
        location_name="Autauga",
    ):
        """Rows for all fifteen measures, both AgeAdjPrv and CrdPrv."""
        if values is None:
            values = {
                "CASTHMA": (10.5, 10.1, 10.9, 10.2, 9.8, 10.6),
                "DIABETES": (11.0, 10.5, 11.5, 10.8, 10.3, 11.3),
                "MHLTH": (12.0, 11.5, 12.5, 11.8, 11.3, 12.3),
                "OBESITY": (30.0, 29.5, 30.5, 30.2, 29.7, 30.7),
                "CSMOKING": (15.0, 14.5, 15.5, 15.2, 14.7, 15.7),
                "LPA": (25.0, 24.5, 25.5, 25.2, 24.7, 25.7),
                "BINGE": (18.0, 17.5, 18.5, 18.2, 17.7, 18.7),
                "SLEEP": (35.0, 34.5, 35.5, 35.2, 34.7, 35.7),
                "COPD": (6.0, 5.5, 6.5, 6.2, 5.7, 6.7),
                "CHD": (5.0, 4.5, 5.5, 5.2, 4.7, 5.7),
                "STROKE": (3.0, 2.5, 3.5, 3.2, 2.7, 3.7),
                "DEPRESSION": (20.0, 19.5, 20.5, 20.2, 19.7, 20.7),
                "GHLTH": (17.0, 16.5, 17.5, 17.2, 16.7, 17.7),
                "PHLTH": (11.0, 10.5, 11.5, 11.2, 10.7, 11.7),
                "ACCESS2": (12.0, 11.5, 12.5, 12.2, 11.7, 12.7),
            }
        rows = []
        for measure_id, (v, lo, hi, cv, clo, chi) in values.items():
            rows.append(
                self._row(
                    fips, measure_id, "AgeAdjPrv", v, lo, hi,
                    state_abbr=state_abbr, state_desc=state_desc,
                    location_name=location_name,
                )
            )
            rows.append(
                self._row(
                    fips, measure_id, "CrdPrv", cv, clo, chi,
                    state_abbr=state_abbr, state_desc=state_desc,
                    location_name=location_name,
                )
            )
        return rows

    def _dataset(self, payload, measure_id):
        for ds in payload["datasets"]:
            if ds["measureId"] == measure_id:
                return ds
        raise AssertionError(f"no dataset for measure {measure_id}")

    def _iter_records(self, ds):
        records = ds["records"]
        if isinstance(records, dict):
            return list(records.values())
        return list(records)

    def _record(self, ds, fips):
        records = ds["records"]
        if isinstance(records, dict):
            return records[fips]
        for r in records:
            if r.get("fips") == fips or r.get("locationId") == fips:
                return r
        raise AssertionError(f"no record for {fips}")

    def _dataset_min_max(self, ds):
        min_val = None
        max_val = None
        for key in ("min", "minValue", "valueMin", "min_value"):
            if key in ds:
                min_val = ds[key]
                break
        for key in ("max", "maxValue", "valueMax", "max_value"):
            if key in ds:
                max_val = ds[key]
                break
        return min_val, max_val

    # ------------------------------------------------------------------
    # fixture tests
    # ------------------------------------------------------------------

    def test_happy_path_shape(self):
        rows = self._all_measure_rows("01001")
        payload, _ = self._prepare_synthetic(["01001"], rows)

        self.assertIsInstance(payload, dict)
        self.assertIn("datasets", payload)
        self.assertEqual(len(payload["datasets"]), 15)

        for ds in payload["datasets"]:
            self.assertIn("id", ds)
            self.assertIn("title", ds)
            self.assertIn("measureId", ds)
            self.assertIn("records", ds)

        asthma = self._dataset(payload, "CASTHMA")
        rec = self._record(asthma, "01001")
        self.assertEqual(rec["status"], "available")
        self.assertEqual(rec["value"], 10.5)
        self.assertEqual(rec["low"], 10.1)
        self.assertEqual(rec["high"], 10.9)
        self.assertEqual(rec["crude"], 10.2)
        self.assertEqual(rec["crudeLow"], 9.8)
        self.assertEqual(rec["crudeHigh"], 10.6)
        self.assertIsNone(rec["reason"])

    def test_ct_legacy_unavailable(self):
        rows = self._all_measure_rows(
            "09001",
            state_abbr="CT",
            state_desc="Connecticut",
            location_name="Capitol Planning Region",
        )
        payload, _ = self._prepare_synthetic(["09001"], rows)

        for measure_id in ("CASTHMA", "DIABETES", "MHLTH"):
            ds = self._dataset(payload, measure_id)
            rec = self._record(ds, "09001")
            self.assertEqual(rec["status"], "unavailable")
            self.assertIsNone(rec["value"])
            self.assertTrue(
                rec["reason"].startswith("The source uses Connecticut planning regions"),
                msg=f"unexpected reason: {rec['reason']!r}",
            )

    def test_suppressed_never_zero(self):
        rows = []
        for measure_id in ("CASTHMA", "DIABETES", "MHLTH", "OBESITY", "CSMOKING", "LPA", "BINGE", "SLEEP", "COPD", "CHD", "STROKE", "DEPRESSION", "GHLTH", "PHLTH", "ACCESS2"):
            rows.append(
                self._row(
                    "01001", measure_id, "AgeAdjPrv", None, None, None,
                    footnote="Estimates suppressed",
                )
            )
            rows.append(
                self._row(
                    "01001", measure_id, "CrdPrv", None, None, None,
                    footnote="Estimates suppressed",
                )
            )
        payload, _ = self._prepare_synthetic(["01001"], rows)

        asthma = self._dataset(payload, "CASTHMA")
        rec = self._record(asthma, "01001")
        self.assertEqual(rec["status"], "suppressed")
        self.assertIsNone(rec["value"])
        self.assertEqual(rec["reason"], "Estimates suppressed")

    def test_wrong_sha256_fails_closed(self):
        rows = self._all_measure_rows("01001")
        self._write_counties_geojson(["01001"])
        csv_path = self._write_csv(rows)
        self._write_acquired_at()
        sha_path = self._write_sha256(csv_path)
        sha_path.write_text("0" * 64, encoding="utf-8")

        with self.assertRaises(prep.PreparationError) as ctx:
            prep.build(str(self.root), str(self.root / "counties.geojson"))
        self.assertIn("SHA-256 mismatch", str(ctx.exception))

    def test_wrong_year_fails_closed(self):
        rows = self._all_measure_rows("01001")
        for r in rows:
            if r["MeasureId"] == "CASTHMA" and r["DataValueTypeID"] == "AgeAdjPrv":
                r["Year"] = "2023"

        with self.assertRaises(prep.PreparationError) as ctx:
            self._prepare_synthetic(["01001"], rows)
        self.assertIn("Year", str(ctx.exception))

    def test_duplicate_location_measure_type_fails(self):
        rows = self._all_measure_rows("01001")
        rows.append(dict(rows[0]))

        with self.assertRaises(prep.PreparationError) as ctx:
            self._prepare_synthetic(["01001"], rows)
        self.assertIn("duplicate", str(ctx.exception).lower())

    def test_value_outside_ci_fails(self):
        rows = self._all_measure_rows("01001")
        for r in rows:
            if r["MeasureId"] == "CASTHMA" and r["DataValueTypeID"] == "AgeAdjPrv":
                r["Data_Value"] = "11.0"
                r["Low_Confidence_Limit"] = "10.0"
                r["High_Confidence_Limit"] = "10.5"

        with self.assertRaises(prep.PreparationError) as ctx:
            self._prepare_synthetic(["01001"], rows)
        self.assertIn("outside confidence interval", str(ctx.exception))

    def test_missing_atlas_county_fails(self):
        rows = self._all_measure_rows("01001")
        rows = [r for r in rows if r["MeasureId"] != "DIABETES"]

        with self.assertRaises(prep.PreparationError) as ctx:
            self._prepare_synthetic(["01001"], rows)
        self.assertIn("missing", str(ctx.exception).lower())

    def test_existing_output_preserved_on_failure(self):
        rows = self._all_measure_rows("01001")
        self._write_counties_geojson(["01001"])
        csv_path = self._write_csv(rows)
        self._write_acquired_at()
        sha_path = self._write_sha256(csv_path)
        sha_path.write_text("0" * 64, encoding="utf-8")

        out_path = self.root / "out.json"
        out_path.write_text(json.dumps({"test": True}), encoding="utf-8")

        with self.assertRaises(prep.PreparationError):
            prep.build(
                str(self.root),
                str(self.root / "counties.geojson"),
                str(out_path),
            )

        self.assertEqual(
            json.loads(out_path.read_text(encoding="utf-8")),
            {"test": True},
        )

    def test_ci_partially_missing_fails(self):
        rows = self._all_measure_rows("01001")
        for r in rows:
            if r["MeasureId"] == "CASTHMA" and r["DataValueTypeID"] == "AgeAdjPrv":
                r["Data_Value"] = "10.5"
                r["Low_Confidence_Limit"] = "10.1"
                r["High_Confidence_Limit"] = ""

        with self.assertRaises(prep.PreparationError) as ctx:
            self._prepare_synthetic(["01001"], rows)
        self.assertIn("partially missing", str(ctx.exception))

    def test_non_finite_value_fails(self):
        rows = self._all_measure_rows("01001")
        for r in rows:
            if r["MeasureId"] == "CASTHMA" and r["DataValueTypeID"] == "AgeAdjPrv":
                r["Data_Value"] = "NaN"

        with self.assertRaises(prep.PreparationError) as ctx:
            self._prepare_synthetic(["01001"], rows)
        self.assertIn("non-finite", str(ctx.exception))

    def test_value_outside_bounds_fails(self):
        rows = self._all_measure_rows("01001")
        for r in rows:
            if r["MeasureId"] == "CASTHMA" and r["DataValueTypeID"] == "AgeAdjPrv":
                r["Data_Value"] = "101.0"
                r["Low_Confidence_Limit"] = "100.5"
                r["High_Confidence_Limit"] = "101.5"

        with self.assertRaises(prep.PreparationError) as ctx:
            self._prepare_synthetic(["01001"], rows)
        self.assertIn("outside [0, 100]", str(ctx.exception))

    # ------------------------------------------------------------------
    # real-source test
    # ------------------------------------------------------------------

    def test_real_source_matches_atlas_and_samples(self):
        repo_root = pathlib.Path(__file__).resolve().parent.parent
        source_dir = repo_root / "work" / "places-source-2024"
        csv_path = source_dir / "places-county-2024.csv"
        if not csv_path.exists():
            self.skipTest("real source not available")

        atlas_path = repo_root / "dist" / "data" / "counties.geojson"
        if not atlas_path.exists():
            self.skipTest("atlas not available")

        payload, _ = prep.build(str(source_dir), str(atlas_path))

        self.assertEqual(len(payload["datasets"]), 15)
        for ds in payload["datasets"]:
            records = self._iter_records(ds)
            self.assertEqual(len(records), 3107)
            available = sum(1 for r in records if r["status"] == "available")
            unavailable = sum(1 for r in records if r["status"] == "unavailable")
            self.assertEqual(available + unavailable, 3107)
            self.assertEqual(available, 3099)
            self.assertEqual(unavailable, 8)

        # Independent read of the published CSV: every age-adjusted value
        # for the two sample counties, and each measure's atlas-wide range.
        atlas = {f["properties"]["fips"] for f in json.loads(atlas_path.read_text(encoding="utf-8"))["features"]}
        samples, ranges = {}, {}
        with open(csv_path, newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                if row["DataValueTypeID"] != "AgeAdjPrv" or row["MeasureId"] not in ("CASTHMA", "DIABETES", "MHLTH"):
                    continue
                if row["LocationID"] in ("01001", "06037"):
                    samples[(row["LocationID"], row["MeasureId"])] = float(row["Data_Value"])
                if row["LocationID"] in atlas and row["Data_Value"]:
                    ranges.setdefault(row["MeasureId"], []).append(float(row["Data_Value"]))

        self.assertEqual(len(samples), 6)
        for (fips, measure), expected in samples.items():
            dataset = self._dataset(payload, measure)
            self.assertEqual(self._record(dataset, fips)["value"], expected, (fips, measure))
        for measure, values in ranges.items():
            min_val, max_val = self._dataset_min_max(self._dataset(payload, measure))
            self.assertEqual((min_val, max_val), (min(values), max(values)), measure)

if __name__ == "__main__":
    unittest.main(verbosity=2)
