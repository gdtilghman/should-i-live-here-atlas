'use strict';
// The MCP server reads packed copies of the layer files. Every packed value
// and status must match the layer files exactly, and missing stays missing.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..');
const out = path.join(root, 'mcp', 'src', 'data');
const built = ['counties.json', 'measures.json', 'values.bin', 'status.bin'].every(f => fs.existsSync(path.join(out, f)));
const skip = built ? false : 'run python scripts/build-mcp-data.py first';
const read = f => JSON.parse(fs.readFileSync(path.join(root, f), 'utf8'));
const STATUS = ['available', 'suppressed', 'unavailable', 'not-applicable', 'policy', 'not_designated'];

test('counties match the map file, in FIPS order', { skip }, () => {
  const counties = JSON.parse(fs.readFileSync(path.join(out, 'counties.json'), 'utf8'));
  const geo = read('dist/data/counties.qd.json');
  const traffic = read('dist/data/layers/traffic-deaths-2019-2023.json').records;
  const pop = fips => Number.isFinite(traffic[fips]?.population) ? traffic[fips].population : null;
  const expected = geo.features.map(f => ({ fips: f.p[0], state: f.p[1], name: f.p[2], stateName: f.p[3], population: pop(f.p[0]) }))
    .sort((a, b) => a.fips < b.fips ? -1 : 1);
  assert.equal(counties.length, 3107);
  assert.deepEqual(counties, expected);
  assert.equal(counties.filter(c => c.population === null).length, 8, 'the 8 legacy Connecticut counties');
  assert.equal(counties.find(c => c.fips === '48377').population, 6043);
});

test('measures follow the manifest, with no extras', { skip }, () => {
  const packed = JSON.parse(fs.readFileSync(path.join(out, 'measures.json'), 'utf8'));
  const manifest = read('dist/data/layers/manifest.json');
  assert.equal(packed.countyCount, 3107);
  assert.equal(packed.version, manifest.version);
  assert.deepEqual(packed.statusCodes, STATUS);
  assert.deepEqual(packed.population, { source: 'US Census Bureau American Community Survey, 2019-2023 5-year estimates, table B01003', from: 'traffic:deaths-2019-2023' });
  const expected = [];
  for (const [family, entry] of Object.entries(manifest.families))
    for (const d of entry.datasets) expected.push({ family, d, entry });
  assert.equal(packed.measures.length, 73);
  assert.equal(expected.length, 73);
  packed.measures.forEach((m, i) => {
    const { family, d, entry } = expected[i];
    assert.equal(m.index, i);
    assert.equal(m.key, `${family}:${d.id}`);
    assert.equal(m.family, family);
    assert.equal(m.id, d.id);
    assert.equal(m.title, d.title);
    assert.equal(m.unit, d.unit);
    assert.equal(m.period, d.period);
    assert.equal(m.direction, d.direction || 'higher-worse', m.key);
    assert.equal(m.notApplicableMeans, d.notApplicableMeans || null, m.key);
    assert.equal(m.sex, d.sex || null, m.key);
    assert.equal(m.sourceUrl, d.sourceUrl || entry.sourceUrl || '', m.key);
    assert.equal(m.citation, d.citation || entry.citation || '', m.key);
    assert.equal(m.note, d.note || '', m.key);
    assert.equal(m.familyNote, entry.note || '', m.key);
  });
  const crime = packed.measures.find(m => m.key === 'crime:violent-crime');
  assert.match(crime.note, /The FBI advises against ranking places with these data\./);
});

test('every packed value and status matches its layer file', { skip }, () => {
  const packed = JSON.parse(fs.readFileSync(path.join(out, 'measures.json'), 'utf8'));
  const counties = JSON.parse(fs.readFileSync(path.join(out, 'counties.json'), 'utf8'));
  const manifest = read('dist/data/layers/manifest.json');
  const n = counties.length;
  const vbuf = fs.readFileSync(path.join(out, 'values.bin'));
  const sbuf = fs.readFileSync(path.join(out, 'status.bin'));
  assert.equal(vbuf.length, 73 * n * 8);
  assert.equal(sbuf.length, 73 * n);
  const values = new Float64Array(vbuf.buffer.slice(vbuf.byteOffset, vbuf.byteOffset + vbuf.length));
  let available = 0, missing = 0;
  for (const m of packed.measures) {
    const file = manifest.families[m.family].datasets.find(d => d.id === m.id).file;
    const layer = read(`dist/data/layers/${file}`);
    counties.forEach((c, ci) => {
      const r = layer.records[c.fips];
      const i = m.index * n + ci;
      const ok = r && r.status === 'available' && Number.isFinite(r.value);
      if (ok) {
        available++;
        assert.equal(sbuf[i], 0, `${m.key} ${c.fips}`);
        assert.equal(values[i], r.value, `${m.key} ${c.fips}`);
      } else {
        missing++;
        assert.ok(Number.isNaN(values[i]), `${m.key} ${c.fips} must be NaN, never zero`);
        const status = r ? (r.status === 'available' ? 'unavailable' : r.status) : 'unavailable';
        assert.equal(STATUS[sbuf[i]], status, `${m.key} ${c.fips}`);
      }
    });
  }
  assert.equal(available + missing, 73 * 3107);
  assert.equal(available, 216131);
});
