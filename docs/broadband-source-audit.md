# Broadband source audit — September 24, 2026

## Selected measure

FCC Connect2Health county aggregate `fixed_100_20_pct`: population with reported fixed terrestrial broadband at advertised download/upload speeds of at least100/20Mbps. Metadata tooltip dates the measurement **June2024**; the2025 platform release is not the measurement year. This is an available verified historical snapshot, not a claim to be the newest BDC filing.

Map the derived complement **Residents without reported100/20Mbps access**, percent of population, `100 - fixed_100_20_pct`, higher-worse. Preserve the source access percentage in county details. This gives the existing blue-red/purple adverse-extreme scale its usual meaning without treating greater access as worse. No invented population counts or uncertainty intervals. Reported availability is not measured performance, adoption, reliability, price, or a guarantee at a particular address. Satellite is outside fixed terrestrial service.

## Primary source evidence

- [FCC data definitions](https://c2h.fcc.gov/bh-data.html): population-based fixed terrestrial100/20 access using BDC and FCC staff block estimates.
- [2025 data explainer](https://c2h.fcc.gov/downloads/Connect2Health_2025_Data_Explainer.pdf), page2: data year2024 and variable `fixed_100_20_pct`.
- [Variable metadata](https://c2h.fcc.gov/api/variabledata/getAllVariableData): field-specific tooltip confirms June2024, percent, county availability.
- [County data](https://c2h.fcc.gov/api/crosstabCountyData/getAllCountyData): public aggregate used by the FCC map's county download component. Public client code `js/bh-data-manager.js` identifies this endpoint; `js/bh-data-download.js` offers county CSV/JSON export. No account, key or licensed address-level Fabric was acquired.

Only the FCC broadband aggregate fields are selected. The API also contains health fields with different sources; their rights or suitability are not inferred and none are copied into this layer. Reuse assessment is limited to these publicly downloadable factual county aggregates with FCC attribution; it is not a license to redistribute address-level Fabric, logos or third-party source products. No release/publication is authorized by this audit.

## Acquisition and independent checks

Original responses and PDF retained in ignored work/broadband-source, with URL/SHA256/retrieval timestamps in acquisition.json. Independent extraction found3143 unique source FIPS and exact matches for all3107atlas counties (including the eight legacy Connecticut counties). All selected source reliability flags are `reliable`; available access spans0–100. There are113counties with100%access (derivedgap0) and one with0%access (derivedgap100). No missing value is converted tozero. Scalar numericFIPS are padded to five digits; fractional/invalid/duplicate identities must fail validation.

Samples access → gap: AutaugaAL95.5→4.5; LosAngelesCA96.5→3.5; FairfieldCT96.9→3.1; LovingTX50→50. Independent values are retained privately for full parity review. Existing composite scale on the derivedvalues yields regular range0–72.6, adverse fence73, and40purple extremes. These are comparison statistics, not new source observations.

## Acceptance and current state

Broadband is implemented and locally browser-verified. Importer commit e104a44; integration commit 687f78d. Fireworks implemented the importer (initial plus one correction) and integration (first attempt); independent Luna reviews scored 9.4/10 and 9.2/10 with no unresolved must-fix findings. All 3,107 source/derived pairs match, including all eight legacy Connecticut counties. The app now has 36 datasets in seven families.

Verification: 14 importer tests, 23 integration/healthcare/employment/first-load/attribution tests, composite regression, atlas validation, JavaScript syntax and three staged deployability tests passed. Live browser verified national coverage/legend, Catron100/raw0, Alpine0/raw100, Fairfield3.1/raw96.9, unchanged national scale in state focus, and Los Angeles composite gap3.5/raw96.5 with 2,570 comparable counties. Add/remove input worked; the user's saved recipe was not overwritten. Browser warning/error logs were empty. Phone verification remains limited: the in-app browser reported a480px document despite a375px viewport request and cropped the screenshot. No stylesheet or map-interaction code changed; physical touch and fresh wheel/drag checks were not performed.

## Source hashes

- counties.json: `8869c98860471159e1c9711f083f70207a4e88dd2633feb7d9748f7ca060af50`; retrieved 2026-09-25T00:00:20.474539+00:00.
- variables.json: `bb7064432702cadd75d012936186e7e7d793bb328ae0f9a602463552268d1f9e`; retrieved 2026-09-25T00:00:20.834746+00:00.
- explainer.pdf: `6f49d45ae5e1e2f575638a5cf1afd5b766487725d56b551f3770429950925ae9`; retrieved 2026-09-25T00:00:21.128995+00:00.
