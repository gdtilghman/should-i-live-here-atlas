#!/usr/bin/env python3
"""Prepare FBI reported crime as county layers: violent and property crime.

The measure is offenses known to police per 100,000 residents, 2023-2025,
pooled over the three years. Violent crime is murder and nonnegligent
manslaughter, rape, robbery and aggravated assault. Property crime is
burglary, larceny-theft and motor vehicle theft. Arson is not included.

Source. FBI UCR Return A master files, one fixed-width file a year, from the
Crime Data Explorer (key master_files/reta/reta-YYYY.zip). Layout, worked out
from the data and checked against the Crime Data API (see
docs/crime-source-audit.md): a 305-character agency header, then 12 monthly
blocks of 590 characters. In the header: ORI at 3-10, population and county
code in three slots at 44/53, 59/68, 74/83. In each month: a 17-character
head whose characters 3-7 hold the update date (blank or 0000 means the month
was not reported), then 4 cards of 28 five-digit fields: unfounded, actual,
cleared, cleared under 18. This builder reads the actual card.

Counties. Dave's rule: an agency counts fully, crimes and residents, in the
first county the FBI lists for it (Crime Data API agency list, field
"counties"). When the API has no county, the Return A county code is mapped
through a crosswalk voted from single-county agencies. Connecticut agencies
are matched by town to the legacy counties with the 2021 Census county
subdivisions. A short override table covers the rest. The five New York City
boroughs share one citywide value, because one police department serves all
five.

Coverage. Only agency-years with all 12 months reported count. A county gets
a value only if those agencies serve at least 80% of the residents the FBI
assigns to the county, pooled over the three years; otherwise it is
unavailable, never low.

  python scripts/prepare-crime.py

Inputs in work/crime/ (ignored): reta-2023.txt, reta-2024.txt,
reta-2025.txt, agencies/XX.json (Crime Data API byStateAbbr), and
2021_Gaz_cousubs_national.txt; the counties Gazetteer comes from
work/storm-events/. Standard library only. No network use.
"""

import argparse
import csv
import glob
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
YEARS = (2023, 2024, 2025)
COVERAGE = 0.8
HEADER, BLOCK, HEAD, FIELD, CARD = 305, 590, 17, 5, 140
ACTUAL = 1  # card order: unfounded, actual, cleared, cleared under 18
# Field indexes in a card.
MURDER, RAPE, ROBBERY = 0, 2, 5
AGG_ASSAULT = (11, 12, 13, 14)  # gun, knife, other weapon, hands; 15 is simple assault
BURGLARY, LARCENY, MVT = 16, 20, 21
STATE_ALIAS = {"NB": "NE"}  # the FBI uses NB for Nebraska
NYC = ("36005", "36047", "36061", "36081", "36085")
OVERRIDES = {
    # Agencies with no county in the API or Return A.
    "MOSPD00": "29510",  # St. Louis city police
    "TN01901": "47037", "TN01902": "47037", "TN01903": "47037",  # Davidson County (Nashville) agencies
    "TN01904": "47037", "TN01905": "47037",
    "RIRSP09": "44009",  # State police, Wickford barracks: Washington County
    # Connecticut boroughs and villages that are not towns.
    "CT00058": "09011", "CT00069": "09015", "CT00163": "09015", "CT00A59": "09011", "CT00B59": "09011",
}
NYPD = "NY03030"
NOTE = (
    "This value is crimes known to police per 100,000 residents, 2023–2025, from agencies that reported all 12 months. "
    "It counts reports, not all crime: many crimes are never reported. An agency counts fully in the first county the FBI lists for it, "
    "so a city that spans counties adds to one county only. A county is unavailable when its reporting agencies serve under 80% of its residents. "
    "The FBI advises against ranking places with these data. Source: FBI Uniform Crime Reporting Program, Return A. The FBI does not endorse this atlas."
)
FAMILY_NOTE = "These are crimes reported to police and sent to the FBI. Not every crime is reported, and not every agency reports every month. The FBI advises against ranking places with these data."


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def norm(name):
    name = unicodedata.normalize("NFKD", name.upper()).encode("ascii", "ignore").decode()
    name = name.replace("SAINT ", "ST ").replace("STE. ", "ST ").replace("STE ", "ST ").replace("ST. ", "ST ")
    return re.sub(r"[^A-Z]", "", name)


def read_gazetteer(path):
    by_state = defaultdict(dict)
    with path.open(newline="", encoding="utf-8") as handle:
        rows = csv.DictReader(handle, delimiter="\t")
        rows.fieldnames = [n.strip() for n in rows.fieldnames]
        for row in rows:
            by_state[row["USPS"].strip()][norm(row["NAME"].strip())] = row["GEOID"].strip()
    return by_state


def find_county(gazetteer, state, name):
    names = gazetteer.get(state, {})
    key = norm(name)
    for suffix in ("COUNTY", "PARISH", "", "CITY"):
        if key + suffix in names:
            return names[key + suffix]
    return None


def ct_towns(path):
    towns = {}
    with path.open(newline="", encoding="utf-8") as handle:
        rows = csv.DictReader(handle, delimiter="\t")
        rows.fieldnames = [n.strip() for n in rows.fieldnames]
        for row in rows:
            if row["USPS"].strip() == "CT":
                towns[re.sub(r" town$", "", row["NAME"].strip()).upper()] = row["GEOID"].strip()[:5]
    return towns


def api_agencies(directory):
    agencies = {}
    for path in sorted(directory.glob("*.json")):
        for group in json.loads(path.read_text(encoding="utf-8")).values():
            for agency in group:
                names = [n.strip() for n in (agency.get("counties") or "").split(",")]
                agencies[agency["ori"]] = [n for n in names if n and n not in ("NOT SPECIFIED", "UNMAPPED COUNTY")]
    return agencies


def records(path):
    with path.open(encoding="ascii") as handle:
        for line in handle:
            line = line.rstrip("\n")
            if len(line) != HEADER + 12 * BLOCK:
                raise SystemExit(f"{path.name}: record of {len(line)} characters")
            if line[0] == "1":
                yield line


def population(record):
    return sum(int(record[a:a + 9] or 0) for a in (44, 59, 74))


def month_reported(record, month):
    date = record[HEADER + BLOCK * month + 3:HEADER + BLOCK * month + 7]
    return date.strip() not in ("", "0000")


OVERPUNCH = {**{c: (1, i) for i, c in enumerate("{ABCDEFGHI")}, **{c: (-1, i) for i, c in enumerate("}JKLMNOPQR")}}


def field(cell):
    """Read a five-character count. A letter in the last place is a COBOL
    overpunch sign: J-R are -1 to -9 (corrections to earlier months)."""
    if cell.isdigit():
        return int(cell)
    if cell[:-1].isdigit() and cell[-1] in OVERPUNCH:
        sign, digit = OVERPUNCH[cell[-1]]
        return sign * int(cell[:-1] + str(digit))
    return None


def actual(record, month):
    start = HEADER + BLOCK * month + HEAD + ACTUAL * CARD
    values = [field(record[start + i * FIELD:start + i * FIELD + FIELD]) for i in range(26)]
    if None in values:
        return None
    violent = values[MURDER] + values[RAPE] + values[ROBBERY] + sum(values[i] for i in AGG_ASSAULT)
    return violent, values[BURGLARY] + values[LARCENY] + values[MVT]


def code_crosswalk(paths, agencies, gazetteer):
    """Map (state, Return A county code) to FIPS by a vote of single-county agencies."""
    votes = defaultdict(Counter)
    for path in paths:
        for r in records(path):
            names = agencies.get(r[3:10] + "00")
            if names and len(names) == 1:
                votes[(STATE_ALIAS.get(r[3:5], r[3:5]), r[53:56])][names[0]] += 1
    crosswalk = {}
    for (state, code), names in votes.items():
        if code.strip() in ("", "00", "000", "300"):
            continue
        fips = find_county(gazetteer, state, names.most_common(1)[0][0])
        if fips:
            crosswalk[(state, code)] = fips
    return crosswalk


def county_of(record, agencies, gazetteer, crosswalk, towns):
    """Return (FIPS, route) for an agency's main county, or (None, reason)."""
    ori = record[3:10]
    state = STATE_ALIAS.get(ori[:2], ori[:2])
    if ori == NYPD:
        return "NYC", "new york city"
    if ori in OVERRIDES:
        return OVERRIDES[ori], "override"
    if state == "CT":
        fips = towns.get(record[120:144].strip())
        return (fips, "ct town") if fips else (None, "ct agency with no town")
    names = agencies.get(ori + "00")
    if names:
        fips = find_county(gazetteer, state, names[0])
        if fips:
            return fips, "api county"
    fips = crosswalk.get((state, record[53:56]))
    return (fips, "county code") if fips else (None, "no county")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", default=str(ROOT / "work" / "crime"))
    parser.add_argument("--gazetteer", default=str(ROOT / "work" / "storm-events" / "2021_Gaz_counties_national.txt"))
    parser.add_argument("--geo", default=str(ROOT / "dist" / "data" / "counties.geojson"))
    parser.add_argument("--out", default=str(ROOT / "dist" / "data" / "crime.json"))
    parser.add_argument("--retrieved", default="October 28, 2026")
    args = parser.parse_args()

    source = Path(args.source)
    paths = [source / f"reta-{year}.txt" for year in YEARS]
    gazetteer = read_gazetteer(Path(args.gazetteer))
    towns = ct_towns(source / "2021_Gaz_cousubs_national.txt")
    agencies = api_agencies(source / "agencies")
    crosswalk = code_crosswalk(paths, agencies, gazetteer)
    atlas = sorted(f["properties"]["fips"] for f in json.loads(Path(args.geo).read_text(encoding="utf-8"))["features"])
    states = {f[:2] for f in atlas}
    fips_state = {fips: state for state, names in gazetteer.items() for fips in names.values()}
    lower48 = {s for s in gazetteer if any(fips_state.get(f) == s for f in atlas)}

    totals = defaultdict(lambda: {"violent": 0, "property": 0, "covered": 0, "residents": 0})
    routes, unplaced, bad = Counter(), Counter(), Counter()
    assignment = {}
    for year, path in zip(YEARS, paths):
        for r in records(path):
            if STATE_ALIAS.get(r[3:5], r[3:5]) not in lower48:
                continue
            unit, route = county_of(r, agencies, gazetteer, crosswalk, towns)
            pop = population(r)
            if not unit:
                if pop:
                    unplaced[route] += 1
                continue
            if unit != "NYC" and unit not in set(atlas):
                unplaced["county not in atlas"] += 1
                continue
            if unit in NYC:
                unit = "NYC"
            routes[route] += 1
            assignment[r[3:10]] = unit
            county = totals[unit]
            county["residents"] += pop
            if not all(month_reported(r, m) for m in range(12)):
                continue
            months = [actual(r, m) for m in range(12)]
            if None in months:
                bad[year] += 1
                continue
            county["covered"] += pop
            county["violent"] += sum(v for v, _ in months)
            county["property"] += sum(p for _, p in months)

    def record_for(unit):
        t = totals.get(unit)
        if not t or not t["residents"]:
            return {"status": "unavailable", "value": None, "reason": "No reporting agency with residents is placed in this county."}, None
        share = t["covered"] / t["residents"]
        if share < COVERAGE:
            return {"status": "unavailable", "value": None, "reason": f"Agencies that reported all 12 months serve {share:.0%} of residents, under the 80% rule."}, None
        return None, t

    datasets = []
    for dataset_id, title, key in (("violent-crime", "Violent crime", "violent"), ("property-crime", "Property crime", "property")):
        recs = {}
        for fips in atlas:
            unit = "NYC" if fips in NYC else fips
            missing, t = record_for(unit)
            if missing:
                recs[fips] = missing
                continue
            value = round(t[key] / t["covered"] * 100000, 1)
            recs[fips] = {"status": "available", "value": value, "coverage": round(t["covered"] / t["residents"], 3)}
            if unit == "NYC":
                recs[fips]["reason"] = "New York City value: one police department serves all five boroughs."
        values = [r["value"] for r in recs.values() if r["status"] == "available"]
        datasets.append({
            "id": dataset_id, "title": title,
            "unit": "crimes a year per 100,000 residents", "period": "2023–2025 average",
            "sourceUrl": "https://cde.ucr.cjis.gov/LATEST/webapp/#/pages/downloads",
            "release": "FBI UCR Return A master files 2023–2025",
            "geographyVintage": "Agencies placed in their first FBI-listed county; 2021 Census counties",
            "retrievedAt": args.retrieved,
            "sourceFiles": [{"url": f"https://cde.ucr.cjis.gov/LATEST/s3/signedurl?key=master_files/reta/reta-{y}.zip", "files": 1, "sha256": sha256(p)} for y, p in zip(YEARS, paths)],
            "citation": "FBI Uniform Crime Reporting Program, Return A master files, Crime Data Explorer. https://cde.ucr.cjis.gov/",
            "note": NOTE, "direction": "higher-worse", "category": "community",
            "min": min(values), "max": max(values),
            "records": recs,
        })

    payload = {"sourceUrl": "https://cde.ucr.cjis.gov/", "note": FAMILY_NOTE, "datasets": datasets}
    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    (source / "agency-county.json").write_text(json.dumps(assignment, sort_keys=True))

    statuses = Counter(r["status"] for r in datasets[0]["records"].values())
    print(f"crosswalk codes       {len(crosswalk)}")
    print(f"agency-year routes    {dict(routes)}")
    print(f"unplaced with people  {dict(unplaced)}")
    print(f"bad full-year records {dict(bad)}")
    print(f"county statuses       {dict(statuses)}")
    for d in datasets:
        print(f"{d['id']:<15} {d['min']}–{d['max']}")
    print(f"output                {args.out}")


if __name__ == "__main__":
    main()
