#!/usr/bin/env python3
"""Build three point overlays from acquired official snapshots.

- airmonitors: EPA AQS monitor sites with a PM2.5 (88101) or ozone (44201)
  sample on or after 2025-01-01. One point per site.
- stations: NOAA stations with 1991-2020 US Climate Normals. The type is the
  network from the station ID prefix.
- wildfires: NIFC WFIGS wildfire incidents (IncidentTypeCategory WF)
  discovered in 2025 with a reported size of 100 acres or more. The point is
  the point of origin, not a burn perimeter.

Each point is kept only if it falls inside a mapped lower-48 county, tested
with the app's own geometry by scripts/join-overlay-points.cjs. Coordinates
are used as published; the AQS NAD83 and WGS84 datums differ by about a meter
and are not converted. The builder adds or replaces only these three catalog
entries and leaves the others and their dates alone.

Inputs in work/overlay-new/ (ignored): aqs_monitors.zip,
inventory_30yr.txt, wfigs-2025-100ac.json (see docs/field-overlays-source-audit.md
for the exact queries).

  python scripts/prepare-field-overlays.py --retrieved 2026-10-28

Standard library and Node (for the geometry join). No network use.
"""

import argparse
import csv
import hashlib
import io
import json
import subprocess
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTSIDE = "outside mapped lower-48 county geometry"
AQS_PARAMETERS = {"88101": "PM2.5 monitor", "44201": "Ozone monitor"}
AQS_ACTIVE_FROM = "2025-01-01"
STATION_NETWORKS = {
    "USW": "Weather Service or airport station",
    "USC": "Cooperative observer station",
    "US1": "CoCoRaHS volunteer precipitation station",
    "USS": "NRCS SNOTEL snow station",
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def join_counties(points, work):
    """Return {id: county FIPS} for points inside a mapped county."""
    candidates = work / "join-candidates.json"
    result = work / "join-counties.json"
    candidates.write_text(json.dumps([{"id": p["id"], "longitude": p["longitude"], "latitude": p["latitude"]} for p in points]))
    subprocess.run(["node", str(ROOT / "scripts" / "join-overlay-points.cjs"), str(candidates), str(result)], check=True)
    return json.loads(result.read_text())


def place(points, work, excluded):
    """Keep points inside a mapped county and set their state."""
    counties = join_counties(points, work)
    kept = []
    for point in points:
        fips = counties.get(point["id"])
        if not fips:
            excluded[OUTSIDE] += 1
            continue
        kept.append({**point, "state": fips[:2]})
    return kept


def airmonitors(path, work):
    excluded, audit = Counter(), Counter()
    sites = defaultdict(list)
    with zipfile.ZipFile(path) as archive, archive.open("aqs_monitors.csv") as raw:
        for row in csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8", newline="")):
            if row["Parameter Code"] not in AQS_PARAMETERS:
                continue
            audit["PM2.5 or ozone monitor records"] += 1
            if not row["Last Sample Date"]:
                excluded["no sample date"] += 1
                continue
            if row["Last Sample Date"] < AQS_ACTIVE_FROM:
                excluded["last sample before 2025"] += 1
                continue
            sites[(row["State Code"], row["County Code"], row["Site Number"])].append(row)
    points = []
    for (state, county, site), rows in sorted(sites.items()):
        locations = Counter((float(r["Longitude"]), float(r["Latitude"])) for r in rows)
        if len(locations) > 1:
            audit["sites with more than one monitor coordinate"] += 1
        (lon, lat), _ = locations.most_common(1)[0]
        types = sorted({AQS_PARAMETERS[r["Parameter Code"]] for r in rows})
        first = rows[0]
        name = first["Local Site Name"].strip() or first["Address"].strip() or f"AQS site {state}-{county}-{site}"
        agencies = sorted({r["Reporting Agency"].strip() for r in rows if r["Reporting Agency"].strip()})
        points.append({
            "id": f"AQS-{state}-{county}-{site}",
            "name": name,
            "longitude": round(lon, 6),
            "latitude": round(lat, 6),
            "groups": [{"type": t, "status": "Sampled in 2025 or later"} for t in types],
            "date": max(r["Last Sample Date"] for r in rows),
            "notes": f"{' and '.join(types)}. Reported by {', '.join(agencies) or 'the source agency'}. A monitor measures the air at its site; it does not measure anyone's exposure.",
        })
    audit["active sites before geometry"] = len(points)
    return place(points, work, excluded), dict(excluded), dict(audit)


def stations(path, work):
    excluded, audit = Counter(), Counter()
    points = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        station = line[0:11].strip()
        audit["inventory stations"] += 1
        if not station.startswith("US"):
            excluded["not a United States station"] += 1
            continue
        network = STATION_NETWORKS.get(station[:3])
        if not network:
            raise SystemExit(f"unknown station network {station[:3]} for {station}")
        points.append({
            "id": station,
            "name": line[41:71].strip().title() or station,
            "longitude": round(float(line[21:30]), 6),
            "latitude": round(float(line[12:20]), 6),
            "groups": [{"type": network, "status": "1991–2020 normals"}],
            "notes": f"NOAA station {station}, elevation {float(line[31:37]):g} m. It has 1991–2020 climate normals; some stations have precipitation only.",
        })
    return place(points, work, excluded), dict(excluded), dict(audit)


def size_class(acres):
    if acres >= 10000:
        return "10,000 acres or more"
    if acres >= 1000:
        return "1,000–9,999 acres"
    return "100–999 acres"


def wildfires(path, work):
    excluded, audit = Counter(), Counter()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("exceededTransferLimit"):
        raise SystemExit("the wildfire query was cut off; page it")
    points = []
    for feature in payload["features"]:
        a, geometry = feature["attributes"], feature.get("geometry") or {}
        audit["source incidents"] += 1
        if a.get("IncidentTypeKind") != "FI" or not a.get("IncidentSize") or a["IncidentSize"] < 100:
            raise SystemExit(f"{a.get('UniqueFireIdentifier')}: outside the query filter")
        discovered = datetime.fromtimestamp(a["FireDiscoveryDateTime"] / 1000, tz=timezone.utc).date().isoformat()
        if not discovered.startswith("2025-"):
            raise SystemExit(f"{a['UniqueFireIdentifier']}: discovered {discovered}")
        if "x" not in geometry or "y" not in geometry:
            excluded["no point of origin"] += 1
            continue
        acres = a["IncidentSize"]
        points.append({
            "id": a["UniqueFireIdentifier"],
            "name": (a.get("IncidentName") or "").strip().title() or a["UniqueFireIdentifier"],
            "longitude": round(geometry["x"], 6),
            "latitude": round(geometry["y"], 6),
            "groups": [{"type": size_class(acres), "status": "Discovered in 2025"}],
            "date": discovered,
            "notes": f"Reported size {acres:,.0f} acres. Point of origin, not a burn perimeter. Size and cause can be revised.",
        })
    return place(points, work, excluded), dict(excluded), dict(audit)


SPECS = [
    ({"id": "airmonitors", "label": "Air-quality monitor sites", "file": "airmonitors.json", "color": "#b9e27a",
      "source": "EPA Air Quality System monitors", "sourceUrl": "https://aqs.epa.gov/aqsweb/airdata/download_files.html",
      "relatedFamilies": ["air", "places"],
      "caveat": "Sites with a PM2.5 or ozone sample in 2025 or later. One point per site; the type filter shows each pollutant. A monitor measures the air at its site. It is not a county average, a measured exposure or a health risk, and most counties have no monitor."},
     "aqs_monitors.zip", airmonitors, lambda r: "Monitor list extracted 2026-06-26; retrieved " + r),
    ({"id": "stations", "label": "Climate normals stations", "file": "stations.json", "color": "#e7a3c9",
      "source": "NOAA US Climate Normals 1991–2020", "sourceUrl": "https://www.ncei.noaa.gov/products/land-based-station/us-climate-normals",
      "relatedFamilies": ["climate", "storms"],
      "caveat": "Stations with 1991–2020 climate normals. The type is the observing network. Some stations report precipitation only. A station describes its own site, not the whole county; the county heat layer uses gridded data, not these stations."},
     "inventory_30yr.txt", stations, lambda r: "1991–2020 normals inventory; retrieved " + r),
    ({"id": "wildfires", "label": "Wildfires 100+ acres (2025)", "file": "wildfires.json", "color": "#ff6f3c",
      "source": "NIFC WFIGS incident locations", "sourceUrl": "https://data-nifc.opendata.arcgis.com/datasets/nifc::wfigs-incident-locations/about",
      "relatedFamilies": ["wildfire", "disasters"],
      "caveat": "Wildfire incidents discovered in 2025 with a reported size of 100 acres or more. The point is where the fire started, not the area burned. Sizes can be revised. Smaller fires and prescribed burns are not shown. Not a forecast or a risk estimate."},
     "wfigs-2025-100ac.json", wildfires, lambda r: "2025 discoveries; retrieved " + r),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source-dir", default=str(ROOT / "work" / "overlay-new"))
    parser.add_argument("--retrieved", required=True, help="Actual UTC acquisition date, YYYY-MM-DD")
    args = parser.parse_args()
    work = Path(args.source_dir)
    out = ROOT / "dist" / "data" / "overlays"
    catalog_path = out / "catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))

    entries = []
    for spec, source_name, builder, period in SPECS:
        source = work / source_name
        points, excluded, audit = builder(source, work)
        if not points or len({p["id"] for p in points}) != len(points):
            raise SystemExit(f"{spec['id']}: no points or duplicate IDs")
        record = {"schemaVersion": 1, "points": points, "excluded": excluded, "audit": audit,
                  "exclusionsSummary": "; ".join(f"{n:,} {reason}" for reason, n in excluded.items()),
                  "sourceFiles": [{"file": source.name, "sha256": sha256(source)}], "retrieved": args.retrieved}
        (out / spec["file"]).write_text(json.dumps(record, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        entries.append({**spec, "period": period(args.retrieved), "count": len(points), "retrieved": args.retrieved})
        print(spec["id"], len(points), "excluded", excluded, "audit", audit)

    ids = {e["id"] for e in entries}
    catalog["overlays"] = [o for o in catalog["overlays"] if o["id"] not in ids] + entries
    temporary = catalog_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(catalog_path)


if __name__ == "__main__":
    main()
