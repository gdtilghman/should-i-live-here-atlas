import test from 'node:test';
import assert from 'node:assert/strict';
import composite from '../../dist/composite.js';
import { loadData } from '../src/data.js';
import { rankCounties, CAUTIONS } from '../src/rank.js';
import { packedInput, layer, fipsList, skip } from './helpers.mjs';

const db = skip ? null : loadData(packedInput());

// Reference: the site's own scoring code on the original layer files.
function reference(inputs, countyIds = fipsList()) {
  const signals = inputs.map(i => ({
    key: i.key, dataset: layer(i.key), weight: i.weight ?? 1,
    threshold: i.max != null ? { operator: 'max', value: i.max } : i.min != null ? { operator: 'min', value: i.min } : undefined,
  }));
  const { records } = composite.combine(countyIds, signals);
  return { ranked: composite.rank(records, countyIds), unranked: composite.unranked(records, countyIds) };
}

test('cautions are exact', () => {
  assert.equal(CAUTIONS.county, 'County values describe groups of residents. They are not your personal risk, and they do not tell you where to live.');
  assert.equal(CAUTIONS.missing, 'Counties with missing data are left out, never scored as low.');
  assert.equal(CAUTIONS.proxy, 'Median rent and median home value are proxies. They are not a full cost-of-living index.');
  assert.equal(CAUTIONS.site, 'Check the values at https://shouldilivehere.org/');
  assert.equal(CAUTIONS.small, 'Some of these counties have fewer than 10,000 residents. Rates in small counties can change a lot from year to year.');
  assert.equal(CAUTIONS.population, 'Population: US Census Bureau American Community Survey, 2019-2023 5-year estimates, table B01003.');
});

test('one measure ranks like a plain sort of the layer file', { skip }, () => {
  const r = rankCounties(db, { measures: [{ key: 'broadband:without-100-20' }], count: 25 });
  const ref = layer('broadband:without-100-20');
  const sorted = Object.entries(ref.records).filter(([, x]) => x.status === 'available')
    .sort((a, b) => a[1].value - b[1].value || (a[0] < b[0] ? -1 : 1)).map(([f]) => f);
  assert.deepEqual(r.results.map(x => x.fips), sorted.slice(0, 25));
  assert.equal(r.results[0].rank, 1);
  assert.equal(r.compared, sorted.length);
  assert.equal(r.total, 3107);
  assert.equal(r.results[0].values['broadband:without-100-20'].value, ref.records[sorted[0]].value);
});

test('the example recipe matches composite.js exactly', { skip }, () => {
  const inputs = [
    { key: 'broadband:without-100-20', weight: 1 },
    { key: 'cancer:001', weight: 1 },
    { key: 'crime:violent-crime', weight: 1 },
    { key: 'crime:property-crime', weight: 1 },
    { key: 'community:median-rent', weight: 1 },
  ];
  const r = rankCounties(db, { measures: inputs, count: 25 });
  const ref = reference(inputs);
  assert.deepEqual(r.results.map(x => x.fips), ref.ranked.slice(0, 25).map(x => x.fips));
  r.results.forEach((row, i) => {
    assert.equal(row.rank, i + 1);
    assert.equal(row.concernScore, Math.round(ref.ranked[i].score * 10) / 10);
    assert.deepEqual(row.rankRange, [ref.ranked[i].low, ref.ranked[i].high]);
    assert.equal(typeof row.name, 'string');
    assert.equal(typeof row.state, 'string');
  });
  assert.equal(r.compared, ref.ranked.length);
  assert.equal(r.leftOut.missing, ref.unranked.missing);
  assert.equal(r.leftOut.excluded, ref.unranked.excluded);
  assert.deepEqual(r.leftOut.byMeasure, ref.unranked.inputs.map(x => ({ key: x.key, title: x.title, total: x.total })));
  assert.deepEqual(r.cautions, [
    CAUTIONS.county,
    CAUTIONS.missing,
    'The FBI advises against ranking places with these data. Crime data cover 2,195 of 3,107 counties.',
    CAUTIONS.proxy,
    CAUTIONS.small,
    CAUTIONS.site,
  ]);
  assert.equal(r.results[0].population, 6043);
  assert.equal(r.leftOut.population, undefined, 'no population filter, no population count');
});

test('weights, limits and a state filter pass through to composite.js', { skip }, () => {
  const tx = fipsList().filter(f => f.startsWith('48'));
  const inputs = [
    { key: 'employment:unemployment-rate', weight: 2, max: 5 },
    { key: 'air:pm25-2020-2022', weight: 1 },
  ];
  const r = rankCounties(db, { measures: inputs, state: 'TX', count: 10 });
  const ref = reference(inputs, tx);
  assert.equal(r.total, tx.length);
  assert.deepEqual(r.results.map(x => x.fips), ref.ranked.slice(0, 10).map(x => x.fips));
  assert.equal(r.leftOut.excluded, ref.unranked.excluded);
  assert.ok(r.results.every(x => x.fips.startsWith('48')));
  const small = r.results.some(x => x.population !== null && x.population < 10000);
  assert.deepEqual(r.cautions, [CAUTIONS.county, CAUTIONS.missing, ...(small ? [CAUTIONS.small] : []), CAUTIONS.site]);
});

test('percentile is national: the percent of available counties with a lower value', { skip }, () => {
  const key = 'traffic:deaths-2019-2023';
  const r = rankCounties(db, { measures: [{ key }], state: 'Vermont', count: 3 });
  const all = Object.values(layer(key).records).filter(x => x.status === 'available').map(x => x.value);
  for (const row of r.results) {
    const v = row.values[key].value;
    assert.equal(row.values[key].percentile, Math.round(100 * all.filter(x => x < v).length / all.length));
  }
});

test('missing values never rank', { skip }, () => {
  const r = rankCounties(db, { measures: [{ key: 'crime:violent-crime' }], count: 25 });
  assert.equal(r.compared, 2195);
  assert.equal(r.leftOut.missing, 3107 - 2195);
  for (const row of r.results) assert.equal(db.value('crime:violent-crime', row.fips).status, 'available');
});

test('bad input is refused with a clear message', { skip }, () => {
  assert.throws(() => rankCounties(db, { measures: [] }), /1 to 10 measures/);
  assert.throws(() => rankCounties(db, { measures: Array.from({ length: 11 }, () => ({ key: 'cancer:001' })) }), /1 to 10 measures/);
  assert.throws(() => rankCounties(db, { measures: [{ key: 'schools:best' }] }), /Unknown measure: schools:best/);
  assert.throws(() => rankCounties(db, { measures: [{ key: 'cancer:001', weight: -1 }] }), /Weights must be 0 or more/);
  assert.throws(() => rankCounties(db, { measures: [{ key: 'cancer:001' }], count: 26 }), /count must be 1 to 25/);
  assert.throws(() => rankCounties(db, { measures: [{ key: 'cancer:001' }], state: 'Alaska' }), /Unknown state: Alaska/);
  assert.throws(() => rankCounties(db, { measures: [{ key: 'cancer:001' }, { key: 'cancer:001' }] }), /Each measure may appear once/);
  assert.equal(rankCounties(db, { measures: [{ key: 'cancer:001' }] }).results.length, 10, 'count defaults to 10');
});

test('one ranking stays fast (Workers Paid, 1 s CPU cap)', { skip }, () => {
  const inputs = { measures: [
    { key: 'broadband:without-100-20' }, { key: 'cancer:001' }, { key: 'crime:violent-crime' },
    { key: 'crime:property-crime' }, { key: 'community:median-rent' },
  ], count: 5 };
  rankCounties(db, inputs);
  const t = process.hrtime.bigint();
  for (let i = 0; i < 5; i++) rankCounties(db, inputs);
  const ms = Number(process.hrtime.bigint() - t) / 1e6 / 5;
  assert.ok(ms < 60, `${ms.toFixed(1)} ms per ranking on this machine`);
});

test('min_population leaves out small and unknown counties before ranking', { skip }, () => {
  const counties = packedInput().counties;
  const big = counties.filter(c => c.population !== null && c.population >= 50000).map(c => c.fips);
  const inputs = [
    { key: 'broadband:without-100-20' }, { key: 'cancer:001' }, { key: 'crime:violent-crime' },
    { key: 'crime:property-crime' }, { key: 'community:median-rent' },
  ];
  const r = rankCounties(db, { measures: inputs, count: 25, min_population: 50000 });
  const ref = reference(inputs, big);
  assert.equal(r.total, big.length);
  assert.deepEqual(r.results.map(x => x.fips), ref.ranked.slice(0, 25).map(x => x.fips));
  assert.ok(r.results.every(x => x.population >= 50000));
  assert.deepEqual(r.leftOut.population, {
    min: 50000,
    below: counties.filter(c => c.population !== null && c.population < 50000).length,
    unknown: 8,
  });
  assert.ok(r.cautions.includes(CAUTIONS.population));
  assert.ok(!r.cautions.includes(CAUTIONS.small));
  // National percentiles do not change with the filter.
  const k = 'cancer:001', f = r.results[0].fips;
  assert.equal(r.results[0].values[k].percentile, db.percentile(k, f));
  // The filter combines with a state filter.
  const tx = rankCounties(db, { measures: [{ key: 'cancer:001' }], state: 'TX', min_population: 100000 });
  assert.equal(tx.total, counties.filter(c => c.state === '48' && c.population >= 100000).length);
  assert.throws(() => rankCounties(db, { measures: [{ key: 'cancer:001' }], min_population: -1 }), /min_population must be a whole number, 0 or more/);
  assert.throws(() => rankCounties(db, { measures: [{ key: 'cancer:001' }], min_population: 2.5 }), /min_population must be a whole number, 0 or more/);
});
