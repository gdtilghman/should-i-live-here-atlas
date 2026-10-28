const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {combine,weightSensitivity} = require('../dist/composite.js');
const dataset = (values,extra={}) => ({title:'Test measure',unit:'units',records:Object.fromEntries(values.map((value,i)=>[String(i),{value,status:value===null?'suppressed':'available'}])),...extra});
const close=(x,y,msg)=>assert.ok(Math.abs(x-y)<1e-9,msg||`${x} != ${y}`);
const a=dataset([0,10,20,null]),b=dataset([20,10,0,5]);

// Two-signal known case, independently computed.
let result=combine(['0','1','2','3'],[{key:'a',dataset:a,weight:3},{key:'b',dataset:b,weight:1}]);
const rec=result.records['2'];
const sens=weightSensitivity(rec);
assert.equal(sens.status,'available');
assert.equal(sens.baseline,75);
const wA=.75,wB=.25;
const expected={
 'a:0.8':100*(wA*.8)/(wA*.8+wB),
 'a:1.2':100*(wA*1.2)/(wA*1.2+wB),
 'b:0.8':100*wA/(wA+wB*.8),
 'b:1.2':100*wA/(wA+wB*1.2),
};
assert.deepEqual(sens.scenarios.map(s=>s.key),['a','a','b','b']);
close(sens.scenarios[0].factor,0.8); close(sens.scenarios[1].factor,1.2);
for(const s of sens.scenarios) close(s.value,expected[s.key+':'+s.factor]);
close(sens.min,Math.min(...Object.values(expected),75));
close(sens.max,Math.max(...Object.values(expected),75));

// Single positive component: score unchanged.
const single=combine(['0'],[{key:'a',dataset:a,weight:1}]).records['0'];
const ss=weightSensitivity(single);
assert.equal(ss.baseline,0);
ss.scenarios.forEach(s=>close(s.value,ss.baseline));

// Zero-weight threshold-only component stays inactive.
const zero=combine(['0'],[{key:'a',dataset:a,weight:0,threshold:{operator:'max',value:10}},{key:'b',dataset:b,weight:1}]).records['0'];
const zs=weightSensitivity(zero);
assert.deepEqual(zs.scenarios.map(s=>s.key),['b','b']);
assert.equal(zs.baseline,100);

// Missing and excluded records never fabricate values.
const missing=combine(['3'],[{key:'a',dataset:a,weight:1}]).records['3'];
assert.deepEqual(weightSensitivity(missing),{status:'unavailable',baseline:null,min:null,max:null,scenarios:[]});
const excluded=combine(['0','2'],[{key:'a',dataset:a,weight:0,threshold:{operator:'max',value:10}},{key:'b',dataset:b,weight:1}]).records['2'];
assert.equal(excluded.status,'excluded');
assert.deepEqual(weightSensitivity(excluded),{status:'excluded',baseline:null,min:null,max:null,scenarios:[]});

// Invalid fraction rejected.
for(const f of [0,1,-0.1,1.5,NaN,Infinity,-Infinity,'0.2',null,'']) assert.throws(()=>weightSensitivity(rec,f),/Fraction/);
assert.equal(weightSensitivity(rec).scenarios.length,4);

// Malformed available records rejected rather than producing NaN.
assert.throws(()=>weightSensitivity({status:'available',value:NaN,components:[{key:'a',weight:1,scaled:100}]}),/Malformed/);
assert.throws(()=>weightSensitivity({status:'available',value:50,components:[{key:'a',weight:1,scaled:NaN}]}),/Malformed/);
assert.throws(()=>weightSensitivity({status:'available',value:50,components:[{key:'a',weight:0,scaled:null}]}),/Malformed/);
assert.throws(()=>weightSensitivity({status:'available',value:50,components:[null]}),/Malformed/);
assert.throws(()=>weightSensitivity({status:'available',value:50,components:[{weight:1,scaled:100}]}),/Malformed/);
assert.throws(()=>weightSensitivity({status:'available',value:50,components:[{key:'a',weight:1,scaled:100},{key:'a',weight:1,scaled:50}]}),/Malformed/);
assert.throws(()=>weightSensitivity({status:'available',value:50,components:[{key:'a',weight:-1,scaled:100}]}),/Malformed/);
assert.throws(()=>weightSensitivity({status:'available',value:50,components:[{key:'a',weight:Infinity,scaled:100}]}),/Malformed/);
// Fraction validated on every call, even for inactive records.
assert.throws(()=>weightSensitivity(missing,0),/Fraction/);
assert.throws(()=>weightSensitivity(excluded,NaN),/Fraction/);

// No mutation.
const before=JSON.stringify(result.records['2']);
weightSensitivity(result.records['2']);
assert.equal(JSON.stringify(result.records['2']),before);

// Real default county recipe (audited four-input composite).
const read = name => JSON.parse(fs.readFileSync(path.join(__dirname,'../dist/data',name),'utf8'));
const cancer=read('cancer.json'), disasters=read('disasters.json');
const select=(collection,id)=>collection.datasets.find(d=>d.id===id);
const inputs=[select(disasters,'hazard-fire'),select(cancer,'066'),select(disasters,'hazard-flood'),select(cancer,'047-male')];
assert.ok(inputs.every(Boolean),'Expected exact audited cohorts');
const ids=Object.keys(inputs[0].records);
const recipe=combine(ids,inputs.map((d,i)=>({key:String(i),dataset:d,weight:[40,30,20,10][i]})));
const la=recipe.records['06037'];
assert.ok(Math.abs(la.value-57.5737)<.0001);
const ls=weightSensitivity(la);
assert.equal(ls.status,'available');
close(ls.baseline,la.value);
assert.equal(ls.scenarios.length,8);
assert.ok(ls.scenarios.every(s=>Number.isFinite(s.value)));
assert.ok(ls.min<=ls.baseline && ls.baseline<=ls.max);
assert.ok(ls.min<ls.baseline && ls.max>ls.baseline);
console.log('PASS: weight sensitivity (two-signal case, single/zero weights, missingness, invalid fraction, no mutation, real county recipe).');
assert.throws(()=>weightSensitivity({status:'available',value:50,components:[{key:'a',weight:1e308,scaled:100},{key:'b',weight:1e308,scaled:50}]}),/Malformed/);
