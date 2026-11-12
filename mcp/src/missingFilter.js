// Pure rules that keep automated traffic and placeholder words out of the
// missing-measure counts. No I/O. The full user-agent string is read here
// but never stored; only its first product token is kept.

const PROBE_NAMES = [
  'mcpbeat', 'alalanet-prober', 'addrbook-probe', 'mcpstationbot', 'proofbench',
  'agentrankprobe', 'annalistchecks', 'histor/', 'mcptry.com', 'pulsefeed',
  'brickbluebot', 'moonglade', 'lowdown-scanner', 'factanker',
];
const PROBE_WORDS = ['probe', 'prober', 'scanner', 'crawler', 'liveness', 'health'];

const JUNK_PARTS = ['fixture', 'dummy', 'placeholder', 'lorem'];
// "foo" and "bar" count only as whole words, so "food access" and
// "barbershops" stay real requests.
const JUNK_WORDS = /(^|[^a-z])(foo|bar|foobar)([^a-z]|$)/;
const JUNK_EXACT = new Set(['test', 'example', 'string', 'sample', 'xxx', 'asdf']);

const MAX_CLIENT = 80;
const MAX_TERM = 80;

// True for known automated checkers (uptime, registry and scanner bots).
export function isProbeClient(ua) {
  if (typeof ua !== 'string' || !ua) return false;
  const s = ua.toLowerCase();
  return PROBE_NAMES.some(n => s.includes(n)) || PROBE_WORDS.some(w => s.includes(w));
}

// True for placeholder or test values that are not real measure requests.
export function isJunkTerm(term) {
  if (typeof term !== 'string') return true;
  const t = term.trim().toLowerCase();
  if (t.length < 2 || t.length > MAX_TERM) return true;
  if (JUNK_EXACT.has(t)) return true;
  return JUNK_PARTS.some(p => t.includes(p)) || JUNK_WORDS.test(t);
}

// The first product token of a user agent, for example "Claude-User" or
// "python-httpx/0.28.1". Empty or missing gives "unknown".
export function clientToken(ua) {
  const token = typeof ua === 'string' ? ua.trim().split(/\s+/)[0] : '';
  return token ? token.slice(0, MAX_CLIENT) : 'unknown';
}

// client and kind ("probe", "agent" or "unknown") for one request.
export function classifyClient(ua) {
  const client = clientToken(ua);
  if (client === 'unknown') return { client, kind: 'unknown' };
  return { client, kind: isProbeClient(ua) ? 'probe' : 'agent' };
}
