/* Catalog locations and private browser pins; independent of county measures. */
(() => {
  'use strict';
  const NS = 'http://www.w3.org/2000/svg';
  const STORAGE = 'silh.custom-pins.v1';
  const node = (tag, text, cls) => {
    const n = document.createElement(tag);
    if (text != null) n.textContent = text;
    if (cls) n.className = cls;
    return n;
  };
  window.AtlasOverlays = { create(adapter) {
    const root = document.querySelector('#places-controls');
    if (!root || !window.AtlasOverlaySpatial) return null;
    const spatial = window.AtlasOverlaySpatial;
    const svg = adapter.svg;
    const layer = document.createElementNS(NS, 'g');
    layer.setAttribute('class', 'places-layer');
    layer.setAttribute('aria-hidden', 'true'); // Equivalent searchable list below.
    svg.append(layer);
    const catalogUI = root.querySelector('#places-catalog');
    const status = root.querySelector('#places-status');
    const list = root.querySelector('#places-results');
    const search = root.querySelector('#places-search');
    const details = root.querySelector('#place-detail');
    const editor = root.querySelector('#pin-editor');
    const pinLabel = root.querySelector('#pin-label');
    const pinNotes = root.querySelector('#pin-notes');
    const lat = root.querySelector('#pin-latitude');
    const lon = root.querySelector('#pin-longitude');
    const modeText = root.querySelector('#pin-mode-status');
    const pinToggle = root.querySelector('#pins-visible');
    const more = root.querySelector('#places-more');
    const undo = root.querySelector('#pin-undo');
    let entries = [], pins = [], deleted = null, editId = null, mode = null;
    let renderRevision = 0, lastRenderKey = null, renderedView = null;
    let frame = 0, transitioning = false, visible = [], pageSize = 30, selection = null;
    const projectedCache = new Map();
    let dirtyList = true, previousScope = null, previousFamily = null;
    try {
      const raw = localStorage.getItem(STORAGE);
      pins = spatial.normalizeCustomPins(raw ? JSON.parse(raw) : []).filter(pin => adapter.contains([pin.longitude,pin.latitude], ''));
      if (raw && pins.length === 0 && raw !== '[]') modeText.textContent = 'Saved pins could not be read. Existing browser storage has not been overwritten.';
    } catch (_) { modeText.textContent = 'Saved pins could not be read. You can use pins for this visit; saving may be unavailable.'; }
    const tell = text => { modeText.textContent = text; };
    function savePins() {
      try { localStorage.setItem(STORAGE, JSON.stringify(pins)); tell('Pins saved only in this browser. They are not synced or added to any score.'); }
      catch (_) { tell('Storage is unavailable or full. These changes last only for this visit.'); }
      dirtyList = true; refresh();
    }
    function customRecord(pin) {
      return { ...pin, name: pin.label, overlayId: 'custom', types: ['Your pin'], statuses: ['Personal note'], source: 'Your browser only', period: 'User supplied; no source date', custom: true };
    }
    function matches(record, entry) {
      return record.groups.some(g => (entry.type.value === '*' || g.type === entry.type.value) &&
        (entry.status.value === '*' || g.status === entry.status.value) && (!entry.fuel || entry.fuel.value === '*' || (g.fuelCode || 'unspecified') === entry.fuel.value));
    }
    function records() {
      const scope = adapter.state();
      const result = [];
      for (const entry of entries) {
        if (!entry.toggle.checked || !entry.data) continue;
        for (const p of entry.data.points) {
          if ((!scope || p.state === scope) && matches(p, entry)) result.push({ ...p, overlayId: entry.id, color: entry.color, source: entry.source, period: entry.period, sourceUrl: entry.sourceUrl });
        }
      }
      if (pinToggle.checked) for (const pin of pins) {
        const p = customRecord(pin);
        if (!scope || adapter.contains([p.longitude, p.latitude], scope)) result.push(p);
      }
      return result;
    }
    function metadata(p) {
      const groups = p.groups ? [...new Set(p.groups.map(g => `${g.type}${g.fuelCode ? ` (${g.fuelCode})` : ''}: ${g.status}${g.date ? `; source last reported ${g.date}` : ''}`))].join('; ') : 'Your pin — personal note';
      return `${groups}. ${p.source}. ${p.period}${p.date ? `. Record date: ${p.date}` : ''}`;
    }
    function showDetails(p) {
      selection = p;
      details.replaceChildren(node('h4', p.name), node('p', metadata(p)), node('p', `${p.latitude.toFixed(5)}, ${p.longitude.toFixed(5)}`));
      if (p.notes) details.append(node('p', p.notes));
      if (p.sourceUrl && /^https:\/\//.test(p.sourceUrl)) {
        const link = node('a', 'Source and definitions'); link.href = p.sourceUrl; link.target = '_blank'; link.rel = 'noopener noreferrer'; details.append(link);
      }
      if (p.custom) {
        const actions = node('div', null, 'places-actions');
        const edit = node('button', 'Edit'); edit.type = 'button'; edit.onclick = () => openEditor(p);
        const move = node('button', 'Move on map'); move.type = 'button'; move.onclick = () => { openEditor(p); setMode('move'); };
        const del = node('button', 'Delete this pin'); del.type = 'button'; del.onclick = () => {
          deleted = pins.find(pin => pin.id === p.id); pins = pins.filter(pin => pin.id !== p.id);
          undo.hidden = false; details.hidden = true; selection = null; cancelEditor(); savePins(); undo.focus();
        };
        actions.append(edit, move, del); details.append(actions);
      }
      details.hidden = false;
      if (window.innerWidth <= 760) details.scrollIntoView({block: 'nearest'});
    }
    function showCluster(cluster) {
      details.replaceChildren(node('h4', `${cluster.count} places grouped at this scale`), node('p', 'Zoom in to separate nearby markers, or choose a place below. The count is locations, not risk.'));
      const select = node('select'); select.setAttribute('aria-label', 'Places in this marker group');
      const sorted = [...cluster.members].sort((a,b) => a.record.name.localeCompare(b.record.name));
      sorted.forEach((p, i) => select.append(new Option(p.record.name, String(i))));
      const button = node('button', 'Show place details'); button.type = 'button'; button.onclick = () => showDetails(sorted[Number(select.value)].record);
      details.append(select, button); details.hidden = false;
      if (window.innerWidth <= 760) details.scrollIntoView({block: 'nearest'});
    }
    function updateList() {
      const query = search.value.trim().toLowerCase();
      const filtered = visible.filter(p => !query || `${p.name} ${metadata(p)}`.toLowerCase().includes(query));
      list.replaceChildren();
      filtered.slice(0, pageSize).forEach(p => {
        const li = node('li'), button = node('button', `${p.custom ? '★ ' : ''}${p.name}`);
        button.type = 'button'; button.onclick = () => showDetails(p);
        li.append(button, node('small', `${p.custom ? 'Your pin' : p.source} · ${p.period}`)); list.append(li);
      });
      more.hidden = filtered.length <= pageSize;
      status.textContent = `${visible.length.toLocaleString()} matching places in ${adapter.state() ? 'this state' : 'the lower 48'}; ${filtered.length.toLocaleString()} match your search. Nearby markers are grouped. List includes places outside the current zoom.`;
    }
    function render() {
      frame = 0;
      const scope = adapter.state(), family = adapter.family();
      if (scope !== previousScope) { previousScope = scope; dirtyList = true; details.hidden = true; selection = null; }
      if (family !== previousFamily) {
        previousFamily = family;
        for (const entry of entries) entry.related.hidden = !entry.relatedFamilies.includes(family);
      }
      if (dirtyList) {
        visible = records();
        for (const p of visible) {
          const key = `${p.longitude},${p.latitude}`;
          let xy = projectedCache.get(key);
          if (!xy) { xy = adapter.project([p.longitude,p.latitude]); projectedCache.set(key,xy); }
          p.projected = xy;
        }
        pageSize = 30; updateList(); dirtyList = false; renderRevision++;
      }
      const matrix = svg.getScreenCTM();
      if (!matrix) return;
      const rect = svg.getBoundingClientRect();
      const projected = [];
      const view = adapter.view();
      if (adapter.moving() && renderedView && !transitioning) {
        // Transform existing groups while fingers move; rebuild membership only
        // when motion ends, avoiding tens of thousands of projections per frame.
        const scale = view.k / renderedView.k;
        layer.setAttribute('transform', `translate(${view.x-renderedView.x*scale},${view.y-renderedView.y*scale}) scale(${scale})`);
        refresh(); return;
      }
      layer.removeAttribute('transform');
      const renderKey = [renderRevision,transitioning,rect.width,rect.height,view.x,view.y,view.k].join(':');
      // Keep marker DOM stable across a stationary press. Replacing its target
      // before pointerup can turn a real touch tap into a background click.
      if (renderKey === lastRenderKey) return;
      lastRenderKey = renderKey;
      renderedView = { ...view };
      layer.replaceChildren();
      if (transitioning) return;
      for (const p of visible) {
        const xy = p.projected;
        if (!xy || !Number.isFinite(xy[0]) || !Number.isFinite(xy[1])) continue;
        const sx = view.x + xy[0]*view.k, sy = view.y + xy[1]*view.k;
        const x = matrix.a*sx + matrix.c*sy + matrix.e - rect.left;
        const y = matrix.b*sx + matrix.d*sy + matrix.f - rect.top;
        if (x < 0 || x > rect.width || y < 0 || y > rect.height) continue;
        projected.push({ id: `${p.overlayId}:${p.id}`, x, y, record: p });
      }
      const clusters = spatial.clusterPoints(projected, { width: rect.width, height: rect.height, cellSize: 38, padding: 0 });
      const inverse = matrix.inverse();
      for (const cluster of clusters) {
        const pos = new DOMPoint(cluster.x+rect.left,cluster.y+rect.top).matrixTransform(inverse);
        const g = document.createElementNS(NS,'g');
        g.setAttribute('class', 'place-marker');
        g.setAttribute('transform', `translate(${pos.x},${pos.y}) scale(${1 / Math.hypot(matrix.a,matrix.b)})`);
        g.dataset.count = cluster.count;
        const p = cluster.members[0].record;
        const circle = document.createElementNS(NS,'circle'); circle.setAttribute('r',cluster.count > 1 ? '15' : '11');
        circle.setAttribute('fill',cluster.count > 1 ? '#f5eee0' : (p.custom ? '#bfa2ff' : p.color));
        const title = document.createElementNS(NS,'title'); title.textContent = cluster.count > 1 ? `${cluster.count} places; tap for list` : `${p.name}. ${metadata(p)}`;
        const text = document.createElementNS(NS,'text'); text.textContent = cluster.count > 1 ? String(cluster.count) : p.custom ? '★' : '•';
        g.append(circle,text,title);
        g.addEventListener('click', e => { e.stopPropagation(); if (adapter.suppressed()) return; cluster.count > 1 ? showCluster(cluster) : showDetails(p); });
        layer.append(g);
      }
    }
    function refresh() { if (!frame) frame = requestAnimationFrame(render); }
    function setMode(next) {
      mode = next; adapter.cancelGesture(); svg.classList.toggle('is-placing-pin', Boolean(mode));
      tell(mode ? `${mode === 'move' ? 'Move' : 'Add'} pin: tap a mapped county, or enter coordinates below. Drag and pinch still navigate. Save to keep the pin; Cancel exits.` : 'Pin placement ended.');
      if (mode) svg.scrollIntoView({ block: 'center', behavior: 'auto' });
    }
    function cancelEditor() { mode = null; editId = null; editor.hidden = true; svg.classList.remove('is-placing-pin'); }
    function openEditor(p = null) {
      if (!p && pins.length >= 100) { tell('You can save up to 100 personal pins. Delete a pin before adding another.'); return; }
      editId = p?.id || null; pinLabel.value = p?.name || ''; pinNotes.value = p?.notes || '';
      lat.value = p?.latitude ?? ''; lon.value = p?.longitude ?? ''; editor.hidden = false;
      tell('Edit label, notes or coordinates, then Save. Personal pins are not verified source data.');
      pinLabel.focus();
    }
    root.querySelector('#pin-add').onclick = () => { openEditor(); if (!editor.hidden) setMode('add'); };
    root.querySelector('#pin-cancel').onclick = () => { cancelEditor(); tell('Pin editing cancelled.'); };
    editor.addEventListener('submit', e => {
      e.preventDefault();
      if (!lat.value.trim() || !lon.value.trim()) { tell('Choose a mapped location or enter both coordinates.'); return; }
      const latitude = Number(lat.value), longitude = Number(lon.value);
      if (!Number.isFinite(latitude) || !Number.isFinite(longitude) || !adapter.contains([longitude,latitude], '')) { tell('Use a location inside a mapped lower-48 county. Coastlines are simplified; nearby offshore points are not accepted.'); return; }
      const candidate = { id: editId || crypto.randomUUID(), label: pinLabel.value, notes: pinNotes.value, latitude, longitude };
      const valid = spatial.normalizeCustomPins([candidate]);
      if (!valid.length) { tell('Enter a label of 1–100 characters and notes of at most 1,000 characters.'); return; }
      pins = [...pins.filter(p => p.id !== valid[0].id),valid[0]]; cancelEditor(); savePins(); showDetails(customRecord(valid[0]));
    });
    // Registered after the app's capture-phase gesture suppression: taps only.
    svg.addEventListener('click', e => {
      if (!mode) return;
      e.preventDefault(); e.stopImmediatePropagation();
      if (adapter.suppressed()) return;
      const coords = adapter.invert(e);
      if (!coords || !adapter.contains(coords, adapter.state())) { tell('Tap inside a mapped county, or enter coordinates. Empty background does not place a pin.'); return; }
      lon.value = coords[0].toFixed(6); lat.value = coords[1].toFixed(6);
      tell('Location chosen. Add a label and Save to keep this personal pin.');
      editor.scrollIntoView({block:'nearest'}); pinLabel.focus();
    }, true);
    svg.addEventListener('keydown', e => { if (e.key === 'Escape' && mode) { e.stopImmediatePropagation(); cancelEditor(); tell('Pin placement cancelled.'); } }, true);
    undo.onclick = () => { if (deleted && pins.length < 100) { pins.push(deleted); deleted = null; undo.hidden = true; savePins(); } };
    pinToggle.onchange = () => { dirtyList = true; refresh(); };
    search.oninput = () => { pageSize = 30; updateList(); };
    more.onclick = () => { pageSize += 30; updateList(); };
    window.addEventListener('resize',refresh);
    async function loadCatalog() {
      try {
        const response = await fetch('./data/overlays/catalog.json');
        if (!response.ok) throw new Error('catalog');
        const catalog = await response.json();
        for (const spec of catalog.overlays) {
          const entry = { ...spec, data: null };
          const box = node('details',null,'place-category');
          const summary = node('summary',spec.label);
          const related = node('span','Related to this heatmap','places-related'); related.hidden = !spec.relatedFamilies.includes(adapter.family());
          const toggle = node('input'); toggle.type = 'checkbox'; toggle.id = `places-${spec.id}`;
          const label = node('label',null,'places-toggle'); label.append(toggle,document.createTextNode(` Show ${spec.label}`));
          label.style.setProperty('--place-color',spec.color);
          const type = node('select'); type.setAttribute('aria-label',`${spec.label}: type`); type.append(new Option('All types','*'));
          const stat = node('select'); stat.setAttribute('aria-label',`${spec.label}: status`); stat.append(new Option('All source statuses','*'));
          const fuel = spec.id === 'power' ? node('select') : null;
          if (fuel) { fuel.setAttribute('aria-label','Power plants & storage: fuel or energy source'); fuel.append(new Option('All fuels / energy sources','*')); }
          const note = node('p', `${spec.source} · ${spec.period}. Retrieved ${spec.retrieved}. ${spec.caveat}`);
          const link = node('a','Source'); link.href = spec.sourceUrl; link.target = '_blank'; link.rel = 'noopener noreferrer';
          const loadStatus = node('p'); loadStatus.setAttribute('role','status');
          box.append(summary,related,label,type); if (fuel) box.append(fuel); box.append(stat,note,link,loadStatus); catalogUI.append(box);
          Object.assign(entry,{toggle,type,status:stat,fuel,related}); entries.push(entry);
          const changed = () => { dirtyList = true; details.hidden = true; refresh(); };
          type.onchange = changed; stat.onchange = changed; if (fuel) fuel.onchange = changed;
          toggle.onchange = async () => {
            if (toggle.checked && !entry.data) {
              toggle.disabled = true; loadStatus.textContent = 'Loading locations…';
              try {
                const r = await fetch(`./data/overlays/${spec.file}`); if (!r.ok) throw new Error('source');
                const data = await r.json();
                if (!Array.isArray(data.points) || !data.points.every(p => p && typeof p.id === 'string' && typeof p.name === 'string' && /^\d{2}$/.test(p.state) && Number.isFinite(p.longitude) && Number.isFinite(p.latitude) && Array.isArray(p.groups) && p.groups.length && p.groups.every(g => typeof g.type === 'string' && typeof g.status === 'string'))) throw new Error('format');
                entry.data = data;
                const types = [...new Set(data.points.flatMap(p => p.groups.map(g => g.type)))].sort();
                const statuses = [...new Set(data.points.flatMap(p => p.groups.map(g => g.status)))].sort();
                if (fuel) {
                  const labels = { AB:'Agricultural by-products', BFG:'Blast furnace gas', BIT:'Bituminous coal', BLQ:'Black liquor', DFO:'Distillate fuel oil', GEO:'Geothermal', H2:'Hydrogen', JF:'Jet fuel', KER:'Kerosene', LFG:'Landfill gas', LIG:'Lignite coal', MSW:'Municipal solid waste', MWH:'Electricity for storage', NG:'Natural gas', NUC:'Nuclear', OBG:'Other biomass gas', OBL:'Other biomass liquids', OBS:'Other biomass solids', OG:'Other gas', OTH:'Other energy source', PC:'Petroleum coke', PG:'Gaseous propane', PUR:'Purchased steam', RC:'Refined coal', RFO:'Residual fuel oil', SGC:'Coal-derived synthesis gas', SGP:'Synthesis gas from petroleum coke', SLW:'Sludge waste', SUB:'Subbituminous coal', SUN:'Solar', TDF:'Tire-derived fuels', WAT:'Water / hydro (including pumped storage)', WC:'Waste / other coal', WDL:'Wood waste liquids', WDS:'Wood / wood waste solids', WH:'Waste heat', WND:'Wind', WO:'Waste / other oil', unspecified:'Unspecified' };
                  [...new Set(data.points.flatMap(p => p.groups.map(g => g.fuelCode || 'unspecified')))].sort().forEach(code => {
                    const technologies = [...new Set(data.points.flatMap(p => p.groups.filter(g => (g.fuelCode || 'unspecified') === code).map(g => g.type)))];
                    fuel.append(new Option(`${labels[code] || technologies.join(' / ')} (${code})`,code));
                  });
                }
                types.forEach(t => type.append(new Option(t,t))); statuses.forEach(s => stat.append(new Option(s,s)));
                if (spec.defaultStatus && statuses.includes(spec.defaultStatus)) stat.value = spec.defaultStatus;
                loadStatus.textContent = `${data.points.length.toLocaleString()} mapped source locations. ${data.exclusionsSummary || ''}`;
              } catch (_) { entry.data = null; toggle.checked = false; loadStatus.textContent = 'Locations could not load. Toggle on to retry. Heatmaps still work.'; }
              finally { toggle.disabled = false; }
            }
            changed();
          };
        }
      } catch (_) { catalogUI.textContent = 'Place catalog could not load. Personal pins and heatmaps still work; reload to retry.'; }
      dirtyList = true; refresh();
    }
    loadCatalog();
    return { refresh, transition(active) { transitioning = active; refresh(); }, changed() { dirtyList = true; refresh(); } };
  } };
})();
