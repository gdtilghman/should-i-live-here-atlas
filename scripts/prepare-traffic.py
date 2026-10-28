#!/usr/bin/env python3
"""Prepare traffic safety data from FARS and ACS."""
import argparse
import csv
import hashlib
import io
import json
import os
import re
import statistics
import sys
import tempfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

FARS_YEARS = [2019, 2020, 2021, 2022, 2023]
ACS_NAME = "acsdt5y2023-b01003.dat"
ACS_URL = (
    "https://www2.census.gov/programs-surveys/acs/summary_file/2023/"
    "table-based-SF/data/5YRData/acsdt5y2023-b01003.dat"
)

SHA256 = {
    "FARS2019NationalCSV.zip": "0974abb92cfb04fa022631a838a3f46555025f2b011ee78ecad15bcf86c60f31",
    "FARS2020NationalCSV.zip": "b2806902b3da9b45c632499f82e1c74fd108238ae7f67e108ebf40360ee4c9c3",
    "FARS2021NationalCSV.zip": "743c19a13884614430d295289e655c5ad32b0a025a11e5b2149dfb57acae389b",
    "FARS2022NationalCSV.zip": "989448d7a2f3964264c96a3cdb220f6c413c782a33eb759781f520c5acb5f744",
    "FARS2023NationalCSV.zip": "edde841eb493e55751961b36bac2d1ce8750f601cb8e6e183a525723bb62bab0",
    ACS_NAME: "24ae3f523b4c54332ce0a71ba534569685a8a729056f975915d860d1eb943565",
}

CT_FIPS = {"09001", "09003", "09005", "09007", "09009", "09011", "09013", "09015"}

UNKNOWN_REASON = (
    "The Census count of residents for 2019–2023 uses Connecticut planning regions. These regions do not match the counties this atlas uses."
)


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().lower()


def validate_sources(source_dir):
    entries = []
    for year in FARS_YEARS:
        name = f"FARS{year}NationalCSV.zip"
        expected = SHA256[name]
        path = source_dir / name
        if not path.is_file():
            raise SystemExit(f"Missing source file: {path}")
        actual = file_sha256(path)
        if actual != expected:
            raise SystemExit(f"SHA-256 mismatch for {name}: expected {expected}, got {actual}")
        url = f"https://static.nhtsa.gov/nhtsa/downloads/FARS/{year}/National/{name}"
        entries.append({"name": name, "url": url, "sha256": expected, "retrievedAt": None})

    name = ACS_NAME
    expected = SHA256[name]
    path = source_dir / name
    if not path.is_file():
        raise SystemExit(f"Missing source file: {path}")
    actual = file_sha256(path)
    if actual != expected:
        raise SystemExit(f"SHA-256 mismatch for {name}: expected {expected}, got {actual}")
    entries.append({"name": name, "url": ACS_URL, "sha256": expected, "retrievedAt": None})
    return entries


def extract_fips_from_geo_id(value):
    s = str(value).strip()
    if not s:
        return None
    if s.isdigit() and len(s) == 5:
        return s.zfill(5)
    m = re.search(r"(\d{5})$", s)
    if m:
        return m.group(1)
    try:
        n = int(s)
        if 0 <= n < 100000:
            return f"{n:05d}"
    except ValueError:
        pass
    return None


def load_geo(geo_path):
    with open(geo_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    features = data.get("features", [])
    fips_set = set()
    for feat in features:
        props = feat.get("properties") or {}
        candidates = []
        for key in ("GEOID", "FIPS", "fips", "geoid", "id"):
            if key in props:
                candidates.append(props[key])
        if "id" in feat:
            candidates.append(feat["id"])
        for cand in candidates:
            fips = extract_fips_from_geo_id(cand)
            if fips:
                fips_set.add(fips)
                break
    if not fips_set:
        raise SystemExit(f"Could not find any county FIPS in {geo_path}")
    return sorted(fips_set)


def parse_fars(source_dir):
    deaths = {}
    unknown = 0
    for year in FARS_YEARS:
        zip_path = source_dir / f"FARS{year}NationalCSV.zip"
        with zipfile.ZipFile(zip_path) as z:
            members = [n for n in z.namelist() if n.lower().endswith("accident.csv")]
            if not members:
                raise SystemExit(f"No accident.csv in {zip_path}")
            member = members[0]
            with z.open(member) as f:
                raw = f.read()

        if raw.startswith(b"\xef\xbb\xbf"):
            raw = raw[3:]
        text = raw.decode("latin-1")
        reader = csv.reader(io.StringIO(text))
        try:
            header = next(reader)
        except StopIteration:
            raise SystemExit(f"Empty accident.csv in {zip_path}")

        header = [h.strip().upper() for h in header]
        try:
            state_idx = header.index("STATE")
            county_idx = header.index("COUNTY")
            fatals_idx = header.index("FATALS")
        except ValueError as e:
            raise SystemExit(f"Missing column in {zip_path}: {e}")

        for row in reader:
            if len(row) <= max(state_idx, county_idx, fatals_idx):
                continue
            state_s = row[state_idx].strip()
            county_s = row[county_idx].strip()
            fatals_s = row[fatals_idx].strip()
            if not state_s or not county_s or not fatals_s:
                continue
            try:
                state = int(state_s)
                county = int(county_s)
                fatals = int(float(fatals_s))
            except ValueError:
                continue

            if county in (997, 998, 999) or county == 0:
                unknown += fatals
                continue

            fips = f"{state:02d}{county:03d}"
            if fips == "46113":
                fips = "46102"
            deaths[fips] = deaths.get(fips, 0) + fatals

    return deaths, unknown


def parse_acs(source_dir):
    path = source_dir / ACS_NAME
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")

    lines = text.splitlines()
    if not lines:
        raise SystemExit(f"Empty ACS file {path}")

    first = lines[0]
    if "|" in first:
        delimiter = "|"
    elif "\t" in first:
        delimiter = "\t"
    elif "," in first:
        delimiter = ","
    else:
        delimiter = "|"

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = list(reader)
    if not rows:
        raise SystemExit(f"Empty ACS file {path}")

    header = rows[0]
    header_upper = [h.strip().upper() for h in header]
    has_header = any(
        "B01003_E001" in h or "GEO_ID" in h or "GEOID" in h
        for h in header_upper
    )

    if has_header:
        geo_idx = None
        pop_idx = None
        for i, h in enumerate(header_upper):
            if h in ("GEO_ID", "GEOID"):
                geo_idx = i
            if "B01003_E001" in h or h == "B01003_001":
                pop_idx = i
        if geo_idx is None:
            geo_idx = 0
        if pop_idx is None:
            raise SystemExit(f"Could not find B01003_E001 column in {path}")
        data_rows = rows[1:]
    else:
        geo_idx = 0
        pop_idx = 1
        data_rows = rows

    pop_by_fips = {}
    for row in data_rows:
        if len(row) <= max(geo_idx, pop_idx):
            continue
        geo = row[geo_idx].strip()
        pop_s = row[pop_idx].strip()
        if not geo or not pop_s:
            continue
        # County rows only (summary level 050). Other levels also end in
        # digits, so never take a FIPS from any other row.
        if not re.fullmatch(r"0500000US\d{5}", geo):
            continue
        fips = geo[-5:]
        try:
            pop = int(float(pop_s))
        except ValueError:
            continue
        if fips in pop_by_fips:
            raise SystemExit(f"Duplicate ACS county row for {fips}")
        pop_by_fips[fips] = pop

    return pop_by_fips


def main(argv=None):
    parser = argparse.ArgumentParser(description="Prepare traffic safety data.")
    parser.add_argument("--source-dir", default="work/traffic-source")
    parser.add_argument("--geo", default="dist/data/counties.geojson")
    parser.add_argument("--out", default="dist/data/traffic.json")
    args = parser.parse_args(argv)

    def resolve(p):
        p = Path(p)
        if p.is_absolute():
            return p
        return REPO_ROOT / p

    source_dir = resolve(args.source_dir)
    geo_path = resolve(args.geo)
    out_path = resolve(args.out)

    source_entries = validate_sources(source_dir)

    acquired_path = source_dir / "acquired-at.txt"
    if not acquired_path.is_file():
        raise SystemExit(f"Missing {acquired_path}: record when the sources were downloaded")
    received_at = acquired_path.read_text(encoding="utf-8").strip()

    for entry in source_entries:
        entry["retrievedAt"] = received_at

    geo_fips = load_geo(geo_path)
    deaths_by_fips, unknown = parse_fars(source_dir)
    pop_by_fips = parse_acs(source_dir)

    for fips in geo_fips:
        if fips in CT_FIPS:
            continue
        pop = pop_by_fips.get(fips)
        if pop is None or pop <= 0:
            raise SystemExit(f"Missing or invalid ACS population for county {fips}")

    records = {}
    available_values = []
    zero_count = 0
    for fips in geo_fips:
        deaths = int(deaths_by_fips.get(fips, 0))
        if fips in CT_FIPS:
            records[fips] = {
                "status": "unavailable",
                "value": None,
                "reason": UNKNOWN_REASON,
                "deaths": deaths,
                "population": None,
            }
        else:
            pop = int(pop_by_fips[fips])
            value = round(deaths / (5 * pop) * 100000, 1)
            records[fips] = {
                "status": "available",
                "value": value,
                "reason": None,
                "deaths": deaths,
                "population": pop,
            }
            available_values.append(value)
            if value == 0.0:
                zero_count += 1

    min_val = min(available_values) if available_values else None
    max_val = max(available_values) if available_values else None

    dataset = {
        "id": "deaths-2019-2023",
        "title": "Traffic deaths",
        "unit": "deaths per 100,000 residents a year",
        "period": "2019–2023",
        "method": (
            "FARS deaths in crashes located in the county, 2019–2023, "
            "divided by 5 times the ACS 2019–2023 population, times 100,000"
        ),
        "note": (
            "Five-year average of deaths in crashes on the county's public roads per 100,000 residents. County details show the death count and the number of residents."
        ),
        "sourceUrl": "https://www.nhtsa.gov/research-data/fatality-analysis-reporting-system-fars",
        "datasetUrl": "https://www.nhtsa.gov/file-downloads?p=nhtsa/downloads/FARS/",
        "receivedAt": received_at,
        "direction": "higher-worse",
        "category": "traffic",
        "min": min_val,
        "max": max_val,
        "records": records,
    }

    output = {
        "source": (
            "NHTSA Fatality Analysis Reporting System (FARS) 2019–2023 Final Files. Census Bureau ACS 2019–2023 5-year population."
        ),
        "sourceUrl": "https://www.nhtsa.gov/research-data/fatality-analysis-reporting-system-fars",
        "datasetUrl": "https://www.nhtsa.gov/file-downloads?p=nhtsa/downloads/FARS/",
        "license": "U.S. Government works (public domain); cite NHTSA and the Census Bureau",
        "receivedAt": received_at,
        "sourceFiles": source_entries,
        "citation": (
            "National Highway Traffic Safety Administration, Fatality Analysis Reporting System, "
            "2019–2023 Final Files; U.S. Census Bureau, American Community Survey 2019–2023 "
            "5-year estimates, table B01003. Accessed September 29, 2026."
        ),
        "note": (
            "These are deaths in motor vehicle crashes in the county per 100,000 residents a year for 2019–2023. The value describes how dangerous the county's roads are for everyone, including people passing through. It is not the risk for one resident. Small counties with busy highways can have very high values."
        ),
        "unknownCountyDeaths": unknown,
        "datasets": [dataset],
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=out_path.parent, prefix=out_path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, out_path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise

    available_count = len(available_values)
    unavailable_count = len(records) - available_count
    median_val = statistics.median(available_values) if available_values else None
    print(f"available: {available_count}")
    print(f"unavailable: {unavailable_count}")
    print(f"zero-value: {zero_count}")
    print(f"min: {min_val}")
    print(f"median: {median_val}")
    print(f"max: {max_val}")
    print(f"unknownCountyDeaths: {unknown}")


if __name__ == "__main__":
    main()
