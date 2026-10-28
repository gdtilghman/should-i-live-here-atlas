const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path'),{spawnSync}=require('node:child_process');
const {register}=require('./register-tri.cjs');
const dir=path.join(__dirname,'../dist/data/overlays');
const catalog=JSON.parse(fs.readFileSync(path.join(dir,'catalog.json')));
const data=JSON.parse(fs.readFileSync(path.join(dir,'tri.json')));
test('TRI public snapshot reconciles annual facilities and original source checksum',()=>{
 assert.equal(data.points.length,21265);
 assert.equal(new Set(data.points.map(x=>x.id)).size,21265);
 assert.equal(data.retrieved,'2026-10-20');
 assert.equal(data.sourceFiles.length,1);
 assert.equal(data.sourceFiles[0].sha256,'06dfa3a67bb4c5bd38d9e9f0f7b8bff10b95254a63169423632d7f6f251e1506');
 const types=new Set(),statuses=new Set();
 for(const p of data.points){
  assert.equal(p.date,'2024');
  assert.match(p.state,/^\d{2}$/);
  assert.ok(Number.isFinite(p.longitude)&&p.longitude>=-125&&p.longitude<=-66);
  assert.ok(Number.isFinite(p.latitude)&&p.latitude>=24&&p.latitude<=50);
  assert.ok(p.name&&p.notes);
  assert.ok(Object.keys(p).every(k=>['id','name','state','longitude','latitude','groups','date','notes'].includes(k)));
  for(const g of p.groups){types.add(g.type);statuses.add(g.status);}
 }
 assert.equal(types.size,30);
 assert.deepEqual([...statuses].sort(),['Form A certification (2024)','Form R report (2024)']);
});
test('TRI registration preserves all six existing catalogs and is idempotent',()=>{
 const original={...catalog,overlays:catalog.overlays.filter(x=>x.id!=='tri')},before=JSON.stringify(original);
 const result=register(original,data);
 assert.equal(JSON.stringify(original),before);
 assert.deepEqual(result.overlays.slice(0,-1),original.overlays);
 assert.equal(result.retrieved,original.retrieved);
 assert.equal(result.overlays.at(-1).retrieved,'2026-10-20');
 assert.equal(result.overlays.at(-1).count,21265);
 assert.deepEqual(register(result,data),result);
});
test('TRI registration rejects ambiguous provenance, year, duplicate identities and form schema',()=>{
 for(const patch of [{sourceFiles:[]},{retrieved:''},{points:[]},{schemaVersion:2}]){
  assert.throws(()=>register(catalog,{...data,...patch}));
 }
 const first=data.points[0];
 assert.throws(()=>register(catalog,{...data,points:[first,first]}));
 assert.throws(()=>register(catalog,{...data,points:[{...first,date:'2025'}]}));
 assert.throws(()=>register(catalog,{...data,points:[{...first,groups:[{type:'Chemicals',status:'Operating'}]}]}));
});
test('failed TRI registration leaves existing catalog bytes unchanged',()=>{
 const temporary=fs.mkdtempSync(path.join(os.tmpdir(),'silh-tri-register-'));
 try{
  const target=path.join(temporary,'catalog.json'),shard=path.join(temporary,'tri.json'),bytes=JSON.stringify(catalog);
  fs.writeFileSync(target,bytes);fs.writeFileSync(shard,JSON.stringify({...data,points:[]}));
  const result=spawnSync(process.execPath,[path.join(__dirname,'register-tri.cjs'),target,shard],{encoding:'utf8'});
  assert.notEqual(result.status,0);
  assert.equal(fs.readFileSync(target,'utf8'),bytes);
  assert.equal(fs.existsSync(target+'.tri-tmp'),false);
 }finally{
  for(const name of ['catalog.json','tri.json','catalog.json.tri-tmp']){
   const file=path.join(temporary,name);if(fs.existsSync(file))fs.unlinkSync(file);
  }
  fs.rmdirSync(temporary);
 }
});
