#!/usr/bin/env python3
"""HRSA HPSA primary-care component source audit.

Source audit only. This script does not emit an application dataset and
does not establish legal clearance to reuse the source.

No network access. Python standard library only.
"""

import csv
import hashlib
import json
import statistics
import sys
from argparse import ArgumentParser
from collections import Counter
from pathlib import Path

JOIN_KEY = 'State and County Federal Information Processing Standard Code'
COMMON_FIPS = 'Common State County FIPS Code'
COUNTY_FIPS = 'County or County Equivalent Federal Information Processing Standard Code'

# Only these fields are retained per row. The full file is 79,750 rows by 66
# columns; keeping every column as a dict costs hundreds of megabytes.
KEEP_FIELDS = (
    'HPSA ID', 'HPSA Name', 'Designation Type', 'HPSA Discipline Class',
    'HPSA Score', 'HPSA Status', 'Withdrawn Date',
    'HPSA Component Source Identification Number',
    'HPSA Component Type Description', 'HPSA Designation Population',
    'HPSA Resident Civilian Population', 'HPSA FTE', 'HPSA Shortage',
    'HPSA Formal Ratio', 'HPSA Population Type', 'Rural Status',
    COMMON_FIPS, COUNTY_FIPS, JOIN_KEY,
    'County Equivalent Name', 'State Name', 'State Abbreviation',
    'Data Warehouse Record Create Date Text',
)

NUMERIC_FIELDS = (
    'HPSA Score', 'HPSA Designation Population',
    'HPSA Resident Civilian Population', 'HPSA FTE', 'HPSA Shortage',
    'HPSA Formal Ratio',
)

SUBCOUNTY_TYPES = frozenset({'Census Tract', 'County Subdivision', 'Unknown'})


def repo_root():
    return Path(__file__).resolve().parent.parent


def compute_sha256(file_path):
    """Stream the file so a large CSV never lands in memory at once."""
    digest = hashlib.sha256()
    with open(file_path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b''):
            digest.update(chunk)
    return digest.hexdigest()


def parse_number(value):
    """Return an int or float, or None when the value is not numeric."""
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return float(text) if '.' in text else int(text)
    except ValueError:
        return None


def usable_fips(value):
    """A join FIPS is usable only when it is exactly five digits.

    The source uses the literal sentinel XXXXX for a component whose county
    is not determined. That sentinel is five characters long, so a length
    test alone accepts it as a county. It must not become one.
    """
    if value is None:
        return None
    text = value.strip()
    return text if len(text) == 5 and text.isdigit() else None


def read_csv_audit(csv_path):
    rows = []
    vintage_dates = Counter()
    with open(csv_path, encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        for record in reader:
            rows.append({key: (record.get(key) or '') for key in KEEP_FIELDS})
            vintage = record.get('Data Warehouse Record Create Date Text') or ''
            if vintage:
                vintage_dates[vintage] += 1
    return rows, fieldnames, vintage_dates


def validate_schema(rows, fieldnames):
    checks = {
        'field_count': len(fieldnames),
        'has_empty_trailing_column': '' in fieldnames,
    }

    discipline = Counter(row['HPSA Discipline Class'] for row in rows)
    checks['discipline_class'] = dict(discipline)
    checks['discipline_class_matched'] = (
        discipline == Counter({'Primary Care': len(rows)}))

    status = Counter(row['HPSA Status'] for row in rows)
    checks['status'] = dict(status)
    checks['status_matched'] = status == Counter({
        'Withdrawn': 48840, 'Designated': 20998,
        'Proposed For Withdrawal': 9912})

    component = Counter(row['HPSA Component Type Description'] for row in rows)
    checks['component_type'] = dict(component)
    checks['component_type_matched'] = component == Counter({
        'Census Tract': 48330, 'County Subdivision': 18050,
        'Unknown': 7960, 'Single County': 5410})

    return checks


def validate_fips_fields(rows):
    result = {'join_key': JOIN_KEY}
    fields = {
        COMMON_FIPS: 'common_state_county',
        COUNTY_FIPS: 'county_equiv',
        JOIN_KEY: 'state_county',
    }

    for csv_name, key in fields.items():
        analysis = {
            'blank_count': 0,
            'non_5_length_count': 0,
            'not_five_digits_count': 0,
            'length_distribution': {},
            'non_5_examples': [],
            'five_char_non_numeric_examples': [],
        }
        for row in rows:
            raw = row[csv_name]
            if not raw.strip():
                analysis['blank_count'] += 1
                continue
            length = len(raw)
            analysis['length_distribution'][length] = (
                analysis['length_distribution'].get(length, 0) + 1)
            if length != 5:
                analysis['non_5_length_count'] += 1
                if len(analysis['non_5_examples']) < 5:
                    analysis['non_5_examples'].append(repr(raw))
            if usable_fips(raw) is None:
                analysis['not_five_digits_count'] += 1
                if (length == 5
                        and repr(raw) not in analysis['five_char_non_numeric_examples']
                        and len(analysis['five_char_non_numeric_examples']) < 5):
                    analysis['five_char_non_numeric_examples'].append(repr(raw))
        analysis['length_distribution'] = {
            str(k): v for k, v in sorted(analysis['length_distribution'].items())}
        result[key] = analysis

    all_equal = 0
    disagreements = []
    for row in rows:
        present = [row[COMMON_FIPS].strip(), row[COUNTY_FIPS].strip(),
                   row[JOIN_KEY].strip()]
        present = [value for value in present if value]
        if len(present) == 3 and len(set(present)) == 1:
            all_equal += 1
        elif len(present) > 1 and len(set(present)) > 1:
            if len(disagreements) < 5:
                disagreements.append({
                    'hpsa_id': row['HPSA ID'],
                    'common_state_county': row[COMMON_FIPS],
                    'county_equiv': row[COUNTY_FIPS],
                    'state_county': row[JOIN_KEY],
                })
    result['all_three_present_and_equal'] = all_equal
    result['disagreement_examples'] = disagreements
    result['disagreement_note'] = (
        'The three FIPS-like columns are reported as observed. No column is '
        'repaired, padded or reconciled against another.')
    return result


def validate_raw_values(rows):
    result = {}
    for field in NUMERIC_FIELDS:
        analysis = {
            'empty_count': 0,
            'whitespace_only_count': 0,
            'numeric_count': 0,
            'non_numeric_count': 0,
            'non_numeric_examples': [],
            'numeric_min': None,
            'numeric_max': None,
        }
        values = []
        for row in rows:
            raw = row[field]
            if raw == '':
                analysis['empty_count'] += 1
            elif not raw.strip():
                analysis['whitespace_only_count'] += 1
            else:
                parsed = parse_number(raw)
                if parsed is None:
                    analysis['non_numeric_count'] += 1
                    if (len(analysis['non_numeric_examples']) < 8
                            and repr(raw) not in analysis['non_numeric_examples']):
                        analysis['non_numeric_examples'].append(repr(raw))
                else:
                    analysis['numeric_count'] += 1
                    values.append(parsed)
        if values:
            analysis['numeric_min'] = min(values)
            analysis['numeric_max'] = max(values)
        result[field] = analysis

    out_of_range = 0
    out_examples = []
    for row in rows:
        parsed = parse_number(row['HPSA Score'])
        if parsed is not None and not 0 <= parsed <= 26:
            out_of_range += 1
            if len(out_examples) < 5:
                out_examples.append({'raw_value': row['HPSA Score'],
                                     'parsed': parsed})
    result['HPSA Score']['out_of_range_0_26_count'] = out_of_range
    result['HPSA Score']['out_of_range_examples'] = out_examples

    withdrawn = {'empty_count': 0, 'whitespace_only_count': 0,
                 'non_empty_count': 0, 'examples': []}
    for row in rows:
        raw = row['Withdrawn Date']
        if raw == '':
            withdrawn['empty_count'] += 1
        elif not raw.strip():
            withdrawn['whitespace_only_count'] += 1
        else:
            withdrawn['non_empty_count'] += 1
            if (len(withdrawn['examples']) < 8
                    and repr(raw) not in withdrawn['examples']):
                withdrawn['examples'].append(repr(raw))
    result['Withdrawn Date'] = withdrawn

    result['coercion_note'] = (
        'No empty, whitespace or unparsable value is coerced to zero. Each is '
        'counted as unknown.')
    return result


def get_designated_subset(rows):
    return [row for row in rows if row['HPSA Status'] == 'Designated']


def analyze_designated_subset(rows):
    analysis = {
        'row_count': len(rows),
        'distinct_hpsa_id_count': len({row['HPSA ID'] for row in rows}),
        'distinct_component_source_id_count': len(
            {row['HPSA Component Source Identification Number'] for row in rows}),
        'rows_with_usable_join_fips': sum(
            1 for row in rows if usable_fips(row[JOIN_KEY]) is not None),
        'rows_with_unusable_join_fips': sum(
            1 for row in rows if usable_fips(row[JOIN_KEY]) is None),
        'component_type_breakdown': dict(
            Counter(row['HPSA Component Type Description'] for row in rows)),
    }

    unusable = Counter(repr(row[JOIN_KEY].strip()) for row in rows
                       if usable_fips(row[JOIN_KEY]) is None)
    analysis['unusable_join_fips_values'] = dict(unusable)

    # Most designated rows carry no component source id at all, so a naive
    # (component id, FIPS) duplicate count is dominated by blanks and says
    # nothing about component identity. Blank-id rows are counted separately.
    blank_id_rows = 0
    blank_by_type = Counter()
    pairs = Counter()
    for row in rows:
        comp = row['HPSA Component Source Identification Number'].strip()
        if not comp:
            blank_id_rows += 1
            blank_by_type[row['HPSA Component Type Description']] += 1
            continue
        pairs[(comp, row[JOIN_KEY].strip())] += 1

    duplicates = {pair: count for pair, count in pairs.items() if count > 1}
    analysis['rows_with_blank_component_source_id'] = blank_id_rows
    analysis['blank_component_source_id_by_type'] = dict(sorted(blank_by_type.items()))
    analysis['rows_with_component_source_id'] = len(rows) - blank_id_rows
    analysis['duplicate_component_rows'] = len(duplicates)
    analysis['duplicate_component_examples'] = [
        {'component_source_id': comp, 'fips': fips, 'repeat_count': count}
        for (comp, fips), count in sorted(duplicates.items())[:5]]
    analysis['component_identity_note'] = (
        'HPSA Component Source Identification Number is blank on most '
        'designated rows, so it cannot serve as a component identity key. The '
        'duplicate count above covers only rows that carry an id.')
    return analysis


def aggregate_to_counties(rows):
    counties = {}
    for row in rows:
        fips = usable_fips(row[JOIN_KEY])
        if fips is None:
            continue
        entry = counties.get(fips)
        if entry is None:
            entry = counties[fips] = {
                'designated_component_rows': 0,
                'hpsa_ids': set(),
                'component_types': set(),
                'scores': [],
                'county_name': row['County Equivalent Name'],
                'state_name': row['State Name'],
            }
        entry['designated_component_rows'] += 1
        entry['hpsa_ids'].add(row['HPSA ID'])
        entry['component_types'].add(row['HPSA Component Type Description'])
        parsed = parse_number(row['HPSA Score'])
        if parsed is not None:
            entry['scores'].append(parsed)

    measures = {}
    for fips, entry in counties.items():
        measures[fips] = {
            'max_hpsa_score': max(entry['scores']) if entry['scores'] else None,
            'designated_component_rows': entry['designated_component_rows'],
            'distinct_hpsa_ids': len(entry['hpsa_ids']),
            'component_types': sorted(entry['component_types']),
            'county_name': entry['county_name'],
            'state_name': entry['state_name'],
        }
    return measures


def analyze_county_measure(measures):
    scores = [m['max_hpsa_score'] for m in measures.values()
              if m['max_hpsa_score'] is not None]
    subcounty_only = sorted(
        fips for fips, m in measures.items()
        if m['component_types'] and not set(m['component_types']) - SUBCOUNTY_TYPES)

    analysis = {
        'measure': 'max_hpsa_score',
        'direction': ('higher is worse: a higher HPSA score means greater '
                      'designated shortage priority'),
        'county_count': len(measures),
        'counties_with_score': len(scores),
        'counties_without_parsable_score': len(measures) - len(scores),
        'score_min': min(scores) if scores else None,
        'score_max': max(scores) if scores else None,
        'score_mean': statistics.mean(scores) if scores else None,
        'score_median': statistics.median(scores) if scores else None,
        'score_distribution': {str(score): count for score, count
                               in sorted(Counter(scores).items())},
        'counties_with_only_subcounty_components': len(subcounty_only),
        'subcounty_only_note': (
            'These counties carry no whole-county component. A census tract or '
            'county subdivision designation does not describe the whole county.'),
    }
    return analysis, subcounty_only


def get_county_examples(measures, subcounty_only):
    def score_of(fips):
        value = measures[fips]['max_hpsa_score']
        return -1 if value is None else value

    whole = sorted((f for f, m in measures.items()
                    if 'Single County' in m['component_types']),
                   key=lambda f: (-score_of(f), f))
    tract_only = sorted(subcounty_only, key=lambda f: (-score_of(f), f))
    ordered = sorted(measures, key=lambda f: (score_of(f), f))

    chosen = []
    candidates = whole[:1] + tract_only[:1] + [
        ordered[0], ordered[-1], ordered[len(ordered) // 2]]
    for candidate in candidates:
        if candidate not in chosen:
            chosen.append(candidate)
    for fips in sorted(measures):
        if len(chosen) >= 8:
            break
        if fips not in chosen:
            chosen.append(fips)

    return [{
        'fips': fips,
        'county_name': measures[fips]['county_name'],
        'state_name': measures[fips]['state_name'],
        'max_hpsa_score': measures[fips]['max_hpsa_score'],
        'designated_component_rows': measures[fips]['designated_component_rows'],
        'component_types': measures[fips]['component_types'],
        'whole_county_component': 'Single County' in measures[fips]['component_types'],
    } for fips in sorted(chosen[:8])]


def load_counties_geojson(path):
    with open(path, encoding='utf-8') as handle:
        geojson = json.load(handle)
    features = geojson.get('features', [])
    names = {}
    for feature in features:
        props = feature.get('properties', {})
        fips = props.get('fips', '')
        if fips:
            names[fips] = (props.get('name', ''), props.get('stateName', ''))
    return {'feature_count': len(features),
            'matches_3107': len(features) == 3107,
            'fips_set': set(names),
            'fips_names': names}


def geographic_join(measures, atlas):
    source = set(measures)
    atlas_fips = atlas['fips_set']

    source_only = sorted(source - atlas_fips)
    atlas_only = sorted(atlas_fips - source)

    result = {
        'atlas_feature_count': atlas['feature_count'],
        'atlas_count_matches_3107': atlas['matches_3107'],
        'atlas_counties_with_designation': len(source & atlas_fips),
        'atlas_counties_not_designated': len(atlas_only),
        'atlas_counties_not_designated_note': (
            'These atlas counties have no current primary-care HPSA designation '
            'recorded in this extract. That is not the same as missing data and '
            'is not evidence of adequate access.'),
        'source_only_fips_count': len(source_only),
        'source_only_fips': [{
            'fips': fips,
            'county_name': measures[fips]['county_name'],
            'state_name': measures[fips]['state_name'],
        } for fips in source_only],
        'atlas_only_fips_count': len(atlas_only),
        'atlas_only_fips_examples': [{
            'fips': fips,
            'name': atlas['fips_names'][fips][0],
            'stateName': atlas['fips_names'][fips][1],
        } for fips in atlas_only[:20]],
        'remap_policy': (
            'No FIPS is remapped, padded or fuzzy matched. Both unmatched sides '
            'are reported as observed.'),
    }

    ct_source = sorted(f for f in source if f.startswith('09'))
    ct_atlas = sorted(f for f in atlas_fips if f.startswith('09'))
    ct_shared = sorted(set(ct_source) & set(ct_atlas))
    result['connecticut_note'] = (
        'State FIPS 09: the source carries ' + str(len(ct_source)) + ' codes '
        + str(ct_source) + ' and the atlas carries ' + str(len(ct_atlas))
        + ' codes ' + str(ct_atlas) + '. Shared codes: '
        + (str(ct_shared) if ct_shared else 'none')
        + '. The source uses the newer Connecticut planning regions and the '
        'atlas uses the legacy counties, so every Connecticut county reads as '
        'not designated. That is an artefact of geography vintage, not an '
        'absence of designations. No crosswalk is applied here.')
    result['connecticut_atlas_counties_affected'] = len(
        [f for f in ct_atlas if f not in set(ct_source)])
    return result


def spot_check_verify(measures, csv_path):
    """Recompute three counties by re-reading the CSV from disk.

    This deliberately re-reads the file rather than reusing the parsed rows or
    the aggregation, so an aggregation bug cannot hide behind itself.
    """
    if not measures:
        return [{'error': 'no counties to spot check', 'agree': False}]

    def score_of(fips):
        value = measures[fips]['max_hpsa_score']
        return -1 if value is None else value

    scored = sorted((f for f in measures
                     if measures[f]['max_hpsa_score'] is not None),
                    key=lambda f: (score_of(f), f))
    tract_only = sorted(
        (f for f, m in measures.items()
         if m['component_types']
         and not set(m['component_types']) - SUBCOUNTY_TYPES
         and m['max_hpsa_score'] is not None),
        key=lambda f: (score_of(f), f))

    targets = []
    candidates = [scored[-1], scored[len(scored) // 2],
                  tract_only[len(tract_only) // 2] if tract_only else scored[0]]
    for candidate in candidates:
        if candidate not in targets:
            targets.append(candidate)

    found = {fips: [] for fips in targets}
    with open(csv_path, encoding='utf-8-sig', newline='') as handle:
        for record in csv.DictReader(handle):
            if record.get('HPSA Status') != 'Designated':
                continue
            fips = usable_fips(record.get(JOIN_KEY))
            if fips in found:
                found[fips].append(record.get('HPSA Score') or '')

    results = []
    for fips in targets:
        raw_scores = found[fips]
        parsed = [parse_number(value) for value in raw_scores]
        parsed = [value for value in parsed if value is not None]
        recomputed = max(parsed) if parsed else None
        results.append({
            'fips': fips,
            'county_name': measures[fips]['county_name'],
            'state_name': measures[fips]['state_name'],
            'component_types': measures[fips]['component_types'],
            'rows_found_on_rescan': len(raw_scores),
            'rows_in_aggregation': measures[fips]['designated_component_rows'],
            'recomputed_max_hpsa_score': recomputed,
            'aggregated_max_hpsa_score': measures[fips]['max_hpsa_score'],
            'agree': (recomputed == measures[fips]['max_hpsa_score']
                      and len(raw_scores) == measures[fips]['designated_component_rows']),
            'contributing_score_strings': sorted(raw_scores)[:5],
        })
    return results


def main():
    root = repo_root()
    parser = ArgumentParser(description='HRSA HPSA primary-care source audit')
    parser.add_argument('--csv', default=str(
        root / 'work' / 'healthcare-hpsa-audit' / 'BCD_HPSA_FCT_DET_PC.csv'))
    parser.add_argument('--counties', default=str(
        root / 'dist' / 'data' / 'counties.geojson'))
    parser.add_argument('--out', default=str(
        root / 'work' / 'healthcare-hpsa-audit' / 'audit.json'))
    args = parser.parse_args()

    csv_path = Path(args.csv)
    out_path = Path(args.out)

    rows, fieldnames, vintage = read_csv_audit(csv_path)
    designated = get_designated_subset(rows)
    measures = aggregate_to_counties(designated)
    county_analysis, subcounty_only = analyze_county_measure(measures)
    atlas = load_counties_geojson(Path(args.counties))

    audit = {
        'source': {
            'name': ('HRSA Health Professional Shortage Areas (HPSA) - '
                     'Primary Care, component detail'),
            'file_name': csv_path.name,
            'byte_size': csv_path.stat().st_size,
            'sha256': compute_sha256(csv_path),
            'row_count': len(rows),
            'field_count': len(fieldnames),
            'extract_vintage': dict(sorted(vintage.items())),
        },
        'schema_checks': validate_schema(rows, fieldnames),
        'fips_fields': validate_fips_fields(rows),
        'raw_value_conventions': validate_raw_values(rows),
        'designated_subset': analyze_designated_subset(designated),
        'county_measure_candidate': county_analysis,
        'geographic_join': geographic_join(measures, atlas),
        'spot_check': spot_check_verify(measures, csv_path),
        'prohibited_operations': [
            'Do not sum HPSA Designation Population across a county. The '
            'designation population repeats on every component row of the same '
            'HPSA, so a sum double counts. No county population total is '
            'computed from this file.',
            'Do not compute a provider supply rate such as physicians per '
            '100,000 residents from this file. It does not measure supply.',
            'A county absent from the designated subset means no current '
            'primary-care HPSA designation is recorded. Represent it as '
            'not_designated. Never as score zero and never as missing.',
            'Do not treat the five character sentinel XXXXX as a county FIPS.',
        ],
        'unresolved_gates': [
            'Is max HPSA score a defensible county measure when most components '
            'are sub-county? A tract designation does not describe the county.',
            'HPSA score is an administrative priority score for clinician '
            'placement, not a measured provider supply rate.',
            'Proposed For Withdrawal rows are excluded from the subset. That '
            'choice needs human review.',
            'The HPSA datamart metadata workbook does not document several CSV '
            'columns used here: HPSA Designation Population, HPSA FTE, HPSA '
            'Shortage, HPSA Component Type Description and Withdrawn Date.',
            'Connecticut cannot join at all. A planning-region to county '
            'decision is required before any ingestion.',
            'Source reuse terms require human confirmation. This script does '
            'not establish legal clearance.',
        ],
    }
    audit['county_measure_candidate']['examples'] = get_county_examples(
        measures, subcounty_only)

    with open(out_path, 'w', encoding='utf-8') as handle:
        json.dump(audit, handle, indent=2, sort_keys=True)
        handle.write('\n')

    agreed = all(check.get('agree') for check in audit['spot_check'])
    join = audit['geographic_join']
    print('rows read                     ' + str(len(rows)))
    print('designated rows               ' + str(len(designated)))
    print('unusable join FIPS (desig.)   '
          + str(audit['designated_subset']['rows_with_unusable_join_fips']))
    print('counties with a designation   ' + str(county_analysis['county_count']))
    print('sub-county-only counties      '
          + str(county_analysis['counties_with_only_subcounty_components']))
    print('atlas features                ' + str(join['atlas_feature_count']))
    print('atlas counties designated     '
          + str(join['atlas_counties_with_designation']))
    print('atlas counties not designated '
          + str(join['atlas_counties_not_designated']))
    print('  of which Connecticut        '
          + str(join['connecticut_atlas_counties_affected']))
    print('source-only FIPS              ' + str(join['source_only_fips_count']))
    print('spot check                    ' + ('PASS' if agreed else 'FAIL'))
    print('output                        ' + str(out_path))

    if not agreed:
        print('FAILURE: spot check disagreed with the aggregation.')
        sys.exit(1)


if __name__ == '__main__':
    main()
