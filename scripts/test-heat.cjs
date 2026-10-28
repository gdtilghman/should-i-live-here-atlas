'use strict';
// Guards the heat layer, dist/data/climate.json, built by scripts/prepare-heat.py.
//
// The first tests need only the committed layer. The last one re-derives every
// county's value from NOAA's raw monthly files in JavaScript, independently of
// the Python builder: its own crosswalk parse, its own padding rule and its
// own threshold. It skips until `python scripts/prepare-heat.py --fetch` has
// put the ignored source files in work/heat-source/.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const layerPath = path.join(root, 'dist', 'data', 'climate.json');
const sourceDir = path.join(root, 'work', 'heat-source');
const readJson = (file) => JSON.parse(fs.readFileSync(file, 'utf8'));

function layer() {
  const payload = readJson(layerPath);
  assert.strictEqual(payload.datasets.length, 1);
  return payload.datasets[0];
}

test('the heat layer covers the atlas and marks its one gap with a reason', () => {
  const dataset = layer();
  const atlas = readJson(path.join(root, 'dist', 'data', 'counties.geojson')).features.map((f) => f.properties.fips);
  assert.deepStrictEqual(Object.keys(dataset.records).sort(), [...atlas].sort());
  const statuses = {};
  for (const record of Object.values(dataset.records)) statuses[record.status] = (statuses[record.status] || 0) + 1;
  assert.deepStrictEqual(statuses, { available: 3106, unavailable: 1 });
  const lexington = dataset.records['51678'];
  assert.strictEqual(lexington.status, 'unavailable');
  assert.strictEqual(lexington.value, null, 'no value is borrowed from Rockbridge County');
  assert.match(lexington.reason, /Rockbridge/);
});

test('values are days a year, and zero is a real reading', () => {
  const dataset = layer();
  const values = Object.values(dataset.records).filter((r) => r.status === 'available').map((r) => r.value);
  assert.ok(values.every((v) => Number.isFinite(v) && v >= 0 && v <= 366), 'a value is outside 0–366 days');
  assert.ok(values.some((v) => v === 0), 'no county at zero; cool counties should read 0, not missing');
  assert.strictEqual(dataset.min, Math.min(...values));
  assert.strictEqual(dataset.max, Math.max(...values));
  assert.strictEqual(dataset.direction, 'higher-worse');
  // The note must say what the number is not.
  assert.match(dataset.note, /not a thermometer reading/);
  assert.match(dataset.note, /not a projection/);
  assert.match(dataset.note, /does not endorse/);
});

const sourceSkip = fs.existsSync(path.join(sourceDir, 'tmax-202012-cty-scaled.csv'))
  ? false : 'run python scripts/prepare-heat.py --fetch first';

test('every county value re-derives from NOAA\'s raw monthly files', { skip: sourceSkip }, () => {
  const crosswalk = {};
  const lines = fs.readFileSync(path.join(sourceDir, 'us-state-codes_ncei-to-fips.csv'), 'utf8').trim().split(/\r?\n/);
  const header = lines[0].split(',');
  for (const line of lines.slice(1)) {
    const cells = line.split(',');
    crosswalk[cells[header.indexOf('NCEI_code')].trim()] = cells[header.indexOf('FIPS_code')].trim();
  }
  const totals = {};
  let files = 0;
  for (let year = 1991; year <= 2020; year++) {
    for (let month = 1; month <= 12; month++) {
      const name = `tmax-${year}${String(month).padStart(2, '0')}-cty-scaled.csv`;
      const days = new Date(Date.UTC(year, month, 0)).getUTCDate();
      for (const line of fs.readFileSync(path.join(sourceDir, name), 'utf8').trim().split(/\r?\n/)) {
        const cells = line.split(',');
        const fips = crosswalk[cells[1].trim().slice(0, 2)] + cells[1].trim().slice(2);
        const real = cells.slice(6, 6 + days).map(Number);
        assert.ok(real.every((v) => v > -999), `${name} ${fips}: a real day is padding`);
        assert.ok(cells.slice(6 + days).every((v) => Number(v) === -999.99), `${name} ${fips}: padding holds data`);
        // 95°F is 35°C exactly; values carry two decimals.
        totals[fips] = (totals[fips] || 0) + real.filter((v) => v >= 35).length;
      }
      files++;
    }
  }
  assert.strictEqual(files, 360);
  const dataset = layer();
  const failures = [];
  for (const [fips, record] of Object.entries(dataset.records)) {
    if (record.status !== 'available') continue;
    const expected = Math.round((totals[fips] / 30) * 10) / 10;
    if (record.value !== expected) failures.push(`${fips}: layer ${record.value}, raw ${expected}`);
  }
  assert.deepStrictEqual(failures.slice(0, 5), [], `${failures.length} counties disagree with the raw files`);
  assert.ok(!('51678' in totals), 'NOAA now publishes Lexington city; revisit the unavailable record');
});
