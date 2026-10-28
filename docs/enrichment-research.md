# County data enrichment and combined maps

Research checked September 14, 2026. The user approved implementation. The first data release now includes ACS housing burden and derived commute time plus FEMA NRI inland-flooding, hurricane and tornado building-loss rates. The remaining source candidates below are a roadmap. The selected product remains Night Observatory, with county colors in both national and state views and no ZIP-level drilldown.

## User-selected ingestion order — September 19, 2026

The user selected items 3, 5 and 7 from the remaining-layer shortlist, in this order:

1. **Employment:** BLS county unemployment rate.
2. **Broadband:** FCC reported fixed terrestrial 100/20 Mbps availability.
3. **Additional health measures:** CDC PLACES; choose the specific measures with the user before implementing this layer.

This order supersedes earlier suggested sequencing for remaining data ingestion. Other candidates remain in the backlog. The separately approved hurricane not-applicable correction remains engineering work, not a new ingestion layer. Employment was ingested and browser-verified September 21. Broadband was ingested and browser-verified September24; CDC measure selection remains pending.

## Recommended additions

| Layer | What it helps a mover compare | Proposed first measure | Source / readiness |
| --- | --- | --- | --- |
| Housing pressure | Where rent consumes more household income | Percent of renters spending at least 30% of income on gross rent | [Census ACS 2020–2024](https://www.census.gov/data/developers/data-sets/acs-5year.html); direct county estimates with margins of error |
| Commute | Typical time spent traveling to work | Mean travel time, minutes, excluding people working at home | Same ACS release; initial implementation derives B08013 aggregate minutes / B08303 total workers, with matching universes; no bin-midpoint approximation |
| Employment | Local labor-market conditions | Annual unemployment rate | [BLS LAUS](https://www.bls.gov/lau/tables.htm); county table; retain revisions and the 2025 11-month caveat |
| Healthcare resources | Local primary-care supply | Primary-care physicians per 100,000 residents | [HRSA AHRF](https://data.hrsa.gov/data/download?AHRF=&data=AHRF); deferred: AMA-derived field reproduction requires consent (see source-rights gate below) |
| Hazard-specific loss | Modeled building loss from flooding, hurricane, tornado, wildfire, etc. | Building Expected Annual Loss rate for one selected hazard | [FEMA NRI](https://www.fema.gov/flood-maps/products-tools/national-risk-index); direct county data, hazard-specific vintages |
| Heat | How often a county's climate reaches high temperatures | Mean annual days with county-average daily maximum at least 95°F, 1991–2020 | [NOAA nClimGrid-Daily](https://www.ncei.noaa.gov/products/land-based-station/nclimgrid-daily); derived from supplied county series |
| Air quality | Long-term fine-particle pollution | Annual mean PM2.5, µg/m³ | [EPA/CDC modeled air data](https://www.cdc.gov/environmental-health-tracking/php/data-research/air-quality-outdoor.html); requires audited tract-to-county aggregation |
| Wildfire | Community-scale wildfire exposure beyond declaration history | Raw county Risk to Homes; exact field and units require ingestion verification | [USFS Wildfire Risk to Communities](https://wildfirerisk.org/download/); county downloads; model vintage differs from website version |
| Broadband | Availability for remote work and everyday use | Implemented: percent of residents without reported terrestrial fixed100/20Mbps access, June2024 | [FCC Connect2Health definitions](https://c2h.fcc.gov/bh-data.html); population-based aggregate, availability is not measured performance |
| Public water compliance | Reported regulatory problems | Share of county-associated community systems with a health-based violation | [EPA ECHO](https://echo.epa.gov/tools/data-downloads/sdwa-download-summary); second wave because service areas cross counties |

ACS housing/commute, initial hazard-specific NRI layers and HPSA primary-care shortage are implemented. Follow the user-selected ingestion order above for remaining additions; source-field and reuse audits still apply.

Additional candidates include CDC PLACES prevention/health measures and NHTSA fatal-crash history. Defer FBI crime until agency reporting coverage can be reconciled to counties; defer school-quality comparisons because school districts, county boundaries and state assessments do not form a consistent national measure. Vacancy is useful context but lacks a universal better/worse direction.

The source audits in this folder record release dates, measurement periods, access requirements, coverage and limitations. Some downloads need keys/accounts or source notices; public access does not imply that every underlying licensed input can be redistributed.

## Combined-map proposal

Call it **My priorities — combined comparison**. It summarizes selected measures under a visible recipe. It is not a probability of developing cancer, losing a home, or being safe, and cannot establish that living in a county causes an observed outcome.

### 1. Put comparable inputs on a common scale

For each selected numeric measure, use all available counties in the same national reference universe. Preserve the appropriate sex, age adjustment, denominator, period and source geography. Prefer rates/proportions over raw population-driven totals where that matches the question. FEMA declaration counts remain explicitly administrative counts; dividing them by population would answer a different question.

For the initial higher-is-more-burden measures:

`component = 100 × clamp((raw − L) / (U − L), 0, 1)`

`L` is the actual national minimum. `U` is the actual highest non-extreme county value, using the existing Q3 + 3×IQR high-outlier rule. If IQR is zero, retain the full actual range, as the current app does. A constant measure contributes a neutral 50 and is identified as having no geographic variation. If a selected measure has no usable values anywhere, the recipe cannot produce comparable counties.

Extreme highs retain their raw values and receive a component value of 100 so they cannot stretch everyone else's range. In the combined view, a purple outline or explicit badge identifies an extreme component while the fill still represents the combined value. The current single-measure map keeps its purple fill. The detail panel must also identify which input is extreme; selection styling must not conceal that information.

For higher-is-better resource measures, use the low-tail fence `Q1 − 3×IQR`. Let `L` be the lowest value at or above that fence and `U` the actual maximum. Compute `100 × clamp((U − raw)/(U − L), 0, 1)`. Values below the fence are adverse extremes, capped at 100 and flagged purple. When IQR is zero, use the full range without outlier flags; constants remain neutral 50. The demonstration only contains higher-is-more-burden measures. For a preferred temperature range or other non-monotonic preference, define a visible user-selected target curve first. Do not automatically treat ambiguous quantities, such as vacancy, as good or bad.

This preserves the user's actual-value gradient preference. Percentile ranks are an optional future comparison, not a silent replacement. Min/max normalization makes units comparable but does not give differently shaped distributions equal statistical influence. [JRC's normalization guidance](https://knowledge4policy.ec.europa.eu/composite-indicators/toolkit_en/navigation-page/10-step-guide_en/step-5-normalisation_en) describes these tradeoffs; the exact rule above is our product proposal.

### 2. Apply visible weights

Normalize positive user weights to total 100%. Then:

`combined = Σ(normalized weight × component)`

For example, Fire 40%, male Prostate incidence 30%, Flood 20% and male Lung incidence 10% produces a weighted comparison across those four inputs. Show the raw value, scaled component and weighted contribution for the selected county. A weight of zero excludes that signal, including its missingness.

For the full product, offer category budgets (hazards, health, affordability, access), then divide each budget among its selected measures. This prevents selecting several related health measures from automatically increasing the entire health category's weight. Warn about part/whole overlap such as all-cancer plus prostate, or a FEMA overall index plus its ingredients. Examine correlation as well as meaning; correlation alone does not prove duplication. [JRC's weighting guidance](https://knowledge4policy.ec.europa.eu/composite-indicators/toolkit_en/navigation-page/10-step-guide_en/step-6-weighting_en) explains why indicator counts and correlation affect composite results.

### 3. Preserve missingness and deal-breakers

Default to complete cases: every positively weighted input must be available. Otherwise show a patterned county and name the missing inputs. Never substitute zero or silently redistribute weights separately for each county. All weights off yields no score. Show the number of comparable counties; adding a heavily suppressed cancer cohort can reduce it substantially. Partial-data comparisons, if added later, need a separate explicit mode and cannot be mixed silently with complete cases. [JRC's missing-data guidance](https://knowledge4policy.ec.europa.eu/composite-indicators/toolkit_en/navigation-page/10-step-guide_en/step-3-imputation-missing-data_en) explains the comparability problem.

Keep optional **must avoid / must have** thresholds outside the weighted mean. A user can exclude counties exceeding a chosen raw hazard threshold before comparing the remainder. Missing threshold data is unknown, not a pass. This avoids allowing low rent to compensate for a hazard the user considers unacceptable.

### 4. Color the combined result clearly

Use blue for the actual lowest available combined value and red for the actual highest under the active recipe, with the full gradient between them. Show the actual bounds (which need not be 0 and 100). This is a second display scaling only: the underlying weighted score does not change. Keep that national color scale fixed in state focus. A selected county can be reddest without every component being high.

Changing the recipe changes the score, coverage and color bounds. Therefore colors across two recipes are not directly interchangeable. Show score deltas and unchanged-reference comparisons if a future recipe comparison mode is added. Do not add another outlier-trimming step to the composite; purple identifies extreme source components.

### 5. Make the result reproducible and inspect its stability

Save source IDs/releases, cohorts, periods, geography, bounds, outlier policy, directions, weights and missing-data rules with each recipe. Show component confidence intervals where supplied, but do not manufacture a combined 95% interval by averaging unrelated intervals. Before production, vary weights by ±20%, drop one component at a time and compare reasonable normalization alternatives; identify counties whose apparent advantage is unstable. [JRC's sensitivity guidance](https://knowledge4policy.ec.europa.eu/composite-indicators/toolkit_en/navigation-page/10-step-guide_en/step-8-sensitivity-analysis_en) provides the rationale.

National/state views still show counties. If later adding one summary value per state, use published state statistics or correct additive numerators/denominators; never average county age-adjusted cancer rates, medians or ranks. Summing county disaster declarations also double-counts declarations covering multiple counties.

## Geography and ingestion contract

The atlas uses Census 2021 boundaries, including Connecticut's eight legacy counties. Newer sources can use nine planning regions instead. Do not join these by name or copy values across non-nesting boundaries. Reaggregate lower-level observations where valid; otherwise retain unavailable counties with an explanation. This applies to all sources and to composite coverage.

Each added metric needs a source snapshot/checksum, exact variable definition, explicit zero/missing/suppressed/not-applicable handling, validated county join, finite-value/unit checks, source reconciliation samples, and a live legend/state-view check. Carry sampling/model uncertainty and release metadata alongside values. No ZIP interface is introduced by this roadmap.

## Implementation status and remaining roadmap

The app now includes My priorities with selectable numeric inputs, direct weights, raw hard limits, local recipe save/load and per-county component explanations. The approved first release imports 3,099 housing-burden values, 3,098 derived commute values, 3,099 inland-flooding values, 2,382 hurricane values and 3,099 tornado values into the common 3,107-county universe. Hurricane has 717 source-marked not-applicable counties; meaningful numeric zeros remain available. Eight legacy Connecticut counties cannot be joined to the newer planning regions. Commute is additionally unavailable for Loving County, Texas, because the necessary source estimate is unavailable.

The published S0801 commute endpoint requires a Census API key. Public detailed-table downloads instead provide [aggregate travel minutes B08013](https://api.census.gov/data/2024/acs/acs5/groups/B08013.html) and [commuting-worker totals B08303](https://api.census.gov/data/2024/acs/acs5/groups/B08303.html). Both cover workers aged 16 and over who did not work from home. Their ratio is labeled derived and has no fabricated confidence interval. Housing burden also has no calculated ratio interval in this release. The preparation scripts preserve source checksums and geography metadata.

FEMA's included building-loss rates use total county building value (`BUILDVALUE`) as their denominator, not the narrower hazard-exposed value (`*_EXPB`). Each displayed value equals `*_ALRB × 10000`; every available input reconciles with `*_EALB / BUILDVALUE`. Modeled wildfire is held back because the current source's corresponding identity fails in 50 matched counties. The discrepancy audit remains in the local validation report for source clarification. The historical FEMA Fire declaration layer remains available.

Healthcare supply, heat, air quality, employment, broadband and the other researched sources remain later ingestion tasks. Their presence in this inventory does not mean they are already in the app. Category budgets and statistical sensitivity analysis also remain future enhancements; direct weights and independent hard limits form the initial comparison interface.

The original in-conversation demonstration combines four verified inputs from two source families using real county values: FEMA Fire/Flood declaration measures and NCI/CDC male Prostate/Lung incidence. Related hazard histories can share underlying events or drivers, so separate series are not necessarily independent evidence. It supports weights, county selection, missing patterns and component breakdowns. It does not implement category budgets, hard thresholds, saved recipes or sensitivity analysis. That demonstration remains separate from the app; the imported first-release sources are listed above.

Source uncertainty also limits ordering: two point estimates can differ while remaining indistinguishable within their source uncertainty. The production stability review should include source-supported uncertainty scenarios for ACS margins of error and model standard errors, preserving dependencies where known. It must not treat interval endpoints or independent random draws as a valid joint probability model without justification.

The app refinement delivered with this research keeps wheel zoom on the map SVG in both national and state views. Outside it, wheel input scrolls the page, including over the left controls/legend rail. Mouse dragging and Fit remain available.

### Local weight sensitivity delivered September 15, 2026

The app now provides selected-county baseline/min/max across independent +/-20% positive-weight perturbations with renormalization, fixed source scales and fixed hard limits. Broader rank stability, alternative normalization, source uncertainty and category budgets remain future work. This narrow diagnostic does not implement the full statistical sensitivity roadmap.

Next-source intake: official HRSA AHRF2024-2025 technical documentation identifies `phys_nf_prim_care_pc_exc_rsdt_23` (2023 non-federal primary-care patient-care physicians, excluding hospital residents and ages75+) and matching `popn_est_23`. A per100,000-residents measure is a candidate; it is not imported or approved yet. Audit source rights, missing-value conventions, primary-care definition and geographic joins before ingestion. Official source: https://data.hrsa.gov/topics/health-workforce/nchwa/ahrf . Technical and CSV archives are retained locally under ignored work/healthcare-source-audit/.

AHRF source-rights gate found in the 2024-2025 User Guide (Technical Documentation/AHRF 2024-2025 User Guide.docx, reproduction notice and Primary Care Physicians section): the guide requires Bureau permission for reproduction for reuse/resale and copyright-owner consent for copying AMA/AHA/ADA data. These primary-care fields are explicitly AMA-derived. Do not ship/reproduce this candidate without the required permission; prefer an alternative source with suitable reuse terms. The general download-page availability does not override the archive notice. Primary care includes general/family medicine, general practice, general internal medicine and general pediatrics, excluding subspecialties and physicians75+. Patient care includes office-based and full-time hospital staff. Missing source values must remain missing.

Alternative healthcare source to audit next: HRSA primary-care HPSA component polygons expose status, designation type, county FIPS and HPSA score: https://gisportal.hrsa.gov/server/rest/services/Shortage/HealthProfessionalShortageAreas_FS/MapServer/11 . This is designation-level data with potentially multiple components per county, not a county provider-supply rate. Do not sum repeated designation populations or label a county with no listed designation as having no access problem. Establish a defensible county measure and reuse terms before importing; an empty GIS copyright field alone does not establish permission.

### HPSA primary-care source audit completed September 16, 2026

Audited, not ingested. Reproducible script `scripts/audit-healthcare.py`
(stdlib only, no network). Private result `work/healthcare-hpsa-audit/audit.json`;
rights evidence `work/healthcare-hpsa-audit/source-rights.md`.

The audited file is the tabular HRSA download `BCD_HPSA_FCT_DET_PC.csv`, not
the GIS layer. It is the same designation data with a documented metadata
workbook, so it replaces the REST endpoint as the audit target.
SHA256 `3fa0e75a2a5a3fc68b2d2194cbebf618318ea141a16cc897b64d9c4cc7b50a10`,
extract vintage 09/16/2026, refresh cycle daily.

To reproduce on another machine, fetch the two files into ignored
`work/healthcare-hpsa-audit/` and run the script. The archives are not
committed. HRSA refreshes this extract daily, so a later download will differ
from the SHA256 above; record the new hash and vintage rather than assuming a
match.

```
curl -L -o work/healthcare-hpsa-audit/BCD_HPSA_FCT_DET_PC.csv   https://data.hrsa.gov/DataDownload/DD_Files/BCD_HPSA_FCT_DET_PC.csv
curl -L -o work/healthcare-hpsa-audit/HPSA_DATAMART_METADATA.XLSX   https://data.hrsa.gov/DataDownload/DD_Files/HPSA_DATAMART_METADATA.XLSX
python scripts/audit-healthcare.py
```

Listed on https://data.hrsa.gov/data/download under Shortage Areas,
entry HPSA - Primary Care.

Reuse terms are materially better than AHRF and remain a human decision. The
download page lists HPSA - Primary Care as published by HRSA BHW/DPSD with
"Usage limitations: None". The metadata workbook marks 99 of 100 attributes
`Public`; the single `Restricted` attribute is absent from the 66 CSV columns.
Every organization in the lineage is federal, so no AMA, AHA or ADA licensed
input appears. The 196 MB shapefile archives were not fetched and their
embedded notices are unchecked.

Candidate measure: maximum HPSA score across a county's designated
primary-care components. Higher is worse. Range observed 3 to 25, median 16,
over 2,954 counties. It is an administrative priority score for clinician
placement, not a measured provider supply rate.

Audited facts. 79,750 rows; 20,998 Designated, 48,840 Withdrawn, 9,912
Proposed For Withdrawal. Component types are mostly sub-county: 48,330 census
tract, 18,050 county subdivision, 7,960 unknown, 5,410 single county. 683 of
the 2,954 designated counties carry no whole-county component at all.

Four traps, each verified in the data.

1. `XXXXX` is a literal five-character sentinel in the FIPS column meaning the
   county is not determined; 13 designated rows carry it. A length-five test
   accepts it as a county. Require five digits.
2. Connecticut cannot join. The source uses the nine planning regions
   09110-09190; the atlas uses the eight legacy counties 09001-09015. No code
   is shared, so all eight Connecticut counties read as not designated. That
   is geography vintage, not an absence of designations. No crosswalk is
   applied.
3. `HPSA Component Source Identification Number` is blank on 16,088 of 20,998
   designated rows, so it cannot identify a component. Among rows that carry
   an id there are zero duplicates.
4. 298 of 3,107 atlas counties have no designation. That is `not_designated`.
   It is not missing, not zero and not evidence of adequate access.

Never sum `HPSA Designation Population` across a county; it repeats on every
component row of the same HPSA. Never derive a provider-supply rate from this
file.

Open before any ingestion: whether a max score over mostly sub-county
components is defensible at county level; whether Proposed For Withdrawal
rows belong in the subset; a Connecticut decision; and human confirmation of
reuse terms. The metadata workbook does not document `HPSA Designation
Population`, `HPSA FTE`, `HPSA Shortage`, `HPSA Component Type Description`
or `Withdrawn Date`.


### HPSA decisions, all four SETTLED by the user (September 17, 2026)

The audit is complete and these four were the only things between it and a
prepared layer. Each was recommended as the conservative reading of the audited
evidence, and the user accepted all four as written. None is a legal clearance.
They are now the specification for `scripts/prepare-healthcare.py`; do not
re-open them.

1. REUSE TERMS. DECIDED: proceed, with the caveat recorded. Every organization
   in the lineage is federal, the service metadata is marked `Public`, and no
   AMA, AHA or ADA licensed input appears, which is the specific problem that
   blocked AHRF. The 196 MB shapefile archives were not fetched, so their
   embedded notices are unchecked; the tabular download is the thing being
   used, so that gap does not block the tabular layer. This is a human call.

2. MAX SCORE AT COUNTY LEVEL. DECIDED: publish it, labelled for what it is,
   carrying the component basis alongside. 683 of 2,954 designated
   counties have only sub-county components, so for those the county figure
   describes a part of the county, not the county. That is defensible when
   stated and misleading when not. Recommend a per-county field recording
   whether the score came from a whole-county component, and saying so in the
   county detail. The measure is an administrative priority score for clinician
   placement, never a provider supply rate, and the layer title should say so.

3. CONNECTICUT. DECIDED: `unavailable` with an explicit reason, not
   `not_designated`. The source uses planning regions 09110-09190 and the atlas
   uses legacy counties 09001-09015; no code is shared. Reading eight counties
   as not designated would state something the source never said. This matches
   how the eight legacy Connecticut counties are already handled elsewhere in
   the atlas. Do not invent a crosswalk.

4. PROPOSED FOR WITHDRAWAL. DECIDED: exclude them from the designated
   subset and count them separately. 9,912 rows carry that status. A
   proposal to withdraw is a statement that the designation may no longer hold,
   so including it would overstate shortage. Excluding it silently would
   understate it, which is why the count should be kept and reported rather
   than dropped.

Expected output of the prepared layer, computed independently from the CSV on
September 17, 2026 and used to grade the prepare script rather than trust it.
3,107 emitted records: 2,809 available, 290 `not_designated`, 8 Connecticut
`unavailable`. Of the 2,809 scored, 2,162 have a whole-county component and 647
are sub-county only. Emitted county values range 3 to 25, although individual
designated rows go as low as 0, so the county maximum never falls below 3.
Source rows 79,750: 20,998 designated, 48,840 withdrawn, 9,912 proposed for
withdrawal, spread over 702 counties. 923 rows carry an unusable FIPS, 13 of
them the literal XXXXX on a designated row. The source names 3,224 counties, of
which 186 are outside the atlas, and 9 Connecticut planning regions that join
to nothing.

The earlier figure of 683 sub-county-only counties counted all 2,954 designated
counties. Against the 2,809 that are actually in the atlas and not Connecticut,
the figure is 647. Both are correct; the layer shows the second.

Whatever is decided, `not_designated` must stay distinct from missing. 298 of
3,107 atlas counties have no designation, and that is not evidence of adequate
access.

### September19 healthcare integration

The prepared HPSA layer is connected to the app's lazy-loaded map and recipe builder. Source records, source-rights caveat, and all four settled decisions remain unchanged. Non-designated counties use a distinct neutral slate category and remain unscored in My priorities; this is not evidence of adequate access. Missing Connecticut geography remains separately unavailable. Tests pass; browser visual acceptance is pending a working browser connection. Offline synthesis inclusion is not part of this change.

September19 follow-up: Edge connection recovered; core national/state/detail/composite and desktop/narrow-screen visual checks passed (see README).

### September 21 employment integration

The verified BLS LAUS 2025 workbook now supplies the Unemployment family and optional My priorities input. Published rates are used directly, with labor-force/employed/unemployed counts as context. Coverage is 3,099/3,107; eight legacy Connecticut counties remain unavailable with an explicit planning-region explanation. The 11-month average excludes October 2025; do not infer full-year trend comparability, job vacancies, wages or personal employment odds. Actual national rates span 0.7–18.9%; the existing outlier rule gives blue-red 0.7–8.6 and 27 purple extremes. State focus retains that national scale. Source audit and provenance: [employment-source-audit.md](employment-source-audit.md). Standalone and composite browser checks, saved-recipe restoration and narrow layout passed. Offline normalization/database/ranking still use the earlier four families; extension is separate work.

### September 24 broadband integration

FCC Connect2Health county population access aggregates now supply Broadband and an optional My priorities input. June2024 is the measurement period;2025 is the platform release. Derived gap =100 minus reported fixed terrestrial100/20Mbps access, excluding satellite. Raw access remains visible. All3,107 counties are available;113 genuine zero gaps and one100%gap. National ordinary range0–72.6 with40 purple extremes above73; state scale stays fixed. The default comparison retains2,570 eligible counties with broadband added. Source audit, verification and narrow-screen limitations: [broadband-source-audit.md](broadband-source-audit.md). Next: obtain owner selection of CDC PLACES measures before ingestion. No offline database/ranking extension is implied.


## October 5 location-overlay implementation

The local first pass adds independently selectable EIA plant/storage, HRSA
service-site/hospital, EPA air/water/Superfund, NHTSA 2023 fatal-crash and
USGS 2025 M3+ earthquake catalogs,
plus browser-private custom pins. See [source audit and deferred categories](overlay-source-audit.md).
These are context markers, not additional scoring inputs. Related-place tags
are suggestions, not measured correlations. EPA acquisition recovered through
complete object-ID range queries; no partial layer is included. HRSA reuse
limitations were resolved through its official metadata page. No facility proxies are invented for rent,
unemployment or broadband. Publication is not authorized by this local task.


## October 20 TRI reporting-site addition (local, unpublished)

Dave selected TRI next. The independent 2024 reporting-facility catalog
contains 21,265 locations in the existing 48-state map; DC and territories
are excluded consistently with its geometry. It collapses chemical reporting
forms by TRI facility ID, retaining industry/Form R/Form A same-row filters.
Form A does not mean zero releases. Reporting is not an exposure, compliance,
current-operation or personal-risk determination; unweighted pounds and grams
are not summed into a score. Existing county measures and priorities remain
unchanged.

See [tri-source-audit.md](tri-source-audit.md) for original source bytes/hash,
processing-date caveats, reconciled counts and rebuild/registration commands.
Firecrawl is the documented backup for retrieving official source pages when
primary retrieval fails; original data files still come directly from EPA.
NOAA storms, wildfire incident points, air monitors and climate stations
remain future point candidates, separate from already shipped county layers.
