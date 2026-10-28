# Crime source audit — October 28, 2026

Status: released October 28, 2026. Family `crime`, label "Crime".
Built by `scripts/prepare-crime.py`; guarded by `scripts/test-crime.cjs`.

## Source

- FBI UCR Return A master files 2023, 2024 and 2025 from the Crime Data
  Explorer downloads page. Each file is fetched through the site's public
  link service, `https://cde.ucr.cjis.gov/LATEST/s3/signedurl?key=master_files/reta/reta-YYYY.zip`,
  which returns a short-lived S3 link. Files hold 26,490 agency records of
  7,385 characters. Hashes are in the layer's `sourceFiles`.
- Agency counties: Crime Data API `agency/byStateAbbr/XX` for the 48
  states (19,592 agencies), with the free api.data.gov key
  `DATA_GOV_API_KEY` in `.env`.
- County names to FIPS: 2021 Census Gazetteer counties; Connecticut towns
  to legacy counties: 2021 Census Gazetteer county subdivisions.
- The SRS CSV on the same page (`estimated_crimes_1979_2025.csv`) is state
  and national estimates only, so it is not used.
- The FBI programming-guidelines page on ucr.fbi.gov returned 403. It was not
  fetched another way; the
  layout below was worked out from the data instead.

## Layout (worked out from the data)

- Header 305 characters: record type at 0 (`1`), ORI at 3–10, population
  and county code in three slots: 44–53/53–56, 59–68/68–71, 74–83/83–86.
  City name 120–144. The county code is the FBI's own alphabetical number,
  not FIPS (Los Angeles is 019, FIPS 037).
- 12 monthly blocks of 590 characters. Characters 3–7 of a block hold the
  update date; blank or `0000` means the month was not reported. Then 4
  cards of 28 five-character fields: unfounded, actual, cleared, cleared
  under 18. Field order: murder, manslaughter, rape total, rape by force,
  attempted rape, robbery total and 4 subtypes, assault total (includes
  simple assault), 4 aggravated assault subtypes, simple assault, burglary
  total and 3 subtypes, larceny, motor vehicle theft total and 3 subtypes,
  grand total.
- A letter in the last place is a COBOL overpunch sign: `J`–`R` are −1 to
  −9, a correction to an earlier month. 4 full-year records hold one.

Checks: in 12,000 sampled months every subtotal identity holds (robbery,
assault, burglary, motor vehicle theft, rape, grand total). Camden, DE
monthly violent counts for 2024 and annual totals for 2023 match the API
exactly. Shaker Heights, OH reported months match the API's participation
months. Camden 2025 property crime differs by 2 (Nov and Dec): the API was
refreshed on 2026-10-15, after this master-file snapshot.

## Method

- Violent = murder + rape + robbery + aggravated assault. Property =
  burglary + larceny + motor vehicle theft. Arson is not in Return A.
- An agency counts only for a year in which it reported all 12 months.
- An agency counts fully, crimes and residents (all 3 population slots), in
  the first county the API lists for it. If the API has none, the Return A
  county code is mapped by a vote of single-county agencies (3,056 codes).
  Connecticut agencies are matched by town. Overrides: St. Louis city
  police, 5 Davidson County (Nashville) agencies, one Rhode Island state
  police barracks, and 5 Connecticut boroughs and villages. The
  Connecticut State Police has no county and is not placed.
- NYPD serves all 5 boroughs, so the 5 New York City counties share one
  citywide value, with a reason on each.
- Value = crimes / covered residents × 100,000, pooled over 2023–2025.
  A county is unavailable when full-year agencies serve under 80% of the
  residents the FBI assigns to it. Result: 2,195 available, 912
  unavailable. Gaps are largest in North Dakota, South Dakota, Kansas and
  Nebraska.
- The FBI advises against ranking places with these data. The note says
  so, as the Adult health layer does for CDC's advice.
