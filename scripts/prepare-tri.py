"""Build the static TRI reporting-site catalog from an official EPA TRI Basic CSV.

Standard library only, no runtime API calls. The raw snapshot is read from
disk, its SHA-256 is verified over the original bytes before any parsing, and
the output uses the same static shard shape as the other Related Places
catalogs (see scripts/prepare-overlays.py).

Reporting locations only. Chemical quantities are never parsed or summed,
Pounds and Grams rows are never combined, Form A is never read as a zero
release, and no exposure, risk or compliance claim is derived from the data.

Usage:
    python scripts/prepare-tri.py --source work/tri-2024.csv --year 2024 \
        --retrieved 2026-10-20 --sha256 <64 hex> --output dist/data/overlays/tri.json
"""

import argparse, collections, csv, hashlib, io, json, math, os, re, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Scope mirrors scripts/prepare-overlays.py STATES (lower-48 codes -> FIPS).
STATE_CODES = 'AL AZ AR CA CO CT DE FL GA ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY'.split()
STATE_FIPS = '01 04 05 06 08 09 10 12 13 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40 41 42 44 45 46 47 48 49 50 51 53 54 55 56'.split()
STATES = dict(zip(STATE_CODES, STATE_FIPS))

C_YEAR = '1. YEAR'
C_TRIFD = '2. TRIFD'
C_FRS = '3. FRS ID'
C_NAME = '4. FACILITY NAME'
C_ST = '8. ST'
C_LAT = '12. LATITUDE'
C_LON = '13. LONGITUDE'
C_DATUM = '14. HORIZONTAL DATUM'
C_SECTOR = '23. INDUSTRY SECTOR'
C_DOC = '36. DOC_CTRL_NUM'
C_FORM = '49. FORM TYPE'
REQUIRED_COLUMNS = [C_YEAR, C_TRIFD, C_FRS, C_NAME, C_ST, C_LAT, C_LON, C_DATUM, C_SECTOR, C_DOC, C_FORM]
FORM_LABELS = {'R': 'Form R report', 'A': 'Form A certification'}

# Only datums we actually understand may pass through; a blank cell is reported
# as "not supplied" and no transformation is ever claimed.
UNDERSTOOD_DATUMS = {'WGS84', 'NAD83'}
HEX64 = re.compile(r'^[0-9a-fA-F]{64}$')
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
YEAR_RE = re.compile(r'^\d{4}$')


class TriSourceError(ValueError):
    """The source snapshot cannot be accepted as-is."""


def normalize_datum(value):
    return re.sub(r'[^A-Z0-9]', '', value.upper())


def coord_cell(lon, lat):
    """Classify a pair before geography filtering: blank, invalid, or finite.

    Finite out-of-bounds values remain finite so facility-level conflict checks
    see the original coordinate evidence rather than silently discarding it.
    """
    lon = (lon or '').strip()
    lat = (lat or '').strip()
    if not lon and not lat:
        return 'blank', None
    try:
        x, y = float(lon), float(lat)
    except ValueError:
        return 'invalid', None
    if not (math.isfinite(x) and math.isfinite(y)):
        return 'invalid', None
    return 'finite', (x, y)


def build(source, year, expected_sha256, retrieved):
    """Return the static shard record for a verified TRI Basic snapshot."""
    source = Path(source)
    year = str(year).strip()
    if not YEAR_RE.match(year):
        raise TriSourceError(f'year must be four digits, got {year!r}')
    retrieved = str(retrieved).strip()
    if not DATE_RE.match(retrieved):
        raise TriSourceError(f'retrieved must be YYYY-MM-DD, got {retrieved!r}')
    try:
        datetime.strptime(retrieved, '%Y-%m-%d')
    except ValueError as exc:
        raise TriSourceError(f'retrieved is not a real calendar date: {retrieved!r}') from exc
    expected_sha256 = str(expected_sha256).strip()
    if not HEX64.match(expected_sha256):
        raise TriSourceError('sha256 must be exactly 64 hexadecimal characters')
    if not source.is_file():
        raise TriSourceError(f'source file not found: {source}')
    raw = source.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest.lower() != expected_sha256.lower():
        raise TriSourceError(f'source SHA-256 {digest} does not match the expected digest')
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise TriSourceError(f'source is not valid UTF-8: {exc}') from exc

    reader = csv.reader(io.StringIO(text, newline=''), strict=True)
    line = 2
    try:
        header = next(reader)
    except csv.Error as exc:
        raise TriSourceError(f'line 1: malformed CSV: {exc}') from exc
    except StopIteration:
        raise TriSourceError('source is empty (no header row)')

    header = [h.strip() for h in header]
    duplicates = sorted(h for h, n in collections.Counter(header).items() if n > 1)
    if duplicates:
        raise TriSourceError('duplicate header column(s): ' + ', '.join(duplicates))
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        raise TriSourceError('missing required header column(s): ' + ', '.join(missing))
    idx = {c: header.index(c) for c in REQUIRED_COLUMNS}
    width = len(header)
    facilities = {}
    seen_docs = {}
    audit = collections.Counter()
    form_rows = collections.Counter()

    while True:
        try:
            row = next(reader)
        except csv.Error as exc:
            raise TriSourceError(f'line {line}: malformed CSV: {exc}') from exc
        except StopIteration:
            break
        if not row or all(not cell.strip() for cell in row):
            line += 1
            continue
        if len(row) != width:
            raise TriSourceError(f'line {line}: expected {width} columns, found {len(row)} (malformed or truncated row)')

        def cell(name):
            return row[idx[name]].strip()

        if cell(C_YEAR) != year:
            raise TriSourceError(f'line {line}: YEAR {cell(C_YEAR)!r} does not match requested year {year}')
        doc = cell(C_DOC)
        if not doc:
            raise TriSourceError(f'line {line}: missing DOC_CTRL_NUM')
        if doc in seen_docs:
            raise TriSourceError(f'line {line}: duplicate DOC_CTRL_NUM {doc!r} (first seen on line {seen_docs[doc]})')
        seen_docs[doc] = line
        form = cell(C_FORM).upper()
        if form not in FORM_LABELS:
            raise TriSourceError(f'line {line}: unrecognized FORM TYPE {form!r} (expected A or R)')
        trifd = cell(C_TRIFD)
        if not trifd:
            raise TriSourceError(f'line {line}: missing TRIFD')
        name = cell(C_NAME)
        if not name:
            raise TriSourceError(f'line {line}: missing FACILITY NAME for TRIFD {trifd}')

        audit['source chemical-report rows'] += 1
        form_rows[form] += 1
        facility = facilities.setdefault(trifd, {
            'forms': 0, 'names': set(), 'states': set(), 'coords': set(),
            'invalid_coord': False, 'blank_coord': False, 'map_coords': set(), 'datums': set(), 'pairs': set()})
        facility['forms'] += 1
        facility['names'].add(name)
        facility['states'].add(cell(C_ST))
        kind, value = coord_cell(row[idx[C_LON]], row[idx[C_LAT]])
        if kind == 'finite':
            facility['coords'].add(value)
            if -125 <= value[0] <= -66 and 24 <= value[1] <= 50:
                facility['map_coords'].add(value)
        elif kind == 'blank':
            facility['blank_coord'] = True
        elif kind == 'invalid':
            facility['invalid_coord'] = True
        facility['datums'].add(cell(C_DATUM))
        facility['pairs'].add((cell(C_SECTOR), form))
        line += 1

    if audit['source chemical-report rows'] == 0:
        raise TriSourceError('source contains no chemical-report rows')

    points = []
    excluded = collections.Counter()
    excluded_forms = collections.Counter()
    mapped_forms = 0

    for trifd in sorted(facilities):
        facility = facilities[trifd]
        names = sorted(facility['names'])
        if len(names) > 1:
            raise TriSourceError(f'facility {trifd}: conflicting FACILITY NAME values {names} across its records')

        states = facility['states']
        nonblank_states = sorted(s for s in states if s)
        if not nonblank_states:
            raise TriSourceError(f'facility {trifd}: no ST value in any of its records; cannot place it')
        if len(nonblank_states) > 1 or (len(states) > 1 and '' in states):
            raise TriSourceError(f'facility {trifd}: conflicting ST values {sorted(states)} across its records')

        # Conflict checks use the original finite values before map filtering.
        if len(facility['coords']) > 1:
            raise TriSourceError(f'facility {trifd}: conflicting coordinates {sorted(facility["coords"])} across its records')
        if facility['coords'] and (facility['blank_coord'] or facility['invalid_coord']):
            raise TriSourceError(f'facility {trifd}: some records carry unusable coordinates and others do not; refusing to choose one')

        datum_values = sorted(facility['datums'])
        known_datums = sorted({normalize_datum(value) for value in datum_values if value and normalize_datum(value) in UNDERSTOOD_DATUMS})
        bad_datums = sorted(value for value in datum_values if value and normalize_datum(value) not in UNDERSTOOD_DATUMS)
        if bad_datums:
            raise TriSourceError(f'facility {trifd}: unrecognized HORIZONTAL DATUM {bad_datums}')
        if len(known_datums) > 1:
            raise TriSourceError(f'facility {trifd}: conflicting HORIZONTAL DATUM values {datum_values} across its records')
        if known_datums and '' in facility['datums']:
            raise TriSourceError(f'facility {trifd}: blank and supplied HORIZONTAL DATUM values {datum_values} across its records')

        state = nonblank_states[0]
        if state not in STATES:
            excluded['outside lower 48'] += 1
            excluded_forms['outside lower 48'] += facility['forms']
            continue
        if not facility['map_coords']:
            excluded['missing/invalid coordinates'] += 1
            excluded_forms['missing/invalid coordinates'] += facility['forms']
            continue
        x, y = next(iter(facility['coords']))
        groups = []
        seen_groups = set()
        for sector, form in sorted(facility['pairs']):
            group = {'type': sector or 'Industry not supplied', 'status': f'{FORM_LABELS[form]} ({year})'}
            key = (group['type'], group['status'])
            if key not in seen_groups:
                seen_groups.add(key)
                groups.append(group)
        datum = sorted((d for d in facility['datums'] if d))
        datum_note = f'horizontal datum {datum[0]} as supplied' if datum else 'horizontal datum not supplied by the source'
        notes = (f'Reporting location for {facility["forms"]} chemical reporting form(s) in reporting year {year}. '
                 'Historical reporting year only; not live operating status, exposure, risk or a violation finding. '
                 f'Coordinates are source supplied; {datum_note}.')
        points.append({'id': trifd, 'name': names[0], 'state': STATES[state],
                       'longitude': round(x, 6), 'latitude': round(y, 6),
                       'date': year, 'notes': notes, 'groups': groups})
        mapped_forms += facility['forms']

    points.sort(key=lambda p: p['id'])
    if not points:
        raise TriSourceError('no in-scope reporting sites were produced from the source')
    ids = [p['id'] for p in points]
    if len(set(ids)) != len(ids):
        raise TriSourceError('duplicate point ids were produced')
    audit['distinct national facilities'] = len(facilities)
    audit['mapped facilities'] = len(points)
    audit['mapped chemical-report forms'] = mapped_forms
    audit['excluded facilities'] = sum(excluded.values())
    audit['excluded chemical-report forms'] = sum(excluded_forms.values())
    audit['Form R report rows'] = form_rows['R']
    audit['Form A certification rows'] = form_rows['A']
    if audit['mapped facilities'] + audit['excluded facilities'] != audit['distinct national facilities']:
        raise TriSourceError('internal reconciliation failed for facility counts')
    if audit['mapped chemical-report forms'] + audit['excluded chemical-report forms'] != audit['source chemical-report rows']:
        raise TriSourceError('internal reconciliation failed for form counts')
    record = {'schemaVersion': 1, 'retrieved': retrieved, 'points': points,
              'audit': dict(audit), 'excluded': dict(excluded),
              'exclusionsSummary': '; '.join(f'{n:,} {reason}' for reason, n in excluded.items()),
              'sourceFiles': [{'file': source.name, 'sha256': digest}]}
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description='Build the static TRI reporting-site catalog from an official EPA TRI Basic CSV snapshot.')
    parser.add_argument('--source', required=True, help='Path to the raw EPA TRI Basic CSV')
    parser.add_argument('--year', required=True, help='Reporting year the snapshot must contain')
    parser.add_argument('--retrieved', required=True, help='Actual UTC acquisition date, YYYY-MM-DD')
    parser.add_argument('--sha256', required=True, help='Expected SHA-256 (64 hex) of the source bytes')
    parser.add_argument('--output', required=True, help='Destination JSON path (written atomically)')
    args = parser.parse_args(argv)
    try:
        record = build(args.source, args.year, args.sha256, args.retrieved)
    except TriSourceError as exc:
        print(f'prepare-tri: {exc}', file=sys.stderr)
        return 1
    payload = json.dumps(record, ensure_ascii=False, separators=(',', ':'))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + '.tmp')
    with open(tmp, 'w', encoding='utf-8', newline='') as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, out)
    print(f"tri {len(record['points'])} points retrieved {record['retrieved']} excluded {record['excluded']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
