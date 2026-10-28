#!/usr/bin/env python3
"""Precompute the 0-100 normalization that My priorities does in the browser.

Today `dist/composite.js` derives the national minimum, maximum and the
Q3 + 3xIQR outlier fence from the records it holds in memory, every time the
user changes a weight. That is fine for one page with the data already loaded.

It does not survive the move to ranking counties in SQL. A query that had to
recompute distribution statistics over the whole value table before it could
score anything would read every row to return five. The normalized component
has to be stored beside the value instead, which is a schema addition rather
than a query change.

This script is that addition, built as a file first so the arithmetic can be
proved identical to the JavaScript before any database depends on it.
`scripts/test-normalized.cjs` runs both and compares every record.

An unavailable record gets a null score, never zero. Missing, suppressed,
policy-withheld and not-applicable are distinct from a real zero throughout
this project, and a ranking that scored missing as zero would place counties
first or last for having no data.

One exception, declared rather than inferred. A dataset carrying
`notApplicableMeans: "best-case"` says its source's not-applicable status means
no exposure. Those records score 0, the best end of the output scale, and keep
a null value because nothing was measured. Only the hurricane, coastal
flooding and ice storm layers declare it.

Standard library only. No network. Input files are never modified.
"""

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

FAMILIES = ("cancer", "disasters", "community", "hazards", "healthcare", "employment", "broadband", "places", "air", "wildfire", "water", "traffic", "climate", "storms", "crime")
FORMAT = "normalized-v1"


def repo_root():
    return Path(__file__).resolve().parent.parent


def available(record):
    """True when a record is available and carries a finite numeric value."""
    if not isinstance(record, dict) or record.get("status") != "available":
        return False
    value = record.get("value")
    # A bool is an int in Python. It is not a measurement.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(value)


def best_case(record, stats):
    """True for a not-applicable record in a dataset that declares it means no exposure."""
    return (isinstance(record, dict) and record.get("status") == "not-applicable"
            and stats.get("notApplicableBestCase") is True and stats["count"] > 0)


def clamp(n):
    return max(0.0, min(1.0, n))


def quantile(values, p):
    """Linear-interpolated quantile over an ascending list.

    This matches the JavaScript exactly, including the interpolation. NumPy's
    default and Python's statistics module both differ on some inputs.
    """
    index = (len(values) - 1) * p
    lo = math.floor(index)
    hi = math.ceil(index)
    return values[lo] + (values[hi] - values[lo]) * (index - lo)


def scale_stats(dataset):
    records = dataset.get("records") or {}
    values = sorted(r["value"] for r in records.values() if available(r))
    reverse = dataset.get("direction") == "higher-better"
    best = dataset.get("notApplicableMeans") == "best-case"
    if not values:
        return {"min": None, "max": None, "fence": None, "reversed": reverse,
                "count": 0, "hasExtremes": False, "iqr": None,
                "notApplicableBestCase": best}
    q1 = quantile(values, 0.25)
    q3 = quantile(values, 0.75)
    iqr = q3 - q1
    fence = q1 - 3 * iqr if reverse else q3 + 3 * iqr
    # When the IQR is zero the fence sits on the data and would discard most of
    # it, so the filter is skipped entirely.
    if iqr > 0:
        regular = [v for v in values if (v >= fence if reverse else v <= fence)]
    else:
        regular = values
    return {
        "min": regular[0] if reverse else values[0],
        "max": values[-1] if reverse else regular[-1],
        "fence": fence,
        "reversed": reverse,
        "count": len(values),
        "hasExtremes": len(regular) < len(values),
        "iqr": iqr,
        "notApplicableBestCase": best,
    }


def component(record, stats):
    # 0 is the best end for either direction, because the flip is applied here.
    if best_case(record, stats):
        return {"scaled": 0, "extreme": False}
    if not available(record) or not stats["count"]:
        return {"scaled": None, "extreme": False}
    value = record["value"]
    if stats["min"] == stats["max"]:
        scaled = 50
    else:
        span = stats["max"] - stats["min"]
        offset = stats["max"] - value if stats["reversed"] else value - stats["min"]
        scaled = 100 * clamp(offset / span)
    extreme = stats["hasExtremes"] and (
        value < stats["fence"] if stats["reversed"] else value > stats["fence"]
    )
    return {"scaled": scaled, "extreme": extreme}


def build_family(name, data_dir, audit):
    payload = json.loads((data_dir / f"{name}.json").read_text(encoding="utf-8"))
    datasets = []
    for dataset in payload.get("datasets") or []:
        stats = scale_stats(dataset)
        records = {}
        for fips, record in (dataset.get("records") or {}).items():
            scored = component(record, stats)
            records[fips] = scored
            audit.append((scored["scaled"], scored["extreme"], available(record),
                          best_case(record, stats)))
        datasets.append({
            "id": dataset.get("id"),
            "title": dataset.get("title"),
            "direction": dataset.get("direction"),
            "stats": stats,
            "records": records,
        })
    return {"datasets": datasets}


def verify(families, audit):
    dataset_count = sum(len(family["datasets"]) for family in families.values())
    scored = [entry[0] for entry in audit if entry[0] is not None]
    out_of_range = [v for v in scored if not 0 <= v <= 100]
    # The invariant this project protects: a score exists exactly when the
    # source record was available, or its dataset declared not-applicable a
    # best case. An assumed best case always scores exactly 0.
    mismatched = [e for e in audit if (e[0] is None) == (e[2] or e[3])]
    assumed = [e for e in audit if e[3]]
    wrong_assumed = [e for e in assumed if e[0] != 0 or e[1]]

    print(f"families              {len(families)}")
    print(f"datasets              {dataset_count}")
    print(f"records               {len(audit)}")
    print(f"scored                {len(scored)}")
    print(f"null scores           {len(audit) - len(scored)}")
    print(f"extreme records       {sum(1 for e in audit if e[1])}")
    print(f"assumed best case     {len(assumed)}")

    ok = True
    if out_of_range:
        print(f"FAIL {len(out_of_range)} scores outside 0-100")
        ok = False
    if mismatched:
        print(f"FAIL {len(mismatched)} records where a score and availability disagree")
        ok = False
    if wrong_assumed:
        print(f"FAIL {len(wrong_assumed)} assumed best-case records not scored exactly 0")
        ok = False
    if ok:
        print("every score is 0-100 and exists exactly when the record was available "
              "or a declared best case")
    return ok


def main():
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default=str(root / "dist" / "data"))
    parser.add_argument("--out", default=str(root / "dist" / "data" / "normalized.json"))
    args = parser.parse_args()

    data_dir = Path(args.data)
    out = Path(args.out)
    families = {}
    audit = []
    for name in FAMILIES:
        families[name] = build_family(name, data_dir, audit)

    payload = {
        "format": FORMAT,
        "generated": datetime.now(timezone.utc).date().isoformat(),
        "families": families,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"output                {out}")
    print()
    if not verify(families, audit):
        sys.exit(1)


if __name__ == "__main__":
    main()
