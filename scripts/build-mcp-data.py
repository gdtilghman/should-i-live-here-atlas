# Pack the atlas layers into compact files for the MCP server (mcp/src/data).
import json
import sys
from array import array
from pathlib import Path

STATUS_CODES = [
    "available",
    "suppressed",
    "unavailable",
    "not-applicable",
    "policy",
    "not_designated",
]
STATUS_TO_CODE = {status: i for i, status in enumerate(STATUS_CODES)}
COUNTY_COUNT = 3107
# County population comes from the traffic layer, which keeps the ACS
# population it divides by (docs/traffic-source-audit.md).
POPULATION_LAYER = "traffic-deaths-2019-2023.json"
POPULATION_SOURCE = "US Census Bureau American Community Survey, 2019-2023 5-year estimates, table B01003"
MEASURE_COUNT = 73


def load_json(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def is_finite_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and value == value
        and value != float("inf")
        and value != float("-inf")
    )


def main():
    script_path = Path(__file__).resolve()
    repo_root = script_path.parent.parent
    layers_dir = repo_root / "dist" / "data" / "layers"

    manifest = load_json(layers_dir / "manifest.json")
    counties_data = load_json(repo_root / "dist" / "data" / "counties.qd.json")

    county_rows = []
    for feature in counties_data["features"]:
        p = feature["p"]
        county_rows.append(
            {
                "fips": p[0],
                "state": p[1],
                "name": p[2],
                "stateName": p[3],
            }
        )
    county_rows.sort(key=lambda row: row["fips"])

    population = load_json(layers_dir / POPULATION_LAYER)["records"]
    for row in county_rows:
        value = (population.get(row["fips"]) or {}).get("population")
        row["population"] = value if is_finite_number(value) else None

    if len(county_rows) != COUNTY_COUNT:
        raise SystemExit(f"Expected {COUNTY_COUNT} counties, found {len(county_rows)}")

    measures = []
    layer_files = []

    for family_name, family in manifest["families"].items():
        family_note = family.get("note") or ""
        family_source_url = family.get("sourceUrl") or ""
        family_citation = family.get("citation") or ""

        for dataset in family["datasets"]:
            direction = dataset.get("direction")
            if direction is None or direction == "":
                direction = "higher-worse"

            measures.append(
                {
                    "index": len(measures),
                    "key": f"{family_name}:{dataset['id']}",
                    "family": family_name,
                    "id": dataset["id"],
                    "title": dataset["title"],
                    "unit": dataset["unit"],
                    "period": dataset["period"],
                    "direction": direction,
                    "notApplicableMeans": dataset.get("notApplicableMeans") or None,
                    "sex": dataset.get("sex") or None,
                    "sourceUrl": dataset.get("sourceUrl") or family_source_url or "",
                    "citation": dataset.get("citation") or family_citation or "",
                    "note": dataset.get("note") or "",
                    "familyNote": family_note,
                }
            )
            layer_files.append(dataset["file"])

    if len(measures) != MEASURE_COUNT:
        raise SystemExit(f"Expected {MEASURE_COUNT} measures, found {len(measures)}")

    out_dir = repo_root / "mcp" / "src" / "data"
    out_dir.mkdir(parents=True, exist_ok=True)

    with (out_dir / "counties.json").open("w", encoding="utf-8") as f:
        json.dump(
            county_rows,
            f,
            ensure_ascii=False,
            separators=(",", ":"),
            indent=None,
        )

    measures_payload = {
        "version": manifest["version"],
        "countyCount": COUNTY_COUNT,
        "statusCodes": STATUS_CODES,
        "population": {"source": POPULATION_SOURCE, "from": "traffic:deaths-2019-2023"},
        "measures": measures,
    }
    with (out_dir / "measures.json").open("w", encoding="utf-8") as f:
        json.dump(
            measures_payload,
            f,
            ensure_ascii=False,
            separators=(",", ":"),
            indent=None,
        )

    values = array("d")
    statuses = bytearray()
    available_count = 0
    nan = float("nan")

    for layer_file in layer_files:
        layer = load_json(layers_dir / layer_file)
        records = layer["records"]

        for county in county_rows:
            fips = county["fips"]
            record = records.get(fips)

            if record is None:
                values.append(nan)
                statuses.append(STATUS_TO_CODE["unavailable"])
                continue

            status = record.get("status")

            if status == "available":
                value = record.get("value")
                if is_finite_number(value):
                    values.append(value)
                    statuses.append(STATUS_TO_CODE["available"])
                    available_count += 1
                else:
                    values.append(nan)
                    statuses.append(STATUS_TO_CODE["unavailable"])
                continue

            if status not in STATUS_TO_CODE:
                raise SystemExit(
                    f"Unknown status {status!r} in layer {layer_file} for county {fips}"
                )

            values.append(nan)
            statuses.append(STATUS_TO_CODE[status])

    if sys.byteorder == "big":
        values.byteswap()

    with (out_dir / "values.bin").open("wb") as f:
        f.write(values.tobytes())

    with (out_dir / "status.bin").open("wb") as f:
        f.write(statuses)

    print(
        f"Packed {len(measures)} measures x {len(county_rows)} counties "
        f"({available_count} available) to mcp/src/data"
    )


if __name__ == "__main__":
    main()
