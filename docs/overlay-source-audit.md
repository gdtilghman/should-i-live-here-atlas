# Place overlays: source audit and first-pass limits

Local implementation, October 5, 2026. Base: `d9ae73aca0b553523e08e08743f76b4faf3b4e68`.
Dave subsequently approved this scoped private-preview release on October 5. No source API is called by visitors:
the catalog and each enabled category are same-origin static JSON.

## Included snapshots

| Category | Source period | Mapped locations | Scope and exclusions |
| --- | --- | ---: | --- |
| Power plants and storage | Preliminary EIA-860M August 2026; released September 24 | 18,465 | One Plant ID across operating, planned, retired and canceled/postponed inventories. 54 have an operating nuclear generator. 1,178 generator rows outside the lower 48 and 124 with missing/invalid coordinates excluded. Counts of excluded rows are not counts of unique plants. |
| Health-center service sites | HRSA directory retrieved October 5, 2026 | 16,038 | BPHC Assigned Number is the unique site key. Excludes 1,223 lower-48 administrative-only sites, 1,343 mobile-van base addresses, 736 outside-scope rows, and one invalid coordinate. Permanent and seasonal service sites remain. |
| Fatal road crashes | NHTSA FARS 2023 Final File | 37,459 | Crash coordinates, date and fatalities only; no victim identities. Excludes 184 outside-scope rows and 126 invalid/unavailable coordinates. This one-year point layer is not the full 2019-2023 county heatmap window. |
| Hospitals and critical-access hospitals | CMS/HRSA directory retrieved October 5, 2026 | 6,594 | Complete 6,752-row hospital inventory; the 1,386-row critical-access layer overlaps it. Collapse 1,364 in-scope duplicate provider rows; exclude 172 outside-scope rows and eight nonmedical institutions. |
| EPA air, water and Superfund facilities | Registry snapshot retrieved October 5, 2026 | 27,686 | Complete source rows: AIR_MAJOR 37,769, NPDES_MAJOR 7,710, SEMS_NPL 1,837. Exclude 1,109 outside-scope rows; collapse overlapping interests by Registry ID. Preserve operating/closed, permit and NPL status and supplied last-reported dates. |
| Earthquakes M3+ | USGS 2025 UTC events, retrieved October 5, 2026 | 586 | 868 events in the requested bounding box; excludes 175 non-earthquake events and 107 outside mapped lower-48 county geometry, including offshore events. Epicenters are not shaking/damage footprints or forecasts. |

All point records retain source status. Power technology, fuel/energy code and
status filters must match the **same generator group** before retaining a
plant. Operating gas cannot make a retired nuclear generator look operating.
The default status is OP only; standby and out-of-service units are not silently
called operating. Storage is explicitly named and not treated as a fuel.

EIA locations are representative plant coordinates, not stack positions,
property outlines, exposure measurements or historical exposure records. The
inventory generally covers facilities with at least 1 MW of combined nameplate
capacity; it is not every rooftop system. The retired tab is not an exhaustive
history of all plants. The source describes retired generators since 2002.
Mixed technologies and statuses remain visible in details.

HRSA service sites are not a complete hospital/physician directory and do not
establish appointment availability or quality. The similarly named Location
Identification field is a site-type code (three distinct values), **not** a
unique identifier; the ingestion explicitly uses BPHC Assigned Number.

## Reproduction and provenance

Raw snapshots are ignored under `work/overlay-sources`. SHA-256 hashes of every
input and exclusion/audit counts ship inside the prepared JSON files. Preserve
the original downloaded bytes to reproduce this exact snapshot. Re-downloading
a live directory/catalog can produce a different snapshot; record its actual
retrieval date and inspect the diff.

Exact acquisitions used:

- [EIA August 2026 workbook](https://www.eia.gov/electricity/data/eia860m/xls/august_generator2026.xlsx), saved as `august_generator2026.xlsx`.
- [EIA energy/prime-mover codes](https://www.eia.gov/electricity/data/eia860m/archive/xls/energy_source_codes_prime_mover.xlsx), inspected for the displayed fuel labels. The current inventory also includes H2.
- [HRSA service-delivery CSV](https://data.hrsa.gov/DataDownload/DD_Files/Health_Center_Service_Delivery_and_LookAlike_Sites.csv), saved as `hrsa-health-centers.csv`.
- [NHTSA 2023 Final CSV archive](https://static.nhtsa.gov/nhtsa/downloads/FARS/2023/National/FARS2023NationalCSV.zip). SHA-256 `edde841eb493e55751961b36bac2d1ce8750f601cb8e6e183a525723bb62bab0`, exactly matching the pre-existing traffic-source audit.
- [USGS bounded query](https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime=2025-01-01&endtime=2026-01-01&minmagnitude=3&minlatitude=24&maxlatitude=50&minlongitude=-125&maxlongitude=-66&orderby=time-asc), saved as `usgs-quakes-2025.json`. The build additionally enforces event type and 2025 UTC dates.

From the repository root, using the saved snapshots:

```powershell
node scripts/join-overlay-quakes.cjs
python scripts/prepare-overlays.py --retrieved 2026-10-05
node --test scripts/test-overlay-spatial.cjs scripts/test-overlays.cjs
```

The join uses the existing county geometry and D3 winding normalization. It does
not infer coordinates from a county centroid. The Python ingestion uses only
the standard library, including direct OOXML parsing; no Excel dependency.
The six source shards total about 3.25 MB gzip; the catalog about 1.7 KB.
Only enabled source shards load. Initial map loading does not wait for them.

## Rights and release gate

[EIA's reuse policy](https://www.eia.gov/about/copyrights_reuse.php), inspected
October 5, permits distribution of its data with source/date acknowledgement;
no logos or photographs are used. [USGS's policy](https://www.usgs.gov/information-policies-and-instructions/copyrights-and-credits)
identifies USGS-produced data as public domain. FARS is the same federal final
archive already audited for the existing traffic layer.

HRSA reuse verification is resolved. Its official
[Data Sources and Metadata](https://data.hrsa.gov/data/data-sources) page,
inspected October 5, lists **Usage limitations: None** for Health Center Service
Delivery Sites and CMS Provider of Services. The hospital GIS service explicitly
identifies CMS POS/QIES as its source, and provides hospital and critical-access
point layers. This does not change the existing AHRF/AMA exclusion; these
selected facility fields are not those licensed workforce records.

[EPA geospatial terms](https://www.epa.gov/web-policies-and-procedures/epa-disclaimers)
identify EPA-produced geospatial data as public domain by default unless
otherwise specified. The selected FRS service metadata was inspected; no
additional restriction was identified. Attribute EPA FRS; no endorsement,
measurement of exposure, or warranty is implied. No logo or agency photograph
is used. The scoped private-preview publication is approved; no unresolved source
reuse gate remains for these six included catalogs.

## EPA recovery and completion evidence

The original public base was
`https://geodata.epa.gov/arcgis/rest/services/OEI/FRS_INTERESTS/MapServer`.
`/<layer>/query` GET requests used `f=json`, `where=1=1`,
`outFields=REGISTRY_ID,PRIMARY_NAME,STATE_CODE,ACTIVE_STATUS,LAST_REPORTED_DATE,INTEREST_TYPE`,
`outSR=4326`, `returnGeometry=true`, `orderByFields=OBJECTID`, and the offsets
and limits below. These failures were source responses, not approval denials.

| Attempt | Exact category/offset evidence | Result |
| --- | --- | --- |
| Initial offset paging | Layer 3, 5,000-row pages at offsets 0/5,000/10,000/15,000 | 20,000 rows read; offset 20,000 returned JSON error code 404, Service not found. No partial output included. |
| Smaller cached paging | Layer 12, 1,000-row pages | Offsets 0-3,000 saved (4,000/7,710); offset 4,000 returned HTTP 504, then JSON 404 on bounded retry. |
| NPL offset paging | Layer 22, offset 0, limit 1,000 | HTTP 504; initial count was 1,837. |
| TRI first count | Layer 23, returnCountOnly=true | JSON 404. Later returnIdsOnly succeeded with 74,230 IDs; TRI is not included in this pass. |
| Official bulk alternatives | `https://edg.epa.gov/data/public/OEI/FRS/FRS_Interests_Download.zip` and `https://ordsext.epa.gov/FLA/www3/national_frs.kmz` | Large archive declared 1,862,073,772 bytes; stopped after 122,683,392 bytes and removed only that incomplete file. KML downloaded completely (5,476,827 bytes, 165,250 placemarks), but lacks embedded program membership needed for these filters, so was not used. |
| ID inventory and chunks | Layers 3/12/22, returnIdsOnly=true; 500-ID chunks with exact ID checks | NPL completed 1,837/1,837. Some long GET and read-only POST chunks worked, others returned JSON 404. This does not prove a single failure cause. |
| Successful recovery | Short GET queries with `where=OBJECTID >= first AND OBJECTID <= last`, outFields above plus OBJECTID, resultRecordCount=1000, outSR=4326 | All remaining chunks completed; 85 recovery requests, zero errors. Full returned ID sets and counts matched all three inventories. |

The complete retained raw files are `epa-3.json`, `epa-12.json`, `epa-22.json`.
ID inventories, individual chunks, `epa-id-acquisition-log.json` and
`epa-range-acquisition-log.json` remain ignored source evidence. The latter
contains exact successful request URLs. Output SHA-256 hashes are in `epa.json`.
`python scripts/fetch-overlay-facilities.py --fetch` reproduces the successful
short-range approach and hospital paging, caps transient attempts at three,
stops on 401/403, and checks identity/completeness before writing each shard.
It does not bypass access denials or require credentials. Follow with the
existing prepare script using the actual new retrieval date.

Hospital point endpoints are the official
`https://gisportal.hrsa.gov/server/rest/services/HealthCareFacilities/CMSApprovedFacilities_FS/MapServer/0`
and `/1`. Ordered 1,000-row pages reconciled to counts 6,752 and 1,386; CMS
provider numbers are unique within each layer. Both layers are deduplicated
in one hospital catalog. Their directory membership is not represented as
current operating status. No geocoding was used.

## Excluded and deferred

EPA AIR_MAJOR, NPDES_MAJOR and SEMS_NPL are now complete and included.
TRI was deferred in the October 5 release; major-air and water program facilities provide the first
verified industrial/environmental context. The October 20 local annual TRI addition is audited separately in [tri-source-audit.md](tri-source-audit.md); it does not alter these FRS snapshots. NPDES markers are not drinking-water
service areas, treatment plants as a class, or evidence of violations/exposure.

NOAA storm locations, current wildfire incident points, air-monitor sites and
climate stations remain candidates, not implemented layers. They require their
own acquisition, temporal filters, source-rights checks and tests. No point
proxy is invented for rent, home value, unemployment or broadband availability.
Related-family tags are suggestions only; every included overlay remains
available over every heatmap. No new cancer/water county dataset was added.

## Interaction and interpretation

Clustering uses viewport cells; counts are locations, not severity or risk.
Mixed-category groups can be inspected through a member selector. An equivalent
searchable, paginated list supports keyboard users. Coordinates use the exact
Albers projection and composed national/state transforms. During gestures,
existing groups transform with the map; membership is rebuilt after motion.
The source records never change the heatmap or priority calculations.

Custom pins use explicit placement mode, or editable numeric coordinates. They
must fall inside mapped lower-48 county geometry; coastlines are simplified.
Save, edit, move, delete and undo-last-delete are local to this browser, capped
at 100 pins with bounded labels/notes. Strings render with textContent. Corrupt
or unavailable storage produces a readable message; priorities use their
existing separate storage. No geocoding, sharing, submissions or community
catalog is implemented. Clearing browser storage removes pins.

The prominent UI notice states that visual overlap does not establish
correlation, causation or exposure, periods can differ, and county averages are
not individual risk. No automatic distances-as-risk, correlation or causal
scores are computed.
