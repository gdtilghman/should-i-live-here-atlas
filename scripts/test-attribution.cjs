'use strict';
// Guards required source attribution that is easy to break by accident.
// FEMA's OpenFEMA terms require the not-endorsed statement to be stated
// clearly. It reaches the user through the note field of the disaster
// datasets, so a dropped or reworded note is a compliance regression, not a
// cosmetic one.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const readText = (rel) => fs.readFileSync(path.join(root, rel), 'utf8');

// Quoted verbatim from https://www.fema.gov/about/openfema/terms-conditions
// (last updated January 22, 2025). The curly apostrophe in "Agency’s" and the
// straight apostrophe in "Agency's website(s)" both match the source exactly.
// Do not normalise them.
const FEMA_REQUIRED =
  'This product uses the Federal Emergency Management Agency’s OpenFEMA API, ' +
  'but is not endorsed by FEMA. The Federal Government or FEMA cannot vouch for ' +
  'the data or analyses derived from these data after the data have been ' +
  "retrieved from the Agency's website(s).";

const FEMA_ENDPOINT = 'https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries';

test('every disaster layer carries the FEMA required statement verbatim', () => {
  const data = JSON.parse(readText('dist/data/disasters.json'));
  assert.ok(data.datasets.length > 0, 'expected at least one disaster dataset');
  assert.ok(
    data.note.includes(FEMA_REQUIRED),
    'top-level disasters note is missing the FEMA required statement',
  );
  for (const dataset of data.datasets) {
    assert.ok(
      typeof dataset.note === 'string' && dataset.note.includes(FEMA_REQUIRED),
      `dataset ${dataset.id} is missing the FEMA required statement`,
    );
  }
});

test('the disaster note cites the endpoint and the retrieval date', () => {
  const data = JSON.parse(readText('dist/data/disasters.json'));
  assert.ok(data.note.includes(FEMA_ENDPOINT), 'note does not cite the API endpoint');
  assert.match(
    data.note,
    /Retrieved from \S+ on [A-Z][a-z]+ \d{1,2}, \d{4}\./,
    'note does not cite a retrieval date in the FEMA example format',
  );
});

test('the build script emits the same required statement', () => {
  // Without this the next rebuild would silently drop the notice.
  assert.ok(
    readText('scripts/prepare-disasters.py').includes(FEMA_REQUIRED),
    'scripts/prepare-disasters.py would rebuild disasters.json without the notice',
  );
});

test('the app renders a source note the user can actually see', () => {
  // The notice reaches the page through #source-status and #dock-note. If the
  // app stops rendering a note there, the data file alone is not enough.
  const app = readText('dist/app.js');
  assert.ok(app.includes('elements.sourceStatus.textContent'), 'source line no longer rendered');
  assert.match(app, /notes\s*=\s*\[\.\.\.new Set\(\[dataset\?\.note, collection\?\.note\]/,
    'source line no longer includes the dataset or collection note');
});

test('no FEMA or DHS logo or seal is referenced', () => {
  // FEMA's terms prohibit using their logos or seals without prior written
  // authorization. None is used, and this keeps it that way.
  const files = ['dist/index.html', 'dist/app.js', 'dist/style.css'];
  const forbidden = /fema[-_ ]?(logo|seal)|dhs[-_ ]?(logo|seal)|homeland[-_ ]?security[-_ ]?seal/i;
  for (const rel of files) {
    assert.ok(!forbidden.test(readText(rel)), `${rel} references a FEMA or DHS logo or seal`);
  }
});

// The app reads the manifest and the per-dataset shards, not the family file.
// The shards are build output and are not committed, so these run only when
// scripts/build-shards.py has been run.
const layersDir = path.join(root, 'dist', 'data', 'layers');
const manifestPath = path.join(layersDir, 'manifest.json');
const shardSkip = fs.existsSync(manifestPath) ? false : 'run scripts/build-shards.py first';

test('the shipped manifest carries the FEMA required statement', { skip: shardSkip }, () => {
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  const disasters = manifest.families?.disasters;
  assert.ok(disasters, 'the manifest has no disasters family');
  assert.ok(
    typeof disasters.note === 'string' && disasters.note.includes(FEMA_REQUIRED),
    'the manifest disasters note is missing the FEMA required statement',
  );
  assert.ok(disasters.note.includes(FEMA_ENDPOINT), 'the manifest note does not cite the API endpoint');
  assert.ok(disasters.datasets.length > 0, 'the manifest lists no disaster datasets');
  for (const listing of disasters.datasets) {
    assert.ok(
      typeof listing.note === 'string' && listing.note.includes(FEMA_REQUIRED),
      `manifest listing ${listing.id} is missing the FEMA required statement`,
    );
  }
});

test('every shipped disaster shard carries the FEMA required statement', { skip: shardSkip }, () => {
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  const listings = manifest.families.disasters.datasets;
  for (const listing of listings) {
    const shard = JSON.parse(fs.readFileSync(path.join(layersDir, listing.file), 'utf8'));
    assert.ok(
      typeof shard.note === 'string' && shard.note.includes(FEMA_REQUIRED),
      `shard ${listing.file} is missing the FEMA required statement`,
    );
  }
});

test('the app requests the manifest rather than the family files', { skip: shardSkip }, () => {
  // If the app went back to loading disasters.json directly, the two tests
  // above would still pass while guarding a file nobody downloads.
  const app = readText('dist/app.js');
  assert.ok(app.includes('manifest.json'), 'the app no longer loads the layer manifest');
  assert.ok(
    !app.includes('"./data/disasters.json"'),
    'the app loads the disasters family file again; extend these guards to cover it',
  );
});
