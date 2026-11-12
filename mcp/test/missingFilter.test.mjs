import test from 'node:test';
import assert from 'node:assert/strict';
import { isProbeClient, isJunkTerm, clientToken, classifyClient } from '../src/missingFilter.js';

test('known automated checkers are probes', () => {
  for (const ua of [
    'mcpbeat/0.1 (+https://mcpbeat.com/bot/; liveness check)',
    'MCPBEAT/2',
    'alalanet-prober/1.0',
    'addrbook-probe',
    'MCPStationBot/3.1',
    'ProofBench/0.9',
    'AgentRankProbe',
    'AnnalistChecks/1',
    'histor/1.2',
    'Mozilla/5.0 (compatible; mcptry.com checker)',
    'PulseFeed/4',
    'BrickBlueBot',
    'Moonglade/1.0',
    'lowdown-scanner/2',
    'FACTANKER',
    'some-uptime-probe',
    'acme-crawler/1',
    'Example-Scanner',
    'k8s-liveness',
    'HealthChecker/1.0',
  ]) assert.equal(isProbeClient(ua), true, ua);
});

test('AI apps and plain HTTP clients are not probes', () => {
  for (const ua of [
    'Claude-User',
    'Claude-User (claude-code/2.1.0; +https://support.anthropic.com/)',
    'python-httpx/0.28.1',
    'node',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140.0 Safari/537.36',
    '',
  ]) assert.equal(isProbeClient(ua), false, ua);
  assert.equal(isProbeClient(undefined), false);
  assert.equal(isProbeClient(null), false);
});

test('placeholder and test terms are junk', () => {
  for (const term of [
    'audit-fixture', 'test fixture', 'dummy measure', 'placeholder', 'lorem ipsum',
    'foo', 'bar', 'foobar', 'foo bar', 'foo-measure', 'my_bar',
    'test', 'example', 'string', 'sample', 'xxx', 'asdf', ' TEST ', 'Example',
    '', ' ', 'a', 'x'.repeat(81),
  ]) assert.equal(isJunkTerm(term), true, JSON.stringify(term));
  assert.equal(isJunkTerm(undefined), true);
  assert.equal(isJunkTerm(42), true);
});

test('real measure requests are not junk', () => {
  for (const term of [
    'schools', 'cost of living index', 'food deserts', 'food access', 'barbershops',
    'embargo', 'test scores', 'sample size', 'example schools', 'ok', 'x'.repeat(80),
  ]) assert.equal(isJunkTerm(term), false, term);
});

test('client is the first user-agent product token, max 80 characters', () => {
  assert.equal(clientToken('Claude-User'), 'Claude-User');
  assert.equal(clientToken('mcpbeat/0.1 (+https://mcpbeat.com/bot/; liveness check)'), 'mcpbeat/0.1');
  assert.equal(clientToken('  python-httpx/0.28.1  '), 'python-httpx/0.28.1');
  assert.equal(clientToken('a'.repeat(120) + ' extra'), 'a'.repeat(80));
  assert.equal(clientToken(''), 'unknown');
  assert.equal(clientToken('   '), 'unknown');
  assert.equal(clientToken(undefined), 'unknown');
});

test('classifyClient gives client and kind', () => {
  assert.deepEqual(classifyClient('Claude-User'), { client: 'Claude-User', kind: 'agent' });
  assert.deepEqual(classifyClient('mcpbeat/0.1 (+https://mcpbeat.com/bot/; liveness check)'), { client: 'mcpbeat/0.1', kind: 'probe' });
  // The probe word sits after the product token; the full string is checked.
  assert.deepEqual(classifyClient('Go-http-client/1.1 (uptime probe)'), { client: 'Go-http-client/1.1', kind: 'probe' });
  assert.deepEqual(classifyClient(''), { client: 'unknown', kind: 'unknown' });
  assert.deepEqual(classifyClient(null), { client: 'unknown', kind: 'unknown' });
});
