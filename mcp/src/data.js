// In-memory database over the packed atlas data.
// Cloudflare Worker safe: ES module, no dependencies, no Node-only APIs.

const STATE_POSTAL = {
  AL: '01', AK: '02', AZ: '04', AR: '05', CA: '06', CO: '08', CT: '09', DE: '10',
  DC: '11', FL: '12', GA: '13', HI: '15', ID: '16', IL: '17', IN: '18', IA: '19',
  KS: '20', KY: '21', LA: '22', ME: '23', MD: '24', MA: '25', MI: '26', MN: '27',
  MS: '28', MO: '29', MT: '30', NE: '31', NV: '32', NH: '33', NJ: '34', NM: '35',
  NY: '36', NC: '37', ND: '38', OH: '39', OK: '40', OR: '41', PA: '42', RI: '44',
  SC: '45', SD: '46', TN: '47', TX: '48', UT: '49', VT: '50', VA: '51', WA: '53',
  WV: '54', WI: '55', WY: '56',
};

const COUNTY_SUFFIXES = [
  ' county',
  ' parish',
  ' city',
  ' borough',
  ' census area',
  ' city and borough',
  ' municipality',
];

const SYNONYM_GROUPS = [
  {
    words: ['cost of living', 'living costs', 'affordability', 'housing cost', 'housing costs', 'cost'],
    keys: ['community:median-rent', 'community:median-home-value'],
    proxy: true,
  },
  {
    words: ['home value', 'home values', 'home price', 'home prices', 'house price', 'house prices'],
    keys: ['community:median-home-value'],
    proxy: true,
  },
  { words: ['rent burden'], keys: ['community:rent-burden'], proxy: false },
  { words: ['rent'], keys: ['community:median-rent'], proxy: true },
  { words: ['internet', 'broadband'], keys: ['broadband:without-100-20'], proxy: false },
  { words: ['cancer'], keys: ['cancer:001'], proxy: false },
  { words: ['violent crime'], keys: ['crime:violent-crime'], proxy: false },
  { words: ['property crime'], keys: ['crime:property-crime'], proxy: false },
  { words: ['crime', 'safety'], keys: ['crime:violent-crime', 'crime:property-crime'], proxy: false },
  { words: ['unemployment', 'jobs', 'employment'], keys: ['employment:unemployment-rate'], proxy: false },
  { words: ['air quality', 'air pollution', 'pollution', 'air'], keys: ['air:pm25-2020-2022'], proxy: false },
  { words: ['drinking water', 'water'], keys: ['water:health-violations-2023-2025'], proxy: false },
  { words: ['wildfire', 'fire'], keys: ['wildfire:risk-to-homes'], proxy: false },
  { words: ['heat', 'hot days'], keys: ['climate:hot-days-95f'], proxy: false },
  { words: ['commute'], keys: ['community:commute'], proxy: false },
  { words: ['primary care', 'doctors', 'health care', 'healthcare'], keys: ['healthcare:hpsa-primary-care'], proxy: false },
  { words: ['traffic', 'road safety'], keys: ['traffic:deaths-2019-2023'], proxy: false },
  { words: ['storms', 'severe weather'], keys: ['storms:storm-total'], proxy: false },
  { words: ['tornado', 'tornadoes'], keys: ['storms:storm-tornado'], proxy: false },
  { words: ['uninsured', 'health insurance'], keys: ['places:uninsured'], proxy: false },
];

function escapeRegExp(text) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// Lowercase, collapse whitespace, trim.
function normalizeName(text) {
  return text.toLowerCase().replace(/\s+/g, ' ').trim();
}

function measureLabel(m) {
  if (m.family === 'cancer') return m.title + ' · ' + (m.sex || 'All residents');
  return m.title;
}

// Synonym list, longest first so more specific phrases win.
const SYNONYMS = [];
for (const group of SYNONYM_GROUPS) {
  for (const word of group.words) {
    SYNONYMS.push({
      pattern: new RegExp('\\b' + escapeRegExp(word) + '\\b'),
      keys: group.keys,
      proxy: group.proxy,
      length: word.length,
    });
  }
}
SYNONYMS.sort((a, b) => b.length - a.length);

export function loadData({ counties, measures, values, status }) {
  const countyCount = counties.length;
  const valuesArr = new Float64Array(values);
  const statusArr = new Uint8Array(status);
  const statusCodes = measures.statusCodes;
  const measureList = measures.measures;

  const measureByKey = new Map();
  const searchableTitles = [];
  for (const m of measureList) {
    measureByKey.set(m.key, m);
    searchableTitles.push({ key: m.key, title: m.title.toLowerCase() });
  }

  const countyIndexByFips = new Map();
  const stateSet = new Set();
  const stateByLowerName = new Map();
  for (let i = 0; i < countyCount; i++) {
    const c = counties[i];
    countyIndexByFips.set(c.fips, i);
    stateSet.add(c.state);
    const lowerName = c.stateName.toLowerCase();
    if (!stateByLowerName.has(lowerName)) stateByLowerName.set(lowerName, c.state);
  }

  // Lazily built caches: per-measure available counts, sorted values, dataset records.
  const availableCounts = new Map();
  const sortedValuesByMeasure = new Map();
  const recordsByKey = new Map();

  function measure(key) {
    return measureByKey.get(key) || null;
  }

  function countAvailable(m) {
    let n = availableCounts.get(m.index);
    if (n === undefined) {
      const base = m.index * countyCount;
      n = 0;
      for (let i = 0; i < countyCount; i++) if (statusArr[base + i] === 0) n += 1;
      availableCounts.set(m.index, n);
    }
    return n;
  }

  function listMeasures(filter) {
    const needle = filter === undefined || filter === null ? '' : String(filter).toLowerCase();
    const out = [];
    for (const m of measureList) {
      if (needle) {
        const family = (m.family || '').toLowerCase();
        if (!m.key.toLowerCase().includes(needle)
          && !m.title.toLowerCase().includes(needle)
          && !family.includes(needle)) continue;
      }
      out.push({
        key: m.key,
        family: m.family,
        title: m.title,
        label: measureLabel(m),
        unit: m.unit,
        period: m.period,
        direction: m.direction,
        available: countAvailable(m),
      });
    }
    return out;
  }

  function value(key, fips) {
    const m = measureByKey.get(key);
    const countyIndex = countyIndexByFips.get(fips);
    if (!m || countyIndex === undefined) return { status: 'unavailable', value: null };
    const pos = m.index * countyCount + countyIndex;
    const code = statusArr[pos];
    if (code === 0) return { status: 'available', value: valuesArr[pos] };
    return { status: statusCodes[code], value: null };
  }

  function dataset(key) {
    const m = measureByKey.get(key);
    if (!m) return null;
    let records = recordsByKey.get(key);
    if (!records) {
      records = {};
      const base = m.index * countyCount;
      for (let i = 0; i < countyCount; i++) {
        const code = statusArr[base + i];
        records[counties[i].fips] = code === 0
          ? { status: 'available', value: valuesArr[base + i] }
          : { status: statusCodes[code], value: null };
      }
      recordsByKey.set(key, records);
    }
    return {
      key: m.key,
      title: m.title,
      label: measureLabel(m),
      unit: m.unit,
      period: m.period,
      direction: m.direction,
      notApplicableMeans: m.notApplicableMeans != null ? m.notApplicableMeans : undefined,
      sourceUrl: m.sourceUrl,
      records,
    };
  }

  function stateFips(text) {
    if (typeof text !== 'string') return null;
    const trimmed = text.trim();
    if (!trimmed) return null;
    if (/^\d{2}$/.test(trimmed)) return stateSet.has(trimmed) ? trimmed : null;
    const postal = STATE_POSTAL[trimmed.toUpperCase()];
    if (postal && stateSet.has(postal)) return postal;
    const byName = stateByLowerName.get(trimmed.toLowerCase());
    return byName !== undefined && stateSet.has(byName) ? byName : null;
  }

  function findCounties(query) {
    if (typeof query !== 'string') return [];
    const trimmed = query.trim();
    if (!trimmed) return [];
    if (/^\d{5}$/.test(trimmed)) {
      const index = countyIndexByFips.get(trimmed);
      return index === undefined ? [] : [counties[index]];
    }
    const comma = trimmed.lastIndexOf(',');
    if (comma === -1) return [];
    const wantedName = normalizeName(trimmed.slice(0, comma));
    const state = stateFips(trimmed.slice(comma + 1));
    if (!state) return [];
    const matches = [];
    for (const c of counties) {
      if (c.state !== state) continue;
      const name = normalizeName(c.name);
      let hit = name === wantedName;
      if (!hit) {
        for (const suffix of COUNTY_SUFFIXES) {
          if (name.endsWith(suffix) && name.slice(0, -suffix.length) === wantedName) {
            hit = true;
            break;
          }
        }
      }
      if (hit) matches.push(c);
    }
    matches.sort((a, b) => (a.fips < b.fips ? -1 : a.fips > b.fips ? 1 : 0));
    return matches;
  }

  function findMeasures(terms) {
    const matches = [];
    const notAvailable = [];
    for (const raw of terms || []) {
      if (typeof raw !== 'string') continue;
      const term = raw.trim();
      const t = normalizeName(raw);
      if (!t) continue;
      const exact = measureByKey.get(t);
      if (exact) {
        matches.push({ term, keys: [exact.key], proxy: false });
        continue;
      }
      let synonym = null;
      for (const s of SYNONYMS) {
        if (s.pattern.test(t)) {
          synonym = s;
          break;
        }
      }
      if (synonym) {
        matches.push({ term, keys: synonym.keys.slice(), proxy: synonym.proxy });
        continue;
      }
      const keys = [];
      for (const entry of searchableTitles) {
        if (entry.title.includes(t)) {
          keys.push(entry.key);
          if (keys.length === 5) break;
        }
      }
      if (keys.length) matches.push({ term, keys, proxy: false });
      else notAvailable.push(term);
    }
    return { matches, not_available: notAvailable };
  }

  function availableValuesSorted(m) {
    let sorted = sortedValuesByMeasure.get(m.index);
    if (!sorted) {
      const base = m.index * countyCount;
      const list = [];
      for (let i = 0; i < countyCount; i++) {
        if (statusArr[base + i] === 0) list.push(valuesArr[base + i]);
      }
      list.sort((a, b) => a - b);
      sorted = list;
      sortedValuesByMeasure.set(m.index, sorted);
    }
    return sorted;
  }

  function percentile(key, fips) {
    const m = measureByKey.get(key);
    const countyIndex = countyIndexByFips.get(fips);
    if (!m || countyIndex === undefined) return null;
    const pos = m.index * countyCount + countyIndex;
    if (statusArr[pos] !== 0) return null;
    const sorted = availableValuesSorted(m);
    const total = sorted.length;
    if (!total) return null;
    const target = valuesArr[pos];
    // Binary search for the count of strictly lower values.
    let lo = 0;
    let hi = total;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (sorted[mid] < target) lo = mid + 1;
      else hi = mid;
    }
    return Math.round((100 * lo) / total);
  }

  return {
    counties,
    measures: measureList,
    countyCount,
    measure,
    listMeasures,
    value,
    dataset,
    findCounties,
    stateFips,
    findMeasures,
    percentile,
  };
}
