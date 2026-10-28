#!/usr/bin/env python3
"""Prepare NOAA nClimGrid-Daily as a county heat layer: days at or above 95°F.

The measure is the mean number of days a year, 1991-2020, on which a county's
area-average daily maximum temperature reached 95°F (35°C). It is a climate
normal from smoothed gridded observations. It is not a thermometer reading, it
hides urban heat islands and elevation differences inside a county, and it is
not a projection of future heat. The layer note says so.

Source. NOAA NCEI nClimGrid-Daily v1.0.0, county area averages of daily maximum
temperature, the "scaled" files (adjusted to match monthly nClimGrid), one CSV
per month. They are read from NOAA's open-data mirror on AWS, which carries the
same files as NCEI's web folder; this environment cannot reach ncei.noaa.gov
directly. NOAA data are public domain in the United States.

Joins. Region codes use NCEI state numbers, not FIPS, so NOAA's published
crosswalk (doc/us-state-codes_ncei-to-fips.csv) maps them. The atlas has no
District of Columbia, so NOAA's DC row is unused. NOAA publishes no separate
average for Lexington city, Virginia, which Rockbridge County surrounds; it is
unavailable with that reason rather than given Rockbridge's value.

Checks. Every month must have exactly its calendar days of real values, with
-999.99 only as padding after the last day. Any gap fails the build rather than
silently shortening a year.

  python scripts/prepare-heat.py --fetch   download the 360 monthly files
  python scripts/prepare-heat.py           build dist/data/climate.json

Standard library only. The network is used only with --fetch.
"""

import argparse
import calendar
import csv
import hashlib
import json
import os
import ssl
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BUCKET = "https://noaa-nclimgrid-daily-pds.s3.amazonaws.com"
FILE_PATTERN = "access/averages/{year}/tmax-{year}{month:02d}-cty-scaled.csv"
CROSSWALK = "doc/us-state-codes_ncei-to-fips.csv"
PRODUCT_URL = "https://www.ncei.noaa.gov/products/land-based-station/nclimgrid-daily"
FIRST_YEAR, LAST_YEAR = 1991, 2020
THRESHOLD_C = 35.0  # 95°F exactly
PADDING = -999.99
UNAVAILABLE = {
    "51678": "NOAA publishes no separate area average for Lexington city. Rockbridge County surrounds the city. No value is borrowed from the surrounding county.",
}

NOTE = (
    "This value is the mean number of days a year from 1991–2020. On those days, the county's area-average daily high reached 95°F. NOAA estimates values between weather stations on a 5 km grid. It then averages the grid over the county. So this is a smoothed climate normal, not a thermometer reading. It hides urban heat islands and elevation differences within a county. The same 95°F means different things in humid and dry places. It is not a projection of future heat. Source: NOAA NCEI nClimGrid-Daily v1.0.0. NOAA does not endorse this atlas."
)


def repo_root():
    return Path(__file__).resolve().parent.parent


def months():
    for year in range(FIRST_YEAR, LAST_YEAR + 1):
        for month in range(1, 13):
            yield year, month


def fetch(source_dir):
    """Download the crosswalk and every monthly file not already present."""
    source_dir.mkdir(parents=True, exist_ok=True)
    context = ssl.create_default_context(cafile=os.environ.get("SSL_CERT_FILE") or None)
    keys = [CROSSWALK] + [FILE_PATTERN.format(year=y, month=m) for y, m in months()]

    def get(key):
        target = source_dir / Path(key).name
        if target.exists() and target.stat().st_size > 0:
            return key, "kept"
        with urllib.request.urlopen(f"{BUCKET}/{key}", context=context, timeout=120) as response:
            data = response.read()
        target.write_bytes(data)
        return key, "fetched"

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(get, keys))
    fetched = sum(1 for _, how in results if how == "fetched")
    print(f"files                 {len(results)} ({fetched} fetched, {len(results) - fetched} already present)")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_crosswalk(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["NCEI_code"].strip(): row["FIPS_code"].strip() for row in csv.DictReader(handle)}


def count_hot_days(source_dir, crosswalk):
    """Return {fips: {year: hot days}} and the per-file digests."""
    hot = {}
    digests = []
    for year, month in months():
        path = source_dir / Path(FILE_PATTERN.format(year=year, month=month)).name
        if not path.exists():
            raise SystemExit(f"missing {path.name}; run with --fetch")
        digests.append((path.name, sha256(path)))
        days = calendar.monthrange(year, month)[1]
        seen = set()
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.reader(handle):
                region, code, _, row_year, row_month, element = (cell.strip() for cell in row[:6])
                if region != "cty" or element != "TMAX" or int(row_year) != year or int(row_month) != month:
                    raise SystemExit(f"{path.name}: unexpected row header {row[:6]}")
                values = [float(cell) for cell in row[6:]]
                real, padding = values[:days], values[days:]
                if any(v == PADDING for v in real) or any(v != PADDING for v in padding):
                    raise SystemExit(f"{path.name} {code}: expected {days} real days then padding")
                if any(not -60 < v < 60 for v in real):
                    raise SystemExit(f"{path.name} {code}: implausible temperature")
                state = crosswalk.get(code[:2])
                if not state:
                    raise SystemExit(f"{path.name}: no FIPS state for NCEI code {code[:2]}")
                fips = state + code[2:]
                if fips in seen:
                    raise SystemExit(f"{path.name}: {fips} appears twice")
                seen.add(fips)
                years = hot.setdefault(fips, {})
                years[year] = years.get(year, 0) + sum(1 for v in real if v >= THRESHOLD_C)
    return hot, digests


def atlas_counties(path):
    geo = json.loads(path.read_text(encoding="utf-8"))
    return [feature["properties"]["fips"] for feature in geo["features"]]


def build(atlas, hot):
    records = {}
    year_count = LAST_YEAR - FIRST_YEAR + 1
    for fips in atlas:
        if fips in UNAVAILABLE:
            records[fips] = {"status": "unavailable", "value": None, "reason": UNAVAILABLE[fips]}
            continue
        years = hot.get(fips)
        if not years or len(years) != year_count:
            raise SystemExit(f"{fips}: expected {year_count} years, found {len(years or {})}")
        series = [years[y] for y in range(FIRST_YEAR, LAST_YEAR + 1)]
        records[fips] = {"status": "available", "value": round(sum(series) / year_count, 1)}
    return records


def main():
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fetch", action="store_true", help="download the source files first")
    parser.add_argument("--source", default=str(root / "work" / "heat-source"))
    parser.add_argument("--geo", default=str(root / "dist" / "data" / "counties.geojson"))
    parser.add_argument("--out", default=str(root / "dist" / "data" / "climate.json"))
    parser.add_argument("--series", default=str(root / "work" / "heat-source" / "annual-hot-days.json"))
    parser.add_argument("--retrieved", default="September 29, 2026")
    args = parser.parse_args()

    source_dir = Path(args.source)
    if args.fetch:
        fetch(source_dir)
    crosswalk = read_crosswalk(source_dir / Path(CROSSWALK).name)
    hot, digests = count_hot_days(source_dir, crosswalk)
    atlas = atlas_counties(Path(args.geo))
    records = build(atlas, hot)

    unused = sorted(set(hot) - set(atlas))
    missing = sorted(f for f in atlas if f not in hot and f not in UNAVAILABLE)
    if missing:
        raise SystemExit(f"atlas counties with no source row: {missing}")
    if sorted(f for f in UNAVAILABLE if f in hot):
        raise SystemExit("a county marked unavailable now has source data; review UNAVAILABLE")

    # One digest over the ordered per-file digests, so a change to any month shows.
    combined = hashlib.sha256("".join(f"{name}:{digest}\n" for name, digest in digests).encode()).hexdigest()
    values = [r["value"] for r in records.values() if r["status"] == "available"]
    dataset = {
        "id": "hot-days-95f",
        "title": "Days at or above 95°F",
        "unit": "days a year with a county-average high of 95°F or more",
        "period": "1991–2020 average",
        "sourceUrl": PRODUCT_URL,
        "release": "NOAA NCEI nClimGrid-Daily v1.0.0, scaled county averages",
        "geographyVintage": "NOAA county area averages; joined by FIPS through NOAA's state-code crosswalk",
        "retrievedAt": args.retrieved,
        "sourceFiles": [{"url": f"{BUCKET}/access/averages/YYYY/tmax-YYYYMM-cty-scaled.csv",
                         "files": len(digests), "sha256": combined}],
        "citation": f"NOAA NCEI nClimGrid-Daily, version 1.0.0. {PRODUCT_URL}",
        "note": NOTE,
        "direction": "higher-worse",
        "category": "climate",
        "min": min(values),
        "max": max(values),
        "records": {fips: records[fips] for fips in sorted(records)},
    }
    payload = {
        "sourceUrl": PRODUCT_URL,
        "note": "These climate normals come from NOAA observations on a grid. They describe typical past conditions across a county. They do not describe any one place in the county. They do not describe the future.",
        "datasets": [dataset],
    }
    out = Path(args.out)
    out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")

    series_path = Path(args.series)
    series_path.write_text(json.dumps({
        "measure": "days with county-average tmax >= 35.0 C, per calendar year",
        "years": [FIRST_YEAR, LAST_YEAR],
        "files": dict(digests),
        "counties": {fips: [hot[fips][y] for y in range(FIRST_YEAR, LAST_YEAR + 1)] for fips in sorted(hot)},
    }, separators=(",", ":")), encoding="utf-8")

    statuses = {}
    for record in records.values():
        statuses[record["status"]] = statuses.get(record["status"], 0) + 1
    zero = sum(1 for v in values if v == 0)
    print(f"source files          {len(digests)} months, combined sha256 {combined[:16]}…")
    print(f"source counties       {len(hot)}; unused (not in atlas) {unused}")
    print(f"atlas records         {len(records)} {statuses}")
    print(f"value range           {min(values)}–{max(values)} days a year; {zero} counties average 0.0 (under 0.05 days a year)")
    print(f"output                {out}")
    print(f"annual series         {series_path}")


if __name__ == "__main__":
    main()
