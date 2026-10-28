# Air-monitor, climate-station and wildfire overlays — October 28, 2026

Status: released October 28, 2026. Built by
`scripts/prepare-field-overlays.py`; county attribution by
`scripts/join-overlay-points.cjs` (the same geometry test as the quake layer).
Raw files are in ignored `work/overlay-new/`. Plain HTTP download worked for
all three; no fallback needed. All three are US government works.

## Air-quality monitor sites (`airmonitors`)

- Source: EPA AQS `https://aqs.epa.gov/aqsweb/airdata/aqs_monitors.zip`
  (monitor list extracted 2026-06-26).
- Rule: parameter 88101 (PM2.5 FRM/FEM) or 44201 (ozone), with a last
  sample on or after 2025-01-01. One point per site (state-county-site).
- 8,755 PM2.5/ozone monitor records; 5,538 last sampled before 2025;
  409 have no sample date; 1,713 active sites; 36 outside the map (Hawaii 15,
  Alaska 7, DC 6, Puerto Rico 6, Mexico 2). Result: 1,677 sites.
- Datums: WGS84 and NAD83 used as published (about 1 m apart).

## Climate normals stations (`stations`)

- Source: NOAA `https://www.ncei.noaa.gov/data/normals-annualseasonal/1991-2020/doc/inventory_30yr.txt`.
- Type from the station ID prefix: USW Weather Service or airport, USC
  Cooperative observer, US1 CoCoRaHS precipitation, USS NRCS SNOTEL.
- 15,615 stations; 123 outside the United States; 393 outside the map
  (Alaska 258, Hawaii 132, and 3 coastal stations: 2 Maryland, 1 Florida,
  that fall outside the simplified coastline). Result: 15,099 stations.

## Wildfires 100+ acres (`wildfires`)

- Source: NIFC WFIGS Incident Locations feature service,
  `https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/WFIGS_Incident_Locations/FeatureServer/0/query`
  with `IncidentTypeCategory='WF' AND FireDiscoveryDateTime >= TIMESTAMP '2025-01-01 00:00:00' AND FireDiscoveryDateTime < TIMESTAMP '2026-01-01 00:00:00' AND IncidentSize >= 100`,
  `outSR=4326`, one page of 2,000 (not cut off).
- Why 100 acres and 2025: 41,730 wildfires were found in 2025; most are
  small. A full past year does not go stale like a "current fires" snapshot.
- 1,810 incidents, unique IDs, all with a point of origin; 146 outside the
  map (Alaska 144, Hawaii 2). Result: 1,664 fires. Type is a size class.
- The point is the point of origin, not the burned area. Sizes and causes
  can be revised; cause is blank for most records and is not shown.

## Verification

`scripts/test-field-overlays.cjs` and `scripts/test-overlays.cjs` pass
(146 Node tests, 137 pass, 9 skip for ignored caches). In the local app all
three toggles load, cluster and filter, with no console errors.
