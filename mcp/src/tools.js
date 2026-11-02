import { CAUTIONS, cautionsFor, rankCounties } from './rank.js';
import { normalizeTerms } from './log.js';

export const TOOL_NAMES = [
  'list_measures',
  'find_measure',
  'get_county',
  'compare_counties',
  'rank_counties',
  'request_measure',
];

const SCORE_NOTE = 'concernScore runs from 0 to 100. Lower means less of what you asked to avoid. Rank 1 has the lowest score. sharedBy counts the compared counties with exactly the same score.';
const MISSING_NOTE_START = 'The atlas has no data for: ';
const MISSING_NOTE_END = '. The request was counted, so the owner can consider adding it. No personal data was stored.';

function labelFor(measure) {
  return measure.family === 'cancer'
    ? `${measure.title} · ${measure.sex || 'All residents'}`
    : measure.title;
}

function resolveCounty(db, text) {
  const matches = db.findCounties(text);

  if (matches.length === 0) {
    return { error: `No county matches "${text}". Use a 5-digit FIPS code or "Name, State".` };
  }

  if (matches.length > 1) {
    return {
      error: `More than one county matches "${text}". Pick one by FIPS.`,
      choices: matches.map(c => ({ fips: c.fips, name: c.name, state: c.stateName })),
    };
  }

  return matches[0];
}

function safe(fn) {
  return async (args) => {
    try {
      return await fn(args ?? {});
    } catch (err) {
      return { error: err instanceof Error ? err.message : String(err) };
    }
  };
}

async function listMeasures(db, args) {
  const measures = db.listMeasures(args.filter);
  return { count: measures.length, measures };
}

async function findMeasure(db, logger, args) {
  const found = db.findMeasures(args.terms || []);
  const keys = found.matches.flatMap(match => match.keys || []);
  const result = {
    matches: found.matches,
    not_available: found.not_available,
    cautions: cautionsFor(db, keys),
  };

  if (found.not_available.length > 0) {
    try {
      await logger.logMissing(found.not_available);
    } catch {
      // Logging failures never prevent an answer.
    }
    result.note = MISSING_NOTE_START + found.not_available.join(', ') + MISSING_NOTE_END;
  }

  return result;
}

async function getCounty(db, args) {
  const county = resolveCounty(db, args.county);
  if (county.error) return county;

  const values = db.measures.map(measure => {
    const key = measure.key;
    const v = db.value(key, county.fips);

    return {
      key,
      label: labelFor(measure),
      value: v.value,
      unit: measure.unit,
      period: measure.period,
      status: v.status,
      percentile: db.percentile(key, county.fips),
    };
  });

  return {
    county: { fips: county.fips, name: county.name, state: county.stateName, population: county.population },
    values,
    cautions: [CAUTIONS.county, CAUTIONS.site],
  };
}

async function compareCounties(db, args) {
  const { counties, measures } = args;

  if (!Array.isArray(counties) || counties.length < 2 || counties.length > 10) {
    return { error: 'Give 2 to 10 counties.' };
  }

  if (!Array.isArray(measures) || measures.length < 1 || measures.length > 10) {
    return { error: 'Give 1 to 10 measures.' };
  }

  const keys = measures;

  for (const key of keys) {
    if (db.measure(key) === null) return { error: `Unknown measure: ${key}` };
  }

  const resolved = [];
  for (const text of counties) {
    const county = resolveCounty(db, text);
    if (county.error) return county;
    resolved.push(county);
  }

  const rows = keys.map(key => {
    const measure = db.measure(key);
    // A list, not an object keyed by FIPS: JavaScript would put FIPS without
    // a leading zero first and lose the county order.
    const values = resolved.map(county => {
      const v = db.value(key, county.fips);
      return { fips: county.fips, value: v.value, status: v.status, percentile: db.percentile(key, county.fips) };
    });

    return {
      key,
      label: labelFor(measure),
      unit: measure.unit,
      period: measure.period,
      values,
    };
  });

  return {
    counties: resolved.map(county => ({
      fips: county.fips,
      name: county.name,
      state: county.stateName,
    })),
    rows,
    cautions: cautionsFor(db, keys),
  };
}

async function rank(db, args) {
  const result = rankCounties(db, args);
  const keys = args.measures.map(m => m.key);

  const measures = keys.map(key => {
    const measure = db.measure(key);
    return {
      key,
      label: labelFor(measure),
      unit: measure.unit,
      period: measure.period,
      direction: measure.direction,
      sourceUrl: measure.sourceUrl,
      citation: measure.citation,
      note: measure.note || measure.familyNote,
    };
  });

  return { ...result, measures, scoreNote: SCORE_NOTE };
}

async function requestMeasure(logger, args) {
  const clean = normalizeTerms([args.measure]);

  if (clean.length === 0) {
    return { error: 'Name the measure the atlas is missing.' };
  }

  try {
    await logger.logMissing(clean);
  } catch {
    // Counting is best effort.
  }

  return { recorded: true, measure: clean[0] };
}

export function createHandlers(db, logger) {
  return {
    list_measures: safe(args => listMeasures(db, args)),
    find_measure: safe(args => findMeasure(db, logger, args)),
    get_county: safe(args => getCounty(db, args)),
    compare_counties: safe(args => compareCounties(db, args)),
    rank_counties: safe(args => rank(db, args)),
    request_measure: safe(args => requestMeasure(logger, args)),
  };
}
