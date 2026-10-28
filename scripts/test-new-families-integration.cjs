const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const dist = path.join(root, 'dist');
const dataDir = path.join(dist, 'data');

const FAMILIES = [
  { id: 'wildfire', label: 'Wildfire', datasetIds: ['risk-to-homes', 'likelihood'] },
  { id: 'water', label: 'Drinking water', datasetIds: ['health-violations-2023-2025'] },
  { id: 'traffic', label: 'Traffic safety', datasetIds: ['deaths-2019-2023'] }
];

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

test('manifest lists new families with correct dataset ids and record counts', () => {
  const manifest = readJson(path.join(dataDir, 'layers', 'manifest.json'));

  for (const family of FAMILIES) {
    assert.ok(manifest.families[family.id], `manifest missing family ${family.id}`);
    const datasets = manifest.families[family.id].datasets;
    assert.equal(datasets.length, family.datasetIds.length, `${family.id} dataset count mismatch`);

    for (const datasetId of family.datasetIds) {
      const dataset = datasets.find(d => d.id === datasetId);
      assert.ok(dataset, `manifest missing dataset ${family.id}:${datasetId}`);
      assert.equal(dataset.recordCount, 3107, `${family.id}:${datasetId} record count should be 3107`);
    }
  }
});

test('index.html has new family options', () => {
  const html = fs.readFileSync(path.join(dist, 'index.html'), 'utf8');

  assert.ok(html.includes('<option value="wildfire">Wildfire</option>'));
  assert.ok(html.includes('<option value="water">Drinking water</option>'));
  assert.ok(html.includes('<option value="traffic">Traffic safety</option>'));
});

test('app.js contains new family labels', () => {
  const app = fs.readFileSync(path.join(dist, 'app.js'), 'utf8');

  assert.ok(app.includes('wildfire: "Wildfire"'));
  assert.ok(app.includes('water: "Drinking water"'));
  assert.ok(app.includes('traffic: "Traffic safety"'));
});

test('app.js contains required caveat strings', () => {
  const app = fs.readFileSync(path.join(dist, 'app.js'), 'utf8');

  assert.ok(app.includes('National ranks from a USDA Forest Service model. The value is a rank from 0 to 100. It is not a probability of fire or a loss amount.'));
  assert.ok(app.includes('Share of people on community water systems whose system had a health-based violation in 2023–2025. One large system can decide a county, and private wells are not covered.'));
  assert.ok(app.includes("Deaths in crashes on the county's roads per 100,000 residents, 2019–2023. It includes people passing through, so it is not a resident's own risk."));
});

test('shard files exist and have 3107 records', () => {
  for (const family of FAMILIES) {
    const familyFile = path.join(dataDir, `${family.id}.json`);
    assert.ok(fs.existsSync(familyFile), `missing ${family.id}.json`);

    const json = readJson(familyFile);
    assert.ok(Array.isArray(json.datasets), `${family.id}.json missing datasets array`);
    assert.equal(json.datasets.length, family.datasetIds.length, `${family.id} dataset count mismatch`);

    for (const dataset of json.datasets) {
      assert.ok(family.datasetIds.includes(dataset.id), `unexpected dataset id ${dataset.id} in ${family.id}`);
      assert.ok(dataset.records && typeof dataset.records === 'object', `${family.id}/${dataset.id} missing records`);
      const recordCount = Object.keys(dataset.records).length;
      assert.equal(recordCount, 3107, `${family.id}/${dataset.id} should have 3107 records, got ${recordCount}`);
    }
  }
});

test('layer shard files exist and have 3107 records each', () => {
  const manifest = readJson(path.join(dataDir, 'layers', 'manifest.json'));

  for (const family of FAMILIES) {
    const datasets = manifest.families[family.id].datasets;
    for (const dataset of datasets) {
      const shardFile = path.join(dataDir, 'layers', dataset.file);
      assert.ok(fs.existsSync(shardFile), `missing shard file ${dataset.file}`);

      const shard = readJson(shardFile);
      assert.ok(shard.records, `${dataset.file} missing records`);
      const recordCount = Object.keys(shard.records).length;
      assert.equal(recordCount, 3107, `${dataset.file} should have 3107 records, got ${recordCount}`);
    }
  }
});
