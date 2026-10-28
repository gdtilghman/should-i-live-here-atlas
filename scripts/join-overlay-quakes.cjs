// State attribution uses the same geometry and winding convention as app.js.
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');const d3=require(root+'/dist/vendor/d3.min.js');
const geo=JSON.parse(fs.readFileSync(root+'/dist/data/counties.geojson'));
const norm=coords=>d3.geoArea({type:'Polygon',coordinates:coords})>Math.PI*2?coords.map(r=>r.slice().reverse()):coords;
for(const f of geo.features){const g=f.geometry;g.coordinates=g.type==='Polygon'?norm(g.coordinates):g.coordinates.map(norm);f.bounds=d3.geoBounds(f);}
const events=JSON.parse(fs.readFileSync(root+'/work/overlay-sources/usgs-quakes-2025.json'));const states={};
for(const e of events.features){const xy=e.geometry.coordinates;const f=geo.features.find(f=>xy[0]>=f.bounds[0][0]&&xy[0]<=f.bounds[1][0]&&xy[1]>=f.bounds[0][1]&&xy[1]<=f.bounds[1][1]&&d3.geoContains(f,xy));if(f)states[e.id]=f.properties.state;}
fs.writeFileSync(root+'/work/overlay-sources/usgs-quake-states.json',JSON.stringify(states));console.log('Attributed',Object.keys(states).length,'of',events.features.length,'events');
