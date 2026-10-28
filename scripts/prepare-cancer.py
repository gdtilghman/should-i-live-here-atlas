#!/usr/bin/env python3
"""Build the pinned State Cancer Profiles county incidence snapshot."""
from __future__ import annotations
import argparse, csv, hashlib, json, math, re
from datetime import datetime, timezone
from pathlib import Path

DATASETS = {
    "001": ("scp-all-cancer.csv", "All Cancer Sites", "Both sexes", "0", "001"),
    "047": ("scp-047.csv", "Lung & Bronchus", "Both sexes", "0", "047"),
    "020": ("scp-020.csv", "Colon & Rectum", "Both sexes", "0", "020"),
    "055": ("scp-055.csv", "Breast (Female)", "Female", "2", "055"),
    "066": ("scp-066.csv", "Prostate", "Male", "1", "066"),
    "001-male": ("scp-001-male.csv", "All Cancer Sites", "Male", "1", "001"),
    "001-female": ("scp-001-female.csv", "All Cancer Sites", "Female", "2", "001"),
    "047-male": ("scp-047-male.csv", "Lung & Bronchus", "Male", "1", "047"),
    "047-female": ("scp-047-female.csv", "Lung & Bronchus", "Female", "2", "047"),
    "020-male": ("scp-020-male.csv", "Colon & Rectum", "Male", "1", "020"),
    "020-female": ("scp-020-female.csv", "Colon & Rectum", "Female", "2", "020"),
}
PERIOD = "2018\u20132022"
UNIT = "cases per 100,000 people a year"
NOTE = "These values are historical diagnosis rates for groups of people. They do not estimate your personal risk. They do not show that living in a county causes cancer."
STATES_48 = {"01","04","05","06","08","09","10","12","13","16","17","18","19","20","21","22","23","24","25","26","27","28","29","30","31","32","33","34","35","36","37","38","39","40","41","42","44","45","46","47","48","49","50","51","53","54","55","56"}
FIPS_RE = re.compile(r"^\d{5}$")
NUM_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")

def num(raw):
    x = raw.strip().replace(",", "")
    return float(x) if NUM_RE.fullmatch(x) else None

def count(raw):
    x = raw.strip().replace(",", "")
    return int(x) if x.isdigit() else None

def source_url(cancer_id, sex_id):
    return ("https://statecancerprofiles.cancer.gov/incidencerates/index.php?areatype=county&cancer="
            f"{cancer_id}&race=00&sex={sex_id}&age=001&type=incd&statefips=00&datatype=01&"
            "ruralurban=0&sortVariableName=rate&sortOrder=desc&output=1")

def parse(path: Path, ident: str):
    rows = list(csv.reader(path.open(encoding="utf-8-sig", newline="")))
    hi = next((i for i, r in enumerate(rows) if r and r[0].strip() == "County"), None)
    assert hi is not None and hi >= 4, f"{path}: missing SCP preamble/header"
    preamble_rows = [tuple(x.strip() for x in r) for r in rows[:hi]]
    preamble = " ".join(",".join(r) for r in preamble_rows)
    assert "2018-2022" in preamble, f"{path}: unexpected period"
    expected_sex = {"0": "Both Sexes", "1": "Male", "2": "Female"}[DATASETS[ident][3]]
    source_title = DATASETS[ident][1].split(" (")[0]
    assert any(r and r[0] == f"{source_title} (All Stages^), 2018-2022" for r in preamble_rows), f"{path}: unexpected cancer title"
    selection = next((r[0] for r in preamble_rows if r and r[0].startswith("All Races")), "")
    assert selection == f"All Races (includes Hispanic), {expected_sex}, All Ages", f"{path}: unexpected selections"
    h = rows[hi]
    assert len(h) >= 14 and h[1].strip() == "FIPS" and "Age-Adjusted Incidence Rate" in h[3]
    assert h[4].strip().startswith("Lower 95%") and h[5].strip().startswith("Upper 95%") and h[9].strip() == "Average Annual Count"
    assert h[10].strip() == "Recent Trend" and "Recent 5-Year Trend" in h[11] and h[12].strip().startswith("Lower 95%") and h[13].strip().startswith("Upper 95%")
    records = {}
    for row in rows[hi + 1:]:
        if len(row) < 10 or not FIPS_RE.fullmatch(row[1].strip()):
            continue
        fips = row[1].strip()
        if fips == "00000" or fips[:2] not in STATES_48:
            continue
        source_fips = fips
        # SEER's Bedford City and County combined code covers the present
        # Bedford County after the city rejoined it in 2013 (before this period).
        # This is a documented display alias, not redistribution of a rate.
        fips = {"51917": "51019"}.get(fips, fips)
        assert fips not in records, f"{path}: duplicate {fips}"
        value, low, high = num(row[3]), num(row[4]), num(row[5])
        marker = row[3].strip()
        status = "policy" if marker.startswith("[P1") else "suppressed" if marker.startswith("*") else "available"
        assert status != "available" or (value is not None and low is not None and high is not None and all(math.isfinite(x) for x in (value, low, high)) and low <= value <= high)
        assert status == "available" or (value is None and low is None and high is None)
        trend_value, trend_low, trend_high = num(row[11]), num(row[12]), num(row[13])
        trend_marker = row[11].strip()
        trend_status = "policy" if trend_marker.startswith("[P1") else "suppressed" if trend_marker.startswith("*") else "available"
        assert trend_status != "available" or (trend_value is not None and trend_low is not None and trend_high is not None and all(math.isfinite(x) for x in (trend_value, trend_low, trend_high)) and trend_low <= trend_value <= trend_high)
        assert trend_status == "available" or (trend_value is None and trend_low is None and trend_high is None)
        assert trend_status != "available" or row[10].strip() in {"stable", "falling", "rising"}, f"{path}: invalid trend category for {fips}"
        records[fips] = {"value": value, "low": low, "high": high, "count": count(row[9]), "status": status,
                         "rurality": row[2].strip(),
                         "trend": {"status": trend_status, "value": trend_value, "low": trend_low, "high": trend_high,
                                   "category": row[10].strip() if row[10].strip() in {"stable", "falling", "rising"} else None}}
        if source_fips != fips:
            records[fips]['sourceFips'] = source_fips
            records[fips]['note'] = 'Source reports Bedford City and County (51917); displayed on post-2013 Bedford County (51019).'
    assert len(records) == 3107 and len({k[:2] for k in records}) == 48
    policy = {k for k, r in records.items() if r["status"] == "policy"}
    assert len(policy) == 105 and all(k.startswith("20") for k in policy)
    statuses = {s: sum(r["status"] == s for r in records.values()) for s in ("available", "suppressed", "policy")}
    values = [r["value"] for r in records.values() if r["value"] is not None]
    dataset = {"id": ident, "cancerId": DATASETS[ident][4], "sexId": DATASETS[ident][3], "title": DATASETS[ident][1], "unit": UNIT, "period": PERIOD, "sex": DATASETS[ident][2], "min": min(values), "max": max(values), "records": records}
    manifest = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest().upper(), "sourceUrl": source_url(DATASETS[ident][4], DATASETS[ident][3]), "headerIndex": hi, "sourceRows": len(records), "stateCount": 48, "statusCounts": statuses, "policyKeys": sorted(policy), "sex": DATASETS[ident][2], "cancerId": DATASETS[ident][4], "sexId": DATASETS[ident][3]}
    return dataset, manifest

def main():
    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-dir", type=Path, default=root / "work")
    ap.add_argument("--output", type=Path, default=root / "dist/data/cancer.json")
    ap.add_argument("--validation", type=Path, default=root / "work/cancer-validation.json")
    a = ap.parse_args()
    expected = {"001": (2994, 8, 105), "047": (2774, 228, 105), "020": (2684, 318, 105), "055": (2784, 218, 105), "066": (2799, 203, 105)}
    previous = json.loads(a.output.read_text(encoding="utf-8")) if a.output.exists() else None
    datasets, manifests = [], {}
    missing = []
    for ident, (filename, _, _, _, _) in DATASETS.items():
        source = a.source_dir / filename
        if not source.exists():
            source = root / "work" / filename
        if not source.exists():
            missing.append(ident)
            continue
        d, m = parse(source, ident)
        got = tuple(m["statusCounts"][s] for s in ("available", "suppressed", "policy"))
        if ident in expected:
            assert got == expected[ident], (ident, got)
        datasets.append(d); manifests[ident] = m
    assert not missing, f"Missing required cancer exports: {missing}"
    assert set(manifests) == set(DATASETS)
    if previous:
        now_by_id = {d["id"]: d for d in datasets}
        for old in previous["datasets"]:
            now = now_by_id[old["id"]]
            for key in old["records"]:
                assert {k: now["records"][key][k] for k in ("value", "low", "high", "count", "status")} == {k: old["records"][key][k] for k in ("value", "low", "high", "count", "status")}
    policy_sets = [set(m["policyKeys"]) for m in manifests.values()]
    assert all(s == policy_sets[0] for s in policy_sets[1:])
    source_url = "https://statecancerprofiles.cancer.gov/incidencerates/index.php?areatype=county&cancer=001&race=00&sex=0&age=001&type=incd&statefips=00&datatype=01&ruralurban=0&sortVariableName=rate&sortOrder=desc&output=1"
    payload = {"sourceUrl": source_url, "note": NOTE, "datasets": datasets}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    report = {"generatedAt": datetime.now(timezone.utc).isoformat(), "period": PERIOD, "sourceDir": str(a.source_dir), "sourceUrl": source_url, "missingSexSpecificExports": missing, "sourceMetadata": {"submission": "2024 submissions", "race": "All Races (includes Hispanic)", "age": "All Ages", "stage": "All Stages", "geography": "County; SCP legacy Connecticut counties"}, "files": manifests, "expectedStatusCounts": expected, "geography": {"includedStates": 48, "recordsPerDataset": 3107, "excludedFipsPrefixes": ["02", "11", "15", "72"], "excludedAggregate": "00000", "aliases": {"51917": "51019"}, "aliasSources": ["https://seer.cancer.gov/seerstat/variables/countyattribs/static.html", "https://www.census.gov/programs-surveys/geography/technical-documentation/county-changes.2010.html"]}}
    a.validation.write_text(json.dumps(report, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps({k: m["statusCounts"] for k, m in manifests.items()}, indent=2))

if __name__ == "__main__":
    main()
