#!/usr/bin/env python3
"""Prepare the HRSA primary-care HPSA download as a county layer.

The number this produces is an administrative priority score for placing
clinicians. It is not a measured provider supply rate and it says nothing about
whether any person can get an appointment. The layer notes say so, because the
number reads as a measure of access unless it is told not to.

Four judgements were settled by the user on September 17, 2026 and are
implemented here, not re-opened. They are recorded with their evidence in
docs/enrichment-research.md, and guarded by scripts/test-healthcare.cjs:

  Designated rows alone set the score. Proposed For Withdrawal is excluded,
  because a proposal to withdraw says the designation may no longer hold, but
  the count travels with each county so the exclusion is visible.

  The county value is the maximum score over its designated components, and
  every scored county carries the basis. 647 of 2,809 have no whole-county
  component, so for those the number describes part of a county.

  Connecticut cannot join. The source uses 2022 planning regions and the atlas
  uses legacy counties. Those counties are unavailable with a reason, never
  not designated, because the source never said they had no designation.

  A county with no designated component is not_designated. That is not missing,
  not zero, and not evidence of adequate access.

Standard library only. No network. The input is never modified.
"""

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REQUIRED_COLUMNS = (
    "Common State County FIPS Code",
    "HPSA Status",
    "HPSA Score",
    "HPSA Component Type Description",
)

SOURCE_URL = "https://data.hrsa.gov/topics/health-workforce/shortage-areas"
CSV_URL = "https://data.hrsa.gov/DataDownload/DD_Files/BCD_HPSA_FCT_DET_PC.csv"

CT_REASON = ("The source uses 2022 planning regions. These regions do not match the counties this atlas uses.")

NOTE = ("These are administrative shortage designations. The value is a priority score for placing clinicians. It is not a measured rate of the supply of providers. It is not a statement about one person's access to care.")

# The app shows the family note beside this one, so this one must not repeat
# it, and visitors read it, so it names no internal fields.
DATASET_NOTE = ("Some designations cover only part of a county. For those counties, the score describes that part. It does not describe the whole county. Counties with no current designation appear separately. That is not evidence of adequate access.")

EXPECTED_ATLAS = 3107
EXPECTED_CT = 8


def repo_root():
    return Path(__file__).resolve().parent.parent


def usable_fips(value):
    """A join FIPS is usable only when it is exactly five digits.

    The source uses the literal sentinel XXXXX for a component whose county is
    not determined. That sentinel is five characters long, so a length test
    alone accepts it as a county. It must not become one.
    """
    if value is None:
        return None
    text = value.strip()
    return text if len(text) == 5 and text.isdigit() else None


def parse_score(value):
    """Scores are whole numbers, but a source that writes 16.0 must not vanish.

    int() alone raises on "16.0" and a bare except would drop the row in
    silence, which would understate a county's shortage.
    """
    text = (value or "").strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def atlas_counties(path):
    geo = json.loads(Path(path).read_text(encoding="utf-8"))
    return [f["properties"]["fips"] for f in geo.get("features", [])
            if f.get("properties", {}).get("fips")]


def read_source(path):
    """Accumulate per county. Only the four needed columns are kept.

    Holding all 66 columns for 79,750 rows costs about 400 MB for no reason.
    """
    counts = Counter()
    statuses = Counter()
    scores = defaultdict(list)
    whole_county = set()
    proposed = Counter()
    seen = set()

    # encoding is explicit because county names such as Dona Ana are not ASCII
    # and the default codec differs by platform.
    with open(path, encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames or []
        missing = [name for name in REQUIRED_COLUMNS if name not in header]
        if missing:
            sys.exit(f"missing column(s) in {path}: {', '.join(missing)}")

        for row in reader:
            counts["rows"] += 1
            status = (row["HPSA Status"] or "").strip()
            statuses[status] += 1

            raw = (row["Common State County FIPS Code"] or "").strip()
            fips = usable_fips(raw)
            if fips is None:
                counts["unusable"] += 1
                if raw == "XXXXX":
                    counts["sentinel"] += 1
                    if status == "Designated":
                        counts["sentinel_designated"] += 1
                continue

            seen.add(fips)
            if status == "Designated":
                score = parse_score(row["HPSA Score"])
                if score is None:
                    counts["unparsed_score"] += 1
                    continue
                scores[fips].append(score)
                if (row["HPSA Component Type Description"] or "").strip() == "Single County":
                    whole_county.add(fips)
            elif status == "Proposed For Withdrawal":
                proposed[fips] += 1

    return counts, statuses, scores, whole_county, proposed, seen


def build_records(atlas, scores, whole_county, proposed):
    records = {}
    for fips in sorted(atlas):
        if fips.startswith("09"):
            records[fips] = {"status": "unavailable", "value": None, "reason": CT_REASON}
            continue
        county_scores = scores.get(fips)
        if county_scores:
            records[fips] = {
                "status": "available",
                "value": max(county_scores),
                "componentBasis": "whole-county" if fips in whole_county else "sub-county",
                "components": len(county_scores),
                # Always written, including zero. An absent field cannot be told
                # apart from a count that was never taken.
                "proposedForWithdrawal": proposed.get(fips, 0),
            }
        else:
            records[fips] = {"status": "not_designated", "value": None,
                             "proposedForWithdrawal": proposed.get(fips, 0)}
    return records


def report(counts, statuses, records, seen, atlas_set):
    scored = [r for r in records.values() if r["status"] == "available"]
    distribution = Counter(r["status"] for r in records.values())
    whole = sum(1 for r in scored if r["componentBasis"] == "whole-county")
    values = [r["value"] for r in scored]

    print(f"rows read             {counts['rows']}")
    for name in ("Designated", "Withdrawn", "Proposed For Withdrawal"):
        print(f"  {name:<19} {statuses.get(name, 0)}")
    print(f"unusable fips rows    {counts['unusable']}")
    print(f"  of which XXXXX      {counts['sentinel']} "
          f"({counts['sentinel_designated']} designated)")
    if counts["unparsed_score"]:
        print(f"  unreadable scores   {counts['unparsed_score']}")
    print(f"source counties       {len(seen)}")
    print(f"  not in the atlas    {len(seen - atlas_set)}")
    print(f"atlas counties        {len(records)}")
    print(f"status distribution   {dict(sorted(distribution.items()))}")
    print(f"counties scored       {len(scored)}")
    print(f"  whole-county basis  {whole}")
    print(f"  sub-county only     {len(scored) - whole}")
    print(f"Connecticut           {sum(1 for f in records if f.startswith('09'))}")
    print(f"score range           {min(values)} to {max(values)}")
    return values


def verify(records, values):
    failures = []
    if len(records) != EXPECTED_ATLAS:
        failures.append(f"emitted {len(records)}, expected {EXPECTED_ATLAS}")
    connecticut = [f for f in records if f.startswith("09")]
    if len(connecticut) != EXPECTED_CT:
        failures.append(f"{len(connecticut)} Connecticut counties, expected {EXPECTED_CT}")
    for fips, record in records.items():
        # The invariant: a value exists exactly when the status is available.
        if (record["status"] == "available") != (record["value"] is not None):
            failures.append(f"{fips}: status {record['status']} with value {record['value']}")
        if record["value"] is not None and not 3 <= record["value"] <= 25:
            failures.append(f"{fips}: value {record['value']} outside 3 to 25")
        if fips.startswith("09") and record["status"] != "unavailable":
            failures.append(f"{fips}: Connecticut is {record['status']}, not unavailable")
    if not values:
        failures.append("no county was scored")

    if failures:
        print()
        for line in failures[:10]:
            print("FAIL", line)
        if len(failures) > 10:
            print(f"({len(failures) - 10} more)")
        return False
    print("every atlas county has a record and the status matches the value")
    return True


def main():
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=str(
        root / "work" / "healthcare-hpsa-audit" / "BCD_HPSA_FCT_DET_PC.csv"))
    parser.add_argument("--geo", default=str(root / "dist" / "data" / "counties.geojson"))
    parser.add_argument("--out", default=str(root / "dist" / "data" / "healthcare.json"))
    parser.add_argument("--retrieved", default="September 16, 2026")
    args = parser.parse_args()

    atlas = atlas_counties(args.geo)
    counts, statuses, scores, whole_county, proposed, seen = read_source(args.source)
    records = build_records(atlas, scores, whole_county, proposed)
    values = report(counts, statuses, records, seen, set(atlas))

    payload = {
        "sourceUrl": SOURCE_URL,
        "note": NOTE,
        "datasets": [{
            "id": "hpsa-primary-care",
            "title": "Primary care shortage designation score",
            "unit": "shortage priority score",
            "period": args.retrieved,
            "direction": "higher-worse",
            "category": "healthcare",
            "sourceUrl": CSV_URL,
            "note": DATASET_NOTE,
            "min": min(values) if values else None,
            "max": max(values) if values else None,
            "records": records,
        }],
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                   encoding="utf-8")
    print(f"output                {out}")
    print()
    if not verify(records, values):
        sys.exit(1)


if __name__ == "__main__":
    main()
