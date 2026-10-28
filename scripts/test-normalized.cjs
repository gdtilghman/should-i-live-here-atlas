'use strict';
// Proves the Python normalizer produces the same scores as the browser.
//
// dist/composite.js is what a visitor's score is computed with today.
// scripts/build-normalized.py exists so a future SQL ranking layer does not
// have to recompute distribution statistics on every query. The two must agree
// exactly, or a ranked answer would disagree with the map it came from, and
// only a test keeps a Python file and a JavaScript file in step.
//
// Run scripts/build-normalized.py first; its output is generated.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const dataDir = path.join(root, 'dist', 'data');
const normalizedPath = path.join(dataDir, 'normalized.json');
const composite = require(path.join(root, 'dist', 'composite.js'));

const skip = fs.existsSync(normalizedPath) ? false : 'run scripts/build-normalized.py first';
const FAMILIES = ['cancer', 'disasters', 'community', 'hazards', 'healthcare', 'employment', 'broadband', 'places', 'air', 'wildfire', 'water', 'traffic', 'climate', 'storms', 'crime'];

const readJson = (file) => JSON.parse(fs.readFileSync(file, 'utf8'));

test('the Python scale statistics match the browser', { skip }, () => {
  const normalized = readJson(normalizedPath);
  assert.strictEqual(normalized.format, 'normalized-v1', 'unexpected output format');

  let datasets = 0;
  for (const family of FAMILIES) {
    const source = readJson(path.join(dataDir, `${family}.json`));
    const built = normalized.families[family];
    assert.ok(built, `${family} is missing from the normalized output`);
    assert.strictEqual(built.datasets.length, source.datasets.length,
      `${family} dataset count differs`);

    for (let i = 0; i < source.datasets.length; i++) {
      const dataset = source.datasets[i];
      const entry = built.datasets[i];
      assert.strictEqual(entry.id, dataset.id, `${family} dataset order differs`);
      const expected = composite.scaleStats(dataset);
      const label = `${family}/${dataset.id}`;

      // Both languages use IEEE-754 doubles and the same sequence of
      // operations, so these are compared exactly. A tolerance here would hide
      // a real difference in the quantile or the fence.
      for (const key of ['min', 'max', 'fence', 'count', 'reversed', 'hasExtremes', 'notApplicableBestCase']) {
        assert.strictEqual(entry.stats[key], expected[key] === undefined ? null : expected[key],
          `${label}: stats.${key} is ${entry.stats[key]}, browser gives ${expected[key]}`);
      }
      datasets++;
    }
  }
  assert.strictEqual(datasets, 73, `expected 73 datasets, compared ${datasets}`);
});

test('every county score matches the browser', { skip }, () => {
  const normalized = readJson(normalizedPath);
  let records = 0;
  let scored = 0;
  const failures = [];

  for (const family of FAMILIES) {
    const source = readJson(path.join(dataDir, `${family}.json`));
    const built = normalized.families[family];
    for (let i = 0; i < source.datasets.length; i++) {
      const dataset = source.datasets[i];
      const stats = composite.scaleStats(dataset);
      const entry = built.datasets[i];
      const fipsKeys = Object.keys(dataset.records || {});
      assert.strictEqual(Object.keys(entry.records).length, fipsKeys.length,
        `${family}/${dataset.id}: record count differs`);

      for (const fips of fipsKeys) {
        records++;
        const expected = composite.component(dataset.records[fips], stats);
        const actual = entry.records[fips];
        assert.ok(actual, `${family}/${dataset.id}/${fips} is missing`);
        const want = expected.value === null ? null : expected.value;
        if (actual.scaled !== want || actual.extreme !== expected.extreme) {
          failures.push(`${family}/${dataset.id}/${fips}: ${actual.scaled}/${actual.extreme} ` +
            `against ${want}/${expected.extreme}`);
        }
        if (actual.scaled !== null) scored++;
      }
    }
  }

  assert.deepStrictEqual(failures.slice(0, 5), [],
    `${failures.length} records disagree with the browser`);
  assert.strictEqual(records, 226811, `expected 226,811 records, compared ${records}`);
  // 103,008 measured records, 2,809 of them healthcare and 3,106 heat, 3,053 air and 54 air unavailable, plus
  // the 3,497 not-applicable readings that hurricane, coastal flooding and ice
  // storm declare a best case. Plus 15,535 severe storm records, all measured, and 4,390 crime records.
  assert.strictEqual(scored, 219628, `expected 219,628 scored records, saw ${scored}`);
});

test('an unavailable record scores null, never zero', { skip }, () => {
  // The distinction this whole project protects. A ranking that scored a
  // missing input as zero would place a county first or last for having no
  // data, which is the most likely way this becomes confidently wrong.
  //
  // The one exception is declared by the dataset, never inferred: hurricane
  // not-applicable means no exposure, and scores 0. It is counted separately
  // so that it cannot spread to another status or another dataset unseen.
  const normalized = readJson(normalizedPath);
  let checked = 0;
  const assumed = {};
  for (const family of FAMILIES) {
    const source = readJson(path.join(dataDir, `${family}.json`));
    const built = normalized.families[family];
    for (let i = 0; i < source.datasets.length; i++) {
      const records = source.datasets[i].records || {};
      const entry = built.datasets[i].records;
      for (const [fips, record] of Object.entries(records)) {
        const usable = record.status === 'available' && Number.isFinite(record.value);
        const declared = record.status === 'not-applicable'
          && source.datasets[i].notApplicableMeans === 'best-case';
        if (declared) {
          assert.strictEqual(entry[fips].scaled, 0,
            `${family}/${source.datasets[i].id}/${fips}: declared best case scored ${entry[fips].scaled}`);
          const key = `${family}:${source.datasets[i].id}`;
          assumed[key] = (assumed[key] || 0) + 1;
          continue;
        }
        assert.strictEqual(entry[fips].scaled === null, !usable,
          `${family}/${source.datasets[i].id}/${fips}: status ${record.status} scored ` +
          `${entry[fips].scaled}`);
        if (!usable) checked++;
      }
    }
  }
  // 290 of these are healthcare not_designated, which is not evidence of
  // adequate access and so stays unscored.
  // Plus Lexington city, which NOAA does not publish, the legacy
  // Connecticut counties that BLS and CDC PLACES report as planning regions,
  // and 54 air counties unavailable (49 missing, 5 without population-weighted values).
  // Plus 1,824 crime records in counties under the 80% reporting rule.
  assert.strictEqual(checked, 7183, `expected 7,183 unscored records, saw ${checked}`);
  assert.deepStrictEqual(assumed, { 'hazards:nri-hurricane': 717, 'hazards:nri-coastal-flooding': 2639, 'hazards:nri-ice-storm': 141 },
    'only hurricane, coastal flooding and ice storm may treat not-applicable as a best case');
});
