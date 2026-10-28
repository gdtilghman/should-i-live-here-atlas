'use strict';
// Keeps the first-load page weight a checked number.
//
// The app used to download every layer before it could paint, 1,981 KB
// gzipped. It now reads a manifest and fetches only the datasets a view needs,
// measured at 674 KB. Nothing about that is self-enforcing: one large dataset
// added to the default recipe would quietly undo it, and no existing test
// would notice.
//
// Sizes are gzipped, because that is what a visitor actually transfers.
// Run scripts/build-shards.py and scripts/build-geometry.py first; both
// outputs are generated.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const zlib = require('node:zlib');

const root = path.resolve(__dirname, '..');
const dataDir = path.join(root, 'dist', 'data');
const layerDir = path.join(dataDir, 'layers');
const manifestPath = path.join(layerDir, 'manifest.json');
const geometryPath = path.join(dataDir, 'counties.qd.json');

const ready = fs.existsSync(manifestPath) && fs.existsSync(geometryPath);
const skip = ready ? false : 'run scripts/build-shards.py and scripts/build-geometry.py first';

const KB = 1024;
// The first measure the app shows. initializeDefaultRecipe does not name it,
// so unlike the recipe keys it cannot be read out of the source.
const FIRST_MEASURE = 'cancer:001';

// Measure the bytes on disk, not a re-serialised copy of them. The file is
// what gets served.
const gz = (file) => zlib.gzipSync(fs.readFileSync(file)).length;
const readJson = (file) => JSON.parse(fs.readFileSync(file, 'utf8'));

function defaultRecipeKeys() {
  // Read the keys out of the app rather than repeating them here, so renaming
  // a dataset in one place fails this test instead of passing quietly. The
  // match is anchored inside initializeDefaultRecipe; a loose pattern would
  // catch any ["a:b", 1] pair elsewhere in the file.
  const source = fs.readFileSync(path.join(root, 'dist', 'app.js'), 'utf8');
  const start = source.indexOf('function initializeDefaultRecipe');
  assert.ok(start >= 0, 'initializeDefaultRecipe is gone; this test needs updating');
  const body = source.slice(start, source.indexOf('];', start));
  return [...body.matchAll(/\["([a-z-]+:[a-z0-9-]+)",\s*\d+\]/g)].map(match => match[1]);
}

function shardFile(manifest, key) {
  const separator = key.indexOf(':');
  const family = key.slice(0, separator);
  const id = key.slice(separator + 1);
  const entry = manifest.families[family];
  assert.ok(entry, `${key}: family ${family} is not in the manifest`);
  const listing = entry.datasets.find(dataset => dataset.id === id);
  assert.ok(listing, `${key}: dataset ${id} is not in family ${family}`);
  const file = path.join(layerDir, listing.file);
  assert.ok(fs.existsSync(file), `${key}: shard ${listing.file} is not on disk`);
  return file;
}

function firstLoadKeys() {
  return [...defaultRecipeKeys(), FIRST_MEASURE];
}

test('every default input named by the app exists in the manifest', { skip }, () => {
  const manifest = readJson(manifestPath);
  const keys = defaultRecipeKeys();
  assert.strictEqual(keys.length, 4, `expected 4 default recipe keys, read ${keys.length}`);
  for (const key of keys) shardFile(manifest, key);
});

test('the first load stays inside its budget', { skip }, () => {
  const manifest = readJson(manifestPath);
  const shards = firstLoadKeys().reduce((sum, key) => sum + gz(shardFile(manifest, key)), 0);
  const total = gz(geometryPath) + gz(manifestPath) + shards;
  const kb = Math.round(total / KB);

  assert.ok(total <= 750 * KB, `first load is ${kb} KB gzipped, over the 750 KB budget`);
  // A sudden collapse means a file went missing or emptied, not that the app
  // got faster.
  assert.ok(total >= 300 * KB, `first load is only ${kb} KB gzipped; a file is probably missing`);
});

test('no single shard dominates the first load', { skip }, () => {
  // One large layer landing in the default recipe is the likeliest way this
  // regresses, and a total-only budget would absorb it until it was too late.
  const manifest = readJson(manifestPath);
  for (const key of firstLoadKeys()) {
    const file = shardFile(manifest, key);
    const size = gz(file);
    assert.ok(size <= 100 * KB,
      `${key}: ${path.basename(file)} is ${Math.round(size / KB)} KB gzipped, over the 100 KB limit`);
  }
});

test('lazy loading still beats shipping every layer', { skip }, () => {
  // The claim the migration was made on. Geometry is excluded from both sides
  // because it loads either way; including it would compare the two designs on
  // a cost they share.
  const manifest = readJson(manifestPath);
  const lazy = gz(manifestPath) +
    firstLoadKeys().reduce((sum, key) => sum + gz(shardFile(manifest, key)), 0);
  const eager = ['cancer', 'disasters', 'community', 'hazards', 'healthcare', 'climate']
    .reduce((sum, family) => sum + gz(path.join(dataDir, `${family}.json`)), 0);

  assert.ok(eager >= lazy * 3,
    `shipping every layer is ${Math.round(eager / KB)} KB against ${Math.round(lazy / KB)} KB ` +
    `lazily, only ${(eager / lazy).toFixed(1)}x; the migration no longer pays for its complexity`);
});
