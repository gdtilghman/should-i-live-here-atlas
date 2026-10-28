"""Build the bounded 2024 ACS 5-year county community layers.

The detailed-table bulk file is public and needs no Census API key.  The
subject-table commute layer is fetched only when --acs-api-key is supplied;
without it the output records the real access blocker as unavailable.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, math, os, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BULK_URL = "https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/acsdt5y2024-b25070.dat"
B08013_URL = "https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/acsdt5y2024-b08013.dat"
B08303_URL = "https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/acsdt5y2024-b08303.dat"
B25064_URL = "https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/acsdt5y2024-b25064.dat"
B25077_URL = "https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/acsdt5y2024-b25077.dat"
API_URL = "https://api.census.gov/data/2024/acs/acs5/subject"
SUBJECT_BULK_CANDIDATES = [
    "https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/acsst5y2024-s0801.dat",
    "https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/acsdt5y2024-s0801.dat",
]

def finite(text):
    try:
        x = float(str(text).strip())
        return x if math.isfinite(x) and x >= 0 else None
    except (TypeError, ValueError):
        return None

def atlas_fips():
    geo = json.loads((ROOT / "dist/data/counties.geojson").read_text(encoding="utf-8"))
    out = {f["properties"]["fips"] for f in geo["features"]}
    assert len(out) == 3107 and all(len(x) == 5 for x in out)
    return out

def records_template(fips, reason):
    return {k: {"value": None, "low": None, "high": None, "count": None,
                 "status": "unavailable", "moe": None, "reason": reason}
            for k in sorted(fips)}

def download(url, path):
    if not path.exists():
        part = path.with_suffix(path.suffix + ".part")
        with urllib.request.urlopen(url, timeout=120) as src, part.open("wb") as dst:
            while True:
                block = src.read(1024 * 1024)
                if not block: break
                dst.write(block)
        part.replace(path)

def burden(path, fips):
    out = records_template(fips, "The 2024 ACS data do not match a county in this atlas.")
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="|")
        expected = ["GEO_ID"] + [f"B25070_{kind}{i:03d}" for i in range(1, 12) for kind in ("E", "M")]
        assert reader.fieldnames == expected, reader.fieldnames
        seen = set()
        for row in reader:
            geoid = row["GEO_ID"]
            if not geoid.startswith("0500000US"): continue
            code = geoid[-5:]
            if code not in out: continue
            assert geoid not in seen, geoid
            seen.add(geoid)
            vals = {k: finite(row.get(k)) for k in row}
            total, not_computed = vals["B25070_E001"], vals["B25070_E011"]
            bands = [vals[f"B25070_E{i:03d}"] for i in (7, 8, 9, 10)]
            if total is None or not_computed is None or any(x is None for x in bands):
                out[code]["reason"] = "ACS estimate suppressed or invalid sentinel."
                continue
            denom = total - not_computed
            if denom <= 0:
                out[code]["reason"] = "Invalid ACS denominator after excluding not-computed households."
                continue
            out[code] = {"value": round(100 * sum(bands) / denom, 6),
                         "low": None, "high": None, "count": int(denom),
                         "status": "available", "moe": None,
                         "reason": "The site calculates this share from Census rent tables. The Census does not publish a likely range for it."}
    return out

def commute(fips, key):
    if not key:
        return records_template(fips, "Census ACS subject API requires an API key; no key was provided, and no fallback year or approximation is used.")
    params = urllib.parse.urlencode({"get":"NAME,S0801_C01_046E,S0801_C01_046M", "for":"county:*", "in":"state:*", "key":key})
    with urllib.request.urlopen(API_URL + "?" + params, timeout=120) as fh:
        payload = json.loads(fh.read().decode("utf-8"))
    header, rows = payload[0], payload[1:]
    assert header[:3] == ["NAME", "S0801_C01_046E", "S0801_C01_046M"]
    out = records_template(fips, "No matching 2024 ACS county geography (Connecticut planning regions remain unmatched to the eight atlas counties).")
    for row in rows:
        item = dict(zip(header, row)); code = item.get("state", "") + item.get("county", "")
        if code not in out: continue
        value, moe = finite(item["S0801_C01_046E"]), finite(item["S0801_C01_046M"])
        if value is None:
            out[code]["reason"] = "ACS subject estimate suppressed or invalid."
        else:
            out[code] = {"value": value, "low": None if moe is None else max(0, value-moe),
                         "high": None if moe is None else value+moe, "count": None,
                         "status":"available", "moe":moe,
                         "reason":"S0801_C01_046E; 90% MOE from S0801_C01_046M; universe is workers 16+ who did not work from home."}
    assert len({r["state"]+r["county"] for r in map(lambda x: dict(zip(header,x)), rows)}) == len(rows)
    return out

def derived_commute(minutes_path, workers_path, fips):
    """Derive mean from B08013 aggregate minutes / B08303 total workers.

    Census metadata confirms both tables use workers 16+ who did not work from
    home. No MOE is invented for this ratio.
    """
    def read(path, prefix):
        values = {}
        with path.open(encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh, delimiter="|")
            assert reader.fieldnames and reader.fieldnames[:3] == ["GEO_ID", prefix+"_E001", prefix+"_M001"]
            for row in reader:
                geoid=row["GEO_ID"]
                if geoid.startswith("0500000US") and geoid[-5:] in fips:
                    assert geoid[-5:] not in values, geoid
                    values[geoid[-5:]]=finite(row[prefix+"_E001"])
        return values
    minutes, workers = read(minutes_path,"B08013"), read(workers_path,"B08303")
    out=records_template(fips,"The 2024 ACS data do not match a county in this atlas.")
    for code in fips:
        if code not in minutes or code not in workers:
            out[code]["reason"]="The 2024 survey uses Connecticut planning regions. They do not match the older counties this atlas uses."
            continue
        if minutes.get(code) is None or workers.get(code) is None or workers[code] <= 0:
            out[code]["reason"]="ACS estimate suppressed, invalid sentinel, or nonpositive worker denominator."
        else:
            out[code]={"value":round(minutes[code]/workers[code],6),"low":None,"high":None,"count":int(workers[code]),"status":"available","moe":None,"reason":"The site calculates this average from Census travel-time tables. The Census does not publish a likely range for it."}
    return out

def median_table(path, fips, table):
    out = records_template(fips, "The 2024 survey uses Connecticut planning regions. They do not match the older counties this atlas uses.")
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="|")
        expected = ["GEO_ID", f"{table}_E001", f"{table}_M001"]
        assert reader.fieldnames == expected, reader.fieldnames
        seen = set()
        for row in reader:
            geoid = row["GEO_ID"]
            if not geoid.startswith("0500000US"): continue
            code = geoid[-5:]
            if code not in out: continue
            assert code not in seen, code
            seen.add(code)
            est_raw = row[f"{table}_E001"].strip()
            moe_raw = row[f"{table}_M001"].strip()
            try:
                est = float(est_raw)
                moe = float(moe_raw)
            except ValueError:
                raise AssertionError(f"Invalid numeric value for FIPS {code}: estimate={est_raw!r}, moe={moe_raw!r}")
            if est == -666666666:
                out[code] = {"value": None, "low": None, "high": None, "count": None,
                             "status": "suppressed", "moe": None,
                             "reason": "The Census Bureau could not compute this median. The sample had too few observations."}
                continue
            if est < 0 or moe < 0 or not math.isfinite(est) or not math.isfinite(moe):
                raise AssertionError(f"Invalid median value for FIPS {code}: estimate={est_raw!r}, moe={moe_raw!r}")
            out[code] = {"value": est, "low": None, "high": None, "count": None,
                         "status": "available", "moe": moe, "reason": None}
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--source-dir", type=Path, default=ROOT/"work"); ap.add_argument("--acs-api-key", default=os.getenv("CENSUS_API_KEY")); args = ap.parse_args()
    args.source_dir.mkdir(parents=True, exist_ok=True); fips = atlas_fips()
    bulk = args.source_dir / "acs-b25070-2024-5y.dat"; download(BULK_URL, bulk)
    b = burden(bulk, fips)
    commute_mode="api" if args.acs_api_key else "derived"
    if args.acs_api_key:
        c = commute(fips, args.acs_api_key)
        commute_urls=[API_URL]
    else:
        b08013=args.source_dir/"acs-b08013-2024-5y.dat"; b08303=args.source_dir/"acs-b08303-2024-5y.dat"
        download(B08013_URL,b08013); download(B08303_URL,b08303)
        c=derived_commute(b08013,b08303,fips); commute_urls=[B08013_URL,B08303_URL]
    b25064 = args.source_dir / "acs-b25064-2024-5y.dat"; download(B25064_URL, b25064)
    rent = median_table(b25064, fips, "B25064")
    b25077 = args.source_dir / "acs-b25077-2024-5y.dat"; download(B25077_URL, b25077)
    home = median_table(b25077, fips, "B25077")
    def dataset(i, title, unit, rec, url, note):
        values = [x["value"] for x in rec.values() if x["value"] is not None]
        return {"id":i,"title":title,"unit":unit,"period":"2020–2024 ACS 5-year","sourceUrl":url,"note":note,"direction":"higher-worse","category":"affordability" if i in ("rent-burden","median-rent","median-home-value") else "access","confidenceLevel":90 if i=="commute" and args.acs_api_key else None,"records":rec,"min":min(values) if values else None,"max":max(values) if values else None}
    datasets=[dataset("rent-burden","Renter households spending 30%+ of income on gross rent","percent of renter households whose share could be calculated",b,"https://www.census.gov/programs-surveys/acs/data/summary-file.html","Renter households that pay 30% or more of their income for rent and utilities. The share leaves out households whose share the Census could not calculate. The site calculates this share, so there is no likely range.")]
    if args.acs_api_key: datasets.append(dataset("commute","Mean travel time to work","minutes",c,API_URL,"S0801_C01_046E with S0801_C01_046M 90% MOE; workers 16+ who did not work from home."))
    else: datasets.append(dataset("commute","Mean travel time to work (derived)","minutes",c,"https://www.census.gov/programs-surveys/acs/data/summary-file.html","The average time to work for workers age 16 and older who do not work from home. The site calculates it from Census tables. It is not the Census's own published average. There is no likely range."))
    datasets.append(dataset("median-rent", "Median gross rent", "dollars per month", rent, B25064_URL, "The middle monthly rent for homes rented for cash. Rent includes utilities. County details show the margin of error (90%). Higher means more expensive. It is a cost, not a measure of quality."))
    datasets.append(dataset("median-home-value", "Median home value", "dollars", home, B25077_URL, "The middle value of homes that owners live in, as the owners estimate it. County details show the margin of error (90%). Higher means more expensive. It is a cost, not a measure of quality."))
    for d in datasets:
        d['release']='2024 ACS 5-year'
        d['geographyVintage']='2024 ACS counties; joined to Census 2021 atlas counties where FIPS match'
        if d['id'] == 'rent-burden':
            sources = [(BULK_URL, bulk)]
        elif d['id'] == 'commute':
            sources = [] if args.acs_api_key else [(B08013_URL, b08013), (B08303_URL, b08303)]
        elif d['id'] == 'median-rent':
            sources = [(B25064_URL, b25064)]
        elif d['id'] == 'median-home-value':
            sources = [(B25077_URL, b25077)]
        d['sourceFiles']=[{'url':url,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()} for url,path in sources]
    payload = {"sourceUrl":"https://www.census.gov/data/developers/data-sets/acs-5year.html","note":"These values are estimates for 2020–2024 from the Census Bureau's American Community Survey. An unavailable value is not zero. Connecticut is unavailable because the survey uses planning regions, not the older counties this atlas uses.","datasets":datasets}
    (ROOT/"dist/data/community.json").write_text(json.dumps(payload,separators=(",",":")),encoding="utf-8")
    samples = {k: b[k]["value"] for k in ("06037", "36061", "48201")}
    assert samples == {"06037": 57.663858, "36061": 47.999706, "48201": 53.766136}
    bulk_candidates=[]
    # Prior acquisition investigation; do not repeat unavailable URL probes on every build.
    checksums={"B08013":hashlib.sha256((args.source_dir/"acs-b08013-2024-5y.dat").read_bytes()).hexdigest(),"B08303":hashlib.sha256((args.source_dir/"acs-b08303-2024-5y.dat").read_bytes()).hexdigest()} if not args.acs_api_key else {}
    report={"bulkUrl":BULK_URL,"bulkSha256":hashlib.sha256(bulk.read_bytes()).hexdigest(),"bulkBytes":bulk.stat().st_size,"subjectBulkCandidates":bulk_candidates,"commuteUrls":commute_urls,"commuteMode":commute_mode,"commuteChecksums":checksums,"variables":{"burden":["B25070_E001","B25070_E007","B25070_E008","B25070_E009","B25070_E010","B25070_E011"],"commute":["B08013_E001","B08303_E001"] if not args.acs_api_key else ["S0801_C01_046E","S0801_C01_046M"]},"atlasCounties":len(fips),"burdenAvailable":sum(x["status"]=="available" for x in b.values()),"burdenUnavailable":sum(x["status"]!="available" for x in b.values()),"commuteAvailable":sum(x["status"]=="available" for x in c.values()),"commuteUnavailable":sum(x["status"]!="available" for x in c.values()),"apiKeyProvided":bool(args.acs_api_key),"ctUnmatched":sorted(k for k,v in b.items() if v["status"]!="available" and k.startswith("09")),"sampleChecks":samples,"validation":{"atlasKeysExact":True,"negativeAndSentinelEstimatesExcluded":True,"burdenRatioMoe":None,"commuteRatioMoe":None,"commuteUniversesMatch":not args.acs_api_key,"commuteApiBlocker":None if args.acs_api_key else "Published S0801 requires API key; public detailed-table derivation used instead"}}
    (ROOT/"work/community-validation.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    assert len(payload["datasets"]) == 4 and all(len(d["records"])==3107 for d in payload["datasets"])
    assert all(x["value"] is None or 0 <= x["value"] <= 100 for x in b.values())
    print(json.dumps(report,indent=2))
if __name__ == "__main__": main()
