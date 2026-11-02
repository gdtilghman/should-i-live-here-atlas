import test from 'node:test';
import assert from 'node:assert/strict';
import { loadData } from '../src/data.js';
import { CAUTIONS } from '../src/rank.js';
import { createHandlers, TOOL_NAMES } from '../src/tools.js';
import { packedInput, layer, skip } from './helpers.mjs';

const db = skip ? null : loadData(packedInput());
function handlers() {
  const logged = [];
  const h = createHandlers(db, { logMissing: async terms => { logged.push(...terms); return terms.length; } });
  return { h, logged };
}

test('the six tools exist, read-only', { skip }, () => {
  assert.deepEqual(TOOL_NAMES, ['list_measures', 'find_measure', 'get_county', 'compare_counties', 'rank_counties', 'request_measure']);
  const { h } = handlers();
  assert.deepEqual(Object.keys(h), TOOL_NAMES);
});

test('list_measures', { skip }, async () => {
  const { h } = handlers();
  const all = await h.list_measures({});
  assert.equal(all.count, 73);
  assert.equal(all.measures.length, 73);
  const crime = await h.list_measures({ filter: 'crime' });
  assert.equal(crime.count, 2);
});

test('find_measure logs only what the atlas lacks', { skip }, async () => {
  const { h, logged } = handlers();
  const r = await h.find_measure({ terms: ['internet', 'best schools', 'cost of living'] });
  assert.deepEqual(r.not_available, ['best schools']);
  assert.equal(r.note, 'The atlas has no data for: best schools. The request was counted, so the owner can consider adding it. No personal data was stored.');
  assert.deepEqual(logged, ['best schools']);
  assert.ok(r.cautions.includes(CAUTIONS.proxy));
  const none = await h.find_measure({ terms: ['internet'] });
  assert.equal(none.note, undefined);
  assert.equal(logged.length, 1, 'a full match logs nothing');
});

test('get_county returns values with status, never invented', { skip }, async () => {
  const { h } = handlers();
  const r = await h.get_county({ county: 'Los Angeles, CA' });
  assert.deepEqual(r.county, { fips: '06037', name: 'Los Angeles County', state: 'California', population: 9848406 });
  assert.equal(r.values.length, 73);
  const crime = r.values.find(v => v.key === 'crime:violent-crime');
  const ref = layer('crime:violent-crime').records['06037'];
  assert.equal(crime.status, ref.status);
  assert.equal(crime.value, ref.status === 'available' ? ref.value : null);
  for (const v of r.values) {
    assert.deepEqual(Object.keys(v).sort(), ['key', 'label', 'percentile', 'period', 'status', 'unit', 'value'].sort());
    if (v.status !== 'available') { assert.equal(v.value, null); assert.equal(v.percentile, null); }
  }
  assert.deepEqual(r.cautions, [CAUTIONS.county, CAUTIONS.site]);
  const two = await h.get_county({ county: 'Baltimore, MD' });
  assert.match(two.error, /More than one county matches/);
  assert.equal(two.choices.length, 2);
  const none = await h.get_county({ county: 'Atlantis, Ohio' });
  assert.match(none.error, /No county matches "Atlantis, Ohio"/);
});

test('compare_counties sets counties side by side', { skip }, async () => {
  const { h } = handlers();
  const r = await h.compare_counties({ counties: ['06037', 'Cook, IL'], measures: ['cancer:001', 'crime:violent-crime'] });
  assert.deepEqual(r.counties.map(c => c.fips), ['06037', '17031']);
  assert.equal(r.rows.length, 2);
  assert.deepEqual(r.rows[0].values.map(v => v.fips), ['06037', '17031']);
  assert.deepEqual(Object.keys(r.rows[0].values[0]).sort(), ['fips', 'percentile', 'status', 'value']);
  assert.ok(r.cautions.some(c => c.startsWith('The FBI advises against ranking')));
  assert.match((await h.compare_counties({ counties: ['06037'], measures: ['cancer:001'] })).error, /2 to 10 counties/);
  assert.match((await h.compare_counties({ counties: ['06037', '17031'], measures: ['nope'] })).error, /Unknown measure: nope/);
});

test('rank_counties answers the example query', { skip }, async () => {
  const { h } = handlers();
  const r = await h.rank_counties({ measures: [
    { key: 'broadband:without-100-20' }, { key: 'cancer:001' }, { key: 'crime:violent-crime' },
    { key: 'crime:property-crime' }, { key: 'community:median-rent' },
  ], count: 5 });
  assert.equal(r.results.length, 5);
  assert.equal(r.measures.length, 5);
  assert.deepEqual(Object.keys(r.measures[0]).sort(), ['citation', 'direction', 'key', 'label', 'note', 'period', 'sourceUrl', 'unit'].sort());
  assert.ok(r.cautions.includes(CAUTIONS.proxy));
  assert.equal(r.scoreNote, 'concernScore runs from 0 to 100. Lower means less of what you asked to avoid. Rank 1 has the lowest score. sharedBy counts the compared counties with exactly the same score.');
  const bad = await h.rank_counties({ measures: [{ key: 'schools:best' }] });
  assert.match(bad.error, /Unknown measure: schools:best/);
});

test('request_measure counts a missing layer', { skip }, async () => {
  const { h, logged } = handlers();
  const r = await h.request_measure({ measure: 'School quality' });
  assert.deepEqual(r, { recorded: true, measure: 'school quality' });
  assert.deepEqual(logged, ['school quality']);
  assert.match((await h.request_measure({ measure: '   ' })).error, /Name the measure/);
});
