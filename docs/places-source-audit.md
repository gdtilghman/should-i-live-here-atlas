# CDC PLACES source audit — September 28, 2026

Status: audited; decisions settled September 28, 2026 (see "User decisions").
Ingestion uses the 2024 release.

## Selected measures

The user chose three measures on September 28, 2026. All are model-based
prevalence estimates for adults 18 and older, in percent, higher-worse.

| Measure ID | Title | Definition (CDC) | Category |
|---|---|---|---|
| `CASTHMA` | Current asthma among adults | Adults who report that a health professional told them they have asthma, and who say they still have it. Self-reported; not clinically confirmed. | Health Outcomes |
| `DIABETES` | Diagnosed diabetes among adults | Adults who report that a health professional told them they have diabetes. Excludes gestational diabetes. Undiagnosed diabetes is not counted, so the measure understates true prevalence. | Health Outcomes |
| `MHLTH` | Frequent mental distress among adults | Adults who report 14 or more days of poor mental health in the past 30 days. | Health Status |

## Primary source evidence

- Dataset: "PLACES: Local Data for Better Health, County Data, 2025 release",
  data.cdc.gov `swc5-untb`. Socrata license field: Public Domain. Publisher:
  CDC, Division of Population Health. Release documented in the
  [current release notes](https://www.cdc.gov/places/current-release-notes/index.html)
  (notes dated March 16, 2026, for the December 2025 release).
- Method, from the dataset description and the
  [PLACES FAQ](https://www.cdc.gov/places/faqs/index.html): multilevel
  regression and poststratification of BRFSS 2023 responses, with Census 2023
  county population estimates and ACS 2019–2023. Confidence intervals come from
  Monte Carlo simulation; since the 2023 release, random error varies only
  within counties, which can make intervals wider.
- Definitions: [health outcomes](https://www.cdc.gov/places/measure-definitions/health-outcomes.html)
  and [health status](https://www.cdc.gov/places/measure-definitions/health-status.html).
- Citation the FAQ asks for: "Centers for Disease Control and Prevention.
  PLACES: Local Data for Better Health. Accessed [date].
  https://www.cdc.gov/places". The CDC also cautions that the model cannot
  detect the effect of local interventions.
- Age adjustment: the FAQ says to use age-adjusted values to compare areas.
  The pages read here do not name the standard population. Do not state one
  until a primary source confirms it.

## Acquisition and independent checks

Files in the ignored `work/places-source/` of the main checkout, downloaded
2026-09-28 from `https://data.cdc.gov/api/views/swc5-untb/rows.csv`. The CSV
has 229,298 rows, the same count the dataset API reports.

For each of the three measures and for both crude and age-adjusted values:

- One data year only: 2023. The file's 2022 rows belong to five other
  measures that BRFSS asks every other year.
- 2,958 counties per measure, one row per county. Every value lies inside
  its own confidence interval.
- One suppressed county: Loving County, Texas (48301), with the footnote
  "Estimates suppressed for population less than 50". Keep it as
  suppressed, never zero.
- **195 of the 3,107 atlas counties have no value.**
  - Kentucky, all 120 counties, and Pennsylvania, all 67 counties. The CDC
    says these two states did not collect enough 2023 BRFSS data to meet the
    minimum for the public data set.
  - The 8 legacy Connecticut counties. Since the 2024 release PLACES uses
    Connecticut planning regions (9 source rows). The atlas uses legacy
    counties. Mark them unavailable with a geography-vintage reason, the
    same as the HPSA layer.
  - 46 source rows are outside the lower-48 atlas (Alaska, Hawaii, DC, the
    Connecticut regions and a US total). Drop them.

Age-adjusted values, 2,957 counties:

| Measure | Median | 5th–95th percentile | Middle 50% spread | Median 95% CI width |
|---|---|---|---|---|
| Asthma | 10.7 | 9.3–12.3 | 1.2 | 2.7 |
| Diabetes | 10.7 | 8.2–15.4 | 3.0 | 3.2 |
| Frequent mental distress | 18.6 | 15.3–22.0 | 2.6 | 4.9 |

Asthma's confidence interval is more than twice its middle-50% spread. Most
county-to-county asthma differences on the map will not be distinguishable
from model uncertainty. Diabetes has the most real spread of the three.

Correlation across counties (age-adjusted): asthma–mental distress 0.67,
diabetes–mental distress 0.59, asthma–diabetes 0.24. They overlap but are
not duplicates.

## Alternative source checked

The 2024 release (`fu4u-a9bh`, BRFSS 2022) has age-adjusted asthma rows for
all 120 Kentucky and 67 Pennsylvania counties. It is one survey year older.
Do not mix releases or years between counties on one map.

## Decisions needed before ingestion

The audit offered three choices, with recommendations: 2024 release for full
coverage; map layers only, because the CDC FAQ says PLACES data "should not
be used to rank the overall health" of any county; age-adjusted values on the
map with crude values and confidence intervals in details.

## User decisions — September 28, 2026

1. **Release: 2024** (`fu4u-a9bh`, BRFSS 2022), for every county.
2. **My priorities: include.** The user chose this against the CDC ranking
   caution. The app must say, where these inputs are offered and in their
   county details, that the CDC advises against ranking counties with
   PLACES, that values are model estimates, and that asthma differences are
   mostly within uncertainty.
3. **Values: age-adjusted** on the map, with its 95% CI; crude value and its
   CI in county details.

## 2024 release checks (ingestion source)

Files in the ignored `work/places-source-2024/` of the main checkout,
downloaded 2026-09-28 from
`https://data.cdc.gov/api/views/fu4u-a9bh/rows.csv`. 240,886 data rows, the
same count the dataset API reports. Public Domain. For the three measures and
both value types: one data year (2022); 3,145 source counties, no duplicates,
no suppressed values; every value inside its interval. 3,099 of 3,107 atlas
counties have values; only the 8 legacy Connecticut counties do not.

| Measure (age-adjusted) | Median | 5th–95th percentile | Middle 50% spread | Median 95% CI width |
|---|---|---|---|---|
| Asthma | 10.8 | 9.4–12.4 | 1.2 | 2.7 |
| Diabetes | 10.8 | 8.0–15.1 | 3.2 | 3.0 |
| Frequent mental distress | 18.6 | 15.0–22.6 | 3.0 | 3.7 |

Correlation (age-adjusted): asthma–mental distress 0.71, diabetes–mental
distress 0.65, asthma–diabetes 0.32.

Reuse is public domain with the CDC citation above. No endorsement implied.
No publication is authorized by this audit.

## Source hashes

- places-county-2024.csv (ingestion source): `02517f8a0f85fbc0c02fbeea58e86437f7ad6b68f26e2988a10f7ea5d43f1dcd`

- places-county-2025.csv: `2dc8d4ae93543a217973bdc2d774855134ca01d8adf00c77a082acc4b8ce3377`
- Retrieval time is in `work/places-source/acquired-at.txt`.
