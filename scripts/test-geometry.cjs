'use strict';
// Proves the JavaScript decoder reproduces the original county geometry.
// The encoder is Python and the decoder is JavaScript, so nothing but a test
// keeps them agreeing. Run scripts/build-geometry.py first; the encoded file
// is generated and not committed.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const encodedPath = path.join(root, 'dist', 'data', 'counties.qd.json');
const sourcePath = path.join(root, 'dist', 'data', 'counties.geojson');
const { decode } = require(path.join(root, 'dist', 'geometry-decode.js'));

const available = fs.existsSync(encodedPath);
const skip = available ? false : 'run scripts/build-geometry.py first';

const RING_DEPTH = { Polygon: 1, MultiPolygon: 2 };

function* rings(coords, depth) {
  if (depth === 0) { yield coords; return; }
  for (const part of coords) yield* rings(part, depth - 1);
}

test('the decoder reproduces every county coordinate', { skip }, () => {
  const source = JSON.parse(fs.readFileSync(sourcePath, 'utf8'));
  const restored = decode(JSON.parse(fs.readFileSync(encodedPath, 'utf8')));

  assert.strictEqual(restored.features.length, source.features.length,
    'feature count changed');
  assert.strictEqual(restored.features.length, 3107, 'expected 3107 counties');

  // One grid cell is the most any point may move. Anything larger means the
  // decoder disagrees with the encoder rather than merely quantising.
  const doc = JSON.parse(fs.readFileSync(encodedPath, 'utf8'));
  const limit = Math.max(doc.scale[0], doc.scale[1]) * 1.5;

  let worst = 0;
  let worstFips = null;
  let points = 0;

  for (let i = 0; i < source.features.length; i++) {
    const a = source.features[i];
    const b = restored.features[i];
    assert.strictEqual(b.properties.fips, a.properties.fips, 'feature order changed');
    for (const key of ['fips', 'state', 'name', 'stateName']) {
      assert.strictEqual(b.properties[key], a.properties[key],
        `property ${key} changed for ${a.properties.fips}`);
    }
    assert.strictEqual(b.geometry.type, a.geometry.type,
      `geometry type changed for ${a.properties.fips}`);

    const depth = RING_DEPTH[a.geometry.type];
    const srcRings = [...rings(a.geometry.coordinates, depth)];
    const outRings = [...rings(b.geometry.coordinates, depth)];
    assert.strictEqual(outRings.length, srcRings.length,
      `ring count changed for ${a.properties.fips}`);

    for (let r = 0; r < srcRings.length; r++) {
      assert.strictEqual(outRings[r].length, srcRings[r].length,
        `ring length changed for ${a.properties.fips}`);
      for (let p = 0; p < srcRings[r].length; p++) {
        points++;
        const d = Math.max(
          Math.abs(srcRings[r][p][0] - outRings[r][p][0]),
          Math.abs(srcRings[r][p][1] - outRings[r][p][1]),
        );
        if (d > worst) { worst = d; worstFips = a.properties.fips; }
      }
    }
  }

  assert.ok(points > 150000, `expected about 160k coordinates, saw ${points}`);
  assert.ok(worst <= limit,
    `worst deviation ${worst} deg at ${worstFips} exceeds one grid cell ${limit}`);
  // About 32 m was measured. Allow headroom but catch a real regression.
  assert.ok(worst * 111000 < 80,
    `worst deviation ${(worst * 111000).toFixed(0)} m is larger than expected`);
});

test('the decoder refuses an unknown format', { skip }, () => {
  assert.throws(() => decode({ format: 'something-else' }), /Unsupported geometry format/);
  assert.throws(() => decode(null), /Unsupported geometry format/);
});
