'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('path');

const data = path.join(__dirname, '..', 'dist', 'data');
const read = file => JSON.parse(fs.readFileSync(path.join(data, file), 'utf8'));

test('air family present in manifest with exactly 1 dataset', () => {
  const manifest = read('layers/manifest.json');
  assert.ok(manifest.families.air, 'air family absent from the manifest');
  const datasets = manifest.families.air.datasets;
  assert.equal(datasets.length, 1, 'air must have exactly 1 dataset');
  const dataset = datasets[0];
  assert.equal(dataset.id, 'pm25-2020-2022', `air dataset id mismatch: ${dataset.id}`);
  assert.ok(dataset.file, 'air:pm25-2020-2022 missing file');
  assert.equal(dataset.recordCount, 3107, 'air:pm25-2020-2022 record count mismatch');
});

test('index.html option for air is present', () => {
  const html = fs.readFileSync(path.join(__dirname, '..', 'dist', 'index.html'), 'utf8');
  assert.ok(html.includes('<option value="air">Air quality</option>'), 'index.html missing air option');
});

test('app.js lists air in every family array that contains climate', () => {
  const appJs = fs.readFileSync(path.join(__dirname, '..', 'dist', 'app.js'), 'utf8');
  // Find all arrays containing "climate" as a string literal in quotes
  const pattern = /\[.*?"climate".*?\]/g;
  const climateArrays = appJs.match(pattern) || [];
  assert.ok(climateArrays.length > 0, 'no family arrays found with climate');

  climateArrays.forEach(arr => {
    assert.ok(arr.includes('"air"'), `family array missing air: ${arr}`);
    // Verify air comes after places
    const placesIdx = arr.indexOf('"places"');
    const airIdx = arr.indexOf('"air"');
    assert.ok(placesIdx >= 0 && airIdx > placesIdx, `air must come after places: ${arr}`);
  });
});

test('air caption and measure label are present in app.js', () => {
  const appJs = fs.readFileSync(path.join(__dirname, '..', 'dist', 'app.js'), 'utf8');
  assert.ok(appJs.includes('Model estimates of long-term fine particle pollution where people live. The values average 2020–2022. They are not daily air quality. They are not anyone\'s personal exposure.'), 'air caption missing from app.js');
  assert.ok(appJs.includes('Air measure'), 'Air measure label missing from app.js');
});

test('air shard reproduces records exactly from air.json', () => {
  const original = read('air.json');
  const manifest = read('layers/manifest.json');

  original.datasets.forEach(originalDataset => {
    const listing = manifest.families.air.datasets.find(d => d.id === originalDataset.id);
    assert.ok(listing, `air:${originalDataset.id} absent from manifest`);
    assert.equal(listing.file, `air-${originalDataset.id}.json`, `air:${originalDataset.id} file name mismatch`);

    const shard = read(`layers/${listing.file}`);
    const shardRecords = shard.records;
    const originalRecords = originalDataset.records;

    // Check that all FIPS codes match
    const shardFips = Object.keys(shardRecords).sort();
    const originalFips = Object.keys(originalRecords).sort();
    assert.deepEqual(shardFips, originalFips, `air:${originalDataset.id} FIPS codes mismatch`);

    // Check that all records match
    originalFips.forEach(fips => {
      assert.deepEqual(shardRecords[fips], originalRecords[fips], `air:${originalDataset.id} record ${fips} mismatch`);
    });
  });
});

test('air has expected unavailable counties with reasons', () => {
  const pm25 = read('layers/air-pm25-2020-2022.json');
  const records = pm25.records;

  // Oglala Lakota County, South Dakota (46102) and others should be unavailable with reason
  const { '46102': oglala, '12129': someCounty } = records;
  assert.ok(oglala, 'Oglala Lakota County (46102) missing from air:pm25-2020-2022');
  assert.equal(oglala.status, 'unavailable', 'Oglala Lakota County should be unavailable');
  assert.ok(oglala.reason, 'Oglala Lakota County should have a reason');

  // Count unavailable records with reasons (49 missing + 5 with no pop-weighted values)
  const unavailableWithReason = Object.values(records).filter(r => r.status === 'unavailable' && r.reason);
  assert.equal(unavailableWithReason.length, 54, `expected 54 unavailable with reason, got ${unavailableWithReason.length}`);
});

test('air inputs are offered in app.js composite choices', () => {
  const appJs = fs.readFileSync(path.join(__dirname, '..', 'dist', 'app.js'), 'utf8');

  // Check that air appears in the allCompositeChoices section
  const hasAir = appJs.includes('air:pm25') || (appJs.includes('"air"') && appJs.includes('allCompositeChoices'));
  assert.ok(hasAir, 'air inputs not found in app.js composite logic');
});

test('no U+FFFD replacement character in air files or app', () => {
  const files = [
    path.join(__dirname, '..', 'dist', 'app.js'),
    path.join(__dirname, '..', 'dist', 'index.html'),
    path.join(data, 'air.json'),
    path.join(data, 'layers', 'air-pm25-2020-2022.json')
  ];

  files.forEach(file => {
    const content = fs.readFileSync(file, 'utf8');
    const replacements = (content.match(/�/g) || []).length;
    assert.equal(replacements, 0, `${file} contains ${replacements} U+FFFD replacement character(s)`);
  });
});
