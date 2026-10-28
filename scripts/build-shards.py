#!/usr/bin/env python3
"""Split the prebuilt layer files into per-dataset shards plus a manifest.

The app currently loads every layer before first render. Only one dataset is
ever shown on the map at a time, so most of that transfer is wasted. Sharding
lets the app fetch the manifest and the one dataset it needs, and fetch the
rest on demand.

This changes delivery only. No value, status, count or range is altered, and
the original family files stay in place so nothing breaks while the app is
migrated.

Standard library only. No network.
"""

import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path

FAMILIES = ('cancer', 'disasters', 'community', 'hazards', 'healthcare', 'employment', 'broadband', 'places', 'air', 'wildfire', 'water', 'traffic', 'climate', 'storms', 'crime')

# Keys that belong to the dataset, not to a single county record.
RECORD_KEY = 'records'


def repo_root():
    return Path(__file__).resolve().parent.parent


def gz_size(text):
    return len(gzip.compress(text.encode('utf-8')))


def shard_name(family, dataset_id):
    # Dataset ids are unique only within a family, so the family must be part
    # of the file name.
    safe = ''.join(c if (c.isalnum() or c in '-_') else '-' for c in str(dataset_id))
    return f'{family}-{safe}.json'


def build(data_dir, out_dir, verbose=True):
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {'version': 1, 'families': {}}
    written = []
    totals = {'datasets': 0, 'records': 0}

    for family in FAMILIES:
        src = data_dir / f'{family}.json'
        if not src.exists():
            raise SystemExit(f'missing input: {src}')
        payload = json.loads(src.read_text(encoding='utf-8'))

        entry = {
            'sourceUrl': payload.get('sourceUrl'),
            'note': payload.get('note'),
            'datasets': [],
        }

        for dataset in payload['datasets']:
            meta = {k: v for k, v in dataset.items() if k != RECORD_KEY}
            records = dataset[RECORD_KEY]
            totals['datasets'] += 1
            totals['records'] += len(records)

            # The shard carries the dataset metadata as well as its records, so
            # a lazily fetched dataset is self-describing and needs no lookup
            # back into the manifest.
            shard = dict(meta)
            shard[RECORD_KEY] = {fips: records[fips] for fips in sorted(records)}
            text = json.dumps(shard, ensure_ascii=False, separators=(',', ':'),
                              sort_keys=False)
            name = shard_name(family, dataset['id'])
            (out_dir / name).write_text(text, encoding='utf-8')

            digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
            written.append((family, dataset['id'], name, len(text), gz_size(text)))

            # The manifest holds everything the app needs to build its menus
            # and colour scales without downloading any records.
            listing = dict(meta)
            listing['file'] = name
            listing['recordCount'] = len(records)
            listing['sha256'] = digest
            entry['datasets'].append(listing)

        manifest['families'][family] = entry

    manifest_text = json.dumps(manifest, ensure_ascii=False, separators=(',', ':'))
    (out_dir / 'manifest.json').write_text(manifest_text, encoding='utf-8')

    if verbose:
        report(manifest_text, written, totals, data_dir, out_dir)
    return manifest, written


def report(manifest_text, written, totals, data_dir, out_dir):
    eager_gz = sum(gz_size((data_dir / f'{f}.json').read_text(encoding='utf-8'))
                   for f in FAMILIES)
    geo = data_dir / 'counties.geojson'
    geo_gz = gz_size(geo.read_text(encoding='utf-8')) if geo.exists() else 0
    manifest_gz = gz_size(manifest_text)
    largest = max(written, key=lambda r: r[4])
    smallest = min(written, key=lambda r: r[4])

    print(f'datasets sharded      {totals["datasets"]}')
    print(f'records written       {totals["records"]}')
    print(f'manifest              {manifest_gz / 1024:.1f} KB gz')
    print(f'largest shard         {largest[2]} {largest[4] / 1024:.1f} KB gz')
    print(f'smallest shard        {smallest[2]} {smallest[4] / 1024:.1f} KB gz')
    print()
    print(f'data today, eager     {eager_gz / 1024:.0f} KB gz')
    print(f'data lazy, first load {(manifest_gz + largest[4]) / 1024:.0f} KB gz '
          f'(manifest + one dataset)')
    print(f'saving on first load  {(eager_gz - manifest_gz - largest[4]) / 1024:.0f} KB gz')
    print()
    print(f'geometry (unchanged)  {geo_gz / 1024:.0f} KB gz')
    print(f'total first load now  {(eager_gz + geo_gz) / 1024:.0f} KB gz')
    print(f'total first load lazy {(manifest_gz + largest[4] + geo_gz) / 1024:.0f} KB gz')
    print(f'output                {out_dir}')


def verify(data_dir, out_dir):
    """Re-read the shards and prove they reproduce the originals exactly."""
    manifest = json.loads((out_dir / 'manifest.json').read_text(encoding='utf-8'))
    failures = []
    checked = 0

    for family in FAMILIES:
        original = json.loads((data_dir / f'{family}.json').read_text(encoding='utf-8'))
        listed = manifest['families'][family]['datasets']
        if len(listed) != len(original['datasets']):
            failures.append(f'{family}: dataset count {len(listed)} != '
                            f'{len(original["datasets"])}')
            continue
        by_id = {d['id']: d for d in original['datasets']}
        for listing in listed:
            shard = json.loads((out_dir / listing['file']).read_text(encoding='utf-8'))
            source = by_id[listing['id']]
            if shard[RECORD_KEY] != source[RECORD_KEY]:
                failures.append(f'{family}/{listing["id"]}: records differ')
            meta_shard = {k: v for k, v in shard.items() if k != RECORD_KEY}
            meta_source = {k: v for k, v in source.items() if k != RECORD_KEY}
            if meta_shard != meta_source:
                failures.append(f'{family}/{listing["id"]}: metadata differs')
            if listing['recordCount'] != len(source[RECORD_KEY]):
                failures.append(f'{family}/{listing["id"]}: recordCount wrong')
            checked += 1

    # The distinction between a missing value and a real zero is the invariant
    # this project protects, so it is checked explicitly rather than assumed to
    # survive a round trip.
    statuses = {}
    zeros = 0
    nulls = 0
    for family in FAMILIES:
        for listing in manifest['families'][family]['datasets']:
            shard = json.loads((out_dir / listing['file']).read_text(encoding='utf-8'))
            for record in shard[RECORD_KEY].values():
                statuses[record['status']] = statuses.get(record['status'], 0) + 1
                if record['value'] is None:
                    nulls += 1
                elif record['value'] == 0:
                    zeros += 1
                if (record['status'] == 'available') != (record['value'] is not None):
                    failures.append('status and value disagree after sharding')

    print(f'datasets verified     {checked}')
    print(f'status distribution   {dict(sorted(statuses.items()))}')
    print(f'null values           {nulls}')
    print(f'meaningful zeros      {zeros}')
    if failures:
        print()
        for line in failures[:10]:
            print('FAIL', line)
        print(f'{len(failures)} failure(s)')
        return False
    print('shards reproduce the originals exactly')
    return True


def main():
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', default=str(root / 'dist' / 'data'))
    parser.add_argument('--out', default=str(root / 'dist' / 'data' / 'layers'))
    args = parser.parse_args()

    data_dir = Path(args.data)
    out_dir = Path(args.out)
    build(data_dir, out_dir)
    print()
    if not verify(data_dir, out_dir):
        sys.exit(1)


if __name__ == '__main__':
    main()
