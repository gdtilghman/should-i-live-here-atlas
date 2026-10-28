# Severe storm source audit — October 28, 2026

Status: released October 28, 2026. Family `storms`, label
"Severe storms". Dave chose the layers and the scaling on October 28.

## Source

NOAA NCEI Storm Events Database, details files v1.0, one gzipped CSV per
year, 2006–2025, from
https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/. Product page:
https://www.ncei.noaa.gov/access/storm-events-database/ (the old
www.ncdc.noaa.gov/stormevents/ address redirects there). NOAA data are public
domain in the United States. Plain HTTP download worked; no fallback needed.

Land area: `ALAND_SQMI` from the 2021 Census Gazetteer counties file,
https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2021_Gazetteer/2021_Gaz_counties_national.zip.
It matches the atlas's 2021 TIGER county boundaries.

Files and SHA-256 sums are in `work/storm-events/SHA256SUMS` (ignored). The
layer records one combined digest over the 20 yearly files.

## Method

- Datasets: `storm-tornado`, `storm-hail`, `storm-wind`, `storm-flood`
  (Flash Flood plus Flood), `storm-total` (the four groups together).
- Value: reports a year per 1,000 sq mi of land, 2006–2025 average,
  rounded to 2 places. The total uses the raw report sum, not the rounded
  rates. Zero reports read 0, not missing. All 3,107 counties are available.
- Only `CZ_TYPE = C` rows carry a county FIPS. In 2024, every Tornado, Hail,
  Thunderstorm Wind, Flash Flood and Flood row but 4 was type C. Winter,
  heat, high-wind and tropical types are type Z (forecast zone), and zones
  do not nest in counties, so they are left out. The note says so.
- 2006–2025 totals kept: wind 333,576; hail 218,654; flood 123,460; tornado
  28,892. Event IDs are unique across all 20 files.
- Joins: NOAA keeps the 8 legacy Connecticut counties in all 20 years.
  Bedford city, VA (51515, 15 rows in 2006–2012) joined Bedford County
  (51019) in 2013, so those rows join to 51019. No other lower-48 code
  misses. Rows for Alaska, Hawaii, DC and territories are skipped.

## Caveats

- These are reports, not every storm. More reports come in where more
  people live and watch, so rural counties can read low.
- Small independent cities have little land. A few reports give a high
  rate (Falls Church city, VA: total 391 on 2.0 sq mi). The app marks these
  as purple extremes.
- Counts overlap FEMA declarations in the Natural disasters family. They
  are different measures: reports of events, not federal declarations.

## Verification

- `scripts/test-storms.cjs`: 8 counties match hand-worked rates, and every
  county re-derives from the raw files in JavaScript, independently of the
  Python builder.
- Full suite: 139 Node tests, 130 pass, 9 skip (ignored source caches not on
  this clone); Python importer tests pass; `validate-atlas.py` passes.
- Local app: map, measure list, county details (Oklahoma County tornado
  3.24) and My priorities (5 storm inputs) checked in the built-in browser.
  No console errors.
