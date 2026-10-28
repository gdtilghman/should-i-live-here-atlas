# Air quality (PM2.5) source audit — September 29, 2026

Status: audited. User decision, September 29, 2026: **2020–2022 three-year
mean** (option a below).

## Selected source

"Daily County-Level PM2.5 Concentrations 2001-2022", data.cdc.gov
`53mz-4zqd`, published by the CDC National Environmental Public Health
Tracking Network. Values are modeled predictions from the EPA Downscaler,
which combines air monitor readings with Community Multiscale Air Quality
(CMAQ) model output. They are not direct monitor readings.

This source replaces an earlier plan, which was to aggregate
the 61-million-row tract file ourselves. CDC already publishes county values,
so the project needs no tract-to-county pipeline.

## Fields

Columns: `year`, `date`, `statefips`, `countyfips`, `pm25_max_pred`,
`pm25_med_pred`, `pm25_mean_pred`, `pm25_pop_pred`, in µg/m³, one row per
county per day. The current dataset gives no column descriptions. An archived
description of the 2001–2014 version
([DataLumos](https://www.datalumos.org/datalumos/project/244200/version/V1/view))
names them the maximum, median, mean and population-weighted mean
concentration. The method paper
([PMC3601977](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3601977/)) reports
that population-weighted county estimates matched monitors best.

Proposed measure: the **mean of daily `pm25_pop_pred`** per county per year,
in µg/m³, higher-worse. This is long-term fine-particle pollution where people
live. It is not a daily air quality index, not smoke-event frequency, and not
anyone's personal exposure.

## Reuse terms

Socrata license: **Public Domain U.S. Government**. This is not ODbL, so it
does not conflict with the CC BY 4.0 license for the prepared data. The
dataset lists use conditions that the layer must respect and state:

1. Statistical reporting and analysis only.
2. No attempt to identify people. (County values carry no personal data.)
3. Do not imply that interpretations come from CDC or the data sources.
4. Acknowledge the source and CDC.
5. Citation: "Centers for Disease Control and Prevention. National
   Environmental Public Health Tracking Network. Web. Accessed: [date].
   www.cdc.gov/ephtracking."

## Acquisition

CDC's API computed annual county means on its server, for 2018–2022. The
query URL is in `work/air-quality-source/query-url.txt` (ignored). Output:
`county-annual-2018-2022.csv`, 15,391 rows: year, state, county, mean of
`pm25_pop_pred`, mean of `pm25_mean_pred`, count of non-blank daily values,
and count of rows. The ingestion job must spot-check this aggregate against
raw daily rows for a sample of counties.

## Coverage checks (atlas has 3,107 counties)

| Years | Atlas counties with a population-weighted value | Complete days |
|---|---|---|
| 2018, 2019 | 3,106 | all 365 |
| 2020, 2021, 2022 | 3,053 | all 366 or 365 |

- Oglala Lakota County, South Dakota (46102) is missing in every year.
- For 2020–2022, 49 atlas counties have no rows. They are small, mostly rural
  counties in 20 states, for example 7 in Kansas and 9 in Texas. The dataset
  gives no reason.
- For 2020–2022, 5 more counties have rows, but every daily
  population-weighted value is blank: Wakulla FL, Long GA, Cameron LA, Hyde
  NC and Mathews VA. They do have an area-average value. Do not substitute
  one for the other on the same map without a user decision.
- The District of Columbia is in the source but not in the atlas. Drop it.
- Legacy Connecticut counties are present.

## Values (population-weighted, atlas counties)

| Year | Range µg/m³ | Median |
|---|---|---|
| 2018 | 4.03–16.30 | 7.90 |
| 2019 | 2.77–10.72 | 7.57 |
| 2020 | 3.80–20.83 | 7.42 |
| 2021 | 4.01–17.38 | 7.89 |
| 2022 | 3.15–13.61 | 7.43 |

Western wildfire smoke drives large differences between years (for example
the 2020 maximum). A multi-year mean is steadier than one year.

## Decision needed before ingestion

**Time window.**

- (a) **2020–2022, three-year mean.** Newest. 3,053 counties; 54 unavailable
  (the 49 missing, which include Oglala Lakota, and the 5 blank). Recommended: the newest
  data, a steadier value, and only 1.7% of counties missing.
- (b) **2018–2019, two-year mean.** 3,106 counties. Older, and it misses the
  2020–2021 smoke years.

No publication is authorized by this audit.

## Source hashes

- county-annual-2018-2022.csv: `df860a24facac0f2678d3d9e1b825d64b8de01a4044973b60399f77c4b0e1201`
- Retrieval time is in `work/air-quality-source/acquired-at.txt`.
