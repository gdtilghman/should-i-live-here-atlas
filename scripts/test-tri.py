"""Tests for scripts/prepare-tri.py using synthetic TRI Basic field layouts.

Run: python scripts/test-tri.py
"""

import csv, hashlib, importlib.util, io, json, pathlib, subprocess, sys, tempfile, unittest

HERE = pathlib.Path(__file__).resolve().parent

_spec = importlib.util.spec_from_file_location('prepare_tri', HERE / 'prepare-tri.py')

tri = importlib.util.module_from_spec(_spec)

_spec.loader.exec_module(tri)

# Real TRI Basic column names; unused columns are simply omitted from the
# synthetic fixtures. UNIT OF MEASURE is kept to prove quantities are ignored.
BASE_COLUMNS = ['1. YEAR', '2. TRIFD', '3. FRS ID', '4. FACILITY NAME', '8. ST',
                '12. LATITUDE', '13. LONGITUDE', '14. HORIZONTAL DATUM',
                '23. INDUSTRY SECTOR', '36. DOC_CTRL_NUM', '49. FORM TYPE',
                '50. UNIT OF MEASURE']


def record(**values):
    row = {c: '' for c in BASE_COLUMNS}

    row.update(values)

    return row


def base(**values):
    values.setdefault('1. YEAR', '2024')

    values.setdefault('4. FACILITY NAME', 'Alpha')

    values.setdefault('8. ST', 'TX')

    values.setdefault('12. LATITUDE', '30.0')

    values.setdefault('13. LONGITUDE', '-95.0')

    values.setdefault('49. FORM TYPE', 'R')

    return record(**values)


def csv_bytes(records, columns=BASE_COLUMNS):
    buf = io.StringIO(newline='')

    writer = csv.writer(buf)

    writer.writerow(columns)

    for row in records:
        writer.writerow([row.get(c, '') for c in columns])

    return buf.getvalue().encode('utf-8')


class TriTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()

        self.dir = pathlib.Path(self._tmp.name)

        self.n = 0

    def tearDown(self):
        self._tmp.cleanup()

    def source(self, data, name='tri.csv'):
        path = self.dir / name

        path.write_bytes(data)

        return path

    def build(self, data, year=2024, retrieved='2026-10-20', name='tri.csv'):
        path = self.source(data, name)

        digest = hashlib.sha256(path.read_bytes()).hexdigest()

        return tri.build(path, year, digest, retrieved)

    def assert_fails(self, data, *needles, **kwargs):
        with self.assertRaises(tri.TriSourceError) as ctx:
            self.build(data, **kwargs)

        message = str(ctx.exception)

        for needle in needles:
            self.assertIn(needle, message)

        return message

    # --- grouping and identity ------------------------------------------

    def test_groups_are_same_row_pairs_not_a_cross_product(self):
        data = csv_bytes([
            base(**{'2. TRIFD': 'T1', '36. DOC_CTRL_NUM': 'D1', '23. INDUSTRY SECTOR': 'Chemicals', '49. FORM TYPE': 'R'}),
            base(**{'2. TRIFD': 'T1', '36. DOC_CTRL_NUM': 'D2', '23. INDUSTRY SECTOR': 'Paper', '49. FORM TYPE': 'A'}),
        ])

        record_out = self.build(data)

        point = record_out['points'][0]

        self.assertEqual(point['groups'], [
            {'type': 'Chemicals', 'status': 'Form R report (2024)'},
            {'type': 'Paper', 'status': 'Form A certification (2024)'},
        ])

    def test_blank_industry_gets_placeholder_and_duplicate_groups_collapse(self):
        data = csv_bytes([
            base(**{'2. TRIFD': 'T1', '36. DOC_CTRL_NUM': 'D1', '23. INDUSTRY SECTOR': ''}),
            base(**{'2. TRIFD': 'T1', '36. DOC_CTRL_NUM': 'D2', '23. INDUSTRY SECTOR': ''}),
            base(**{'2. TRIFD': 'T1', '36. DOC_CTRL_NUM': 'D3', '23. INDUSTRY SECTOR': 'Chemicals'}),
        ])

        point = self.build(data)['points'][0]

        self.assertEqual(point['groups'], [
            {'type': 'Industry not supplied', 'status': 'Form R report (2024)'},
            {'type': 'Chemicals', 'status': 'Form R report (2024)'},
        ])

    def test_distinct_trifd_sharing_frs_are_separate_points(self):
        data = csv_bytes([
            base(**{'2. TRIFD': 'T1', '3. FRS ID': '110007', '4. FACILITY NAME': 'Alpha', '36. DOC_CTRL_NUM': 'D1'}),
            base(**{'2. TRIFD': 'T2', '3. FRS ID': '110007', '4. FACILITY NAME': 'Beta', '36. DOC_CTRL_NUM': 'D2'}),
        ])

        points = self.build(data)['points']

        self.assertEqual([p['id'] for p in points], ['T1', 'T2'])

        self.assertEqual([p['name'] for p in points], ['Alpha', 'Beta'])

    def test_point_shape_uses_state_fips_six_decimals_date_and_notes(self):
        data = csv_bytes([
            base(**{'2. TRIFD': 'T1', '4. FACILITY NAME': 'Alpha', '8. ST': 'MA',
                    '12. LATITUDE': '42.10000004', '13. LONGITUDE': '-71.80000009',
                    '23. INDUSTRY SECTOR': 'Chemicals', '36. DOC_CTRL_NUM': 'D1'}),
        ])

        point = self.build(data)['points'][0]

        self.assertEqual(point['state'], '25')

        self.assertEqual(point['latitude'], 42.1)

        self.assertEqual(point['longitude'], -71.8)

        self.assertEqual(point['date'], '2024')

        self.assertIn('1 chemical reporting form', point['notes'])

        self.assertIn('not live operating status', point['notes'])

        self.assertIn('horizontal datum not supplied', point['notes'])

        self.assertNotIn('address', json.dumps(point).lower())

    # --- scope -----------------------------------------------------------

    def test_dc_is_excluded_as_whole_facility(self):
        data = csv_bytes([
            base(**{'2. TRIFD': 'T1', '4. FACILITY NAME': 'TX site', '36. DOC_CTRL_NUM': 'D1'}),
            base(**{'2. TRIFD': 'T2', '4. FACILITY NAME': 'DC site', '8. ST': 'DC', '36. DOC_CTRL_NUM': 'D2'}),
            base(**{'2. TRIFD': 'T2', '4. FACILITY NAME': 'DC site', '8. ST': 'DC', '36. DOC_CTRL_NUM': 'D3', '49. FORM TYPE': 'A'}),
        ])

        out = self.build(data)

        self.assertEqual([p['id'] for p in out['points']], ['T1'])

        self.assertEqual(out['excluded'], {'outside lower 48': 1})

        self.assertEqual(out['audit']['source chemical-report rows'], 3)

        self.assertEqual(out['audit']['distinct national facilities'], 2)

        self.assertEqual(out['audit']['mapped facilities'], 1)

        self.assertEqual(out['audit']['excluded facilities'], 1)

        self.assertEqual(out['audit']['excluded chemical-report forms'], 2)

        self.assertEqual(out['audit']['mapped chemical-report forms'], 1)

        self.assertEqual(out['exclusionsSummary'], '1 outside lower 48')

    def test_form_a_zero_release_is_kept_and_quantities_never_emitted(self):
        data = csv_bytes([
            base(**{'2. TRIFD': 'T1', '4. FACILITY NAME': 'Alpha', '36. DOC_CTRL_NUM': 'D1',
                    '49. FORM TYPE': 'A', '50. UNIT OF MEASURE': 'Pounds'}),
        ])

        out = self.build(data)

        self.assertEqual(len(out['points']), 1)

        self.assertEqual(out['points'][0]['groups'], [{'type': 'Industry not supplied', 'status': 'Form A certification (2024)'}])

        self.assertEqual(out['audit']['Form A certification rows'], 1)

        text = json.dumps(out['points'])

        self.assertNotIn('Pounds', text)

        self.assertNotIn('Grams', text)

    def test_grams_and_pounds_rows_collapse_into_one_point(self):
        data = csv_bytes([
            base(**{'2. TRIFD': 'T1', '4. FACILITY NAME': 'Alpha', '36. DOC_CTRL_NUM': 'D1',
                    '23. INDUSTRY SECTOR': 'Chemicals', '50. UNIT OF MEASURE': 'Pounds'}),
            base(**{'2. TRIFD': 'T1', '4. FACILITY NAME': 'Alpha', '36. DOC_CTRL_NUM': 'D2',
                    '23. INDUSTRY SECTOR': 'Chemicals', '50. UNIT OF MEASURE': 'Grams'}),
        ])

        out = self.build(data)

        self.assertEqual(len(out['points']), 1)

        self.assertEqual(out['points'][0]['groups'], [{'type': 'Chemicals', 'status': 'Form R report (2024)'}])

        self.assertEqual(out['audit']['mapped chemical-report forms'], 2)

        self.assertNotIn('Grams', json.dumps(out['points']))

    # --- coordinates -----------------------------------------------------

    def test_bad_coordinates_exclude_the_whole_facility(self):
        cases = {'blank': ('', ''), 'nan': ('nan', 'nan'), 'inf': ('inf', '-95.0'),
                 'outofbounds': ('30.0', '10.0')}

        rows = [base(**{'2. TRIFD': 'T9', '4. FACILITY NAME': 'Good site', '36. DOC_CTRL_NUM': 'D9'})]

        for i, (label, (lat, lon)) in enumerate(cases.items()):
            for j in range(2):
                rows.append(base(**{'2. TRIFD': f'T{i}', '4. FACILITY NAME': label,
                                    '12. LATITUDE': lat, '13. LONGITUDE': lon,
                                    '36. DOC_CTRL_NUM': f'D{i}{j}'}))

        out = self.build(csv_bytes(rows))

        self.assertEqual([p['id'] for p in out['points']], ['T9'])

        self.assertEqual(out['excluded'], {'missing/invalid coordinates': 4})

        self.assertEqual(out['audit']['excluded chemical-report forms'], 8)

        self.assertEqual(out['audit']['mapped facilities'], 1)

    def test_conflicting_coordinates_fail_even_before_rounding(self):
        data = csv_bytes([
            base(**{'2. TRIFD': 'T1', '4. FACILITY NAME': 'Alpha', '12. LATITUDE': '30.0000001', '13. LONGITUDE': '-95.0000001', '36. DOC_CTRL_NUM': 'D1'}),
            base(**{'2. TRIFD': 'T1', '4. FACILITY NAME': 'Alpha', '12. LATITUDE': '30.0000002', '13. LONGITUDE': '-95.0000002', '36. DOC_CTRL_NUM': 'D2'}),
        ])

        self.assert_fails(data, 'conflicting coordinates', 'T1')

    def test_conflict_on_out_of_scope_rows_still_fails_closed(self):
        data = csv_bytes([
            base(**{'2. TRIFD': 'T1', '4. FACILITY NAME': 'PR site', '8. ST': 'PR', '12. LATITUDE': '30.0', '13. LONGITUDE': '-95.0', '36. DOC_CTRL_NUM': 'D1'}),
            base(**{'2. TRIFD': 'T1', '4. FACILITY NAME': 'PR site', '8. ST': 'PR', '12. LATITUDE': '31.5', '13. LONGITUDE': '-96.5', '36. DOC_CTRL_NUM': 'D2'}),
        ])

        self.assert_fails(data, 'conflicting coordinates')

    def test_valid_plus_blank_coordinate_refuses_to_choose(self):
        data = csv_bytes([
            base(**{'2. TRIFD': 'T1', '4. FACILITY NAME': 'Alpha', '36. DOC_CTRL_NUM': 'D1'}),
            base(**{'2. TRIFD': 'T1', '4. FACILITY NAME': 'Alpha', '12. LATITUDE': '', '13. LONGITUDE': '', '36. DOC_CTRL_NUM': 'D2'}),
        ])

        self.assert_fails(data, 'T1', 'unusable coordinates')

    def test_valid_plus_invalid_text_coordinate_refuses_to_choose(self):
        data = csv_bytes([
            base(**{'2. TRIFD': 'T1', '4. FACILITY NAME': 'Alpha', '36. DOC_CTRL_NUM': 'D1'}),
            base(**{'2. TRIFD': 'T1', '4. FACILITY NAME': 'Alpha', '12. LATITUDE': 'bad', '13. LONGITUDE': '-95.0', '36. DOC_CTRL_NUM': 'D2'}),
        ])

        self.assert_fails(data, 'T1', 'unusable coordinates')

    def test_mixed_blank_and_nonblank_state_fails_closed(self):
        data = csv_bytes([
            base(**{'2. TRIFD': 'T1', '4. FACILITY NAME': 'Alpha', '8. ST': '', '36. DOC_CTRL_NUM': 'D1'}),
            base(**{'2. TRIFD': 'T1', '4. FACILITY NAME': 'Alpha', '8. ST': 'TX', '36. DOC_CTRL_NUM': 'D2'}),
        ])

        self.assert_fails(data, 'T1', 'conflicting ST')

    def test_conflicting_out_of_scope_finite_coordinates_fail(self):
        data = csv_bytes([
            base(**{'2. TRIFD': 'T1', '4. FACILITY NAME': 'PR site', '8. ST': 'PR', '12. LATITUDE': '18.2', '13. LONGITUDE': '-66.5', '36. DOC_CTRL_NUM': 'D1'}),
            base(**{'2. TRIFD': 'T1', '4. FACILITY NAME': 'PR site', '8. ST': 'PR', '12. LATITUDE': '18.3', '13. LONGITUDE': '-66.6', '36. DOC_CTRL_NUM': 'D2'}),
        ])

        self.assert_fails(data, 'T1', 'conflicting coordinates')

    def test_repeated_out_of_scope_coordinates_exclude_whole_facility(self):
        data = csv_bytes([
            base(**{'2. TRIFD': 'T1', '4. FACILITY NAME': 'TX site', '36. DOC_CTRL_NUM': 'D1'}),
            base(**{'2. TRIFD': 'T2', '4. FACILITY NAME': 'PR site', '8. ST': 'PR', '12. LATITUDE': '18.2', '13. LONGITUDE': '-66.5', '36. DOC_CTRL_NUM': 'D2'}),
            base(**{'2. TRIFD': 'T2', '4. FACILITY NAME': 'PR site', '8. ST': 'PR', '12. LATITUDE': '18.2', '13. LONGITUDE': '-66.5', '36. DOC_CTRL_NUM': 'D3'}),
        ])

        out = self.build(data)

        self.assertEqual([p['id'] for p in out['points']], ['T1'])

        self.assertEqual(out['excluded'], {'outside lower 48': 1})

    # --- identity and consistency failures -------------------------------

    def test_conflicting_name_or_state_fails_closed(self):
        self.assert_fails(csv_bytes([
            base(**{'2. TRIFD': 'T1', '4. FACILITY NAME': 'Alpha', '36. DOC_CTRL_NUM': 'D1'}),
            base(**{'2. TRIFD': 'T1', '4. FACILITY NAME': 'Renamed', '36. DOC_CTRL_NUM': 'D2'}),
        ]), 'conflicting FACILITY NAME')

        self.assert_fails(csv_bytes([
            base(**{'2. TRIFD': 'T1', '4. FACILITY NAME': 'Alpha', '8. ST': 'TX', '36. DOC_CTRL_NUM': 'D1'}),
            base(**{'2. TRIFD': 'T1', '4. FACILITY NAME': 'Alpha', '8. ST': 'OK', '36. DOC_CTRL_NUM': 'D2'}),
        ]), 'conflicting ST')

    def test_missing_identity_fails_the_source(self):
        self.assert_fails(csv_bytes([
            base(**{'2. TRIFD': '', '4. FACILITY NAME': 'Alpha', '36. DOC_CTRL_NUM': 'D1'}),
        ]), 'missing TRIFD')

        self.assert_fails(csv_bytes([
            base(**{'2. TRIFD': 'T1', '4. FACILITY NAME': '  ', '36. DOC_CTRL_NUM': 'D1'}),
        ]), 'missing FACILITY NAME')

    # --- schema, year, form, document control ---------------------------

    def test_wrong_year_fails(self):
        data = csv_bytes([base(**{'1. YEAR': '2023', '2. TRIFD': 'T1', '4. FACILITY NAME': 'Alpha', '36. DOC_CTRL_NUM': 'D1'})])

        self.assert_fails(data, 'does not match requested year')

        good = csv_bytes([base(**{'2. TRIFD': 'T1', '4. FACILITY NAME': 'Alpha', '36. DOC_CTRL_NUM': 'D1'})])

        with self.assertRaises(tri.TriSourceError):
            self.build(good, year=2023)

    def test_missing_or_duplicate_doc_ctrl_num_fails(self):
        self.assert_fails(csv_bytes([
            base(**{'2. TRIFD': 'T1', '4. FACILITY NAME': 'Alpha', '36. DOC_CTRL_NUM': ''}),
        ]), 'missing DOC_CTRL_NUM')

        self.assert_fails(csv_bytes([
            base(**{'2. TRIFD': 'T1', '4. FACILITY NAME': 'Alpha', '36. DOC_CTRL_NUM': 'D1'}),
            base(**{'2. TRIFD': 'T2', '4. FACILITY NAME': 'Beta', '36. DOC_CTRL_NUM': 'D1'}),
        ]), 'duplicate DOC_CTRL_NUM')

    def test_unrecognized_form_fails(self):
        self.assert_fails(csv_bytes([
            base(**{'2. TRIFD': 'T1', '4. FACILITY NAME': 'Alpha', '36. DOC_CTRL_NUM': 'D1', '49. FORM TYPE': 'C'}),
        ]), 'unrecognized FORM TYPE')

    def test_sha_mismatch_and_bad_sha_format_fail(self):
        data = csv_bytes([base(**{'2. TRIFD': 'T1', '4. FACILITY NAME': 'Alpha', '36. DOC_CTRL_NUM': 'D1'})])

        path = self.source(data)

        with self.assertRaises(tri.TriSourceError) as ctx:
            tri.build(path, 2024, '0' * 64, '2026-10-20')

        self.assertIn('does not match', str(ctx.exception))

        with self.assertRaises(tri.TriSourceError) as ctx:
            tri.build(path, 2024, 'abc', '2026-10-20')

        self.assertIn('64 hexadecimal', str(ctx.exception))

    def test_invalid_retrieved_date_fails(self):
        data = csv_bytes([base(**{'2. TRIFD': 'T1', '4. FACILITY NAME': 'Alpha', '36. DOC_CTRL_NUM': 'D1'})])

        self.assert_fails(data, 'retrieved', retrieved='2026-13-45')

        self.assert_fails(data, 'retrieved', retrieved='20 October 2026')

    def test_missing_and_duplicate_header_fail(self):
        columns = [c for c in BASE_COLUMNS if c != '8. ST']

        self.assert_fails(csv_bytes([], columns=columns), 'missing required header column')

        duped = BASE_COLUMNS + ['8. ST']

        self.assert_fails(csv_bytes([], columns=duped), 'duplicate header column')

    def test_truncated_row_and_empty_source_fail(self):
        columns = BASE_COLUMNS

        buf = io.StringIO(newline='')

        writer = csv.writer(buf)

        writer.writerow(columns)

        writer.writerow(['2024', 'T1', 'FRS'])

        self.assert_fails(buf.getvalue().encode('utf-8'), 'truncated')

        self.assert_fails(csv_bytes([]), 'no chemical-report rows')

        self.assert_fails(b'', 'empty')

    def test_unknown_datum_fails_and_known_datum_is_reported(self):
        self.assert_fails(csv_bytes([
            base(**{'2. TRIFD': 'T1', '4. FACILITY NAME': 'Alpha', '36. DOC_CTRL_NUM': 'D1', '14. HORIZONTAL DATUM': 'NAD27'}),
        ]), 'unrecognized HORIZONTAL DATUM')

    def test_mutually_conflicting_datums_fail_closed(self):
        data = csv_bytes([
            base(**{'2. TRIFD': 'T1', '4. FACILITY NAME': 'Alpha', '36. DOC_CTRL_NUM': 'D1', '14. HORIZONTAL DATUM': 'WGS84'}),
            base(**{'2. TRIFD': 'T1', '4. FACILITY NAME': 'Alpha', '36. DOC_CTRL_NUM': 'D2', '14. HORIZONTAL DATUM': 'NAD83'}),
        ])

        self.assert_fails(data, 'T1', 'conflicting HORIZONTAL DATUM')

    def test_blank_and_known_datum_mixture_fails_closed(self):
        data = csv_bytes([
            base(**{'2. TRIFD': 'T1', '4. FACILITY NAME': 'Alpha', '36. DOC_CTRL_NUM': 'D1', '14. HORIZONTAL DATUM': ''}),
            base(**{'2. TRIFD': 'T1', '4. FACILITY NAME': 'Alpha', '36. DOC_CTRL_NUM': 'D2', '14. HORIZONTAL DATUM': 'WGS 84'}),
        ])

        self.assert_fails(data, 'T1', 'blank and supplied HORIZONTAL DATUM')

    def test_equivalent_datum_spellings_are_not_conflicting(self):
        data = csv_bytes([
            base(**{'2. TRIFD': 'T1', '4. FACILITY NAME': 'Alpha', '36. DOC_CTRL_NUM': 'D1', '14. HORIZONTAL DATUM': 'WGS84'}),
            base(**{'2. TRIFD': 'T1', '4. FACILITY NAME': 'Alpha', '36. DOC_CTRL_NUM': 'D2', '14. HORIZONTAL DATUM': 'WGS 84'}),
        ])

        point = self.build(data)['points'][0]

        self.assertIn('horizontal datum WGS 84 as supplied', point['notes'])

    def test_unterminated_quoted_field_fails_as_source_error(self):
        data = csv_bytes([base(**{'2. TRIFD': 'T1', '36. DOC_CTRL_NUM': 'D1'})]) + b'"'

        self.assert_fails(data, 'malformed CSV')

    def test_malformed_csv_cli_preserves_previous_output(self):
        data = csv_bytes([base(**{'2. TRIFD': 'T1', '36. DOC_CTRL_NUM': 'D1'})]) + b'"'

        path = self.source(data)

        digest = hashlib.sha256(data).hexdigest()

        out = self.dir / 'tri.json'

        out.write_bytes(b'prior-output')

        result = self.cli('--source', str(path), '--year', '2024', '--retrieved', '2026-10-20',
                          '--sha256', digest, '--output', str(out))

        self.assertEqual(result.returncode, 1, result.stderr)

        self.assertIn('malformed CSV', result.stderr)

        self.assertEqual(out.read_bytes(), b'prior-output')

    def test_known_datum_success_regression(self):
        out = self.build(csv_bytes([
            base(**{'2. TRIFD': 'T1', '4. FACILITY NAME': 'Alpha', '36. DOC_CTRL_NUM': 'D1', '14. HORIZONTAL DATUM': 'WGS 84'}),
        ]))

        self.assertIn('horizontal datum WGS 84 as supplied', out['points'][0]['notes'])

    # --- output contract -------------------------------------------------

    def test_audit_reconciles_and_output_is_deterministic(self):
        rows = [
            base(**{'2. TRIFD': 'T1', '4. FACILITY NAME': 'Alpha', '23. INDUSTRY SECTOR': 'Chemicals', '36. DOC_CTRL_NUM': 'D1'}),
            base(**{'2. TRIFD': 'T1', '4. FACILITY NAME': 'Alpha', '23. INDUSTRY SECTOR': 'Chemicals', '36. DOC_CTRL_NUM': 'D2', '49. FORM TYPE': 'A'}),
            base(**{'2. TRIFD': 'T2', '4. FACILITY NAME': 'Beta', '8. ST': 'PR', '12. LATITUDE': '18.2', '13. LONGITUDE': '-66.5', '36. DOC_CTRL_NUM': 'D3'}),
            base(**{'2. TRIFD': 'T3', '4. FACILITY NAME': 'Gamma', '12. LATITUDE': '', '13. LONGITUDE': '', '36. DOC_CTRL_NUM': 'D4'}),
        ]

        data = csv_bytes(rows)

        out = self.build(data)

        audit = out['audit']

        self.assertEqual(audit['source chemical-report rows'], 4)

        self.assertEqual(audit['mapped facilities'] + audit['excluded facilities'], audit['distinct national facilities'])

        self.assertEqual(audit['mapped chemical-report forms'] + audit['excluded chemical-report forms'], audit['source chemical-report rows'])

        self.assertEqual(audit['Form R report rows'] + audit['Form A certification rows'], audit['source chemical-report rows'])

        self.assertEqual(len(out['points']), 1)

        self.assertEqual(out['sourceFiles'][0]['sha256'], hashlib.sha256(data).hexdigest())

        self.assertEqual(out['retrieved'], '2026-10-20')

        self.assertEqual(out['schemaVersion'], 1)

        self.assertEqual(json.dumps(out, sort_keys=True), json.dumps(self.build(data), sort_keys=True))

    def test_point_ids_are_unique_and_nonempty(self):
        rows = [base(**{'2. TRIFD': f'T{i}', '4. FACILITY NAME': f'Site {i}', '36. DOC_CTRL_NUM': f'D{i}'}) for i in range(5)]

        out = self.build(csv_bytes(rows))

        ids = [p['id'] for p in out['points']]

        self.assertTrue(ids)

        self.assertEqual(len(set(ids)), len(ids))

        self.assertEqual(ids, sorted(ids))

    # --- CLI -------------------------------------------------------------

    def cli(self, *args):
        return subprocess.run([sys.executable, str(HERE / 'prepare-tri.py'), *args],
                              capture_output=True, text=True)

    def test_cli_writes_atomically_and_preserves_output_on_failure(self):
        data = csv_bytes([
            base(**{'2. TRIFD': 'T1', '4. FACILITY NAME': 'Alpha', '36. DOC_CTRL_NUM': 'D1'}),
            base(**{'2. TRIFD': 'T1', '4. FACILITY NAME': 'Alpha', '36. DOC_CTRL_NUM': 'D2', '49. FORM TYPE': 'A'}),
        ])

        path = self.source(data)

        digest = hashlib.sha256(data).hexdigest()

        out = self.dir / 'tri.json'

        result = self.cli('--source', str(path), '--year', '2024', '--retrieved', '2026-10-20',
                          '--sha256', digest, '--output', str(out))

        self.assertEqual(result.returncode, 0, result.stderr)

        written = json.loads(out.read_text(encoding='utf-8'))

        self.assertEqual(written, self.build(data))

        self.assertEqual(written['points'][0]['groups'], [
            {'type': 'Industry not supplied', 'status': 'Form A certification (2024)'},
            {'type': 'Industry not supplied', 'status': 'Form R report (2024)'},
        ])

        before = out.read_bytes()

        failed = self.cli('--source', str(path), '--year', '2024', '--retrieved', '2026-10-20',
                          '--sha256', '0' * 64, '--output', str(out))

        self.assertEqual(failed.returncode, 1)

        self.assertIn('does not match', failed.stderr)

        self.assertEqual(out.read_bytes(), before)

        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ['tri.csv', 'tri.json'])

    def test_cli_help_is_concise(self):
        result = self.cli('--help')

        self.assertEqual(result.returncode, 0)

        self.assertIn('--sha256', result.stdout)

        self.assertLess(len(result.stdout.splitlines()), 25)


if __name__ == '__main__':
    unittest.main(verbosity=2)
