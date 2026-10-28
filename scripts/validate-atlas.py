"""Validate county data contracts used by single and combined maps."""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
geo = json.loads((ROOT / 'dist/data/counties.geojson').read_text(encoding='utf-8'))
ids = [f['properties']['fips'] for f in geo['features']]
assert len(ids) == len(set(ids)) == 3107
report = {}
for family in ('cancer', 'disasters', 'community', 'hazards', 'healthcare', 'employment', 'broadband', 'places', 'air', 'wildfire', 'water', 'traffic', 'climate', 'storms', 'crime'):
    file = ROOT / f'dist/data/{family}.json'
    if not file.exists():
        report[family] = {'present': False}
        continue
    collection = json.loads(file.read_text(encoding='utf-8'))
    names = [d['id'] for d in collection['datasets']]
    assert len(names) == len(set(names)), (family, 'duplicate dataset id')
    layers = []
    for dataset in collection['datasets']:
        assert set(dataset['records']) == set(ids), (family, dataset['id'], 'county universe')
        assert dataset['title'] and dataset['unit'] and dataset['period']
        available = 0
        for fips, record in dataset['records'].items():
            value = record['value']
            if record['status'] == 'available':
                assert isinstance(value, (int,float)) and not isinstance(value,bool) and math.isfinite(value), (family,fips,'nonfinite')
                assert value >= 0, (family,fips,'negative source value')
                if family == 'employment':
                    assert value <= 100, (family,fips,'rate outside 0-100')
                available += 1
            else:
                assert value is None, (family,fips,'unavailable must be null')
            low, high = record.get('low'), record.get('high')
            assert (low is None) == (high is None), (family,fips,'partial interval')
            if low is not None:
                assert math.isfinite(low) and math.isfinite(high) and low <= value <= high, (family,fips,'interval')
            if family == 'employment':
                for key in ('laborForce','employed','unemployed'):
                    count = record.get(key)
                    # Published counts remain useful even when the rate is unavailable.
                    assert count is None or (isinstance(count,int) and not isinstance(count,bool) and count >= 0), (family,fips,key)
            if family == 'broadband':
                source_access = record.get('sourceAccessPercent')
                # The reported percentage is independent context: it may be
                # absent even when the derived rate itself is unavailable.
                assert source_access is None or (isinstance(source_access,(int,float)) and not isinstance(source_access,bool) and math.isfinite(source_access) and 0 <= source_access <= 100), (family,fips,'sourceAccessPercent')
                if record['status'] == 'available' and source_access is not None:
                    assert abs(record['value'] + source_access - 100) <= 1e-9, (family,fips,'derived gap parity')
            if record.get('moe') is not None:
                assert math.isfinite(record['moe']) and record['moe'] >= 0
        if family in ('community','hazards','healthcare','climate','places','storms','crime'):
            assert dataset.get('sourceUrl','').startswith('https://')
            assert dataset.get('direction') in ('higher-worse','higher-better')
        if family == 'employment':
            assert dataset.get('sourceUrl','').startswith('https://'), (family, dataset['id'], 'sourceUrl')
            assert dataset.get('direction') == 'higher-worse', (family, dataset['id'], 'direction')
        if family == 'broadband':
            assert dataset['id'] == 'without-100-20', (family, dataset['id'], 'dataset id')
            assert dataset.get('sourceUrl','').startswith('https://'), (family, dataset['id'], 'sourceUrl')
            assert dataset.get('direction') == 'higher-worse', (family, dataset['id'], 'direction')
        if family == 'places':
            assert dataset.get('sourceUrl','').startswith('https://'), (family, dataset['id'], 'sourceUrl')
            assert dataset.get('direction') == 'higher-worse', (family, dataset['id'], 'direction')
            assert set(names) == {'asthma', 'diabetes', 'mental-distress', 'obesity', 'smoking', 'physical-inactivity', 'binge-drinking', 'short-sleep', 'copd', 'heart-disease', 'stroke', 'depression', 'poor-health', 'physical-distress', 'uninsured'}, (family, 'dataset ids')
            for fips, record in dataset['records'].items():
                if record['status'] == 'available':
                    assert all(math.isfinite(v) for v in [record.get('crude'), record.get('crudeLow'), record.get('crudeHigh')]), (family,fips,'crude interval')
                    assert record.get('crudeLow') <= record.get('crude') <= record.get('crudeHigh'), (family,fips,'crude bounds')
        if family == 'air':
            assert dataset.get('sourceUrl','').startswith('https://'), (family, dataset['id'], 'sourceUrl')
            assert dataset.get('direction') == 'higher-worse', (family, dataset['id'], 'direction')
            assert dataset['id'] == 'pm25-2020-2022', (family, 'dataset id')
            for fips, record in dataset['records'].items():
                if record['status'] == 'available':
                    annual = record.get('annual', {})
                    assert isinstance(annual, dict) and set(annual.keys()) == {'2020', '2021', '2022'}, (family, fips, 'annual keys')
                    assert all(isinstance(annual[y], (int, float)) and math.isfinite(annual[y]) and annual[y] >= 0 for y in ['2020', '2021', '2022']), (family, fips, 'annual values')
        if family == 'wildfire':
            assert dataset.get('sourceUrl', '').startswith('https://'), (family, dataset['id'], 'sourceUrl')
            assert dataset.get('direction') == 'higher-worse', (family, dataset['id'], 'direction')
            assert dataset['id'] in ['risk-to-homes', 'likelihood'], (family, 'dataset id')
            for fips, record in dataset['records'].items():
                if record['status'] == 'available':
                    v = record['value']
                    assert math.isfinite(v) and 0 <= v <= 100, (family, fips, 'wildfire value')
        if family == 'water':
            assert dataset.get('sourceUrl', '').startswith('https://'), (family, dataset['id'], 'sourceUrl')
            assert dataset.get('direction') == 'higher-worse', (family, dataset['id'], 'direction')
            assert dataset['id'] == 'health-violations-2023-2025', (family, 'dataset id')
            for fips, record in dataset['records'].items():
                if record['status'] == 'available':
                    v = record['value']
                    assert math.isfinite(v) and 0 <= v <= 100, (family, fips, 'water value')
                    assert record.get('populationServed') is not None and record.get('populationServed') > 0, (family, fips, 'populationServed')
        if family == 'traffic':
            assert dataset.get('sourceUrl', '').startswith('https://'), (family, dataset['id'], 'sourceUrl')
            assert dataset.get('direction') == 'higher-worse', (family, dataset['id'], 'direction')
            assert dataset['id'] == 'deaths-2019-2023', (family, 'dataset id')
            for fips, record in dataset['records'].items():
                if record['status'] == 'available':
                    assert isinstance(record.get('deaths'), int) and record.get('deaths') >= 0, (family, fips, 'deaths')
                    assert isinstance(record.get('population'), int) and record.get('population') > 0, (family, fips, 'population')
        layers.append({'id':dataset['id'],'available':available,'unavailable':len(ids)-available})
    report[family] = layers
print(json.dumps(report,indent=2))
