#!/usr/bin/env python3
"""Encode the county geometry compactly for delivery.

`dist/data/counties.geojson` is 1,044 KB gzipped, which is most of what a
visitor downloads before the map appears. Two things make it large: every
coordinate is a full decimal string, and consecutive coordinates repeat most
of their digits.

This quantises coordinates onto an integer grid and stores deltas between
consecutive points. Small integers that mostly repeat compress far better than
decimal strings. The saving is about 55% with a worst-case positional error of
roughly 64 metres, which is under half a pixel at the deepest zoom this app
offers.

This does NOT build a topology. TopoJSON would also remove the duplicated
shared borders that GeoJSON stores twice and would be smaller again, but it
needs a build tool and a runtime decoder library. This needs neither.

Standard library only. No network.
"""

import argparse
import gzip
import json
import math
import sys
from pathlib import Path

# 1e5 grid over the national bounding box gives about 64 m. 1e4 was measured at
# about 643 m, which is visible when a state is zoomed in.
DEFAULT_QUANTIZATION = 100000
PROPERTY_ORDER = ('fips', 'state', 'name', 'stateName')


def repo_root():
    return Path(__file__).resolve().parent.parent


def iter_rings(coords, depth):
    """Yield every coordinate ring, whatever the nesting depth."""
    if depth == 0:
        yield coords
        return
    for part in coords:
        yield from iter_rings(part, depth - 1)


def ring_depth(geom_type):
    # Polygon nests rings one level deep, MultiPolygon two.
    return {'Polygon': 1, 'MultiPolygon': 2}[geom_type]


def encode(geojson, quantization):
    xs_min = ys_min = math.inf
    xs_max = ys_max = -math.inf
    for feature in geojson['features']:
        geom = feature['geometry']
        for ring in iter_rings(geom['coordinates'], ring_depth(geom['type'])):
            for x, y in ring:
                xs_min = min(xs_min, x); xs_max = max(xs_max, x)
                ys_min = min(ys_min, y); ys_max = max(ys_max, y)

    scale_x = (xs_max - xs_min) / (quantization - 1)
    scale_y = (ys_max - ys_min) / (quantization - 1)

    def encode_ring(ring):
        out = []
        prev_x = prev_y = 0
        for x, y in ring:
            qx = round((x - xs_min) / scale_x)
            qy = round((y - ys_min) / scale_y)
            out.append(qx - prev_x)
            out.append(qy - prev_y)
            prev_x, prev_y = qx, qy
        return out

    def encode_coords(coords, depth):
        if depth == 0:
            return encode_ring(coords)
        return [encode_coords(part, depth - 1) for part in coords]

    features = []
    for feature in geojson['features']:
        geom = feature['geometry']
        props = feature['properties']
        features.append({
            'p': [props.get(key) for key in PROPERTY_ORDER],
            't': geom['type'],
            'c': encode_coords(geom['coordinates'], ring_depth(geom['type'])),
        })

    return {
        'format': 'quantized-delta-v1',
        'quantization': quantization,
        'translate': [xs_min, ys_min],
        'scale': [scale_x, scale_y],
        'properties': list(PROPERTY_ORDER),
        'features': features,
    }


def decode(doc):
    """Reference decoder. The app needs the same 15 lines in JavaScript."""
    tx, ty = doc['translate']
    sx, sy = doc['scale']

    def decode_ring(flat):
        ring = []
        x = y = 0
        for i in range(0, len(flat), 2):
            x += flat[i]
            y += flat[i + 1]
            ring.append([x * sx + tx, y * sy + ty])
        return ring

    def decode_coords(node, depth):
        if depth == 0:
            return decode_ring(node)
        return [decode_coords(part, depth - 1) for part in node]

    features = []
    for item in doc['features']:
        features.append({
            'type': 'Feature',
            'properties': dict(zip(doc['properties'], item['p'])),
            'geometry': {
                'type': item['t'],
                'coordinates': decode_coords(item['c'], ring_depth(item['t'])),
            },
        })
    return {'type': 'FeatureCollection', 'features': features}


def verify(original, doc):
    """Decode and compare every coordinate against the original."""
    restored = decode(doc)
    if len(restored['features']) != len(original['features']):
        print('FAIL feature count changed')
        return False

    worst = 0.0
    worst_fips = None
    props_bad = []
    points = 0

    for src, out in zip(original['features'], restored['features']):
        if src['properties'].get('fips') != out['properties'].get('fips'):
            props_bad.append(src['properties'].get('fips'))
            continue
        for key in PROPERTY_ORDER:
            if src['properties'].get(key) != out['properties'].get(key):
                props_bad.append(f"{src['properties'].get('fips')}:{key}")
        if src['geometry']['type'] != out['geometry']['type']:
            props_bad.append(f"{src['properties'].get('fips')}:type")
            continue
        depth = ring_depth(src['geometry']['type'])
        for a, b in zip(iter_rings(src['geometry']['coordinates'], depth),
                        iter_rings(out['geometry']['coordinates'], depth)):
            if len(a) != len(b):
                props_bad.append(f"{src['properties'].get('fips')}:ringlen")
                break
            for (ax, ay), (bx, by) in zip(a, b):
                points += 1
                d = max(abs(ax - bx), abs(ay - by))
                if d > worst:
                    worst = d
                    worst_fips = src['properties'].get('fips')

    metres = worst * 111000
    print(f'coordinates checked   {points}')
    print(f'worst deviation       {worst:.7f} deg  about {metres:.0f} m  (county {worst_fips})')
    if props_bad:
        print(f'FAIL property or structure mismatches: {props_bad[:5]} ({len(props_bad)} total)')
        return False
    print('every property and ring structure preserved')
    # A point must never move by more than one grid cell.
    limit = max(doc['scale']) * 1.5
    if worst > limit:
        print(f'FAIL deviation exceeds one grid cell ({limit:.7f} deg)')
        return False
    return True


def main():
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--src', default=str(root / 'dist' / 'data' / 'counties.geojson'))
    parser.add_argument('--out', default=str(root / 'dist' / 'data' / 'counties.qd.json'))
    parser.add_argument('--quantization', type=int, default=DEFAULT_QUANTIZATION)
    args = parser.parse_args()

    src = Path(args.src)
    out = Path(args.out)
    original = json.loads(src.read_text(encoding='utf-8'))

    doc = encode(original, args.quantization)
    text = json.dumps(doc, separators=(',', ':'))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding='utf-8')

    before = len(gzip.compress(src.read_bytes()))
    after = len(gzip.compress(text.encode('utf-8')))
    print(f'features              {len(doc["features"])}')
    print(f'quantization          {args.quantization}')
    print(f'source                {before / 1024:.0f} KB gz')
    print(f'encoded               {after / 1024:.0f} KB gz')
    print(f'saving                {(before - after) / 1024:.0f} KB gz '
          f'({100 * (before - after) / before:.0f}%)')
    print(f'output                {out}')
    print()
    if not verify(original, doc):
        sys.exit(1)


if __name__ == '__main__':
    main()
