"""Read-only official EPA/HRSA acquisition; complete ID sets or no output shard.

Explicit --fetch permits public network reads. No keys, accounts or geocoding.
Raw snapshots and request evidence remain under ignored work/overlay-sources.
"""
import argparse
import http.cookiejar
import json
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fetch', action='store_true', required=True)
    parser.add_argument('--source-dir', default='work/overlay-sources')
    args = parser.parse_args()
    out = ROOT / args.source_dir
    out.mkdir(parents=True, exist_ok=True)
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    log = []

    def query(url, params):
        full = url + '?' + urllib.parse.urlencode(params)
        for attempt in range(3):
            try:
                with opener.open(full, timeout=60) as response:
                    data = json.load(response)
                if 'error' in data:
                    code = data['error'].get('code')
                    if code in (401,403): raise PermissionError(str(data['error']))
                    raise ValueError(str(data['error']))
                log.append({'url':full, 'attempt':attempt+1, 'ok':True})
                return data
            except Exception as error:
                log.append({'url':full, 'attempt':attempt+1, 'error':str(error)})
                if isinstance(error,PermissionError) or getattr(error,'code',None) in (401,403) or attempt==2:
                    raise
                time.sleep(.5)

    try:
        for layer in (3,12,22):
            url = f'https://geodata.epa.gov/arcgis/rest/services/OEI/FRS_INTERESTS/MapServer/{layer}/query'
            inventory = query(url,{'f':'json','where':'1=1','returnIdsOnly':'true'})
            ids = sorted(inventory['objectIds'])
            (out/f'epa-{layer}-ids.json').write_text(json.dumps(inventory),encoding='utf-8')
            rows = []
            for offset in range(0,len(ids),500):
                wanted = set(ids[offset:offset+500])
                # Short range queries avoid observed failures in long GETs and
                # POSTs. Always compare actual returned IDs, not just row counts.
                data = query(url,{'f':'json','where':f'OBJECTID >= {min(wanted)} AND OBJECTID <= {max(wanted)}',
                    'outFields':'OBJECTID,REGISTRY_ID,PRIMARY_NAME,STATE_CODE,ACTIVE_STATUS,LAST_REPORTED_DATE,INTEREST_TYPE',
                    'outSR':'4326','returnGeometry':'true','resultRecordCount':1000})
                assert {row['attributes']['OBJECTID'] for row in data['features']} == wanted
                (out/f'epa-{layer}-idchunk-{offset}.json').write_text(json.dumps(data),encoding='utf-8')
                rows.extend(data['features'])
            assert {row['attributes']['OBJECTID'] for row in rows} == set(ids)
            (out/f'epa-{layer}.json').write_text(json.dumps({'features':rows,'count':len(ids)},separators=(',',':')),encoding='utf-8')
            print('Complete EPA layer',layer,len(rows),flush=True)

        for layer in (0,1):
            url = f'https://gisportal.hrsa.gov/server/rest/services/HealthCareFacilities/CMSApprovedFacilities_FS/MapServer/{layer}/query'
            count = query(url,{'f':'json','where':'1=1','returnCountOnly':'true'})['count']
            rows=[]
            while len(rows)<count:
                data=query(url,{'f':'json','where':'1=1',
                    'outFields':'CMS_PROVIDER_NUM,FACILITY_NM,CMS_PROVIDER_CAT_DESC,CMS_PROVIDER_CAT_SUB_TYP_DESC,CMS_PROVIDER_STATE_ABBR',
                    'returnGeometry':'true','outSR':'4326','orderByFields':'OBJECTID','resultOffset':len(rows),'resultRecordCount':1000})
                assert data['features']
                rows.extend(data['features'])
            assert len(rows)==count
            assert len({r['attributes']['CMS_PROVIDER_NUM'] for r in rows})==count
            (out/f'hrsa-hospitals-{layer}.json').write_text(json.dumps({'features':rows,'count':count},separators=(',',':')),encoding='utf-8')
            print('Complete CMS/HRSA layer',layer,count,flush=True)
    finally:
        (out/'facility-fetch-log.json').write_text(json.dumps(log,indent=2),encoding='utf-8')

if __name__ == '__main__':main()
