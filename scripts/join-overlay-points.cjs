// County attribution for point overlays, with the same geometry and winding
// convention as app.js (see join-overlay-quakes.cjs).
// Usage: node scripts/join-overlay-points.cjs <points.json> <out.json>
// points.json is [{id, longitude, latitude}]; out.json is {id: county FIPS}.
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');const d3=require(root+'/dist/vendor/d3.min.js');
const [input,output]=process.argv.slice(2);
if(!input||!output)throw Error('Usage: node scripts/join-overlay-points.cjs <points.json> <out.json>');
const geo=JSON.parse(fs.readFileSync(root+'/dist/data/counties.geojson'));
const norm=coords=>d3.geoArea({type:'Polygon',coordinates:coords})>Math.PI*2?coords.map(r=>r.slice().reverse()):coords;
for(const f of geo.features){const g=f.geometry;g.coordinates=g.type==='Polygon'?norm(g.coordinates):g.coordinates.map(norm);f.bounds=d3.geoBounds(f);}
const points=JSON.parse(fs.readFileSync(input));const counties={};
for(const p of points){const xy=[p.longitude,p.latitude];const f=geo.features.find(f=>xy[0]>=f.bounds[0][0]&&xy[0]<=f.bounds[1][0]&&xy[1]>=f.bounds[0][1]&&xy[1]<=f.bounds[1][1]&&d3.geoContains(f,xy));if(f)counties[p.id]=f.properties.fips;}
fs.writeFileSync(output,JSON.stringify(counties));console.log('Attributed',Object.keys(counties).length,'of',points.length,'points');
