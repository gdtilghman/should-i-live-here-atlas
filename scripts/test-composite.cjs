const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {scaleStats,component,combine,rank,unranked} = require('../dist/composite.js');
const dataset = (values,extra={}) => ({title:'Test measure',unit:'units',records:Object.fromEntries(values.map((value,i)=>[String(i),{value,status:value===null?'suppressed':'available'}])),...extra});
const a=dataset([0,10,20,null]),b=dataset([20,10,0,5]);
let result=combine(['0','1','2','3'],[{key:'a',dataset:a,weight:3},{key:'b',dataset:b,weight:1}]);
assert.deepEqual(Object.values(result.records).map(r=>r.value),[25,50,75,null]);
assert.equal(result.stats.available,3);
assert.match(result.records['3'].reason,/suppressed/);
const notApplicable=dataset([null]);
notApplicable.records['0'].status='not-applicable';
assert.match(combine(['0'],[{key:'na',dataset:notApplicable,weight:1}]).records['0'].reason,/not applicable/);
// Not applicable stays missing unless the dataset itself declares it means no exposure.
const noExposure=dataset([10,20,null],{notApplicableMeans:'best-case'});
noExposure.records['2'].status='not-applicable';
assert.equal(component(noExposure.records['2'],scaleStats(noExposure)).value,0);
assert.equal(scaleStats(noExposure).count,2,'an assumed best case must not move the scale');
const assumed=combine(['0','1','2'],[{key:'h',dataset:noExposure,weight:1}]).records['2'];
assert.equal(assumed.status,'available');
assert.equal(assumed.value,0);
assert.equal(assumed.components[0].value,null,'no measurement is invented');
assert.equal(assumed.components[0].status,'not-applicable');
const betterNoExposure=dataset([10,20,null],{notApplicableMeans:'best-case',direction:'higher-better'});
betterNoExposure.records['2'].status='not-applicable';
assert.equal(combine(['2'],[{key:'h',dataset:betterNoExposure,weight:1}]).records['2'].value,0);
// Suppressed stays missing even on a dataset that declares the rule.
const declaredSuppressed=dataset([10,20,null],{notApplicableMeans:'best-case'});
assert.equal(combine(['2'],[{key:'h',dataset:declaredSuppressed,weight:1}]).records['2'].status,'unavailable');
// No exposure passes a limit on the adverse side and fails one on the favourable side.
assert.equal(combine(['2'],[{key:'h',dataset:noExposure,weight:1,threshold:{operator:'max',value:5}}]).records['2'].status,'available');
assert.equal(combine(['2'],[{key:'h',dataset:noExposure,weight:1,threshold:{operator:'min',value:5}}]).records['2'].status,'excluded');
assert.equal(combine(['2'],[{key:'h',dataset:betterNoExposure,weight:1,threshold:{operator:'min',value:5}}]).records['2'].status,'available');
assert.equal(result.weights.a,.75);
assert.equal(result.records['1'].components.reduce((n,c)=>n+c.contribution,0),50);
// Missing inactive inputs cannot remove coverage; zero active weights cannot invent a score.
assert.equal(combine(['3'],[{key:'a',dataset:a,weight:0},{key:'b',dataset:b,weight:1}]).stats.available,1);
assert.equal(combine(['0'],[{key:'a',dataset:a,weight:0}]).records['0'].value,null);
// Limits are raw values, inclusive, independent of weight, and unknown does not pass.
result=combine(['0','1','2','3'],[{key:'a',dataset:a,weight:0,threshold:{operator:'max',value:10}},{key:'b',dataset:b,weight:1}]);
assert.equal(result.records['1'].status,'available');
assert.equal(result.records['2'].status,'excluded');
assert.equal(result.records['3'].status,'unavailable');
const outliers=dataset([10,11,12,13,14,15,16,17,1000]);
assert.equal(component(outliers.records['8'],scaleStats(outliers)).extreme,true);
assert.equal(component(outliers.records['8'],scaleStats(outliers)).value,100);
const reverse=dataset([-1000,10,11,12,13,14,15,16,17],{direction:'higher-better'});
assert.equal(component(reverse.records['0'],scaleStats(reverse)).extreme,true);
assert.equal(component(reverse.records['8'],scaleStats(reverse)).value,0);
const rare=dataset([0,0,0,0,0,0,0,0,7]);
assert.equal(scaleStats(rare).hasExtremes,false);
assert.equal(component(rare.records['8'],scaleStats(rare)).value,100);
assert.equal(component(dataset([4]).records['0'],scaleStats(dataset([4]))).value,50);
assert.equal(scaleStats(dataset([null])).count,0);
assert.throws(()=>combine(['0'],[{key:'a',dataset:a,weight:NaN}]),/Weights/);
assert.throws(()=>combine(['0'],[{key:'a',dataset:a,weight:1},{key:'a',dataset:b,weight:1}]),/unique/);
// Real-data regression: independent audited four-input demonstration.
const read = name => JSON.parse(fs.readFileSync(path.join(__dirname,'../dist/data',name),'utf8'));
const cancer=read('cancer.json'), disasters=read('disasters.json');
const select=(collection,id)=>collection.datasets.find(d=>d.id===id);
const inputs=[select(disasters,'hazard-fire'),select(cancer,'066'),select(disasters,'hazard-flood'),select(cancer,'047-male')];
assert.ok(inputs.every(Boolean),'Expected exact audited cohorts');
const ids=Object.keys(inputs[0].records);
result=combine(ids,inputs.map((d,i)=>({key:String(i),dataset:d,weight:[40,30,20,10][i]})));
assert.equal(result.stats.available,2570);
assert.ok(Math.abs(result.records['06037'].value-57.5737)<.0001);
assert.equal(result.records['12125'].extreme,true);
assert.equal(result.records['12125'].value,40);
console.log('PASS: composite weights, missingness, thresholds, outliers, reverse direction and audited 3,107-county recipe.');
// Ranking: lowest score is rank 1, missing and excluded counties are never
// placed, ties fall back to FIPS, and each rank range contains the rank.
{
  const x = dataset([10, 20, 30, null, 10, 40]), y = dataset([30, 20, 10, 5, 30, 0]);
  const ids = ['0','1','2','3','4','5'];
  const r = combine(ids, [{key:'x',dataset:x,weight:1},{key:'y',dataset:y,weight:1,threshold:{operator:'max',value:25}}]);
  const ranked = rank(r.records, ids);
  assert.deepEqual(ranked.map(row => row.fips), ['1','2','5'], 'only available counties, lowest score first');
  assert.ok(ranked.every(row => row.low <= row.rank && row.rank <= row.high));
  assert.equal(rank(r.records, ['2','1']).map(row => row.rank).join(), '1,2');
  const tally = unranked(r.records, ids);
  assert.equal(tally.missing, 1);
  assert.equal(tally.excluded, 2, 'counties 0 and 4 fail the hard limit');
  assert.deepEqual(tally.inputs.map(i => [i.key, i.total, i.statuses.suppressed]), [['x', 1, 1]]);
  // Equal scores keep a stable order.
  const tie = combine(['9','8'], [{key:'t',dataset:{title:'T',records:{'9':{status:'available',value:1},'8':{status:'available',value:1}}},weight:1}]);
  assert.deepEqual(rank(tie.records, ['9','8']).map(row => row.fips), ['8','9']);
  // Two inputs pulling opposite ways: a 20% weight shift can swap them, so both ranges span 1-2.
  const p = dataset([0, 10]), q = dataset([11, 0]);
  const close = rank(combine(['0','1'], [{key:'p',dataset:p,weight:1},{key:'q',dataset:q,weight:1}]).records, ['0','1']);
  assert.deepEqual(close.map(row => [row.low, row.high]), [[1, 2], [1, 2]]);
  // A declared best case is scored, so it is ranked and never tallied as missing.
  const h = dataset([10, 20, null], {notApplicableMeans:'best-case'}); h.records['2'].status = 'not-applicable';
  const hr = combine(['0','1','2'], [{key:'h',dataset:h,weight:1}]).records;
  assert.equal(rank(hr, ['0','1','2']).find(row => row.fips === '2')?.score, 0);
  assert.equal(unranked(hr, ['0','1','2']).missing, 0);
  assert.throws(() => rank(hr, ['0'], 1), /Fraction/);
}
