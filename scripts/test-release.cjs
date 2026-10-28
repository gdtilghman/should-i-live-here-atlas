'use strict';
// Release checks for static hosting (Cloudflare): the page loads nothing
// from other hosts, uses only relative paths, ships no secrets, and keeps
// every file well under common static-asset size limits.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const dist = path.join(__dirname, '..', 'dist');
const walk = dir => fs.readdirSync(dir, { withFileTypes: true })
  .flatMap(entry => entry.isDirectory() ? walk(path.join(dir, entry.name)) : [path.join(dir, entry.name)]);
const files = walk(dist);
const code = files.filter(file => /\.(html|js|css)$/.test(file) && !file.includes(`${path.sep}vendor${path.sep}`));

test('the page loads nothing from other hosts', () => {
  for (const file of code) {
    const text = fs.readFileSync(file, 'utf8');
    // Loaded resources only; plain <a href> links a visitor clicks are fine.
    const resources = text.match(/<(?:script|img|iframe|source|audio|video)\b[^>]*\bsrc=["'](?:https?:)?\/\/[^"']+|<link\b[^>]*\bhref=["'](?:https?:)?\/\/[^"']+|@import[^;]*https?:|url\(\s*["']?https?:|fetch\(\s*["'`]https?:/g) || [];
    assert.deepStrictEqual(resources, [], `${path.relative(dist, file)} loads an external resource`);
  }
});

test('paths are relative, with no local server addresses', () => {
  for (const file of code) {
    const text = fs.readFileSync(file, 'utf8');
    assert.ok(!/localhost|127\.0\.0\.1/.test(text), `${path.relative(dist, file)} names a local server`);
    assert.ok(!/(?:src|href)="\/(?!\/)|fetch\(\s*["'`]\/(?!\/)/.test(text), `${path.relative(dist, file)} uses an absolute path`);
  }
});

test('no file contains a secret-like value', () => {
  const pattern = /fw_[A-Za-z0-9]{16,}|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----/;
  for (const file of files) {
    if (fs.statSync(file).size > 20 * 1024 * 1024) continue;
    assert.ok(!pattern.test(fs.readFileSync(file, 'latin1')), `${path.relative(dist, file)} contains a secret-like value`);
  }
});

test('every file is under 20 MB', () => {
  for (const file of files) {
    assert.ok(fs.statSync(file).size < 20 * 1024 * 1024, `${path.relative(dist, file)} is 20 MB or larger`);
  }
});
