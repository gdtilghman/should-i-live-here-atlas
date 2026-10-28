# Employment intake — September 19, 2026

## Selected measure

First approved remaining ingestion: BLS LAUS county unemployment rate, by place of residence, not seasonally adjusted. Proposed dataset key `employment:unemployment-rate`, category employment, direction higher-worse. This is labor-market context, not a personal chance of finding work, wage measure or job-vacancy count.

## Source evidence

- Official county tables: https://www.bls.gov/lau/tables.htm — links 2025 annual county workbook at https://www.bls.gov/lau/laucnty25.xlsx .
- Revision notice: https://www.bls.gov/lau/launews1.htm — May 19, 2026 substate revisions and 11-month averages for 2025. October CPS collection did not occur. Label 2025 explicitly as an 11-month average; do not imply direct comparability with prior full years.
- Bulk format: https://download.bls.gov/pub/time.series/la/la.txt — tab-delimited source files with series_id, year, period, value and footnotes; M13 denotes annual average. The current 2025-forward file is la.data.0.CurrentU25-29; la.data.64.County is the county-specific history. Validate series geography using official mappings before extraction.
- Reuse: https://www.bls.gov/opub/copyright-information.htm — BLS published data are public domain; cite BLS. Do not use the BLS emblem.

## Acquisition verified — September 21, 2026

Downloaded by hand from BLS as `laucnty25.xlsx`; original preserved in ignored `work/employment-source/`. SHA256: `8b7d01a87807bbeb13cf18db9ee1cb393273803a5384f4f48262048fb37b1505`. Exact original download time is unverified; receipt timestamp is recorded separately in acquisition.json. Workbook title and footer identify BLS LAUS, 2025 11-month/annual averages, release May19,2026. Source footnote confirms all counties outside Puerto Rico exclude October; Puerto Rico is outside this atlas.

Independent XML extraction found3221 source county rows and3099 exact atlas joins. Only the eight legacy Connecticut counties are unmatched. Published matched rates span0.7–18.9 percent. Samples: AutaugaAL2.4, LosAngelesCA5.7, NewYorkNY4.7, HarrisTX4.5. Source rate is used directly, rounded to its published one decimal to remove binary spreadsheet artifacts; it is not recomputed from rounded counts. Independent rates/audit remain under ignored work/employment-source/ for full parity review.

Earlier HTTP403 and Edge download blocking are resolved by the user-supplied source; no protections were changed.

## Acceptance contract

- Preserve source file, actual receipt time (download time unknown), URL and SHA256 in ignored work source cache/provenance.
- Verify column definitions, year, footnotes, series/FIPS mapping and uniqueness before ingestion. Use source-published rate rather than deriving it from rounded counts.
- Join exact atlas FIPS only; audit Connecticut planning-region mismatch and other unmatched geography. Unmatched/suppressed/invalid remain null with a reason; genuine zero remains zero.
- Preserve published labor-force/employment/unemployment counts as context if supplied and verified, without confusing them with the mapped rate or cancer case counts.
- Retain measurement period and revision caveat in picker/legend/details/source metadata. Do not invent uncertainty intervals or compare incomplete-year trends.
- Verify all mapped values against source, bounds, missingness, national/state color consistency and My priorities behavior. Preserve default recipe and existing layers.
- Review source and implementation independently; test live desktop/narrow map before claiming completion.

## Current implementation

Importer accepted after Fireworks implementation plus one correction and orchestrator review. Main checkout passes 15 tests, including malformed workbook, duplicate identity, LAUS/FIPS mismatch, zero/null, schema/year and output-preservation checks. Every one of 3099 mapped rates matches an independent XML extraction. Collection includes all 3107 atlas counties with explicit legacy Connecticut mismatch reasons. App integration is accepted after independent review (9.1/10), main-checkout tests and live Edge verification. Importer review scored 9.2/10. The 35-layer manifest and exact employment shard serve the optional standalone/composite measure. Live checks confirm national coverage/range/outliers, Los Angeles 5.7% and source counts, CT missing reasons, state-scale consistency, add/remove and saved-recipe reload. Narrow-screen card has no horizontal overflow; browser error/warning logs are empty.
