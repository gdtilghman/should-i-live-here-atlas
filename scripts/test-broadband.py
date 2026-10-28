#!/usr/bin/env python3
"""Offline fixture and optional real-source tests for the broadband importer."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("prepare_broadband", ROOT / "scripts/prepare-broadband.py")
prep = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(prep)


def variable_metadata(period: str = "June 2024", tooltip: str | None = None) -> list[dict]:
    return [
        {
            "id": 31,
            "name": "Fixed Broadband Access",
            "data_col": prep.SOURCE_FIELD,
            "tooltip": tooltip
            or (
                "Percentage of population with access to fixed terrestrial broadband service at "
                f"100/20 Mbps or higher advertised speeds, as of {period}."
            ),
            "unit": "%",
            "availability": ["county"],
            "data_type": "numerical",
        }
    ]


class BroadbandImporterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "counties.json"
        self.metadata = self.root / "variables.json"
        self.acquisition = self.root / "acquisition.json"
        self.geo = self.root / "counties.geojson"
        self.out = self.root / "broadband.json"

    def tearDown(self):
        self.temp.cleanup()

    def write_files(self, rows, ids, metadata=None, acquisition_override=None):
        self.source.write_text(json.dumps(rows), encoding="utf-8")
        meta = variable_metadata() if metadata is None else metadata
        self.metadata.write_text(json.dumps(meta), encoding="utf-8")
        acquisition = {
            "counties.json": {
                "url": prep.EXPECTED_SOURCE_URL,
                "sha256": hashlib.sha256(self.source.read_bytes()).hexdigest(),
                "retrievedAt": "2026-09-25T00:00:20.474539+00:00",
            },
            "variables.json": {
                "url": prep.EXPECTED_METADATA_URL,
                "sha256": hashlib.sha256(self.metadata.read_bytes()).hexdigest(),
                "retrievedAt": "2026-09-25T00:00:20.834746+00:00",
            },
        }
        if acquisition_override:
            acquisition.update(acquisition_override)
        self.acquisition.write_text(json.dumps(acquisition), encoding="utf-8")
        self.geo.write_text(
            json.dumps(
                {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "properties": {"fips": fips, "name": f"County {fips}"},
                        }
                        for fips in ids
                    ],
                }
            ),
            encoding="utf-8",
        )
        return acquisition

    def prepare(self, rows, ids, **kwargs):
        self.write_files(rows, ids, **kwargs)
        return prep.build_data(self.source, self.metadata, self.acquisition, self.geo)

    def test_zero_and_full_access_are_meaningful(self):
        payload, audit = self.prepare(
            [
                {"fips": 1001, prep.SOURCE_FIELD: 0, prep.RELIABILITY_FIELD: "reliable"},
                {"fips": 1003, prep.SOURCE_FIELD: 100, prep.RELIABILITY_FIELD: "reliable"},
            ],
            ["01001", "01003"],
        )
        records = payload["datasets"][0]["records"]
        self.assertEqual(records["01001"]["sourceAccessPercent"], 0)
        self.assertEqual(records["01001"]["value"], 100)
        self.assertEqual(records["01001"]["status"], "available")
        self.assertEqual(records["01003"]["sourceAccessPercent"], 100)
        self.assertEqual(records["01003"]["value"], 0)
        self.assertEqual(records["01003"]["status"], "available")
        self.assertEqual((audit["min"], audit["max"]), (0, 100))

    def test_fractional_conversion_preserves_source_value(self):
        payload, _ = self.prepare(
            [
                {"fips": 1001, prep.SOURCE_FIELD: 95.5, prep.RELIABILITY_FIELD: "reliable"},
                {"fips": 1003, prep.SOURCE_FIELD: 82.9, prep.RELIABILITY_FIELD: "reliable"},
            ],
            ["01001", "01003"],
        )
        records = payload["datasets"][0]["records"]
        self.assertEqual(records["01001"]["sourceAccessPercent"], 95.5)
        self.assertEqual(records["01001"]["value"], 4.5)
        self.assertEqual(records["01003"]["sourceAccessPercent"], 82.9)
        self.assertEqual(records["01003"]["value"], 17.1)

    def test_missing_sentinel_and_unreliable_values_never_become_zero(self):
        payload, _ = self.prepare(
            [
                {"fips": 1001, prep.SOURCE_FIELD: None, prep.RELIABILITY_FIELD: "reliable"},
                {"fips": 1003, prep.SOURCE_FIELD: -1111, prep.RELIABILITY_FIELD: "unavailable"},
                {"fips": 1005, prep.SOURCE_FIELD: 42.3, prep.RELIABILITY_FIELD: "unreliable"},
                {"fips": 1007, prep.SOURCE_FIELD: 51.2, prep.RELIABILITY_FIELD: None},
                {"fips": 1009, prep.SOURCE_FIELD: 60, prep.RELIABILITY_FIELD: "reliable"},
            ],
            ["01001", "01003", "01005", "01007", "01009"],
        )
        records = payload["datasets"][0]["records"]
        self.assertEqual(records["01001"]["status"], "unavailable")
        self.assertIsNone(records["01001"]["value"])
        self.assertIsNone(records["01001"]["sourceAccessPercent"])
        self.assertEqual(records["01003"]["status"], "unavailable")
        self.assertIsNone(records["01003"]["sourceAccessPercent"])
        self.assertIn("sentinel", records["01003"]["reason"])
        self.assertEqual(records["01005"]["status"], "unavailable")
        self.assertEqual(records["01005"]["sourceAccessPercent"], 42.3)
        self.assertIsNone(records["01005"]["value"])
        self.assertEqual(records["01007"]["status"], "unavailable")
        self.assertEqual(records["01007"]["sourceAccessPercent"], 51.2)

    def test_invalid_bounds_are_unavailable(self):
        payload, _ = self.prepare(
            [
                {"fips": 1001, prep.SOURCE_FIELD: 101, prep.RELIABILITY_FIELD: "reliable"},
                {"fips": 1003, prep.SOURCE_FIELD: -1, prep.RELIABILITY_FIELD: "reliable"},
                {"fips": 1005, prep.SOURCE_FIELD: 50, prep.RELIABILITY_FIELD: "reliable"},
            ],
            ["01001", "01003", "01005"],
        )
        records = payload["datasets"][0]["records"]
        self.assertEqual(records["01001"]["status"], "unavailable")
        self.assertIsNone(records["01001"]["sourceAccessPercent"])
        self.assertIn("above", records["01001"]["reason"])
        self.assertEqual(records["01003"]["status"], "unavailable")
        self.assertIsNone(records["01003"]["sourceAccessPercent"])
        self.assertIn("below zero", records["01003"]["reason"])
        self.assertEqual(records["01005"]["value"], 50)

    def test_duplicate_fips_fails_closed(self):
        with self.assertRaisesRegex(prep.PreparationError, "duplicate source FIPS"):
            self.prepare(
                [
                    {"fips": 1001, prep.SOURCE_FIELD: 50, prep.RELIABILITY_FIELD: "reliable"},
                    {"fips": 1001, prep.SOURCE_FIELD: 60, prep.RELIABILITY_FIELD: "reliable"},
                ],
                ["01001"],
            )

    def test_malformed_fips_fail_closed(self):
        ids = ["01001"]
        for bad in (True, 1.5, -1, 123456):
            with self.subTest(fips=bad):
                with self.assertRaises(prep.PreparationError):
                    self.prepare(
                        [{"fips": bad, prep.SOURCE_FIELD: 50, prep.RELIABILITY_FIELD: "reliable"}],
                        ids,
                    )

    def test_expected_fields_are_required_in_every_row(self):
        row = {"fips": 1001, prep.SOURCE_FIELD: 50, prep.RELIABILITY_FIELD: "reliable"}
        del row[prep.SOURCE_FIELD]
        with self.assertRaisesRegex(prep.PreparationError, "lacks fixed_100_20_pct"):
            self.prepare([row], ["01001"])

    def test_wrong_hash_fails_closed(self):
        self.write_files(
            [{"fips": 1001, prep.SOURCE_FIELD: 95.5, prep.RELIABILITY_FIELD: "reliable"}],
            ["01001"],
        )
        acquisition = json.loads(self.acquisition.read_text(encoding="utf-8"))
        acquisition["counties.json"]["sha256"] = "0" * 64
        self.acquisition.write_text(json.dumps(acquisition), encoding="utf-8")
        with self.assertRaisesRegex(prep.PreparationError, "Source SHA-256 mismatch"):
            prep.build_data(self.source, self.metadata, self.acquisition, self.geo)

    def test_wrong_metadata_period_or_field_fails_closed(self):
        with self.assertRaisesRegex(prep.PreparationError, "as of June 2024"):
            self.prepare(
                [{"fips": 1001, prep.SOURCE_FIELD: 50, prep.RELIABILITY_FIELD: "reliable"}],
                ["01001"],
                metadata=variable_metadata("June 2025"),
            )
        with self.assertRaisesRegex(prep.PreparationError, "exactly one"):
            self.prepare(
                [{"fips": 1001, prep.SOURCE_FIELD: 50, prep.RELIABILITY_FIELD: "reliable"}],
                ["01001"],
                metadata=[],
            )

    def test_wrong_metadata_denominator_or_technology_fails_closed(self):
        rows = [{"fips": 1001, prep.SOURCE_FIELD: 50, prep.RELIABILITY_FIELD: "reliable"}]
        with self.assertRaisesRegex(prep.PreparationError, "population denominator"):
            self.prepare(
                rows,
                ["01001"],
                metadata=variable_metadata(
                    tooltip=(
                        "Percentage of households with access to fixed terrestrial broadband service at "
                        "100/20 Mbps or higher advertised speeds, as of June 2024."
                    )
                ),
            )
        with self.assertRaisesRegex(prep.PreparationError, "fixed terrestrial technology"):
            self.prepare(
                rows,
                ["01001"],
                metadata=variable_metadata(
                    tooltip=(
                        "Percentage of population with access to fixed wireless broadband service at "
                        "100/20 Mbps or higher advertised speeds, as of June 2024."
                    )
                ),
            )
        payload, _ = self.prepare(
            rows,
            ["01001"],
            metadata=variable_metadata(
                tooltip=(
                    "PERCENTAGE OF POPULATION WITH ACCESS TO FIXED TERRESTRIAL BROADBAND SERVICE AT "
                    "100/20 MBPS OR HIGHER ADVERTISED SPEEDS, AS OF JUNE 2024."
                )
            ),
        )
        self.assertEqual(payload["datasets"][0]["id"], "without-100-20")
        self.assertEqual(payload["datasets"][0]["records"]["01001"]["value"], 50)

    def test_no_numeric_matches_fails_without_placeholder(self):
        with self.assertRaisesRegex(prep.PreparationError, "No numeric source rows matched"):
            self.prepare(
                [{"fips": 99999, prep.SOURCE_FIELD: 50, prep.RELIABILITY_FIELD: "reliable"}],
                ["01001"],
            )

    def test_existing_output_is_preserved_on_failure(self):
        self.write_files(
            [{"fips": 1001, prep.SOURCE_FIELD: 95.5, prep.RELIABILITY_FIELD: "reliable"}],
            ["01001"],
        )
        acquisition = json.loads(self.acquisition.read_text(encoding="utf-8"))
        acquisition["counties.json"]["sha256"] = "1" * 64
        self.acquisition.write_text(json.dumps(acquisition), encoding="utf-8")
        self.out.write_text('{"existing": true}', encoding="utf-8")
        self.assertEqual(prep.main(["--source", str(self.source), "--metadata", str(self.metadata), "--acquisition", str(self.acquisition), "--geo", str(self.geo), "--out", str(self.out)]), 1)
        self.assertEqual(json.loads(self.out.read_text(encoding="utf-8")), {"existing": True})

    def test_acquisition_urls_checksums_and_dates_are_preserved(self):
        payload, _ = self.prepare(
            [{"fips": 1001, prep.SOURCE_FIELD: 95.5, prep.RELIABILITY_FIELD: "reliable"}],
            ["01001"],
        )
        self.assertEqual(
            payload["sourceFiles"],
            [
                {
                    "name": "counties.json",
                    "url": prep.EXPECTED_SOURCE_URL,
                    "sha256": hashlib.sha256(self.source.read_bytes()).hexdigest(),
                    "retrievedAt": "2026-09-25T00:00:20.474539+00:00",
                },
                {
                    "name": "variables.json",
                    "url": prep.EXPECTED_METADATA_URL,
                    "sha256": hashlib.sha256(self.metadata.read_bytes()).hexdigest(),
                    "retrievedAt": "2026-09-25T00:00:20.834746+00:00",
                },
            ],
        )


@unittest.skipUnless((ROOT / "work/broadband-source/counties.json").exists(), "real FCC source is not available")
class RealBroadbandSourceTests(unittest.TestCase):
    def test_real_source_matches_atlas_and_published_samples(self):
        payload, audit = prep.build_data(
            ROOT / "work/broadband-source/counties.json",
            ROOT / "work/broadband-source/variables.json",
            ROOT / "work/broadband-source/acquisition.json",
            ROOT / "dist/data/counties.geojson",
        )
        dataset = payload["datasets"][0]
        self.assertEqual(dataset["id"], "without-100-20")
        records = dataset["records"]
        self.assertEqual(audit["atlasCounties"], 3107)
        self.assertEqual(audit["matched"], 3107)
        self.assertEqual(audit["sourceRows"], 3143)
        self.assertEqual(audit["excludedNonAtlas"], 36)
        for fips, access, gap in (
            ("01001", 95.5, 4.5),
            ("06037", 96.5, 3.5),
            ("09001", 96.9, 3.1),
            ("48301", 50, 50),
        ):
            self.assertEqual(records[fips]["sourceAccessPercent"], access)
            self.assertEqual(records[fips]["value"], gap)


if __name__ == "__main__":
    unittest.main(verbosity=2)
