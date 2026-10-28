(() => {
  "use strict";

  const WIDTH = 1100;
  const HEIGHT = 650;
  const THEME_SETTINGS = {
    night: { duration: 780, inset: [105, 55, 105, 55], centerX: 560, contextOpacity: .16 },
    atlas: { duration: 650, inset: [72, 55, 92, 55], centerX: 550, contextOpacity: .13 },
    contour: { duration: 720, inset: [100, 54, 105, 54], centerX: 610, contextOpacity: .17 }
  };
  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  const elements = {
    body: document.body,
    family: document.querySelector("#data-family"),
    measure: document.querySelector("#measure-select"),
    measureControl: document.querySelector(".control-cluster--measure"),
    measureLabel: document.querySelector('label[for="measure-select"]'),
    sexControl: document.querySelector("#sex-control"),
    sex: document.querySelector("#sex-select"),
    cancerViewControl: document.querySelector("#cancer-view-control"),
    cancerView: document.querySelector("#cancer-view-select"),
    recipeBuilder: document.querySelector("#recipe-builder"),
    recipeCoverage: document.querySelector("#recipe-coverage"),
    recipeAdd: document.querySelector("#recipe-add-select"),
    recipeAddButton: document.querySelector("#recipe-add-button"),
    recipeSignals: document.querySelector("#recipe-signals"),
    overlapWarning: document.querySelector("#overlap-warning"),
    recipeSave: document.querySelector("#recipe-save"),
    recipeLoad: document.querySelector("#recipe-load"),
    recipeStatus: document.querySelector("#recipe-status"),
    sourceLoadStatus: document.querySelector("#source-load-status"),
    state: document.querySelector("#state-select"),
    county: document.querySelector("#county-select"),
    keyboardHint: document.querySelector("#keyboard-hint"),
    controls: document.querySelector(".controls-panel"),
    back: document.querySelector("#back-button"),
    reset: document.querySelector("#reset-button"),
    zoomControls: document.querySelector("#map-zoom-controls"),
    zoomIn: document.querySelector("#zoom-in"),
    zoomOut: document.querySelector("#zoom-out"),
    zoomReset: document.querySelector("#zoom-reset"),
    mapFrame: document.querySelector("#map-frame"),
    map: document.querySelector("#county-map"),
    context: document.querySelector(".context-layer"),
    focus: document.querySelector(".focus-layer"),
    message: document.querySelector("#map-message"),
    tooltip: document.querySelector("#map-tooltip"),
    heading: document.querySelector("#map-heading"),
    kicker: document.querySelector("#location-kicker"),
    coverage: document.querySelector("#coverage-pill"),
    legendTitle: document.querySelector("#legend-title"),
    legendMeta: document.querySelector("#legend-meta"),
    legendPeriod: document.querySelector("#legend-period"),
    legendRamp: document.querySelector(".legend-ramp"),
    legendTicks: document.querySelector("#legend-ticks"),
    legendOutlier: document.querySelector("#legend-outlier"),
    legendOutlierText: document.querySelector("#legend-outlier-text"),
    legendExcluded: document.querySelector("#legend-excluded"),
    legendMissingLabel: document.querySelector("#legend-missing-text"),
    legendNotDesignated: document.querySelector("#legend-not-designated"),
    legend: document.querySelector(".legend-block"),
    scaleExplanation: document.querySelector("#scale-explanation"),
    layerCaveat: document.querySelector("#layer-caveat"),
    factPanel: document.querySelector("#fact-panel"),
    factTitle: document.querySelector("#fact-title"),
    factEyebrow: document.querySelector("#fact-eyebrow"),
    factBody: document.querySelector("#fact-body"),
    factClose: document.querySelector("#close-fact"),
    sourceStatus: document.querySelector("#source-status"),
    sourceLink: document.querySelector("#source-link"),
    tableBody: document.querySelector("#county-table-body"),
    valueColumn: document.querySelector("#value-column"),
    ciColumn: document.querySelector("#ci-column"),
    interpretation: document.querySelector("#interpretation-copy"),
    methodDetail: document.querySelector("#method-detail"),
    dockTitle: document.querySelector("#data-dock-title"),
    dockNote: document.querySelector("#dock-note"),
    dockLocation: document.querySelector("#dock-location"),
    dockRange: document.querySelector("#dock-range"),
    announcer: document.querySelector("#announcer"),
    layerLoading: document.querySelector("#layer-loading"),
    rankingReport: document.querySelector("#ranking-report"),
    rankingTitle: document.querySelector("#ranking-title"),
    rankingFrame: document.querySelector("#ranking-frame"),
    rankingBody: document.querySelector("#ranking-body"),
    rankingKey: document.querySelector("#ranking-key"),
    rankingMore: document.querySelector("#ranking-more"),
    rankingMissingCount: document.querySelector("#ranking-missing-count"),
    rankingMissingBody: document.querySelector("#ranking-missing-body"),
    layerLoadingText: document.querySelector("#layer-loading-text")
  };

  const app = {
    geo: null,
    data: { cancer: null, disasters: null, community: null, hazards: null, healthcare: null, employment: null, broadband: null, places: null, air: null, wildfire: null, water: null, traffic: null, climate: null, storms: null, crime: null },
    family: "cancer",
    cancerId: "001",
    sexId: "0",
    cancerView: "incidence",
    disasterId: "declarations",
    selectedDatasetIds: { community: "", hazards: "", healthcare: "", employment: "", broadband: "", places: "", air: "", wildfire: "", water: "", traffic: "", climate: "", storms: "", crime: "" },
    recipe: [],
    compositeResult: null,
    compositeDataset: null,
    optionalErrors: {},
    defaultMissing: [],
    recipeMessage: "",
    stateFips: "",
    countyFips: "",
    theme: "night",
    projection: null,
    path: null,
    states: [],
    featuresByState: new Map(),
    featureByFips: new Map(),
    lastCountyTrigger: null,
    nationalZoom: { x: 0, y: 0, k: 1 },
    nationalZoomTarget: { x: 0, y: 0, k: 1 },
    statePan: { x: 0, y: 0, k: 1 },
    stateZoomTarget: { x: 0, y: 0, k: 1 },
    zoomAnimating: false,
    glide: null,
    stateBorders: null,
    panActive: false,
    mapDrag: null,
    mapPointers: new Map(),
    suppressMapClick: false,
    mapBackgroundPress: false
  };

  let placeOverlays = null;

  const desktopLegend = window.matchMedia("(min-width: 761px)");

  // Each look has its own five-stop county scale. The legend ramp shows the
  // same stops through the CSS variables in style.css.
  const COLOR_STOPS = {
    weather: ["#1d47c9", "#86aef2", "#f3f3ef", "#ffa04a", "#d2321c"],
    night: ["#1b55c9", "#74adde", "#eee8df", "#dd8a73", "#aa263b"]
  };
  const colorScales = Object.fromEntries(Object.entries(COLOR_STOPS).map(([look, stops]) => [look,
    d3.scaleLinear().domain([0, .25, .5, .75, 1]).range(stops).interpolate(d3.interpolateRgb).clamp(true)]));
  function colorInterpolator(share) {
    return colorScales[document.documentElement.dataset.skin === "weather" ? "weather" : "night"](share);
  }
  const scaleStatsCache = new WeakMap();

  // Layer records arrive one dataset at a time. The manifest carries every
  // dataset's metadata, so menus, units, periods and labels work before any
  // records exist. ensureDataset fetches the records the current view needs.
  const LAYER_PATH = "./data/layers/";
  const datasetLoads = new Map();

  function hasRecords(dataset) {
    return Boolean(dataset && dataset.records);
  }

  function ensureDataset(family, dataset) {
    if (!dataset) return Promise.resolve(null);
    if (hasRecords(dataset)) return Promise.resolve(dataset);
    const key = `${family}:${dataset.id}`;
    if (!datasetLoads.has(key)) {
      const pending = d3.json(LAYER_PATH + dataset.file).then(shard => {
        if (!shard || !shard.records || typeof shard.records !== "object") {
          throw new Error(`The layer file for ${key} contains no records.`);
        }
        // Mutate this object rather than replacing it. A replacement would
        // strand the scaleStats cache and any composite copy already pointing
        // at this dataset.
        dataset.records = shard.records;
        // The cache can already hold the empty stats computed before the
        // records arrived.
        scaleStatsCache.delete(dataset);
        return dataset;
      });
      // A failed fetch must not be remembered as done, or a retry could never
      // succeed.
      pending.catch(() => datasetLoads.delete(key));
      datasetLoads.set(key, pending);
    }
    return datasetLoads.get(key);
  }

  function datasetForKey(key) {
    const separator = String(key).indexOf(":");
    if (separator < 0) return null;
    const family = String(key).slice(0, separator);
    const id = String(key).slice(separator + 1);
    const dataset = (app.data[family]?.datasets || []).find(entry => entry.id === id);
    return dataset ? [family, dataset] : null;
  }

  // Every input of My priorities stays loaded, whichever family is shown,
  // because the composite is recomputed on reset, on save and on load.
  function pendingDatasetRefs() {
    const refs = app.recipe.map(item => datasetForKey(item.key)).filter(Boolean);
    if (!isCompositeView()) {
      const dataset = activeDataset();
      if (dataset) refs.push([app.family, dataset]);
    }
    return refs.filter(entry => !hasRecords(entry[1]));
  }

  // While records load, the map, legend and source note still describe the
  // previous layer. They are dimmed and a label names what is coming, so the
  // old colours cannot be read as the new layer. Most shards arrive in well
  // under this delay, so a fast load shows nothing and nothing flickers.
  const LOADING_DELAY_MS = 300;
  let loadingTimer = null;

  function loadingLabel() {
    if (isCompositeView()) return "your priorities";
    const dataset = activeDataset();
    if (!dataset) return "data";
    return app.family === "cancer" ? cancerTypeLabel(dataset) : (dataset.hazardType || dataset.title);
  }

  function setLayerLoading(active) {
    elements.coverage.setAttribute("aria-busy", active ? "true" : "false");
    clearTimeout(loadingTimer);
    if (!active) {
      document.body.classList.remove("is-layer-loading");
      elements.layerLoading.hidden = true;
      return;
    }
    // Already showing, and the selection changed again: name the new target now.
    if (!elements.layerLoading.hidden) elements.layerLoadingText.textContent = `Loading ${loadingLabel()}…`;
    loadingTimer = setTimeout(() => {
      elements.layerLoadingText.textContent = `Loading ${loadingLabel()}…`;
      elements.layerLoading.hidden = false;
      document.body.classList.add("is-layer-loading");
    }, LOADING_DELAY_MS);
  }

  // Set while a load failure is on screen, so a later success can take the
  // message down without clobbering the different message updateFamilyOptions
  // shows when a whole family is absent from the manifest.
  let layerErrorShown = false;

  function showLayerError(error) {
    console.error(error);
    setLayerLoading(false);
    layerErrorShown = true;
    elements.sourceLoadStatus.hidden = false;
    elements.sourceLoadStatus.textContent = "That measure did not load. Check your connection. Then choose that measure again.";
    announce("The site did not load that measure.");
  }

  function clearLayerError() {
    if (!layerErrorShown) return;
    layerErrorShown = false;
    // Hand the line back to its owner rather than blanking it, so a genuine
    // family failure is restored instead of erased.
    updateFamilyOptions();
  }

  // Each control that changes what is on screen goes through here. It loads the
  // records the new view needs, then runs the original render unchanged.
  //
  // The selection can change again while a load is in flight. When it does, the
  // earlier load finishes first and its render reads the CURRENT selection,
  // whose records have not arrived. Measured: the map painted all 3,107
  // counties as missing and the coverage read "0 of 3,107 available" under the
  // new layer's name, for as long as the second fetch took. So on arrival this
  // asks again what the selection now needs, and waits for that too. Each pass
  // loads at least one more dataset and the set is finite, so it terminates.
  function withPendingData(render) {
    const refs = pendingDatasetRefs();
    if (!refs.length) {
      render();
      return;
    }
    setLayerLoading(true);
    Promise.all(refs.map(entry => ensureDataset(entry[0], entry[1])))
      .then(() => {
        if (pendingDatasetRefs().length) {
          withPendingData(render);
          return;
        }
        setLayerLoading(false);
        clearLayerError();
        render();
      })
      .catch(showLayerError);
  }
  const OUTLIER_COLOR = "#7c3aed";
  // Families whose values are plain numbers rather than cancer rates.
  const GENERIC_FAMILIES = new Set(["community", "hazards", "healthcare", "climate", "places", "air", "wildfire", "water", "traffic", "storms", "crime"]);
  const RECIPE_STORAGE_KEY = "atlas-composite-recipe-v1";
  const RECIPE_VERSION = 1;
  const NORMALIZATION_POLICY = "national-minmax-3iqr-v1";
  const FAMILY_LABELS = {
    cancer: "Cancer incidence",
    disasters: "Natural disasters",
    community: "Housing & commute",
    hazards: "Modeled hazards",
    healthcare: "Primary care shortage",
    employment: "Unemployment",
    broadband: "Broadband",
    places: "Adult health",
    air: "Air quality",
    wildfire: "Wildfire",
    water: "Drinking water",
    traffic: "Traffic safety",
    climate: "Climate",
    storms: "Severe storms",
    crime: "Crime",
    composite: "My priorities"
  };

  function activeCollection() {
    if (app.family === "composite") {
      return app.compositeDataset ? { datasets: [app.compositeDataset], note: app.compositeDataset.note } : null;
    }
    return app.data[app.family];
  }

  function isCompositeView() {
    return app.family === "composite";
  }

  function datasetCancerId(dataset) {
    return String(dataset?.cancerId || dataset?.id || "");
  }

  function datasetSexId(dataset) {
    if (dataset?.sexId !== undefined && dataset?.sexId !== null) return String(dataset.sexId);
    const sex = String(dataset?.sex || "").toLowerCase();
    return sex.includes("female") ? "2" : sex.includes("male") ? "1" : "0";
  }

  function cancerTypeLabel(dataset) {
    return String(dataset?.cancerTitle || dataset?.title || "Cancer")
      .replace(/\s*\((female|male|both sexes)\)\s*$/i, "");
  }

  function activeDataset() {
    if (isCompositeView()) return app.compositeDataset;
    const collection = activeCollection();
    if (!collection) return null;
    if (app.family === "cancer") {
      return collection.datasets.find(dataset => datasetCancerId(dataset) === app.cancerId && datasetSexId(dataset) === app.sexId)
        || collection.datasets.find(dataset => datasetCancerId(dataset) === app.cancerId)
        || collection.datasets[0]
        || null;
    }
    const id = app.family === "disasters" ? app.disasterId : app.selectedDatasetIds[app.family];
    return collection.datasets.find(dataset => dataset.id === id) || collection.datasets[0] || null;
  }

  function sourceRecord(fips) {
    const dataset = activeDataset();
    return dataset?.records?.[fips] || null;
  }

  function isTrendView() {
    return app.family === "cancer" && app.cancerView === "trend";
  }

  function activeRecord(fips) {
    const record = sourceRecord(fips);
    return isTrendView() ? record?.trend || null : record;
  }

  function isAvailable(record) {
    return record?.status === "available" && Number.isFinite(record.value);
  }

  function valueFormat(value) {
    if (!Number.isFinite(value)) return "—";
    const hasFraction = Math.abs(value - Math.round(value)) > 0.00001;
    return new Intl.NumberFormat("en-US", {
      minimumFractionDigits: hasFraction ? 1 : 0,
      maximumFractionDigits: hasFraction ? 1 : 0
    }).format(value);
  }

  function genericValueFormat(value) {
    if (!Number.isFinite(value)) return "—";
    return new Intl.NumberFormat("en-US", { maximumSignificantDigits: 4 }).format(value);
  }

  function familyValueFormat(value, family = app.family) {
    return GENERIC_FAMILIES.has(family) ? genericValueFormat(value) : valueFormat(value);
  }

  function metricValueFormat(value) {
    if (!Number.isFinite(value)) return "—";
    if (isCompositeView()) return new Intl.NumberFormat("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(value);
    if (!isTrendView()) return familyValueFormat(value);
    return new Intl.NumberFormat("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(value);
  }

  function unitLabel(dataset) {
    if (isCompositeView()) return dataset?.unit || "concern score";
    if (isTrendView()) return "average change per year, in percent";
    return app.family === "cancer" ? `Age-adjusted ${dataset.unit}` : dataset.unit;
  }

  function displayPeriod(dataset) {
    if (isCompositeView()) return "Source periods vary";
    if (!isTrendView()) return dataset?.period || "Not stated";
    return dataset?.trendPeriod ? `Recent 5-year trend · ${dataset.trendPeriod}` : "Recent 5-year trend";
  }

  function metricTitle(dataset) {
    if (!dataset) return "Unavailable";
    if (isCompositeView()) return "My priorities: combined comparison";
    return isTrendView() ? `${cancerTypeLabel(dataset)} · Recent 5-year trend` : dataset.title;
  }

  function trendCategoryLabel(record) {
    const category = String(record?.category || "").toLowerCase();
    return { falling: "Falling", stable: "Stable", rising: "Rising" }[category] || "Uncategorized";
  }

  function thresholdFormat(value) {
    if (!Number.isFinite(value)) return "—";
    if (GENERIC_FAMILIES.has(app.family)) return genericValueFormat(value);
    return new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(value);
  }

  function scaleStats(dataset) {
    if (!dataset) return null;
    if (scaleStatsCache.has(dataset)) return scaleStatsCache.get(dataset);
    const values = Object.values(dataset.records || {})
      .filter(isAvailable)
      .map(record => record.value)
      .sort(d3.ascending);
    if (!values.length) {
      const empty = {
        availableCount: 0,
        actualMin: null,
        actualMax: null,
        q1: null,
        q3: null,
        iqr: null,
        fence: null,
        regularMin: null,
        regularMax: null,
        outlierCount: 0,
        outlierMin: null,
        outlierMax: null
      };
      scaleStatsCache.set(dataset, empty);
      return empty;
    }
    const q1 = d3.quantileSorted(values, .25);
    const q3 = d3.quantileSorted(values, .75);
    const iqr = Math.max(0, q3 - q1);
    const fence = q3 + 3 * iqr;
    const firstOutlier = iqr > 0 ? d3.bisectRight(values, fence) : values.length;
    const regularValues = values.slice(0, firstOutlier);
    const outlierValues = values.slice(firstOutlier);
    const stats = {
      availableCount: values.length,
      actualMin: values[0],
      actualMax: values[values.length - 1],
      q1,
      q3,
      iqr,
      fence,
      regularMin: regularValues[0] ?? null,
      regularMax: regularValues[regularValues.length - 1] ?? null,
      outlierCount: outlierValues.length,
      outlierMin: outlierValues[0] ?? null,
      outlierMax: outlierValues[outlierValues.length - 1] ?? null
    };
    scaleStatsCache.set(dataset, stats);
    return stats;
  }

  function isExtremeHigh(record, dataset = activeDataset()) {
    if (isTrendView() || isCompositeView()) return false;
    const stats = scaleStats(dataset);
    return isAvailable(record) && stats?.outlierCount > 0 && record.value > stats.fence;
  }

  function colorForRecord(record) {
    const dataset = activeDataset();
    if (isCompositeView() && record?.status === "excluded") return "url(#excluded-pattern)";
    // A real answer from the source, not missing data: no current designation.
    // It is not evidence of adequate access either, so it sits off the scale.
    if (!isCompositeView() && record?.status === "not_designated") return "url(#not-designated-pattern)";
    if (!dataset || !isAvailable(record)) return "url(#missing-pattern)";
    if (isCompositeView()) {
      const stats = app.compositeResult?.stats;
      if (!Number.isFinite(stats?.min) || !Number.isFinite(stats?.max)) return "url(#missing-pattern)";
      if (stats.min === stats.max) return colorInterpolator(.5);
      return colorInterpolator(d3.scaleLinear().domain([stats.min, stats.max]).range([0, 1]).clamp(true)(record.value));
    }
    if (isTrendView()) {
      return {
        falling: "#2563eb",
        stable: "#d8d5ce",
        rising: "#d13f52"
      }[String(record.category || "").toLowerCase()] || "url(#missing-pattern)";
    }
    const stats = scaleStats(dataset);
    if (isExtremeHigh(record, dataset)) return OUTLIER_COLOR;
    if (!Number.isFinite(stats?.regularMin) || !Number.isFinite(stats?.regularMax)) return "url(#missing-pattern)";
    if (stats.regularMin === stats.regularMax) return colorInterpolator(.5);
    const domain = d3.scaleLinear().domain([stats.regularMin, stats.regularMax]).range([0, 1]).clamp(true);
    return colorInterpolator(domain(record.value));
  }

  function statusLabel(record) {
    if (isAvailable(record)) return "Available";
    if (!record) return "No record";
    return {
      suppressed: "Suppressed by the source",
      policy: "Unavailable by source policy",
      unavailable: "Unavailable for this comparison",
      not_designated: "No primary care shortage area",
      excluded: "Excluded by your hard limit",
      not_available: "Unavailable",
      not_applicable: "Not applicable",
      not_designated: "Not designated a shortage area",
      "not-applicable": "Not applicable",
      insufficient_data: "Too little data",
      "insufficient-data": "Too little data",
      unmatched_geography: "Geography does not match",
      source_error: "Source error"
    }[record.status] || "Unavailable";
  }

  function statusExplanation(record) {
    if (record?.status === "not_designated") return "This county has no designated primary care shortage area. This does not prove that access to health care is good. The county gets no score.";
    if (record?.reason) return record.reason;
    if (!record) return "The selected source has no record for this county. The site never treats an unavailable value as zero.";
    if (record.status === "suppressed") return `The source suppressed this ${isTrendView() ? "trend" : "rate"}. The site did not estimate or infer a value.`;
    if (record.status === "policy") return "The source does not publish this county's value under its current reporting policy.";
    if (record.status === "unavailable") return "This county is unavailable for the selected comparison window.";
    if (record.status === "not_designated") return "HRSA lists no current primary care shortage designation for this county. This does not prove that access to care is good. A designation needs an application, and some areas that qualify have none.";
    return "The source does not provide a value for this county.";
  }

  function countyLabel(feature) {
    const { name, stateName } = feature.properties;
    const suffix = stateName === "Louisiana" ? "Parish" : "County";
    const alreadyQualified = /(county|parish|borough|municipality|census area|city)$/i.test(name);
    return `${name}${alreadyQualified ? "" : ` ${suffix}`}, ${stateName}`;
  }

  function selectedDatasetKey(family, dataset) {
    return `${family}:${dataset.id}`;
  }

  function compositeChoiceLabel(family, dataset) {
    const cohort = family === "cancer" ? ` · ${dataset.sex || "All residents"}` : "";
    const title = family === "cancer" ? cancerTypeLabel(dataset) : dataset.title;
    return `${FAMILY_LABELS[family]} · ${title}${cohort}`;
  }

  function allCompositeChoices() {
    const choices = new Map();
    ["cancer", "disasters", "community", "hazards", "healthcare", "employment", "broadband", "places", "air", "wildfire", "water", "traffic", "climate", "storms", "crime"].forEach(family => {
      (app.data[family]?.datasets || []).forEach(dataset => {
        const key = selectedDatasetKey(family, dataset);
        const sourceUrl = sourceUrlForFamilyDataset(family, app.data[family], dataset);
        const compositeDataset = family === "cancer"
          ? { ...dataset, title: `${cancerTypeLabel(dataset)} · ${dataset.sex || "All residents"}`, unit: `Age-adjusted ${dataset.unit}`, sourceUrl: dataset.sourceUrl || sourceUrl }
          : { ...dataset, sourceUrl: dataset.sourceUrl || sourceUrl };
        // The copy must read records from the live dataset. Records can arrive
        // after the copy is made, and a stale empty copy would score every
        // county as missing data while looking like working code.
        Object.defineProperty(compositeDataset, "records", {
          get: () => dataset.records,
          enumerable: true,
          configurable: true
        });
        choices.set(key, {
          key,
          family,
          label: compositeChoiceLabel(family, dataset),
          dataset: compositeDataset
        });
      });
    });
    return choices;
  }

  function initializeDefaultRecipe() {
    const defaults = [
      ["disasters:hazard-fire", 40],
      ["cancer:066", 30],
      ["disasters:hazard-flood", 20],
      ["cancer:047-male", 10]
    ];
    const choices = allCompositeChoices();
    app.defaultMissing = defaults.filter(([key]) => !choices.has(key)).map(([key]) => key);
    app.recipe = defaults
      .filter(([key]) => choices.has(key))
      .map(([key, weight]) => ({ key, weight, threshold: null }));
  }

  function populateMeasures() {
    const collection = activeCollection();
    elements.measure.replaceChildren();
    const cancerMode = app.family === "cancer";
    const compositeMode = isCompositeView();
    elements.sexControl.hidden = !cancerMode;
    elements.cancerViewControl.hidden = !cancerMode;
    elements.measureControl.hidden = compositeMode;
    elements.recipeBuilder.hidden = !compositeMode;
    if (compositeMode) {
      renderRecipeBuilder();
      return;
    }
    elements.measureLabel.textContent = cancerMode
      ? "Cancer type"
      : app.family === "disasters"
        ? "Hazard type"
        : app.family === "hazards"
          ? "Modeled hazard"
          : app.family === "healthcare"
            ? "Shortage measure"
            : app.family === "places"
              ? "Health measure"
              : app.family === "air"
                ? "Air measure"
                : app.family === "wildfire"
                ? "Wildfire measure"
                : app.family === "water"
                ? "Water measure"
                : app.family === "traffic"
                ? "Traffic measure"
                : app.family === "climate"
                ? "Climate measure"
                : app.family === "storms"
                ? "Storm measure"
                : app.family === "crime"
                ? "Crime measure"
                : "Measure";
    if (!collection?.datasets?.length) {
      elements.measure.append(new Option("Unavailable", ""));
      elements.measure.disabled = true;
      return;
    }
    if (cancerMode) {
      const cancerTypes = new Map();
      collection.datasets.forEach(dataset => {
        const id = datasetCancerId(dataset);
        if (!cancerTypes.has(id)) cancerTypes.set(id, cancerTypeLabel(dataset));
      });
      if (!cancerTypes.has(app.cancerId)) app.cancerId = cancerTypes.keys().next().value;
      cancerTypes.forEach((label, id) => elements.measure.append(new Option(label, id)));
      elements.measure.value = app.cancerId;
      populateSexes();
      elements.cancerView.value = app.cancerView;
    } else {
      const currentId = app.family === "disasters" ? app.disasterId : app.selectedDatasetIds[app.family];
      const selectedId = collection.datasets.some(dataset => dataset.id === currentId) ? currentId : collection.datasets[0].id;
      if (app.family === "disasters") app.disasterId = selectedId;
      else app.selectedDatasetIds[app.family] = selectedId;
      collection.datasets.forEach(dataset => elements.measure.append(new Option(dataset.hazardType || dataset.title, dataset.id)));
      elements.measure.value = selectedId;
    }
    elements.measure.disabled = false;
  }

  function populateSexes() {
    const datasets = (app.data.cancer?.datasets || [])
      .filter(dataset => datasetCancerId(dataset) === app.cancerId);
    const bySex = new Map();
    datasets.forEach(dataset => {
      const id = datasetSexId(dataset);
      if (!bySex.has(id)) bySex.set(id, dataset.sex || ({ "0": "Both sexes", "1": "Male", "2": "Female" }[id] || id));
    });
    const ordered = [...bySex.entries()].sort((a, b) => Number(a[0]) - Number(b[0]));
    if (!bySex.has(app.sexId)) app.sexId = bySex.has("0") ? "0" : ordered[0]?.[0] || "0";
    elements.sex.replaceChildren();
    ordered.forEach(([id, label]) => elements.sex.append(new Option(label, id)));
    elements.sex.value = app.sexId;
    elements.sex.disabled = ordered.length <= 1;
  }

  function usableThreshold(item) {
    return item?.threshold
      && ["min", "max"].includes(item.threshold.operator)
      && Number.isFinite(item.threshold.value)
      ? { operator: item.threshold.operator, value: item.threshold.value }
      : null;
  }

  function recomputeComposite() {
    if (!app.geo || !window.AtlasComposite) return;
    const choices = allCompositeChoices();
    const signals = app.recipe.map(item => {
      const choice = choices.get(item.key);
      return choice ? {
        key: item.key,
        dataset: choice.dataset,
        weight: Number.isFinite(item.weight) ? item.weight : 0,
        threshold: usableThreshold(item)
      } : null;
    }).filter(Boolean);
    app.compositeResult = window.AtlasComposite.combine(
      app.geo.features.map(feature => feature.properties.fips),
      signals
    );
    app.compositeDataset = {
      id: "my-priorities",
      title: "My priorities: combined comparison",
      unit: "concern score",
      period: "Source periods vary",
      records: app.compositeResult.records,
      min: app.compositeResult.stats.min,
      max: app.compositeResult.stats.max,
      note: "This is a transparent weighted comparison of selected measures. It is not a probability, a safety rating, or a claim that one measure causes another."
    };
  }

  function renderRecipeBuilder() {
    recomputeComposite();
    const choices = allCompositeChoices();
    const selected = new Set(app.recipe.map(item => item.key));
    elements.recipeAdd.replaceChildren();
    ["cancer", "disasters", "community", "hazards", "healthcare", "employment", "broadband", "places", "air", "wildfire", "water", "traffic", "climate", "storms", "crime"].forEach(family => {
      const available = [...choices.values()].filter(choice => choice.family === family && !selected.has(choice.key));
      if (!available.length) return;
      const group = document.createElement("optgroup");
      group.label = FAMILY_LABELS[family];
      available.forEach(choice => group.append(new Option(choice.label.replace(`${FAMILY_LABELS[family]} · `, ""), choice.key)));
      elements.recipeAdd.append(group);
    });
    elements.recipeAddButton.disabled = !elements.recipeAdd.options.length;
    elements.recipeSignals.replaceChildren();
    app.recipe.forEach((item, index) => {
      const choice = choices.get(item.key);
      if (!choice) return;
      const row = document.createElement("article");
      row.className = "recipe-signal";
      row.dataset.recipeKey = item.key;

      const head = document.createElement("div");
      head.className = "recipe-signal__head";
      const titleWrap = document.createElement("div");
      const family = document.createElement("span");
      family.textContent = FAMILY_LABELS[choice.family];
      const title = document.createElement("strong");
      title.textContent = choice.label.replace(`${FAMILY_LABELS[choice.family]} · `, "");
      titleWrap.append(family, title);
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "recipe-remove";
      remove.textContent = "Remove";
      remove.setAttribute("aria-label", `Remove ${choice.label} from My priorities`);
      remove.addEventListener("click", () => {
        const nextKey = app.recipe[index + 1]?.key || "";
        app.recipe.splice(index, 1);
        app.recipeMessage = `${choice.label} removed.`;
        renderRecipeBuilder();
        refreshCompositeView();
        const nextRow = [...elements.recipeSignals.querySelectorAll("[data-recipe-key]")]
          .find(candidate => candidate.dataset.recipeKey === nextKey);
        (nextRow?.querySelector(".recipe-remove") || elements.recipeAddButton).focus();
      });
      head.append(titleWrap, remove);

      const fields = document.createElement("div");
      fields.className = "recipe-fields";
      const weightId = `recipe-weight-${index}`;
      const weightLabel = document.createElement("label");
      weightLabel.className = "recipe-weight-label";
      weightLabel.htmlFor = weightId;
      weightLabel.textContent = "Weight (0–100)";
      const weight = document.createElement("input");
      weight.className = "recipe-weight-input";
      weight.id = weightId;
      weight.type = "number";
      weight.min = "0";
      weight.max = "100";
      weight.step = "1";
      weight.value = String(item.weight);
      weight.setAttribute("aria-label", `${choice.label} weight, from 0 to 100`);
      weight.addEventListener("change", () => {
        item.weight = clamp(Number.isFinite(weight.valueAsNumber) ? weight.valueAsNumber : 0, 0, 100);
        weight.value = String(item.weight);
        app.recipeMessage = "";
        refreshCompositeView();
      });
      const effective = document.createElement("span");
      effective.className = "effective-weight";
      effective.dataset.effectiveKey = item.key;

      const operatorId = `recipe-limit-${index}`;
      const operatorLabel = document.createElement("label");
      operatorLabel.className = "recipe-operator-label";
      operatorLabel.htmlFor = operatorId;
      operatorLabel.textContent = "Hard limit";
      const operator = document.createElement("select");
      operator.className = "recipe-operator";
      operator.id = operatorId;
      operator.append(
        new Option("No limit", ""),
        new Option("Exclude above", "max"),
        new Option("Exclude below", "min")
      );
      operator.value = item.threshold?.operator || "";
      operator.setAttribute("aria-label", `${choice.label} hard limit rule`);
      const limitId = `recipe-limit-value-${index}`;
      const limitLabel = document.createElement("label");
      limitLabel.className = "recipe-limit-label";
      limitLabel.htmlFor = limitId;
      limitLabel.textContent = `Hard limit in ${choice.dataset.unit || "source units"}`;
      const limit = document.createElement("input");
      limit.className = "recipe-limit-input";
      limit.id = limitId;
      limit.type = "number";
      limit.step = "any";
      limit.placeholder = "Value";
      limit.disabled = !operator.value;
      limit.setAttribute("aria-label", `${choice.label} hard limit value in ${choice.dataset.unit || "source units"}`);
      if (Number.isFinite(item.threshold?.value)) limit.value = String(item.threshold.value);
      operator.addEventListener("change", () => {
        limit.disabled = !operator.value;
        item.threshold = operator.value
          ? { operator: operator.value, value: Number.isFinite(limit.valueAsNumber) ? limit.valueAsNumber : null }
          : null;
        app.recipeMessage = "";
        updateLimitSummary();
        refreshCompositeView();
      });
      limit.addEventListener("change", () => {
        item.threshold = operator.value
          ? { operator: operator.value, value: Number.isFinite(limit.valueAsNumber) ? limit.valueAsNumber : null }
          : null;
        app.recipeMessage = "";
        updateLimitSummary();
        refreshCompositeView();
      });
      fields.append(weightLabel, weight, effective);
      const limitDetails = document.createElement("details");
      limitDetails.className = "recipe-limit-details";
      limitDetails.open = Boolean(item.threshold);
      const limitSummary = document.createElement("summary");
      const updateLimitSummary = () => {
        const activeLimit = usableThreshold(item);
        limitSummary.textContent = activeLimit
          ? `Hard limit: ${activeLimit.operator === "max" ? "≤" : "≥"} ${familyValueFormat(activeLimit.value, choice.family)}`
          : "Optional hard limit";
        limitSummary.setAttribute("aria-label", activeLimit
          ? `${choice.label} hard limit: ${activeLimit.operator === "max" ? "at or below" : "at or above"} ${familyValueFormat(activeLimit.value, choice.family)}`
          : `Optional hard limit for ${choice.label}`);
      };
      updateLimitSummary();
      const limitFields = document.createElement("div");
      limitFields.className = "recipe-limit-fields";
      limitFields.append(operatorLabel, operator, limitLabel, limit);
      limitDetails.append(limitSummary, limitFields);
      row.append(head, fields, limitDetails);
      elements.recipeSignals.append(row);
      if (choice.family === "places") {
        const caution = document.createElement("p");
        caution.className = "recipe-signal-caution";
        caution.textContent = "CDC model estimate. The CDC advises against ranking counties with PLACES data. Small differences may not be meaningful. This is especially true for asthma.";
        elements.recipeSignals.append(caution);
      }
    });
    if (!app.recipe.length) {
      const empty = document.createElement("p");
      empty.className = "recipe-empty";
      empty.textContent = "Add an input to build a comparison.";
      elements.recipeSignals.append(empty);
    }
    updateRecipeSummary();
  }

  function updateRecipeSummary() {
    const weights = app.compositeResult?.weights || {};
    elements.recipeSignals.querySelectorAll("[data-effective-key]").forEach(node => {
      node.textContent = `Effective ${((weights[node.dataset.effectiveKey] || 0) * 100).toFixed(1)}%`;
    });
    const stats = app.compositeResult?.stats;
    elements.recipeCoverage.textContent = stats ? `${stats.available.toLocaleString()} comparable` : "Unavailable";
    const invalid = app.recipe.filter(item => item.threshold && !usableThreshold(item));
    const warnings = overlapWarnings();
    elements.overlapWarning.hidden = !warnings.length;
    elements.overlapWarning.textContent = warnings.join(" ");
    const missingDefault = app.defaultMissing.length
      ? `These default inputs are unavailable: ${app.defaultMissing.join(", ")}. The site did not select a substitute.`
      : "";
    elements.recipeStatus.textContent = invalid.length
      ? "Enter a value for each selected hard limit. The site does not apply incomplete limits."
      : app.recipeMessage || missingDefault;
  }

  function overlapWarnings() {
    const choices = allCompositeChoices();
    const active = app.recipe.filter(item => item.weight > 0 || usableThreshold(item)).map(item => choices.get(item.key)).filter(Boolean);
    const cancers = active.filter(choice => choice.family === "cancer").map(choice => datasetCancerId(choice.dataset));
    const disasters = active.filter(choice => choice.family === "disasters").map(choice => choice.dataset.id);
    const warnings = [];
    if (cancers.includes("001") && cancers.some(id => id !== "001")) {
      warnings.push("Overlap notice: all-cancer and cancer-subtype rates describe related outcomes. Their weights can emphasize cancer twice.");
    }
    if (disasters.includes("declarations") && disasters.some(id => id !== "declarations")) {
      warnings.push("Overlap notice: total declarations include the selected hazard declarations. Their weights can emphasize the same records twice.");
    }
    return warnings;
  }

  function refreshCompositeView() {
    recomputeComposite();
    updateRecipeSummary();
    if (!isCompositeView() || !app.geo) return;
    populateCounties();
    repaintMap();
    renderAllText();
  }

  function addRecipeSignal() {
    const key = elements.recipeAdd.value;
    if (!key || app.recipe.some(item => item.key === key)) return;
    app.recipe.push({ key, weight: app.recipe.length ? 10 : 100, threshold: null });
    app.recipeMessage = "You added an input. The site adjusts the effective weights to total 100%.";
    withPendingData(() => {
      renderRecipeBuilder();
      refreshCompositeView();
    });
  }

  function recipeProvenance(choice) {
    const collection = app.data[choice.family] || {};
    const scale = window.AtlasComposite?.scaleStats(choice.dataset) || {};
    const sourceFiles = (choice.dataset.sourceFiles || collection.sourceFiles || [])
      .map(file => ({ url: String(file?.url || ""), sha256: String(file?.sha256 || "") }))
      .filter(file => file.url || file.sha256);
    return {
      title: choice.dataset.title || "",
      period: choice.dataset.period || "",
      sourceUrl: choice.dataset.sourceUrl || collection.sourceUrl || "",
      direction: choice.dataset.direction || "higher-worse",
      // Only where declared, so recipes without such an input stay unchanged,
      // and a recipe saved before the declaration reports that scores moved.
      ...(choice.dataset.notApplicableMeans ? { notApplicableMeans: choice.dataset.notApplicableMeans } : {}),
      scaleStats: {
        min: Number.isFinite(scale.min) ? scale.min : null,
        max: Number.isFinite(scale.max) ? scale.max : null,
        fence: Number.isFinite(scale.fence) ? scale.fence : null,
        availableCount: Number.isFinite(scale.count) ? scale.count : 0,
        hasExtremes: Boolean(scale.hasExtremes)
      },
      release: choice.dataset.release || collection.release || "",
      geographyVintage: choice.dataset.geographyVintage || collection.geographyVintage || "",
      sourceFiles
    };
  }

  function combinedDisplayBounds() {
    const stats = app.compositeResult?.stats || {};
    return {
      min: Number.isFinite(stats.min) ? stats.min : null,
      max: Number.isFinite(stats.max) ? stats.max : null
    };
  }

  function saveRecipe() {
    try {
      recomputeComposite();
      const choices = allCompositeChoices();
      const keys = new Set();
      const items = app.recipe.map(item => {
        if (!choices.has(item.key) || keys.has(item.key) || !Number.isFinite(item.weight) || item.weight < 0 || item.weight > 100) {
          throw new Error("Your priorities contain an input or a weight that is not valid.");
        }
        keys.add(item.key);
        if (item.threshold && !usableThreshold(item)) throw new Error("Complete each hard limit before saving.");
        return { key: item.key, weight: item.weight, threshold: usableThreshold(item), provenance: recipeProvenance(choices.get(item.key)) };
      });
      localStorage.setItem(RECIPE_STORAGE_KEY, JSON.stringify({
        version: RECIPE_VERSION,
        normalizationPolicy: NORMALIZATION_POLICY,
        displayBounds: combinedDisplayBounds(),
        items
      }));
      app.recipeMessage = "Priorities saved in this browser.";
    } catch (error) {
      app.recipeMessage = error?.message || "This browser could not save your priorities.";
    }
    updateRecipeSummary();
  }

  function loadRecipe() {
    try {
      const parsed = JSON.parse(localStorage.getItem(RECIPE_STORAGE_KEY) || "null");
      const choices = allCompositeChoices();
      if (!parsed || parsed.version !== RECIPE_VERSION || typeof parsed.normalizationPolicy !== "string" || !Array.isArray(parsed.items)) throw new Error("No saved priorities were found.");
      const savedBounds = parsed.displayBounds;
      const validBound = value => value === null || (typeof value === "number" && Number.isFinite(value));
      if (savedBounds !== undefined && (!savedBounds || typeof savedBounds !== "object" || Array.isArray(savedBounds) || !validBound(savedBounds.min) || !validBound(savedBounds.max))) {
        throw new Error("The saved priorities contain a display range that is not valid.");
      }
      const keys = new Set();
      const savedProvenance = new Map();
      let provenanceChanged = parsed.normalizationPolicy !== NORMALIZATION_POLICY || savedBounds === undefined;
      const items = parsed.items.map(item => {
        if (!item || typeof item.key !== "string" || !choices.has(item.key) || keys.has(item.key)) throw new Error("The saved priorities contain an unknown input or the same input twice.");
        if (typeof item.weight !== "number" || !Number.isFinite(item.weight) || item.weight < 0 || item.weight > 100) throw new Error("The saved priorities contain a weight that is not valid.");
        const threshold = item.threshold === null
          ? null
          : item.threshold && ["min", "max"].includes(item.threshold.operator) && Number.isFinite(item.threshold.value)
            ? { operator: item.threshold.operator, value: item.threshold.value }
            : null;
        if (item.threshold !== null && !threshold) throw new Error("The saved priorities contain a hard limit that is not valid.");
        if (!item.provenance || typeof item.provenance !== "object" || Array.isArray(item.provenance)) throw new Error("The saved priorities do not include source details.");
        savedProvenance.set(item.key, item.provenance);
        keys.add(item.key);
        return { key: item.key, weight: item.weight, threshold };
      });
      app.recipe = items;
      // A saved recipe can name inputs never displayed this visit, so their
      // records may not be loaded yet. Validation above needs metadata only.
      withPendingData(() => {
        // Compare provenance only once the records exist. Scale statistics read
        // from an unloaded dataset are null, which would report every saved
        // recipe as changed.
        const loadedChoices = allCompositeChoices();
        savedProvenance.forEach((saved, key) => {
          if (JSON.stringify(saved) !== JSON.stringify(recipeProvenance(loadedChoices.get(key)))) provenanceChanged = true;
        });
        recomputeComposite();
        const currentBounds = combinedDisplayBounds();
        if (savedBounds !== undefined && (savedBounds.min !== currentBounds.min || savedBounds.max !== currentBounds.max)) provenanceChanged = true;
        app.recipeMessage = provenanceChanged
          ? "Saved priorities loaded and calculated again with current data. Source details, value ranges or the weight rule changed since you saved them."
          : "Saved priorities loaded and calculated again. The source details did not change.";
        renderRecipeBuilder();
        refreshCompositeView();
      });
    } catch (error) {
      app.recipeMessage = error?.message || "The saved priorities could not load.";
      updateRecipeSummary();
    }
  }

  function buildGeographyIndexes() {
    app.featureByFips.clear();
    app.featuresByState.clear();
    for (const feature of app.geo.features) {
      const { fips, state } = feature.properties;
      app.featureByFips.set(fips, feature);
      if (!app.featuresByState.has(state)) app.featuresByState.set(state, []);
      app.featuresByState.get(state).push(feature);
    }
    app.states = [...app.featuresByState.entries()]
      .map(([fips, features]) => ({ fips, name: features[0].properties.stateName }))
      .sort((a, b) => a.name.localeCompare(b.name));
    app.stateBorders = buildStateBorders(app.geo.features);
  }

  function normalizeForD3(feature) {
    const geometry = feature.geometry;
    if (!geometry) return feature;
    const normalizePolygon = coordinates => {
      const polygon = { type: "Polygon", coordinates };
      return d3.geoArea(polygon) > Math.PI * 2
        ? coordinates.map(ring => [...ring].reverse())
        : coordinates;
    };
    let coordinates = geometry.coordinates;
    if (geometry.type === "Polygon") {
      coordinates = normalizePolygon(coordinates);
    } else if (geometry.type === "MultiPolygon") {
      coordinates = coordinates.map(normalizePolygon);
    }
    return { ...feature, geometry: { ...geometry, coordinates } };
  }

  function populateStates() {
    elements.state.replaceChildren(new Option("All states", ""));
    app.states.forEach(state => elements.state.append(new Option(state.name, state.fips)));
    elements.state.disabled = false;
  }

  function populateCounties() {
    elements.county.replaceChildren();
    if (!app.stateFips) {
      elements.county.append(new Option("Choose a state first", ""));
      elements.county.disabled = true;
      return;
    }
    elements.county.append(new Option("Select a county", ""));
    const features = [...(app.featuresByState.get(app.stateFips) || [])]
      .sort((a, b) => a.properties.name.localeCompare(b.properties.name));
    features.forEach(feature => elements.county.append(new Option(countyLabel(feature), feature.properties.fips)));
    elements.county.disabled = false;
    elements.county.value = app.countyFips;
  }

  function renderBaseMap() {
    app.projection = d3.geoAlbers().fitExtent([[30, 34], [WIDTH - 30, HEIGHT - 34]], app.geo);
    app.path = d3.geoPath(app.projection);
    d3.select(elements.context)
      .selectAll("path.county-shape")
      .data(app.geo.features, feature => feature.properties.fips)
      .join("path")
      .attr("class", "county-shape")
      .classed("is-selected", feature => feature.properties.fips === app.countyFips)
      .classed("has-extreme-component", feature => isCompositeView() && Boolean(activeRecord(feature.properties.fips)?.extreme))
      .classed("is-excluded", feature => isCompositeView() && activeRecord(feature.properties.fips)?.status === "excluded")
      .attr("d", app.path)
      .attr("fill", feature => colorForRecord(activeRecord(feature.properties.fips)))
      .attr("data-fips", feature => feature.properties.fips)
      .on("pointerenter", showTooltip)
      .on("pointermove", moveTooltip)
      .on("pointerleave", hideTooltip)
      .on("click", (_event, feature) => selectCountyFromMap(feature));
    drawStateBorders(d3.select(elements.context), app.stateBorders?.national);
    elements.map.classList.add("is-draggable");
  }

  // One unfilled path, drawn above the counties, so state shapes stay
  // readable on any data layer. Clicks pass through it to the counties.
  function drawStateBorders(layer, lines) {
    layer.selectAll("path.state-borders")
      .data(lines ? [lines] : [])
      .join("path")
      .attr("class", "state-borders")
      .attr("d", app.path)
      .raise();
  }

  // A county edge is a border when it belongs to only one county (the
  // national edge) or to two counties in different states. Neighboring
  // counties share exact quantized points, so their shared edges match.
  function buildStateBorders(features) {
    const pointKey = point => `${point[0]},${point[1]}`;
    const edges = new Map();
    for (const feature of features) {
      const state = feature.properties.state;
      const geometry = feature.geometry;
      const polygons = geometry.type === "Polygon" ? [geometry.coordinates] : geometry.coordinates;
      for (const ring of polygons.flat()) {
        for (let i = 1; i < ring.length; i++) {
          const a = ring[i - 1], b = ring[i];
          const ka = pointKey(a), kb = pointKey(b);
          if (ka === kb) continue;
          const key = ka < kb ? `${ka};${kb}` : `${kb};${ka}`;
          const edge = edges.get(key);
          if (edge) edge.states.push(state);
          else edges.set(key, { a, b, states: [state] });
        }
      }
    }
    const national = [];
    const perState = new Map();
    for (const edge of edges.values()) {
      if (edge.states.length > 1 && edge.states.every(state => state === edge.states[0])) continue;
      national.push(edge);
      for (const state of new Set(edge.states)) {
        if (!perState.has(state)) perState.set(state, []);
        perState.get(state).push(edge);
      }
    }
    const byState = new Map();
    perState.forEach((stateEdges, state) => byState.set(state, chainBorderEdges(stateEdges, pointKey)));
    return { national: chainBorderEdges(national, pointKey), byState };
  }

  // Join single edges end to end so the browser draws long lines, not
  // thousands of tiny ones.
  function chainBorderEdges(edges, pointKey) {
    const ends = new Map();
    edges.forEach((edge, index) => {
      for (const point of [edge.a, edge.b]) {
        const key = pointKey(point);
        if (!ends.has(key)) ends.set(key, []);
        ends.get(key).push(index);
      }
    });
    const used = new Uint8Array(edges.length);
    const extend = line => {
      for (;;) {
        const tip = line[line.length - 1];
        const next = ends.get(pointKey(tip)).find(index => !used[index]);
        if (next === undefined) return line;
        used[next] = 1;
        const edge = edges[next];
        line.push(pointKey(edge.a) === pointKey(tip) ? edge.b : edge.a);
      }
    };
    const lines = [];
    edges.forEach((edge, index) => {
      if (used[index]) return;
      used[index] = 1;
      const forward = extend([edge.a, edge.b]);
      const backward = extend([edge.a]).slice(1).reverse();
      lines.push(backward.concat(forward));
    });
    return { type: "MultiLineString", coordinates: lines };
  }

  function repaintMap() {
    placeOverlays?.refresh();
    d3.select(elements.context)
      .selectAll("path.county-shape")
      .attr("fill", feature => colorForRecord(activeRecord(feature.properties.fips)))
      .classed("is-selected", feature => feature.properties.fips === app.countyFips)
      .classed("has-extreme-component", feature => isCompositeView() && Boolean(activeRecord(feature.properties.fips)?.extreme))
      .classed("is-excluded", feature => isCompositeView() && activeRecord(feature.properties.fips)?.status === "excluded");
    d3.select(elements.focus)
      .selectAll("path.county-shape")
      .attr("fill", feature => colorForRecord(activeRecord(feature.properties.fips)))
      .classed("is-selected", feature => feature.properties.fips === app.countyFips)
      .classed("has-extreme-component", feature => isCompositeView() && Boolean(activeRecord(feature.properties.fips)?.extreme))
      .classed("is-excluded", feature => isCompositeView() && activeRecord(feature.properties.fips)?.status === "excluded");
  }

  function constrainNationalZoom(transform) {
    const rawK = Number.isFinite(transform?.k) ? transform.k : 1;
    const k = Math.max(1, Math.min(8, rawK));
    const bounds = app.path && app.geo ? app.path.bounds(app.geo) : [[0, 0], [WIDTH, HEIGHT]];
    const scaled = [[bounds[0][0] * k, bounds[0][1] * k], [bounds[1][0] * k, bounds[1][1] * k]];
    const limits = panLimitsForBounds(scaled);
    return {
      x: clamp(Number.isFinite(transform?.x) ? transform.x : 0, limits.minX, limits.maxX),
      y: clamp(Number.isFinite(transform?.y) ? transform.y : 0, limits.minY, limits.maxY),
      k
    };
  }

  function clamp(value, minimum, maximum) {
    return Math.max(minimum, Math.min(maximum, value));
  }

  function panLimitsForBounds(bounds) {
    const width = Math.max(1, bounds[1][0] - bounds[0][0]);
    const height = Math.max(1, bounds[1][1] - bounds[0][1]);
    const keepWidth = Math.min(width * .78, WIDTH * .72);
    const keepHeight = Math.min(height * .78, HEIGHT * .72);
    return {
      minX: keepWidth - bounds[1][0],
      maxX: WIDTH - keepWidth - bounds[0][0],
      minY: keepHeight - bounds[1][1],
      maxY: HEIGHT - keepHeight - bounds[0][1]
    };
  }

  function transformAroundPoint(base, nextScale, point) {
    const k = Math.max(1, Math.min(8, nextScale));
    const [px, py] = point;
    const mapX = (px - base.x) / base.k;
    const mapY = (py - base.y) / base.k;
    return constrainNationalZoom({
      x: px - mapX * k,
      y: py - mapY * k,
      k
    });
  }

  function setNationalZoomTransform(transform) {
    app.nationalZoom = transform;
    placeOverlays?.refresh();
    d3.select(elements.context).attr("transform", `translate(${transform.x},${transform.y}) scale(${transform.k})`);
    updateZoomControls();
  }

  function stopNationalZoom() {
    d3.select(elements.context).interrupt("national-zoom");
    stopGlide();
    app.nationalZoomTarget = { ...app.nationalZoom };
  }

  function animateNationalZoom(target, announceOnEnd = "") {
    const constrained = constrainNationalZoom(target);
    d3.select(elements.context).interrupt("national-zoom");
    app.nationalZoomTarget = constrained;
    hideTooltip();
    glideTo("national", constrained, announceOnEnd);
  }

  // Wheel steps and zoom buttons only move the target view. One frame loop
  // eases the shown view toward that target, so quick wheel steps blend into
  // one smooth motion instead of restarting a short animation each step.
  const GLIDE_TIME = 85;

  function glideTo(kind, target, announceOnEnd = "") {
    if (app.glide && app.glide.kind !== kind) stopGlide();
    const apply = kind === "national" ? setNationalZoomTransform : setStatePanTransform;
    if (prefersReducedMotion.matches) {
      stopGlide();
      apply(target);
      if (announceOnEnd) announce(announceOnEnd);
      return;
    }
    app.zoomAnimating = true;
    if (app.glide) {
      app.glide.target = target;
      app.glide.announceOnEnd = announceOnEnd;
      return;
    }
    app.glide = { kind, target, announceOnEnd, apply, last: performance.now(), frame: 0 };
    app.glide.frame = requestAnimationFrame(stepGlide);
  }

  function stepGlide(now) {
    const glide = app.glide;
    if (!glide) return;
    const elapsed = Math.min(64, Math.max(0, now - glide.last));
    glide.last = now;
    const view = glide.kind === "national" ? app.nationalZoom : app.statePan;
    const target = glide.target;
    const share = 1 - Math.exp(-elapsed / GLIDE_TIME);
    const next = {
      x: view.x + (target.x - view.x) * share,
      y: view.y + (target.y - view.y) * share,
      k: view.k + (target.k - view.k) * share
    };
    const settled = Math.abs(target.k - next.k) < .001
      && Math.abs(target.x - next.x) < .25
      && Math.abs(target.y - next.y) < .25;
    if (!settled) {
      glide.apply(next);
      glide.frame = requestAnimationFrame(stepGlide);
      return;
    }
    app.glide = null;
    app.zoomAnimating = false;
    glide.apply(target);
    if (glide.announceOnEnd) announce(glide.announceOnEnd);
  }

  function stopGlide() {
    if (app.glide) cancelAnimationFrame(app.glide.frame);
    app.glide = null;
    app.zoomAnimating = false;
  }

  function resetNationalZoom(animate = false, announceChange = false) {
    const message = announceChange ? "The site reset the national map zoom to fit the lower 48." : "";
    if (animate) {
      animateNationalZoom({ x: 0, y: 0, k: 1 }, message);
    } else {
      d3.select(elements.context).interrupt("national-zoom");
      stopGlide();
      app.nationalZoomTarget = { x: 0, y: 0, k: 1 };
      setNationalZoomTransform(app.nationalZoomTarget);
      if (message) announce(message);
    }
  }

  function zoomMapBy(factor) {
    cancelMapGesture();
    if (!app.geo) return;
    if (app.stateFips) {
      const desiredScale = app.stateZoomTarget.k * factor;
      const target = transformStateAroundPoint(app.stateZoomTarget, desiredScale, [WIDTH / 2, HEIGHT / 2]);
      const direction = target.k > app.stateZoomTarget.k ? "in" : "out";
      animateStateView(target, `The map zoomed ${stateName(app.stateFips)} ${direction} to ${target.k.toFixed(1)} times its fitted size.`);
      return;
    }
    const desiredScale = app.nationalZoomTarget.k * factor;
    const target = transformAroundPoint(app.nationalZoomTarget, desiredScale, [WIDTH / 2, HEIGHT / 2]);
    const direction = target.k > app.nationalZoomTarget.k ? "in" : "out";
    animateNationalZoom(target, `The national map zoomed ${direction} to ${target.k.toFixed(1)} times.`);
  }

  function handleMapWheel(event) {
    cancelMapGesture();
    if (!app.geo) return;
    event.preventDefault();
    hideTooltip();
    const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? HEIGHT : 1;
    const factor = Math.exp(-event.deltaY * unit * .0018);
    const pointer = d3.pointer(event, elements.map);
    if (app.stateFips) {
      const desiredScale = app.stateZoomTarget.k * factor;
      animateStateView(transformStateAroundPoint(app.stateZoomTarget, desiredScale, pointer));
      return;
    }
    const desiredScale = app.nationalZoomTarget.k * factor;
    animateNationalZoom(transformAroundPoint(app.nationalZoomTarget, desiredScale, pointer));
  }

  function handleMapKeydown(event) {
    const directions = {
      ArrowLeft: { x: 1, y: 0, label: "left" },
      ArrowRight: { x: -1, y: 0, label: "right" },
      ArrowUp: { x: 0, y: 1, label: "up" },
      ArrowDown: { x: 0, y: -1, label: "down" }
    };
    const direction = directions[event.key];
    if (!direction || !app.geo || event.altKey || event.ctrlKey || event.metaKey) return;
    cancelMapGesture();
    event.preventDefault();
    hideTooltip();
    const step = event.shiftKey ? 90 : 44;
    if (app.stateFips) {
      stopStateZoom();
      const target = constrainStatePan({
        x: app.statePan.x + direction.x * step,
        y: app.statePan.y + direction.y * step,
        k: app.statePan.k
      });
      app.stateZoomTarget = target;
      setStatePanTransform(target);
      announce(`The ${stateName(app.stateFips)} map panned ${direction.label}.`);
      return;
    }
    stopNationalZoom();
    const target = constrainNationalZoom({
      x: app.nationalZoom.x + direction.x * step,
      y: app.nationalZoom.y + direction.y * step,
      k: app.nationalZoom.k
    });
    app.nationalZoomTarget = target;
    setNationalZoomTransform(target);
    announce(`The national map panned ${direction.label}.`);
  }

  // Pointer positions stay in CSS pixels until d3.pointer converts them to
  // the SVG viewBox. Only the map owns touch input; the rest of the page scrolls.
  function mapGesturePoints() {
    return [...app.mapPointers.values()].slice(0, 2).map(event => d3.pointer(event, elements.map));
  }

  function rebaseMapGesture() {
    const points = mapGesturePoints();
    if (!points.length) return;
    const first = app.mapPointers.values().next().value;
    const midpoint = points.length === 2
      ? [(points[0][0] + points[1][0]) / 2, (points[0][1] + points[1][1]) / 2]
      : points[0];
    app.mapDrag = {
      stateFips: app.stateFips,
      startClientX: first.clientX,
      startClientY: first.clientY,
      startPoint: midpoint,
      span: points.length === 2 ? Math.hypot(points[1][0] - points[0][0], points[1][1] - points[0][1]) : 0,
      origin: { ...(app.stateFips ? app.statePan : app.nationalZoom) }
    };
  }

  function activateMapGesture() {
    app.panActive = true;
    app.suppressMapClick = true;
    app.mapBackgroundPress = false;
    hideTooltip();
    elements.map.classList.add("is-panning");
    // Leave a pending single-finger tap captured by its original county.
    // Capture on the SVG only once it becomes a drag or a pinch.
    for (const id of app.mapPointers.keys()) {
      if (!elements.map.hasPointerCapture(id)) elements.map.setPointerCapture(id);
    }
  }

  function cancelMapGesture() {
    const ids = [...app.mapPointers.keys()];
    if (ids.length) app.suppressMapClick = true;
    app.mapPointers.clear();
    app.mapBackgroundPress = false;
    app.mapDrag = null;
    app.panActive = false;
    elements.map.classList.remove("is-panning");
    // Clear bookkeeping first: releasing capture can emit lostpointercapture.
    for (const id of ids) {
      if (elements.map.hasPointerCapture(id)) elements.map.releasePointerCapture(id);
    }
    hideTooltip();
  }

  function beginMapDrag(event) {
    if (!app.geo || !["mouse", "touch"].includes(event.pointerType) || event.button !== 0) return;
    const first = app.mapPointers.values().next().value;
    if (first && (first.pointerType !== "touch" || event.pointerType !== "touch")) return;
    if (!first) {
      // A fresh press starts a legitimate tap; a delayed click without a new
      // press remains suppressed for as long as necessary after a gesture.
      app.suppressMapClick = false;
      // Only a press that starts on the bare SVG background can become a
      // click-away; county targets and controls keep their own behavior.
      app.mapBackgroundPress = Boolean(app.stateFips) && event.target === elements.map;
      if (app.stateFips) {
        stopStateZoom();
        // An interrupted state-entry fade must not leave counties invisible.
        d3.select(elements.focus).style("opacity", 1);
        setStatePanTransform(app.statePan);
      } else {
        stopNationalZoom();
      }
      hideTooltip();
    }
    app.mapPointers.set(event.pointerId, event);
    if (app.mapPointers.size <= 2) rebaseMapGesture();
    if (app.mapPointers.size > 1 || app.panActive) activateMapGesture();
  }

  function continueMapDrag(event) {
    const drag = app.mapDrag;
    if (!drag || !app.mapPointers.has(event.pointerId)) return;
    if (drag.stateFips !== app.stateFips) {
      cancelMapGesture();
      return;
    }
    app.mapPointers.set(event.pointerId, event);
    if (!app.panActive) {
      const distance = Math.hypot(event.clientX - drag.startClientX, event.clientY - drag.startClientY);
      if (distance < 6) return;
      activateMapGesture();
    }
    event.preventDefault();
    const points = mapGesturePoints();
    let point = points[0];
    let k = drag.origin.k;
    if (points.length === 2) {
      point = [(points[0][0] + points[1][0]) / 2, (points[0][1] + points[1][1]) / 2];
      const span = Math.hypot(points[1][0] - points[0][0], points[1][1] - points[0][1]);
      if (drag.span < .01) {
        rebaseMapGesture();
        return;
      }
      k = clamp(drag.origin.k * span / drag.span, 1, 8);
    }
    // Keep the initial midpoint's map location under the moving midpoint.
    const transform = {
      x: point[0] - (drag.startPoint[0] - drag.origin.x) * k / drag.origin.k,
      y: point[1] - (drag.startPoint[1] - drag.origin.y) * k / drag.origin.k,
      k
    };
    if (app.stateFips) {
      app.stateZoomTarget = constrainStatePan(transform);
      setStatePanTransform(app.stateZoomTarget);
    } else {
      app.nationalZoomTarget = constrainNationalZoom(transform);
      setNationalZoomTransform(app.nationalZoomTarget);
    }
  }

  function endMapDrag(event, cancelled = false) {
    if (!app.mapPointers.has(event.pointerId)) return;
    if (cancelled) {
      cancelMapGesture();
      return;
    }
    app.mapPointers.delete(event.pointerId);
    if (elements.map.hasPointerCapture(event.pointerId)) elements.map.releasePointerCapture(event.pointerId);
    if (app.mapPointers.size) {
      // Rebase when either pinch finger lifts (or a third finger replaces it).
      rebaseMapGesture();
    } else {
      app.mapDrag = null;
      app.panActive = false;
      elements.map.classList.remove("is-panning");
      hideTooltip();
    }
  }

  function suppressClickAfterDrag(event) {
    // Keyboard/assistive activation has no pointer press and should still work.
    if ((!app.suppressMapClick && !app.panActive) || event.detail === 0) return;
    event.preventDefault();
    event.stopImmediatePropagation();
  }

  // A deliberate press and click on the empty SVG background leaves the
  // focused state for the fitted national view without touching the dataset.
  function handleMapBackgroundClick(event) {
    const eligible = app.mapBackgroundPress;
    app.mapBackgroundPress = false;
    if (!eligible || event.target !== elements.map || !app.stateFips) return;
    if (app.suppressMapClick || app.panActive || app.mapPointers.size) return;
    setState("", false);
    announce("The map now shows the national county view.");
  }

  function fitCurrentMap() {
    cancelMapGesture();
    if (app.stateFips) {
      resetStatePan(true, true);
    } else {
      resetNationalZoom(true, true);
    }
  }

  // The legend always sits under the map. The recipe builder joins the
  // controls on desktop and follows the legend on phones.
  function placeLegend() {
    elements.mapFrame.insertAdjacentElement("afterend", elements.legend);
    if (desktopLegend.matches) {
      elements.controls.append(elements.recipeBuilder);
    } else {
      elements.legend.insertAdjacentElement("afterend", elements.recipeBuilder);
    }
    requestAnimationFrame(thinLegendTicks);
  }

  // Hide middle tick labels that would overlap a neighbour. The end labels stay.
  function thinLegendTicks() {
    const ticks = [...elements.legendTicks.children];
    ticks.forEach(tick => tick.classList.remove("is-crowded"));
    if (ticks.length < 3) return;
    const last = ticks[ticks.length - 1].getBoundingClientRect();
    let previous = ticks[0].getBoundingClientRect();
    for (const tick of ticks.slice(1, -1)) {
      const box = tick.getBoundingClientRect();
      if (box.left < previous.right + 12 || box.right > last.left - 12) {
        tick.classList.add("is-crowded");
      } else {
        previous = box;
      }
    }
  }

  function updateZoomControls() {
    const ready = Boolean(app.geo);
    const stateFocused = Boolean(app.stateFips);
    const nationalAtFit = Math.abs(app.nationalZoomTarget.k - 1) < .001
      && Math.abs(app.nationalZoomTarget.x) < .5
      && Math.abs(app.nationalZoomTarget.y) < .5;
    const stateAtFit = Math.abs(app.stateZoomTarget.k - 1) < .001
      && Math.abs(app.stateZoomTarget.x) < .5
      && Math.abs(app.stateZoomTarget.y) < .5;
    elements.zoomControls.hidden = !ready;
    elements.zoomIn.hidden = false;
    elements.zoomOut.hidden = false;
    elements.zoomIn.disabled = !ready || (stateFocused ? app.stateZoomTarget.k >= 7.999 : app.nationalZoomTarget.k >= 7.999);
    elements.zoomOut.disabled = !ready || (stateFocused ? app.stateZoomTarget.k <= 1.001 : app.nationalZoomTarget.k <= 1.001);
    elements.zoomReset.disabled = !ready || (stateFocused ? stateAtFit : nationalAtFit);
    elements.zoomIn.setAttribute("aria-label", stateFocused ? "Zoom in on the focused state" : "Zoom in on the national map");
    elements.zoomOut.setAttribute("aria-label", stateFocused ? "Zoom out on the focused state" : "Zoom out on the national map");
    elements.zoomReset.setAttribute("aria-label", stateFocused ? "Fit the focused state in the map" : "Reset national map zoom and pan");
  }

  function focusBaseTransform(stateFips) {
    const features = app.featuresByState.get(stateFips) || [];
    if (!features.length) return { x: 0, y: 0, k: 1, bounds: [[0, 0], [WIDTH, HEIGHT]] };
    const collection = { type: "FeatureCollection", features };
    const [[x0, y0], [x1, y1]] = app.path.bounds(collection);
    const settings = THEME_SETTINGS[app.theme];
    const [left, top, right, bottom] = settings.inset;
    const availableW = WIDTH - left - right;
    const availableH = HEIGHT - top - bottom;
    const scale = Math.max(1, .9 / Math.max((x1 - x0) / availableW, (y1 - y0) / availableH));
    const cx = (x0 + x1) / 2;
    const cy = (y0 + y1) / 2;
    const targetY = top + availableH / 2;
    return {
      x: settings.centerX - cx * scale,
      y: targetY - cy * scale,
      k: scale,
      bounds: [[x0, y0], [x1, y1]]
    };
  }

  function constrainStatePan(pan) {
    if (!app.stateFips || !app.path) return { x: 0, y: 0, k: 1 };
    const base = focusBaseTransform(app.stateFips);
    const baselineBounds = [
      [base.x + base.bounds[0][0] * base.k, base.y + base.bounds[0][1] * base.k],
      [base.x + base.bounds[1][0] * base.k, base.y + base.bounds[1][1] * base.k]
    ];
    const k = clamp(Number.isFinite(pan?.k) ? pan.k : 1, 1, 8);
    const bounds = [
      [baselineBounds[0][0] * k, baselineBounds[0][1] * k],
      [baselineBounds[1][0] * k, baselineBounds[1][1] * k]
    ];
    const limits = panLimitsForBounds(bounds);
    return {
      x: clamp(Number.isFinite(pan?.x) ? pan.x : 0, limits.minX, limits.maxX),
      y: clamp(Number.isFinite(pan?.y) ? pan.y : 0, limits.minY, limits.maxY),
      k
    };
  }

  function focusTransform(stateFips, pan = app.statePan) {
    const base = focusBaseTransform(stateFips);
    const bounded = constrainStatePan(pan);
    return `translate(${bounded.x},${bounded.y}) scale(${bounded.k}) translate(${base.x},${base.y}) scale(${base.k})`;
  }

  function setStatePanTransform(pan) {
    app.statePan = constrainStatePan(pan);
    placeOverlays?.transition(false);
    d3.select(elements.focus).attr("transform", focusTransform(app.stateFips, app.statePan));
    updateZoomControls();
  }

  function transformStateAroundPoint(view, nextScale, point) {
    const k = clamp(nextScale, 1, 8);
    const [px, py] = point;
    const mapX = (px - view.x) / view.k;
    const mapY = (py - view.y) / view.k;
    return constrainStatePan({
      x: px - mapX * k,
      y: py - mapY * k,
      k
    });
  }

  function stopStateZoom() {
    d3.select(elements.focus).interrupt().interrupt("state-zoom");
    stopGlide();
    app.stateZoomTarget = { ...app.statePan };
  }

  function animateStateView(target, announceOnEnd = "") {
    if (!app.stateFips) return;
    const constrained = constrainStatePan(target);
    d3.select(elements.focus).interrupt().interrupt("state-zoom");
    app.stateZoomTarget = constrained;
    hideTooltip();
    glideTo("state", constrained, announceOnEnd);
  }

  function resetStatePan(animate = false, announceChange = false) {
    if (!app.stateFips) {
      app.statePan = { x: 0, y: 0, k: 1 };
      app.stateZoomTarget = { x: 0, y: 0, k: 1 };
      updateZoomControls();
      return;
    }
    const message = announceChange ? `The map recentered ${stateName(app.stateFips)}.` : "";
    if (animate) {
      animateStateView({ x: 0, y: 0, k: 1 }, message);
    } else {
      stopStateZoom();
      app.stateZoomTarget = { x: 0, y: 0, k: 1 };
      setStatePanTransform(app.stateZoomTarget);
      if (message) announce(message);
    }
  }

  function renderFocusedState(animate = true) {
    placeOverlays?.transition(Boolean(app.stateFips));
    placeOverlays?.changed();
    cancelMapGesture();
    const focus = d3.select(elements.focus).interrupt().interrupt("state-zoom");
    stopGlide();
    if (!app.stateFips) {
      focus.classed("is-active", false).attr("aria-hidden", "true").selectAll("path").remove();
      d3.select(elements.context).interrupt().classed("is-dimmed", false).transition().duration(reducedDuration(240)).style("opacity", 1);
      return;
    }

    const features = app.featuresByState.get(app.stateFips) || [];
    focus
      .attr("aria-hidden", null)
      .attr("transform", "translate(0,0) scale(1)")
      .style("opacity", 0)
      .classed("is-active", true)
      .selectAll("path.county-shape")
      .data(features, feature => feature.properties.fips)
      .join("path")
      .attr("class", "county-shape")
      .classed("is-selected", feature => feature.properties.fips === app.countyFips)
      .classed("has-extreme-component", feature => isCompositeView() && Boolean(activeRecord(feature.properties.fips)?.extreme))
      .classed("is-excluded", feature => isCompositeView() && activeRecord(feature.properties.fips)?.status === "excluded")
      .attr("d", app.path)
      .attr("fill", feature => colorForRecord(activeRecord(feature.properties.fips)))
      .attr("data-fips", feature => feature.properties.fips)
      .on("pointerenter", showTooltip)
      .on("pointermove", moveTooltip)
      .on("pointerleave", hideTooltip)
      .on("click", (_event, feature) => selectCounty(feature.properties.fips, elements.county));
    drawStateBorders(focus, app.stateBorders?.byState.get(app.stateFips));

    d3.select(elements.context)
      .interrupt()
      .style("opacity", 1)
      .classed("is-dimmed", true)
      .transition()
      .duration(reducedDuration(220))
      .style("opacity", THEME_SETTINGS[app.theme].contextOpacity);

    const duration = animate ? reducedDuration(THEME_SETTINGS[app.theme].duration) : 0;
    focus
      .transition()
      .duration(duration)
      .ease(d3.easeCubicInOut)
      .style("opacity", 1)
      .attr("transform", focusTransform(app.stateFips))
      .on("end", () => { placeOverlays?.transition(false); announce(`The map focused ${stateName(app.stateFips)}. The full lower 48 remains visible in the background.`); });
  }

  function reducedDuration(duration) {
    return prefersReducedMotion.matches ? 0 : duration;
  }

  function stateName(fips) {
    return app.states.find(state => state.fips === fips)?.name || "Selected state";
  }

  function showTooltip(event, feature) {
    if (app.zoomAnimating || app.panActive) {
      hideTooltip();
      return;
    }
    const record = activeRecord(feature.properties.fips);
    const dataset = activeDataset();
    elements.tooltip.replaceChildren();
    const strong = document.createElement("strong");
    strong.textContent = countyLabel(feature);
    const detail = document.createElement("span");
    detail.textContent = isAvailable(record)
      ? `${metricValueFormat(record.value)} ${unitLabel(dataset)}${isCompositeView() && record.extreme ? " · One input has an extreme value" : isTrendView() ? ` · ${trendCategoryLabel(record)}` : isExtremeHigh(record, dataset) ? " · Extreme high value, shown in purple" : ""}`
      : app.family === "healthcare" && record?.status === "not_designated" ? statusExplanation(record) : statusLabel(record);
    elements.tooltip.append(strong, detail);
    elements.tooltip.hidden = false;
    moveTooltip(event);
  }

  function moveTooltip(event) {
    if (app.zoomAnimating || app.panActive) {
      hideTooltip();
      return;
    }
    const x = Math.min(window.innerWidth - 255, event.clientX + 14);
    const y = Math.min(window.innerHeight - 90, event.clientY + 14);
    elements.tooltip.style.left = `${Math.max(8, x)}px`;
    elements.tooltip.style.top = `${Math.max(8, y)}px`;
  }

  function hideTooltip() {
    elements.tooltip.hidden = true;
  }

  function selectCountyFromMap(feature) {
    const nextState = feature.properties.state;
    const stateChanged = nextState !== app.stateFips;
    if (stateChanged) setState(nextState, true);
    selectCounty(feature.properties.fips, elements.county);
  }

  function setState(fips, animate = true) {
    cancelMapGesture();
    hideTooltip();
    resetNationalZoom(false);
    if (fips !== app.stateFips) {
      stopStateZoom();
      app.statePan = { x: 0, y: 0, k: 1 };
      app.stateZoomTarget = { x: 0, y: 0, k: 1 };
    }
    app.stateFips = fips;
    app.countyFips = "";
    elements.state.value = fips;
    populateCounties();
    renderFocusedState(animate);
    renderAllText();
    repaintMap();
  }

  function selectCounty(fips, trigger) {
    if (!fips) {
      clearCounty(false);
      return;
    }
    const feature = app.featureByFips.get(fips);
    if (!feature) return;
    if (feature.properties.state !== app.stateFips) setState(feature.properties.state, true);
    app.countyFips = fips;
    app.lastCountyTrigger = trigger || elements.county;
    elements.county.value = fips;
    renderFact();
    repaintMap();
    updateNavigationText();
    announce(factAnnouncement(feature, activeRecord(fips)));
    if (window.innerWidth <= 760 && trigger?.classList?.contains("table-action")) {
      elements.factPanel.scrollIntoView({ behavior: prefersReducedMotion.matches ? "auto" : "smooth", block: "start" });
    }
  }

  function clearCounty(restoreFocus = false) {
    app.countyFips = "";
    elements.county.value = "";
    renderFact();
    repaintMap();
    updateNavigationText();
    if (restoreFocus && app.lastCountyTrigger) app.lastCountyTrigger.focus();
  }

  function factAnnouncement(feature, record) {
    const dataset = activeDataset();
    if (isCompositeView()) {
      return isAvailable(record)
        ? `${countyLabel(feature)}: concern score ${metricValueFormat(record.value)}, lower is better.${record.extreme ? " One or more inputs have extreme values." : ""}`
        : `${countyLabel(feature)}: ${statusLabel(record)}. ${statusExplanation(record)}`;
    }
    return isAvailable(record)
      ? `${countyLabel(feature)}: ${metricValueFormat(record.value)} ${unitLabel(dataset)}, ${displayPeriod(dataset)}.${isTrendView() ? ` ${trendCategoryLabel(record)} trend.` : isExtremeHigh(record, dataset) ? " Extreme high value, shown in purple." : ""}`
      : `${countyLabel(feature)}: ${statusLabel(record)}. ${statusExplanation(record)}`;
  }

  // Ranked view of My priorities. rank() in composite.js does the ordering;
  // this only presents it. Rank 1 is the least of what the recipe weighs
  // against, and only counties with every input can be placed.
  const RANKING_PANEL_SIZE = 5;
  const RANKING_PAGE = 25;
  const RANKING_COLORS = ["#e07a5f", "#81b29a", "#6fa8dc", "#c9a0dc", "#f2cc8f", "#8ecae6", "#b5838d", "#90be6d"];
  let rankingCache = { result: null, scope: null, ranked: [], tally: null, limit: RANKING_PAGE };
  const rankingOpen = new Set();

  function rankingScope() {
    return app.stateFips ? (app.featuresByState.get(app.stateFips) || []) : app.geo.features;
  }

  function currentRanking() {
    const result = app.compositeResult;
    if (rankingCache.result !== result || rankingCache.scope !== app.stateFips) {
      const ids = rankingScope().map(feature => feature.properties.fips);
      rankingCache = {
        result, scope: app.stateFips, limit: RANKING_PAGE,
        ranked: result ? window.AtlasComposite.rank(result.records, ids) : [],
        tally: result ? window.AtlasComposite.unranked(result.records, ids) : null
      };
    }
    return rankingCache;
  }

  // A short name for an input, for one-line county summaries.
  function shortInputLabel(key) {
    const found = datasetForKey(key);
    if (!found) return key;
    const [family, dataset] = found;
    if (family === "cancer") return cancerTypeLabel(dataset).replace("Lung & Bronchus", "Lung");
    if (family === "disasters") return dataset.title.replace(/ declarations$/i, "");
    if (family === "hazards") return dataset.title.replace(/ modeled.*$/i, "");
    if (family === "healthcare") return "Primary care shortage";
    if (family === "places") return dataset.shortLabel || dataset.title;
    if (family === "air") return "PM2.5";
    if (family === "wildfire") return dataset.id === "risk-to-homes" ? "Wildfire risk" : "Wildfire likelihood";
    if (family === "water") return "Water violations";
    if (family === "traffic") return "Traffic deaths";
    if (family === "climate") return "Days at 95°F+";
    if (family === "storms") return dataset.title.replace(/ reports$/, "");
    if (family === "crime") return dataset.title;
    return dataset.title;
  }

  function activeInputs() {
    return app.recipe.filter(item => item.weight > 0).map((item, index) => {
      const found = datasetForKey(item.key);
      return { key: item.key, family: found?.[0], dataset: found?.[1], label: shortInputLabel(item.key), color: RANKING_COLORS[index % RANKING_COLORS.length] };
    });
  }

  function componentValue(row, key) {
    return row.components.find(component => component.key === key)?.value;
  }

  function inputValueText(input, value) {
    return Number.isFinite(value) ? familyValueFormat(value, input.family) : "no exposure";
  }

  // Inputs whose value is identical across the shown counties are stated once.
  function sharedInputs(rows, inputs) {
    if (rows.length < 2) return [];
    return inputs.filter(input => {
      const first = componentValue(rows[0], input.key);
      return rows.every(row => componentValue(row, input.key) === first);
    });
  }

  function sharedSentence(rows, shared) {
    // Zero declarations over one period read as one phrase: "no fire or flood
    // disasters declared (2000–2025)".
    const none = shared.filter(input => input.family === "disasters" && componentValue(rows[0], input.key) === 0);
    const periods = new Set(none.map(input => input.dataset.period));
    const parts = [];
    if (none.length && periods.size === 1) {
      const names = none.map(input => input.label.toLowerCase());
      parts.push(`no ${names.length > 1 ? `${names.slice(0, -1).join(", ")} or ${names.at(-1)}` : names[0]} disasters declared in ${[...periods][0]}`);
    }
    shared.filter(input => !(periods.size === 1 && none.includes(input))).forEach(input => {
      const value = componentValue(rows[0], input.key);
      parts.push(input.family === "disasters" && value === 0
        ? `no ${input.label.toLowerCase()} disasters declared in ${input.dataset.period}`
        : `${input.label} ${inputValueText(input, value)}`);
    });
    const list = parts.length > 1 ? `${parts.slice(0, -1).join(", ")} and ${parts.at(-1)}` : parts[0];
    return `All ${rows.length} had ${list}. The other inputs decide the order.`;
  }

  function directionSentence(inputs) {
    const better = inputs.filter(input => input.dataset?.direction === "higher-better").map(input => input.label);
    return better.length
      ? `Lower values are better. Higher values are better for ${better.join(" and ")}.`
      : "For every input, lower values are better.";
  }

  function unitSentence(inputs) {
    const byUnit = new Map();
    inputs.forEach(input => {
      const unit = input.family === "cancer" ? `new cases per 100,000 ${input.dataset.sex === "Male" ? "men" : input.dataset.sex === "Female" ? "women" : "people"} a year` : input.dataset?.unit || "";
      byUnit.set(unit, [...(byUnit.get(unit) || []), input.label]);
    });
    return [...byUnit].map(([unit, labels]) => `${labels.join(" and ")}: ${unit}`).join(". ") + ".";
  }

  function closeCallText(row, rows) {
    if (row.low === row.high) return "";
    const others = rows.filter(other => other !== row && other.low <= row.high && other.high >= row.low).map(other => `#${other.rank}`);
    return others.length ? `Too close to call with ${others.slice(0, 2).join(" and ")}` : `Could rank #${row.low} to #${row.high}`;
  }

  function statesWithNoneRanked(ranking) {
    if (app.stateFips) return [];
    const rankedStates = new Set(ranking.ranked.map(row => app.featureByFips.get(row.fips)?.properties.state));
    const names = new Set();
    app.geo.features.forEach(feature => {
      if (!rankedStates.has(feature.properties.state)) names.add(feature.properties.stateName);
    });
    return [...names].sort();
  }

  function scopeName() {
    return app.stateFips ? app.featuresByState.get(app.stateFips)?.[0]?.properties.stateName || "this state" : "";
  }

  function countyButton(fips, className) {
    const feature = app.featureByFips.get(fips);
    const button = document.createElement("button");
    button.type = "button";
    button.className = className;
    button.textContent = feature ? feature.properties.name : fips;
    button.addEventListener("click", () => selectCounty(fips, button));
    return button;
  }

  function renderRankingPanel() {
    const ranking = currentRanking();
    const inputs = activeInputs();
    const state = scopeName();
    elements.factEyebrow.textContent = state ? `Your top counties in ${state}` : "Your top counties";
    elements.factTitle.textContent = "Best fit for what you want to avoid";
    const wrap = document.createElement("div");
    wrap.className = "rank-panel";
    if (!ranking.ranked.length) {
      const empty = document.createElement("p");
      empty.className = "empty-state";
      empty.textContent = inputs.length
        ? "No county here has every input you chose. None can be ranked. The site never scores unavailable values as zero."
        : "Give at least one input a weight above zero to rank counties.";
      wrap.append(empty);
      elements.factBody.append(wrap);
      return;
    }
    const rows = ranking.ranked.slice(0, RANKING_PANEL_SIZE);
    const shared = sharedInputs(rows, inputs);
    const own = inputs.filter(input => !shared.includes(input));

    const key = document.createElement("div");
    key.className = "rank-panel__key";
    const badge = document.createElement("span");
    badge.className = "rank-panel__badge";
    badge.textContent = "#1";
    badge.setAttribute("aria-hidden", "true");
    const keyText = document.createElement("span");
    const strong = document.createElement("strong");
    strong.textContent = "#1 is the best fit.";
    keyText.append(strong, ` Ranked by the ${inputs.length} ${inputs.length === 1 ? "thing" : "things"} you picked and your weight for each.`);
    key.append(badge, keyText);
    wrap.append(key);

    const basis = document.createElement("p");
    basis.className = "rank-panel__basis";
    basis.textContent = [shared.length && shared.length < inputs.length ? sharedSentence(rows, shared) : "", directionSentence(own.length ? own : inputs)].filter(Boolean).join(" ");
    wrap.append(basis);

    const list = document.createElement("ol");
    list.className = "rank-panel__list";
    rows.forEach(row => {
      const item = document.createElement("li");
      const head = document.createElement("div");
      head.className = "rank-panel__head";
      const number = document.createElement("span");
      number.className = "rank-panel__rank";
      number.textContent = row.rank;
      const name = countyButton(row.fips, "rank-panel__name");
      head.append(number, name);
      if (!app.stateFips) {
        const stateName = document.createElement("span");
        stateName.className = "rank-panel__state";
        stateName.textContent = app.featureByFips.get(row.fips)?.properties.stateName || "";
        head.append(stateName);
      }
      item.append(head);
      const values = document.createElement("p");
      values.className = "rank-panel__values";
      (own.length ? own : inputs).forEach((input, index) => {
        if (index) values.append(" · ");
        const bold = document.createElement("b");
        bold.textContent = inputValueText(input, componentValue(row, input.key));
        values.append(`${input.label} `, bold);
      });
      item.append(values);
      const close = closeCallText(row, rows);
      if (close) {
        const tag = document.createElement("span");
        tag.className = "rank-panel__close";
        tag.textContent = close;
        item.append(tag);
      }
      list.append(item);
    });
    wrap.append(list);

    const units = document.createElement("p");
    units.className = "rank-panel__basis";
    units.textContent = `${unitSentence(own.length ? own : inputs)} This compares county records. It is not advice about where to live.`;
    wrap.append(units);

    const tally = ranking.tally;
    if (tally.missing || tally.excluded) {
      const missing = document.createElement("div");
      missing.className = "rank-panel__missing";
      const total = tally.missing + tally.excluded;
      const lead = document.createElement("strong");
      lead.textContent = `Not ranked: ${total.toLocaleString()} ${total === 1 ? "county" : "counties"}`;
      const none = statesWithNoneRanked(ranking);
      const reason = tally.missing && tally.excluded
        ? ` (${tally.missing.toLocaleString()} with unavailable values, ${tally.excluded.toLocaleString()} excluded by your hard limit)`
        : tally.missing ? " with unavailable values" : " excluded by your hard limit";
      const states = none.length ? `, including every county in ${none.length > 3 ? `${none.length} states` : none.length === 1 ? none[0] : `${none.slice(0, -1).join(", ")} and ${none.at(-1)}`}` : "";
      missing.append(lead, `${reason}${states}. `);
      const why = document.createElement("a");
      why.href = "#ranking-missing";
      why.textContent = "Why?";
      missing.append(why);
      wrap.append(missing);
    }
    const more = document.createElement("a");
    more.className = "rank-panel__more";
    more.href = "#ranking-report";
    more.textContent = `See all ${ranking.ranked.length.toLocaleString()} and the full breakdown ↓`;
    wrap.append(more);
    elements.factBody.append(wrap);
  }

  function renderRankingReport() {
    const show = isCompositeView() && Boolean(app.compositeResult);
    elements.rankingReport.hidden = !show;
    if (!show) return;
    const ranking = currentRanking();
    const inputs = activeInputs();
    const total = rankingScope().length;
    const state = scopeName();
    elements.rankingTitle.textContent = state ? `How counties in ${state} compare` : "How the top counties compare";
    elements.rankingFrame.replaceChildren();
    const strong = document.createElement("strong");
    strong.textContent = "what your weights imply";
    elements.rankingFrame.append("This is ", strong, `, not a recommendation. A lower concern score means less of what you chose to avoid. County #1 has the lowest score. It compares historical county records. It says nothing about any one household. Only the ${ranking.ranked.length.toLocaleString()} of ${total.toLocaleString()} counties with every input can be ranked.`);
    if (app.recipe.some(item => item.weight > 0 && datasetForKey(item.key)?.[0] === "places")) {
      const placesNote = document.createElement("p");
      placesNote.className = "ranking-places-caution";
      placesNote.textContent = "CDC model estimate. The CDC advises against ranking counties with PLACES data.";
      elements.rankingFrame.append(placesNote);
    }

    const rows = ranking.ranked.slice(0, rankingCache.limit);
    const barMax = Math.max(...rows.map(row => row.score), 1);
    elements.rankingBody.replaceChildren();
    rows.forEach(row => {
      const tr = document.createElement("tr");
      const rankCell = document.createElement("td");
      rankCell.className = "ranking-rank";
      rankCell.textContent = row.rank;
      const countyCell = document.createElement("td");
      const countyBtn = countyButton(row.fips, "ranking-county");
      countyCell.append(countyBtn);
      if (!app.stateFips) {
        const small = document.createElement("span");
        small.className = "ranking-state";
        small.textContent = app.featureByFips.get(row.fips)?.properties.stateName || "";
        countyCell.append(small);
      }
      const isOpen = rankingOpen.has(row.fips);
      const toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "ranking-toggle";
      toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
      toggle.setAttribute("aria-controls", `ranking-detail-${row.fips}`);
      toggle.setAttribute("aria-label", `Show score breakdown for ${countyBtn.textContent}`);
      const arrow = document.createElement("span");
      arrow.setAttribute("aria-hidden", "true");
      arrow.textContent = isOpen ? "▲" : "▼";
      toggle.append(arrow);
      countyCell.append(toggle);
      const scoreCell = document.createElement("td");
      scoreCell.className = "ranking-score";
      scoreCell.textContent = metricValueFormat(row.score);
      const barCell = document.createElement("td");
      barCell.className = "ranking-bar-cell";
      const bar = document.createElement("div");
      bar.className = "ranking-bar";
      const described = [];
      inputs.forEach(input => {
        const component = row.components.find(c => c.key === input.key);
        const contribution = Number.isFinite(component?.contribution) ? component.contribution : 0;
        const piece = document.createElement("span");
        piece.style.width = `${(contribution / barMax) * 100}%`;
        piece.style.background = input.color;
        bar.append(piece);
        described.push(`${input.label} ${contribution.toFixed(1)}`);
      });
      bar.setAttribute("role", "img");
      bar.setAttribute("aria-label", `Score made up of ${described.join(", ")}`);
      barCell.append(bar);
      const rangeCell = document.createElement("td");
      rangeCell.className = row.high - row.low >= 2 ? "ranking-range is-shaky" : "ranking-range";
      rangeCell.textContent = row.low === row.high ? `Stays #${row.rank}` : `#${row.low}–#${row.high}`;
      tr.append(rankCell, countyCell, scoreCell, barCell, rangeCell);

      const detailRow = document.createElement("tr");
      detailRow.className = "ranking-detail";
      detailRow.id = `ranking-detail-${row.fips}`;
      const detailBlankCell = document.createElement("td");
      const detailCell = document.createElement("td");
      detailCell.colSpan = 3;
      const detailInner = document.createElement("div");
      detailInner.className = "ranking-detail__inner";
      const detailBar = bar.cloneNode(true);
      detailBar.setAttribute("aria-hidden", "true");
      const detailText = document.createElement("span");
      detailText.textContent = described.join(" · ");
      detailInner.append(detailBar, detailText);
      detailCell.append(detailInner);
      detailRow.append(detailBlankCell, detailCell);
      if (!isOpen) detailRow.hidden = true;
      elements.rankingBody.append(tr, detailRow);

      toggle.addEventListener("click", () => {
        const open = toggle.getAttribute("aria-expanded") === "true";
        toggle.setAttribute("aria-expanded", open ? "false" : "true");
        arrow.textContent = open ? "▼" : "▲";
        detailRow.hidden = open;
        if (open) rankingOpen.delete(row.fips);
        else rankingOpen.add(row.fips);
      });
    });
    elements.rankingMore.hidden = ranking.ranked.length <= rows.length;
    elements.rankingMore.textContent = `Show ${Math.min(RANKING_PAGE, ranking.ranked.length - rows.length)} more`;

    elements.rankingKey.replaceChildren();
    const weights = app.compositeResult.weights || {};
    inputs.forEach(input => {
      const item = document.createElement("span");
      item.style.setProperty("--c", input.color);
      item.textContent = `${input.label} · ${Math.round((weights[input.key] || 0) * 100)}% of the weight`;
      elements.rankingKey.append(item);
    });
    const barNote = document.createElement("span");
    barNote.className = "ranking-key__note";
    barNote.textContent = `Bars share one scale, 0 to ${metricValueFormat(barMax)}.`;
    elements.rankingKey.append(barNote);

    const tally = ranking.tally;
    const notRanked = tally.missing + tally.excluded;
    elements.rankingMissingCount.textContent = notRanked.toLocaleString();
    elements.rankingMissingBody.replaceChildren();
    const intro = document.createElement("p");
    intro.textContent = notRanked
      ? `${notRanked === 1 ? "county is" : "counties are"} not ranked. The site never scores an unavailable value as zero. A county is ranked only when every input you chose has a value.`
      : "Every county here has every input you chose.";
    elements.rankingMissingBody.append(intro);
    const addRow = (label, value) => {
      const row = document.createElement("div");
      row.className = "ranking-missing__row";
      const a = document.createElement("span");
      a.textContent = label;
      const b = document.createElement("span");
      b.textContent = value;
      row.append(a, b);
      elements.rankingMissingBody.append(row);
    };
    const statusText = { suppressed: "suppressed by the source", policy: "unavailable by state policy", unavailable: "unavailable", "not-applicable": "not applicable", not_designated: "not designated" };
    if (tally.inputs.length) {
      const heading = document.createElement("h4");
      heading.textContent = "Missing, by input";
      elements.rankingMissingBody.append(heading);
      tally.inputs.forEach(entry => {
        addRow(`${shortInputLabel(entry.key)} (${Object.entries(entry.statuses).map(([status, count]) => `${count.toLocaleString()} ${statusText[status] || status.replace(/[-_]/g, " ")}`).join(", ")})`, entry.total.toLocaleString());
      });
    }
    if (tally.excluded) addRow("Excluded by your hard limits", tally.excluded.toLocaleString());
    const none = statesWithNoneRanked(ranking);
    if (none.length) {
      const heading = document.createElement("h4");
      heading.textContent = "States with no ranked county";
      elements.rankingMissingBody.append(heading);
      const note = document.createElement("p");
      note.textContent = `${none.join(", ")}. A ranked list cannot include ${none.length === 1 ? "this state" : "these states"} with your inputs.`;
      elements.rankingMissingBody.append(note);
    }
  }

  function renderFact() {
    const dataset = activeDataset();
    const feature = app.featureByFips.get(app.countyFips);
    elements.factBody.replaceChildren();
    elements.factClose.hidden = !feature;
    if (!feature && dataset && isCompositeView()) {
      renderRankingPanel();
      return;
    }
    if (!feature || !dataset) {
      elements.factEyebrow.textContent = "County details";
      elements.factTitle.textContent = "Select a county";
      const empty = document.createElement("p");
      empty.className = "empty-state";
      empty.textContent = "Choose a county on the map or from the county picker. The map stays at the state level.";
      elements.factBody.append(empty);
      return;
    }

    const baseRecord = sourceRecord(app.countyFips);
    const record = activeRecord(app.countyFips);
    elements.factEyebrow.textContent = feature.properties.stateName;
    elements.factTitle.textContent = countyLabel(feature).replace(`, ${feature.properties.stateName}`, "");
    if (isCompositeView()) {
      renderCompositeFact(record);
      return;
    }
    if (isAvailable(record)) {
      const value = document.createElement("p");
      value.className = "fact-value";
      value.textContent = metricValueFormat(record.value);
      const unit = document.createElement("p");
      unit.className = "fact-unit";
      unit.textContent = unitLabel(dataset);
      elements.factBody.append(value, unit, factGrid(dataset, record, baseRecord));
    } else {
      const value = document.createElement("p");
      value.className = "fact-value fact-value--status";
      value.textContent = record?.status === "not_designated" ? "Not designated" : "Unavailable";
      const status = document.createElement("p");
      status.className = "fact-unit";
      status.textContent = statusLabel(record);
      elements.factBody.append(value, status, factGrid(dataset, record, baseRecord));
    }
    const note = document.createElement("p");
    note.className = "status-note";
    note.textContent = isAvailable(record)
      ? [app.family === "healthcare" ? "This is the highest priority score among designated areas in the county. It is not a measure of provider availability or healthcare safety." : "", baseRecord?.note, baseRecord?.reason, extremeCountyExplanation(record, dataset), interpretationShort()].filter(Boolean).join(" ")
      : statusExplanation(record);
    elements.factBody.append(note);
  }

  function renderCompositeFact(record) {
    const available = isAvailable(record);
    const value = document.createElement("p");
    value.className = available ? "fact-value" : "fact-value fact-value--status";
    value.textContent = available ? metricValueFormat(record.value) : statusLabel(record);
    const unit = document.createElement("p");
    unit.className = "fact-unit";
    unit.textContent = available ? "concern score under your weights · lower is better" : statusExplanation(record);
    elements.factBody.append(value, unit);

    const summary = document.createElement("div");
    summary.className = "fact-grid";
    const stats = app.compositeResult?.stats;
    [
      ["Status", statusLabel(record)],
      ["Comparable counties", stats ? `${stats.available.toLocaleString()} of ${stats.total.toLocaleString()}` : "Unavailable"],
      ["Inputs", String(app.recipe.length)],
      ["Excluded by your hard limit", stats ? stats.excluded.toLocaleString() : "—"]
    ].forEach(([label, content]) => {
      const item = document.createElement("div");
      const key = document.createElement("span");
      const strong = document.createElement("strong");
      key.textContent = label;
      strong.textContent = content;
      item.append(key, strong);
      summary.append(item);
    });
    elements.factBody.append(summary);
    const sensitivityHeading = document.createElement("h3");
    sensitivityHeading.className = "component-heading";
    sensitivityHeading.textContent = "Weight changes";
    const sensitivitySection = document.createElement("div");
    sensitivitySection.className = "weight-sensitivity";
    elements.factBody.append(sensitivityHeading, sensitivitySection);

    const sensitivity = available && Array.isArray(record?.components) && record.components.length
      ? AtlasComposite.weightSensitivity(record)
      : null;
    const componentTitleFor = key => {
      const match = (record?.components || []).find(component => component.key === key);
      return match?.title || key;
    };
    const activeInputs = (record?.components || []).filter(component => Number(component.weight) > 0);
    if (!available || !sensitivity || sensitivity.status !== "available") {
      const unavailable = document.createElement("p");
      unavailable.className = "weight-sensitivity__range";
      unavailable.textContent = "The weighted range is unavailable for this county.";
      const unavailableNote = document.createElement("p");
      unavailableNote.className = "status-note";
      unavailableNote.textContent = "The site never scores excluded or unavailable counties. It cannot show a range for weight changes.";
      sensitivitySection.append(unavailable, unavailableNote);
    } else if (activeInputs.length <= 1) {
      const single = document.createElement("p");
      single.className = "weight-sensitivity__range";
      single.textContent = `Concern score ${sensitivity.baseline.toFixed(1)}.`;
      const singleNote = document.createElement("p");
      singleNote.className = "status-note";
      singleNote.textContent = "The score stays unchanged with only one active input.";
      sensitivitySection.append(single, singleNote);
    } else {
      const range = document.createElement("p");
      range.className = "weight-sensitivity__range";
      range.textContent = `Concern score ${sensitivity.baseline.toFixed(1)} · range ${sensitivity.min.toFixed(1)} to ${sensitivity.max.toFixed(1)}`;
      const explanation = document.createElement("p");
      explanation.className = "weight-sensitivity__explanation";
      explanation.textContent = "Each positive weight goes up or down by 20%, one at a time. The site holds the other weights fixed. Then it scales all weights again. Source scales and hard limits stay fixed. This is not a likely range. It does not guarantee that the order stays the same.";
      const count = document.createElement("p");
      count.className = "weight-sensitivity__count";
      count.textContent = `${sensitivity.scenarios.length} scenarios across ${activeInputs.length} active inputs.`;
      const details = document.createElement("details");
      details.className = "weight-sensitivity__details";
      const detailsSummary = document.createElement("summary");
      detailsSummary.textContent = "See weight changes";
      const scenarioList = document.createElement("ul");
      scenarioList.className = "weight-sensitivity__list";
      sensitivity.scenarios.forEach(scenario => {
        const item = document.createElement("li");
        item.textContent = `${componentTitleFor(scenario.key)} · ${scenario.factor < 1 ? "-20%" : "+20%"} · score ${scenario.value.toFixed(1)}`;
        scenarioList.append(item);
      });
      details.append(detailsSummary, scenarioList);
      sensitivitySection.append(range, explanation, count, details);
    }

    const heading = document.createElement("h3");
    heading.className = "component-heading";
    heading.textContent = "Input breakdown";
    const list = document.createElement("ol");
    list.className = "component-list";
    (record?.components || []).forEach(component => {
      const componentFamily = String(component.key || "").split(":", 1)[0];
      const item = document.createElement("li");
      if (component.extreme) item.classList.add("is-extreme");
      const head = document.createElement("div");
      head.className = "component-head";
      const title = document.createElement("strong");
      title.textContent = component.title;
      const contribution = document.createElement("span");
      contribution.textContent = Number.isFinite(component.contribution) ? `${component.contribution.toFixed(1)} points` : "No contribution";
      head.append(title, contribution);
      item.append(head);

      const meta = document.createElement("p");
      meta.textContent = component.status === "available"
        ? `${familyValueFormat(component.value, componentFamily)} ${component.unit || ""} · score ${component.scaled.toFixed(1)}/100 · weight ${(component.weight * 100).toFixed(1)}%`
        : `${statusLabel(component)} · ${componentFamily === "healthcare" && component.status === "not_designated" ? statusExplanation(component) : component.reason || "No numeric value"}`;
      item.append(meta);
      if (componentFamily === "broadband") {
        const source = datasetForKey(component.key)?.[1]?.records?.[app.countyFips];
        const broadbandNote = document.createElement("p");
        broadbandNote.className = "status-note";
        broadbandNote.textContent = isAvailable(source)
          ? `Reported access at 100/20 Mbps: ${Number.isFinite(source.sourceAccessPercent) ? `${familyValueFormat(source.sourceAccessPercent, "broadband")}%` : "Not supplied"} of residents · displayed gap: ${Number.isFinite(source.value) ? `${familyValueFormat(source.value, "broadband")}%` : "Unavailable"} of residents. The gap is 100% minus reported access.`
          : statusExplanation(source);
        item.append(broadbandNote);
      }
      if (componentFamily === "healthcare") {
        const source = datasetForKey(component.key)?.[1]?.records?.[app.countyFips];
        const basis = document.createElement("p");
        basis.className = "status-note";
        basis.textContent = isAvailable(source)
          ? `This is the highest priority score among the county's shortage areas. It does not measure how many providers there are or how safe care is. ${source.componentBasis === "whole-county" ? "At least one shortage area covers the whole county. The highest score can come from another area." : "The shortage areas cover only part of the county."} Shortage areas: ${source.components}. Proposed for withdrawal: ${source.proposedForWithdrawal}.`
          : statusExplanation(source);
        item.append(basis);
      }
      const context = document.createElement("p");
      const uncertainty = Number.isFinite(component.moe)
        ? `Margin of error (90%) ±${familyValueFormat(component.moe, componentFamily)}`
        : Number.isFinite(component.low) && Number.isFinite(component.high)
          ? `Likely range (95%) ${familyValueFormat(component.low, componentFamily)} to ${familyValueFormat(component.high, componentFamily)}`
          : "No likely range from the source";
      const threshold = usableThreshold(app.recipe.find(signal => signal.key === component.key));
      const limit = threshold
        ? ` · hard limit ${threshold.operator === "max" ? "at or below" : "at or above"} ${familyValueFormat(threshold.value, componentFamily)} ${component.unit || ""}`
        : "";
      context.textContent = `${component.period || "Period not stated"} · ${uncertainty}${limit}`;
      item.append(context);
      const badges = [];
      if (component.extreme) badges.push("Extreme value. Purple outline on map.");
      if (record.thresholdFailures?.includes(component.title)) badges.push("Excluded by your hard limit");
      if (badges.length) {
        const badge = document.createElement("p");
        badge.className = "component-badge";
        badge.textContent = badges.join(" · ");
        item.append(badge);
      }
      if (component.sourceUrl) {
        const source = document.createElement("a");
        source.href = component.sourceUrl;
        source.target = "_blank";
        source.rel = "noreferrer";
        source.textContent = "View measure source ↗";
        item.append(source);
      }
      list.append(item);
    });
    elements.factBody.append(heading, list);
    const note = document.createElement("p");
    note.className = "status-note";
    note.textContent = available
      ? "The fill compares the actual concern scores for your inputs. A purple outline marks at least one extreme value from a source. It does not mean the concern score is an error."
      : statusExplanation(record);
    elements.factBody.append(note);
  }

  function extremeCountyExplanation(record, dataset) {
    if (!isExtremeHigh(record, dataset)) return "";
    const stats = scaleStats(dataset);
    return `This value is extreme. It is above ${thresholdFormat(stats.fence)}, the national limit for extreme values, so it shows in purple. Purple does not mean a data error.`;
  }

  function employmentPeople(value) {
    return Number.isFinite(value) ? `${value.toLocaleString("en-US")} people, 2025 11-month average` : "Unavailable";
  }

  function factGrid(dataset, record, baseRecord) {
    const grid = document.createElement("div");
    grid.className = "fact-grid";
    const items = isTrendView()
      ? [
          ["Status", isAvailable(record) ? `Available · ${trendCategoryLabel(record)}` : statusLabel(record)],
          ["Trend window", displayPeriod(dataset)],
          ["Population", dataset.sex || "All residents"],
          ["Trend likely range (95%)", Number.isFinite(record?.low) && Number.isFinite(record?.high) ? `${metricValueFormat(record.low)}% to ${metricValueFormat(record.high)}%` : "Unavailable"],
          ["Incidence rate context", isAvailable(baseRecord) ? `${valueFormat(baseRecord.value)} per 100,000 people a year · ${dataset.period}` : statusLabel(baseRecord)],
          ["Average annual count", Number.isFinite(baseRecord?.count) ? valueFormat(baseRecord.count) : "Unavailable"]
        ]
      : app.family === "cancer"
      ? [
          ["Status", statusLabel(record)],
          ["Period", displayPeriod(dataset)],
          ["Population", dataset.sex || "All residents"],
          ["Likely range (95%)", Number.isFinite(record?.low) && Number.isFinite(record?.high) ? `${valueFormat(record.low)}–${valueFormat(record.high)}` : "Unavailable"],
          ["Average annual count", Number.isFinite(record?.count) ? valueFormat(record.count) : "Unavailable"]
        ]
      : app.family === "community"
        ? [
            ["Status", statusLabel(record)],
            ["Period", dataset.period || "Unavailable"],
            ["Margin of error (90%)", Number.isFinite(record?.moe) ? `±${familyValueFormat(record.moe, "community")}` : "Unavailable"],
            ["Comparison direction", dataset.direction === "higher-better" ? "Lower values raise the concern score" : "Higher values raise the concern score"]
          ]
      : app.family === "healthcare"
        ? [
            ["Status", statusLabel(record)],
            ["Designations as of", dataset.period || "Unavailable"],
            ["Score covers", record?.componentBasis === "whole-county" ? "The whole county"
              : record?.componentBasis === "sub-county" ? "Part of the county only" : "Not applicable"],
            ["Designated areas", Number.isFinite(record?.components) ? String(record.components) : "None"],
            ["Proposed for withdrawal", Number.isFinite(record?.proposedForWithdrawal)
              ? `${record.proposedForWithdrawal}. Not counted in the score.` : "Unavailable"]
          ]
      : app.family === "employment"
        ? [
            ["Status", statusLabel(record)],
            ["Period", displayPeriod(dataset)],
            ["Civilian labor force", employmentPeople(record?.laborForce)],
            ["Employed", employmentPeople(record?.employed)],
            ["Unemployed", employmentPeople(record?.unemployed)]
          ]
      : app.family === "broadband"
        ? [
            ["Status", statusLabel(record)],
            ["Period", displayPeriod(dataset)],
            ["Reported access at 100/20 Mbps", Number.isFinite(record?.sourceAccessPercent) ? `${metricValueFormat(record.sourceAccessPercent)}% of population` : "Unavailable"],
            ["Without reported access, calculated", isAvailable(record) && Number.isFinite(record?.value) ? `${metricValueFormat(record.value)}% of population` : "Unavailable"],
            ["Calculation", "100% − reported access"]
          ]
      : app.family === "places"
        ? [
            ["Status", statusLabel(record)],
            ["Period", "2022"],
            ["Map value, adjusted for age", isAvailable(record) && Number.isFinite(record?.value) && Number.isFinite(record?.low) && Number.isFinite(record?.high) ? `${metricValueFormat(record.value)}% (95% likely range ${valueFormat(record.low)}–${valueFormat(record.high)}%)` : statusLabel(record)],
            ["Share before age adjustment", isAvailable(record) && Number.isFinite(record?.crude) && Number.isFinite(record?.crudeLow) && Number.isFinite(record?.crudeHigh) ? `${metricValueFormat(record.crude)}% (95% likely range ${valueFormat(record.crudeLow)}–${valueFormat(record.crudeHigh)}%)` : "Unavailable"],
            ["Source", "CDC PLACES 2024 release (BRFSS 2022)"]
          ]
      : app.family === "air"
        ? [
            ["Status", statusLabel(record)],
            ["Period", dataset.period],
            ["Three-year average", isAvailable(record) && Number.isFinite(record?.value) ? `${genericValueFormat(record.value)} µg/m³` : statusLabel(record)],
            ["2020", Number.isFinite(record?.annual?.["2020"]) ? `${genericValueFormat(record.annual["2020"])} µg/m³` : "Unavailable"],
            ["2021", Number.isFinite(record?.annual?.["2021"]) ? `${genericValueFormat(record.annual["2021"])} µg/m³` : "Unavailable"],
            ["2022", Number.isFinite(record?.annual?.["2022"]) ? `${genericValueFormat(record.annual["2022"])} µg/m³` : "Unavailable"],
            ["Source", "CDC Tracking Network, EPA Downscaler model"]
          ]
      : app.family === "wildfire"
        ? [
            ["Status", statusLabel(record)],
            ["Period", dataset.period],
            ["National percentile", isAvailable(record) && Number.isFinite(record?.value) ? genericValueFormat(record.value) : statusLabel(record)],
            ["Source", "USDA Forest Service, Wildfire Risk to Communities"]
          ]
      : app.family === "water"
        ? [
            ["Status", statusLabel(record)],
            ["Period", dataset.period],
            ["People on a water system with a violation", isAvailable(record) && Number.isFinite(record?.value) ? `${genericValueFormat(record.value)}%` : statusLabel(record)],
            ["People served by community water systems", Number.isFinite(record?.populationServed) ? record.populationServed.toLocaleString() : "Unavailable"],
            ["People on water systems with a violation", Number.isFinite(record?.populationWithViolation) ? record.populationWithViolation.toLocaleString() : "Unavailable"],
            ["Community water systems", Number.isFinite(record?.systems) ? record.systems.toLocaleString() : "Unavailable"],
            ["Water systems with a violation", Number.isFinite(record?.systemsWithViolation) ? record.systemsWithViolation.toLocaleString() : "Unavailable"],
            ["Source", "EPA ECHO / SDWIS"]
          ]
      : app.family === "traffic"
        ? [
            ["Status", statusLabel(record)],
            ["Period", dataset.period],
            ["Deaths per 100,000 residents", isAvailable(record) && Number.isFinite(record?.value) ? genericValueFormat(record.value) : statusLabel(record)],
            ["Deaths, 2019–2023", Number.isFinite(record?.deaths) ? record.deaths.toLocaleString() : "Unavailable"],
            ["Residents (ACS 2019–2023)", Number.isFinite(record?.population) ? record.population.toLocaleString() : "Unavailable"],
            ["Source", "NHTSA FARS; Census ACS"]
          ]
      : [
          ["Status", statusLabel(record)],
          ["Period", dataset.period || "Unavailable"]
        ];
    items.forEach(([label, value]) => {
      const item = document.createElement("div");
      const span = document.createElement("span");
      const strong = document.createElement("strong");
      span.textContent = label;
      strong.textContent = value;
      item.append(span, strong);
      grid.append(item);
    });
    return grid;
  }

  function renderLegend() {
    const dataset = activeDataset();
    if (!dataset) return;
    elements.legendExcluded.hidden = true;
    elements.legendNotDesignated.hidden = isCompositeView()
      || !Object.values(dataset.records || {}).some(record => record?.status === "not_designated");
    elements.legendMissingLabel.textContent = "Unavailable or suppressed";
    elements.legendOutlier.classList.remove("is-outline-key");
    elements.legendTitle.textContent = isTrendView() ? cancerTypeLabel(dataset) : metricTitle(dataset);
    elements.legendMeta.textContent = app.family === "cancer"
      ? `${unitLabel(dataset)} · ${dataset.sex || "All residents"}`
      : unitLabel(dataset);
    elements.legendPeriod.textContent = displayPeriod(dataset);
    elements.legendTicks.replaceChildren();
    requestAnimationFrame(thinLegendTicks);
    elements.legendRamp.classList.toggle("is-categorical", isTrendView());
    elements.legendTicks.classList.toggle("is-categorical", isTrendView());
    if (isCompositeView()) {
      const stats = app.compositeResult?.stats;
      elements.legendTitle.textContent = "My priorities";
      elements.legendMeta.textContent = `Concern score · lower is better · ${app.recipe.length} selected inputs`;
      elements.legendPeriod.textContent = "Source periods vary";
      elements.legendRamp.hidden = !stats?.available;
      elements.legendMissingLabel.textContent = "Selected inputs unavailable";
      elements.legendExcluded.hidden = !(stats?.excluded > 0);
      if (!stats?.available || !Number.isFinite(stats.min) || !Number.isFinite(stats.max)) {
        const emptyTick = document.createElement("span");
        emptyTick.className = "is-single";
        emptyTick.textContent = "No comparable concern scores";
        emptyTick.style.left = "50%";
        elements.legendTicks.append(emptyTick);
      } else {
        const span = stats.max - stats.min;
        const ticks = span > 0 ? d3.ticks(stats.min, stats.max, 4) : [];
        const values = [stats.min, ...ticks.filter(value => span > 0 && (value - stats.min) / span > .1 && (value - stats.min) / span < .9), ...(span > 0 ? [stats.max] : [])];
        values.forEach((value, index) => {
          const tick = document.createElement("span");
          tick.textContent = span === 0 ? `Only ${metricValueFormat(value)}` : index === 0 ? `Less ${metricValueFormat(value)}` : index === values.length - 1 ? `More ${metricValueFormat(value)}` : metricValueFormat(value);
          if (span === 0) tick.className = "is-single";
          tick.style.left = `${span === 0 ? 50 : ((value - stats.min) / span) * 100}%`;
          elements.legendTicks.append(tick);
        });
      }
      const extremeCount = Object.values(app.compositeResult?.records || {}).filter(record => record.extreme).length;
      elements.legendOutlier.hidden = extremeCount === 0;
      elements.legendOutlier.classList.add("is-outline-key");
      if (extremeCount) elements.legendOutlierText.textContent = `Purple outline: ${extremeCount.toLocaleString()} ${extremeCount === 1 ? "county has" : "counties have"} an extreme value`;
      elements.scaleExplanation.textContent = "Blue means less of the measures you chose to avoid. Red means more. The range covers the actual concern scores for your weights. It stays fixed in state views.";
      return;
    }
    if (isTrendView()) {
      elements.legendRamp.hidden = false;
      [
        ["Falling", 0],
        ["Stable", 50],
        ["Rising", 100]
      ].forEach(([label, position]) => {
        const tick = document.createElement("span");
        tick.textContent = label;
        tick.style.left = `${position}%`;
        elements.legendTicks.append(tick);
      });
      elements.legendOutlier.hidden = true;
      elements.scaleExplanation.textContent = "Blue means falling. Neutral means stable. Red means rising. The map uses the source categories. Categories stay fixed in state views.";
      return;
    }

    const stats = scaleStats(dataset);
    elements.legendRamp.hidden = !stats.availableCount;
    if (!stats.availableCount) {
      const emptyTick = document.createElement("span");
      emptyTick.className = "is-single";
      emptyTick.textContent = "No numeric values";
      emptyTick.style.left = "50%";
      elements.legendTicks.append(emptyTick);
      elements.legendOutlier.hidden = true;
      elements.scaleExplanation.textContent = "The map cannot show any national values for this measure.";
      return;
    }

    const span = stats.regularMax - stats.regularMin;
    const ticks = span > 0 ? d3.ticks(stats.regularMin, stats.regularMax, 4) : [];
    const values = [
      stats.regularMin,
      ...ticks.filter(tick => span > 0
        && (app.family !== "disasters" || Number.isInteger(tick))
        && (tick - stats.regularMin) / span > .1
        && (tick - stats.regularMin) / span < .9),
      ...(span > 0 ? [stats.regularMax] : [])
    ];
    values.forEach((value, index) => {
      const tick = document.createElement("span");
      tick.textContent = span === 0
        ? `Only ${metricValueFormat(value)}`
        : index === 0
        ? `Low ${metricValueFormat(value)}`
        : index === values.length - 1
          ? `High ${metricValueFormat(value)}`
          : metricValueFormat(value);
      if (span === 0) tick.className = "is-single";
      const position = span === 0 ? 50 : ((value - stats.regularMin) / span) * 100;
      tick.style.left = `${position}%`;
      elements.legendTicks.append(tick);
    });
    elements.legendOutlier.hidden = stats.outlierCount === 0;
    if (stats.outlierCount > 0) elements.legendOutlierText.textContent = outlierLegendText(stats);
    elements.scaleExplanation.textContent = scaleExplanationText(stats);
  }

  function outlierLegendText(stats) {
    const counties = stats.outlierCount === 1 ? "county" : "counties";
    const range = stats.outlierMin === stats.outlierMax
      ? metricValueFormat(stats.outlierMin)
      : `${metricValueFormat(stats.outlierMin)}–${metricValueFormat(stats.outlierMax)}`;
    return `Purple: ${stats.outlierCount} extreme-high ${counties} · observed ${range} · above ${thresholdFormat(stats.fence)}`;
  }

  function scaleExplanationText(stats) {
    if (!stats?.availableCount) return "The map cannot show any national values for this measure.";
    return stats.outlierCount > 0
      ? "The blue-to-red range covers the remaining county values. Purple marks extreme values. The national scale stays fixed in state views."
      : "The blue-to-red range covers all available county values. The map flags no extreme values. The national scale stays fixed in state views.";
  }

  function scaleRangeSummary(stats) {
    if (!stats?.availableCount) return "No numeric values";
    const range = `${metricValueFormat(stats.regularMin)}–${metricValueFormat(stats.regularMax)}`;
    return stats.outlierCount > 0
      ? `Blue–red ${range} · ${stats.outlierCount} purple > ${thresholdFormat(stats.fence)}`
      : `Blue-to-red ${range} · no purple extreme values`;
  }

  function scaleAnnouncement(stats) {
    if (!stats?.availableCount) return "No national values are available.";
    const range = `${metricValueFormat(stats.regularMin)} to ${metricValueFormat(stats.regularMax)}`;
    return stats.outlierCount > 0
      ? `The national blue-to-red range is ${range}. ${stats.outlierCount} ${stats.outlierCount === 1 ? "county is" : "counties are"} purple because the value is extreme, above ${thresholdFormat(stats.fence)}.`
      : `The national blue-to-red range is ${range}. No extreme values are purple.`;
  }

  function activeScaleRangeSummary(dataset) {
    if (isCompositeView()) {
      const stats = app.compositeResult?.stats;
      return stats?.available ? `Combined ${metricValueFormat(stats.min)}–${metricValueFormat(stats.max)}` : "No comparable concern scores";
    }
    return isTrendView()
      ? "Falling · Stable · Rising"
      : scaleRangeSummary(scaleStats(dataset));
  }

  function activeScaleAnnouncement(dataset) {
    if (isCompositeView()) {
      const stats = app.compositeResult?.stats;
      return stats?.available
        ? `The national concern score range is ${metricValueFormat(stats.min)} to ${metricValueFormat(stats.max)}. The map has ${stats.available} comparable counties. Hard limits exclude ${stats.excluded} counties.`
        : "No counties have a comparable concern score for these inputs and weights.";
    }
    return isTrendView()
      ? "The national source categories are Falling, Stable, and Rising."
      : scaleAnnouncement(scaleStats(dataset));
  }

  function renderTable() {
    elements.tableBody.replaceChildren();
    const dataset = activeDataset();
    elements.valueColumn.textContent = dataset ? `${metricTitle(dataset)} (${unitLabel(dataset)})` : "Value";
    const showUncertainty = app.family === "cancer" || app.family === "community";
    elements.ciColumn.hidden = !showUncertainty;
    elements.ciColumn.textContent = app.family === "community" ? "Margin of error (90%)" : isTrendView() ? "Trend likely range (95%)" : "Likely range (95%)";
    if (!app.stateFips || !dataset) {
      tableEmpty("Choose a state to fill this table.");
      return;
    }
    const features = [...(app.featuresByState.get(app.stateFips) || [])]
      .sort((a, b) => a.properties.name.localeCompare(b.properties.name));
    for (const feature of features) {
      const record = activeRecord(feature.properties.fips);
      const row = document.createElement("tr");
      const county = document.createElement("th");
      county.scope = "row";
      county.textContent = countyLabel(feature).replace(`, ${feature.properties.stateName}`, "");
      const value = document.createElement("td");
      value.textContent = isAvailable(record) ? metricValueFormat(record.value) : "—";
      const ci = document.createElement("td");
      ci.textContent = app.family === "community"
        ? Number.isFinite(record?.moe) ? `±${familyValueFormat(record.moe, "community")}` : "Unavailable"
        : Number.isFinite(record?.low) && Number.isFinite(record?.high)
          ? isTrendView()
            ? `${metricValueFormat(record.low)}% to ${metricValueFormat(record.high)}%`
            : `${valueFormat(record.low)}–${valueFormat(record.high)}`
          : "Unavailable";
      const status = document.createElement("td");
      status.textContent = isTrendView() && isAvailable(record)
        ? `Available · ${trendCategoryLabel(record)}`
        : app.family === "healthcare" && record?.status === "not_designated"
          ? "No primary care shortage area · not proof that access to care is good"
        : isCompositeView() && isAvailable(record) && record.extreme
          ? "Available · An input has an extreme value, purple outline"
        : isExtremeHigh(record, dataset)
          ? "Available · Extreme value, purple"
          : statusLabel(record);
      const actionCell = document.createElement("td");
      const action = document.createElement("button");
      action.type = "button";
      action.className = "table-action";
      action.textContent = "Details";
      action.setAttribute("aria-label", `Show details for ${countyLabel(feature)}`);
      action.addEventListener("click", () => selectCounty(feature.properties.fips, action));
      actionCell.append(action);
      row.append(county, value);
      if (showUncertainty) row.append(ci);
      row.append(status, actionCell);
      elements.tableBody.append(row);
    }
  }

  function tableEmpty(message) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = app.family === "cancer" || app.family === "community" ? 5 : 4;
    cell.className = "table-empty";
    cell.textContent = message;
    row.append(cell);
    elements.tableBody.append(row);
  }

  function interpretationShort() {
    if (isCompositeView()) return "A weighted comparison of selected county measures. It is not a probability or a safety rating. It does not claim cause.";
    if (isTrendView()) return "Recent trends in county cancer rates. They are not your personal cancer risk. They are not a forecast.";
    if (app.family === "cancer") return "Values for all residents of the county. They are not your personal cancer risk.";
    if (app.family === "disasters") return "Historical federal declarations. They are not a complete event history. They are not a forecast of future risk.";
    if (app.family === "community") return "County estimates describe local conditions. They do not determine one household's experience.";
    if (app.family === "healthcare") return "An administrative priority score for placing clinicians. It is not a measured count of doctors. It is not anyone's personal access to care.";
    if (app.family === "employment") return "The share of county residents who are unemployed and available for work. The value uses where people live. It is not job openings. It is not one person's chance of employment.";
    if (app.family === "broadband") return "The share of residents who do not have reported access to fixed land-based broadband at 100/20 Mbps or faster. The value shows advertised availability. It is not measured speed, reliability, price, or a guarantee at an address.";
    if (app.family === "places") return "CDC model estimates for adults, adjusted for age. They are not a count. They are not your personal risk. The CDC advises against ranking counties with these values.";
    if (app.family === "air") return "Model estimates of long-term fine particle pollution where people live. The values average 2020–2022. They are not daily air quality. They are not anyone's personal exposure.";
    if (app.family === "wildfire") return "National ranks from a USDA Forest Service model. The value is a rank from 0 to 100. It is not a probability of fire or a loss amount.";
    if (app.family === "water") return "Share of people on community water systems whose system had a health-based violation in 2023–2025. One large system can decide a county, and private wells are not covered.";
    if (app.family === "traffic") return "Deaths in crashes on the county's roads per 100,000 residents, 2019–2023. It includes people passing through, so it is not a resident's own risk.";
    if (app.family === "climate") return "A 30-year climate average for the whole county. It is not a value for one place in the county. It is not a forecast.";
    if (app.family === "storms") return "Storm reports a year per 1,000 square miles, 2006–2025. More reports come in where more people live. Winter, heat and high-wind storms are not counted. It is not a forecast.";
    if (app.family === "crime") return "Crimes reported to police per 100,000 residents, 2023–2025. Many crimes are never reported. Counties with too little reporting show as unavailable. The FBI advises against ranking places with these data.";
    return "Model estimates for county hazards describe a scenario from the source. They are not a forecast for one property.";
  }

  function sourceUrlForFamilyDataset(family, collection, dataset) {
    const baseUrl = dataset?.sourceUrl || collection?.sourceUrl || "";
    if (!baseUrl || family !== "cancer" || !dataset) return baseUrl;
    try {
      const url = new URL(baseUrl);
      url.searchParams.set("cancer", datasetCancerId(dataset));
      url.searchParams.set("sex", datasetSexId(dataset));
      return url.href;
    } catch (_error) {
      return baseUrl;
    }
  }

  function sourceUrlForDataset(collection, dataset) {
    return sourceUrlForFamilyDataset(app.family, collection, dataset);
  }

  function updateMethod() {
    const collection = activeCollection();
    const dataset = activeDataset();
    const scaleMethod = "For each measure, a value is extreme when it is far above most counties. The rule is a value more than 3 times the middle spread above the upper quarter of counties. Extreme values show in purple. The blue-to-red scale ignores them, so the other colors stay useful. County details and the table still show the exact values. If most counties have the same value, the site marks no extreme values. Purple does not mean an error.";
    elements.interpretation.textContent = interpretationShort();
    elements.layerCaveat.textContent = interpretationShort();
    if (isCompositeView()) {
      elements.methodDetail.textContent = "The site puts each input on a scale from 0 to 100. The scale runs from the lowest to the highest county value in the country. An extreme value counts as the top of the scale. Then the site multiplies each input by its weight. The weights add up to 100%. A county needs a value for every input with a weight. The site never treats an unavailable value as zero. A hard limit excludes counties outside the value you set. Excluded counties get no concern score. The map colors run from the lowest to the highest concern score. Purple outlines mark an extreme value in an input, not an error. When you change inputs or weights, the scores and colors change.";
    } else if (isTrendView()) {
      elements.methodDetail.textContent = "The recent 5-year trend is the source-reported average yearly percent change. It has its own likely range and source category. Blue means falling. Neutral means stable. Red means rising. The categories do not show the size of the change. A recent trend does not prove cause. It does not predict a future rate. It does not mean the current rate is low or high. People move. Screening, resident characteristics, healthcare access, and exposures can affect observed values.";
    } else if (app.family === "cancer") {
      elements.methodDetail.textContent = `People move. Cancers can develop over many years. Screening, resident characteristics, healthcare access, and exposures can affect observed values. Adjusting for age helps compare counties with different age groups. It does not remove all differences. This map does not show that living in a county causes cancer. It does not show that moving would change one person's risk. ${scaleMethod}`;
    } else if (app.family === "disasters") {
      elements.methodDetail.textContent = `This map counts distinct qualifying federal major-disaster declarations assigned to counties during the shown period. It excludes emergency and fire-management declarations, biological events, statewide-only records, and non-county designations. A declaration is an administrative record. It is not an event severity score, a complete hazard history, an insurance quote, or a forecast. ${scaleMethod}`;
    } else if (app.family === "healthcare") {
      elements.methodDetail.textContent = `Each county with a score shows the highest priority score among its designated shortage areas. A shortage area can cover the whole county or only part of it. The highest score can come from a part-county area even when a whole-county area exists. Areas proposed for withdrawal are counted separately. They do not count in the score. A county with no shortage area gets no score. This does not prove that access to care is good. Connecticut is unavailable because the source uses 2022 planning regions. This atlas uses the older counties. ${scaleMethod}`;
    } else if (app.family === "employment") {
      elements.methodDetail.textContent = `This map shows the published BLS unemployment rate for each county. The rate is the share of residents who are unemployed and available for work. It uses where people live. It is not seasonally adjusted. The 2025 value is an 11-month average. It excludes October 2025 because of the federal government shutdown. It is not fully comparable with yearly averages for other years. It is not a count of job openings. It is not an estimate of one person's chance of employment. Connecticut is unavailable because the source reports planning regions. This atlas uses older counties. ${scaleMethod}`;
    } else if (app.family === "broadband") {
      elements.methodDetail.textContent = `The value is the share of residents without reported broadband at 100/20 Mbps or faster. It counts wired and fixed wireless service. Satellite does not count. The site calculates the value as 100% minus the share with reported access. The measurement is from June 2024. The FCC released it in 2025. That is not a newer measurement. Advertised access is not measured speed, reliability, price or use. It is not a promise for one address. County details keep the source values. The source gives no resident counts and no likely range. ${scaleMethod}`;
    } else {
      elements.methodDetail.textContent = `${dataset?.note || collection?.note || "This county layer uses the source definition and period shown."} Values can be uncertain. They do not describe every household or property. ${scaleMethod}`;
    }
    if (isCompositeView()) {
      elements.sourceStatus.textContent = "Each input in the county breakdown links to its source. The Data sources list at the end of the page names every source.";
      elements.sourceLink.hidden = true;
      return;
    }
    const sourceName = app.family === "cancer"
      ? "NCI/CDC State Cancer Profiles"
      : app.family === "disasters"
        ? "FEMA OpenFEMA"
        : dataset?.source || collection?.source || FAMILY_LABELS[app.family];
    const notes = [...new Set([dataset?.note, collection?.note].filter(Boolean))];
    elements.sourceStatus.textContent = [sourceName, displayPeriod(dataset), app.geo?.source, ...notes].filter(Boolean).join(" · ") || "Source details unavailable.";
    const sourceUrl = sourceUrlForDataset(collection, dataset);
    if (sourceUrl) {
      elements.sourceLink.href = sourceUrl;
      elements.sourceLink.hidden = false;
    } else {
      elements.sourceLink.hidden = true;
    }
  }

  function updateNavigationText() {
    const dataset = activeDataset();
    const state = app.stateFips ? stateName(app.stateFips) : "";
    elements.kicker.textContent = state ? "State focus · National scale retained" : "National comparison";
    elements.heading.textContent = state || "Counties across the lower 48";
    elements.dockLocation.textContent = app.countyFips
      ? countyLabel(app.featureByFips.get(app.countyFips))
      : state || "Lower 48";
    elements.dockTitle.textContent = metricTitle(dataset);
    elements.dockRange.textContent = dataset ? activeScaleRangeSummary(dataset) : "—";
    elements.back.disabled = !app.stateFips && !app.countyFips;
    elements.keyboardHint.textContent = app.stateFips
      ? "Drag the map to pan. You can also use the arrow keys when the map has focus. Pinch with two fingers or scroll over the map to zoom the focused state. Page scrolling still works outside the map. Click a county for details. Tap or click empty map space to return to the US view."
      : "Drag the map to pan. You can also use the arrow keys when the map has focus. Pinch with two fingers or scroll over the map to zoom. Page scrolling still works outside the map. Click a county to focus its state."
    updateZoomControls();
  }

  function updateCoverage() {
    const dataset = activeDataset();
    if (!dataset) return;
    const features = app.stateFips ? (app.featuresByState.get(app.stateFips) || []) : app.geo.features;
    const available = features.filter(feature => isAvailable(activeRecord(feature.properties.fips))).length;
    if (isCompositeView()) {
      const excluded = features.filter(feature => activeRecord(feature.properties.fips)?.status === "excluded").length;
      elements.coverage.textContent = `${available.toLocaleString()} comparable · ${excluded.toLocaleString()} excluded of ${features.length.toLocaleString()}`;
    } else {
      const notDesignated = features.filter(feature => activeRecord(feature.properties.fips)?.status === "not_designated").length;
      elements.coverage.textContent = `${available.toLocaleString()} of ${features.length.toLocaleString()} available`
        + (notDesignated ? ` · ${notDesignated.toLocaleString()} not designated` : "");
    }
  }

  function renderAllText() {
    renderLegend();
    renderFact();
    renderRankingReport();
    renderTable();
    updateMethod();
    updateNavigationText();
    updateCoverage();
    const dataset = activeDataset();
    elements.dockNote.textContent = isCompositeView()
      ? "Weights use counties with all selected values. Hard limits exclude counties before the comparison."
      : isTrendView()
      ? "The source sets the recent trend categories. They stay fixed when you focus on a state."
      : dataset?.note || "The same national scale remains in place when you focus on a state.";
  }

  function changeFamily() {
    app.family = elements.family.value;
    populateMeasures();
    withPendingData(() => {
      populateCounties();
      repaintMap();
      renderAllText();
      announce(`${metricTitle(activeDataset())} loaded. ${activeScaleAnnouncement(activeDataset())}`);
    });
  }

  function changeMeasure() {
    if (app.family === "cancer") {
      app.cancerId = elements.measure.value;
      populateSexes();
    } else if (app.family === "disasters") {
      app.disasterId = elements.measure.value;
    } else {
      app.selectedDatasetIds[app.family] = elements.measure.value;
    }
    withPendingData(() => {
      populateCounties();
      repaintMap();
      renderAllText();
      announce(`${metricTitle(activeDataset())} loaded. ${activeScaleAnnouncement(activeDataset())}`);
    });
  }

  function changeSex() {
    app.sexId = elements.sex.value;
    withPendingData(() => {
      populateCounties();
      repaintMap();
      renderAllText();
      announce(`${metricTitle(activeDataset())}, ${activeDataset()?.sex || "selected group"}, loaded. ${activeScaleAnnouncement(activeDataset())}`);
    });
  }

  function changeCancerView() {
    app.cancerView = elements.cancerView.value;
    repaintMap();
    renderAllText();
    announce(`${metricTitle(activeDataset())} loaded. ${activeScaleAnnouncement(activeDataset())}`);
  }

  function resetView() {
    cancelMapGesture();
    app.family = "cancer";
    app.cancerId = "001";
    app.sexId = "0";
    app.cancerView = "incidence";
    app.disasterId = "declarations";
    app.stateFips = "";
    app.countyFips = "";
    app.statePan = { x: 0, y: 0, k: 1 };
    app.stateZoomTarget = { x: 0, y: 0, k: 1 };
    elements.family.value = "cancer";
    elements.state.value = "";
    initializeDefaultRecipe();
    recomputeComposite();
    populateMeasures();
    populateCounties();
    renderFocusedState(true);
    resetNationalZoom(true);
    repaintMap();
    renderAllText();
    announce(`The map now shows all cancer sites across the lower 48. ${activeScaleAnnouncement(activeDataset())}`);
  }

  function goBack() {
    if (app.countyFips) {
      clearCounty(true);
    } else if (app.stateFips) {
      setState("", true);
      announce("The map now shows the national county view.");
    }
  }

  function announce(message) {
    elements.announcer.textContent = "";
    window.setTimeout(() => { elements.announcer.textContent = message; }, 20);
  }

  function attachEvents() {
    placeLegend();
    if (!elements.map.hasAttribute("tabindex")) elements.map.tabIndex = 0;
    elements.map.setAttribute("aria-keyshortcuts", "ArrowLeft ArrowRight ArrowUp ArrowDown");
    elements.family.addEventListener("change", changeFamily);
    elements.measure.addEventListener("change", changeMeasure);
    elements.sex.addEventListener("change", changeSex);
    elements.cancerView.addEventListener("change", changeCancerView);
    elements.recipeAddButton.addEventListener("click", addRecipeSignal);
    elements.recipeSave.addEventListener("click", saveRecipe);
    elements.recipeLoad.addEventListener("click", loadRecipe);
    elements.state.addEventListener("change", () => setState(elements.state.value, true));
    elements.county.addEventListener("change", () => selectCounty(elements.county.value, elements.county));
    elements.back.addEventListener("click", goBack);
    elements.reset.addEventListener("click", resetView);
    elements.zoomIn.addEventListener("click", () => zoomMapBy(1.6));
    elements.zoomOut.addEventListener("click", () => zoomMapBy(1 / 1.6));
    elements.zoomReset.addEventListener("click", fitCurrentMap);
    elements.map.addEventListener("wheel", handleMapWheel, { passive: false });
    elements.map.addEventListener("keydown", handleMapKeydown);
    elements.map.addEventListener("pointerdown", beginMapDrag);
    elements.map.addEventListener("pointermove", continueMapDrag);
    elements.map.addEventListener("pointerup", event => endMapDrag(event));
    elements.map.addEventListener("pointercancel", event => endMapDrag(event, true));
    elements.map.addEventListener("lostpointercapture", event => {
      // Ignore the county losing implicit capture when a drag captures the SVG.
      if (event.target === elements.map) endMapDrag(event, true);
    });
    window.addEventListener("blur", cancelMapGesture);
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) cancelMapGesture();
    });
    elements.map.addEventListener("pointerleave", event => {
      if (event.pointerType === "mouse" && !app.panActive) endMapDrag(event, true);
    });
    elements.map.addEventListener("click", suppressClickAfterDrag, true);
    elements.map.addEventListener("click", handleMapBackgroundClick);
    desktopLegend.addEventListener?.("change", placeLegend);
    document.addEventListener("silh:viewchange", () => { if (app.geo) repaintMap(); });
    window.addEventListener("resize", cancelMapGesture);
    window.addEventListener("resize", () => requestAnimationFrame(thinLegendTicks));
    elements.factClose.addEventListener("click", () => clearCounty(true));
    document.addEventListener("keydown", event => {
      if (event.key === "Escape" && app.countyFips) {
        event.preventDefault();
        clearCounty(true);
      }
    });
    prefersReducedMotion.addEventListener?.("change", () => {
      if (app.stateFips) {
        renderFocusedState(false);
      } else {
        animateNationalZoom(app.nationalZoomTarget);
      }
    });
  }

  function showError(error) {
    console.error(error);
    elements.message.hidden = false;
    elements.message.replaceChildren();
    const copy = document.createElement("div");
    const title = document.createElement("strong");
    const detail = document.createElement("p");
    title.textContent = "The county map did not load.";
    detail.textContent = "Check that the local data files and the D3 library are available. Then reload this page.";
    detail.style.margin = ".45rem 0 0";
    copy.append(title, detail);
    elements.message.append(copy);
    elements.coverage.textContent = "Load failed";
    announce("The county map did not load.");
  }

  // The geometry ships quantised and delta encoded: 474 KB gzipped against
  // 1,044 KB for the plain GeoJSON, with a worst positional error of 32 m.
  // A checkout without the encoded file still runs on the GeoJSON.
  async function loadGeometry() {
    if (window.GeometryDecode) {
      try {
        return window.GeometryDecode.decode(await d3.json("./data/counties.qd.json"));
      } catch (error) {
        console.warn("Encoded map shapes are unavailable. The map uses the GeoJSON data.", error);
      }
    }
    return d3.json("./data/counties.geojson");
  }

  function updateFamilyOptions() {
    const failures = [];
    ["community", "hazards", "healthcare", "employment", "broadband", "places", "air", "wildfire", "water", "traffic", "climate", "storms", "crime"].forEach(family => {
      const option = elements.family.querySelector(`option[value="${family}"]`);
      if (!option) return;
      const loaded = Boolean(app.data[family]?.datasets?.length);
      option.disabled = !loaded;
      option.textContent = loaded ? FAMILY_LABELS[family] : `${FAMILY_LABELS[family]} — unavailable`;
      if (!loaded) failures.push(`${FAMILY_LABELS[family]} did not load`);
    });
    const compositeOption = elements.family.querySelector('option[value="composite"]');
    if (compositeOption) {
      compositeOption.disabled = !window.AtlasComposite;
      compositeOption.textContent = window.AtlasComposite ? FAMILY_LABELS.composite : "My priorities — unavailable";
      if (!window.AtlasComposite) failures.push("My priorities did not start");
    }
    elements.sourceLoadStatus.hidden = !failures.length;
    elements.sourceLoadStatus.textContent = failures.length ? `${failures.join(". ")}. Available measures still work.` : "";
  }

  async function init() {
    attachEvents();
    elements.rankingMore.addEventListener("click", () => {
      rankingCache.limit += RANKING_PAGE;
      renderRankingReport();
    });
    try {
      const [geo, manifest] = await Promise.all([
        loadGeometry(),
        d3.json(`${LAYER_PATH}manifest.json`)
      ]);
      if (!geo?.features?.length || !manifest?.families) {
        throw new Error("Data files do not match the expected format.");
      }
      app.geo = { ...geo, features: geo.features.map(normalizeForD3) };
      ["cancer", "disasters", "community", "hazards", "healthcare", "employment", "broadband", "places", "air", "wildfire", "water", "traffic", "climate", "storms", "crime"].forEach(family => {
        const entry = manifest.families[family];
        if (entry?.datasets?.length) app.data[family] = entry;
        else app.optionalErrors[family] = new Error(`The manifest lists no datasets for ${family}.`);
      });
      if (!app.data.cancer?.datasets?.length || !app.data.disasters?.datasets?.length) {
        throw new Error("Data files do not match the expected format.");
      }
      updateFamilyOptions();
      elements.family.disabled = false;
      buildGeographyIndexes();
      initializeDefaultRecipe();
      // The default recipe inputs and the first measure shown are the only
      // records needed before the map can paint.
      await Promise.all(pendingDatasetRefs().map(entry => ensureDataset(entry[0], entry[1])));
      recomputeComposite();
      populateStates();
      populateMeasures();
      populateCounties();
      renderBaseMap();
      placeOverlays = window.AtlasOverlays?.create({
        svg: elements.map,
        state: () => app.stateFips,
        family: () => app.family,
        cancelGesture: cancelMapGesture,
        moving: () => app.panActive || app.zoomAnimating,
        suppressed: () => app.suppressMapClick || app.panActive || app.mapPointers.size > 0,
        contains: (coordinates, state) => {
          if (!Array.isArray(coordinates) || !coordinates.every(Number.isFinite)) return false;
          const features = state ? app.featuresByState.get(state) || [] : app.geo.features;
          return features.some(feature => d3.geoContains(feature, coordinates));
        },
        project: coordinates => app.projection(coordinates),
        view: () => {
          const base = app.stateFips ? focusBaseTransform(app.stateFips) : { x: 0, y: 0, k: 1 };
          const view = app.stateFips ? app.statePan : app.nationalZoom;
          return { x: view.x + base.x * view.k, y: view.y + base.y * view.k, k: base.k * view.k };
        },
        invert: event => {
          const p = d3.pointer(event, elements.map);
          const base = app.stateFips ? focusBaseTransform(app.stateFips) : { x: 0, y: 0, k: 1 };
          const view = app.stateFips ? app.statePan : app.nationalZoom;
          return app.projection.invert([((p[0] - view.x) / view.k - base.x) / base.k, ((p[1] - view.y) / view.k - base.y) / base.k]);
        }
      });
      renderAllText();
      elements.message.hidden = true;
      announce(`The map loaded ${app.geo.features.length.toLocaleString()} county boundaries. It shows ${metricTitle(activeDataset())}. ${activeScaleAnnouncement(activeDataset())}`);
    } catch (error) {
      showError(error);
    }
  }

  init();
})();
