import composite from '../../dist/composite.js';

export const CAUTIONS = Object.freeze({
  county: 'County values describe groups of residents. They are not your personal risk, and they do not tell you where to live.',
  missing: 'Counties with missing data are left out, never scored as low.',
  proxy: 'Median rent and median home value are proxies. They are not a full cost-of-living index.',
  site: 'Check the values at https://shouldilivehere.org/',
  small: 'Some of these counties have fewer than 10,000 residents. Rates in small counties can change a lot from year to year.',
  population: 'Population: US Census Bureau American Community Survey, 2019-2023 5-year estimates, table B01003.',
});
const SMALL_COUNTY = 10000;

// fips -> county, built once per db.
const countyMaps = new WeakMap();

function countyMap(db) {
  let map = countyMaps.get(db);
  if (!map) {
    map = new Map(db.counties.map(c => [c.fips, c]));
    countyMaps.set(db, map);
  }
  return map;
}

export function crimeCaution(db) {
  const measure = db.listMeasures().find(m => m.key === 'crime:violent-crime');
  const covered = measure ? measure.available : 0;
  return `The FBI advises against ranking places with these data. Crime data cover ${covered.toLocaleString('en-US')} of ${db.countyCount.toLocaleString('en-US')} counties.`;
}

export function tieCaution(count) {
  return `${count.toLocaleString('en-US')} counties share the best score. Within a tie, the order is by FIPS code only.`;
}

export function cautionsFor(db, keys, { small = false, population = false, topTie = 0 } = {}) {
  const cautions = [CAUTIONS.county, CAUTIONS.missing];
  if (keys.some(k => k.startsWith('crime:'))) cautions.push(crimeCaution(db));
  if (keys.includes('community:median-rent') || keys.includes('community:median-home-value')) {
    cautions.push(CAUTIONS.proxy);
  }
  if (small) cautions.push(CAUTIONS.small);
  if (population) cautions.push(CAUTIONS.population);
  if (topTie > 1) cautions.push(tieCaution(topTie));
  cautions.push(CAUTIONS.site);
  return cautions;
}

const isFiniteNumber = x => typeof x === 'number' && Number.isFinite(x);

export function rankCounties(db, { measures, state, count, min_population: minPopulation } = {}) {
  if (!Array.isArray(measures) || measures.length < 1 || measures.length > 10) {
    throw new Error('Give 1 to 10 measures.');
  }

  const keys = measures.map(m => m.key);
  if (new Set(keys).size !== keys.length) throw new Error('Each measure may appear once.');

  for (const key of keys) {
    if (db.measure(key) === null) throw new Error(`Unknown measure: ${key}`);
  }

  for (const m of measures) {
    if (m.weight !== undefined && (!isFiniteNumber(m.weight) || m.weight < 0)) {
      throw new Error('Weights must be 0 or more.');
    }
  }

  if (count !== undefined && (!Number.isInteger(count) || count < 1 || count > 25)) {
    throw new Error('count must be 1 to 25.');
  }

  if (minPopulation !== undefined && (!Number.isInteger(minPopulation) || minPopulation < 0)) {
    throw new Error('min_population must be a whole number, 0 or more.');
  }

  let stateFips = null;
  if (typeof state === 'string' && state !== '') {
    stateFips = db.stateFips(state);
    if (stateFips === null) throw new Error(`Unknown state: ${state}`);
  }

  const inState = db.counties.filter(c => stateFips === null || c.state === stateFips);
  // Like the state filter, the population limit chooses which counties are
  // compared. Scales and percentiles stay national.
  const usePopulation = minPopulation !== undefined;
  const countyIds = inState
    .filter(c => !usePopulation || (c.population !== null && c.population >= minPopulation))
    .map(c => c.fips);

  const signals = measures.map(m => ({
    key: m.key,
    dataset: db.dataset(m.key),
    weight: m.weight ?? 1,
    threshold: isFiniteNumber(m.max)
      ? { operator: 'max', value: m.max }
      : isFiniteNumber(m.min) ? { operator: 'min', value: m.min } : undefined,
  }));

  const { records } = composite.combine(countyIds, signals);
  const ranked = composite.rank(records, countyIds);
  const unranked = composite.unranked(records, countyIds);

  // composite.rank breaks equal scores by FIPS, so a shared score needs saying.
  const shared = new Map();
  for (const row of ranked) shared.set(row.score, (shared.get(row.score) || 0) + 1);

  const byFips = countyMap(db);
  const results = ranked.slice(0, count ?? 10).map((row, i) => {
    const county = byFips.get(row.fips);
    const values = {};
    for (const key of keys) {
      values[key] = {
        value: db.value(key, row.fips).value,
        percentile: db.percentile(key, row.fips),
      };
    }
    return {
      rank: i + 1,
      fips: row.fips,
      name: county.name,
      state: county.stateName,
      population: county.population,
      concernScore: Math.round(row.score * 10) / 10,
      sharedBy: shared.get(row.score),
      rankRange: [row.low, row.high],
      values,
    };
  });

  const leftOut = {
    missing: unranked.missing,
    excluded: unranked.excluded,
    byMeasure: unranked.inputs.map(x => ({ key: x.key, title: x.title, total: x.total })),
  };
  if (usePopulation) {
    leftOut.population = {
      min: minPopulation,
      below: inState.filter(c => c.population !== null && c.population < minPopulation).length,
      unknown: inState.filter(c => c.population === null).length,
    };
  }
  const small = results.some(r => r.population !== null && r.population < SMALL_COUNTY);
  const topCount = ranked.length ? shared.get(ranked[0].score) : 0;
  const topTie = topCount > 1 ? { count: topCount, concernScore: Math.round(ranked[0].score * 10) / 10 } : null;

  return {
    results,
    compared: ranked.length,
    total: countyIds.length,
    leftOut,
    topTie,
    cautions: cautionsFor(db, keys, { small, population: usePopulation, topTie: topCount }),
  };
}
