# Should I Live Here?

Should I Live Here? is a free, interactive data atlas of United States counties.
It shows public federal data on a county map. You can compare health, hazards,
housing, jobs, internet access, air, water and road safety. You can also weight
the measures that matter to you and see a combined score.

The atlas covers 3,107 counties in the lower 48 states. Alaska, Hawaii and
the territories are not included. The atlas works
at county level only. It has no ZIP-code or neighborhood data.

**Example site:** https://shouldilivehere.org/

<!-- TODO (owner): add a screenshot, for example docs/screenshot.png, and link it here. -->

## What you can do

- Pick a measure and see it on the national map. Colors use a fixed national
  scale, so a state view keeps the same colors.
- Click or tap a county to open its state view and its details.
- Zoom with the mouse wheel, a pinch, or the zoom buttons. Pan with a drag, or
  focus the map and use the arrow keys.
- Use **My priorities** to choose measures, set weights and limits, and save
  the recipe in your browser.
- Turn on **Related Places** to show point locations over any map, such as
  hospitals or power plants. **Browse places** gives a searchable list.
- Use **Add a pin** to mark your own places. Pins stay in your browser only.
  The site does not send them anywhere.
- Use the **Night view** button to switch from the default light "Weather
  Desk" look to a dark look. The site remembers your choice.

## Data

The atlas has 66 county datasets in 13 families. Each layer shows its source,
period and cautions in the app. [LICENSE-DATA.md](LICENSE-DATA.md) lists the
full terms for each source. The `docs/*-source-audit.md` files record how each
source was checked.

| Family | Datasets | Source |
| --- | --- | --- |
| Cancer | 11 | NCI and CDC State Cancer Profiles, 2018-2022 incidence, with five-year trends |
| Disaster declarations | 17 | FEMA OpenFEMA Disaster Declarations Summaries v2, 2000-2025 |
| Modeled hazard loss | 10 | FEMA National Risk Index v1.20 |
| Housing and commute | 4 | US Census Bureau American Community Survey, 2020-2024 |
| Primary care shortage | 1 | HRSA Health Professional Shortage Areas |
| Unemployment | 1 | BLS Local Area Unemployment Statistics, 2025 |
| Broadband access gap | 1 | FCC Connect2Health, Broadband Data Collection |
| Adult health | 15 | CDC PLACES, 2024 release (2022 BRFSS data) |
| Air quality (PM2.5) | 1 | CDC Tracking Network, EPA Downscaler model, 2020-2022 |
| Wildfire | 2 | USDA Forest Service, Wildfire Risk to Communities (2nd edition) |
| Drinking water | 1 | EPA ECHO SDWA data (SDWIS), 2023-2025 violations |
| Traffic deaths | 1 | NHTSA FARS 2019-2023, with ACS population |
| Heat (days at or above 95°F) | 1 | NOAA NCEI nClimGrid-Daily v1.0.0, 1991-2020 |

County boundaries come from the US Census Bureau TIGER/Line 2021 county file,
simplified with Mapshaper.

### Related Places

Seven point catalogs can show over any map. The overlay source audit
([docs/overlay-source-audit.md](docs/overlay-source-audit.md)) and the TRI audit
([docs/tri-source-audit.md](docs/tri-source-audit.md)) give the details.

| Catalog | Source | Period |
| --- | --- | --- |
| Power plants and storage | US EIA-860M | August 2026 preliminary inventory |
| Health-center service sites | HRSA | Directory snapshot, October 5, 2026 |
| Hospitals and critical-access hospitals | CMS Provider of Services, through HRSA | Snapshot, October 5, 2026 |
| EPA air, water and Superfund facilities | EPA Facility Registry Service | Snapshot, October 5, 2026 |
| TRI reporting facilities | EPA Toxics Release Inventory | 2024 reporting year |
| Fatal road crashes | NHTSA FARS final file | 2023 |
| Earthquakes M3+ | USGS earthquake catalog | 2025 |

A point shows a location only. It does not show exposure, emissions, risk or
quality. The atlas does not infer a cause or a correlation from points that
overlap a county color.

### Required notices and credits

FEMA requires this statement:

> This product uses the Federal Emergency Management Agency’s OpenFEMA API, but is not endorsed by FEMA. The Federal Government or FEMA cannot vouch for the data or analyses derived from these data after the data have been retrieved from the Agency's website(s).

Citation:

> Federal Emergency Management Agency (FEMA), OpenFEMA Dataset: Disaster Declarations Summaries - v2. Retrieved from https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries on September 14, 2026.

The app shows this notice with every disaster layer. This product uses no
FEMA or Department of Homeland Security logo or seal.

Other credits:

- NOAA NCEI nClimGrid-Daily v1.0.0. This atlas does not imply NOAA
  endorsement.
- CDC PLACES and the CDC National Environmental Public Health Tracking
  Network. No CDC endorsement of these interpretations is implied.
- BLS Local Area Unemployment Statistics. No BLS endorsement is implied.
- EPA ECHO/SDWIS, EPA Facility Registry Service and EPA TRI. No EPA
  endorsement is implied.
- NCI and CDC State Cancer Profiles; US Census Bureau; HRSA; CMS; FCC; NHTSA;
  USGS; US EIA; USDA Forest Service, Wildfire Risk to Communities.

No agency logo is used. When you reuse a measurement, cite its upstream source
as well as this project.

## Important cautions

- **This is not advice.** The atlas does not give medical, financial, legal or
  safety advice. Do not make a decision from this map alone.
- **The data describe the past.** Most values are averages over past years.
  They do not predict the future.
- **County values are not personal values.** A county rate describes a group
  of people. It does not give your personal risk. It does not show that a
  place causes an outcome.
- **Missing is not zero.** Suppressed, excluded or unavailable values stay
  empty. The app shows them apart from a true zero.
- **Some counties have gaps.** For example, eight legacy Connecticut counties
  have no value in several layers, because the sources now report Connecticut
  planning regions.
- **Some sources warn against ranking.** The CDC advises against ranking
  counties with PLACES data. My priorities lets you choose your own inputs;
  read the cautions in the app before you compare.

## Run it locally

You need Python 3 and Node.js.

1. Clone the repository.
2. Run `python scripts/serve.py`.
3. Open `http://127.0.0.1:4173`.

The site is static. Everything it serves is in `dist/`. The browser does not
call any source-data API.

Run the tests:

```sh
node --test scripts/test-*.cjs
python scripts/validate-atlas.py
```

Some families also have Python tests, for example
`python scripts/test-water.py`.

## Rebuild the data

Raw downloads go in the git-ignored `work/` folder. The repository does not
include them. Each family has a prepare script in `scripts/`, for example:

```sh
python scripts/prepare-cancer.py --source-dir <folder-with-the-csv-exports>
python scripts/prepare-disasters.py
python scripts/prepare-heat.py --fetch
python scripts/prepare-tri.py
```

Then rebuild the files that the app loads:

```sh
python scripts/build-shards.py
python scripts/build-geometry.py
```

Each source audit in `docs/` gives the download location, file checks and the
commands for that source. Read [LICENSE-DATA.md](LICENSE-DATA.md) before you
add a new source.

A planned employment refresh uses a free BLS API key. Copy `.env.example` to `.env`
and add your own key. Never commit `.env`.

## Hosting

The example site runs as static files on Cloudflare Workers. `wrangler.jsonc`
serves only `dist/`. Any static host can serve `dist/`.

## License

- Software: [Apache License 2.0](LICENSE).
- Prepared data in `dist/data/`: [CC BY 4.0](LICENSE-DATA.md). Credit the
  upstream sources too.
- `dist/vendor/d3.min.js`: D3 7.9.0, ISC license.
- `dist/vendor/fonts/`: Public Sans and Atkinson Hyperlegible Next, SIL Open
  Font License 1.1.

See [NOTICE](NOTICE) for the full attribution.

## Contributing

Issues and pull requests are welcome. The owner reviews and merges every
change. Read [CONTRIBUTING.md](CONTRIBUTING.md) first. In short:

- Use public sources only, and check their reuse terms first.
- Keep missing values apart from zero.
- Add or update the tests, and run the test commands above.
- Use plain, short sentences in text that users see.

## Support

This project is free to use, with no ads. Donations keep the example site
running and pay for data updates.

Give on [Ko-fi](https://ko-fi.com/gdtilghman), one time or monthly.
