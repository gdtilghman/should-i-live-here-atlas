'use strict';
// Node tests for the pure spatial overlay helpers in dist/overlay-spatial.js.
// These exercise the shipped module directly (no production-only hooks). The
// browser global (window.AtlasOverlaySpatial) is covered by a separate check.
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const spatial = require(path.join(__dirname, '..', 'dist', 'overlay-spatial.js'));
const { clusterPoints, normalizeCustomPins } = spatial;

test('exports clusterPoints and normalizeCustomPins', () => {
  assert.equal(typeof clusterPoints, 'function');
  assert.equal(typeof normalizeCustomPins, 'function');
});

test('clusterPoints includes the padded viewport edges and rejects beyond them', () => {
  const width = 400, height = 300, cellSize = 40, padding = 20;
  const points = [
    { id: 'origin', x: 0, y: 0 },
    { id: 'corner', x: width, y: height },
    { id: 'padded-max', x: width + padding, y: height + padding },
    { id: 'padded-min', x: -padding, y: -padding },
    { id: 'beyond-x', x: width + padding + 1, y: 0 },
    { id: 'beyond-y', x: 0, y: height + padding + 1 },
    { id: 'below-x', x: -padding - 1, y: 0 },
    { id: 'below-y', x: 0, y: -padding - 1 }
  ];
  const ids = [];
  for (const cluster of clusterPoints(points, { width, height, cellSize, padding })) {
    for (const member of cluster.members) ids.push(member.id);
  }
  assert.deepEqual(ids.sort(), ['corner', 'origin', 'padded-max', 'padded-min']);
});

test('clusterPoints padding controls how far outside the viewport is kept', () => {
  const width = 100, height = 100, cellSize = 40;
  const points = [{ id: 'near', x: -1, y: 10 }];
  assert.deepEqual(clusterPoints(points, { width, height, cellSize, padding: 0 }), []);
  const kept = clusterPoints(points, { width, height, cellSize, padding: 20 });
  assert.equal(kept.length, 1);
  assert.deepEqual(kept[0].members.map(m => m.id), ['near']);
});

test('clusterPoints buckets by cell and orders cells by index', () => {
  const options = { width: 400, height: 300, cellSize: 40, padding: 20 };
  const points = [
    { id: 'a', x: 5, y: 5 },     // cell (0,0)
    { id: 'b', x: 39, y: 39 },   // cell (0,0)
    { id: 'c', x: 40, y: 40 },   // cell (1,1)
    { id: 'd', x: 41, y: 5 }     // cell (1,0)
  ];
  const clusters = clusterPoints(points, options);
  assert.deepEqual(clusters.map(c => c.id), ['cell:0:0', 'cell:1:0', 'cell:1:1']);
  assert.deepEqual(clusters.map(c => c.count), [2, 1, 1]);
  assert.deepEqual(clusters[0].members.map(m => m.id), ['a', 'b']);
});

test('clusterPoints keeps coincident points inspectable in one cluster', () => {
  const options = { width: 400, height: 300, cellSize: 40, padding: 20 };
  const p1 = { id: 'plant-1', x: 123.5, y: 88.25, name: 'Alpha' };
  const p2 = { id: 'plant-2', x: 123.5, y: 88.25, name: 'Beta' };
  const clusters = clusterPoints([p1, p2], options);
  assert.equal(clusters.length, 1);
  assert.equal(clusters[0].count, 2);
  assert.equal(clusters[0].x, 123.5);
  assert.equal(clusters[0].y, 88.25);
  assert.equal(clusters[0].members[0], p1);
  assert.equal(clusters[0].members[1], p2);
});

test('clusterPoints averages members and retains singletons as count 1', () => {
  const options = { width: 400, height: 300, cellSize: 40, padding: 20 };
  const clusters = clusterPoints([
    { id: 'a', x: 4, y: 10 },
    { id: 'b', x: 8, y: 20 },
    { id: 'solo', x: 200, y: 200 }
  ], options);
  assert.equal(clusters[0].count, 2);
  assert.equal(clusters[0].x, 6);
  assert.equal(clusters[0].y, 15);
  assert.equal(clusters[1].count, 1);
  assert.equal(clusters[1].x, 200);
  assert.equal(clusters[1].y, 200);
});

test('clusterPoints output is identical regardless of input ordering', () => {
  const options = { width: 400, height: 300, cellSize: 40, padding: 20 };
  const points = [
    { id: 'z', x: 5, y: 5 }, { id: 'a', x: 7, y: 9 }, { id: 'm', x: 45, y: 5 },
    { id: 'q', x: 200, y: 100 }, { id: 'b', x: 6, y: 4 }
  ];
  const shape = clusters => clusters.map(c => ({
    id: c.id, x: c.x, y: c.y, count: c.count, members: c.members.map(m => m.id)
  }));
  const forward = shape(clusterPoints(points, options));
  const reversed = shape(clusterPoints(points.slice().reverse(), options));
  assert.deepEqual(forward, reversed);
});

test('clusterPoints does not mutate its input array or point objects', () => {
  const options = { width: 400, height: 300, cellSize: 40, padding: 20 };
  const points = [
    { id: 'z', x: 5, y: 5, extra: 1 },
    { id: 'a', x: 6, y: 6, extra: 2 }
  ];
  const orderBefore = points.map(p => p.id);
  const snapshot = JSON.parse(JSON.stringify(points));
  const clusters = clusterPoints(points, options);
  assert.deepEqual(points.map(p => p.id), orderBefore);
  assert.deepEqual(JSON.parse(JSON.stringify(points)), snapshot);
  assert.equal(clusters[0].members[0], points[1]);
  assert.equal(clusters[0].members[1], points[0]);
});

test('clusterPoints returns [] for invalid options', () => {
  const points = [{ id: 'a', x: 1, y: 1 }];
  const bad = [
    undefined,
    null,
    {},
    { width: 100 },
    { width: 0, height: 100 },
    { width: -5, height: 100 },
    { width: 100, height: 0 },
    { width: '100', height: 100 },
    { width: 100, height: NaN },
    { width: 100, height: 100, cellSize: 0 },
    { width: 100, height: 100, cellSize: '40' },
    { width: 100, height: 100, padding: -1 },
    { width: 100, height: 100, padding: NaN },
    { width: 100, height: 100, padding: '5' }
  ];
  for (const options of bad) {
    assert.deepEqual(clusterPoints(points, options), [], `options ${JSON.stringify(options)}`);
  }
  // Defaults apply when cellSize/padding are omitted.
  const ok = clusterPoints(points, { width: 100, height: 100 });
  assert.equal(ok.length, 1);
});

test('clusterPoints never throws on malformed points', () => {
  const options = { width: 400, height: 300 };
  const hostile = { id: 'boom', get x() { throw new Error('nope'); }, y: 1 };
  const points = [
    null, 5, 'text', undefined, {},
    { id: 'good', x: 10, y: 10 },
    { id: 'nan', x: NaN, y: 10 },
    { id: 'inf', x: Infinity, y: 10 },
    { id: 'strx', x: '3', y: 4 },
    hostile
  ];
  let clusters;
  assert.doesNotThrow(() => { clusters = clusterPoints(points, options); });
  const ids = clusters.flatMap(c => c.members.map(m => m.id));
  assert.deepEqual(ids, ['good']);
  assert.deepEqual(clusterPoints('not an array', options), []);
  assert.deepEqual(clusterPoints(null, options), []);
});

test('clusterPoints handles a 10000 point smoke case in linear time', () => {
  const options = { width: 400, height: 300, cellSize: 40, padding: 20 };
  const points = [];
  for (let i = 0; i < 100; i++) {
    for (let j = 0; j < 100; j++) {
      points.push({ id: `p-${i}-${j}`, x: i * 4 + 1, y: j * 3 + 1 });
    }
  }
  const start = Date.now();
  const clusters = clusterPoints(points, options);
  const elapsed = Date.now() - start;
  const total = clusters.reduce((sum, c) => sum + c.count, 0);
  assert.equal(total, 10000);
  assert.ok(clusters.length > 0 && clusters.length <= 10000);
  assert.ok(elapsed < 5000, `clustering took ${elapsed}ms`);
});

test('normalizeCustomPins returns [] for non-arrays', () => {
  for (const value of [null, undefined, {}, 'x', 42, true, () => {}]) {
    assert.deepEqual(normalizeCustomPins(value), []);
  }
  assert.deepEqual(normalizeCustomPins([]), []);
});

test('normalizeCustomPins keeps valid pins, trims text and strips unknown fields', () => {
  const input = [{
    id: '  pin-1  ',
    label: '  Riverside Park  ',
    notes: 'Shade and benches',
    longitude: -122.4194,
    latitude: 37.7749,
    unknown: 'drop me',
    html: '<b>nope</b>'
  }];
  const out = normalizeCustomPins(input);
  assert.equal(out.length, 1);
  assert.deepEqual(Object.keys(out[0]).sort(), ['id', 'label', 'latitude', 'longitude', 'notes']);
  assert.equal(out[0].id, 'pin-1');
  assert.equal(out[0].label, 'Riverside Park');
  assert.equal(out[0].notes, 'Shade and benches');
  assert.equal(out[0].longitude, -122.4194);
  assert.equal(out[0].latitude, 37.7749);
});

test('normalizeCustomPins drops invalid entries and rejects bad coordinates', () => {
  const valid = { id: 'ok', label: 'Ok', notes: '', longitude: 0, latitude: 0 };
  const input = [
    valid,
    null, 5, 'text',
    { id: '', label: 'x', notes: '', longitude: 0, latitude: 0 },
    { id: '   ', label: 'x', notes: '', longitude: 0, latitude: 0 },
    { id: 'a'.repeat(81), label: 'x', notes: '', longitude: 0, latitude: 0 },
    { id: 'no-label', label: '', notes: '', longitude: 0, latitude: 0 },
    { id: 'space-label', label: '   ', notes: '', longitude: 0, latitude: 0 },
    { id: 'long-label', label: 'l'.repeat(101), notes: '', longitude: 0, latitude: 0 },
    { id: 'long-notes', label: 'x', notes: 'n'.repeat(1001), longitude: 0, latitude: 0 },
    { id: 'num-notes', label: 'x', notes: 42, longitude: 0, latitude: 0 },
    { id: 'lon-str', label: 'x', notes: '', longitude: '-122', latitude: 0 },
    { id: 'lat-str', label: 'x', notes: '', longitude: 0, latitude: '37' },
    { id: 'lon-nan', label: 'x', notes: '', longitude: NaN, latitude: 0 },
    { id: 'lat-inf', label: 'x', notes: '', longitude: 0, latitude: Infinity },
    { id: 'lon-range', label: 'x', notes: '', longitude: 180.1, latitude: 0 },
    { id: 'lat-range', label: 'x', notes: '', longitude: 0, latitude: -90.1 }
  ];
  const out = normalizeCustomPins(input);
  assert.deepEqual(out.map(p => p.id), ['ok']);
});

test('normalizeCustomPins keeps the first valid entry for a duplicate id', () => {
  const out = normalizeCustomPins([
    { id: 'dup', label: 'First', notes: '', longitude: 1, latitude: 1 },
    { id: 'dup', label: 'Second', notes: '', longitude: 2, latitude: 2 }
  ]);
  assert.equal(out.length, 1);
  assert.equal(out[0].label, 'First');
  assert.equal(out[0].longitude, 1);
});

test('normalizeCustomPins bounds the result to 100 pins', () => {
  const input = [];
  for (let i = 0; i < 150; i++) {
    input.push({ id: `pin-${i}`, label: `Pin ${i}`, notes: '', longitude: i % 180, latitude: i % 90 });
  }
  const out = normalizeCustomPins(input);
  assert.equal(out.length, 100);
  assert.equal(out[0].id, 'pin-0');
  assert.equal(out[99].id, 'pin-99');
});

test('normalizeCustomPins does not mutate the input array or objects', () => {
  const input = [
    { id: ' a ', label: ' A ', notes: 'n', longitude: 5, latitude: 6, junk: 1 }
  ];
  const snapshot = JSON.parse(JSON.stringify(input));
  normalizeCustomPins(input);
  assert.deepEqual(JSON.parse(JSON.stringify(input)), snapshot);
  assert.equal(input[0].id, ' a ');
  assert.equal(input[0].junk, 1);
});

test('normalizeCustomPins keeps strings as literal text (no HTML parsing)', () => {
  const out = normalizeCustomPins([{
    id: 'xss',
    label: '<img src=x onerror=alert(1)>',
    notes: '<script>alert(1)</script>',
    longitude: 0,
    latitude: 0
  }]);
  assert.equal(out.length, 1);
  assert.equal(out[0].label, '<img src=x onerror=alert(1)>');
  assert.equal(out[0].notes, '<script>alert(1)</script>');
});

test('normalizeCustomPins never throws on hostile prototypes or getters', () => {
  const boom = { id: 'boom', get label() { throw new Error('nope'); }, notes: '', longitude: 0, latitude: 0 };
  const nullProto = Object.assign(Object.create(null), {
    id: 'null-proto', label: 'Null proto', notes: '', longitude: 10, latitude: 10
  });
  const evil = JSON.parse('{"id":"evil","label":"Evil","notes":"","longitude":0,"latitude":0,"__proto__":{"polluted":true}}');
  const protoId = { id: '__proto__', label: 'Proto id', notes: '', longitude: 0, latitude: 0 };

  let out;
  assert.doesNotThrow(() => { out = normalizeCustomPins([boom, nullProto, evil, protoId, protoId]); });
  assert.deepEqual(out.map(p => p.id), ['null-proto', 'evil', '__proto__']);
  assert.equal({}.polluted, undefined, 'prototype pollution must not leak');
});