# Wildfire source audit — September 29, 2026

Status: audited. Recommended defaults taken under the user's September 29
instruction to add the remaining layers for breadth. Family `wildfire`,
label "Wildfire".

## Source

USDA Forest Service, Wildfire Risk to Communities, data download
spreadsheet `wrc_download_20260415.xlsx` ("last update 4/15/2026"), from
https://wildfirerisk.org/download/. It summarizes the 2nd-edition spatial
datasets (Forest Service Research Data Archive RDS-2020-0016-2 and
RDS-2020-0060-2, 2024). Methods:
https://wildfirerisk.org/wp-content/uploads/2024/09/WildfireRiskToCommunities_V2_Methods_PopulatedAreas.pdf

Reuse: the archive record states "These data were collected using funding
from the U.S. Government and can be used without additional permissions or
fees." Citation from the workbook: "USDA Forest Service. 2026. Wildfire Risk
to Communities. https://wildfirerisk.org [Date Accessed]". The archive also
says the data are modeled, carry error and uncertainty, and are meant to
compare relative wildfire risk.

This is a separate source from FEMA NRI wildfire, which stays held out
because 50 records fail its source-ratio check.

## Fields (Counties sheet, 3,144 rows)

| Field | Workbook description | Use |
|---|---|---|
| `RISK_NATIONAL_RANK` | Percentile rank of the county's mean Risk to Potential Structures (RPS) within the nation | Dataset `risk-to-homes` |
| `BP_NATIONAL_RANK` | Percentile rank of the county's mean burn probability within the nation | Dataset `likelihood` |
| `BUILDINGS_FRACTION_DE` | Share of buildings in the Direct Exposure Zone | Not used (see below) |

RPS "integrates wildfire likelihood and intensity with generalized
consequences to a home on every pixel". Burn probability is "the annual
probability of wildfire burning in a specific location". The workbook gives
only percentile ranks for counties, not raw RPS or burn probability.

Published value: percentile × 100, so 0 to 100, higher-worse. The unit reads
"national percentile (0–100)". A percentile is a rank, so equal steps are not
equal differences in risk.

`BUILDINGS_FRACTION_DE` is left out. The median county has 63% of buildings
"directly exposed", including counties with low likelihood, so on its own it
would overstate risk.

## Coverage (atlas has 3,107 counties)

- 3,099 counties join by FIPS (GEOID zero-padded to 5 digits). Every value is
  numeric; the range is 0 to 1 for both percentiles.
- The 8 legacy Connecticut counties are unavailable: the source uses the 9
  planning regions (09110–09190). Reason text as in the other layers.
- Spot values (risk, likelihood): Los Angeles CA 0.985, 0.967; Ada ID 0.985,
  0.991; Missoula MT 0.961, 0.958; New York NY 0.145, 0.145.

## Source file

- `work/wildfire-source/wrc_download_20260415.xlsx` (ignored), 4,968,274
  bytes, SHA-256
  `437C25429EB2A1CFE755832C5A02F01F2707FFA4238712DD7EF1C4CCCC76BDBD`.
- URL: https://wildfirerisk.org/wp-content/uploads/2026/04/wrc_download_20260415.xlsx

No publication is authorized by this audit.
