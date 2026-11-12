// Counts requests for measures the atlas lacks, so the owner can see which
// data layers people want. Stores the term, the UTC day and the client app
// name (first user-agent product token): no prompt, IP address, full
// user-agent string or other personal data. A logging failure never breaks
// an answer.
import { classifyClient, isJunkTerm } from './missingFilter.js';

export const SCHEMA = 'CREATE TABLE IF NOT EXISTS missing_requests (day TEXT NOT NULL, term TEXT NOT NULL, count INTEGER NOT NULL DEFAULT 1, PRIMARY KEY (day, term))';
export const UPSERT = 'INSERT INTO missing_requests (day, term, count) VALUES (?1, ?2, 1) ON CONFLICT (day, term) DO UPDATE SET count = count + 1';
// Table made by migrations/0001_missing_request_clients.sql.
export const CLIENT_UPSERT = 'INSERT INTO missing_request_clients (day, term, client, kind, count) VALUES (?1, ?2, ?3, ?4, 1) ON CONFLICT (day, term, client) DO UPDATE SET count = count + 1, kind = excluded.kind';

const MAX_TERMS = 5;
const MAX_LENGTH = 60;

export function normalizeTerms(terms) {
  if (!Array.isArray(terms)) return [];
  const seen = new Set();
  for (const t of terms) {
    if (typeof t !== 'string') continue;
    const term = t.toLowerCase().replace(/\s+/g, ' ').trim().slice(0, MAX_LENGTH);
    if (term) seen.add(term);
    if (seen.size === MAX_TERMS) break;
  }
  return [...seen];
}

async function run(d1, statements) {
  if (!statements.length) return 0;
  try {
    await d1.batch(statements);
    return statements.length;
  } catch {
    return 0;
  }
}

// Every term goes to missing_request_clients, so probes stay visible there.
// missing_requests gets only real terms from clients that are not probes.
// The two writes are separate, so one failing table never blocks the other.
// Returns how many missing_requests rows were written.
export async function logMissing(d1, terms, { ua = '', now = new Date() } = {}) {
  const clean = normalizeTerms(terms);
  if (!d1 || !clean.length) return 0;
  const day = now.toISOString().slice(0, 10);
  const { client, kind } = classifyClient(ua);
  const kept = kind === 'probe' ? [] : clean.filter(term => !isJunkTerm(term));
  const [written] = await Promise.all([
    run(d1, kept.map(term => d1.prepare(UPSERT).bind(day, term))),
    run(d1, clean.map(term => d1.prepare(CLIENT_UPSERT).bind(day, term, client, kind))),
  ]);
  return written;
}
