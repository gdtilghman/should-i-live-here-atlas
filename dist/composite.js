(function (root) {
  'use strict';
  const finite = Number.isFinite;
  const available = r => r?.status === 'available' && finite(r.value);
  const clamp = n => Math.max(0, Math.min(1, n));
  // A dataset may declare that its source's not-applicable status means no
  // exposure rather than no data. Only then does such a record score, and it
  // scores at the best end. It is never inferred, and every other
  // non-available status stays missing.
  const bestCase = (record, stats) => record?.status === 'not-applicable' && stats?.notApplicableBestCase === true && stats.count > 0;
  function quantile(values, p) {
    const index = (values.length - 1) * p, lo = Math.floor(index);
    return values[lo] + (values[Math.ceil(index)] - values[lo]) * (index - lo);
  }
  function scaleStats(dataset) {
    const values = Object.values(dataset.records || {}).filter(available).map(r => r.value).sort((a,b) => a-b);
    const reversed = dataset.direction === 'higher-better';
    const notApplicableBestCase = dataset.notApplicableMeans === 'best-case';
    if (!values.length) return { min: null, max: null, fence: null, reversed, count: 0, hasExtremes: false, notApplicableBestCase };
    const q1 = quantile(values,.25), q3 = quantile(values,.75), iqr = q3-q1;
    const fence = reversed ? q1-3*iqr : q3+3*iqr;
    const regular = iqr > 0 ? values.filter(v => reversed ? v >= fence : v <= fence) : values;
    return { min: reversed ? regular[0] : values[0], max: reversed ? values.at(-1) : regular.at(-1), fence,
      reversed, count: values.length, hasExtremes: regular.length < values.length, iqr, notApplicableBestCase };
  }
  function component(record, stats) {
    // 0 is the best end for either direction, because the flip is applied here.
    if (bestCase(record, stats)) return { value: 0, extreme: false };
    if (!available(record) || !stats.count) return { value: null, extreme: false };
    const value = stats.min === stats.max ? 50 : 100*clamp(stats.reversed
      ? (stats.max-record.value)/(stats.max-stats.min) : (record.value-stats.min)/(stats.max-stats.min));
    return { value, extreme: stats.hasExtremes && (stats.reversed ? record.value < stats.fence : record.value > stats.fence) };
  }
  function combine(countyIds, signals) {
    const seen = new Set();
    const selected = signals.filter(s => {
      if (!s?.key || seen.has(s.key)) throw new Error('Each selected signal must have a unique key.');
      seen.add(s.key);
      if (!finite(s.weight) || s.weight < 0) throw new Error('Weights must be finite and nonnegative.');
      if (s.threshold && (!['min','max'].includes(s.threshold.operator) || !finite(s.threshold.value))) throw new Error('Invalid threshold.');
      return s.weight > 0 || s.threshold;
    });
    const totalWeight = selected.reduce((sum,s) => sum+s.weight,0);
    const weights = Object.fromEntries(signals.map(s => [s.key,totalWeight ? s.weight/totalWeight : 0]));
    const prepared = selected.map(s => ({...s, stats:scaleStats(s.dataset)}));
    const records = {};
    for (const fips of countyIds) {
      let sum = 0;
      const missing = [], thresholdFailures = [], components = [];
      for (const s of prepared) {
        const record = s.dataset.records?.[fips];
        const measured = available(record), assumed = bestCase(record,s.stats), usable = measured || assumed;
        const scaled = component(record,s.stats), weight = weights[s.key];
        const contribution = usable ? scaled.value*weight : null;
        if (!usable) missing.push(s.dataset.title + ' — ' + (record?.status || 'unavailable').replace(/[-_]/g, ' '));
        else {
          sum += contribution;
          // No exposure lies beyond the favourable end of the raw scale, so it
          // passes a limit on the adverse side and fails one on the other.
          const favourableLimit = s.stats.reversed ? 'min' : 'max';
          if (s.threshold && (assumed ? s.threshold.operator !== favourableLimit
            : s.threshold.operator === 'max' ? record.value > s.threshold.value : record.value < s.threshold.value)) thresholdFailures.push(s.dataset.title);
        }
        components.push({ key:s.key, title:s.dataset.title, value:measured ? record.value : null,
          scaled:scaled.value, weight, contribution, status:measured ? 'available' : record?.status || 'unavailable',
          extreme:s.weight > 0 && scaled.extreme, unit:s.dataset.unit, period:s.dataset.period, sourceUrl:s.dataset.sourceUrl,
          sex:s.dataset.sex || '', confidenceLevel:s.dataset.confidenceLevel ?? null,
          low:record?.low ?? null, high:record?.high ?? null, moe:record?.moe ?? null,
          reason:assumed ? 'The source marks this county as having no exposure; scored as the best case, 0/100.' : record?.reason || '' });
      }
      // Failed hard limits take precedence; unknown inputs never count as passing.
      const status = thresholdFailures.length ? 'excluded' : !totalWeight || missing.length ? 'unavailable' : 'available';
      const reason = thresholdFailures.length ? 'Outside your limits: '+thresholdFailures.join(', ')
        : !totalWeight ? 'Choose at least one signal with a positive weight.'
        : missing.length ? 'Missing selected data: '+missing.join(', ') : '';
      records[fips] = { value:status === 'available' ? sum : null, status, reason,
        extreme:components.some(c => c.extreme), components, thresholdFailures };
    }
    const values = Object.values(records).filter(available).map(r => r.value);
    return { records, weights, stats:{ min:values.length ? Math.min(...values) : null, max:values.length ? Math.max(...values) : null,
      available:values.length, total:countyIds.length, excluded:Object.values(records).filter(r => r.status === 'excluded').length } };
  }

  // The score a county would get with one input's weight scaled by factor and
  // the weights renormalized. Shared by weightSensitivity and rank so the rank
  // ranges and the county detail can never disagree.
  function scenarioScore(components, key, factor) {
    let weightSum = 0, scoreSum = 0;
    for (const c of components) {
      const w = finite(c.weight) ? c.weight : 0;
      const w2 = c.key === key ? w * factor : w;
      weightSum += w2;
      if (w2 > 0) scoreSum += c.scaled * w2;
    }
    return scoreSum / weightSum;
  }

  // Orders the comparable counties from least to most of what the recipe
  // weighs against, so rank 1 has the lowest score. Only available records are
  // ranked; a missing or excluded county is never placed. Equal scores fall
  // back to FIPS order so the list is stable between renders.
  //
  // low and high are the best and worst rank the county takes when any one
  // positive weight moves by the fraction either way, others held, ranked
  // within the same set of counties. A wide range means the order is a close
  // call that the weights, not the data, are deciding.
  function rank(records, countyIds, fraction = 0.2) {
    if (!finite(fraction) || fraction <= 0 || fraction >= 1) throw new Error('Fraction must be a finite number between 0 and 1.');
    const byScore = (a, b) => a.score - b.score || (a.fips < b.fips ? -1 : a.fips > b.fips ? 1 : 0);
    const ranked = countyIds.filter(fips => records[fips]?.status === 'available' && finite(records[fips].value))
      .map(fips => ({ fips, score: records[fips].value, components: records[fips].components }))
      .sort(byScore);
    ranked.forEach((row, i) => { row.rank = row.low = row.high = i + 1; });
    const keys = [...new Set(ranked.flatMap(row => row.components.filter(c => c.weight > 0).map(c => c.key)))];
    for (const key of keys) for (const factor of [1 - fraction, 1 + fraction]) {
      ranked.map(row => ({ row, fips: row.fips, score: scenarioScore(row.components, key, factor) }))
        .sort(byScore)
        .forEach(({ row }, i) => { row.low = Math.min(row.low, i + 1); row.high = Math.max(row.high, i + 1); });
    }
    return ranked;
  }

  // Why the counties that were not ranked were left out, per positively
  // weighted input. One county can be missing several inputs, so the per-input
  // totals can sum to more than the number of counties.
  function unranked(records, countyIds) {
    const inputs = new Map();
    let missing = 0, excluded = 0;
    for (const fips of countyIds) {
      const record = records[fips];
      if (record?.status === 'available') continue;
      if (record?.status === 'excluded') { excluded++; continue; }
      missing++;
      for (const c of record?.components || []) {
        if (!(c.weight > 0) || c.status === 'available' || finite(c.scaled)) continue;
        const entry = inputs.get(c.key) || { key: c.key, title: c.title, total: 0, statuses: {} };
        entry.total++;
        entry.statuses[c.status] = (entry.statuses[c.status] || 0) + 1;
        inputs.set(c.key, entry);
      }
    }
    return { missing, excluded, inputs: [...inputs.values()].sort((a, b) => b.total - a.total) };
  }

  function weightSensitivity(record, fraction = 0.2) {
    if (!finite(fraction) || fraction <= 0 || fraction >= 1) throw new Error('Fraction must be a finite number between 0 and 1.');
    const inactive = { status: record?.status, baseline: null, min: null, max: null, scenarios: [] };
    if (!record || record.status !== 'available') return inactive;
    const components = record.components;
    if (!Array.isArray(components)) throw new Error('Malformed available record: missing components.');
    const baseline = record.value;
    if (!finite(baseline)) throw new Error('Malformed available record: non-finite value.');
    const keys = new Set();
    for (const c of components) {
      if (!c || typeof c !== 'object') throw new Error('Malformed available record: null or non-object component entry.');
      if (!c.key) throw new Error('Malformed available record: component missing key.');
      if (keys.has(c.key)) throw new Error('Malformed available record: duplicate component key ' + c.key + '.');
      keys.add(c.key);
      if (!finite(c.weight) || c.weight < 0) throw new Error('Malformed available record: non-finite or negative weight for ' + c.key + '.');
      if (c.weight > 0 && !finite(c.scaled)) throw new Error('Malformed available record: non-finite scaled value for ' + c.key + '.');
    }
    const active = components.filter(c => c.weight > 0);
    if (!active.length) throw new Error('Malformed available record: no positive component weights.');
    const scenarioValue = (key, factor) => {
      const value = scenarioScore(components, key, factor);
      if (!finite(value)) throw new Error("Malformed available record: non-finite scenario.");
      return value;
    };
    const scenarios = [];
    for (const c of active) for (const factor of [1 - fraction, 1 + fraction])
      scenarios.push({ key: c.key, factor, value: scenarioValue(c.key, factor) });
    const values = scenarios.map(s => s.value).concat(baseline);
    return { status: 'available', baseline, min: Math.min(...values), max: Math.max(...values), scenarios };
  }
  const api = {scaleStats,component,combine,weightSensitivity,rank,unranked};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.AtlasComposite = api;
})(typeof window !== 'undefined' ? window : globalThis);
