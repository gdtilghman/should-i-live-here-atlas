'use strict';
// Every topic must name its source with links anyone can open, a retrieval
// date and a citation, and every measure must link to its source.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const dist = path.join(__dirname, '..', 'dist');
const read = file => JSON.parse(fs.readFileSync(path.join(dist, 'data', file), 'utf8'));

test('every topic in the manifest has one checked source entry', () => {
  const manifest = read('layers/manifest.json');
  const sources = read('sources.json').sources;
  const families = Object.keys(manifest.families).sort();
  assert.deepStrictEqual(sources.map(s => s.family).sort(), families);
  for (const s of sources) {
    for (const key of ['topic', 'source', 'retrieved', 'citation']) {
      assert.ok(typeof s[key] === 'string' && s[key].trim(), `${s.family}: ${key} missing`);
    }
    for (const key of ['page', 'data', 'terms']) {
      if (key === 'terms' && !s.terms) continue;
      assert.match(s[key], /^https:\/\//, `${s.family}: ${key} is not an https link`);
    }
  }
});

test('every measure links to its source', () => {
  const manifest = read('layers/manifest.json');
  for (const family of Object.keys(manifest.families)) {
    const collection = read(`${family}.json`);
    for (const dataset of collection.datasets) {
      const url = dataset.sourceUrl || collection.sourceUrl;
      assert.match(url || '', /^https:\/\//, `${family}:${dataset.id} has no https source link`);
    }
  }
});

test('the page shows the source list', () => {
  const html = fs.readFileSync(path.join(dist, 'index.html'), 'utf8');
  assert.ok(html.includes('id="data-sources-list"'), 'source list container missing');
  assert.ok(html.includes('<script src="./sources.js" defer></script>'), 'sources.js not loaded');
  assert.ok(fs.existsSync(path.join(dist, 'sources.js')), 'sources.js missing');
});
