'use strict';
// Proves the SQL ranking agrees with the browser, county for county.
//
// This is the guard on the project's endgame. A map that colours a county
// wrongly is a visible mistake. A ranked list that quietly scores a county on
// partial data, or drops one it should have kept, looks exactly like a correct
// answer. The two implementations must not be allowed to drift.
//
// The most dangerous specific failure is that SQL makes "missing" and "zero"
// easy to confuse: a county with no reading simply does not join, and a naive
// query then either omits it silently or sums it as zero and ranks it first or
// last. The second test below is that case, stated directly.
//
// Run scripts/build-database.py and scripts/rank-counties.py first; both
// outputs live in the ignored work/ directory.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const dataDir = path.join(root, 'dist', 'data');
const rankingPath = path.join(root, 'work', 'ranking.json');
const hurricanePath = path.join(root, 'work', 'ranking-hurricane.json');
const composite = require(path.join(root, 'dist', 'composite.js'));

const skip = fs.existsSync(rankingPath) && fs.existsSync(hurricanePath)
  ? false
  : 'run scripts/build-database.py then scripts/rank-counties.py first';

const readJson = (file) => JSON.parse(fs.readFileSync(file, 'utf8'));

// Summing in a different order gives a different last bit or two. SQL groups
// rows in whatever order it likes; the browser adds them in recipe order. This
// tolerance allows that and nothing else: a single misweighted or wrongly
// included input moves a score by far more.
const TOLERANCE = 1e-9;

function browserResult(recipe, { withoutDeclaredBestCase = false } = {}) {
  const geo = readJson(path.join(dataDir, 'counties.geojson'));
  const countyIds = geo.features.map((feature) => feature.properties.fips);
  const byKey = new Map();
  for (const family of ['cancer', 'disasters', 'community', 'hazards', 'healthcare', 'employment', 'broadband', 'places', 'air', 'wildfire', 'water', 'traffic', 'climate', 'storms', 'crime']) {
    for (const dataset of readJson(path.join(dataDir, `${family}.json`)).datasets) {
      if (withoutDeclaredBestCase) delete dataset.notApplicableMeans;
      byKey.set(`${family}:${dataset.id}`, dataset);
    }
  }
  const signals = recipe.map((item) => {
    const dataset = byKey.get(item.key);
    assert.ok(dataset, `${item.key} is not in the source data`);
    return { key: item.key, dataset, weight: item.weight, threshold: null };
  });
  return composite.combine(countyIds, signals);
}

// The default recipe has no hurricane input. The second recipe does, so the
// declared best case for hurricane not-applicable is compared with the browser
// county for county too.
for (const [name, file, expected] of [
  ['default recipe', rankingPath, 2570],
  ['hurricane recipe', hurricanePath, 3099],
]) {
  test(`${name}: SQL ranks exactly the counties the browser can score`, { skip }, () => {
    const ranking = readJson(file);
    const result = browserResult(ranking.recipe);

    const fromBrowser = new Set(
      Object.entries(result.records)
        .filter(([, record]) => record.status === 'available')
        .map(([fips]) => fips),
    );
    const fromSql = new Set(ranking.ranked.map((row) => row.fips));

    const onlySql = [...fromSql].filter((fips) => !fromBrowser.has(fips));
    const onlyBrowser = [...fromBrowser].filter((fips) => !fromSql.has(fips));

    assert.deepStrictEqual(onlySql.slice(0, 10), [],
      `${onlySql.length} counties ranked by SQL that the browser excludes`);
    assert.deepStrictEqual(onlyBrowser.slice(0, 10), [],
      `${onlyBrowser.length} counties the browser scores that SQL drops`);
    assert.strictEqual(fromSql.size, expected,
      `expected ${expected} comparable counties, got ${fromSql.size}`);
  });

  test(`${name}: every SQL score matches the browser score`, { skip }, () => {
    const ranking = readJson(file);
    const result = browserResult(ranking.recipe);
    let worst = 0;
    let worstFips = null;

    for (const row of ranking.ranked) {
      const record = result.records[row.fips];
      assert.ok(record, `${row.fips} is missing from the browser result`);
      const difference = Math.abs(record.value - row.score);
      if (difference > worst) {
        worst = difference;
        worstFips = row.fips;
      }
    }
    assert.ok(worst < TOLERANCE,
      `worst score difference ${worst} at ${worstFips} exceeds ${TOLERANCE}`);
  });

  test(`${name}: a county missing one input is excluded, never scored zero`, { skip }, () => {
    // The failure this whole file exists to catch. If SQL scored a missing
    // reading as zero, the county would still appear, and on a scale where low
    // means least adverse it would rank at or near the top.
    const ranking = readJson(file);
    const result = browserResult(ranking.recipe);
    const ranked = new Set(ranking.ranked.map((row) => row.fips));

    const missingSomething = Object.entries(result.records)
      .filter(([, record]) => record.status === 'unavailable'
        && /Missing selected data/.test(record.reason || ''));
    assert.ok(missingSomething.length > 0,
      'no county is missing an input, so this test proves nothing');

    for (const [fips] of missingSomething) {
      assert.ok(!ranked.has(fips),
        `${fips} is missing a selected input but SQL still ranked it`);
    }

    // And nothing scored exactly zero, which is what a summed-null county would
    // look like on this scale.
    const zeros = ranking.ranked.filter((row) => row.score === 0);
    assert.deepStrictEqual(zeros, [],
      `${zeros.length} counties scored exactly 0, the signature of summed nulls`);
  });
}

test('the browser ranks counties in the same order as SQL', { skip }, () => {
  // The ranked list a visitor sees comes from rank() in dist/composite.js.
  // SQL is the future server path. Where scores differ by more than the
  // summation-order tolerance, the two orders must agree county for county.
  for (const file of [rankingPath, hurricanePath]) {
    const ranking = readJson(file);
    const result = browserResult(ranking.recipe);
    const browser = composite.rank(result.records, Object.keys(result.records));
    const sql = [...ranking.ranked].sort((a, b) => a.score - b.score);
    assert.strictEqual(browser.length, sql.length, `${path.basename(file)}: ranked counts differ`);
    for (let i = 0; i < sql.length; i++) {
      if (browser[i].fips === sql[i].fips) continue;
      assert.ok(Math.abs(browser[i].score - sql[i].score) < TOLERANCE,
        `${path.basename(file)} rank ${i + 1}: browser ${browser[i].fips}, SQL ${sql[i].fips}, and their scores are not tied`);
    }
  }
});

test('inland counties are ranked on hurricane risk, not dropped', { skip }, () => {
  // Hurricane not-applicable means no exposure, and the dataset declares it a
  // best case. Before that declaration the same recipe dropped all 717 inland
  // counties, so a person avoiding hurricanes lost the safest places.
  const ranking = readJson(hurricanePath);
  const ranked = new Map(ranking.ranked.map((row) => [row.fips, row]));
  const before = browserResult(ranking.recipe, { withoutDeclaredBestCase: true });
  const after = browserResult(ranking.recipe);
  const scored = (result) => Object.entries(result.records)
    .filter(([, record]) => record.status === 'available').map(([fips]) => fips);
  const beforeSet = new Set(scored(before));
  const gained = scored(after).filter((fips) => !beforeSet.has(fips));

  assert.strictEqual(beforeSet.size, 2382, `without the rule, expected 2,382, got ${beforeSet.size}`);
  assert.strictEqual(gained.length, 717, `expected 717 inland counties gained, got ${gained.length}`);
  for (const fips of gained) {
    assert.ok(ranked.has(fips), `${fips} has no hurricane exposure but SQL dropped it`);
    const hurricane = after.records[fips].components.find((c) => c.key === 'hazards:nri-hurricane');
    assert.strictEqual(hurricane.status, 'not-applicable');
    assert.strictEqual(hurricane.scaled, 0, `${fips} hurricane scored ${hurricane.scaled}, not the best case`);
    assert.strictEqual(hurricane.value, null, `${fips} invented a hurricane measurement`);
  }
  // The rule removed nobody who was ranked before.
  for (const fips of beforeSet) assert.ok(ranked.has(fips), `${fips} was ranked before and is not now`);
});
