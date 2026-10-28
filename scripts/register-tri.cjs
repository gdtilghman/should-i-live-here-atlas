/* Register one independently prepared annual TRI catalog without redating older sources. */
'use strict';
const fs=require('node:fs'),path=require('node:path');
function register(catalog,shard){
  if(catalog.schemaVersion!==1||!Array.isArray(catalog.overlays))throw Error('Invalid overlay catalog');
  if(shard.schemaVersion!==1||!Array.isArray(shard.points)||!shard.points.length||!/^\d{4}-\d{2}-\d{2}$/.test(shard.retrieved||''))throw Error('Invalid TRI snapshot');
  if(!Array.isArray(shard.sourceFiles)||!shard.sourceFiles.length||!shard.sourceFiles.every(x=>/^[a-f0-9]{64}$/.test(x.sha256)))throw Error('TRI source provenance required');
  if(shard.points.some(p=>p.date!=='2024'||!p.id||!p.groups?.length||p.groups.some(g=>!g.type||!['Form R report (2024)','Form A certification (2024)'].includes(g.status))))throw Error('Expected audited 2024 reporting-site schema');
  if(new Set(shard.points.map(p=>p.id)).size!==shard.points.length)throw Error('Duplicate TRI facility identities');
  const spec={id:'tri',label:'TRI reporting facilities (2024)',file:'tri.json',color:'#ded49a',
    source:'EPA Toxics Release Inventory',sourceUrl:'https://www.epa.gov/toxics-release-inventory-tri-program/tri-basic-data-files-calendar-years-1987-present',
    period:'2024 reporting year; CSV retrieved '+shard.retrieved,relatedFamilies:['air','water','cancer','hazards'],
    caveat:'Facilities submitting 2024 TRI chemical reporting forms; industry and form filters match the same report. Limited sectors, chemicals and thresholds: not every pollution source. Reporting does not establish a release, violation, measured exposure, current operating status or individual health risk. Form A is not a zero-release measurement. Counts are facilities, not toxicity.',
    count:shard.points.length,retrieved:shard.retrieved};
  const overlays=catalog.overlays.filter(x=>x.id!=='tri');
  return {...catalog,overlays:[...overlays,spec]};
}
if(require.main===module){
  const args=process.argv.slice(2);
  if(args.length!==2)throw Error('Usage: node scripts/register-tri.cjs <catalog.json> <tri.json>');
  const [catalogPath,shardPath]=args.map(x=>path.resolve(x));
  if(path.dirname(catalogPath)!==path.dirname(shardPath)||path.basename(shardPath)!=='tri.json')throw Error('Catalog and tri.json must share the overlay directory');
  const result=register(JSON.parse(fs.readFileSync(catalogPath,'utf8')),JSON.parse(fs.readFileSync(shardPath,'utf8')));
  const temporary=catalogPath+'.tri-tmp';
  try{fs.writeFileSync(temporary,JSON.stringify(result,null,2)+'\n');fs.renameSync(temporary,catalogPath);}
  finally{if(fs.existsSync(temporary))fs.unlinkSync(temporary);}
  console.log('Registered TRI:',result.overlays.at(-1).count,'sites; original source metadata preserved.');
}
module.exports={register};
