#!/usr/bin/env python3
"""Prepare dist/data/water.json from EPA ECHO SDWA download."""

import argparse
import csv
import datetime
import hashlib
import io
import json
import os
import re
import statistics
import sys
import unicodedata
import zipfile

EXPECTED_SHA256 = "a18a20f9091c2e0466c91c83d0bac5651473441642331d09504e447a6e2ac7a4"
ZIP_NAME = "SDWA_latest_downloads.zip"
ZIP_URL = "https://echo.epa.gov/files/echodownloads/SDWA_latest_downloads.zip"

PUB_REQUIRED = {
    "PWSID", "PWS_TYPE_CODE", "PWS_ACTIVITY_CODE",
    "POPULATION_SERVED_COUNT", "STATE_CODE",
}
GEO_REQUIRED = {"PWSID", "AREA_TYPE_CODE", "COUNTY_SERVED"}
VIOL_REQUIRED = {
    "PWSID", "VIOLATION_ID", "IS_HEALTH_BASED_IND",
    "NON_COMPL_PER_BEGIN_DATE", "NON_COMPL_PER_END_DATE",
    "VIOLATION_CATEGORY_CODE",
}

STATE_POSTAL_TO_FIPS = {
    "AL": "01", "AZ": "04", "AR": "05", "CA": "06", "CO": "08",
    "CT": "09", "DE": "10", "DC": "11", "FL": "12", "GA": "13",
    "ID": "16", "IL": "17", "IN": "18", "IA": "19", "KS": "20",
    "KY": "21", "LA": "22", "ME": "23", "MD": "24", "MA": "25",
    "MI": "26", "MN": "27", "MS": "28", "MO": "29", "MT": "30",
    "NE": "31", "NV": "32", "NH": "33", "NJ": "34", "NM": "35",
    "NY": "36", "NC": "37", "ND": "38", "OH": "39", "OK": "40",
    "OR": "41", "PA": "42", "RI": "44", "SC": "45", "SD": "46",
    "TN": "47", "TX": "48", "UT": "49", "VT": "50", "VA": "51",
    "WA": "53", "WV": "54", "WI": "55", "WY": "56",
}


def remove_accents(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalize_county_name(name, state_postal=None):
    """Normalize a county name for matching."""
    if name is None:
        return ""
    s = remove_accents(str(name))
    s = s.lower()
    s = s.replace("&", " and ")
    s = re.sub(r"\bsaint\b", "st", s)
    s = re.sub(r"[^a-z0-9\s]", "", s)
    s = re.sub(r"\s+", " ", s).strip()

    while True:
        m = re.search(r"\s+(county|parish|borough|census area|municipality)$", s)
        if m:
            s = s[: m.start()].strip()
        else:
            break

    if state_postal == "LA" and s == "la salle":
        s = "lasalle"
    if state_postal == "SD" and s == "shannon":
        s = "oglala lakota"

    return s


def parse_date(s):
    if s is None:
        return None
    s = s.strip()
    if s == "" or s == "--->":
        return None

    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.datetime.strptime(s[:10], fmt).date()
        except ValueError:
            pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%m/%d/%Y %H:%M:%S"):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def violation_overlaps_window(begin_str, end_str):
    """True if a violation's noncompliance period overlaps 2023-01-01..2025-12-31."""
    begin = parse_date(begin_str)
    if begin is None:
        return False

    end = parse_date(end_str)
    window_start = datetime.date(2023, 1, 1)
    window_end = datetime.date(2025, 12, 31)

    if end is None:
        return begin <= window_end
    return begin <= window_end and end >= window_start


def compute_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().lower()


def find_member(zf, basename):
    for name in zf.namelist():
        if os.path.basename(name) == basename:
            return name
    raise KeyError(f"member not found in zip: {basename}")


def check_columns(zf, member, required):
    with zf.open(member) as f:
        text = io.TextIOWrapper(f, encoding="latin-1", newline="")
        reader = csv.reader(text)
        try:
            header = next(reader)
        except StopIteration:
            header = []
    header_set = {h.strip() for h in header}
    missing = required - header_set
    if missing:
        print(
            f"Missing required columns in {member}: {sorted(missing)}",
            file=sys.stderr,
        )
        raise SystemExit(1)


def read_acquired_at(source_path):
    candidates = [
        os.path.join(os.path.dirname(source_path), "acquired-at.txt"),
        "acquired-at.txt",
    ]
    for p in candidates:
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                return f.read().strip()
    return ""


def get_prop(props, keys, default=None):
    for k in keys:
        if k in props:
            return props[k]
    return default


def get_fips(props):
    fips = get_prop(props, ["FIPS", "fips", "GEOID", "geoid", "id"])
    if fips is None:
        return None
    s = str(fips).strip()
    if s.isdigit():
        return s.zfill(5)
    return s


def get_name(props):
    return get_prop(
        props,
        ["NAME", "name", "County", "county", "NAMELSAD", "NAMELSAD10", "NAME10"],
    )


def load_atlas_counties(geo_path):
    with open(geo_path, encoding="utf-8") as f:
        data = json.load(f)

    all_counties = {}
    mapping = {}

    for feature in data.get("features", []):
        props = feature.get("properties", {})
        fips = get_fips(props)
        name = get_name(props)
        if not fips or not name:
            continue
        state_fips = fips[:2].zfill(2)
        norm = normalize_county_name(name)
        all_counties[fips] = name
        mapping[(state_fips, norm)] = fips

    return all_counties, mapping


def process_pub(zf, member):
    active = {}
    with zf.open(member) as f:
        text = io.TextIOWrapper(f, encoding="latin-1", newline="")
        reader = csv.reader(text)
        header = [h.strip() for h in next(reader)]
        idx = {h: i for i, h in enumerate(header)}

        for row in reader:
            if row[idx["PWS_TYPE_CODE"]].strip() != "CWS":
                continue
            if row[idx["PWS_ACTIVITY_CODE"]].strip() != "A":
                continue

            pwsid = row[idx["PWSID"]].strip()
            state_code = row[idx["STATE_CODE"]].strip()
            pop_str = row[idx["POPULATION_SERVED_COUNT"]].strip()
            pop = int(pop_str) if pop_str else 0

            if len(pwsid) >= 2 and pwsid[:2].isalpha():
                state_postal = pwsid[:2].upper()
            else:
                state_postal = state_code.upper()

            state_fips = STATE_POSTAL_TO_FIPS.get(state_postal)
            if state_fips is None:
                if state_postal.isdigit() and len(state_postal) == 2:
                    state_fips = state_postal.zfill(2)

            active[pwsid] = {
                "state_postal": state_postal,
                "state_fips": state_fips,
                "population": pop,
            }

    return active


def process_geo(zf, member, active_systems, county_mapping, all_counties):
    county_systems = {fips: set() for fips in all_counties}

    with zf.open(member) as f:
        text = io.TextIOWrapper(f, encoding="latin-1", newline="")
        reader = csv.reader(text)
        header = [h.strip() for h in next(reader)]
        idx = {h: i for i, h in enumerate(header)}

        for row in reader:
            if row[idx["AREA_TYPE_CODE"]].strip() != "CN":
                continue

            pwsid = row[idx["PWSID"]].strip()
            sysrec = active_systems.get(pwsid)
            if sysrec is None:
                continue

            state_fips = sysrec["state_fips"]
            if state_fips is None:
                continue

            county_name = row[idx["COUNTY_SERVED"]].strip()
            if not county_name:
                continue

            norm = normalize_county_name(county_name, sysrec["state_postal"])
            if not norm:
                continue

            fips = county_mapping.get((state_fips, norm))
            if fips is None:
                continue

            county_systems[fips].add(pwsid)

    return county_systems


def process_violations(zf, member, active_systems):
    qualifying = set()
    systems_with = set()
    rows_read = 0

    print("Reading violations...", file=sys.stderr)

    with zf.open(member) as f:
        text = io.TextIOWrapper(f, encoding="latin-1", newline="")
        reader = csv.reader(text)
        header = [h.strip() for h in next(reader)]
        idx = {h: i for i, h in enumerate(header)}

        pwsid_i = idx["PWSID"]
        viol_id_i = idx["VIOLATION_ID"]
        health_i = idx["IS_HEALTH_BASED_IND"]
        begin_i = idx["NON_COMPL_PER_BEGIN_DATE"]
        end_i = idx["NON_COMPL_PER_END_DATE"]

        for row in reader:
            rows_read += 1
            if rows_read % 2_000_000 == 0:
                print(f"Read {rows_read:,} violation rows", file=sys.stderr)

            if row[health_i].strip() != "Y":
                continue

            pwsid = row[pwsid_i].strip()
            if pwsid not in active_systems:
                continue

            if not violation_overlaps_window(row[begin_i], row[end_i]):
                continue

            # VIOLATION_ID is unique only within a system; many systems reuse
            # the same ID, so a violation is keyed by (PWSID, VIOLATION_ID).
            qualifying.add((pwsid, row[viol_id_i].strip()))
            systems_with.add(pwsid)

    print(f"Read {rows_read:,} violation rows total", file=sys.stderr)
    return qualifying, systems_with


def compute_records(all_counties, county_systems, active_systems, systems_with_violation):
    records = {}

    for fips in sorted(all_counties.keys()):
        pwsids = county_systems.get(fips, set())
        systems_count = len(pwsids)

        if systems_count == 0:
            records[fips] = {
                "status": "unavailable",
                "value": None,
                "reason": "No active community water system in EPA's records lists this county as an area it serves.",
                "populationServed": None,
                "populationWithViolation": None,
                "systems": 0,
                "systemsWithViolation": 0,
            }
            continue

        pop_served = sum(active_systems[p]["population"] for p in pwsids)
        pwsids_with = [p for p in pwsids if p in systems_with_violation]
        pop_viol = sum(active_systems[p]["population"] for p in pwsids_with)
        systems_with_viol_count = len(pwsids_with)

        if pop_served == 0:
            records[fips] = {
                "status": "unavailable",
                "value": None,
                "reason": "Community water systems listed for this county report no population served.",
                "populationServed": None,
                "populationWithViolation": None,
                "systems": systems_count,
                "systemsWithViolation": systems_with_viol_count,
            }
        else:
            value = round(100.0 * pop_viol / pop_served, 1)
            records[fips] = {
                "status": "available",
                "value": value,
                "reason": None,
                "populationServed": pop_served,
                "populationWithViolation": pop_viol,
                "systems": systems_count,
                "systemsWithViolation": systems_with_viol_count,
            }

    return records


def build_json(records, acquired_at):
    values = [r["value"] for r in records.values() if r["status"] == "available"]
    min_val = min(values) if values else None
    max_val = max(values) if values else None

    return {
        "source": "EPA ECHO Safe Drinking Water Act data download (SDWIS), files dated July 9, 2026 (2026Q2)",
        "sourceUrl": "https://echo.epa.gov",
        "datasetUrl": "https://echo.epa.gov/tools/data-downloads/sdwa-download-summary",
        "license": "U.S. Government work (public domain); cite EPA ECHO/SDWIS",
        "receivedAt": acquired_at,
        "sourceFiles": [
            {
                "name": ZIP_NAME,
                "url": ZIP_URL,
                "sha256": EXPECTED_SHA256,
                "retrievedAt": acquired_at,
            }
        ],
        "citation": "U.S. Environmental Protection Agency, Enforcement and Compliance History Online (ECHO), SDWA data download, accessed September 29, 2026.",
        "note": "This value is the share of people on community water systems. Their system had at least one health-based Safe Drinking Water Act violation in 2023–2025. One large system can decide a county's value. One violation of any length counts. Private wells are not covered. Interpretations here are not EPA's.",
        "datasets": [
            {
                "id": "health-violations-2023-2025",
                "title": "Drinking water health-based violations",
                "unit": "percent of people on community water systems",
                "period": "2023–2025",
                "method": "Population served by active community water systems with a health-based violation overlapping 2023–2025, divided by population served by all active community water systems listing the county, times 100",
                "sourceUrl": "https://echo.epa.gov",
                "datasetUrl": "https://echo.epa.gov/tools/data-downloads/sdwa-download-summary",
                "receivedAt": acquired_at,
                "note": "This value is the share of people on community water systems in the county. Their system had a health-based violation in 2023–2025. A violation can be a contaminant level, a treatment technique or a disinfectant limit. County details show the number of people and the number of systems.",
                "direction": "higher-worse",
                "category": "water",
                "min": min_val,
                "max": max_val,
                "records": records,
            }
        ],
    }


def write_json(data, out_path):
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    tmp_path = out_path + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
            f.write("\n")
        os.replace(tmp_path, out_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def print_summary(records, active_systems, qualifying_violation_ids, systems_with_violation):
    available = sum(1 for r in records.values() if r["status"] == "available")
    unavailable = len(records) - available
    zero_count = sum(
        1 for r in records.values()
        if r["status"] == "available" and r["value"] == 0.0
    )
    values = [r["value"] for r in records.values() if r["status"] == "available"]
    median = statistics.median(values) if values else None
    max_val = max(values) if values else None

    print(f"Available: {available}", file=sys.stderr)
    print(f"Unavailable: {unavailable}", file=sys.stderr)
    print(f"Zero values: {zero_count}", file=sys.stderr)
    print(f"Median: {median}", file=sys.stderr)
    print(f"Max: {max_val}", file=sys.stderr)
    print(f"Active CWS: {len(active_systems)}", file=sys.stderr)
    print(f"Total qualifying violations: {len(qualifying_violation_ids)}", file=sys.stderr)
    print(f"Systems with violation: {len(systems_with_violation)}", file=sys.stderr)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        default="work/water-source/SDWA_latest_downloads.zip",
    )
    parser.add_argument("--geo", default="dist/data/counties.geojson")
    parser.add_argument("--out", default="dist/data/water.json")
    args = parser.parse_args(argv)

    source_path = args.source
    geo_path = args.geo
    out_path = args.out

    if not os.path.exists(source_path):
        print(f"Source not found: {source_path}", file=sys.stderr)
        return 1

    sha = compute_sha256(source_path)
    if sha != EXPECTED_SHA256:
        print(
            f"SHA-256 mismatch: expected {EXPECTED_SHA256}, got {sha}",
            file=sys.stderr,
        )
        return 1

    acquired_at = read_acquired_at(source_path)

    all_counties, county_mapping = load_atlas_counties(geo_path)

    with zipfile.ZipFile(source_path, "r") as zf:
        pub_member = find_member(zf, "SDWA_PUB_WATER_SYSTEMS.csv")
        geo_member = find_member(zf, "SDWA_GEOGRAPHIC_AREAS.csv")
        viol_member = find_member(zf, "SDWA_VIOLATIONS_ENFORCEMENT.csv")

        check_columns(zf, pub_member, PUB_REQUIRED)
        check_columns(zf, geo_member, GEO_REQUIRED)
        check_columns(zf, viol_member, VIOL_REQUIRED)

        active_systems = process_pub(zf, pub_member)
        county_systems = process_geo(
            zf, geo_member, active_systems, county_mapping, all_counties
        )
        qualifying, systems_with_violation = process_violations(
            zf, viol_member, active_systems
        )

    records = compute_records(
        all_counties, county_systems, active_systems, systems_with_violation
    )
    data = build_json(records, acquired_at)
    write_json(data, out_path)
    print_summary(records, active_systems, qualifying, systems_with_violation)

    return 0


if __name__ == "__main__":
    sys.exit(main())
