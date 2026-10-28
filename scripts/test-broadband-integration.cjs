'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { combine } = require('../dist/composite.js');

const data = path.join(__dirname, '..', 'dist', 'data');
const read = file => JSON.parse(fs.readFileSync(path.join(data, file), 'utf8'));

function quantileSorted(values, p) {
  if (!values.length) return null;
  const position = (values.length - 1) * p;
  const lower = Math.floor(position);
  const upper = Math.min(lower + 1, values.length - 1);
  return values[lower] + (values[upper] - values[lower]) * (position - lower);
}

test('broadband manifest shard reproduces the verified family file exactly', () => {
  const original = read('broadband.json');
  const dataset = original.datasets[0];
  const manifest = read('layers/manifest.json');
  assert.ok(manifest.families.broadband, 'broadband family absent from the manifest');
  const listing = manifest.families.broadband.datasets.find(item => item.id === 'without-100-20');
  assert.ok(listing, 'without-100-20 is absent from the manifest');
  assert.equal(listing.file, 'broadband-without-100-20.json');
  const shard = read(`layers/${listing.file}`);
  assert.deepEqual(shard.records, dataset.records);
  assert.equal(listing.recordCount, 3107);
  assert.equal(Object.keys(shard.records).length, 3107);
  assert.equal(listing.direction, 'higher-worse');
  assert.equal(listing.title, 'Residents without reported 100/20 Mbps access');
  assert.equal(listing.unit, '% of residents');
  assert.equal(listing.period, 'June 2024');
  assert.equal(listing.source, 'FCC Connect2Health / Broadband Data Collection');
  assert.equal(listing.sourceUrl, 'https://c2h.fcc.gov/bh-data.html');
  assert.ok(Number.isFinite(listing.min) && Number.isFinite(listing.max));
});

test('broadband scores all 3107 counties, including Connecticut, with exact raw and derived values', () => {
  const broadband = read('layers/broadband-without-100-20.json');
  const records = broadband.records;
  const ids = Object.keys(records);
  assert.equal(ids.length, 3107);
  const connecticut = ids.filter(id => id.startsWith('09'));
  assert.equal(connecticut.length, 8);
  const available = ids.filter(id => records[id].status === 'available');
  assert.equal(available.length, 3107);
  for (const id of available) {
    const record = records[id];
    assert.ok(Number.isFinite(record.value), `${id} derived value`);
    assert.ok(record.value >= 0 && record.value <= 100, `${id} derived range`);
    assert.ok(Number.isFinite(record.sourceAccessPercent), `${id} reported value`);
    assert.ok(record.sourceAccessPercent >= 0 && record.sourceAccessPercent <= 100, `${id} reported range`);
    assert.ok(Math.abs(record.value + record.sourceAccessPercent - 100) <= 1e-9, `${id} raw/derived parity`);
  }
  assert.equal(available.filter(id => records[id].value === 0).length, 113, 'meaningful zero gaps');
  assert.equal(records['35003'].value, 100);
  assert.equal(records['35003'].sourceAccessPercent, 0);
  assert.equal(records['06003'].value, 0);
  assert.equal(records['06003'].sourceAccessPercent, 100);
  assert.equal(records['06037'].value, 3.5);
  assert.equal(records['06037'].sourceAccessPercent, 96.5);
});

test('broadband uses the actual national range and 3×IQR purple extremes', () => {
  const broadband = read('layers/broadband-without-100-20.json');
  const values = Object.values(broadband.records)
    .map(record => record.value)
    .sort((a, b) => a - b);
  assert.equal(values.length, 3107);
  assert.equal(values[0], 0);
  assert.equal(values[values.length - 1], 100);
  const q1 = quantileSorted(values, 0.25);
  const q3 = quantileSorted(values, 0.75);
  const iqr = q3 - q1;
  const fence = q3 + 3 * iqr;
  const firstOutlier = values.findIndex(value => value > fence);
  assert.equal(firstOutlier, 3067);
  assert.equal(values[firstOutlier - 1], 72.6);
  assert.equal(values[firstOutlier], 75.4);
  assert.equal(values.slice(firstOutlier).length, 40);
});

test('broadband-only composition scores larger access gaps as worse', () => {
  const broadband = read('layers/broadband-without-100-20.json');
  const ids = Object.keys(broadband.records);
  const result = combine(ids, [{ key: 'broadband:without-100-20', dataset: broadband, weight: 1 }]);
  assert.equal(result.stats.available, 3107);
  assert.ok(Number.isFinite(result.stats.min));
  assert.ok(Number.isFinite(result.stats.max));
  assert.ok(result.stats.max > result.stats.min);
  const scored = ids
    .filter(id => result.records[id].value !== null)
    .sort((a, b) => broadband.records[a].value - broadband.records[b].value);
  assert.equal(scored.length, 3107);
  for (let i = 1; i < scored.length; i += 1) {
    assert.ok(result.records[scored[i]].value >= result.records[scored[i - 1]].value,
      `higher gap scored lower: ${scored[i - 1]} ${broadband.records[scored[i - 1]].value} -> ${result.records[scored[i - 1]].value}; ${scored[i]} ${broadband.records[scored[i]].value} -> ${result.records[scored[i]].value}`);
  }
});

test('a missing broadband county is not converted to zero in composition', () => {
  const broadband = read('layers/broadband-without-100-20.json');
  const fixture = { ...broadband, records: { '01001': { ...broadband.records['01001'], status: 'unavailable', value: null, reason: 'Test-only unavailable value' } } };
  const result = combine(['01001'], [{ key: 'broadband:without-100-20', dataset: fixture, weight: 1 }]);
  assert.equal(result.stats.available, 0);
  assert.equal(result.records['01001'].value, null);
  assert.notEqual(result.records['01001'].value, 0);
});

test('broadband joins the untouched default recipe without breaking it', () => {
  const broadband = read('layers/broadband-without-100-20.json');
  const cancer = read('cancer.json');
  const disasters = read('disasters.json');
  const select = (collection, id) => collection.datasets.find(dataset => dataset.id === id);
  const defaults = [
    { key: 'disasters:hazard-fire', dataset: select(disasters, 'hazard-fire'), weight: 40 },
    { key: 'cancer:066', dataset: select(cancer, '066'), weight: 30 },
    { key: 'disasters:hazard-flood', dataset: select(disasters, 'hazard-flood'), weight: 20 },
    { key: 'cancer:047-male', dataset: select(cancer, '047-male'), weight: 10 }
  ];
  assert.ok(defaults.every(item => item.dataset), 'expected exact audited default inputs');
  const ids = Object.keys(broadband.records);
  const base = combine(ids, defaults);
  assert.equal(base.stats.available, 2570, 'default recipe regression');
  const withBroadband = combine(ids, [
    ...defaults,
    { key: 'broadband:without-100-20', dataset: broadband, weight: 15 }
  ]);
  assert.ok(Number.isFinite(withBroadband.stats.min));
  assert.ok(Number.isFinite(withBroadband.stats.max));
  assert.equal(withBroadband.stats.available, 2570, 'adding fully available broadband preserves comparable counties');
  for (const id of ids) {
    const expected = base.records[id].value !== null;
    assert.equal(Number.isFinite(withBroadband.records[id].value), expected, id);
  }
});
