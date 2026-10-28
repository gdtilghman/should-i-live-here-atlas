# TRI reporting-facility overlay - October 20, 2026

Local addition; not deployed. Dave chose TRI as the next Related Places
category. This is an independent point catalog over any heatmap, not a new
county risk measure or priority input.

## Source and meaning

Official [EPA TRI Basic Data Files](https://www.epa.gov/toxics-release-inventory-tri-program/tri-basic-data-files-calendar-years-1987-present)
link the [2024 US CSV](https://data.epa.gov/efservice/downloads/tri/mv_tri_basic_download/2024_US/csv).
Original bytes were acquired directly from that URL on October 20, 2026,
HTTP 200; 60,550,684 bytes. SHA-256:

    06dfa3a67bb4c5bd38d9e9f0f7b8bff10b95254a63169423632d7f6f251e1506

The retrieved page lists reporting forms processed through November 5, 2025
and was last updated January 28, 2026. Retrieval time is not reporting year,
processing date or proof of current operation. These are the actual acquired
2024 bytes, not a claim that 2024 is the latest possible TRI reporting year.
EPA permits revisions; a changed file needs a new hash and reviewed counts.

TRI covers specified chemicals, industry sectors and reporting thresholds;
it does not inventory every facility or pollution source. A reporting site
may report recycling/treatment or submit a Form A certification. Its presence
does not establish a release, violation, measured exposure, causation or
individual health risk. Absence of a point does not mean absence of pollution.
See [EPA's program explanation](https://www.epa.gov/toxics-release-inventory-tri-program/what-toxics-release-inventory)
and [interpretation guide](https://www.epa.gov/toxics-release-inventory-tri-program/factors-consider-when-using-toxics-release-inventory-data).

## Scope and reconciliation

| Invariant | Original annual snapshot |
| --- | ---: |
| Chemical reporting-form rows | 77,295 |
| Distinct national TRI facility IDs | 21,482 |
| Lower-48 mapped facility IDs | 21,265 |
| Forms belonging to mapped facilities | 76,349 |
| Excluded out-of-scope facilities | 217 |
| Forms belonging to those excluded facilities | 946 |
| Form R rows nationally | 68,567 |
| Form A rows nationally | 8,728 |
| Conflicting within-facility location records | 0 |
| Missing/invalid lower-48 coordinates | 0 |

All 122-column rows have reporting year 2024. Each document-control number is
unique. Chemical rows collapse by TRIFD, never by a name/address or FRS ID.
A TRIFD is a stable string, not a number. The source state maps to the existing
48-state FIPS scope (DC has no feature in this atlas). Coordinates are original facility coordinates rounded
to six decimals, checked for finite values and lower-48 bounds; no centroids,
geocoding, distance buffers or coordinate imputation. All datum cells are
blank in this source; the UI says datum not supplied. No survey precision or
verified datum transformation is implied.

Each marker preserves unique same-row industry/form combinations. Users can
filter industry and Form R/Form A separately; one facility can have both.
Zero-release Form R reporters and Form A certifications remain included.
Form A is not coerced to zero. The marker count is facilities, not chemical
forms, toxicity or release severity. Reporting-form counts appear only as
context in details. Chemical quantities are deliberately not summed:
the CSV mixes pounds and grams, and unweighted mass is not health risk.

Public points contain facility name, TRIFD, state, coordinates, reporting
year, industry/form groups and interpretation notes. Street addresses,
parent-company information, document-control IDs and individual records
are not published. No source API is called by visitors. The existing
catalog handles lazy loading, clustering, searchable keyboard list, state
focus and coexistence with browser-local personal pins.

## Retrieval fallback

Primary web opens of the exact EPA download and reuse-policy pages returned
502. Connected Firecrawl MCP live scrapes (maxAge 0) returned HTTP 200,
one credit each; the source-page scrape exposed the official CSV link.
Source bytes then came directly from EPA. Saved original bytes, HTTP
metadata, page text/links and Firecrawl receipts are ignored under
work/tri-source-oct20/. No broad crawl, browser actions, credentials,
new API key, app dependency or visitor-side Firecrawl request was added.

HTML/markdown recovered by Firecrawl can document source semantics and
links, but cannot substitute for original dataset bytes or completeness
checks. Access denials are not bypassed.

## Rebuild and reuse

The new importer verifies the exact source checksum before parsing and
fails closed on malformed schema/rows, wrong year, duplicate report identity
or conflicting facility identity/coordinates. Output is replaced atomically
after validation; a failed run leaves existing output unchanged.

    python scripts/prepare-tri.py --source work/tri-source-oct20/tri-2024-us.download --year 2024 --retrieved 2026-10-20 --sha256 06dfa3a67bb4c5bd38d9e9f0f7b8bff10b95254a63169423632d7f6f251e1506 --output dist/data/overlays/tri.json
    node scripts/register-tri.cjs dist/data/overlays/catalog.json dist/data/overlays/tri.json
    python scripts/test-tri.py
    node --test scripts/test-overlays.cjs scripts/test-tri.cjs
    python scripts/validate-atlas.py

This dedicated importer does not regenerate or redate the original six
catalog shards. The registration command above inserts/replaces only the
tri entry, preserving all older entry metadata and the catalog's original
retrieval field. It is idempotent and validates provenance/year before
replacing the catalog. Run it after any older prepare-overlays.py rebuild
to restore the combined seven-source catalog. Each entry retains its own
period and retrieval date; do not label old bytes as freshly retrieved.

EPA's [geospatial reuse terms](https://www.epa.gov/web-policies-and-procedures/epa-disclaimers)
default EPA-produced geospatial data to public domain unless otherwise
specified. The source page did not list an additional restriction for the
selected data. Attribute EPA TRI and the reporting/retrieval dates; no logo,
agency endorsement or warranty is implied. This audit concerns the prepared
facility-location data, not a blanket license for every linked document or
third-party content. Publication still needs Dave's approval.

## Acceptance evidence

Fresh October 20 checks: 133 Node application tests passed, one unchanged
NOAA source-cache skip; 35 Python importer tests passed; atlas validation,
syntax and whitespace checks passed. A separate parser reconciled every
mapped ID/name/FIPS/coordinate/industry-form group and reporting-form count.
All six prior shard bytes and older catalog metadata were unchanged.

Sixteen rendered checks passed across desktop 1440px and mobile-emulated
390/320px: optional lazy loading, counts, industry/form filters, source
details, state focus, all heatmap families, Fit, separate personal pins and
isolated load failure. Normal runs had no page errors, HTTP failures or
external requests. Desktop/narrow screenshots were inspected.

A separate Fireworks evaluator reconciled the raw CSV and public points and
ran 14 adversarial probes. Scores: data/provenance 9.3, fail-closed/preservation
9.4, privacy/interpretation 9.4, reproducibility/integration 9.2; no blocking
finding. Nonblocking limits: the generic detail uses annual Record date:
2024; CSV error numbers count records rather than physical lines inside
quoted fields; registration checks digest syntax while the importer and
snapshot test verify actual source identity. Runtime/UI checks were supplied
by the orchestrator, not inferred from that source review.

Physical iPhone/Safari testing
remains separate from Chromium emulation.
