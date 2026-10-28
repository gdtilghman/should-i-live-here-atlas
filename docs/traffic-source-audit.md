# Traffic safety source audit — September 29, 2026

Status: audited. Recommended defaults taken under the user's September 29
instruction to add the remaining layers for breadth. Family `traffic`,
label "Traffic safety".

## Sources

- **Deaths:** NHTSA Fatality Analysis Reporting System (FARS), a census of
  fatal motor-vehicle crashes on public roads. National CSV files
  `https://static.nhtsa.gov/nhtsa/downloads/FARS/{year}/National/FARS{year}NationalCSV.zip`,
  file `accident.csv`, fields `STATE`, `COUNTY`, `FATALS`. Years 2019–2023
  are Final Files (2023 Final File first released April 1, 2026, per the
  FARS 2023 release notes). 2024 is still the Annual Report File, so it is not
  used. FARS is a U.S. Government work (public domain); cite NHTSA.
- **Population:** Census Bureau ACS 2019–2023 5-year, table B01003 (total
  population), summary file
  `https://www2.census.gov/programs-surveys/acs/summary_file/2023/table-based-SF/data/5YRData/acsdt5y2023-b01003.dat`.
  A 5-year ACS estimate describes the same five years as the death window.

## Measure

Traffic deaths per 100,000 residents per year, 2019–2023:

`value = deaths_2019_2023 / (5 × B01003_E001) × 100,000`, rounded to 1
decimal. Higher-worse.

What it measures: deaths in crashes **located in** the county, divided by
the people who **live** there. It describes how dangerous the county's roads
have been, including for travelers passing through. It is not a resident's
own risk. Counties with a small population and a busy highway get very high
values. Each record keeps its death count and population, so details can show
them.

## Checks (atlas has 3,107 counties)

- Deaths by year, all states: 2019 36,355; 2020 39,007; 2021 43,230; 2022
  42,721; 2023 41,025.
- Deaths with an unknown county (codes 997, 998, 999, and code 000 "not
  applicable" in Alaska and Montana) are left out: 10 in five years, all
  states.
- FARS used the old Shannon County code 46113 for 2020–2022 (21 deaths). It is
  Oglala Lakota County, 46102, which FARS uses in 2023. Map 46113 to 46102.
- Connecticut: FARS uses the legacy counties, but ACS 2019–2023 uses the new
  planning regions, so no matching population exists. The 8 legacy counties
  are unavailable, with the geography reason used by other layers.
- 3,099 counties have a rate. 18 have zero deaths in five years; that is a
  real zero, not missing.
- Rate: median 18.6, 95th percentile 55.7, maximum 7,777.8 (Loving County,
  Texas: 21 deaths, 54 residents). The atlas marks extreme values in purple.
- Spot values (deaths, population, rate): Los Angeles CA 4,033, 9,848,406,
  8.2; New York NY 182, 1,627,788, 2.2; Cook IL 1,900, 5,185,812, 7.3;
  Miami-Dade FL 1,596, 2,685,296, 11.9.

## Source files (ignored, `work/traffic-source/`)

| File | Bytes | SHA-256 |
|---|---|---|
| FARS2019NationalCSV.zip | 26,974,033 | `0974ABB92CFB04FA022631A838A3F46555025F2B011EE78ECAD15BCF86C60F31` |
| FARS2020NationalCSV.zip | 31,016,385 | `B2806902B3DA9B45C632499F82E1C74FD108238AE7F67E108EBF40360EE4C9C3` |
| FARS2021NationalCSV.zip | 35,190,858 | `743C19A13884614430D295289E655C5AD32B0A025A11E5B2149DFB57ACAE389B` |
| FARS2022NationalCSV.zip | 34,689,724 | `989448D7A2F3964264C96A3CDB220F6C413C782A33EB759781F520C5ACB5F744` |
| FARS2023NationalCSV.zip | 34,174,899 | `EDDE841EB493E55751961B36BAC2D1CE8750F601CB8E6E183A525723BB62BAB0` |
| acsdt5y2023-b01003.dat | 18,311,997 | `24AE3F523B4C54332CE0A71BA534569685A8A729056F975915D860D1EB943565` |

One `accident.csv` starts with a UTF-8 byte-order mark; read the bytes, drop
the mark, decode as Latin-1.

No publication is authorized by this audit.
