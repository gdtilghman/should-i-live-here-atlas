'use strict';
// Guards the severe storm layer, dist/data/storms.json, built by
// scripts/prepare-storms.py.
//
// The first tests need only the committed layer. They check eight counties
// against values worked out by hand from the raw files on October 28, 2026.
// The last one re-derives every county from NOAA's raw files in JavaScript,
// independently of the Python builder: its own CSV parser, its own event-type
// map and its own area join. It skips until the ignored source files are in
// work/storm-events/.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const zlib = require('node:zlib');

const root = path.resolve(__dirname, '..');
const layerPath = path.join(root, 'dist', 'data', 'storms.json');
const sourceDir = path.join(root, 'work', 'storm-events');
const readJson = (file) => JSON.parse(fs.readFileSync(file, 'utf8'));

const IDS = ['storm-tornado', 'storm-hail', 'storm-wind', 'storm-flood', 'storm-total'];
const KEY = { 'storm-tornado': 'tornado', 'storm-hail': 'hail', 'storm-wind': 'wind', 'storm-flood': 'flood', 'storm-total': 'total' };
const GROUP = { 'Tornado': 'tornado', 'Hail': 'hail', 'Thunderstorm Wind': 'wind', 'Flash Flood': 'flood', 'Flood': 'flood' };
const YEARS = 20;

// Rates per year per 1,000 square miles of land, worked out by hand.
const REFERENCE = {
  '40109': { tornado: 3.24, hail: 44.58, wind: 27.65, flood: 12.84, total: 88.31 }, // Oklahoma County, OK
  '08031': { tornado: 2.29, hail: 63.04, wind: 21.88, flood: 5.55, total: 92.76 }, // Denver, CO
  '51019': { tornado: 0.39, hail: 7.7, wind: 19.67, flood: 3.75, total: 31.51 }, // Bedford County, VA, with the old Bedford city
  '06071': { tornado: 0.01, hail: 0.08, wind: 0.28, flood: 1.93, total: 2.29 }, // San Bernardino, CA
  '51610': { tornado: 0, hail: 48.88, wind: 244.38, flood: 97.75, total: 391.01 }, // Falls Church city, VA
  '09003': { tornado: 0.27, hail: 6.46, wind: 20.68, flood: 8.44, total: 35.85 }, // Hartford County, CT (legacy county)
  '46102': { tornado: 0.1, hail: 5.49, wind: 5.95, flood: 0.53, total: 12.06 }, // Oglala Lakota, SD
  '12086': { tornado: 0.74, hail: 3.89, wind: 4.95, flood: 4.21, total: 13.79 }, // Miami-Dade, FL
};

function datasets() {
  const payload = readJson(layerPath);
  assert.deepStrictEqual(payload.datasets.map((d) => d.id), IDS);
  return payload;
}

test('the storm layer covers the atlas with five datasets, all available', () => {
  const atlas = readJson(path.join(root, 'dist', 'data', 'counties.geojson')).features.map((f) => f.properties.fips).sort();
  for (const dataset of datasets().datasets) {
    assert.deepStrictEqual(Object.keys(dataset.records).sort(), atlas, dataset.id);
    assert.ok(Object.values(dataset.records).every((r) => r.status === 'available'), `${dataset.id} has a county that is not available`);
  }
});

test('values are report rates, and zero is a real reading', () => {
  for (const dataset of datasets().datasets) {
    const values = Object.values(dataset.records).map((r) => r.value);
    assert.ok(values.every((v) => Number.isFinite(v) && v >= 0), `${dataset.id} has a value that is not a rate`);
    assert.strictEqual(dataset.min, Math.min(...values), dataset.id);
    assert.strictEqual(dataset.max, Math.max(...values), dataset.id);
    assert.strictEqual(dataset.direction, 'higher-worse', dataset.id);
    assert.strictEqual(dataset.unit, 'reports a year per 1,000 sq mi of land', dataset.id);
    assert.strictEqual(dataset.period, '2006–2025 average', dataset.id);
  }
  const tornado = datasets().datasets[0];
  assert.ok(Object.values(tornado.records).some((r) => r.value === 0), 'no county at zero; zero tornado reports must read 0, not missing');
});

test('the note says what the number is not', () => {
  const payload = datasets();
  for (const dataset of payload.datasets) {
    assert.match(dataset.note, /reports/, dataset.id);
    assert.match(dataset.note, /more people/, dataset.id);
    assert.match(dataset.note, /forecast zone/, dataset.id);
    assert.match(dataset.note, /not a forecast/, dataset.id);
    assert.match(dataset.note, /does not endorse/, dataset.id);
  }
});

test('eight counties match the hand-worked rates', () => {
  const payload = datasets();
  for (const [fips, expected] of Object.entries(REFERENCE)) {
    for (const dataset of payload.datasets) {
      assert.strictEqual(dataset.records[fips].value, expected[KEY[dataset.id]], `${fips} ${dataset.id}`);
    }
  }
});

// A CSV parser for NOAA's quoted fields, which can hold commas and newlines.
function parseCsv(text) {
  const rows = [];
  let row = [], field = '', quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') { field += '"'; i++; }
      else if (c === '"') quoted = false;
      else field += c;
    } else if (c === '"') quoted = true;
    else if (c === ',') { row.push(field); field = ''; }
    else if (c === '\n') { row.push(field.replace(/\r$/, '')); rows.push(row); row = []; field = ''; }
    else field += c;
  }
  if (field || row.length) { row.push(field); rows.push(row); }
  return rows;
}

const stormFiles = fs.existsSync(sourceDir)
  ? fs.readdirSync(sourceDir).filter((f) => /^StormEvents_details-ftp_v1\.0_d20(0[6-9]|1\d|2[0-5])_c\d+\.csv\.gz$/.test(f)).sort()
  : [];
const sourceSkip = stormFiles.length === YEARS && fs.existsSync(path.join(sourceDir, '2021_Gaz_counties_national.txt'))
  ? false : 'put the 2006–2025 Storm Events files and the 2021 Gazetteer in work/storm-events/ first';

test('every county value re-derives from the raw NOAA files', { skip: sourceSkip }, () => {
  const atlas = new Set(readJson(path.join(root, 'dist', 'data', 'counties.geojson')).features.map((f) => f.properties.fips));
  const gazLines = fs.readFileSync(path.join(sourceDir, '2021_Gaz_counties_national.txt'), 'utf8').trim().split(/\r?\n/);
  const gazHeader = gazLines[0].split('\t').map((h) => h.trim());
  const area = {};
  for (const line of gazLines.slice(1)) {
    const cells = line.split('\t').map((c) => c.trim());
    area[cells[gazHeader.indexOf('GEOID')]] = Number(cells[gazHeader.indexOf('ALAND_SQMI')]);
  }
  const counts = {};
  for (const file of stormFiles) {
    const rows = parseCsv(zlib.gunzipSync(fs.readFileSync(path.join(sourceDir, file))).toString('latin1'));
    const header = rows[0];
    const col = (name) => header.indexOf(name);
    const [type, czType, state, cz] = ['EVENT_TYPE', 'CZ_TYPE', 'STATE_FIPS', 'CZ_FIPS'].map(col);
    for (const row of rows.slice(1)) {
      if (row.length < header.length) continue;
      const group = GROUP[row[type]];
      if (!group || row[czType] !== 'C') continue;
      let fips = row[state].padStart(2, '0') + row[cz].padStart(3, '0');
      if (fips === '51515') fips = '51019'; // Bedford city joined Bedford County in 2013
      if (!atlas.has(fips)) continue;
      const c = counts[fips] || (counts[fips] = { tornado: 0, hail: 0, wind: 0, flood: 0 });
      c[group]++;
    }
  }
  const rate = (n, fips) => Math.round((n / YEARS / (area[fips] / 1000)) * 100) / 100;
  const failures = [];
  for (const dataset of datasets().datasets) {
    for (const fips of atlas) {
      const c = counts[fips] || { tornado: 0, hail: 0, wind: 0, flood: 0 };
      const n = KEY[dataset.id] === 'total' ? c.tornado + c.hail + c.wind + c.flood : c[KEY[dataset.id]];
      const expected = rate(n, fips);
      if (Math.abs(dataset.records[fips].value - expected) > 0.005) failures.push(`${dataset.id} ${fips} ${dataset.records[fips].value} != ${expected}`);
    }
  }
  assert.deepStrictEqual(failures.slice(0, 5), [], `${failures.length} values disagree`);
});
