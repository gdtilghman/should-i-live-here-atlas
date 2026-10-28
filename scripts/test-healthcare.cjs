'use strict';
// Guards the four settled decisions behind the HPSA primary-care layer.
//
// Each of these was a judgement the user made on September 17, 2026, not a
// detail of the code, and each is the kind of thing a later rebuild could undo
// without anything looking wrong. The counts come from an independent pass over
// the source CSV, recorded in docs/enrichment-research.md.
//
// The layer is built by scripts/prepare-healthcare.py from an archive in the
// ignored work/ directory, so these skip until it has been run.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const layerPath = path.join(root, 'dist', 'data', 'healthcare.json');
const skip = fs.existsSync(layerPath) ? false : 'run scripts/prepare-healthcare.py first';

const layer = () => JSON.parse(fs.readFileSync(layerPath, 'utf8'));
const dataset = () => layer().datasets[0];

// Independently computed from BCD_HPSA_FCT_DET_PC.csv, not read back from the
// script's own output.
const EXPECTED = {
  total: 3107,
  available: 2809,
  notDesignated: 290,
  connecticut: 8,
  wholeCounty: 2162,
  subCounty: 647,
  minValue: 3,
  maxValue: 25,
};

test('every atlas county gets a record and none is invented', { skip }, () => {
  const records = dataset().records;
  const fips = Object.keys(records);
  assert.strictEqual(fips.length, EXPECTED.total,
    `expected ${EXPECTED.total} counties, got ${fips.length}`);
  const badFips = fips.filter((f) => !/^\d{5}$/.test(f));
  assert.deepStrictEqual(badFips, [], 'a record key is not a five-digit FIPS');
  // The literal XXXXX sentinel in the source means the county is undetermined.
  // It is five characters long, so a length test alone would let it through.
  assert.ok(!fips.includes('XXXXX'), 'the XXXXX sentinel became a county');
});

test('a value exists exactly when the status is available', { skip }, () => {
  // The invariant the whole project protects. not_designated is not zero and
  // is not evidence of adequate access.
  const records = Object.entries(dataset().records);
  for (const [fips, record] of records) {
    assert.strictEqual(record.status === 'available', record.value !== null
      && record.value !== undefined,
      `${fips}: status ${record.status} with value ${record.value}`);
  }
  const zeros = records.filter(([, r]) => r.value === 0);
  assert.deepStrictEqual(zeros.map(([f]) => f), [],
    'a county scored 0, which this source never means');
});

test('the four settled decisions are still in force', { skip }, () => {
  const records = dataset().records;
  const byStatus = {};
  for (const record of Object.values(records)) {
    byStatus[record.status] = (byStatus[record.status] || 0) + 1;
  }

  assert.strictEqual(byStatus.available, EXPECTED.available,
    `scored counties changed: ${byStatus.available}`);
  assert.strictEqual(byStatus.not_designated, EXPECTED.notDesignated,
    `not_designated changed: ${byStatus.not_designated}`);

  // Decision 3. Connecticut cannot join: the source uses 2022 planning regions
  // and the atlas uses legacy counties. Reading them as not designated would
  // state something the source never said.
  const ct = Object.entries(records).filter(([fips]) => fips.startsWith('09'));
  assert.strictEqual(ct.length, EXPECTED.connecticut, 'Connecticut county count changed');
  for (const [fips, record] of ct) {
    assert.strictEqual(record.status, 'unavailable',
      `${fips}: Connecticut must be unavailable, not ${record.status}`);
    assert.match(record.reason || '', /planning region/i,
      `${fips}: the Connecticut reason no longer explains the geography vintage`);
  }

  // Decision 2. A sub-county score describes part of a county, so the basis
  // travels with the value rather than being implied.
  const scored = Object.entries(records).filter(([, r]) => r.status === 'available');
  const whole = scored.filter(([, r]) => r.componentBasis === 'whole-county').length;
  const sub = scored.filter(([, r]) => r.componentBasis === 'sub-county').length;
  assert.strictEqual(whole, EXPECTED.wholeCounty, `whole-county basis changed: ${whole}`);
  assert.strictEqual(sub, EXPECTED.subCounty, `sub-county basis changed: ${sub}`);
  assert.strictEqual(whole + sub, scored.length,
    'a scored county has no componentBasis');

  // Decision 4. Proposed For Withdrawal is excluded from the score, but the
  // count travels so the exclusion is visible rather than silent.
  const missingCount = scored.filter(([, r]) => typeof r.proposedForWithdrawal !== 'number');
  assert.deepStrictEqual(missingCount.map(([f]) => f).slice(0, 5), [],
    'a scored county does not report its proposed-for-withdrawal count');
});

test('the layer says what the number is and is not', { skip }, () => {
  // An administrative priority score for clinician placement reads as a
  // measure of access unless the layer says otherwise.
  const collection = layer();
  const set = dataset();
  const notes = `${collection.note || ''} ${set.note || ''}`.toLowerCase();
  assert.match(notes, /not .*(supply|measure|access)/,
    'the note does not say what this number is not');
  assert.strictEqual(set.direction, 'higher-worse', 'direction changed');
  const values = Object.values(set.records)
    .filter((r) => r.status === 'available').map((r) => r.value);
  assert.strictEqual(Math.min(...values), EXPECTED.minValue, 'minimum score changed');
  assert.strictEqual(Math.max(...values), EXPECTED.maxValue, 'maximum score changed');
});
