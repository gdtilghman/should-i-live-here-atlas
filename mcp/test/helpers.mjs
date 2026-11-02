// Shared test helpers. Tests read the packed data the build script writes,
// and the original layer files as an independent reference.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const root = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const out = path.join(root, 'mcp', 'src', 'data');
export const built = ['counties.json', 'measures.json', 'values.bin', 'status.bin']
  .every(f => fs.existsSync(path.join(out, f)));
export const skip = built ? false : 'run python scripts/build-mcp-data.py first';

const buffer = f => { const b = fs.readFileSync(path.join(out, f)); return b.buffer.slice(b.byteOffset, b.byteOffset + b.length); };

export function packedInput() {
  return {
    counties: JSON.parse(fs.readFileSync(path.join(out, 'counties.json'), 'utf8')),
    measures: JSON.parse(fs.readFileSync(path.join(out, 'measures.json'), 'utf8')),
    values: buffer('values.bin'),
    status: buffer('status.bin'),
  };
}

const manifest = () => JSON.parse(fs.readFileSync(path.join(root, 'dist', 'data', 'layers', 'manifest.json'), 'utf8'));

// The layer file for a key such as "crime:violent-crime", as the site loads it.
export function layer(key) {
  const [family, id] = key.split(':');
  const d = manifest().families[family].datasets.find(x => x.id === id);
  const data = JSON.parse(fs.readFileSync(path.join(root, 'dist', 'data', 'layers', d.file), 'utf8'));
  return { ...data, direction: data.direction || 'higher-worse' };
}

export const fipsList = () => packedInput().counties.map(c => c.fips);

// A recording stand-in for a Cloudflare D1 binding.
export function fakeD1({ fail = false } = {}) {
  const calls = [];
  return {
    calls,
    prepare(sql) {
      return { bind(...args) { return { sql, args }; } };
    },
    async batch(statements) {
      if (fail) throw new Error('D1 is down');
      calls.push(...statements);
      return statements.map(() => ({ success: true }));
    },
  };
}
