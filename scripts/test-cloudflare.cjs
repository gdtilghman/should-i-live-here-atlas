'use strict';
// Cloudflare hosting must serve dist/ only, with no Worker script and no
// preview URLs, so the workers.dev address is the only way in.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..');
const raw = fs.readFileSync(path.join(root, 'wrangler.jsonc'), 'utf8');
const config = JSON.parse(raw.replace(/^\s*\/\/.*$/gm, ''));

test('Cloudflare serves dist/ only, as static files', () => {
  assert.strictEqual(config.assets?.directory, './dist');
  assert.ok(!('main' in config), 'a Worker script would run code on every request');
});

test('only the workers.dev address exists', () => {
  assert.strictEqual(config.workers_dev, true);
  assert.strictEqual(config.preview_urls, false, 'preview URLs would be a second address');
  assert.ok(!config.routes && !config.route, 'no custom domain until one is bought');
});

test('files the app never loads stay off the host', () => {
  const ignore = fs.readFileSync(path.join(root, 'dist', '.assetsignore'), 'utf8');
  assert.match(ignore, /^data\/normalized\.json$/m);
  const families = JSON.parse(fs.readFileSync(path.join(root, 'dist', 'data', 'layers', 'manifest.json'), 'utf8')).families;
  for (const family of Object.keys(families)) assert.match(ignore, new RegExp(`^data/${family}\\.json$`, 'm'), family);
  for (const runtime of ['data/layers/', 'data/overlays/', 'data/sources.json', 'data/counties.qd.json', 'data/counties.geojson']) {
    assert.ok(!ignore.split('\n').some((line) => line.trim() && !line.startsWith('#') && runtime.startsWith(line.trim())), `${runtime} must stay on the host`);
  }
});
