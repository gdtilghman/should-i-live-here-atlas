import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { normalizeTerms, logMissing, SCHEMA, UPSERT, CLIENT_UPSERT } from '../src/log.js';
import { fakeD1 } from './helpers.mjs';

const DAY = new Date('2026-11-02T23:59:59Z');
const MCPBEAT = 'mcpbeat/0.1 (+https://mcpbeat.com/bot/; liveness check)';

test('schema and upserts are exact and store no personal data', () => {
  assert.equal(SCHEMA, 'CREATE TABLE IF NOT EXISTS missing_requests (day TEXT NOT NULL, term TEXT NOT NULL, count INTEGER NOT NULL DEFAULT 1, PRIMARY KEY (day, term))');
  assert.equal(UPSERT, 'INSERT INTO missing_requests (day, term, count) VALUES (?1, ?2, 1) ON CONFLICT (day, term) DO UPDATE SET count = count + 1');
  assert.equal(CLIENT_UPSERT, 'INSERT INTO missing_request_clients (day, term, client, kind, count) VALUES (?1, ?2, ?3, ?4, 1) ON CONFLICT (day, term, client) DO UPDATE SET count = count + 1, kind = excluded.kind');
});

test('migration creates the client table with the agreed shape', () => {
  const sql = fs.readFileSync(new URL('../migrations/0001_missing_request_clients.sql', import.meta.url), 'utf8');
  const body = sql.replace(/--.*$/gm, '').replace(/\s+/g, ' ').trim();
  assert.equal(body, 'CREATE TABLE IF NOT EXISTS missing_request_clients ( day TEXT NOT NULL, term TEXT NOT NULL, client TEXT NOT NULL, kind TEXT NOT NULL, count INTEGER NOT NULL DEFAULT 1, PRIMARY KEY (day, term, client) );');
});

test('terms are cleaned, shortened, deduplicated and capped', () => {
  assert.deepEqual(normalizeTerms(['  Best   Schools ', 'best schools', 'SCHOOLS', '', null, 42]), ['best schools', 'schools']);
  assert.equal(normalizeTerms(['x'.repeat(80)])[0].length, 60);
  assert.deepEqual(normalizeTerms(['a', 'b', 'c', 'd', 'e', 'f', 'g']), ['a', 'b', 'c', 'd', 'e']);
  assert.deepEqual(normalizeTerms('not an array'), []);
});

test('an agent request writes both tables, by UTC day', async () => {
  const d1 = fakeD1();
  const n = await logMissing(d1, ['Schools', 'cost of living index'], { ua: 'Claude-User (claude-code)', now: DAY });
  assert.equal(n, 2);
  assert.deepEqual(d1.calls, [
    { sql: UPSERT, args: ['2026-11-02', 'schools'] },
    { sql: UPSERT, args: ['2026-11-02', 'cost of living index'] },
    { sql: CLIENT_UPSERT, args: ['2026-11-02', 'schools', 'Claude-User', 'agent'] },
    { sql: CLIENT_UPSERT, args: ['2026-11-02', 'cost of living index', 'Claude-User', 'agent'] },
  ]);
});

test('junk terms reach only the client table', async () => {
  const d1 = fakeD1();
  const n = await logMissing(d1, ['audit-fixture', 'schools'], { ua: 'python-httpx/0.28.1', now: DAY });
  assert.equal(n, 1);
  assert.deepEqual(d1.calls, [
    { sql: UPSERT, args: ['2026-11-02', 'schools'] },
    { sql: CLIENT_UPSERT, args: ['2026-11-02', 'audit-fixture', 'python-httpx/0.28.1', 'agent'] },
    { sql: CLIENT_UPSERT, args: ['2026-11-02', 'schools', 'python-httpx/0.28.1', 'agent'] },
  ]);
});

test('probe requests reach only the client table', async () => {
  const d1 = fakeD1();
  const n = await logMissing(d1, ['schools'], { ua: MCPBEAT, now: DAY });
  assert.equal(n, 0);
  assert.deepEqual(d1.calls, [
    { sql: CLIENT_UPSERT, args: ['2026-11-02', 'schools', 'mcpbeat/0.1', 'probe'] },
  ]);
});

test('a missing user agent is logged as unknown and still counted', async () => {
  const d1 = fakeD1();
  assert.equal(await logMissing(d1, ['schools'], { now: DAY }), 1);
  assert.deepEqual(d1.calls[1], { sql: CLIENT_UPSERT, args: ['2026-11-02', 'schools', 'unknown', 'unknown'] });
});

test('a failing client table does not block missing_requests', async () => {
  const calls = [];
  const d1 = {
    prepare: sql => ({ bind: (...args) => ({ sql, args }) }),
    async batch(statements) {
      if (statements[0].sql === CLIENT_UPSERT) throw new Error('no such table: missing_request_clients');
      calls.push(...statements);
    },
  };
  assert.equal(await logMissing(d1, ['schools'], { ua: 'Claude-User', now: DAY }), 1);
  assert.deepEqual(calls, [{ sql: UPSERT, args: ['2026-11-02', 'schools'] }]);
});

test('logging never breaks an answer', async () => {
  assert.equal(await logMissing(undefined, ['schools']), 0);
  assert.equal(await logMissing(fakeD1({ fail: true }), ['schools']), 0);
  const d1 = fakeD1();
  assert.equal(await logMissing(d1, []), 0);
  assert.equal(d1.calls.length, 0);
});
