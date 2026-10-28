#!/usr/bin/env python3
"""Prepare dist/data/wildfire.json from the USFS Wildfire Risk to Communities workbook."""
import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

import openpyxl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = "work/wildfire-source/wrc_download_20260415.xlsx"
DEFAULT_GEO = "dist/data/counties.geojson"
DEFAULT_OUT = "dist/data/wildfire.json"

EXPECTED_SHA256 = "437C25429EB2A1CFE755832C5A02F01F2707FFA4238712DD7EF1C4CCCC76BDBD"
EXPECTED_HEADER = [
    "GEOID", "GEOIDFQ", "STUSPS", "NAME", "STATE_NAME", "STATEFP", "COUNTYFP", "COUNTYNS",
    "TOTAL_BUILDINGS", "BUILDINGS_FRACTION_ME", "BUILDINGS_FRACTION_IE", "BUILDINGS_FRACTION_DE",
    "BP_STATE_RANK", "BP_NATIONAL_RANK", "RISK_STATE_RANK", "RISK_NATIONAL_RANK",
]
SHEET_NAME = "Counties"

CT_FIPS = {"09001", "09003", "09005", "09007", "09009", "09011", "09013", "09015"}
CT_REASON = ("The source uses Connecticut planning regions. These regions do not match the counties this atlas uses.")

DATASET_SPECS = [
    {
        "id": "risk-to-homes",
        "title": "Wildfire risk to homes",
        "field": "RISK_NATIONAL_RANK",
        "key": "risk",
        "method": "National percentile rank of the county's mean Risk to Potential Structures, times 100",
        "note": ("How the county's average wildfire risk to a home ranks among U.S. counties. "
                 "Risk to homes combines wildfire likelihood and intensity with the general effect "
                 "on a house. 100 is the highest risk."),
    },
    {
        "id": "likelihood",
        "title": "Wildfire likelihood",
        "field": "BP_NATIONAL_RANK",
        "key": "bp",
        "method": "National percentile rank of the county's mean annual burn probability, times 100",
        "note": ("How the county's average chance of wildfire in a year ranks among U.S. counties. "
                 "100 is the highest likelihood."),
    },
]


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_county_fips(geojson_path):
    with open(geojson_path, "r", encoding="utf-8") as f:
        gj = json.load(f)
    fips = set()
    for feature in gj.get("features", []):
        props = feature.get("properties", {}) or {}
        raw = None
        for key in ("GEOID", "geoid", "FIPS", "fips"):
            if key in props and props[key] is not None:
                raw = props[key]
                break
        if raw is None:
            raise SystemExit("counties.geojson feature is missing a GEOID/FIPS property")
        fips.add(str(raw).strip().zfill(5))
    return fips


def atomic_write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_text_file(path, label):
    if not path.is_file():
        raise SystemExit(f"error: missing {label}: {path}")
    return path.read_text(encoding="utf-8").strip()


def read_source_rows(source_path):
    wb = openpyxl.load_workbook(source_path, read_only=True, data_only=True)
    try:
        if SHEET_NAME not in wb.sheetnames:
            raise SystemExit(f"error: sheet {SHEET_NAME!r} not found in {source_path}")
        ws = wb[SHEET_NAME]
        rows = ws.iter_rows(values_only=True)
        try:
            header = next(rows)
        except StopIteration:
            raise SystemExit("error: source sheet has no header row")
        header = [str(h) for h in header]
        if header != EXPECTED_HEADER:
            raise SystemExit(
                "error: unexpected header row in source sheet\n"
                f"  expected: {EXPECTED_HEADER}\n"
                f"  found:    {header}"
            )
        idx = {name: i for i, name in enumerate(header)}
        out = {}
        for row in rows:
            if row is None:
                continue
            geoid_raw = row[idx["GEOID"]]
            if geoid_raw is None or str(geoid_raw).strip() == "":
                continue
            try:
                geoid = str(int(geoid_raw)).zfill(5)
            except (TypeError, ValueError):
                raise SystemExit(f"error: non-numeric GEOID value: {geoid_raw!r}")
            out[geoid] = {
                "risk": row[idx["RISK_NATIONAL_RANK"]],
                "bp": row[idx["BP_NATIONAL_RANK"]],
            }
        return out
    finally:
        wb.close()


def build_datasets(county_fips, source_values, received_at):
    records_by_id = {spec["id"]: {} for spec in DATASET_SPECS}

    for geoid in sorted(county_fips):
        if geoid in CT_FIPS:
            for spec in DATASET_SPECS:
                records_by_id[spec["id"]][geoid] = {
                    "status": "unavailable", "value": None, "reason": CT_REASON,
                }
            continue

        if geoid not in source_values:
            raise SystemExit(f"error: atlas county {geoid} is missing from the source workbook")

        vals = source_values[geoid]
        for spec in DATASET_SPECS:
            raw = vals[spec["key"]]
            try:
                frac = float(raw)
            except (TypeError, ValueError):
                raise SystemExit(
                    f"error: non-numeric {spec['field']} for county {geoid}: {raw!r}"
                )
            if not (0.0 <= frac <= 1.0):
                raise SystemExit(
                    f"error: out-of-range {spec['field']} for county {geoid}: {raw!r} "
                    "(expected 0..1)"
                )
            records_by_id[spec["id"]][geoid] = {
                "status": "available",
                "value": round(frac * 100.0, 1),
                "reason": None,
            }

    datasets = []
    for spec in DATASET_SPECS:
        records = records_by_id[spec["id"]]
        available_values = [r["value"] for r in records.values() if r["status"] == "available"]
        datasets.append({
            "id": spec["id"],
            "title": spec["title"],
            "unit": "national rank, 0–100",
            "period": "2nd edition model, data updated April 2026",
            "method": spec["method"],
            "sourceUrl": "https://wildfirerisk.org",
            "datasetUrl": "https://wildfirerisk.org/download/",
            "receivedAt": received_at,
            "note": spec["note"],
            "direction": "higher-worse",
            "category": "wildfire",
            "min": min(available_values),
            "max": max(available_values),
            "records": records,
        })
    return datasets


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=DEFAULT_SOURCE)
    parser.add_argument("--geo", default=DEFAULT_GEO)
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    source_path = REPO_ROOT / args.source
    geo_path = REPO_ROOT / args.geo
    out_path = REPO_ROOT / args.out

    if not source_path.is_file():
        print(f"error: source workbook not found: {source_path}", file=sys.stderr)
        return 1
    if not geo_path.is_file():
        print(f"error: counties geojson not found: {geo_path}", file=sys.stderr)
        return 1

    digest = sha256_file(source_path)
    if digest.lower() != EXPECTED_SHA256.lower():
        print(
            "error: SHA-256 mismatch for source workbook\n"
            f"  expected: {EXPECTED_SHA256.lower()}\n"
            f"  found:    {digest.lower()}",
            file=sys.stderr,
        )
        return 1

    try:
        source_values = read_source_rows(source_path)
        county_fips = load_county_fips(geo_path)
        received_at = read_text_file(
            REPO_ROOT / "work/wildfire-source/acquired-at.txt", "acquired-at.txt"
        )
        source_url = read_text_file(
            REPO_ROOT / "work/wildfire-source/source-url.txt", "source-url.txt"
        )
        datasets = build_datasets(county_fips, source_values, received_at)
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 1

    data = {
        "source": "USDA Forest Service, Wildfire Risk to Communities (2nd edition), data download updated April 15, 2026",
        "sourceUrl": "https://wildfirerisk.org",
        "datasetUrl": "https://wildfirerisk.org/download/",
        "license": "U.S. Government work: can be used without additional permissions or fees",
        "receivedAt": received_at,
        "sourceFiles": [
            {
                "name": "wrc_download_20260415.xlsx",
                "url": source_url,
                "sha256": EXPECTED_SHA256.lower(),
                "retrievedAt": received_at,
            }
        ],
        "citation": ("USDA Forest Service. 2026. Wildfire Risk to Communities. "
                     "https://wildfirerisk.org. Accessed September 29, 2026."),
        "note": ("This measure is a model estimate of wildfire risk from the USDA Forest Service. The value is a national rank for the county average. The scale runs from 0 to 100. The value is a rank, not a probability or a loss amount. Interpretations here are not the Forest Service's."),
        "datasets": datasets,
    }

    atomic_write_json(out_path, data)

    for ds in data["datasets"]:
        recs = ds["records"]
        available = sum(1 for r in recs.values() if r["status"] == "available")
        unavailable = sum(1 for r in recs.values() if r["status"] == "unavailable")
        print(f"{ds['id']}: available={available} unavailable={unavailable} "
              f"min={ds['min']} max={ds['max']}")
    print(f"output: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
