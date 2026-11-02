// Counts requests for measures the atlas lacks, so the owner can see which
// data layers people want. Stores the term and the UTC day only: no prompt,
// IP address or other personal data. A logging failure never breaks an answer.

export const SCHEMA = 'CREATE TABLE IF NOT EXISTS missing_requests (day TEXT NOT NULL, term TEXT NOT NULL, count INTEGER NOT NULL DEFAULT 1, PRIMARY KEY (day, term))';
export const UPSERT = 'INSERT INTO missing_requests (day, term, count) VALUES (?1, ?2, 1) ON CONFLICT (day, term) DO UPDATE SET count = count + 1';

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

export async function logMissing(d1, terms, now = new Date()) {
  const clean = normalizeTerms(terms);
  if (!d1 || !clean.length) return 0;
  const day = now.toISOString().slice(0, 10);
  try {
    await d1.batch(clean.map(term => d1.prepare(UPSERT).bind(day, term)));
    return clean.length;
  } catch {
    return 0;
  }
}
