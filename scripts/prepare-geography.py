"""Add display metadata and validate 2021 Census geography after mapshaper conversion."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATES = dict(pair.split(':') for pair in ('01:Alabama|04:Arizona|05:Arkansas|06:California|08:Colorado|09:Connecticut|10:Delaware|12:Florida|13:Georgia|16:Idaho|17:Illinois|18:Indiana|19:Iowa|20:Kansas|21:Kentucky|22:Louisiana|23:Maine|24:Maryland|25:Massachusetts|26:Michigan|27:Minnesota|28:Mississippi|29:Missouri|30:Montana|31:Nebraska|32:Nevada|33:New Hampshire|34:New Jersey|35:New Mexico|36:New York|37:North Carolina|38:North Dakota|39:Ohio|40:Oklahoma|41:Oregon|42:Pennsylvania|44:Rhode Island|45:South Carolina|46:South Dakota|47:Tennessee|48:Texas|49:Utah|50:Vermont|51:Virginia|53:Washington|54:West Virginia|55:Wisconsin|56:Wyoming').split('|'))
path = ROOT/'dist/data/counties.geojson'
data = json.loads(path.read_text())
for feature in data['features']:
    props = feature['properties']
    props['stateName'] = STATES[props['state']]
assert len(data['features']) == 3107
assert len({f['properties']['fips'] for f in data['features']}) == 3107
assert len({f['properties']['state'] for f in data['features']}) == 48
assert len([f for f in data['features'] if f['properties']['state']=='09']) == 8
data['source'] = 'US Census Bureau, 2021 TIGER/Line county boundaries; simplified for display.'
data['sourceUrl'] = 'https://www2.census.gov/geo/tiger/TIGER2021/COUNTY/tl_2021_us_county.zip'
path.write_text(json.dumps(data,separators=(',',':')),encoding='utf-8')
print('Geography: 3107 unique counties, 48 states, 8 legacy Connecticut counties verified.')
