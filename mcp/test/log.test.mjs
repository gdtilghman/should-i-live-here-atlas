import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeTerms, logMissing, SCHEMA, UPSERT } from '../src/log.js';
import { fakeD1 } from './helpers.mjs';

test('schema and upsert are exact and store no personal data', () => {
  assert.equal(SCHEMA, 'CREATE TABLE IF NOT EXISTS missing_requests (day TEXT NOT NULL, term TEXT NOT NULL, count INTEGER NOT NULL DEFAULT 1, PRIMARY KEY (day, term))');
  assert.equal(UPSERT, 'INSERT INTO missing_requests (day, term, count) VALUES (?1, ?2, 1) ON CONFLICT (day, term) DO UPDATE SET count = count + 1');
});

test('terms are cleaned, shortened, deduplicated and capped', () => {
  assert.deepEqual(normalizeTerms(['  Best   Schools ', 'best schools', 'SCHOOLS', '', null, 42]), ['best schools', 'schools']);
  assert.equal(normalizeTerms(['x'.repeat(80)])[0].length, 60);
  assert.deepEqual(normalizeTerms(['a', 'b', 'c', 'd', 'e', 'f', 'g']), ['a', 'b', 'c', 'd', 'e']);
  assert.deepEqual(normalizeTerms('not an array'), []);
});

test('logMissing writes one row per term in one batch, by UTC day', async () => {
  const d1 = fakeD1();
  const n = await logMissing(d1, ['Schools', 'cost of living index'], new Date('2026-11-02T23:59:59Z'));
  assert.equal(n, 2);
  assert.deepEqual(d1.calls, [
    { sql: UPSERT, args: ['2026-11-02', 'schools'] },
    { sql: UPSERT, args: ['2026-11-02', 'cost of living index'] },
  ]);
});

test('logging never breaks an answer', async () => {
  assert.equal(await logMissing(undefined, ['schools']), 0);
  assert.equal(await logMissing(fakeD1({ fail: true }), ['schools']), 0);
  const d1 = fakeD1();
  assert.equal(await logMissing(d1, []), 0);
  assert.equal(d1.calls.length, 0);
});
