#!/usr/bin/env python3
"""Prepare CDC PLACES 2024 county health metrics for the atlas.

Imports the CDC PLACES 2024 release (BRFSS 2022 survey data) as county
health metrics. Fifteen measures are included:

    * asthma              (MeasureId CASTHMA)
    * diabetes            (MeasureId DIABETES)
    * mental distress     (MeasureId MHLTH)
    * obesity             (MeasureId OBESITY)
    * smoking             (MeasureId CSMOKING)
    * physical inactivity (MeasureId LPA)
    * binge drinking      (MeasureId BINGE)
    * short sleep         (MeasureId SLEEP)
    * COPD                (MeasureId COPD)
    * heart disease       (MeasureId CHD)
    * stroke              (MeasureId STROKE)
    * depression          (MeasureId DEPRESSION)
    * poor health         (MeasureId GHLTH)
    * physical distress   (MeasureId PHLTH)
    * uninsured           (MeasureId ACCESS2)

Both the PLACES age-adjusted prevalence (DataValueTypeID ``AgeAdjPrv``)
and the crude prevalence (DataValueTypeID ``CrdPrv``) are captured, each
with its 95% confidence interval.

Inputs (under ``--source``, default ``work/places-source-2024``):

    places-county-2024.csv   (utf-8-sig)
    acquired-at.txt
    sha256.txt

Output (``--out``, default ``dist/data/places.json``):

    A JSON document covering all 3,107 atlas counties. The eight legacy
    Connecticut counties are marked unavailable because the source uses
    Connecticut planning regions instead.

The importer is fail-closed: any validation problem aborts the run and
leaves an existing output file untouched.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
import tempfile
from pathlib import Path


# ---------------------------------------------------------------------------
# Paths and constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_SOURCE_DIR = REPO_ROOT / "work" / "places-source-2024"
DEFAULT_GEO_PATH = REPO_ROOT / "dist" / "data" / "counties.geojson"
DEFAULT_OUT_PATH = REPO_ROOT / "dist" / "data" / "places.json"

SOURCE_CSV_NAME = "places-county-2024.csv"
ACQUIRED_AT_NAME = "acquired-at.txt"
SHA256_NAME = "sha256.txt"

# SHA-256 of the canonical PLACES 2024 county CSV. The value is also
# recorded in ``sha256.txt`` next to the source file; the importer verifies
# the two agree before doing anything else.
EXPECTED_SHA256 = "02517f8a0f85fbc0c02fbeea58e86437f7ad6b68f26e2988a10f7ea5d43f1dcd"

SOURCE_URL = "https://www.cdc.gov/places"
DATASET_URL = (
    "https://data.cdc.gov/500-Cities-Places/"
    "PLACES-Local-Data-for-Better-Health-County-Data-20/fu4u-a9bh"
)
DOWNLOAD_URL = "https://data.cdc.gov/api/views/fu4u-a9bh/rows.csv?accessType=DOWNLOAD"

SOURCE_LABEL = "CDC PLACES: Local Data for Better Health, 2024 release"
RELEASE_LABEL = "PLACES 2024 release; BRFSS 2022 survey data"
CITATION = (
    "Centers for Disease Control and Prevention. PLACES: Local Data for "
    "Better Health. Accessed September 28, 2026. https://www.cdc.gov/places"
)

TARGET_YEAR = "2022"

AGE_ADJUSTED_TYPE = "AgeAdjPrv"
CRUDE_TYPE = "CrdPrv"

# The eight legacy Connecticut counties. The PLACES 2024 release reports
# Connecticut using the newer planning-region geography, so these legacy
# FIPS codes have no counterpart in the source.
CT_LEGACY_FIPS = frozenset(
    {
        "09001",
        "09003",
        "09005",
        "09007",
        "09009",
        "09011",
        "09013",
        "09015",
    }
)
CT_REASON = (
    "The source uses Connecticut planning regions. These regions do not match the counties this atlas uses."
)

FAMILY_NOTE = (
    "These are model estimates for adults from CDC PLACES, 2024 release. The model uses a 2022 CDC telephone health survey. The values are not direct counts. The CDC advises against using PLACES to rank the overall health of counties. The values are adjusted for age, so counties with older or younger people compare fairly. County details show the share before the age adjustment and the likely range (95%). The CDC does not endorse this atlas."
)

MEASURES = (
    {
        "id": "asthma",
        "MeasureId": "CASTHMA",
        "title": "Current asthma among adults",
        "shortLabel": "Asthma",
        "note": (
            "A health professional told these adults that they have asthma. These adults say they still have it. People report this themselves. Most differences between counties are smaller than the 95% likely range. Treat small gaps on this map as noise."
        ),
    },
    {
        "id": "diabetes",
        "MeasureId": "DIABETES",
        "title": "Diagnosed diabetes among adults",
        "shortLabel": "Diabetes",
        "note": (
            "A health professional told these adults that they have diabetes. This does not count diabetes only during pregnancy. The measure does not include diabetes that no one has found. So the true share is higher."
        ),
    },
    {
        "id": "mental-distress",
        "MeasureId": "MHLTH",
        "title": "Frequent mental distress among adults",
        "shortLabel": "Mental distress",
        "note": (
            "Adults who report 14 or more days of poor mental health in the "
            "past 30 days."
        ),
    },
    {
        "id": "obesity",
        "MeasureId": "OBESITY",
        "title": "Obesity among adults",
        "shortLabel": "Obesity",
        "note": "Adults with a body mass index of 30 or more. Body mass index comes from height and weight that people report themselves.",
    },
    {
        "id": "smoking",
        "MeasureId": "CSMOKING",
        "title": "Current cigarette smoking among adults",
        "shortLabel": "Smoking",
        "note": "Adults who have smoked at least 100 cigarettes in their life and now smoke every day or some days.",
    },
    {
        "id": "physical-inactivity",
        "MeasureId": "LPA",
        "title": "No leisure-time physical activity among adults",
        "shortLabel": "Physical inactivity",
        "note": "Adults who report no physical activity or exercise in the past month outside their regular job.",
    },
    {
        "id": "binge-drinking",
        "MeasureId": "BINGE",
        "title": "Binge drinking among adults",
        "shortLabel": "Binge drinking",
        "note": "Men who report 5 or more drinks on one occasion in the past 30 days. Women who report 4 or more drinks on one occasion in the past 30 days.",
    },
    {
        "id": "short-sleep",
        "MeasureId": "SLEEP",
        "title": "Short sleep duration among adults",
        "shortLabel": "Short sleep",
        "note": "Adults who report usually sleeping less than 7 hours in a 24-hour period.",
    },
    {
        "id": "copd",
        "MeasureId": "COPD",
        "title": "Chronic obstructive pulmonary disease among adults",
        "shortLabel": "COPD",
        "note": "A health professional told these adults that they have chronic obstructive pulmonary disease, emphysema or chronic bronchitis.",
    },
    {
        "id": "heart-disease",
        "MeasureId": "CHD",
        "title": "Coronary heart disease among adults",
        "shortLabel": "Heart disease",
        "note": "A health professional told these adults that they have angina or coronary heart disease.",
    },
    {
        "id": "stroke",
        "MeasureId": "STROKE",
        "title": "Stroke among adults",
        "shortLabel": "Stroke",
        "note": "A health professional told these adults that they had a stroke.",
    },
    {
        "id": "depression",
        "MeasureId": "DEPRESSION",
        "title": "Depression among adults",
        "shortLabel": "Depression",
        "note": "A health professional told these adults that they have a depressive disorder.",
    },
    {
        "id": "poor-health",
        "MeasureId": "GHLTH",
        "title": "Fair or poor self-rated health among adults",
        "shortLabel": "Fair or poor health",
        "note": "Adults who rate their general health as fair or poor.",
    },
    {
        "id": "physical-distress",
        "MeasureId": "PHLTH",
        "title": "Frequent physical distress among adults",
        "shortLabel": "Physical distress",
        "note": "Adults who report 14 or more days of poor physical health in the past 30 days.",
    },
    {
        "id": "uninsured",
        "MeasureId": "ACCESS2",
        "title": "No health insurance among adults aged 18-64",
        "shortLabel": "No health insurance",
        "note": "Adults aged 18 to 64 who report no current health insurance coverage.",
    },
)

MEASURE_IDS = frozenset(measure["MeasureId"] for measure in MEASURES)

# Columns the importer reads from the source CSV. ``Data_Value_Footnote``
# is optional: it is only consulted when ``Data_Value`` is blank.
REQUIRED_COLUMNS = (
    "Year",
    "LocationID",
    "MeasureId",
    "DataValueTypeID",
    "Data_Value",
    "Low_Confidence_Limit",
    "High_Confidence_Limit",
)

FOOTNOTE_COLUMN = "Data_Value_Footnote"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class PreparationError(Exception):
    """Raised when the source data cannot be prepared."""


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    """Return the hex SHA-256 digest of ``path``."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path):
    """Load a JSON document, raising :class:`PreparationError` on failure."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise PreparationError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PreparationError(f"invalid JSON in {path}: {exc}") from exc


def _read_text(path: Path) -> str:
    """Read a UTF-8 text file, raising :class:`PreparationError` on failure."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    except FileNotFoundError as exc:
        raise PreparationError(f"missing file: {path}") from exc


def _parse_sha256_file(text: str, path: Path) -> str:
    """Extract the digest from a ``sha256.txt`` file.

    Accepts either a bare digest or the ``sha256sum`` output format
    (``<digest>  <filename>``).
    """
    tokens = text.split()
    if not tokens:
        raise PreparationError(f"{path}: empty sha256 file")
    value = tokens[0].strip().lower()
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise PreparationError(f"{path}: not a valid sha256 digest: {value!r}")
    return value


def _parse_number(text: str, context: str):
    """Parse a finite float, returning ``None`` for a blank string."""
    text = text.strip()
    if text == "":
        return None
    try:
        value = float(text)
    except ValueError as exc:
        raise PreparationError(f"{context}: not a number: {text!r}") from exc
    if not math.isfinite(value):
        raise PreparationError(f"{context}: non-finite value: {text!r}")
    return value


# ---------------------------------------------------------------------------
# Atlas geometry
# ---------------------------------------------------------------------------


def _load_atlas_fips(geo_path: Path):
    """Return the ordered list of atlas FIPS codes from a GeoJSON file."""
    geo = _load_json(geo_path)
    features = geo.get("features")
    if not isinstance(features, list) or not features:
        raise PreparationError(f"{geo_path}: expected a non-empty FeatureCollection")

    fips_list = []
    seen = set()
    for index, feature in enumerate(features):
        if not isinstance(feature, dict):
            raise PreparationError(f"{geo_path}: feature {index} is not an object")
        props = feature.get("properties")
        if not isinstance(props, dict):
            raise PreparationError(f"{geo_path}: feature {index} has no properties")

        raw = None
        for key in ("fips", "FIPS", "GEOID", "geoid"):
            if key in props and props[key] is not None:
                raw = str(props[key]).strip()
                break
        if raw is None:
            raise PreparationError(f"{geo_path}: feature {index} has no fips property")

        fips = raw.zfill(5)
        if len(fips) != 5 or not fips.isdigit():
            raise PreparationError(
                f"{geo_path}: feature {index} has invalid fips {raw!r}"
            )
        if fips in seen:
            raise PreparationError(f"{geo_path}: duplicate fips {fips}")
        seen.add(fips)
        fips_list.append(fips)

    return fips_list


# ---------------------------------------------------------------------------
# Source CSV
# ---------------------------------------------------------------------------


def _read_source_rows(csv_path: Path):
    """Read every data row from the PLACES county CSV."""
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise PreparationError(f"{csv_path}: empty CSV")
        missing = [name for name in REQUIRED_COLUMNS if name not in reader.fieldnames]
        if missing:
            raise PreparationError(
                f"{csv_path}: missing required columns: {', '.join(missing)}"
            )
        return list(reader)


def _parse_measurement(row, csv_path: Path, index: int):
    """Validate a single CSV row and return its measurement payload."""
    context = f"{csv_path}: row {index}"

    raw_value = (row.get("Data_Value") or "").strip()
    raw_low = (row.get("Low_Confidence_Limit") or "").strip()
    raw_high = (row.get("High_Confidence_Limit") or "").strip()
    footnote = (row.get(FOOTNOTE_COLUMN) or "").strip()

    if raw_value == "":
        if not footnote:
            raise PreparationError(f"{context}: blank Data_Value without a footnote")
        if raw_low or raw_high:
            raise PreparationError(
                f"{context}: suppressed row carries confidence limits"
            )
        return {"suppressed": True, "reason": footnote}

    value = _parse_number(raw_value, f"{context}: Data_Value")

    if raw_low == "" and raw_high == "":
        raise PreparationError(
            f"{context}: Data_Value present but confidence limits missing"
        )
    if raw_low == "" or raw_high == "":
        raise PreparationError(f"{context}: confidence limits partially missing")

    low = _parse_number(raw_low, f"{context}: Low_Confidence_Limit")
    high = _parse_number(raw_high, f"{context}: High_Confidence_Limit")

    if low > high:
        raise PreparationError(
            f"{context}: Low_Confidence_Limit {low} exceeds High_Confidence_Limit {high}"
        )
    if value < low or value > high:
        raise PreparationError(
            f"{context}: Data_Value {value} outside confidence interval [{low}, {high}]"
        )
    if value < 0.0 or value > 100.0:
        raise PreparationError(f"{context}: Data_Value {value} outside [0, 100]")

    return {"suppressed": False, "value": value, "low": low, "high": high}


def _parse_rows(rows, csv_path: Path):
    """Filter and validate the source rows.

    Returns ``(parsed, selected)`` where ``parsed`` maps
    ``(fips, measure_id, value_type)`` to a measurement payload and
    ``selected`` is the number of rows that survived the measure/year/type
    filters.
    """
    parsed = {}
    seen = set()
    selected = 0

    for index, row in enumerate(rows, start=2):
        measure_id = (row.get("MeasureId") or "").strip()
        if measure_id not in MEASURE_IDS:
            continue

        year = (row.get("Year") or "").strip()
        if year != TARGET_YEAR:
            raise PreparationError(
                f"{csv_path}: row {index}: Year {year!r} is not {TARGET_YEAR!r} "
                f"for measure {measure_id}"
            )

        value_type = (row.get("DataValueTypeID") or "").strip()
        if value_type not in (AGE_ADJUSTED_TYPE, CRUDE_TYPE):
            continue

        location = (row.get("LocationID") or "").strip()
        fips = location.zfill(5)
        if len(fips) != 5 or not fips.isdigit():
            raise PreparationError(
                f"{csv_path}: row {index}: LocationID {location!r} is not a "
                "5-digit FIPS code"
            )

        key = (fips, measure_id, value_type)
        if key in seen:
            raise PreparationError(
                f"{csv_path}: row {index}: duplicate row for "
                f"{fips}/{measure_id}/{value_type}"
            )
        seen.add(key)

        parsed[key] = _parse_measurement(row, csv_path, index)
        selected += 1

    return parsed, selected


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def write_atomic(path, payload) -> None:
    """Serialise ``payload`` to ``path`` via a temp file and ``os.replace``."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"

    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=path.name + ".", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------


def build(source_dir, geo_path, out_path=None):
    """Build the PLACES payload.

    Returns ``(payload, audit)``. When ``out_path`` is provided the payload
    is written atomically after every validation has passed; on any failure
    an existing output file is left untouched.
    """
    source_dir = Path(source_dir)
    geo_path = Path(geo_path)

    csv_path = source_dir / SOURCE_CSV_NAME
    acquired_path = source_dir / ACQUIRED_AT_NAME
    sha_path = source_dir / SHA256_NAME

    for path in (csv_path, acquired_path, sha_path):
        if not path.is_file():
            raise PreparationError(f"missing source file: {path}")

    # --- integrity ---------------------------------------------------------
    actual_sha = _sha256(csv_path)
    declared_sha = _parse_sha256_file(_read_text(sha_path), sha_path)
    if actual_sha != declared_sha:
        raise PreparationError(
            f"SHA-256 mismatch for {csv_path}: declared {declared_sha}, "
            f"computed {actual_sha}"
        )

    received_at = _read_text(acquired_path).strip()
    if not received_at:
        raise PreparationError(f"{acquired_path}: empty acquisition timestamp")

    # --- atlas -------------------------------------------------------------
    atlas_fips = _load_atlas_fips(geo_path)
    atlas_set = set(atlas_fips)

    # --- source ------------------------------------------------------------
    rows = _read_source_rows(csv_path)
    parsed, selected = _parse_rows(rows, csv_path)

    rows_dropped = sum(1 for key in parsed if key[0] not in atlas_set)

    # --- per-measure datasets ---------------------------------------------
    datasets = []
    audit_datasets = []

    for measure in MEASURES:
        records = {}
        values = []
        available = 0
        unavailable = 0
        suppressed = 0

        for fips in sorted(atlas_fips):
            if fips in CT_LEGACY_FIPS:
                records[fips] = {
                    "status": "unavailable",
                    "value": None,
                    "reason": CT_REASON,
                }
                unavailable += 1
                continue

            age = parsed.get((fips, measure["MeasureId"], AGE_ADJUSTED_TYPE))
            crude = parsed.get((fips, measure["MeasureId"], CRUDE_TYPE))
            if age is None or crude is None:
                raise PreparationError(
                    f"atlas county {fips} is missing {measure['MeasureId']} data"
                )

            if age["suppressed"] or crude["suppressed"]:
                if not (age["suppressed"] and crude["suppressed"]):
                    raise PreparationError(
                        f"atlas county {fips} {measure['MeasureId']}: "
                        "age-adjusted and crude suppression disagree"
                    )
                records[fips] = {
                    "status": "suppressed",
                    "value": None,
                    "reason": age["reason"],
                }
                suppressed += 1
                continue

            records[fips] = {
                "status": "available",
                "value": age["value"],
                "low": age["low"],
                "high": age["high"],
                "crude": crude["value"],
                "crudeLow": crude["low"],
                "crudeHigh": crude["high"],
                "reason": None,
            }
            available += 1
            values.append(age["value"])

        min_value = min(values) if values else None
        max_value = max(values) if values else None

        datasets.append(
            {
                "id": measure["id"],
                "title": measure["title"],
                "shortLabel": measure["shortLabel"],
                "measureId": measure["MeasureId"],
                "source": "CDC PLACES 2024 (BRFSS 2022)",
                "unit": "% of adults, adjusted for age",
                "period": TARGET_YEAR,
                "sourceUrl": SOURCE_URL,
                "datasetUrl": DATASET_URL,
                "receivedAt": received_at,
                "valueType": "age-adjusted prevalence",
                "note": measure["note"],
                "direction": "higher-worse",
                "category": "places",
                "min": min_value,
                "max": max_value,
                "records": records,
            }
        )

        audit_datasets.append(
            {
                "id": measure["id"],
                "available": available,
                "unavailable": unavailable,
                "suppressed": suppressed,
                "min": min_value,
                "max": max_value,
            }
        )

    # --- payload -----------------------------------------------------------
    payload = {
        "source": SOURCE_LABEL,
        "sourceUrl": SOURCE_URL,
        "datasetUrl": DATASET_URL,
        "release": RELEASE_LABEL,
        "receivedAt": received_at,
        "sourceFiles": [
            {
                "name": SOURCE_CSV_NAME,
                "url": DOWNLOAD_URL,
                "sha256": actual_sha,
                "retrievedAt": received_at,
            }
        ],
        "citation": CITATION,
        "note": FAMILY_NOTE,
        "datasets": datasets,
    }

    audit = {
        "csvName": SOURCE_CSV_NAME,
        "sha256": actual_sha,
        "rowsRead": len(rows),
        "rowsSelected": selected,
        "rowsDropped": rows_dropped,
        "datasets": audit_datasets,
        "outputPath": str(out_path) if out_path is not None else None,
    }

    if out_path is not None:
        write_atomic(out_path, payload)

    return payload, audit


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _print_summary(audit) -> None:
    print(f"source: {audit['csvName']} sha256={audit['sha256'][:16]}")
    print(
        f"rows: read={audit['rowsRead']} selected={audit['rowsSelected']} "
        f"dropped={audit['rowsDropped']}"
    )
    for entry in audit["datasets"]:
        print(
            f"dataset {entry['id']}: available={entry['available']} "
            f"unavailable={entry['unavailable']} "
            f"range={entry['min']}-{entry['max']}"
        )
    print(f"output: {audit['outputPath']}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Prepare CDC PLACES 2024 county health metrics for the atlas."
    )
    parser.add_argument(
        "--source",
        default=str(DEFAULT_SOURCE_DIR),
        help="directory holding the PLACES source files",
    )
    parser.add_argument(
        "--geo",
        default=str(DEFAULT_GEO_PATH),
        help="atlas counties GeoJSON used to enumerate FIPS codes",
    )
    parser.add_argument(
        "--out",
        default=str(DEFAULT_OUT_PATH),
        help="destination JSON file",
    )
    args = parser.parse_args(argv)

    try:
        _payload, audit = build(args.source, args.geo, args.out)
    except PreparationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    _print_summary(audit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
