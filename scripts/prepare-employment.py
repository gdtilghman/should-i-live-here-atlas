#!/usr/bin/env python3
"""Prepare the BLS county unemployment dataset using only the standard library."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from zipfile import BadZipFile, ZipFile

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
R_NS = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
EXPECTED_URL = "https://www.bls.gov/lau/laucnty25.xlsx"
EXPECTED_TITLE = "Labor Force Data by County, 2025 11-Month and Annual Averages*"
EXPECTED_HEADERS = [
    "LAUS Code",
    "State FIPS Code",
    "County FIPS Code",
    "County Name/State Abbreviation",
    "Year",
    "Labor Force",
    "Employed",
    "Unemployed",
    "Unemployment Rate (%)",
]
SOURCE_RELEASE = "May 19, 2026"
SOURCE_NAME = "BLS Local Area Unemployment Statistics"
UNIT = "% of civilian labor force"
CONNECTICUT_REASON = (
    "BLS Local Area Unemployment Statistics reports Connecticut by planning regions. They do not match the older counties this atlas uses. The site does not convert the values."
)
PERIOD = "2025, 11-month average"
SOURCE_NOTE = (
    "The unemployment rate is the share of people in the labor force who have no job and look for one. The rate uses where people live, not where they work. It is not adjusted for seasons. The 2025 value is an average of 11 months, without October 2025. So it does not fully compare with other years. It is not a count of open jobs. It is not one person's chance of finding a job."
)
IDENTITY_RE = re.compile(r"^CN\d{13}$")


class PreparationError(RuntimeError):
    """Raised for fail-closed source, schema, or atlas validation problems."""


def _element(data: bytes) -> ET.Element:
    try:
        return ET.fromstring(data)
    except ET.ParseError as exc:
        raise PreparationError(f"Invalid XML in source workbook: {exc}") from exc


def _column(cell_ref: str) -> int:
    letters = "".join(ch for ch in cell_ref if ch.isalpha()).upper()
    if not letters or not letters.isalpha():
        raise PreparationError(f"Invalid cell reference: {cell_ref!r}")
    value = 0
    for ch in letters:
        value = value * 26 + ord(ch) - 64
    return value


def _shared_strings(archive: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = _element(archive.read("xl/sharedStrings.xml"))
    values: list[str] = []
    for item in root.findall("m:si", NS):
        values.append("".join(node.text or "" for node in item.findall(".//m:t", NS)))
    return values


def _first_sheet_path(archive: ZipFile) -> str:
    # Official BLS workbook and the test fixtures both use the conventional first path.
    if "xl/worksheets/sheet1.xml" in archive.namelist():
        return "xl/worksheets/sheet1.xml"
    try:
        workbook = _element(archive.read("xl/workbook.xml"))
        rels = _element(archive.read("xl/_rels/workbook.xml.rels"))
        rid = workbook.find("m:sheets/m:sheet", NS).attrib[
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        ]
        target = next(
            rel.attrib["Target"]
            for rel in rels.findall("r:Relationship", R_NS)
            if rel.attrib["Id"] == rid
        )
        return target.lstrip("/") if target.startswith("/") else "xl/" + target
    except (KeyError, StopIteration, AttributeError, TypeError) as exc:
        raise PreparationError("Workbook does not contain a readable first worksheet") from exc


def _cell_value(cell: ET.Element, shared: list[str]) -> object:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        text_node = cell.find("m:is", NS)
        return "".join(node.text or "" for node in text_node.findall(".//m:t", NS)) if text_node is not None else None
    raw_node = cell.find("m:v", NS)
    if raw_node is None or raw_node.text is None:
        return None
    raw = raw_node.text
    if cell_type == "s":
        try:
            return shared[int(raw)]
        except (ValueError, IndexError) as exc:
            raise PreparationError(f"Invalid shared-string index {raw!r}") from exc
    if cell_type in {"str", "e"}:
        return raw
    try:
        number = float(raw)
    except ValueError:
        return raw
    return int(number) if number.is_integer() else number


def read_xlsx(path: Path) -> dict[int, dict[int, object]]:
    """Read the first worksheet as sparse {row: {column: value}} data."""
    try:
        with ZipFile(path) as archive:
            shared = _shared_strings(archive)
            root = _element(archive.read(_first_sheet_path(archive)))
            rows: dict[int, dict[int, object]] = {}
            for row in root.findall(".//m:sheetData/m:row", NS):
                row_number = int(row.attrib["r"])
                rows[row_number] = {}
                for cell in row.findall("m:c", NS):
                    ref = cell.attrib.get("r")
                    if not ref:
                        raise PreparationError("Source worksheet contains a cell without a reference")
                    rows[row_number][_column(ref)] = _cell_value(cell, shared)
            return rows
    except (OSError, KeyError, ET.ParseError, BadZipFile) as exc:
        raise PreparationError(f"Cannot read source workbook {path}: {exc}") from exc


def _text(row: dict[int, object], column: int) -> str:
    value = row.get(column)
    return str(value).strip() if value is not None else ""


def _optional_number(row: dict[int, object], column: int) -> tuple[float | int | None, str | None]:
    raw = row.get(column)
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None, "missing"
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None, "not numeric"
    if not math.isfinite(value):
        return None, "not finite"
    return value, None


def _count(row: dict[int, object], column: int) -> tuple[int | None, str | None]:
    value, reason = _optional_number(row, column)
    if value is None:
        return None, reason
    if value < 0 or not float(value).is_integer():
        return None, "invalid count"
    return int(value), None


def _source_rate(row: dict[int, object], column: int = 9) -> tuple[float | None, str | None]:
    value, reason = _optional_number(row, column)
    if value is None:
        return None, reason
    if value < 0 or value > 100:
        return None, "outside 0-100"
    # BLS publishes one decimal; xlsx storage can contain IEEE-754 noise.
    return float(Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)), None


def _load_acquisition(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PreparationError(f"Cannot read acquisition metadata {path}: {exc}") from exc
    required = {"url", "sha256", "receivedAt", "acquisition"}
    missing = sorted(required - set(data))
    if missing:
        raise PreparationError(f"Acquisition metadata missing fields: {', '.join(missing)}")
    if data["url"] != EXPECTED_URL:
        raise PreparationError(f"Unexpected source URL: {data['url']!r}")
    if not re.fullmatch(r"[0-9a-f]{64}", str(data["sha256"])):
        raise PreparationError("Acquisition SHA256 is not a 64-character hexadecimal digest")
    if not str(data["receivedAt"]):
        raise PreparationError("Acquisition receivedAt is empty")
    return data


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise PreparationError(f"Cannot hash source workbook {path}: {exc}") from exc
    return digest.hexdigest()


def _atlas_ids(geo_path: Path) -> dict[str, str]:
    try:
        geo = json.loads(geo_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PreparationError(f"Cannot read county atlas {geo_path}: {exc}") from exc
    features = geo.get("features") if isinstance(geo, dict) else None
    if not isinstance(features, list):
        raise PreparationError("County atlas has no features array")
    ids: dict[str, str] = {}
    for feature in features:
        props = feature.get("properties") if isinstance(feature, dict) else None
        fips = props.get("fips") if isinstance(props, dict) else None
        if not isinstance(fips, str) or not re.fullmatch(r"\d{5}", fips):
            raise PreparationError(f"County atlas contains invalid FIPS: {fips!r}")
        if fips in ids:
            raise PreparationError(f"County atlas contains duplicate FIPS {fips}")
        ids[fips] = props.get("name") if isinstance(props.get("name"), str) else ""
    return ids


def build_data(source_path: Path, geo_path: Path, acquisition_path: Path) -> tuple[dict, dict]:
    """Build and fully validate the dataset without writing output."""
    acquisition = _load_acquisition(acquisition_path)
    actual_hash = _sha256(source_path)
    if actual_hash != acquisition["sha256"]:
        raise PreparationError(
            f"Source SHA256 mismatch: expected {acquisition['sha256']}, got {actual_hash}"
        )

    rows = read_xlsx(source_path)
    if 1 not in rows or _text(rows[1], 1) != EXPECTED_TITLE:
        actual_title = _text(rows.get(1, {}), 1)
        raise PreparationError(f"Unexpected source title: {actual_title!r}")
    if 2 not in rows:
        raise PreparationError("Source worksheet is missing its header row")
    actual_headers = [_text(rows[2], i) for i in range(1, 10)]
    if actual_headers != EXPECTED_HEADERS:
        raise PreparationError(f"Unexpected source headers: {actual_headers!r}")

    all_text = " | ".join(str(value) for row in rows.values() for value in row.values() if value is not None)
    if SOURCE_RELEASE not in all_text:
        raise PreparationError(f"Source footer does not confirm release {SOURCE_RELEASE}")
    if not ("outside of Puerto Rico" in all_text and "11-month" in all_text and "exclude October 2025" in all_text):
        raise PreparationError("Source footnote does not confirm the 11-month, October-excluding period")

    source: dict[str, dict] = {}
    duplicate_fips: list[str] = []
    schema_errors: list[str] = []
    year_errors: list[str] = []
    laus_errors: list[str] = []
    invalid_years = Counter()

    for row_number in sorted(row for row in rows if row >= 3):
        laus = _text(rows[row_number], 1)
        if not laus.startswith("CN"):
            continue
        state = _text(rows[row_number], 2)
        county = _text(rows[row_number], 3)
        name = _text(rows[row_number], 4)
        year = _text(rows[row_number], 5)
        fips = state + county
        if not re.fullmatch(r"\d{2}", state) or not re.fullmatch(r"\d{3}", county):
            schema_errors.append(f"row {row_number}: invalid FIPS {state!r}/{county!r}")
            continue
        if not IDENTITY_RE.fullmatch(laus):
            schema_errors.append(f"row {row_number}: invalid LAUS code {laus!r}")
            continue
        if laus != "CN" + state + county + "0" * 8:
            laus_errors.append(f"row {row_number}: LAUS {laus} disagrees with FIPS {fips}")
        if year != "2025":
            invalid_years[year] += 1
            year_errors.append(f"row {row_number}: year {year!r}")
        if fips in source:
            duplicate_fips.append(fips)
            continue
        labor_force, labor_reason = _count(rows[row_number], 6)
        employed, employed_reason = _count(rows[row_number], 7)
        unemployed, unemployed_reason = _count(rows[row_number], 8)
        rate, rate_reason = _source_rate(rows[row_number], 9)
        source[fips] = {
            "row": row_number,
            "name": name,
            "year": year,
            "laborForce": labor_force,
            "laborForceReason": labor_reason,
            "employed": employed,
            "employedReason": employed_reason,
            "unemployed": unemployed,
            "unemployedReason": unemployed_reason,
            "rate": rate,
            "rateReason": rate_reason,
        }

    if schema_errors:
        raise PreparationError("Source schema errors: " + "; ".join(schema_errors[:5]))
    if laus_errors:
        raise PreparationError("LAUS-to-FIPS errors: " + "; ".join(laus_errors[:5]))
    if year_errors:
        sample = "; ".join(year_errors[:3])
        raise PreparationError(f"Source contains non-2025 rows ({len(year_errors)}): {sample}")
    if duplicate_fips:
        raise PreparationError(f"Duplicate source FIPS: {', '.join(sorted(set(duplicate_fips))[:10])}")
    if not source:
        raise PreparationError("Source contains no county data rows")

    atlas = _atlas_ids(geo_path)
    if not atlas:
        raise PreparationError("County atlas contains no county IDs")

    records: dict[str, dict] = {}
    for fips in sorted(atlas):
        row = source.get(fips)
        if row is None:
            unmatched_reason = (
                CONNECTICUT_REASON
                if fips.startswith("09")
                else "The BLS source has no value for this county."
            )
            records[fips] = {
                "status": "unavailable",
                "value": None,
                "count": None,
                "low": None,
                "high": None,
                "moe": None,
                "laborForce": None,
                "employed": None,
                "unemployed": None,
                "sourceName": None,
                "reason": unmatched_reason,
            }
            continue
        context_reasons = []
        for label, key in (
            ("Labor force", "laborForce"),
            ("Employed", "employed"),
            ("Unemployed", "unemployed"),
        ):
            if row[key] is None:
                context_reasons.append(f"{label} unavailable ({row[key + 'Reason']}).")
        if row["rate"] is None:
            records[fips] = {
                "status": "unavailable",
                "value": None,
                "count": None,
                "low": None,
                "high": None,
                "moe": None,
                "laborForce": row["laborForce"],
                "employed": row["employed"],
                "unemployed": row["unemployed"],
                "sourceName": row["name"],
                "reason": f"Unemployment rate unavailable ({row['rateReason']}).",
            }
            if context_reasons:
                records[fips]["contextReason"] = " ".join(context_reasons)
        else:
            record = {
                "status": "available",
                "value": row["rate"],
                "count": None,
                "low": None,
                "high": None,
                "moe": None,
                "laborForce": row["laborForce"],
                "employed": row["employed"],
                "unemployed": row["unemployed"],
                "sourceName": row["name"],
                "reason": None,
            }
            if context_reasons:
                record["contextReason"] = " ".join(context_reasons)
            records[fips] = record

    if len(records) != len(atlas):
        raise PreparationError("Internal error: output records do not cover every atlas county")
    valid_rates = [record["value"] for record in records.values() if record["status"] == "available"]
    if not valid_rates:
        raise PreparationError("No valid unemployment-rate records were produced")

    dataset = {
        "id": "unemployment-rate",
        "title": "Unemployment rate",
        "source": SOURCE_NAME,
        "unit": UNIT,
        "period": PERIOD,
        "sourceUrl": EXPECTED_URL,
        "release": SOURCE_RELEASE,
        "receivedAt": acquisition["receivedAt"],
        "note": SOURCE_NOTE,
        "direction": "higher-worse",
        "category": "employment",
        "min": min(valid_rates),
        "max": max(valid_rates),
        "records": records,
    }
    payload = {
        "source": SOURCE_NAME,
        "sourceUrl": EXPECTED_URL,
        "sha256": acquisition["sha256"],
        "receivedAt": acquisition["receivedAt"],
        "acquisition": acquisition["acquisition"],
        "sourceRelease": SOURCE_RELEASE,
        "sourceFiles": [{"name": source_path.name, "sha256": acquisition["sha256"]}],
        "note": SOURCE_NOTE,
        "datasets": [dataset],
    }
    audit = {
        "sourceRows": len(source),
        "atlasCounties": len(atlas),
        "matched": sum(fips in atlas for fips in source),
        "excludedNonAtlas": sum(fips not in atlas for fips in source),
        "available": len(valid_rates),
        "unavailable": len(atlas) - len(valid_rates),
        "min": min(valid_rates),
        "max": max(valid_rates),
    }
    return payload, audit


def write_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
        ) as handle:
            temporary = handle.name
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, path)
    except OSError as exc:
        if temporary:
            try:
                os.unlink(temporary)
            except OSError:
                pass
        raise PreparationError(f"Cannot write output {path}: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    repository = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=repository / "work/employment-source/laucnty25.xlsx")
    parser.add_argument("--geo", type=Path, default=repository / "dist/data/counties.geojson")
    parser.add_argument("--acquisition", type=Path, default=repository / "work/employment-source/acquisition.json")
    parser.add_argument("--out", type=Path, default=repository / "dist/data/employment.json")
    args = parser.parse_args(argv)

    try:
        payload, audit = build_data(args.source, args.geo, args.acquisition)
        write_atomic(args.out, payload)
    except PreparationError as exc:
        print(f"employment preparation failed: {exc}", file=sys.stderr)
        return 1

    samples = [fips for fips in ("01001", "09001", "12086", "36061", "56041") if fips in payload["datasets"][0]["records"]]
    print(f" wrote {args.out}")
    print(
        " coverage: {atlasCounties}/{atlasCounties} atlas counties; {available} available; "
        "{unavailable} unavailable; {matched} source rows joined; {excludedNonAtlas} non-atlas source rows excluded".format(**audit)
    )
    print(f" bounds: rate min {audit['min']:.1f}%, max {audit['max']:.1f}%")
    print(" samples: " + ", ".join(f"{fips}={payload['datasets'][0]['records'][fips]['value']}" for fips in samples))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


