'use strict';
// Guards the crime layer, dist/data/crime.json, built by scripts/prepare-crime.py.
//
// The first tests need only the committed layer. The last ones read the
// ignored Return A files in work/crime/ with their own fixed-width parser,
// check Camden, DE against counts read from the FBI Crime Data API on
// October 28, 2026, and re-derive every county from the raw files and the
// builder's agency placement (work/crime/agency-county.json).
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const layerPath = path.join(root, 'dist', 'data', 'crime.json');
const sourceDir = path.join(root, 'work', 'crime');
const readJson = (file) => JSON.parse(fs.readFileSync(file, 'utf8'));
const NYC = ['36005', '36047', '36061', '36081', '36085'];
const YEARS = [2023, 2024, 2025];

function layer() {
  const payload = readJson(layerPath);
  assert.deepStrictEqual(payload.datasets.map((d) => d.id), ['violent-crime', 'property-crime']);
  return payload.datasets;
}

test('the crime layer covers the atlas; gaps are unavailable with a reason, never zero', () => {
  const atlas = readJson(path.join(root, 'dist', 'data', 'counties.geojson')).features.map((f) => f.properties.fips).sort();
  for (const dataset of layer()) {
    assert.deepStrictEqual(Object.keys(dataset.records).sort(), atlas);
    const statuses = {};
    for (const r of Object.values(dataset.records)) statuses[r.status] = (statuses[r.status] || 0) + 1;
    assert.deepStrictEqual(statuses, { available: 2195, unavailable: 912 });
    for (const r of Object.values(dataset.records)) {
      if (r.status === 'available') assert.ok(Number.isFinite(r.value) && r.value >= 0 && r.coverage >= 0.8 && r.coverage <= 1);
      else { assert.strictEqual(r.value, null); assert.ok(r.reason); }
    }
    assert.strictEqual(dataset.direction, 'higher-worse');
    assert.strictEqual(dataset.unit, 'crimes a year per 100,000 residents');
    assert.match(dataset.note, /advises against ranking/);
    assert.match(dataset.note, /does not endorse/);
  }
});

test('the five New York City boroughs share one citywide value', () => {
  for (const dataset of layer()) {
    const values = NYC.map((f) => dataset.records[f].value);
    assert.ok(values.every((v) => v === values[0] && v > 0), dataset.id);
    assert.ok(NYC.every((f) => /New York City/.test(dataset.records[f].reason)));
  }
});

test('known counties keep their values', () => {
  const [violent, property] = layer();
  const expected = { '10001': [441.0, 2145.6], '06037': [589.1, 2344.0], '29510': [1351.7, 5738.6], '24510': [1552.3, 4430.6], '51760': [397.5, 3434.8] };
  for (const [fips, [v, p]] of Object.entries(expected)) {
    assert.strictEqual(violent.records[fips].value, v, fips);
    assert.strictEqual(property.records[fips].value, p, fips);
  }
  assert.strictEqual(violent.records['22071'].status, 'unavailable', 'Orleans Parish reported for 34% of residents');
});

const HEADER = 305, BLOCK = 590;
const raw = (year) => path.join(sourceDir, `reta-${year}.txt`);
const sourceSkip = YEARS.every((y) => fs.existsSync(raw(y))) && fs.existsSync(path.join(sourceDir, 'agency-county.json'))
  ? false : 'put reta-2023..2025.txt in work/crime/ and run python scripts/prepare-crime.py first';

function* agencies(year) {
  const text = fs.readFileSync(raw(year), 'ascii');
  for (const line of text.split('\n')) if (line[0] === '1') yield line;
}
const num = (s) => Number(s.trim() || 0);
// COBOL overpunch: a letter in the last place carries the sign and digit.
const count = (s) => {
  const last = s[4], neg = '}JKLMNOPQR'.indexOf(last), pos = '{ABCDEFGHI'.indexOf(last);
  if (neg >= 0) return -Number(s.slice(0, 4) + neg);
  if (pos >= 0) return Number(s.slice(0, 4) + pos);
  assert.match(s, /^\d{5}$/);
  return Number(s);
};
function month(line, m) {
  const b = line.slice(HEADER + BLOCK * m, HEADER + BLOCK * (m + 1));
  const card = b.slice(17 + 140, 17 + 280); // actual offenses
  const f = (i) => count(card.slice(i * 5, i * 5 + 5));
  return {
    reported: !['', '0000'].includes(b.slice(3, 7).trim()),
    violent: f(0) + f(2) + f(5) + f(11) + f(12) + f(13) + f(14),
    property: f(16) + f(20) + f(21),
  };
}

test('Camden, DE matches the FBI Crime Data API by month', { skip: sourceSkip }, () => {
  const camden = [...agencies(2024)].find((l) => l.slice(3, 10) === 'DE00104');
  assert.deepStrictEqual([...Array(12).keys()].map((m) => month(camden, m).violent), [2, 1, 0, 1, 2, 1, 4, 1, 0, 0, 2, 1]);
  assert.strictEqual(num(camden.slice(44, 53)), 4364);
  const c2023 = [...agencies(2023)].find((l) => l.slice(3, 10) === 'DE00104');
  const sum = (l, k) => [...Array(12).keys()].reduce((a, m) => a + month(l, m)[k], 0);
  assert.strictEqual(sum(c2023, 'violent'), 17);
  assert.strictEqual(sum(c2023, 'property'), 214);
});

test('known agencies sit in the right county', { skip: sourceSkip }, () => {
  const placed = readJson(path.join(sourceDir, 'agency-county.json'));
  const expected = { DE00104: '10001', CA01942: '06037', NY03030: 'NYC', MOSPD00: '29510', TN01901: '47037', VA12200: '51760', OH01848: '39035' };
  for (const [ori, fips] of Object.entries(expected)) assert.strictEqual(placed[ori], fips, ori);
});

test('every county value re-derives from the raw files', { skip: sourceSkip }, () => {
  const placed = readJson(path.join(sourceDir, 'agency-county.json'));
  const totals = {};
  for (const year of YEARS) {
    for (const line of agencies(year)) {
      const unit = placed[line.slice(3, 10)];
      if (!unit) continue;
      const t = totals[unit] || (totals[unit] = { violent: 0, property: 0, covered: 0, residents: 0 });
      const pop = num(line.slice(44, 53)) + num(line.slice(59, 68)) + num(line.slice(74, 83));
      t.residents += pop;
      const months = [...Array(12).keys()].map((m) => month(line, m));
      if (!months.every((m) => m.reported)) continue;
      t.covered += pop;
      for (const m of months) { t.violent += m.violent; t.property += m.property; }
    }
  }
  const failures = [];
  for (const dataset of layer()) {
    const key = dataset.id === 'violent-crime' ? 'violent' : 'property';
    for (const [fips, record] of Object.entries(dataset.records)) {
      const t = totals[NYC.includes(fips) ? 'NYC' : fips];
      const ok = t && t.residents && t.covered / t.residents >= 0.8;
      const expected = ok ? Math.round((t[key] / t.covered) * 100000 * 10) / 10 : null;
      if (ok ? Math.abs(record.value - expected) > 0.05 : record.status !== 'unavailable') failures.push(`${dataset.id} ${fips} ${record.value} != ${expected}`);
    }
  }
  assert.deepStrictEqual(failures.slice(0, 5), [], `${failures.length} values disagree`);
});
