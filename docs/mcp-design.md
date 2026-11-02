# Should I Live Here? MCP server - design (v2)

Status: draft for owner review, November 2, 2026. No code yet.

## Objective

Let people ask an AI app questions about the atlas data, for example:

> Use the SILH MCP to find the top 5 places to live based on internet
> access, low cancer rates, low crime, good schools and low cost of living.

The AI app calls the MCP server. The server answers with county values,
ranks, sources and cautions from the atlas. It never invents a value.

## Non-goals

- No new datasets in this version. Schools and a true cost-of-living index
  are not in the atlas. The server says so and logs the request.
- No accounts, sign-in, payments or write access to atlas data.
- No ZIP-code, city or neighborhood answers. County level only.
- No advice. The server returns data. The site rule stays true: the values
  do not tell you where to live.

## Hosting

- A second Cloudflare Worker, `silh-mcp`, separate from the static site.
  The site stays static, and its tests stay unchanged.
- Address: `https://mcp.shouldilivehere.org/mcp` (Streamable HTTP, no sign-in).
- Code: `mcp/` folder in this repo, with its own `wrangler.jsonc` and
  `package.json`.
- Built with `createMcpHandler` from the Cloudflare Agents SDK and
  `@modelcontextprotocol/server` (stateless: no sessions, no Durable Objects).
- The account is on Workers Paid ($5 a month, already in place; renews
  December 1, 2026). One ranking takes about 25 ms of CPU, over the free
  plan's 10 ms but far under the paid default. `limits.cpu_ms` is set to
  1000 so a runaway request cannot run up cost.
- Deploys through Workers Builds on a push to `master`, like the site.

## Data design

The site reads 74 JSON layer files (25.7 MB). Parsing them per request would
exceed 10 ms. So a build script packs the data once:

- `scripts/build-mcp-data.py` reads `dist/data/layers/*.json` and the county
  list, and writes `mcp/src/data/`:
  - `counties.json`: FIPS, name, state for 3,107 counties.
  - `measures.json`: per measure: id, family, title, unit, period, direction,
    source URL, citation, caution note.
  - `values.bin`: one Float64 (little-endian) array per measure, 3,107 values, county order
    fixed. Missing or suppressed = NaN. A status code array keeps
    "unavailable", "suppressed" and "not applicable" apart (never zero).
- 73 measures in 15 families x 3,107 counties x 8 bytes = about 1.8 MB.
  64-bit values keep the exact layer values, so near-ties rank as on the site.
- Ranking calls the site's `dist/composite.js` unchanged, so the MCP and the
  site's **My priorities** give the same order for the same recipe.
- A test fails if the packed data and the layer files disagree.

## Tools

All tools are read-only. Every answer includes the source, the period and
the caution notes for each measure it used.

1. `list_measures` - families and measures, with units, periods and direction
   (lower is better or higher is better). Optional text filter.
2. `find_measure` - maps plain words to measures, for example "internet" to
   `broadband/without-100-20`, "cost of living" to median rent and median
   home value. Unmatched words come back in `not_available`, and are logged.
3. `get_county` - all values for one county, by FIPS or "Name, State".
4. `compare_counties` - 2 to 10 counties side by side on chosen measures.
5. `rank_counties` - the core tool. Inputs: measures with weights, optional
   limits (for example "unemployment under 5%"), optional state filter,
   count (default 10, max 25). Output per county: rank, score 0-100, each
   measure value and its national percentile, and the counties left out
   because a value was missing.
6. `request_measure` - the AI app can report a measure the user wanted that
   the atlas lacks, for example "schools". Logged like unmatched words.

## Answering the example query

| Asked for | Atlas measure | Notes |
| --- | --- | --- |
| Internet availability | Residents without 100/20 Mbps access | lower is better |
| Lowest cancer rates | All cancer sites incidence | lower is better |
| Lowest crime | Violent crime, property crime | 2,195 of 3,107 counties; FBI advises against ranking |
| Best schools | none | `not_available`, logged |
| Cost of living | Median gross rent, median home value | proxy only, said so |

## Cautions the server must return

- County values describe groups of residents. They are not personal risk.
- A county with a missing value is left out of a ranking, never scored as
  low. The answer lists how many counties were left out and why.
- When a ranking uses crime: "The FBI advises against ranking places with
  these data." Crime covers 2,195 of 3,107 counties.
- When rent or home value stands in for cost of living: "This is a proxy.
  It is not a full cost-of-living index."
- Every answer ends with the site link, so people can check the values.

## Request log (missing measures)

- Purpose: learn which data layers people ask for that the atlas lacks.
- Storage: Cloudflare D1 (free plan: 100,000 row writes a day; over that,
  logging fails quietly and the answer still returns).
- Stored per row: the requested term (lowercase, max 60 characters), the
  date (day only) and a count. Nothing else.
- Not stored: the user's prompt, IP address, user agent, or any identifier.
  The MCP server never sees the prompt; it sees only tool inputs.
- The site's privacy note and the server's tool descriptions say that
  missing-measure requests are counted.
- The owner reads the counts with a small script or the Cloudflare
  dashboard. A public `request_counts` tool is not planned.

## Abuse and cost controls

- Runs on the existing Workers Paid plan. No new paid service.
- Inputs are validated (lengths, counts, known measure ids).
- `rank_counties` count max 25; `compare_counties` max 10 counties.
- A test fails if one ranking takes over 60 ms on the dev machine.

## Acceptance criteria

1. `list_measures` returns all measures in the manifest, with no extras.
2. `rank_counties` with one measure matches a plain sort of the layer file.
3. `rank_counties` with several weights matches `composite.js` on the same
   recipe for the first 25 counties.
4. Missing values never rank; the left-out count is exact.
5. "schools" comes back as `not_available` and adds one log row.
6. Crime rankings carry the FBI caution. Rent proxies carry the proxy caution.
7. The example query returns 5 counties, the cautions, and the schools gap.
8. Works from Claude Code (`claude mcp add --transport http ...`) and the
   MCP Inspector against the deployed URL.
9. Site tests still pass; the site Worker is unchanged.

## Work split (one Fireworks worker per file)

Claude writes the requirements and the acceptance tests first. Each worker
writes one file, and does not edit tests.

1. `scripts/build-mcp-data.py` - pack the data.
2. `mcp/src/data.js` - load packed data, lookups, measure matching.
3. `mcp/src/rank.js` - ranking on packed data with `composite.js` rules.
4. `mcp/src/server.js` - tool definitions and answer text.
5. `mcp/src/log.js` - D1 request counts.
Claude integrates, runs the tests, deploys, and checks the live server.

## Owner steps

- Approve this design.
- Approve the D1 database and the `mcp.shouldilivehere.org` custom domain
  (both free; Claude can create them now that the connector can write).
- Connect the `mcp/` folder to Workers Builds, or approve Claude doing it.
- Approve the privacy note change on the site.
