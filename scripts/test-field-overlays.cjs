'use strict';
// Guards the air-monitor, climate-station and wildfire overlays built by
// scripts/prepare-field-overlays.py. Counts were checked by hand against the
// sources on October 28, 2026: every point dropped as outside the map is in
// Alaska, Hawaii, DC, Puerto Rico or Mexico, except 3 coastal stations
// (2 in Maryland, 1 in Florida) that fall outside the simplified coastline.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const dir = path.join(__dirname, '../dist/data/overlays');
const load = (name) => JSON.parse(fs.readFileSync(path.join(dir, name)));
const catalog = load('catalog.json');
const entry = (id) => catalog.overlays.find((o) => o.id === id);

test('the three overlays are registered after the older ones, which keep their dates', () => {
  assert.deepEqual(catalog.overlays.map((o) => o.id).slice(-3), ['airmonitors', 'stations', 'wildfires']);
  assert.equal(catalog.retrieved, '2026-10-05');
  for (const id of ['power', 'health', 'crashes', 'quakes', 'hospitals', 'epa']) assert.equal(entry(id).retrieved, '2026-10-05', id);
  assert.equal(entry('tri').retrieved, '2026-10-20');
  for (const id of ['airmonitors', 'stations', 'wildfires']) assert.equal(entry(id).retrieved, '2026-10-28', id);
});

test('air monitors: recent PM2.5 or ozone sites only', () => {
  const d = load('airmonitors.json');
  assert.equal(d.points.length, 1677);
  assert.deepEqual(d.excluded, { 'last sample before 2025': 5538, 'no sample date': 409, 'outside mapped lower-48 county geometry': 36 });
  assert.equal(d.audit['PM2.5 or ozone monitor records'], 8755);
  assert.ok(d.points.every((p) => /^AQS-\d{2}-\d{3}-\d{4}$/.test(p.id) && p.date >= '2025-01-01'));
  assert.ok(d.points.every((p) => p.groups.every((g) => ['PM2.5 monitor', 'Ozone monitor'].includes(g.type))));
  assert.match(entry('airmonitors').caveat, /not a county average/);
});

test('stations: US climate normals stations by network', () => {
  const d = load('stations.json');
  assert.equal(d.points.length, 15099);
  assert.deepEqual(d.excluded, { 'not a United States station': 123, 'outside mapped lower-48 county geometry': 393 });
  const types = new Set(d.points.map((p) => p.groups[0].type));
  assert.deepEqual([...types].sort(), ['CoCoRaHS volunteer precipitation station', 'Cooperative observer station', 'NRCS SNOTEL snow station', 'Weather Service or airport station']);
  assert.match(entry('stations').caveat, /precipitation only/);
});

test('wildfires: 2025 discoveries of 100 acres or more, as points of origin', () => {
  const d = load('wildfires.json');
  assert.equal(d.points.length, 1664);
  assert.deepEqual(d.excluded, { 'outside mapped lower-48 county geometry': 146 });
  assert.ok(d.points.every((p) => p.date.startsWith('2025-')));
  const sizes = {};
  for (const p of d.points) sizes[p.groups[0].type] = (sizes[p.groups[0].type] || 0) + 1;
  assert.deepEqual(Object.keys(sizes).sort(), ['1,000–9,999 acres', '10,000 acres or more', '100–999 acres']);
  assert.ok(d.points.every((p) => /not a burn perimeter/.test(p.notes)));
  assert.match(entry('wildfires').caveat, /not the area burned/);
});
