'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { combine } = require('../dist/composite.js');

const data = path.join(__dirname, '..', 'dist', 'data');
const read = file => JSON.parse(fs.readFileSync(path.join(data, file), 'utf8'));

test('healthcare manifest loads an exact shard and only designated scores can compose', () => {
  const original = read('healthcare.json');
  const manifest = read('layers/manifest.json');
  const listing = manifest.families.healthcare.datasets.find(item => item.id === 'hpsa-primary-care');
  assert.ok(listing, 'healthcare option is absent from the lazy manifest');
  const shard = read(`layers/${listing.file}`);
  assert.deepEqual(shard.records, original.datasets[0].records);
  assert.equal(listing.recordCount, 3107);
  const ids = Object.keys(shard.records);
  const result = combine(ids, [{ key: 'healthcare:hpsa-primary-care', dataset: shard, weight: 1 }]);
  assert.equal(result.stats.available, 2809);
  for (const id of ids) {
    const source = shard.records[id];
    const scored = result.records[id];
    assert.equal(Number.isFinite(scored.value), source.status === 'available', id);
    if (source.status === 'not_designated' || id.startsWith('09')) {
      assert.equal(scored.value, null, id);
    }
  }
  assert.equal(ids.filter(id => shard.records[id].status === 'not_designated').length, 290);
  assert.equal(ids.filter(id => id.startsWith('09') && shard.records[id].status === 'unavailable').length, 8);
});
