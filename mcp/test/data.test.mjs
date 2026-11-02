import test from 'node:test';
import assert from 'node:assert/strict';
import { loadData } from '../src/data.js';
import { packedInput, layer, skip } from './helpers.mjs';

const db = skip ? null : loadData(packedInput());

test('measures and counties load', { skip }, () => {
  assert.equal(db.countyCount, 3107);
  assert.equal(db.counties.length, 3107);
  assert.equal(db.measures.length, 73);
  assert.equal(db.measure('crime:violent-crime').title, 'Violent crime');
  assert.equal(db.measure('nope:nothing'), null);
});

test('listMeasures gives labels, counts and an optional filter', { skip }, () => {
  const all = db.listMeasures();
  assert.equal(all.length, 73);
  const first = all[0];
  assert.deepEqual(Object.keys(first).sort(), ['available', 'direction', 'family', 'key', 'label', 'period', 'title', 'unit'].sort());
  assert.equal(all.find(m => m.key === 'cancer:001').label, 'All Cancer Sites · Both sexes');
  assert.equal(all.find(m => m.key === 'cancer:001-male').label, 'All Cancer Sites · Male');
  assert.equal(all.find(m => m.key === 'crime:violent-crime').label, 'Violent crime');
  assert.equal(all.find(m => m.key === 'crime:violent-crime').available, 2195);
  const crime = db.listMeasures('CRIME');
  assert.deepEqual(crime.map(m => m.key), ['crime:violent-crime', 'crime:property-crime']);
  assert.ok(db.listMeasures('rent').some(m => m.key === 'community:median-rent'));
});

test('value() returns layer values, and null for anything not available', { skip }, () => {
  const ref = layer('crime:violent-crime');
  for (const [fips, r] of Object.entries(ref.records)) {
    const v = db.value('crime:violent-crime', fips);
    if (r.status === 'available') assert.deepEqual(v, { status: 'available', value: r.value });
    else assert.deepEqual(v, { status: r.status, value: null });
  }
  assert.deepEqual(db.value('crime:violent-crime', '99999'), { status: 'unavailable', value: null });
});

test('dataset() is a composite.js dataset with the same records', { skip }, () => {
  const d = db.dataset('hazards:nri-hurricane');
  const ref = layer('hazards:nri-hurricane');
  assert.equal(d.title, ref.title);
  assert.equal(d.direction, 'higher-worse');
  assert.equal(d.notApplicableMeans, 'best-case');
  assert.equal(Object.keys(d.records).length, 3107);
  for (const [fips, r] of Object.entries(ref.records)) {
    const got = d.records[fips];
    if (r.status === 'available') assert.deepEqual(got, { status: 'available', value: r.value });
    else assert.deepEqual(got, { status: r.status, value: null });
  }
  assert.equal(db.dataset('nope:nothing'), null);
});

test('findCounties accepts FIPS, "Name, State" and postal codes', { skip }, () => {
  const byFips = db.findCounties('06037');
  assert.equal(byFips.length, 1);
  assert.equal(byFips[0].name, 'Los Angeles County');
  assert.deepEqual(db.findCounties('Los Angeles County, California').map(c => c.fips), ['06037']);
  assert.deepEqual(db.findCounties('los angeles, ca').map(c => c.fips), ['06037']);
  assert.deepEqual(db.findCounties('Orleans Parish, Louisiana').map(c => c.fips), ['22071']);
  assert.deepEqual(db.findCounties('Orleans, LA').map(c => c.fips), ['22071']);
  // Two Baltimores in Maryland: the county and the independent city.
  assert.deepEqual(db.findCounties('Baltimore, MD').map(c => c.fips).sort(), ['24005', '24510']);
  assert.deepEqual(db.findCounties('Nowhere, Texas'), []);
  assert.deepEqual(db.findCounties(''), []);
});

test('stateFips resolves names, postal codes and FIPS', { skip }, () => {
  assert.equal(db.stateFips('Texas'), '48');
  assert.equal(db.stateFips('tx'), '48');
  assert.equal(db.stateFips('48'), '48');
  assert.equal(db.stateFips('Alaska'), null, 'Alaska is not in the atlas');
  assert.equal(db.stateFips('Narnia'), null);
});

test('findMeasures maps plain words and reports what the atlas lacks', { skip }, () => {
  const r = db.findMeasures(['internet availability', 'lowest cancer rates', 'crime', 'best schools', 'cost of living']);
  const by = Object.fromEntries(r.matches.map(m => [m.term, m]));
  assert.deepEqual(by['internet availability'].keys, ['broadband:without-100-20']);
  assert.deepEqual(by['lowest cancer rates'].keys, ['cancer:001']);
  assert.deepEqual(by['crime'].keys, ['crime:violent-crime', 'crime:property-crime']);
  assert.deepEqual(by['cost of living'].keys, ['community:median-rent', 'community:median-home-value']);
  assert.equal(by['cost of living'].proxy, true);
  assert.equal(by['crime'].proxy, false);
  assert.deepEqual(r.not_available, ['best schools']);
  assert.deepEqual(db.findMeasures(['crime:property-crime']).matches[0].keys, ['crime:property-crime']);
  assert.deepEqual(db.findMeasures(['obesity']).matches[0].keys, ['places:obesity']);
  assert.deepEqual(db.findMeasures(['  ', 'unicorns']).not_available, ['unicorns']);
});
