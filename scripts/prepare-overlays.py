"""Build static place catalogs from explicitly acquired official snapshots.



No runtime API calls. Raw files stay in ignored work/overlay-sources. Standard

library only; EIA XLSX uses its public OOXML tables, not installed Excel.

"""

import argparse, collections, csv, hashlib, io, json, math, re, zipfile

from datetime import datetime, timezone

from pathlib import Path

import xml.etree.ElementTree as ET



ROOT = Path(__file__).resolve().parents[1]

NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

STATE_CODES = 'AL AZ AR CA CO CT DE FL GA ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY'.split()

STATE_FIPS = '01 04 05 06 08 09 10 12 13 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40 41 42 44 45 46 47 48 49 50 51 53 54 55 56'.split()

STATES = dict(zip(STATE_CODES, STATE_FIPS))



def coords(lon, lat):

    try:

        x, y = float(lon), float(lat)

    except (TypeError, ValueError):

        return None

    # Coarse validation only; do not invent county-center locations. Source

    # state determines map scope; offshore coastal facilities remain possible.

    if not (math.isfinite(x) and math.isfinite(y) and -125 <= x <= -66 and 24 <= y <= 50):

        return None

    return round(x, 6), round(y, 6)



def sheet_rows(path, sheet):

    with zipfile.ZipFile(path) as z:

        strings = [''.join(e.itertext()) for e in ET.fromstring(z.read('xl/sharedStrings.xml'))]

        root = ET.fromstring(z.read(f'xl/worksheets/sheet{sheet}.xml'))

        headers = None

        for row in root.findall('m:sheetData/m:row', NS):

            values = {}

            for c in row:

                v = c.find('m:v', NS)

                value = v.text if v is not None else ''

                if c.get('t') == 's':

                    value = strings[int(value)]

                values[re.sub(r'\d+', '', c.get('r'))] = str(value).strip()

            if row.get('r') == '3':

                headers = values

            elif headers:

                yield {name: values.get(col, '') for col, name in headers.items()}



def power(path):

    plants, excluded, audit = {}, collections.Counter(), collections.Counter()

    for sheet, kind in [(1, 'Operating inventory'), (2, 'Planned inventory'), (3, 'Retired inventory'), (4, 'Canceled/postponed inventory')]:

        for row in sheet_rows(path, sheet):

            audit[kind] += 1

            if row.get('Plant State') not in STATES:

                excluded['outside lower 48'] += 1; continue

            xy = coords(row.get('Longitude'), row.get('Latitude'))

            if xy is None:

                excluded['missing/invalid coordinates'] += 1; continue

            pid = row['Plant ID']; name = row['Plant Name']

            if not pid or not name: excluded['missing identity'] += 1; continue

            status = row.get('Status') or ('Retired (RE)' if sheet == 3 else kind)

            if status.startswith('(OP)'): status = 'Operating (OP)'

            tech = row.get('Technology') or 'Technology unspecified'

            plant = plants.setdefault(pid, {'id': pid, 'name': name, 'state': STATES[row['Plant State']], 'longitude': xy[0], 'latitude': xy[1], 'groups': []})

            if [plant['longitude'],plant['latitude']] != list(xy): audit['conflicting coordinate rows (first inventory coordinate retained)'] += 1

            group = {'type': tech, 'status': status, 'fuelCode': row.get('Energy Source Code','')}

            if group not in plant['groups']: plant['groups'].append(group)

    return sorted(plants.values(),key=lambda p:int(p['id'])),dict(excluded),dict(audit)



def health(path):

    points, excluded, seen = [], collections.Counter(), set()

    with path.open(encoding='utf-8-sig',newline='') as f:

        for row in csv.DictReader(f):

            if row['Site State Abbreviation'] not in STATES: excluded['outside lower 48'] += 1; continue

            if row['Health Center Type Description'] == 'Administrative': excluded['administrative-only'] += 1; continue

            if row['Health Center Location Type Description'] == 'Mobile Van': excluded['mobile base is not service location'] += 1; continue

            xy=coords(row['Geocoding Artifact Address Primary X Coordinate'],row['Geocoding Artifact Address Primary Y Coordinate'])

            if xy is None: excluded['missing/invalid coordinates'] += 1; continue

            pid=row['BPHC Assigned Number']

            if pid in seen: raise ValueError(f'Duplicate HRSA id {pid}')

            seen.add(pid)

            points.append({'id':pid,'name':row['Site Name'],'state':STATES[row['Site State Abbreviation']], 'longitude':xy[0],'latitude':xy[1],

                'groups':[{'type':row['Health Center Location Type Description']+' health-center site','status':row['Site Status Description']}],

                'date':row['Data Warehouse Record Create Date'],

                'notes':'Service setting: '+row['Health Center Service Delivery Site Location Setting Description']+'. Schedule: '+row['Health Center Operational Schedule Description']+'. Not a directory of all hospitals or physicians.'})

    return points,dict(excluded),{}



def epa(paths):

    points, excluded, counts = {}, collections.Counter(), {}

    names={3:'Major air-program facility',12:'Major NPDES discharger',22:'Superfund NPL program listing',23:'Toxics Release Inventory facility'}

    for layer,path in paths:

        data=json.loads(path.read_text());rows=data['features'];assert len(rows)==data['count'];counts[names[layer]]=len(rows)

        for row in rows:

            a=row['attributes'];geo=row.get('geometry') or {}

            if a.get('STATE_CODE') not in STATES: excluded['outside lower 48']+=1;continue

            xy=coords(geo.get('x'),geo.get('y'))

            if not xy: excluded['missing/invalid coordinates']+=1;continue

            pid=str(a['REGISTRY_ID']);p=points.setdefault(pid,{'id':pid,'name':a['PRIMARY_NAME'],'state':STATES[a['STATE_CODE']], 'longitude':xy[0],'latitude':xy[1],'groups':[]})

            group={'type':names[layer],'status':str(a.get('ACTIVE_STATUS') or 'Source status unspecified')}

            timestamp=a.get('LAST_REPORTED_DATE')
            if isinstance(timestamp,(int,float)):
                group['date']=datetime.fromtimestamp(timestamp/1000,timezone.utc).date().isoformat()
            if group not in p['groups']:p['groups'].append(group)

    return list(points.values()),dict(excluded),counts






def hospitals(paths):
    points,excluded,audit={},collections.Counter(),{}
    for layer,path in paths:
        data=json.loads(path.read_text());rows=data['features'];assert len(rows)==data['count'];audit['source layer '+str(layer)]=len(rows)
        for row in rows:
            a=row['attributes'];geo=row.get('geometry') or {};state=a.get('CMS_PROVIDER_STATE_ABBR')
            if state not in STATES:excluded['outside lower 48 rows']+=1;continue
            subtype=a.get('CMS_PROVIDER_CAT_SUB_TYP_DESC') or 'Subtype not supplied'
            if subtype=='Religious Nonmedical Health Care Institutions':excluded['nonmedical institutions']+=1;continue
            xy=coords(geo.get('x'),geo.get('y'))
            if not xy:excluded['missing/invalid coordinate rows']+=1;continue
            pid=a['CMS_PROVIDER_NUM'];point=points.setdefault(pid,{'id':pid,'name':a['FACILITY_NM'],'state':STATES[state],'longitude':xy[0],'latitude':xy[1],'groups':[],
                'notes':'CMS Provider of Services directory, distributed by HRSA. Not a real-time operating or emergency-capacity report; verify services with the facility.'})
            group={'type':subtype,'status':'CMS directory listing; operating status not supplied'}
            if group not in point['groups']:point['groups'].append(group)
            else:audit['duplicate provider rows collapsed']=audit.get('duplicate provider rows collapsed',0)+1
    return list(points.values()),dict(excluded),audit

def crashes(path):

    expected='edde841eb493e55751961b36bac2d1ce8750f601cb8e6e183a525723bb62bab0'

    if hashlib.sha256(path.read_bytes()).hexdigest()!=expected: raise ValueError('FARS snapshot differs from existing traffic-source audit')

    points,excluded=[],collections.Counter()

    with zipfile.ZipFile(path) as z:

        name=next(n for n in z.namelist() if n.lower().endswith('accident.csv'))

        for row in csv.DictReader(io.TextIOWrapper(z.open(name),encoding='utf-8-sig')):

            state=row['STATE'].zfill(2)

            if state not in STATE_FIPS: excluded['outside lower 48']+=1;continue

            xy=coords(row['LONGITUD'],row['LATITUDE'])

            if not xy: excluded['missing/invalid coordinates']+=1;continue

            date=f"2023-{int(row['MONTH']):02d}-{int(row['DAY']):02d}"

            points.append({'id':row['ST_CASE'],'name':'Fatal crash '+row['ST_CASE']+' ('+date+')','state':state,'longitude':xy[0],'latitude':xy[1],

                'groups':[{'type':'Fatal road crash','status':'2023 final file'}],'date':date,'notes':row['FATALS']+' fatalities reported. Crash location, not residence. No names or individual records are included.'})

    return points,dict(excluded),{}



def quakes(path,states_path):

    data=json.loads(path.read_text());states=json.loads(states_path.read_text());points=[];excluded=collections.Counter()

    for feature in data['features']:

        prop=feature['properties'];pid=feature['id'];xy=coords(*feature['geometry']['coordinates'][:2])

        if pid not in states: excluded['outside mapped lower-48 county geometry (including offshore)']+=1;continue

        if not xy: excluded['missing/invalid coordinates']+=1;continue

        if prop['type']!='earthquake': excluded['non-earthquake event']+=1;continue

        date=datetime.fromtimestamp(prop['time']/1000,timezone.utc).isoformat()

        if not date.startswith('2025-'): excluded['outside 2025 UTC']+=1;continue

        points.append({'id':pid,'name':prop['title'],'state':states[pid],'longitude':xy[0],'latitude':xy[1],

            'groups':[{'type':'Earthquake M3+','status':prop['status']}],'date':date,'notes':'Magnitude '+str(prop['mag'])+' ('+str(prop['magType'])+'). Epicenter, not a shaking or damage footprint. Catalog values may be revised.'})

    return points,dict(excluded),{'source bounding-box events':len(data['features'])}



def main():

    parser=argparse.ArgumentParser();parser.add_argument('--source-dir',default='work/overlay-sources');parser.add_argument('--retrieved',required=True,help='Actual UTC acquisition date, YYYY-MM-DD');args=parser.parse_args()

    source=ROOT/args.source_dir;out=ROOT/'dist/data/overlays';out.mkdir(parents=True,exist_ok=True)

    catalog={'schemaVersion':1,'retrieved':args.retrieved,'overlays':[]}

    def emit(spec,paths,builder):

        points,excluded,audit=builder()

        assert points and len({p['id'] for p in points})==len(points)

        record={'schemaVersion':1,'points':points,'excluded':excluded,'audit':audit,'exclusionsSummary':'; '.join(f'{n:,} {reason}' for reason,n in excluded.items()),

            'sourceFiles':[{'file':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths], 'retrieved':args.retrieved}

        (out/spec['file']).write_text(json.dumps(record,ensure_ascii=False,separators=(',',':')),encoding='utf-8')

        spec['count']=len(points);spec['retrieved']=args.retrieved;catalog['overlays'].append(spec)

        print(spec['id'],len(points),'excluded',excluded,'audit',audit)

    p=source/'august_generator2026.xlsx'

    emit({'id':'power','label':'Power plants & storage','file':'power.json','color':'#f6ca72','source':'US EIA-860M','sourceUrl':'https://www.eia.gov/electricity/data/eia860m/','period':'Preliminary August 2026 inventory; released September 24, 2026','defaultStatus':'Operating (OP)',

        'relatedFamilies':['cancer','air','water','hazards','climate'],

        'caveat':'EIA-tracked grid-connected facilities, generally at least 1 MW; not every rooftop system. One representative point per plant; mixed technologies/statuses retained. Type and status filters match the same generator record. Storage is not a fuel. A location is not an exposure, emission or historical operating record.'},[p],lambda:power(p))

    p=source/'hrsa-health-centers.csv'

    emit({'id':'health','label':'Health-center service sites','file':'health.json','color':'#80d9bc','source':'HRSA health-center sites','sourceUrl':'https://data.hrsa.gov/topics/health-centers','period':'Directory snapshot '+args.retrieved,

        'relatedFamilies':['healthcare','places','cancer','community'],

        'caveat':'Permanent and seasonal health-center service sites; excludes administrative-only and mobile-van base addresses. Not all clinics, hospitals or physicians. Listed service sites do not establish appointment availability, quality or individual access.'},[p],lambda:health(p))

    p=source/'FARS2023NationalCSV.zip'

    if p.exists():

        emit({'id':'crashes','label':'Fatal road crashes (2023)','file':'crashes.json','color':'#ff9b85','source':'NHTSA FARS final file','sourceUrl':'https://www.nhtsa.gov/research-data/fatality-analysis-reporting-system-fars','period':'2023 events; final file',

            'relatedFamilies':['traffic','community'],

            'caveat':'Fatal crash locations, not all crashes or a forecast. No victim identities. This one-year point layer differs from the 2019–2023 county traffic rate. Counts are not adjusted for traffic volume or population.'},[p],lambda:crashes(p))

    p=source/'usgs-quakes-2025.json';state_path=source/'usgs-quake-states.json'

    if p.exists() and state_path.exists():

        emit({'id':'quakes','label':'Earthquakes M3+ (2025)','file':'quakes.json','color':'#d7abef','source':'USGS earthquake catalog','sourceUrl':'https://earthquake.usgs.gov/fdsnws/event/1/','period':'2025 UTC events; retrieved '+args.retrieved,

            'relatedFamilies':['disasters','hazards'],

            'caveat':'Epicenters within mapped lower-48 counties, magnitude at least 3. Not a complete history, damage footprint or future hazard estimate. Offshore events excluded; catalog locations and magnitudes can be revised.'},[p,state_path],lambda:quakes(p,state_path))

    hospital_paths=[(layer,source/f'hrsa-hospitals-{layer}.json') for layer in [0,1]]
    if all(p.exists() for _,p in hospital_paths):
        emit({'id':'hospitals','label':'Hospitals & critical-access hospitals','file':'hospitals.json','color':'#57cbdc','source':'CMS Provider of Services via HRSA','sourceUrl':'https://data.hrsa.gov/data/data-sources','period':'Directory snapshot '+args.retrieved,
            'relatedFamilies':['healthcare','places','cancer','community'],
            'caveat':'CMS-listed hospital facilities, including critical-access and specialty types; one point per CMS provider number. Not all care providers. Directory membership is not a live operating status, quality rating, capacity or travel-time estimate. Verify services with the facility.'},[p for _,p in hospital_paths],lambda:hospitals(hospital_paths))
    paths=[(layer,source/f'epa-{layer}.json') for layer in [3,12,22,23] if (source/f'epa-{layer}.json').exists()]

    if paths:

        emit({'id':'epa','label':'EPA air, water & Superfund facilities','file':'epa.json','color':'#90bdf5','source':'EPA Facility Registry Service','sourceUrl':'https://www.epa.gov/frs/geospatial-data-download-service','period':'Registry snapshot '+args.retrieved,

            'relatedFamilies':['air','water','cancer','hazards','disasters'],

            'caveat':'Facility program listings, not measured exposure or proof of violations. NPDES dischargers include industrial facilities and are not drinking-water service areas. One point per registry ID across included programs. Status is the source program status, not a claim that a facility is operating. Included categories are shown in the type filter.'},[p for _,p in paths],lambda:epa(paths))

    (out/'catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')



if __name__=='__main__':main()
