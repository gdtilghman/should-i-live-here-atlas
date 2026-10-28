#!/usr/bin/env python3
"""Prepare FEMA NRI v1.20 county building Expected Annual Loss rates.

The source ``*_ALRB`` fields are fractions of total county building value.
Published values multiply those source fractions by 10,000 so the unit is
modeled expected annual building loss per $10,000 of total building value.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ITEM_ID = "39485e8035d446a5bff03259508ae355"
ITEM_URL = f"https://fema.maps.arcgis.com/home/item.html?id={ITEM_ID}&sublayer=0"
ITEM_API = f"https://www.arcgis.com/sharing/rest/content/items/{ITEM_ID}?f=json"
LAYER_URL = (
    "https://services.arcgis.com/XG15cJAlne2vxtgt/arcgis/rest/services/"
    "National_Risk_Index_Counties/FeatureServer/0"
)
QUERY_URL = LAYER_URL + "/query"
TECHNICAL_URL = (
    "https://www.fema.gov/sites/default/files/documents/"
    "fema_national-risk-index_technical-documentation.pdf"
)
DATA_DICTIONARY_ITEM = "4b9db412e99542029b3c37c37ad714bb"
VERSION_LABEL = "December 2025"
VERSION_NUMBER = "1.20.0"
RATE_MULTIPLIER = 10_000.0
TARGET_COUNT = 3107

SOURCE_HAZARDS = {
    "nri-inland-flooding": ("IFLD", "Inland Flooding"),
    "nri-wildfire": ("WFIR", "Wildfire"),
    "nri-hurricane": ("HRCN", "Hurricane"),
    "nri-tornado": ("TRND", "Tornado"),
    # Added September 29, 2026. Each one reconciles with EAL / BUILDVALUE in
    # every county. Landslide fails in 50 counties, like wildfire, so it is a
    # candidate only. Heat wave and cold wave are left out: their modeled
    # building loss is near zero, so the measure would mislead.
    "nri-coastal-flooding": ("CFLD", "Coastal Flooding"),
    "nri-earthquake": ("ERQK", "Earthquake"),
    "nri-hail": ("HAIL", "Hail"),
    "nri-ice-storm": ("ISTM", "Ice Storm"),
    "nri-lightning": ("LTNG", "Lightning"),
    "nri-strong-wind": ("SWND", "Strong Wind"),
    "nri-winter-weather": ("WNTW", "Winter Weather"),
    "nri-landslide": ("LNDS", "Landslide"),
}
EXCLUDED = {"nri-wildfire", "nri-landslide"}
# How each hazard reads inside the visitor note ("damage to buildings from ...").
NOTE_NOUN = {
    "nri-inland-flooding": "inland flooding", "nri-hurricane": "hurricanes",
    "nri-tornado": "tornadoes", "nri-coastal-flooding": "coastal flooding",
    "nri-earthquake": "earthquakes", "nri-hail": "hail", "nri-ice-storm": "ice storms",
    "nri-lightning": "lightning", "nri-strong-wind": "strong wind",
    "nri-winter-weather": "winter weather",
}
HAZARDS = {key: value for key, value in SOURCE_HAZARDS.items() if key not in EXCLUDED}
# Where the source's not-applicable status means no exposure rather than no
# data. For hurricane it marks inland counties, and the user decided on
# September 17, 2026 that ranking should read them as the best case. This is a
# statement about what the source means, so it ships with the dataset, and only
# a dataset listed here gets it. Every other hazard keeps not-applicable as
# missing.
# Coastal flooding and ice storm follow the same rule on September 29, 2026:
# FEMA marks them not applicable where the county has no exposure (inland
# counties; counties with no ice-storm history), so that is the best case.
NOT_APPLICABLE_MEANS = {
    "nri-hurricane": "best-case",
    "nri-coastal-flooding": "best-case",
    "nri-ice-storm": "best-case",
}

UNIT = "annual building loss per $10,000 of total building value"
PERIOD = "FEMA model, version 1.20. Input years vary by hazard."
TOP_NOTE = (
    "These are FEMA National Risk Index model estimates, version 1.20. They are not losses that happened. They do not predict a single year. The model uses data from different years for different hazards. FEMA's technical documents list them. Connecticut is unavailable because FEMA uses planning regions, not the older counties this atlas uses. This product uses FEMA's National Risk Index data but is not endorsed by FEMA. FEMA cannot vouch for analyses made after the data were retrieved."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def get_json(url: str, params: dict[str, object] | None = None) -> dict:
    data = None
    if params:
        encoded = urllib.parse.urlencode(params)
        if len(encoded) > 1500:
            data = encoded.encode("ascii")
        else:
            url += ("&" if "?" in url else "?") + encoded
    request = urllib.request.Request(url, data=data, headers={"User-Agent": "Should-I-Live-Here data preparation/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.loads(response.read())
    if "error" in payload:
        raise RuntimeError(f"ArcGIS request failed: {payload['error']}")
    return payload


def download_snapshot(raw_path: Path, layer_path: Path, item_path: Path) -> None:
    layer = get_json(LAYER_URL, {"f": "json"})
    item = get_json(ITEM_API)
    field_names = {field["name"] for field in layer["fields"]}
    requested = ["OBJECTID", "STCOFIPS", "COUNTY", "STATEABBRV", "NRI_VER", "BUILDVALUE"]
    for prefix, _ in SOURCE_HAZARDS.values():
        requested.extend([f"{prefix}_EXPB", f"{prefix}_EALB", f"{prefix}_ALRB", f"{prefix}_EALR"])
    assert set(requested) <= field_names, sorted(set(requested) - field_names)

    id_payload = get_json(
        QUERY_URL,
        {"where": "1=1", "returnIdsOnly": "true", "returnGeometry": "false", "f": "json"},
    )
    object_ids = sorted(id_payload["objectIds"])
    features: list[dict] = []
    for start in range(0, len(object_ids), 500):
        page = get_json(
            QUERY_URL,
            {
                "objectIds": ",".join(map(str, object_ids[start : start + 500])),
                "outFields": ",".join(requested),
                "returnGeometry": "false",
                "orderByFields": "OBJECTID",
                "f": "json",
            },
        )
        features.extend(feature["attributes"] for feature in page["features"])
    assert len(features) == len(object_ids) == len({row["OBJECTID"] for row in features})
    assert {row["NRI_VER"] for row in features} == {VERSION_LABEL}

    retrieved_at = utc_now()
    raw = {
        "retrievedAt": retrieved_at,
        "sourceUrl": LAYER_URL,
        "itemUrl": ITEM_URL,
        "objectIdField": layer["objectIdField"],
        "sourceFeatureCount": len(features),
        "fields": requested,
        "features": sorted(features, key=lambda row: row["STCOFIPS"]),
    }
    raw_path.write_text(json.dumps(raw, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    layer_path.write_text(json.dumps(layer, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    item_path.write_text(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def read_target_fips(path: Path) -> list[str]:
    geography = json.loads(path.read_text(encoding="utf-8"))
    fips = sorted(feature["properties"]["fips"] for feature in geography["features"])
    assert len(fips) == len(set(fips)) == TARGET_COUNT
    assert sum(code.startswith("09") for code in fips) == 8
    return fips


def source_status(rate: object, rating: object) -> tuple[str, str | None]:
    if isinstance(rate, (int, float)) and not isinstance(rate, bool):
        assert math.isfinite(rate) and rate >= 0
        return "available", None
    normalized = str(rating or "").strip().lower()
    if "not applicable" in normalized:
        return "not-applicable", "FEMA marks this hazard not applicable for the county."
    if "insufficient" in normalized:
        return "insufficient-data", "FEMA reports insufficient data for this hazard."
    return "unavailable", "FEMA did not publish a numeric building Expected Annual Loss Rate."


def prepare(
    raw_path: Path,
    layer_path: Path,
    item_path: Path,
    dictionary_path: Path,
    geography_path: Path,
) -> tuple[dict, dict]:
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    layer = json.loads(layer_path.read_text(encoding="utf-8"))
    item = json.loads(item_path.read_text(encoding="utf-8"))
    assert item["id"] == ITEM_ID and item["owner"] == "FEMA_NationalRiskIndex"
    assert item["url"].rstrip("/") == LAYER_URL.rsplit("/", 1)[0]
    assert {row["NRI_VER"] for row in raw["features"]} == {VERSION_LABEL}
    source_rows = {row["STCOFIPS"]: row for row in raw["features"]}
    assert len(source_rows) == len(raw["features"])
    target_fips = read_target_fips(geography_path)
    target_set = set(target_fips)
    ct_target = {code for code in target_fips if code.startswith("09")}
    ct_source = sorted(code for code in source_rows if code.startswith("09"))
    assert len(ct_source) == 9 and not (ct_target & set(ct_source)), ct_source
    joined = target_set & source_rows.keys()
    missing_non_ct = (target_set - source_rows.keys()) - ct_target
    assert not missing_non_ct, sorted(missing_non_ct)
    assert len(joined) == TARGET_COUNT - len(ct_target)

    field_metadata = {field["name"]: field for field in layer["fields"]}
    dictionary_rows = []
    import csv
    with dictionary_path.open(encoding="utf-8-sig", newline="") as handle:
        dictionary_rows = list(csv.DictReader(handle))
    dictionary = {row["Field Name"]: row for row in dictionary_rows}

    datasets = []
    audits: dict[str, dict] = {}
    sample_fips = ["06037", "12086", "17031", "30111", "36061", "48201"]
    for dataset_id, (prefix, hazard) in HAZARDS.items():
        rate_field = f"{prefix}_ALRB"
        eal_field = f"{prefix}_EALB"
        hazard_exposure_field = f"{prefix}_EXPB"
        rating_field = f"{prefix}_EALR"
        for field in ("BUILDVALUE", rate_field, eal_field, hazard_exposure_field, rating_field):
            assert field in field_metadata and field in dictionary
            assert dictionary[field]["Version"] == VERSION_NUMBER
            assert dictionary[field]["Version Date"] == VERSION_LABEL

        records = {}
        status_counts: Counter[str] = Counter()
        rating_by_status: dict[str, Counter[str]] = {}
        formula_errors = []
        formula_checks = 0
        source_nulls = 0
        source_zeros = 0
        for fips in target_fips:
            if fips in ct_target:
                record = {
                    "value": None,
                    "low": None,
                    "high": None,
                    "count": None,
                    "status": "unavailable",
                    "reason": "FEMA uses Connecticut planning regions. They do not match the older counties this atlas uses.",
                }
            else:
                row = source_rows[fips]
                rate = row[rate_field]
                rating = row[rating_field]
                status, reason = source_status(rate, rating)
                if rate is None:
                    source_nulls += 1
                elif rate == 0:
                    source_zeros += 1
                value = rate * RATE_MULTIPLIER if status == "available" else None
                record = {
                    "value": value,
                    "low": None,
                    "high": None,
                    "count": None,
                    "status": status,
                }
                if reason:
                    record["reason"] = reason
                rating_by_status.setdefault(status, Counter())[str(rating)] += 1

                building_value = row["BUILDVALUE"]
                eal = row[eal_field]
                if status == "available" and building_value and eal is not None:
                    derived_rate = eal / building_value
                    formula_checks += 1
                    delta = abs(rate - derived_rate)
                    if not math.isclose(rate, derived_rate, rel_tol=1e-10, abs_tol=1e-14):
                        formula_errors.append({"fips": fips, "sourceRate": rate, "derivedRate": derived_rate, "delta": delta})
            records[fips] = record
            status_counts[record["status"]] += 1

        assert len(records) == TARGET_COUNT
        assert not formula_errors, formula_errors[:5]
        values = [record["value"] for record in records.values() if record["status"] == "available"]
        assert values and all(isinstance(value, float) and math.isfinite(value) and value >= 0 for value in values)
        assert all(record["value"] is None for record in records.values() if record["status"] != "available")
        assert status_counts["unavailable"] >= len(ct_target)

        # Visitor text in plain language (docs/glossary.md). The formula lives in
        # the audit: value = *_ALRB x 10,000, where *_ALRB = *_EALB / BUILDVALUE.
        dataset_note = (
            f"A FEMA computer model estimates the average damage to buildings from {NOTE_NOUN[dataset_id]} "
            "each year. The value is the damage in dollars for each $10,000 of building value in "
            "the county. The model uses data from different years for different hazards."
        )
        datasets.append(
            {
                "id": dataset_id,
                "title": f"{hazard} modeled annual building loss rate",
                "unit": UNIT,
                "period": PERIOD,
                "sourceUrl": ITEM_URL,
                "release": f"FEMA NRI {VERSION_NUMBER} — {VERSION_LABEL}",
                "geographyVintage": "Census 2021 counties; newer Connecticut planning regions unmatched",
                "retrievedAt": raw["retrievedAt"],
                "sourceFiles": [{"url": LAYER_URL, "sha256": sha256(raw_path)}],
                "note": dataset_note,
                "direction": "higher-worse",
                **({"notApplicableMeans": NOT_APPLICABLE_MEANS[dataset_id]}
                   if dataset_id in NOT_APPLICABLE_MEANS else {}),
                "category": "hazards",
                "min": min(values),
                "max": max(values),
                "records": records,
            }
        )

        samples = {}
        for fips in sample_fips:
            row = source_rows[fips]
            samples[fips] = {
                "county": row["COUNTY"],
                "state": row["STATEABBRV"],
                "totalBuildingValue": row["BUILDVALUE"],
                "hazardExposedBuildingValue": row[hazard_exposure_field],
                "expectedAnnualBuildingLoss": row[eal_field],
                "sourceRateFraction": row[rate_field],
                "recomputedRateFraction": row[eal_field] / row["BUILDVALUE"] if row["BUILDVALUE"] and row[eal_field] is not None else None,
                "publishedPer10000": records[fips]["value"],
                "status": records[fips]["status"],
            }
        audits[dataset_id] = {
            "sourceFields": {
                "rate": rate_field,
                "numerator": eal_field,
                "denominator": "BUILDVALUE",
                "hazardExposureNotDenominator": hazard_exposure_field,
                "rating": rating_field,
            },
            "fieldAliases": {field: field_metadata[field]["alias"] for field in (rate_field, eal_field, "BUILDVALUE", hazard_exposure_field, rating_field)},
            "statusCounts": dict(sorted(status_counts.items())),
            "ratingByStatus": {status: dict(sorted(counts.items())) for status, counts in sorted(rating_by_status.items())},
            "availableMinimum": min(values),
            "availableMaximum": max(values),
            "availableZeros": source_zeros,
            "sourceNullRatesOutsideConnecticut": source_nulls,
            "formulaChecks": formula_checks,
            "formulaMismatchCount": len(formula_errors),
            "samples": samples,
        }

    excluded_candidates = {}
    for dataset_id, (prefix, hazard) in SOURCE_HAZARDS.items():
        if dataset_id in HAZARDS:
            continue
        rate_field = f"{prefix}_ALRB"
        eal_field = f"{prefix}_EALB"
        mismatches = []
        checked = 0
        for fips in sorted(joined):
            row = source_rows[fips]
            if row[rate_field] is None or not row["BUILDVALUE"] or row[eal_field] is None:
                continue
            checked += 1
            expected = row[eal_field] / row["BUILDVALUE"]
            if not math.isclose(row[rate_field], expected, rel_tol=1e-10, abs_tol=1e-14):
                mismatches.append(
                    {
                        "fips": fips,
                        "sourceRate": row[rate_field],
                        "ealDividedByFullCommunityBuildingValue": expected,
                        "relativeDifference": abs(row[rate_field] - expected) / max(abs(row[rate_field]), 1e-300),
                    }
                )
        excluded_candidates[dataset_id] = {
            "hazard": hazard,
            "sourceRateField": rate_field,
            "documentedDenominatorField": "BUILDVALUE",
            "formulaChecks": checked,
            "formulaMismatchCount": len(mismatches),
            "mismatchedFips": [row["fips"] for row in mismatches],
            "maximumRelativeDifference": max((row["relativeDifference"] for row in mismatches), default=0),
            "reason": "Not emitted: the current FEMA service rate does not reconcile with EAL / full community building value for every target county; FEMA clarification is needed.",
        }
        assert mismatches, f"Excluded candidate {dataset_id} unexpectedly reconciled; reconsider inclusion"

    payload = {"sourceUrl": ITEM_URL, "note": TOP_NOTE, "datasets": datasets}
    artifacts = {}
    for path in [raw_path, layer_path, item_path, dictionary_path, ROOT / "work/nri-metadata-v120.pdf", ROOT / "work/nri-glossary-v120.pdf"]:
        if path.exists():
            artifacts[path.name] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
    validation = {
        "generatedAt": utc_now(),
        "retrievedAt": raw["retrievedAt"],
        "source": {
            "dataset": "FEMA National Risk Index Counties",
            "version": VERSION_NUMBER,
            "versionLabel": VERSION_LABEL,
            "itemId": ITEM_ID,
            "itemOwner": item["owner"],
            "itemUrl": ITEM_URL,
            "featureLayerUrl": LAYER_URL,
            "technicalDocumentationUrl": TECHNICAL_URL,
            "dataDictionaryItem": f"https://fema.maps.arcgis.com/home/item.html?id={DATA_DICTIONARY_ITEM}",
        },
        "geography": {
            "target": "Census 2021 contiguous-48 county equivalents with eight legacy Connecticut counties",
            "source": "Census 2021 counties except Connecticut uses 2024 planning regions",
            "targetCount": TARGET_COUNT,
            "sourceFeatureCount": len(source_rows),
            "matchedTargetCount": len(joined),
            "connecticutUnavailable": sorted(ct_target),
            "sourceConnecticutPlanningRegions": ct_source,
            "missingNonConnecticut": sorted(missing_non_ct),
        },
        "transformation": {
            "unit": UNIT,
            "formula": "published value = source *_ALRB fraction * 10000",
            "sourceIdentity": "*_ALRB = *_EALB / BUILDVALUE",
            "excludedFields": "No NRI score, rank, percentile, rating, or overall composite is used as a value.",
            "period": PERIOD,
        },
        "datasets": audits,
        "excludedCandidates": excluded_candidates,
        "artifacts": artifacts,
    }
    return payload, validation


def verify_live_samples(payload: dict, sample_fips: list[str]) -> dict:
    fields = ["STCOFIPS", "COUNTY", "STATEABBRV", "NRI_VER", "BUILDVALUE"]
    for prefix, _ in HAZARDS.values():
        fields.extend([f"{prefix}_EALB", f"{prefix}_ALRB", f"{prefix}_EALR"])
    where = "STCOFIPS IN (" + ",".join(f"'{fips}'" for fips in sample_fips) + ")"
    response = get_json(
        QUERY_URL,
        {"where": where, "outFields": ",".join(fields), "returnGeometry": "false", "f": "json"},
    )
    rows = {feature["attributes"]["STCOFIPS"]: feature["attributes"] for feature in response["features"]}
    assert set(rows) == set(sample_fips)
    datasets = {dataset["id"]: dataset for dataset in payload["datasets"]}
    checks = {}
    for dataset_id, (prefix, hazard) in HAZARDS.items():
        samples = {}
        for fips in sample_fips:
            source = rows[fips]
            output = datasets[dataset_id]["records"][fips]
            source_rate = source[f"{prefix}_ALRB"]
            expected_value = None if source_rate is None else source_rate * RATE_MULTIPLIER
            assert output["status"] == source_status(source_rate, source[f"{prefix}_EALR"])[0]
            if expected_value is None:
                assert output["value"] is None
            else:
                assert math.isclose(output["value"], expected_value, rel_tol=0, abs_tol=1e-12)
            samples[fips] = {
                "county": source["COUNTY"],
                "state": source["STATEABBRV"],
                "sourceVersion": source["NRI_VER"],
                "sourceRateFraction": source_rate,
                "sourceExpectedAnnualBuildingLoss": source[f"{prefix}_EALB"],
                "sourceFullCommunityBuildingExposure": source["BUILDVALUE"],
                "expectedPublishedValue": expected_value,
                "outputValue": output["value"],
                "outputStatus": output["status"],
                "matches": True,
            }
        checks[dataset_id] = {"hazard": hazard, "samples": samples}
    return {
        "checkedAt": utc_now(),
        "queryUrl": QUERY_URL,
        "sampleFips": sample_fips,
        "datasets": checks,
        "allMatched": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="Download a fresh official FEMA ArcGIS snapshot")
    parser.add_argument("--verify-live", action="store_true", help="Re-query independent source samples")
    parser.add_argument("--raw", type=Path, default=ROOT / "work/nri-counties-v120.json")
    parser.add_argument("--layer-metadata", type=Path, default=ROOT / "work/nri-layer-metadata-v120.json")
    parser.add_argument("--item-metadata", type=Path, default=ROOT / "work/nri-item-metadata-v120.json")
    parser.add_argument("--dictionary", type=Path, default=ROOT / "work/nri-data-dictionary-v120.csv")
    parser.add_argument("--geography", type=Path, default=ROOT / "dist/data/counties.geojson")
    parser.add_argument("--output", type=Path, default=ROOT / "dist/data/hazards.json")
    parser.add_argument("--validation", type=Path, default=ROOT / "work/hazard-validation.json")
    parser.add_argument("--live-samples", type=Path, default=ROOT / "work/nri-live-sample-reconciliation.json")
    args = parser.parse_args()
    for path in (args.raw.parent, args.output.parent, args.validation.parent):
        path.mkdir(parents=True, exist_ok=True)
    if args.refresh or not all(path.exists() for path in (args.raw, args.layer_metadata, args.item_metadata)):
        download_snapshot(args.raw, args.layer_metadata, args.item_metadata)
    assert args.dictionary.exists(), "Download the official FEMA v1.20 data dictionary item first."
    payload, validation = prepare(args.raw, args.layer_metadata, args.item_metadata, args.dictionary, args.geography)
    if args.verify_live:
        live = verify_live_samples(payload, ["06037", "12086", "17031", "30111", "36061", "48201"])
        args.live_samples.write_text(json.dumps(live, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        validation["liveSampleReconciliation"] = live
        validation["artifacts"][args.live_samples.name] = {"bytes": args.live_samples.stat().st_size, "sha256": sha256(args.live_samples)}
    args.output.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    validation["outputArtifact"] = {"name": args.output.name, "bytes": args.output.stat().st_size, "sha256": sha256(args.output)}
    args.validation.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"datasets": {d["id"]: {"min": d["min"], "max": d["max"], "records": len(d["records"])} for d in payload["datasets"]}, "geography": validation["geography"]}, indent=2))


if __name__ == "__main__":
    main()
