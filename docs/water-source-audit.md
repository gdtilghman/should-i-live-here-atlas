# Drinking water source audit — September 29, 2026

Status: audited. Corrected September 29: the first audit counts keyed
violations by `VIOLATION_ID` alone and undercounted; the importer and an
independent recount agree on every county.
 Recommended defaults taken under the user's September 29
instruction to add the remaining layers for breadth. Family `water`, label
"Drinking water". This is the weakest of the new layers; read the limits.

## Source

EPA Enforcement and Compliance History Online (ECHO), SDWA data download
`https://echo.epa.gov/files/echodownloads/SDWA_latest_downloads.zip`
(424 MB, files dated July 9, 2026, SDWIS submission quarter 2026Q2). Field
reference: https://echo.epa.gov/tools/data-downloads/sdwa-download-summary.
EPA data are U.S. Government works (public domain); cite EPA ECHO/SDWIS.

Files used from the zip:

- `SDWA_PUB_WATER_SYSTEMS.csv`: `PWSID`, `PWS_TYPE_CODE`, `PWS_ACTIVITY_CODE`,
  `POPULATION_SERVED_COUNT`, `STATE_CODE`.
- `SDWA_GEOGRAPHIC_AREAS.csv`: `PWSID`, `AREA_TYPE_CODE`, `COUNTY_SERVED`.
- `SDWA_VIOLATIONS_ENFORCEMENT.csv` (4.1 GB, 15.4 million rows; one row per
  violation and enforcement pair): `PWSID`, `VIOLATION_ID`,
  `IS_HEALTH_BASED_IND`, `NON_COMPL_PER_BEGIN_DATE`,
  `NON_COMPL_PER_END_DATE`, `VIOLATION_CATEGORY_CODE`.

All three are read as Latin-1 CSV directly from the zip.

## Measure

Share of people served by community water systems in the county whose
system had at least one health-based violation during 2023–2025, in
percent. Higher-worse.

1. Systems: active community water systems only (`PWS_TYPE_CODE` "CWS",
   `PWS_ACTIVITY_CODE` "A"): 49,378 systems.
2. State of a system: the first two letters of `PWSID` when they are
   letters (state primacy). Otherwise (tribal systems under EPA primacy,
   numeric IDs) use `STATE_CODE`. `STATE_CODE` alone is the owner's mailing
   state and put systems in the wrong state, so it is only the fallback.
3. County: `AREA_TYPE_CODE` "CN" rows, matched to atlas counties by state
   and name. `ANSI_ENTITY_CODE` is **not** used: it is not a reliable county
   FIPS code (for example Arizona 031 and Connecticut 305 appear). Name
   normalization: accents removed; lower case; "&" to "and"; "saint",
   "st." to "st"; punctuation removed; a trailing "county", "parish",
   "borough", "census area" or "municipality" removed; spaces collapsed.
   Aliases: Louisiana "la salle" is LaSalle Parish; South Dakota "shannon"
   is Oglala Lakota County. "Richmond city" and "Richmond County" stay
   distinct. Area rows with a blank county name are not matched.
4. Violation in window: `IS_HEALTH_BASED_IND` "Y", counted once per
   (`PWSID`, `VIOLATION_ID`) pair, with a noncompliance period that overlaps January 1,
   2023 to December 31, 2025. A blank end date or the value "--->" means the
   violation is still open (3,362 such values). `VIOLATION_ID` is unique
   only within a system: 24,396 IDs are reused by more than one system (ID
   "605" by more than 150), so the ID alone must never be the key.
5. County value = 100 × (population served by the county's systems that
   had a violation) / (population served by all the county's systems),
   rounded to 1 decimal. A system that lists several counties counts fully
   in each (174 of 49,006 systems list more than one).

## Limits (state them in the app)

- `POPULATION_SERVED_COUNT` is the system's estimate of people served, not
  county residents. One large system can decide a county: New York County
  is 100% because the New York City system lists only that county and had a
  health-based violation in the window.
- One violation of any length marks all of a system's customers. The
  measure says a violation happened, not how long or how serious it was.
- People on private wells are not covered.
- Violation records depend on state reporting to EPA.

## Checks (atlas has 3,107 counties)

- 280,250 health-based violations (system and ID pairs) for active
  community systems; 28,678 overlap 2023–2025, at 9,722 systems
  (categories: treatment technique 14,560; maximum contaminant level
  14,098; maximum residual disinfectant level 20).
- 3,057 counties have a value. 935 are exactly 0 (a real zero); 23 more
  have a share under 0.05% and show as 0.0 after rounding.
- 50 counties have no matched community system and are unavailable. They
  include most Virginia independent cities, which are recorded as city
  areas, not county areas, plus places served only by private wells or by
  systems that did not list the county.
- The 8 legacy Connecticut counties match by name and are available.
- Distribution: median 3.9, 75th percentile 26.3, maximum 100.
- Spot values (percent, population served, population with a violation):
  Cook IL 4.1, 5,221,530, 213,274; Harris TX 52.2, 5,897,137, 3,080,296;
  New York NY 100.0, 8,271,000, 8,271,000; LaSalle LA 55.1, 19,338, 10,646;
  Autauga AL 0.0, 71,034, 0; Oglala Lakota SD 0.0, 1,398, 0.

## Source file

`work/water-source/SDWA_latest_downloads.zip` (ignored), 423,774,232 bytes,
SHA-256 `A18A20F9091C2E0466C91C83D0BAC5651473441642331D09504E447A6E2AC7A4`.

No publication is authorized by this audit.
