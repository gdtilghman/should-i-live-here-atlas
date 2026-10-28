"""Build local-review FEMA declaration counts. No inference from sample rows."""
import csv, json, hashlib
from collections import Counter, defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
path=ROOT/'work/fema-all.csv'
raw=list(csv.DictReader(path.open(encoding='utf-8-sig',newline='')))
filtered=[r for r in raw if r['declarationType']=='DR' and '2000-01-01'<=r['declarationDate']<'2026-01-01']
reference=json.loads((ROOT/'work/fema-page-0.json').read_text())['metadata']['count']
assert len(filtered)==reference, (len(filtered),reference)
assert len({r['id'] for r in raw})==len(raw)
allow={'Drought','Earthquake','Fire','Flood','Hurricane','Mud/Landslide','Severe Ice Storm','Severe Storm','Snowstorm','Tornado','Tropical Storm','Tsunami','Volcanic Eruption','Winter Storm','Coastal Storm','Freezing','Typhoon','Tropical Depression','Straight-Line Winds'}
exclude={'Biological','Chemical','Terrorist','Human Cause','Toxic Substances','Other','Dam/Levee Break'}
unknown=set(r['incidentType'] for r in filtered)-allow-exclude
assert not unknown,unknown
geo=json.loads((ROOT/'dist/data/counties.geojson').read_text())
fips={f['properties']['fips'] for f in geo['features']}
# Conservative unavailable values until historical boundary audit is completed.
uncertain={f for f in fips if f.startswith('09')}|{'08014','51019','46102'}
events=defaultdict(set); hazard_events=defaultdict(lambda: defaultdict(set)); unmatched=Counter(); excluded=Counter(); lineage=defaultdict(list)
for r in filtered:
    code=r['fipsStateCode'].zfill(2)+r['fipsCountyCode'].zfill(3)
    if r['incidentType'] not in allow:
        excluded[r['incidentType']]+=1; continue
    if code not in fips or r['tribalRequest'] in {'1','true','True'}:
        unmatched[code]+=1; continue
    if code in uncertain: continue
    events[code].add(r['disasterNumber'])
    hazard_events[r['incidentType']][code].add(r['disasterNumber'])
    lineage[code].append({'number':r['disasterNumber'],'type':r['incidentType'],'date':r['declarationDate'],'id':r['id']})
records={f:{'value':None if f in uncertain else len(events[f]),'low':None,'high':None,'count':None,'status':'unavailable' if f in uncertain else 'available'} for f in sorted(fips)}
for f in uncertain: records[f]['reason']='Historical boundary coverage needs review for the full 2000–2025 period.'
vals=[r['value'] for r in records.values() if r['value'] is not None]
note="This product uses the Federal Emergency Management Agency’s OpenFEMA API, but is not endorsed by FEMA. The Federal Government or FEMA cannot vouch for the data or analyses derived from these data after the data have been retrieved from the Agency's website(s). Federal Emergency Management Agency (FEMA), OpenFEMA Dataset: Disaster Declarations Summaries - v2. Retrieved from https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries on September 14, 2026. The values count federal major-disaster declarations. They do not count every disaster. They do not measure future risk. Biological events and unclear categories are not counted. Some historical county boundaries still need review."
datasets=[{'id':'declarations','title':'Major natural-disaster declarations','hazardType':'All included natural hazards','unit':'declarations','period':'2000–2025','sex':'All residents','min':min(vals),'max':max(vals),'note':note,'records':records}]
for hazard, county_events in sorted(hazard_events.items()):
    hazard_records={f:{**record,'value':None if f in uncertain else len(county_events.get(f, set()))} for f,record in records.items()}
    hazard_values=[r['value'] for r in hazard_records.values() if r['value'] is not None]
    datasets.append({'id':'hazard-' + hazard.lower().replace('/','-').replace(' ','-'),'title':hazard + ' declarations','hazardType':hazard,'unit':'declarations','period':'2000–2025','sex':'All residents','min':min(hazard_values),'max':max(hazard_values),'note':note,'records':hazard_records})
assert all(sum(1 for r in d['records'].values() if r['status']=='unavailable')==11 for d in datasets)
assert all(d['records'][f]['value'] <= records[f]['value'] for d in datasets for f in records if records[f]['value'] is not None)
payload={'sourceUrl':'https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries','note':note,'datasets':datasets}
(ROOT/'dist/data/disasters.json').write_text(json.dumps(payload,separators=(',',':')),encoding='utf-8')
report={'rawRows':len(raw),'windowRows':len(filtered),'apiMatchingWindowCount':reference,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'incidentInventory':dict(Counter(r['incidentType'] for r in filtered)),'allowedIncidentTypes':sorted(allow),'excludedIncidentRows':dict(excluded),'notJoinedRows':dict(unmatched),'unavailableCounties':sorted(uncertain),'availableCounties':len(vals),'min':min(vals),'max':max(vals),'lineage':dict(lineage)}
(ROOT/'work/disaster-validation.json').write_text(json.dumps(report,indent=2))
assert len(records)==3107 and all(isinstance(v,int) and v>=0 for v in vals)
assert records['12047']['value']>=1 and any(r['number']=='4834' for r in lineage['12047'])
print(json.dumps({k:report[k] for k in ['rawRows','windowRows','apiMatchingWindowCount','availableCounties','unavailableCounties','min','max']}))
