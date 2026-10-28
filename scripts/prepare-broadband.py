#!/usr/bin/env python3
"""Prepare the FCC fixed terrestrial broadband 100/20 Mbps availability dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import tempfile
from decimal import Decimal, InvalidOperation
from pathlib import Path

EXPECTED_SOURCE_URL = "https://c2h.fcc.gov/api/crosstabCountyData/getAllCountyData"
EXPECTED_METADATA_URL = "https://c2h.fcc.gov/api/variabledata/getAllVariableData"
SOURCE_NAME = "FCC Connect2Health / Broadband Data Collection"
SOURCE_URL = "https://c2h.fcc.gov/bh-data.html"
SOURCE_FIELD = "fixed_100_20_pct"
RELIABILITY_FIELD = "fixed_100_20_pct_unreliable"
EXPECTED_FIELDS = ("fips", SOURCE_FIELD, RELIABILITY_FIELD)
PERIOD = "June 2024"
UNIT = "% of residents"
SOURCE_NOTE = (
    "The value is the share of residents with no reported access. It is 100% minus the reported access share. County details show the reported access share. A lower value is better. It is a county total, not a check of one address. It counts wired or fixed wireless broadband advertised at 100/20 Mbps or faster. Satellite does not count. The measurement is from June 2024. The FCC released it in 2025. It does not measure real speed, reliability, price or use. It is not a promise for one address. The source gives no resident counts and no likely range."
)
UNMATCHED_REASON = (
    "No exact five-digit FIPS match in the FCC source; no fuzzy join or geography remapping was applied."
)


class PreparationError(RuntimeError):
    """Raised for fail-closed source, schema, or atlas validation problems."""


def _pairs(pairs: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise PreparationError(f"Duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _load_json(path: Path, label: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs)
    except (OSError, UnicodeError, json.JSONDecodeError, PreparationError) as exc:
        raise PreparationError(f"Cannot read valid {label} JSON {path}: {exc}") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise PreparationError(f"Cannot hash {path}: {exc}") from exc
    return digest.hexdigest()


def _acquisition_entry(acquisition: object, name: str, expected_url: str) -> dict:
    if not isinstance(acquisition, dict) or not isinstance(acquisition.get(name), dict):
        raise PreparationError(f"Acquisition metadata is missing {name!r}")
    entry = acquisition[name]
    for key in ("url", "sha256", "retrievedAt"):
        if not isinstance(entry.get(key), str) or not entry[key].strip():
            raise PreparationError(f"Acquisition metadata for {name!r} has invalid {key!r}")
    if entry["url"] != expected_url:
        raise PreparationError(
            f"Acquisition URL for {name!r} is {entry['url']!r}, expected {expected_url!r}"
        )
    if len(entry["sha256"]) != 64 or any(ch not in "0123456789abcdef" for ch in entry["sha256"]):
        raise PreparationError(f"Acquisition SHA-256 for {name!r} is not a 64-character hex digest")
    return entry


def _validate_metadata(metadata: object) -> None:
    if not isinstance(metadata, list):
        raise PreparationError("FCC variable metadata must be a JSON array")
    matches = [
        item
        for item in metadata
        if isinstance(item, dict) and item.get("data_col") == SOURCE_FIELD
    ]
    if len(matches) != 1:
        raise PreparationError(
            f"Variable metadata must contain exactly one {SOURCE_FIELD!r} definition; found {len(matches)}"
        )
    item = matches[0]
    tooltip = item.get("tooltip")
    if not isinstance(tooltip, str):
        raise PreparationError("Variable metadata must define a tooltip")
    normalized_tooltip = tooltip.casefold()
    if "as of june 2024" not in normalized_tooltip:
        raise PreparationError("Variable metadata does not define the source field as of June 2024")
    if "100/20 mbps" not in normalized_tooltip:
        raise PreparationError("Variable metadata does not define 100/20 Mbps availability")
    if "population" not in normalized_tooltip:
        raise PreparationError("Variable metadata does not define a population denominator")
    if "fixed terrestrial" not in normalized_tooltip:
        raise PreparationError("Variable metadata does not define fixed terrestrial technology")
    if item.get("unit") != "%" or item.get("data_type") != "numerical":
        raise PreparationError("Variable metadata does not define a county numerical percentage")
    availability = item.get("availability")
    if not isinstance(availability, list) or "county" not in availability:
        raise PreparationError("Variable metadata is not available at county level")


def _source_fips(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, int):
        raise PreparationError(f"Source FIPS must be an integer, got {value!r}")
    if value < 0:
        raise PreparationError(f"Source FIPS must not be negative, got {value!r}")
    fips = str(value).zfill(5)
    if len(fips) > 5:
        raise PreparationError(f"Source FIPS must have at most five digits, got {value!r}")
    return fips


def _atlas_ids(geo_path: Path) -> dict[str, str]:
    data = _load_json(geo_path, "county atlas")
    if not isinstance(data, dict) or data.get("type") != "FeatureCollection" or not isinstance(data.get("features"), list):
        raise PreparationError("County atlas is not a FeatureCollection with a features array")
    atlas: dict[str, str] = {}
    for index, feature in enumerate(data["features"]):
        if not isinstance(feature, dict) or not isinstance(feature.get("properties"), dict):
            raise PreparationError(f"County atlas feature {index} has no properties object")
        fips = feature["properties"].get("fips")
        if not isinstance(fips, str) or len(fips) != 5 or not fips.isdigit():
            raise PreparationError(f"County atlas feature {index} has invalid five-digit FIPS {fips!r}")
        if fips in atlas:
            raise PreparationError(f"Duplicate atlas FIPS: {fips}")
        atlas[fips] = feature["properties"].get("name")
    if not atlas:
        raise PreparationError("County atlas contains no county IDs")
    return atlas


def _number(value: object) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise PreparationError(f"Invalid numeric source value: {value!r}") from exc


def _json_number(value: Decimal) -> int | float:
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def build_data(
    source_path: Path, metadata_path: Path, acquisition_path: Path, geo_path: Path
) -> tuple[dict, dict]:
    acquisition = _load_json(acquisition_path, "acquisition")
    source_entry = _acquisition_entry(acquisition, source_path.name, EXPECTED_SOURCE_URL)
    metadata_entry = _acquisition_entry(acquisition, metadata_path.name, EXPECTED_METADATA_URL)
    for path, entry, label in (
        (source_path, source_entry, "source"),
        (metadata_path, metadata_entry, "metadata"),
    ):
        actual = _sha256(path)
        if actual != entry["sha256"]:
            raise PreparationError(f"{label.capitalize()} SHA-256 mismatch: expected {entry['sha256']}, got {actual}")

    metadata = _load_json(metadata_path, "FCC variable")
    _validate_metadata(metadata)
    rows = _load_json(source_path, "FCC county")
    if not isinstance(rows, list):
        raise PreparationError("FCC county source must be a JSON array")
    source: dict[str, dict] = {}
    schema_errors: list[str] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            schema_errors.append(f"row {index} is not an object")
            continue
        missing = [field for field in EXPECTED_FIELDS if field not in row]
        if missing:
            schema_errors.append(f"row {index} lacks {', '.join(missing)}")
            continue
        try:
            fips = _source_fips(row["fips"])
        except PreparationError as exc:
            schema_errors.append(str(exc))
            continue
        if fips in source:
            schema_errors.append(f"duplicate source FIPS {fips}")
        else:
            source[fips] = row
    if schema_errors:
        raise PreparationError("Source schema errors: " + "; ".join(schema_errors[:8]))
    if not source:
        raise PreparationError("FCC county source contains no rows")

    atlas = _atlas_ids(geo_path)
    records: dict[str, dict] = {}
    available_values: list[Decimal] = []
    for fips in sorted(atlas):
        row = source.get(fips)
        if row is None:
            records[fips] = _record(None, UNMATCHED_REASON)
            continue
        raw = row[SOURCE_FIELD]
        reliability = row[RELIABILITY_FIELD]
        access = _number(raw)
        reasons: list[str] = []
        if reliability is None:
            reasons.append("Source reliability is missing.")
        elif reliability != "reliable":
            reasons.append(f"Source reliability is {reliability!r}.")
        if access is None:
            reason = (
                "Source access percentage is missing."
                if raw is None
                else "Source access percentage is not a finite number."
            )
            reasons.append(reason)
        elif access < 0:
            reasons.append("Source access percentage is a missing-data sentinel or below zero.")
        elif access > 100:
            reasons.append("Source access percentage is above the published 0-100 range.")
        if reasons:
            records[fips] = _record(
                raw if access is not None and 0 <= access <= 100 else None,
                " ".join(reasons),
            )
            continue
        gap = Decimal("100") - access
        available_values.append(gap)
        records[fips] = {
            "status": "available",
            "value": _json_number(gap),
            "count": None,
            "low": None,
            "high": None,
            "moe": None,
            "sourceAccessPercent": raw,
            "reason": None,
        }

    if not available_values:
        raise PreparationError("No numeric source rows matched the county atlas")
    if len(records) != len(atlas):
        raise PreparationError("Internal error: output records do not cover every atlas county")

    dataset = {
        "id": "without-100-20",
        "title": "Residents without reported 100/20 Mbps access",
        "source": SOURCE_NAME,
        "unit": UNIT,
        "period": PERIOD,
        "sourceUrl": SOURCE_URL,
        "receivedAt": source_entry["retrievedAt"],
        "sourceField": SOURCE_FIELD,
        "reliabilityField": RELIABILITY_FIELD,
        "formula": f"100 - {SOURCE_FIELD}",
        "note": SOURCE_NOTE,
        "direction": "higher-worse",
        "category": "broadband",
        "min": _json_number(min(available_values)),
        "max": _json_number(max(available_values)),
        "records": records,
    }
    payload = {
        "source": SOURCE_NAME,
        "sourceUrl": SOURCE_URL,
        "receivedAt": source_entry["retrievedAt"],
        "sourceFiles": [
            {
                "name": source_path.name,
                "url": source_entry["url"],
                "sha256": source_entry["sha256"],
                "retrievedAt": source_entry["retrievedAt"],
            },
            {
                "name": metadata_path.name,
                "url": metadata_entry["url"],
                "sha256": metadata_entry["sha256"],
                "retrievedAt": metadata_entry["retrievedAt"],
            },
        ],
        "note": SOURCE_NOTE,
        "datasets": [dataset],
    }
    audit = {
        "sourceRows": len(source),
        "atlasCounties": len(atlas),
        "matched": sum(fips in atlas for fips in source),
        "excludedNonAtlas": sum(fips not in atlas for fips in source),
        "available": len(available_values),
        "unavailable": len(atlas) - len(available_values),
        "min": dataset["min"],
        "max": dataset["max"],
    }
    return payload, audit


def _record(source_access: object, reason: str) -> dict:
    return {
        "status": "unavailable",
        "value": None,
        "count": None,
        "low": None,
        "high": None,
        "moe": None,
        "sourceAccessPercent": source_access,
        "reason": reason,
    }


def write_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
        ) as handle:
            temporary = handle.name
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except OSError as exc:
        if temporary:
            Path(temporary).unlink(missing_ok=True)
        raise PreparationError(f"Cannot write output {path}: {exc}") from exc
    except BaseException:
        if temporary:
            Path(temporary).unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    repository = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=repository / "work/broadband-source/counties.json")
    parser.add_argument("--metadata", type=Path, default=repository / "work/broadband-source/variables.json")
    parser.add_argument("--acquisition", type=Path, default=repository / "work/broadband-source/acquisition.json")
    parser.add_argument("--geo", type=Path, default=repository / "dist/data/counties.geojson")
    parser.add_argument("--out", type=Path, default=repository / "dist/data/broadband.json")
    args = parser.parse_args(argv)

    try:
        payload, audit = build_data(args.source, args.metadata, args.acquisition, args.geo)
        write_atomic(args.out, payload)
    except PreparationError as exc:
        print(f"broadband preparation failed: {exc}", file=sys.stderr)
        return 1

    dataset = payload["datasets"][0]
    samples = [fips for fips in ("01001", "06037", "09001", "48301") if fips in dataset["records"]]
    print(f" wrote {args.out}")
    print(
        " coverage: {atlasCounties}/{atlasCounties} atlas counties; {available} available; "
        "{unavailable} unavailable; {matched} source rows joined; {excludedNonAtlas} non-atlas source rows excluded".format(**audit)
    )
    print(f" bounds: without-access min {audit['min']}%, max {audit['max']}%")
    print(" samples: " + ", ".join(f"{fips}={dataset['records'][fips]['value']}" for fips in samples))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
