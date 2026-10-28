'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { combine } = require('../dist/composite.js');

const data = path.join(__dirname, '..', 'dist', 'data');
const read = file => JSON.parse(fs.readFileSync(path.join(data, file), 'utf8'));

test('employment manifest shard reproduces the verified family file exactly', () => {
  const original = read('employment.json');
  const dataset = original.datasets[0];
  const manifest = read('layers/manifest.json');
  assert.ok(manifest.families.employment, 'employment family absent from the manifest');
  const listing = manifest.families.employment.datasets.find(item => item.id === 'unemployment-rate');
  assert.ok(listing, 'unemployment-rate is absent from the manifest');
  assert.equal(listing.file, 'employment-unemployment-rate.json');
  const shard = read(`layers/${listing.file}`);
  assert.deepEqual(shard.records, dataset.records);
  assert.equal(listing.recordCount, 3107);
  assert.equal(Object.keys(shard.records).length, 3107);
  assert.equal(listing.direction, 'higher-worse');
  assert.equal(listing.unit, '% of civilian labor force');
  assert.equal(listing.period, '2025, 11-month average');
  assert.equal(listing.source, 'BLS Local Area Unemployment Statistics');
  assert.equal(listing.sourceUrl, 'https://www.bls.gov/lau/laucnty25.xlsx');
  assert.ok(Number.isFinite(listing.min) && Number.isFinite(listing.max));
});

test('employment has 3099 scored counties, null Connecticut legacy counties, and no invented zeros', () => {
  const shard = read('layers/employment-unemployment-rate.json');
  const records = shard.records;
  const ids = Object.keys(records);
  assert.equal(ids.length, 3107);
  const available = ids.filter(id => records[id].status === 'available');
  assert.equal(available.length, 3099);
  const connecticut = ids.filter(id => id.startsWith('09'));
  assert.equal(connecticut.length, 8);
  for (const id of connecticut) {
    assert.equal(records[id].status, 'unavailable', id);
    assert.equal(records[id].value, null, id);
    assert.ok(records[id].reason, `missing reason for ${id}`);
    for (const key of ['laborForce', 'employed', 'unemployed']) {
      assert.equal(records[id][key], null, `${id} ${key}`);
    }
  }
  assert.equal(ids.filter(id => records[id].value === 0).length, 0, 'a missing value became zero');
  for (const id of available) {
    const record = records[id];
    assert.ok(Number.isFinite(record.value), id);
    assert.ok(record.value >= 0 && record.value <= 100, id);
    for (const key of ['laborForce', 'employed', 'unemployed']) {
      assert.ok(record[key] === null || (Number.isInteger(record[key]) && record[key] >= 0), `${id} ${key}`);
    }
  }
});

test('employment-only composition scores higher unemployment as worse', () => {
  const employment = read('layers/employment-unemployment-rate.json');
  const ids = Object.keys(employment.records);
  const result = combine(ids, [{ key: 'employment:unemployment-rate', dataset: employment, weight: 1 }]);
  assert.equal(result.stats.available, 3099);
  assert.ok(Number.isFinite(result.stats.min));
  assert.ok(Number.isFinite(result.stats.max));
  assert.ok(result.stats.max > result.stats.min);
  const scored = ids
    .filter(id => result.records[id].value !== null)
    .sort((a, b) => employment.records[a].value - employment.records[b].value);
  assert.equal(scored.length, 3099);
  for (let i = 1; i < scored.length; i += 1) {
    assert.ok(result.records[scored[i]].value >= result.records[scored[i - 1]].value,
      `higher rate scored lower: ${scored[i - 1]} ${employment.records[scored[i - 1]].value} -> ${result.records[scored[i - 1]].value}; ${scored[i]} ${employment.records[scored[i]].value} -> ${result.records[scored[i]].value}`);
  }
});

test('employment joins the untouched default recipe without breaking it', () => {
  const employment = read('layers/employment-unemployment-rate.json');
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
  const ids = Object.keys(employment.records);
  const base = combine(ids, defaults);
  assert.equal(base.stats.available, 2570, 'default recipe regression');
  const withEmployment = combine(ids, [
    ...defaults,
    { key: 'employment:unemployment-rate', dataset: employment, weight: 15 }
  ]);
  assert.ok(Number.isFinite(withEmployment.stats.min));
  assert.ok(Number.isFinite(withEmployment.stats.max));
  for (const id of ids) {
    const expected = base.records[id].value !== null && employment.records[id].status === 'available';
    assert.equal(Number.isFinite(withEmployment.records[id].value), expected, id);
  }
  assert.ok(withEmployment.stats.available > 0 && withEmployment.stats.available <= base.stats.available);
});
