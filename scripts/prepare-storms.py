#!/usr/bin/env python3
"""Prepare NOAA Storm Events as county severe storm layers.

The measure is the mean number of reports a year, 2006-2025, per 1,000 square
miles of county land, for four groups and their total: tornado, hail,
thunderstorm wind, and flash flood plus flood. A report is one storm event in
one county, as logged in NOAA's Storm Events Database. It is not a count of
every storm: more reports come in where more people live and watch.

Source. NOAA NCEI Storm Events Database, details files v1.0, one gzipped CSV
per year. NOAA data are public domain in the United States. Land area is
ALAND_SQMI from the 2021 Census Gazetteer, which matches the atlas's 2021
county boundaries.

Joins. Only rows with CZ_TYPE "C" carry a county FIPS. Winter, heat,
high-wind and tropical storms are logged by forecast zone (CZ_TYPE "Z"), and
zones do not nest in counties, so those types are not counted. NOAA keeps the
legacy Connecticut counties for all 20 years. Bedford city, Virginia (51515)
joined Bedford County (51019) in 2013, so its 2006-2012 rows join to 51019.
Rows outside the atlas (Alaska, Hawaii, DC, territories) are skipped.

Checks. Exactly one file per year, unique event IDs across all files, and a
land area for every atlas county. A county with no reports reads 0, not
missing.

  python scripts/prepare-storms.py   build dist/data/storms.json

Download the 20 yearly files and the Gazetteer into work/storm-events/ first.
Standard library only. No network use.
"""

import argparse
import csv
import gzip
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

FILE_RE = re.compile(r"^StormEvents_details-ftp_v1\.0_d(20\d\d)_c\d+\.csv\.gz$")
GAZETTEER = "2021_Gaz_counties_national.txt"
FIRST_YEAR, LAST_YEAR = 2006, 2025
YEARS = LAST_YEAR - FIRST_YEAR + 1
GROUPS = {"Tornado": "tornado", "Hail": "hail", "Thunderstorm Wind": "wind", "Flash Flood": "flood", "Flood": "flood"}
REMAP = {"51515": "51019"}  # Bedford city joined Bedford County in 2013
PRODUCT_URL = "https://www.ncei.noaa.gov/access/storm-events-database/"
FILES_URL = "https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/StormEvents_details-ftp_v1.0_dYYYY_cYYYYMMDD.csv.gz"
GAZETTEER_URL = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2021_Gazetteer/2021_Gaz_counties_national.zip"
DATASETS = [
    ("storm-tornado", "Tornado reports", "tornado"),
    ("storm-hail", "Hail reports", "hail"),
    ("storm-wind", "Thunderstorm wind reports", "wind"),
    ("storm-flood", "Flash flood and flood reports", "flood"),
    ("storm-total", "All severe storm reports", "total"),
]

FAMILY_NOTE = "These are storm reports to NOAA's Storm Events Database. More reports come in where more people live and watch. They are not a count of every storm, and they are not a forecast."
NOTE = (
    "This value is the mean number of reports a year from 2006–2025, per 1,000 square miles of county land. Each report is one storm event in one county, as logged in NOAA's Storm Events Database. More reports come in where more people live and watch, so rural counties can read low. Winter, heat, high-wind and tropical storms are logged by forecast zone, not by county, so they are not counted here. Small independent cities have little land, so a few reports give a high rate. It is not a forecast. Source: NOAA NCEI Storm Events Database. NOAA does not endorse this atlas."
)


def repo_root():
    return Path(__file__).resolve().parent.parent


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def storm_files(source_dir):
    """Return the one details file for each year, sorted by name."""
    by_year = {}
    for path in source_dir.iterdir():
        match = FILE_RE.match(path.name)
        if not match or not FIRST_YEAR <= int(match.group(1)) <= LAST_YEAR:
            continue
        if match.group(1) in by_year:
            raise SystemExit(f"two files for {match.group(1)}: {by_year[match.group(1)].name}, {path.name}")
        by_year[match.group(1)] = path
    if len(by_year) != YEARS:
        missing = sorted(set(map(str, range(FIRST_YEAR, LAST_YEAR + 1))) - set(by_year))
        raise SystemExit(f"expected {YEARS} yearly files, missing {missing}")
    return sorted(by_year.values(), key=lambda p: p.name)


def read_areas(path):
    with path.open(newline="", encoding="utf-8") as handle:
        rows = csv.DictReader(handle, delimiter="\t")
        rows.fieldnames = [name.strip() for name in rows.fieldnames]
        return {row["GEOID"].strip(): float(row["ALAND_SQMI"].strip()) for row in rows}


def count_reports(paths, atlas):
    """Return {fips: Counter(group: reports)}, rows kept per group, and skipped FIPS."""
    counts = {}
    kept = Counter()
    skipped = Counter()
    seen = set()
    for path in paths:
        with gzip.open(path, "rt", encoding="latin-1", newline="") as handle:
            for row in csv.DictReader(handle):
                if row["EVENT_ID"] in seen:
                    raise SystemExit(f"{path.name}: event {row['EVENT_ID']} appears twice")
                seen.add(row["EVENT_ID"])
                group = GROUPS.get(row["EVENT_TYPE"])
                if not group or row["CZ_TYPE"] != "C":
                    continue
                fips = row["STATE_FIPS"].zfill(2) + row["CZ_FIPS"].zfill(3)
                fips = REMAP.get(fips, fips)
                if fips not in atlas:
                    skipped[fips] += 1
                    continue
                counts.setdefault(fips, Counter())[group] += 1
                kept[group] += 1
    return counts, kept, skipped


def rate(reports, area):
    return round(reports / YEARS / (area / 1000), 2)


def main():
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", default=str(root / "work" / "storm-events"))
    parser.add_argument("--geo", default=str(root / "dist" / "data" / "counties.geojson"))
    parser.add_argument("--out", default=str(root / "dist" / "data" / "storms.json"))
    parser.add_argument("--retrieved", default="October 28, 2026")
    args = parser.parse_args()

    source_dir = Path(args.source)
    paths = storm_files(source_dir)
    gazetteer = source_dir / GAZETTEER
    areas = read_areas(gazetteer)
    geo = json.loads(Path(args.geo).read_text(encoding="utf-8"))
    atlas = sorted(feature["properties"]["fips"] for feature in geo["features"])
    no_area = [f for f in atlas if not areas.get(f, 0) > 0]
    if no_area:
        raise SystemExit(f"atlas counties with no Gazetteer land area: {no_area}")

    counts, kept, skipped = count_reports(paths, set(atlas))
    digests = [(path.name, sha256(path)) for path in paths]
    # One digest over the ordered per-file digests, so a change to any year shows.
    combined = hashlib.sha256("".join(f"{name}:{digest}\n" for name, digest in digests).encode()).hexdigest()

    datasets = []
    for dataset_id, title, group in DATASETS:
        records = {}
        for fips in atlas:
            county = counts.get(fips, Counter())
            reports = sum(county.values()) if group == "total" else county[group]
            records[fips] = {"status": "available", "value": rate(reports, areas[fips])}
        values = [r["value"] for r in records.values()]
        datasets.append({
            "id": dataset_id,
            "title": title,
            "unit": "reports a year per 1,000 sq mi of land",
            "period": "2006–2025 average",
            "sourceUrl": PRODUCT_URL,
            "release": "NOAA NCEI Storm Events Database, details files v1.0",
            "geographyVintage": "NOAA county codes joined by FIPS to 2021 Census counties; land area from the 2021 Census Gazetteer",
            "retrievedAt": args.retrieved,
            "sourceFiles": [
                {"url": FILES_URL, "files": len(digests), "sha256": combined},
                {"url": GAZETTEER_URL, "files": 1, "sha256": sha256(gazetteer)},
            ],
            "citation": f"NOAA National Centers for Environmental Information, Storm Events Database. {PRODUCT_URL}",
            "note": NOTE,
            "direction": "higher-worse",
            "category": "climate",
            "min": min(values),
            "max": max(values),
            "records": records,
        })

    payload = {"sourceUrl": PRODUCT_URL, "note": FAMILY_NOTE, "datasets": datasets}
    out = Path(args.out)
    out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")

    print(f"source files          {len(digests)} years, combined sha256 {combined[:16]}…")
    print(f"reports kept          {dict(kept)}")
    print(f"skipped (not atlas)   {sum(skipped.values())} reports in {len(skipped)} codes")
    for dataset in datasets:
        values = [r["value"] for r in dataset["records"].values()]
        zero = sum(1 for v in values if v == 0)
        print(f"{dataset['id']:<21} {dataset['min']}–{dataset['max']}; {zero} counties at 0")
    print(f"output                {out}")


if __name__ == "__main__":
    main()
