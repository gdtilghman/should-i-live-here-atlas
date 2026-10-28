const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const dir=path.join(__dirname,'../dist/data/overlays');
const load=name=>JSON.parse(fs.readFileSync(path.join(dir,name)));
const catalog=load('catalog.json');
test('overlay catalog entries have period, caveat and independent family suggestions',()=>{
 assert.deepEqual(catalog.overlays.map(x=>x.id),['power','health','crashes','quakes','hospitals','epa','tri','airmonitors','stations','wildfires']);
 for(const entry of catalog.overlays){assert.match(entry.sourceUrl,/^https:\/\//);assert.ok(entry.period&&entry.caveat&&entry.relatedFamilies.length);}
});
for(const entry of catalog.overlays)test(entry.id+' source locations have unique IDs, valid coordinates and provenance',()=>{
 const data=load(entry.file);assert.equal(data.points.length,entry.count);assert.equal(new Set(data.points.map(p=>p.id)).size,entry.count);
 assert.ok(data.sourceFiles.every(f=>/^[a-f0-9]{64}$/.test(f.sha256)));
 for(const p of data.points){assert.ok(p.name&&/^\d{2}$/.test(p.state));assert.ok(Number.isFinite(p.longitude)&&p.longitude>=-125&&p.longitude<=-66);assert.ok(Number.isFinite(p.latitude)&&p.latitude>=24&&p.latitude<=50);assert.ok(p.groups.length&&p.groups.every(g=>g.type&&g.status));}
});
test('power technologies and statuses preserve nuclear, storage and retired categories',()=>{
 const data=load('power.json');const activeNuclear=data.points.filter(p=>p.groups.some(g=>g.type==='Nuclear'&&g.status==='Operating (OP)'));
 assert.equal(activeNuclear.length,54);assert.ok(data.points.some(p=>p.groups.some(g=>g.type==='Batteries')));assert.ok(data.points.some(p=>p.groups.some(g=>g.status==='Retired (RE)')));
 assert.equal(data.excluded['missing/invalid coordinates'],124);assert.equal(data.audit['Operating inventory'],28379);
});
test('technology and status must match the same generator group',()=>{
 const source=fs.readFileSync(path.join(__dirname,'../dist/overlays.js'),'utf8');const start=source.indexOf('    function matches('),end=source.indexOf('    function records()',start);const context={};vm.createContext(context);vm.runInContext(source.slice(start,end),context);
 const p={groups:[{type:'Natural Gas',fuelCode:'NG',status:'Operating (OP)'},{type:'Nuclear',fuelCode:'NUC',status:'Retired (RE)'}]};
 assert.equal(context.matches(p,{type:{value:'Nuclear'},status:{value:'Operating (OP)'}}),false);
 assert.equal(context.matches(p,{type:{value:'Nuclear'},status:{value:'Retired (RE)'}}),true);
 assert.equal(context.matches(p,{type:{value:'*'},status:{value:'Operating (OP)'}}),true);
 assert.equal(context.matches(p,{type:{value:'*'},fuel:{value:'NUC'},status:{value:'Operating (OP)'}}),false);
});
test('health sites exclude administrative-only and mobile base locations',()=>{
 const d=load('health.json');assert.equal(d.points.length,16038);assert.equal(d.excluded['mobile base is not service location'],1343);assert.equal(d.excluded['administrative-only'],1223);assert.ok(d.points.every(p=>p.id.startsWith('BPS-')));
});
test('historical events retain explicit years and exclude non-earthquakes',()=>{
 assert.ok(load('crashes.json').points.every(p=>p.date.startsWith('2023-')));const q=load('quakes.json');assert.ok(q.points.every(p=>p.date.startsWith('2025-')&&p.groups[0].type==='Earthquake M3+'));assert.equal(q.excluded['non-earthquake event'],175);
});
