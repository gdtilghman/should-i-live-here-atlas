# Data license and source terms

This file covers the prepared data files under `dist/data/`. It does not
cover the software in this repository, which is licensed under the Apache
License, Version 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

## License for the prepared layers

The prepared files under `dist/data/` are licensed under
[Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/)
(CC BY 4.0).

These files are derived works. The selection, cleaning, county matching,
scaling and structure are the contribution licensed here. The underlying
federal measurements are separate and are described below.

Attribution for reuse:

> Should I Live Here county atlas, copyright 2026 Gerald Tilghman, CC BY 4.0.
> Derived from United States federal sources listed in LICENSE-DATA.md.

Attributing this project does not satisfy the attribution each upstream
source asks for. Cite the upstream source as well when you reuse a specific
measurement.

## Why the split

United States federal government works are generally not subject to domestic
copyright. That does not mean everything inside a federal release is free to
redistribute. A federal agency can publish a file that contains third-party
licensed input, and that input keeps its own restrictions.

This project has already hit that case once. Treat every new source as
restricted until its own archive notice has been read.

## Source inventory

| Layer | Upstream source | Terms and limits as observed |
| --- | --- | --- |
| Cancer incidence and trend | NCI and CDC State Cancer Profiles, 2018-2022 incidence exports | Federal public data. Sex-specific, age-adjusted. Suppressed values and Kansas policy exclusions stay null, never zero. The five-year trend category is distinct from the fixed incidence window. |
| Disaster declarations | FEMA OpenFEMA Disaster Declarations Summaries v2, retrieved September 14, 2026 | Federal public data. FEMA requires a not-endorsed notice, which now ships in the `note` field of every disaster layer; see the FEMA attribution section in README.md. FEMA and DHS logos and seals may not be used without prior written authorization, and none are used here. |
| Modeled hazard loss | FEMA National Risk Index v1.20: inland flooding, hurricane, tornado, coastal flooding, earthquake, hail, ice storm, lightning, strong wind, winter weather | Federal public data. Modeled annual building loss per $10,000 of county building value. Hazard vintages differ. Source-marked not applicable stays distinct from a meaningful zero; hurricane, coastal flooding and ice storm declare it a best case. Wildfire and landslide are held out (source-ratio check fails in 50 counties). |
| Housing burden, costs and commute | US Census Bureau American Community Survey, 2020-2024 | Federal public data. Rent burden is published. Median gross rent (B25064) and median home value (B25077) are published medians with 90% margins of error; medians the Census could not compute stay suppressed. Mean commute here is **derived** from B08013 and B08303, not the published S0801 estimate, and carries no fabricated confidence interval. |
| Unemployment | BLS Local Area Unemployment Statistics, 2025 county table released May 19, 2026 | BLS public-domain data; cite BLS, no agency logo or endorsement. Source-published unemployment rates by residence, not seasonally adjusted. 11-month averages exclude October 2025 and are not fully comparable with other annual years. Exact FIPS joins leave eight legacy Connecticut counties unavailable. [BLS reuse terms](https://www.bls.gov/opub/copyright-information.htm). |
| Broadband access gap | FCC Connect2Health county aggregate from Broadband Data Collection and FCC staff block estimates, June2024 measurement /2025platform | Publicly downloadable factual county aggregates with FCC attribution. Derived gap is100 minus reported population access at fixed terrestrial100/20Mbps. No address-level Location Fabric, agency logo or unrelated health fields are redistributed. [Source audit](docs/broadband-source-audit.md). |
| Adult health (15 measures, from asthma to no health insurance) | CDC PLACES 2024 release, county-level estimates with 2022 BRFSS survey data, retrieved September 28, 2026 | Public domain; cite CDC PLACES. Model-based prevalence for adults, age-adjusted map values with crude percentages and 95% confidence intervals in county details. The CDC advises against ranking counties with PLACES data. Asthma differences are mostly within measurement uncertainty. Eight legacy Connecticut counties unavailable; the source reports planning regions. No CDC endorsement implied. [Source audit](docs/places-source-audit.md). |
| Air quality (PM2.5) | CDC Tracking Network daily county PM2.5 (EPA Downscaler model, 2001–2022), 2020–2022 mean of annual population-weighted means, retrieved September 29, 2026 | Public domain U.S. Government; statistical reporting and analysis only. No attribution may imply CDC endorsement of interpretations. Acknowledge the source and CDC. Source: CDC National Environmental Public Health Tracking Network; EPA Downscaler combines monitors with air quality model output. Modeled long-term fine-particle pollution where people live, not daily air quality, smoke-event frequency or anyone's personal exposure. Forty-nine missing counties; five others have rows but no population-weighted values. [Source audit](docs/air-quality-source-audit.md). |
| Primary care shortage | HRSA Health Professional Shortage Areas, primary care, retrieved September 16, 2026 | Federal public data; the download page states "Usage limitations: None" and every organization in the lineage is federal. An administrative priority score, not a provider supply rate. Counties with no designation are marked not designated, which is not evidence of adequate access. Audit evidence is recorded in docs/enrichment-research.md. |
| Heat (days at or above 95°F) | NOAA NCEI nClimGrid-Daily v1.0.0, scaled county area averages of daily maximum temperature, 1991-2020, retrieved September 29, 2026 from NOAA's open-data mirror on AWS | NOAA-produced data are public domain in the United States. Cite NOAA NCEI nClimGrid-Daily v1.0.0; the layer does not imply NOAA endorsement. Derived here as the mean annual count of days at or above 35°C. Lexington city, Virginia, has no NOAA average and stays unavailable. |
| Wildfire | USDA Forest Service, Wildfire Risk to Communities (2nd edition), county workbook updated April 15, 2026 | U.S. Government data; "can be used without additional permissions or fees". Cite USDA Forest Service, Wildfire Risk to Communities. National percentile ranks of modeled risk to homes and burn probability; a rank, not a probability or loss. Eight legacy Connecticut counties unavailable. [Source audit](docs/wildfire-source-audit.md). |
| Drinking water | EPA ECHO SDWA data download (SDWIS 2026Q2), retrieved September 29, 2026 | U.S. Government work (public domain); cite EPA ECHO/SDWIS. Share of people on active community water systems whose system had a health-based violation in 2023-2025. One large system can decide a county; private wells are not covered; no EPA endorsement implied. [Source audit](docs/water-source-audit.md). |
| Traffic safety | NHTSA FARS 2019-2023 Final Files; US Census Bureau ACS 2019-2023 population (B01003) | U.S. Government works (public domain); cite NHTSA and the Census Bureau. Deaths in crashes located in the county per 100,000 residents; includes people passing through. Eight legacy Connecticut counties unavailable (population uses planning regions). [Source audit](docs/traffic-source-audit.md). || County boundaries | US Census Bureau TIGER/Line 2021 county file | Federal public data. Simplified for display with Mapshaper. Legacy Connecticut counties; see the note below. |

## Excluded sources and why

**HRSA Area Health Resources File (AHRF).** Excluded. The 2024-2025 User
Guide inside the archive requires Bureau permission for reproduction and
copyright-owner consent for copying American Medical Association, American
Hospital Association and American Dental Association data. The primary-care
physician fields are explicitly AMA derived. The download page shows
"Usage limitations: None", which does not override the notice inside the
archive. Do not ship these fields without the required permission.

## Audit record for the primary care shortage layer

**HRSA Health Professional Shortage Areas, primary care.** Audited on
September 16, 2026 by `scripts/audit-healthcare.py`; the user settled the
open questions on September 17 and the layer shipped on September 28.

Rights position, recorded as evidence and not as a clearance: the download
page lists the dataset as published by HRSA Bureau of Health Workforce,
Division of Policy and Shortage Designation, with "Usage limitations: None".
The metadata workbook marks 99 of 100 attributes `Public`, and the single
`Restricted` attribute is not among the 66 columns used. Every organization
in the lineage is federal, so no AMA, AHA or ADA input appears. The
shapefile archives were not fetched and their embedded notices are unchecked.

Open questions are recorded in
[docs/enrichment-research.md](docs/enrichment-research.md).

## Known geographic limits

Connecticut reorganized from counties into planning regions. This atlas uses
the eight legacy counties `09001` to `09015`. Newer federal sources use the
nine planning regions `09110` to `09190`. The two sets share no code. No
crosswalk is applied, so a Connecticut county can read as having no data when
the source simply uses a different geography. Do not read that as an absence
of the underlying condition.

Absence of a value is never the same as zero. Missing, excluded, not
applicable, not designated and a meaningful zero are kept distinct throughout
this project. Preserve that distinction in any reuse.


## New point overlays - local source audit (October 5, 2026)

Prepared `dist/data/overlays/` follows the existing prepared-data license,
subject to the upstream checks in [docs/overlay-source-audit.md](docs/overlay-source-audit.md).
EIA-860M preliminary August 2026 was released September 24, 2026; EIA permits
data reuse with acknowledgement. USGS-produced earthquake data are public
domain under its published policy. NHTSA FARS 2023 is the previously audited
federal final archive. No agency logos or photographs are included.

HRSA's official Data Sources and Metadata page lists no usage limitations
for Health Center Service Delivery Sites and CMS Provider of Services; this
was verified October 5, 2026. CMS hospital points are distributed by HRSA.
EPA's geospatial terms identify EPA-produced data as public domain by default
unless otherwise specified; selected FRS metadata showed no extra restriction.
Source links and exact acquisition evidence are in the overlay audit. These
site records do not change the excluded licensed AHRF physician fields.

Custom personal pins are user-provided browser data, not distributed source
records or part of this prepared-data catalog.


## TRI reporting-site locations - local addition (October 20, 2026)

The optional 2024 TRI location catalog is prepared from the official EPA
TRI Basic US CSV. Reuse basis, source links, retrieval date, exact source hash
and interpretation limits are in [docs/tri-source-audit.md](docs/tri-source-audit.md).
Attribute EPA TRI; no agency logo, endorsement, exposure measurement or
individual risk estimate is included. This does not change county-data rights
or the treatment of private browser pins. Publication is a separate approval.
