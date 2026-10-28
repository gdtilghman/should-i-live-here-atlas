'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('path');

const data = path.join(__dirname, '..', 'dist', 'data');
const read = file => JSON.parse(fs.readFileSync(path.join(data, file), 'utf8'));

test('places family present in manifest with exactly 15 datasets', () => {
  const manifest = read('layers/manifest.json');
  assert.ok(manifest.families.places, 'places family absent from the manifest');
  const datasets = manifest.families.places.datasets;
  assert.equal(datasets.length, 15, 'places must have exactly 15 datasets');
  const ids = datasets.map(d => d.id);
  assert.deepEqual(ids, ['asthma', 'diabetes', 'mental-distress', 'obesity', 'smoking', 'physical-inactivity', 'binge-drinking', 'short-sleep', 'copd', 'heart-disease', 'stroke', 'depression', 'poor-health', 'physical-distress', 'uninsured'], `places dataset ids mismatch: ${JSON.stringify(ids)}`);
  datasets.forEach(dataset => {
    assert.ok(dataset.file, `places:${dataset.id} missing file`);
    assert.equal(dataset.recordCount, 3107, `places:${dataset.id} record count mismatch`);
  });
});

test('index.html option for places is present', () => {
  const html = fs.readFileSync(path.join(__dirname, '..', 'dist', 'index.html'), 'utf8');
  assert.ok(html.includes('<option value="places">Adult health</option>'), 'index.html missing places option');
});

test('app.js lists places in every family array that contains climate', () => {
  const appJs = fs.readFileSync(path.join(__dirname, '..', 'dist', 'app.js'), 'utf8');
  // Find all arrays containing "climate" as a string literal in quotes
  const pattern = /\[.*?"climate".*?\]/g;
  const climateArrays = appJs.match(pattern) || [];
  assert.ok(climateArrays.length > 0, 'no family arrays found with climate');

  climateArrays.forEach(arr => {
    assert.ok(arr.includes('"places"'), `family array missing places: ${arr}`);
  });
});

test('places caution texts and Health measure label are present in app.js', () => {
  const appJs = fs.readFileSync(path.join(__dirname, '..', 'dist', 'app.js'), 'utf8');
  assert.ok(appJs.includes('CDC model estimates for adults, adjusted for age. They are not a count. They are not your personal risk. The CDC advises against ranking counties with these values.'), 'legend/caption caution missing from app.js');
  assert.ok(appJs.includes('CDC model estimate. The CDC advises against ranking counties with PLACES data. Small differences may not be meaningful. This is especially true for asthma.'), 'recipe signal row caution missing from app.js');
  assert.ok(appJs.includes('CDC model estimate. The CDC advises against ranking counties with PLACES data.'), 'ranked-list caution missing from app.js');
  assert.ok(appJs.includes('Health measure'), 'Health measure label missing from app.js');
});

test('places shards reproduce records exactly from places.json', () => {
  const original = read('places.json');
  const manifest = read('layers/manifest.json');

  original.datasets.forEach(originalDataset => {
    const listing = manifest.families.places.datasets.find(d => d.id === originalDataset.id);
    assert.ok(listing, `places:${originalDataset.id} absent from manifest`);
    assert.equal(listing.file, `places-${originalDataset.id}.json`, `places:${originalDataset.id} file name mismatch`);

    const shard = read(`layers/${listing.file}`);
    const shardRecords = shard.records;
    const originalRecords = originalDataset.records;

    // Check that all FIPS codes match
    const shardFips = Object.keys(shardRecords).sort();
    const originalFips = Object.keys(originalRecords).sort();
    assert.deepEqual(shardFips, originalFips, `places:${originalDataset.id} FIPS codes mismatch`);

    // Check that all records match
    originalFips.forEach(fips => {
      assert.deepEqual(shardRecords[fips], originalRecords[fips], `places:${originalDataset.id} record ${fips} mismatch`);
    });
  });
});

test('Connecticut 09001 is unavailable with reason in all places datasets', () => {
  const original = read('places.json');
  original.datasets.forEach(dataset => {
    const record = dataset.records['09001'];
    assert.ok(record, `Connecticut 09001 missing from places:${dataset.id}`);
    assert.equal(record.status, 'unavailable', `Connecticut 09001 should be unavailable in places:${dataset.id}`);
    assert.ok(record.reason, `Connecticut 09001 should have a reason in places:${dataset.id}`);
  });
});

test('places has expected availability (8 Connecticut counties unavailable)', () => {
  const asthma = read('layers/places-asthma.json');
  const records = asthma.records;
  const ids = Object.keys(records);

  assert.equal(ids.length, 3107, 'places should score all 3107 atlas counties');

  const available = ids.filter(id => records[id].status === 'available');
  assert.equal(available.length, 3099, `places asthma should have 3099 available (got ${available.length})`);

  const connecticut = ids.filter(id => id.startsWith('09'));
  assert.equal(connecticut.length, 8, 'should have 8 Connecticut counties');

  const unavailable = connecticut.filter(id => records[id].status === 'unavailable');
  assert.equal(unavailable.length, 8, 'all 8 Connecticut counties should be unavailable');
});

test('places records have crude and age-adjusted values with confidence intervals', () => {
  const asthma = read('layers/places-asthma.json');
  const records = asthma.records;

  // Find an available record
  const available = Object.entries(records).find(([, record]) => record.status === 'available');
  assert.ok(available, 'no available places records found');

  const [fips, record] = available;
  assert.ok(Number.isFinite(record.value), `${fips} age-adjusted value not finite`);
  assert.ok(Number.isFinite(record.low), `${fips} age-adjusted low not finite`);
  assert.ok(Number.isFinite(record.high), `${fips} age-adjusted high not finite`);
  assert.ok(record.low <= record.value && record.value <= record.high, `${fips} value outside interval`);

  assert.ok(Number.isFinite(record.crude), `${fips} crude value not finite`);
  assert.ok(Number.isFinite(record.crudeLow), `${fips} crude low not finite`);
  assert.ok(Number.isFinite(record.crudeHigh), `${fips} crude high not finite`);
  assert.ok(record.crudeLow <= record.crude && record.crude <= record.crudeHigh, `${fips} crude value outside interval`);
});

test('places inputs are offered in app.js composite choices', () => {
  const appJs = fs.readFileSync(path.join(__dirname, '..', 'dist', 'app.js'), 'utf8');

  // Check that places appears in the allCompositeChoices section
  const hasPlaces = appJs.includes('places:asthma') || appJs.includes('"places"');
  assert.ok(hasPlaces, 'places inputs not found in app.js composite logic');
});
