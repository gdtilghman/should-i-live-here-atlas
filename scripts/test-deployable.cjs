'use strict';
// Proves a fresh clone can actually run the app.
//
// Cloudflare serves dist/ as it stands. There is no build step at deploy
// time, so anything the page fetches at runtime must be in the repository.
// Until September 17, 2026 the shards and the encoded geometry were generated
// and git ignored, which was correct while nothing read them. The moment the
// app started reading them, that ignore rule became a broken deployment that
// no test would have noticed, because every file is present on the machine
// that generated it.
//
// This checks the repository, not the working directory, which is the whole
// point: a file can be on disk and still be missing from a clone.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');

const root = path.resolve(__dirname, '..');

function trackedFiles() {
  const output = execFileSync('git', ['ls-files'], { cwd: root, encoding: 'utf8' });
  // git reports forward slashes on every platform; normalise anyway so this
  // does not quietly pass on Windows by comparing nothing.
  return new Set(output.split('\n').map((line) => line.trim().replace(/\\/g, '/')).filter(Boolean));
}

function runtimeFiles() {
  const needed = [
    'dist/index.html',
    'dist/app.js',
    'dist/composite.js',
    'dist/geometry-decode.js',
    'dist/data/counties.qd.json',
    'dist/data/layers/manifest.json',
  ];
  const manifestPath = path.join(root, 'dist', 'data', 'layers', 'manifest.json');
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  for (const family of Object.values(manifest.families)) {
    for (const listing of family.datasets) {
      needed.push(`dist/data/layers/${listing.file}`);
    }
  }
  return needed;
}

const manifestExists = fs.existsSync(path.join(root, 'dist', 'data', 'layers', 'manifest.json'));
const skip = manifestExists ? false : 'run scripts/build-shards.py first';

test('every file the app fetches at runtime is in the repository', { skip }, () => {
  const tracked = trackedFiles();
  const needed = runtimeFiles();
  const missing = needed.filter((file) => !tracked.has(file));
  assert.deepStrictEqual(missing.slice(0, 10), [],
    `${missing.length} runtime files are not tracked, so a clone cannot run the app`);
  assert.ok(needed.length >= 37,
    `expected the manifest plus 35 shards and the page files, counted ${needed.length}`);
});

test('the vendored map library ships with the page', { skip }, () => {
  // d3 is vendored deliberately so no visitor request leaves the site. If it
  // stopped being tracked the page would load from nowhere.
  const tracked = [...trackedFiles()];
  const vendored = tracked.filter((file) => file.startsWith('dist/vendor/'));
  assert.ok(vendored.some((file) => /d3.*\.js$/.test(file)),
    'no vendored d3 build is tracked under dist/vendor/');
  assert.ok(vendored.some((file) => /licen[sc]e/i.test(file)),
    'the vendored d3 license is not tracked beside it');
});

test('the page loads the geometry decoder', { skip }, () => {
  // Without this tag the app silently falls back to the 1,044 KB GeoJSON,
  // which still works and so would not fail any other test here.
  const html = fs.readFileSync(path.join(root, 'dist', 'index.html'), 'utf8');
  assert.match(html, /<script src="\.\/geometry-decode\.js"/,
    'index.html does not load geometry-decode.js, so the encoded geometry is unused');
});
