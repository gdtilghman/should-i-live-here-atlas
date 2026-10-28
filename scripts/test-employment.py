#!/usr/bin/env python3
"""Unit tests for the employment importer, including parity with the supplied BLS source."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from xml.sax.saxutils import escape

import importlib.util
spec = importlib.util.spec_from_file_location("prepare_employment", Path(__file__).with_name("prepare-employment.py"))
prep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prep)

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "work/employment-source/laucnty25.xlsx"
ACQUISITION = REPO / "work/employment-source/acquisition.json"
GEO = REPO / "dist/data/counties.geojson"
URL = prep.EXPECTED_URL


def laus(fips: str) -> str:
    return "CN" + fips + "0" * 8


def row_xml(row_number: int, values: list[object], inline: bool) -> str:
    cells = []
    for index, value in enumerate(values, 1):
        column = chr(64 + index)
        ref = f"{column}{row_number}"
        if value is None:
            cells.append(f'<c r="{ref}"/>')
        elif isinstance(value, (int, float)):
            cells.append(f'<c r="{ref}"><v>{value}</v></c>')
        elif inline:
            cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>')
        else:
            raise AssertionError("Shared fixture indexes are resolved by write_xlsx")
    return f'<row r="{row_number}">{"".join(cells)}</row>'


class SharedRef(int):
    pass

def write_xlsx(
    path: Path,
    data_rows: list[tuple[object, ...]],
    *,
    inline: bool = False,
    title: str = prep.EXPECTED_TITLE,
    headers: list[str] | None = None,
    footer: bool = True,
    footnote: bool = True,
) -> None:
    headers = prep.EXPECTED_HEADERS if headers is None else headers
    all_rows = [[title], headers, *data_rows]
    if footnote:
        all_rows.append([
            "*Annual estimates for all counties outside of Puerto Rico are 11-month averages "
            "that exclude October 2025 and are not fully comparable to other years."
        ])
    if footer:
        all_rows.append([prep.SOURCE_RELEASE])

    shared: list[str] = []
    shared_index: dict[str, int] = {}
    body = []
    for row_number, values in enumerate(all_rows, 1):
        if inline:
            body.append(row_xml(row_number, values, True))
            continue
        resolved = []
        for value in values:
            if value is None or isinstance(value, (int, float)):
                resolved.append(value)
            else:
                text = str(value)
                if text not in shared_index:
                    shared_index[text] = len(shared)
                    shared.append(text)
                resolved.append(SharedRef(shared_index[text]))
        cells = []
        for index, value in enumerate(resolved, 1):
            ref = f"{chr(64 + index)}{row_number}"
            if value is None:
                cells.append(f'<c r="{ref}"/>')
            elif isinstance(value, SharedRef):
                cells.append(f'<c r="{ref}" t="s"><v>{int(value)}</v></c>')
            elif isinstance(value, (int, float)):
                cells.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                raise AssertionError("Unresolved fixture cell")
        body.append(f'<row r="{row_number}">{"".join(cells)}</row>')

    shared_xml = (
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="0" uniqueCount="0"/>'
        if inline or not shared
        else '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        f'count="{len(shared)}" uniqueCount="{len(shared)}">'
        + "".join(f"<si><t>{escape(value)}</t></si>" for value in shared)
        + "</sst>"
    )
    sheet = (
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
        + "".join(body)
        + "</sheetData></worksheet>"
    )
    workbook = (
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    rels = (
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )
    content = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
        "</Types>"
    )
    root_rels = (
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    with path.open("wb") as output:
        from zipfile import ZipFile, ZIP_DEFLATED

        with ZipFile(output, "w", ZIP_DEFLATED) as archive:
            archive.writestr("[Content_Types].xml", content)
            archive.writestr("_rels/.rels", root_rels)
            archive.writestr("xl/workbook.xml", workbook)
            archive.writestr("xl/_rels/workbook.xml.rels", rels)
            archive.writestr("xl/sharedStrings.xml", shared_xml)
            archive.writestr("xl/worksheets/sheet1.xml", sheet)


def write_acquisition(path: Path, source: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "url": URL,
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "receivedAt": "2026-09-21T12:00:00+00:00",
                "acquisition": "User supplied local file; exact download time unverified.",
            }
        ),
        encoding="utf-8",
    )


def write_geo(path: Path, ids: list[str]) -> None:
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"fips": fips, "name": f"County {fips}", "state": fips[:2]},
                    }
                    for fips in ids
                ],
            }
        ),
        encoding="utf-8",
    )


class EmploymentImporterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "fixture.xlsx"
        self.geo = self.root / "counties.geojson"
        self.acquisition = self.root / "acquisition.json"

    def tearDown(self):
        self.temp.cleanup()

    def prepare(self, rows, ids, **kwargs):
        write_xlsx(self.source, rows, **kwargs)
        write_geo(self.geo, ids)
        write_acquisition(self.acquisition, self.source)
        return prep.build_data(self.source, self.geo, self.acquisition)

    def test_shared_string_fixture(self):
        rows = [
            (laus("01001"), "01", "001", "Autauga County, AL", "2025", 100, 90, 10, 10.0),
            (laus("01003"), "01", "003", "Baldwin County, AL", "2025", 80, 70, 10, 0),
            (laus("72001"), "72", "001", "Adjuntas Municipio, PR", "2025", 50, 40, 10, 20.0),
        ]
        payload, audit = self.prepare(rows, ["01001", "01003"])
        records = payload["datasets"][0]["records"]
        self.assertEqual(records["01001"]["value"], 10.0)
        self.assertEqual(records["01001"]["laborForce"], 100)
        self.assertEqual(records["01003"]["value"], 0)
        self.assertEqual(records["01003"]["status"], "available")
        self.assertNotIn("72001", records)
        self.assertEqual(audit["excludedNonAtlas"], 1)

    def test_inline_string_fixture(self):
        rows = [
            (laus("01001"), "01", "001", "Autauga County, AL", "2025", 100, 90, 10, 2.4),
        ]
        payload, _ = self.prepare(rows, ["01001"], inline=True)
        self.assertEqual(payload["datasets"][0]["records"]["01001"]["value"], 2.4)

    def test_zero_valid_and_missing_invalid_null(self):
        rows = [
            (laus("01001"), "01", "001", "A County, AL", "2025", 100, 90, 10, 0),
            (laus("01003"), "01", "003", "B County, AL", "2025", None, 80, None, None),
            (laus("01005"), "01", "005", "C County, AL", "2025", 100, 90, 10, "not numeric"),
        ]
        payload, audit = self.prepare(rows, ["01001", "01003", "01005"])
        records = payload["datasets"][0]["records"]
        self.assertEqual(records["01001"]["status"], "available")
        self.assertEqual(records["01001"]["value"], 0)
        self.assertEqual(records["01003"]["status"], "unavailable")
        self.assertIsNone(records["01003"]["value"])
        self.assertIn("missing", records["01003"]["reason"])
        self.assertEqual(records["01005"]["status"], "unavailable")
        self.assertIn("not numeric", records["01005"]["reason"])
        self.assertEqual(audit["available"], 1)
        self.assertEqual(audit["unavailable"], 2)

    def test_duplicate_fips_fails_closed(self):
        rows = [
            (laus("01001"), "01", "001", "A County, AL", "2025", 100, 90, 10, 2.0),
            (laus("01001"), "01", "001", "A County, AL", "2025", 110, 100, 10, 3.0),
        ]
        with self.assertRaisesRegex(prep.PreparationError, "Duplicate source FIPS: 01001"):
            self.prepare(rows, ["01001"])

    def test_laus_fips_mismatch_fails_closed(self):
        rows = [(laus("01003"), "01", "001", "A County, AL", "2025", 100, 90, 10, 2.0)]
        with self.assertRaisesRegex(prep.PreparationError, "LAUS-to-FIPS errors"):
            self.prepare(rows, ["01001"])

    def test_wrong_year_fails_closed(self):
        rows = [(laus("01001"), "01", "001", "A County, AL", "2024", 100, 90, 10, 2.0)]
        with self.assertRaisesRegex(prep.PreparationError, "non-2025"):
            self.prepare(rows, ["01001"])

    def test_wrong_headers_fail_closed(self):
        rows = [(laus("01001"), "01", "001", "A County, AL", "2025", 100, 90, 10, 2.0)]
        headers = list(prep.EXPECTED_HEADERS)
        headers[-1] = "Wrong header"
        with self.assertRaisesRegex(prep.PreparationError, "Unexpected source headers"):
            self.prepare(rows, ["01001"], headers=headers)

    def test_rate_bounds_and_rounding(self):
        rows = [
            (laus("01001"), "01", "001", "A County, AL", "2025", 100, 90, 10, -0.1),
            (laus("01003"), "01", "003", "B County, AL", "2025", 100, 90, 10, 101.0),
            (laus("01005"), "01", "005", "C County, AL", "2025", 100, 90, 10, 2.2000000000000002),
        ]
        payload, _ = self.prepare(rows, ["01001", "01003", "01005"])
        records = payload["datasets"][0]["records"]
        self.assertEqual(records["01001"]["status"], "unavailable")
        self.assertIn("outside 0-100", records["01001"]["reason"])
        self.assertEqual(records["01003"]["status"], "unavailable")
        self.assertIn("outside 0-100", records["01003"]["reason"])
        self.assertEqual(records["01005"]["value"], 2.2)

    def test_exact_fips_join_and_unmatched_reason(self):
        rows = [
            (laus("01001"), "01", "001", "A County, AL", "2025", 100, 90, 10, 2.0),
            (laus("72001"), "72", "001", "PR Municipio", "2025", 50, 40, 10, 4.0),
        ]
        payload, _ = self.prepare(rows, ["01001", "01003"])
        records = payload["datasets"][0]["records"]
        self.assertEqual(records["01001"]["sourceName"], "A County, AL")
        self.assertEqual(records["01003"]["status"], "unavailable")
        self.assertIn("The BLS source has no value for this county.", records["01003"]["reason"])
        self.assertEqual(set(records), {"01001", "01003"})

    def test_no_valid_records_fail_closed(self):
        rows = [(laus("01001"), "01", "001", "A County, AL", "2025", 100, 90, 10, None)]
        with self.assertRaisesRegex(prep.PreparationError, "No valid unemployment-rate records"):
            self.prepare(rows, ["01001"])

    def test_failure_does_not_overwrite_output(self):
        rows = [(laus("01001"), "01", "001", "A County, AL", "2024", 100, 90, 10, 2.0)]
        write_xlsx(self.source, rows)
        write_geo(self.geo, ["01001"])
        write_acquisition(self.acquisition, self.source)
        output = self.root / "employment.json"
        output.write_text("PREEXISTING", encoding="utf-8")
        code = prep.main(
            [
                "--source", str(self.source),
                "--geo", str(self.geo),
                "--acquisition", str(self.acquisition),
                "--out", str(output),
            ]
        )
        self.assertEqual(code, 1)
        self.assertEqual(output.read_text(encoding="utf-8"), "PREEXISTING")
    def test_connecticut_planning_region_mismatch_reason(self):
        rows = [
            (laus("01001"), "01", "001", "A County, AL", "2025", 100, 90, 10, 2.0),
        ]
        payload, _ = self.prepare(rows, ["01001", "09001", "09003", "01003"])
        records = payload["datasets"][0]["records"]
        for fips in ("09001", "09003"):
            self.assertEqual(records[fips]["status"], "unavailable")
            self.assertIn("BLS Local Area Unemployment Statistics", records[fips]["reason"])
            self.assertIn("Connecticut by planning regions", records[fips]["reason"])
            self.assertIn("older counties this atlas uses", records[fips]["reason"])
            self.assertIn("does not convert the values", records[fips]["reason"])
        self.assertIn("The BLS source has no value for this county.", records["01003"]["reason"])
        self.assertNotIn("Connecticut", records["01003"]["reason"])
        self.assertEqual(records["01001"]["value"], 2.0)

    def test_visible_source_and_unit_metadata(self):
        rows = [(laus("01001"), "01", "001", "A County, AL", "2025", 100, 90, 10, 2.0)]
        payload, _ = self.prepare(rows, ["01001"])
        dataset = payload["datasets"][0]
        self.assertEqual(payload["source"], prep.SOURCE_NAME)
        self.assertEqual(dataset["source"], prep.SOURCE_NAME)
        self.assertEqual(dataset["unit"], prep.UNIT)

    def test_corrupt_zip_fails_closed_and_preserves_output(self):
        self.source.write_bytes(b"this is not a zip workbook")
        write_geo(self.geo, ["01001"])
        write_acquisition(self.acquisition, self.source)
        output = self.root / "employment.json"
        output.write_text("PREEXISTING", encoding="utf-8")
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = prep.main(
                [
                    "--source", str(self.source),
                    "--geo", str(self.geo),
                    "--acquisition", str(self.acquisition),
                    "--out", str(output),
                ]
            )
        self.assertEqual(code, 1)
        self.assertIn("Cannot read source workbook", stderr.getvalue())
        self.assertIn("PREEXISTING", output.read_text(encoding="utf-8"))

    def test_real_source_parity_and_all_atlas_ids(self):
        if not SOURCE.exists():
            self.skipTest("supplied BLS workbook is unavailable")
        payload, audit = prep.build_data(SOURCE, GEO, ACQUISITION)
        records = payload["datasets"][0]["records"]
        atlas_ids = {feature["properties"]["fips"] for feature in json.loads(GEO.read_text(encoding="utf-8"))["features"]}
        self.assertEqual(len(atlas_ids), 3107)
        self.assertEqual(set(records), atlas_ids)

        parsed = prep.read_xlsx(SOURCE)
        source_by_fips = {}
        for row_number in sorted(row for row in parsed if row >= 3):
            laus_code = prep._text(parsed[row_number], 1)
            if not laus_code.startswith("CN"):
                continue
            fips = prep._text(parsed[row_number], 2) + prep._text(parsed[row_number], 3)
            if fips in atlas_ids:
                source_by_fips[fips] = parsed[row_number]
        self.assertEqual(len(source_by_fips), audit["matched"])
        for fips, source_row in source_by_fips.items():
            expected_rate, reason = prep._source_rate(source_row)
            if reason is None:
                self.assertEqual(records[fips]["status"], "available", fips)
                self.assertEqual(records[fips]["value"], expected_rate, fips)
            else:
                self.assertEqual(records[fips]["status"], "unavailable", fips)
                self.assertIsNone(records[fips]["value"], fips)
            for column, field in ((6, "laborForce"), (7, "employed"), (8, "unemployed")):
                expected_count, count_reason = prep._count(source_row, column)
                self.assertEqual(records[fips][field], expected_count, f"{fips} {field}")
                self.assertEqual(records[fips][field] is None, count_reason is not None, f"{fips} {field}")


if __name__ == "__main__":
    unittest.main(verbosity=2)





