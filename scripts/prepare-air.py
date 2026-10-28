#!/usr/bin/env python3
"""Prepare CDC PM2.5 air quality data for the atlas.

Reads CDC Environmental Public Health Tracking Network county-level PM2.5
data and produces dist/data/air.json with one record per atlas county.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SOURCE_FILES = {
    "county-annual-2018-2022.csv": (
        "df860a24facac0f2678d3d9e1b825d64b8de01a4044973b60399f77c4b0e1201"
    ),
    "sample-daily-2020-2022.csv": (
        "5f834b3aafa5eac024c56f8abc320e76c1d3cc2b674eea6b77692c6a5d7bf613"
    ),
}

YEARS = ("2020", "2021", "2022")
EXPECTED_DAYS = {"2020": 366, "2021": 365, "2022": 365}

# Using \u escapes to prevent Unicode corruption (mojibake)
# µ = MICRO SIGN, ³ = SUPERSCRIPT THREE, – = EN DASH
REASON_NO_ROWS = (
    "CDC's county PM2.5 file has no 2020–2022 value for this county."
)
REASON_BLANK = (
    "CDC's county file has no values weighted to where people live for this county in 2020–2022."
)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def pad_fips(state, county):
    return f"{int(state):02d}{int(county):03d}"


def load_annual(path):
    """Return {fips: {year: row}}. Raise on duplicate (fips, year)."""
    result = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            fips = pad_fips(row["statefips"], row["countyfips"])
            year = row["year"].strip()
            if year in result.get(fips, {}):
                raise ValueError(f"duplicate annual row for {fips}/{year}")
            result.setdefault(fips, {})[year] = row
    return result


def load_daily(path):
    """Return {(fips, year): [row, ...]}."""
    result = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            fips = pad_fips(row["statefips"], row["countyfips"])
            year = row["year"].strip()
            result.setdefault((fips, year), []).append(row)
    return result


def verify_sample(annual, daily):
    """Cross-check sample daily rows against the annual aggregate."""
    for (fips, year), rows in daily.items():
        agg = annual.get(fips, {}).get(year)
        if agg is None:
            raise ValueError(
                f"sample county {fips} year {year} missing from annual file"
            )
        pop_values = [
            r["pm25_pop_pred"].strip()
            for r in rows
            if r["pm25_pop_pred"].strip()
        ]
        agg_pop = agg["pop_mean"].strip()
        if not pop_values:
            if agg_pop:
                raise ValueError(
                    f"sample {fips}/{year}: daily pop values all blank "
                    f"but aggregate is {agg_pop}"
                )
            continue
        if not agg_pop:
            raise ValueError(
                f"sample {fips}/{year}: aggregate pop_mean blank but "
                f"daily values present"
            )
        mean = sum(float(v) for v in pop_values) / len(pop_values)
        if abs(mean - float(agg_pop)) > 1e-6:
            raise ValueError(
                f"sample {fips}/{year}: daily mean {mean} != aggregate {agg_pop}"
            )
        days = int(agg["days"])
        if len(pop_values) != days:
            raise ValueError(
                f"sample {fips}/{year}: {len(pop_values)} non-blank daily "
                f"values != days {days}"
            )


def compute_county(annual_rows):
    """Compute the record for one county from its annual rows.

    CRITICAL: value = round(mean of UNROUNDED annual values, 2).
    Annual values are rounded separately for display only.
    """
    present = [y for y in YEARS if y in annual_rows]
    if not present:
        return {
            "status": "unavailable",
            "value": None,
            "annual": None,
            "reason": REASON_NO_ROWS,
        }
    for y in YEARS:
        if y not in annual_rows or not annual_rows[y]["pop_mean"].strip():
            return {
                "status": "unavailable",
                "value": None,
                "annual": None,
                "reason": REASON_BLANK,
            }
    # Collect UNROUNDED values for averaging.
    unrounded = []
    for y in YEARS:
        row = annual_rows[y]
        days = int(row["days"])
        rows_count = int(row["rows"])
        expected = EXPECTED_DAYS[y]
        if days != rows_count:
            raise ValueError(
                f"invalid days/rows for {y}: days={days} rows={rows_count}"
            )
        if days != expected:
            raise ValueError(
                f"invalid days for {y}: days={days} expected={expected}"
            )
        unrounded.append(float(row["pop_mean"]))
    # Compute value from unrounded mean, then round once.
    value = round(sum(unrounded) / len(unrounded), 2)
    # Annual values are rounded separately for display only.
    annual = {y: round(unrounded[i], 2) for i, y in enumerate(YEARS)}
    return {
        "status": "available",
        "value": value,
        "annual": annual,
        "reason": None,
    }


def load_county_fips(geojson_path):
    with open(geojson_path, encoding="utf-8") as f:
        gj = json.load(f)
    fips_list = []
    for feat in gj["features"]:
        props = feat.get("properties", {})
        fips = (
            props.get("GEOID")
            or props.get("geoid")
            or props.get("FIPS")
            or props.get("fips")
        )
        if not fips:
            raise ValueError(f"feature missing FIPS: {props}")
        fips_list.append(str(fips))
    return fips_list


def atomic_write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        dir=str(path.parent), prefix=".air-", suffix=".json"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
            f.write("\n")
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def build(source_dir, geojson_path):
    source_dir = Path(source_dir)

    for name, expected in SOURCE_FILES.items():
        p = source_dir / name
        if not p.exists():
            raise FileNotFoundError(f"missing source file: {p}")
        actual = sha256_file(p)
        if actual != expected:
            raise ValueError(
                f"hash mismatch for {name}: {actual} != {expected}"
            )

    query_url = (source_dir / "query-url.txt").read_text(
        encoding="utf-8"
    ).strip()
    sample_query_url = (source_dir / "sample-daily-query-url.txt").read_text(
        encoding="utf-8"
    ).strip()
    acquired_at = (source_dir / "acquired-at.txt").read_text(
        encoding="utf-8"
    ).strip()

    annual = load_annual(source_dir / "county-annual-2018-2022.csv")
    daily = load_daily(source_dir / "sample-daily-2020-2022.csv")
    verify_sample(annual, daily)

    fips_list = load_county_fips(geojson_path)

    records = {}
    values = []
    available = 0
    unavailable = 0
    for fips in fips_list:
        rec = compute_county(annual.get(fips, {}))
        records[fips] = rec
        if rec["status"] == "available":
            values.append(rec["value"])
            available += 1
        else:
            unavailable += 1

    min_value = min(values) if values else None
    max_value = max(values) if values else None

    annual_csv_sha = sha256_file(source_dir / "county-annual-2018-2022.csv")
    daily_csv_sha = sha256_file(source_dir / "sample-daily-2020-2022.csv")

    source_files = [
        {
            "name": "county-annual-2018-2022.csv",
            "url": query_url,
            "sha256": annual_csv_sha,
            "retrievedAt": acquired_at,
        },
        {
            "name": "sample-daily-2020-2022.csv",
            "url": sample_query_url,
            "sha256": daily_csv_sha,
            "retrievedAt": acquired_at,
        },
    ]

    data = {
        "source": "CDC National Environmental Public Health Tracking Network: Daily County-Level PM2.5 Concentrations 2001-2022",
        "sourceUrl": "https://ephtracking.cdc.gov",
        "datasetUrl": "https://data.cdc.gov/Environmental-Health-Toxicology/Daily-County-Level-PM2-5-Concentrations-2001-2022/53mz-4zqd",
        "license": "Public Domain U.S. Government",
        "receivedAt": acquired_at,
        "sourceFiles": source_files,
        "citation": "Centers for Disease Control and Prevention. National Environmental Public Health Tracking Network. Web. Accessed: September 29, 2026. www.cdc.gov/ephtracking",
        "note": "This measure is a model estimate of long-term fine particle pollution, known as PM2.5, where people live. The EPA Downscaler combines air monitors with an air quality model. Values are averages over 2020–2022. They are not daily air quality, smoke-event counts, or personal exposure. Source: CDC National Environmental Public Health Tracking Network. Interpretations here are not CDC's.",
        "datasets": [
            {
                "id": "pm25-2020-2022",
                "title": "Fine particle pollution (PM2.5)",
                "unit": "µg/m³, population-weighted annual mean",
                "period": "2020–2022 average",
                "method": "Mean of the 2020, 2021 and 2022 annual means of CDC's daily population-weighted county PM2.5 predictions (EPA Downscaler)",
                "sourceUrl": "https://ephtracking.cdc.gov",
                "datasetUrl": "https://data.cdc.gov/Environmental-Health-Toxicology/Daily-County-Level-PM2-5-Concentrations-2001-2022/53mz-4zqd",
                "receivedAt": acquired_at,
                "note": "This value is the average for 2020, 2021 and 2022. Each year is an average of daily values, weighted to where people live. The unit is micrograms per cubic meter. Wildfire smoke can change a county's value a lot from year to year. County details show each year.",
                "direction": "higher-worse",
                "category": "air",
                "min": min_value,
                "max": max_value,
                "records": records,
            }
        ],
    }

    return data, {
        "available": available,
        "unavailable": unavailable,
        "min": min_value,
        "max": max_value,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        default="work/air-quality-source",
        help="directory containing the CDC source files",
    )
    parser.add_argument(
        "--geo",
        default=str(REPO_ROOT / "dist" / "data" / "counties.geojson"),
        help="counties GeoJSON used to enumerate atlas counties (default: dist/data/counties.geojson)",
    )
    parser.add_argument(
        "--out",
        default="dist/data/air.json",
        help="output JSON path",
    )
    args = parser.parse_args(argv)

    try:
        data, audit = build(args.source, args.geo)
        atomic_write_json(args.out, data)
        print(f"available={audit['available']} unavailable={audit['unavailable']}")
        print(f"value range: {audit['min']} - {audit['max']}")
        print(f"output: {args.out}")
        return 0
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
