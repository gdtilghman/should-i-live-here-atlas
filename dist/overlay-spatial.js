// Pure spatial helpers for the atlas location overlays.
//
// This file is intentionally dependency-free and side-effect-free: it only
// performs arithmetic on plain data so the parent app can call it from the
// browser (window.AtlasOverlaySpatial) or from Node/CommonJS. Nothing here
// touches the DOM, the network or any global state.
//
// clusterPoints groups viewport-space plant markers with deterministic screen
// grid bucketing. normalizeCustomPins sanitizes a persisted array of user pins
// into a bounded, typed shape. Both never mutate their inputs and never throw
// on malformed JSON-compatible structures.

(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.AtlasOverlaySpatial = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var DEFAULT_CELL_SIZE = 40;
  var DEFAULT_PADDING = 20;

  var MAX_PINS = 100;
  var MAX_ID = 80;
  var MAX_LABEL = 100;
  var MAX_NOTES = 1000;

  var LON_MIN = -180;
  var LON_MAX = 180;
  var LAT_MIN = -90;
  var LAT_MAX = 90;

  function isFiniteNumber(value) {
    return typeof value === "number" && Number.isFinite(value);
  }

  function isPositiveNumber(value) {
    return isFiniteNumber(value) && value > 0;
  }

  function isNonNegativeNumber(value) {
    return isFiniteNumber(value) && value >= 0;
  }

  // Order members by id first so the output does not depend on the input
  // ordering; break ties on position so duplicate ids stay deterministic too.
  function compareEntries(a, b) {
    var ai = String(a.id);
    var bi = String(b.id);
    if (ai < bi) return -1;
    if (ai > bi) return 1;
    if (a.x < b.x) return -1;
    if (a.x > b.x) return 1;
    if (a.y < b.y) return -1;
    if (a.y > b.y) return 1;
    return 0;
  }

  // Groups points into deterministic screen-grid cells. Each returned cluster
  // carries the arithmetic mean of its members, the original member objects and
  // the member count. Singletons are kept as count 1. Points with non-finite
  // coordinates or lying outside the padded viewport are ignored. Buckets in O(n); deterministic sorting is O(n log n) worst case.
  // No pairwise spatial comparisons between points.
  function clusterPoints(points, options) {
    try {
      if (!Array.isArray(points)) return [];
      if (options === null || typeof options !== "object") return [];

      var width = options.width;
      var height = options.height;
      var cellSize = options.cellSize === undefined ? DEFAULT_CELL_SIZE : options.cellSize;
      var padding = options.padding === undefined ? DEFAULT_PADDING : options.padding;

      if (!isPositiveNumber(width) || !isPositiveNumber(height)) return [];
      if (!isPositiveNumber(cellSize) || !isNonNegativeNumber(padding)) return [];

      var minX = -padding;
      var maxX = width + padding;
      var minY = -padding;
      var maxY = height + padding;

      var cells = new Map();

      for (var i = 0; i < points.length; i++) {
        var point = points[i];
        if (point === null || typeof point !== "object") continue;

        var x, y, id;
        try {
          x = point.x;
          y = point.y;
          id = point.id;
        } catch (err) {
          continue;
        }

        if (!isFiniteNumber(x) || !isFiniteNumber(y)) continue;
        if (x < minX || x > maxX || y < minY || y > maxY) continue;

        var cx = Math.floor(x / cellSize);
        var cy = Math.floor(y / cellSize);
        var key = cx + ":" + cy;

        var cell = cells.get(key);
        if (!cell) {
          cell = { cx: cx, cy: cy, entries: [] };
          cells.set(key, cell);
        }
        cell.entries.push({ point: point, x: x, y: y, id: id });
      }

      var ordered = [];
      cells.forEach(function (cell) { ordered.push(cell); });
      ordered.sort(function (a, b) {
        return (a.cx - b.cx) || (a.cy - b.cy);
      });

      var clusters = new Array(ordered.length);
      for (var c = 0; c < ordered.length; c++) {
        var current = ordered[c];
        var entries = current.entries.slice();
        entries.sort(compareEntries);

        var sumX = 0;
        var sumY = 0;
        var members = new Array(entries.length);
        for (var m = 0; m < entries.length; m++) {
          sumX += entries[m].x;
          sumY += entries[m].y;
          members[m] = entries[m].point;
        }

        clusters[c] = {
          id: "cell:" + current.cx + ":" + current.cy,
          x: sumX / entries.length,
          y: sumY / entries.length,
          count: entries.length,
          members: members
        };
      }

      return clusters;
    } catch (err) {
      return [];
    }
  }

  // Reads one candidate pin, returning a fresh sanitized object or null when the
  // entry is invalid. Strings are kept as text; callers are expected to render
  // them with textContent. Unknown fields are dropped.
  function readPin(raw) {
    var id = raw.id;
    if (typeof id !== "string") return null;
    id = id.trim();
    if (id.length === 0 || id.length > MAX_ID) return null;

    var label = raw.label;
    if (typeof label !== "string") return null;
    label = label.trim();
    if (label.length === 0 || label.length > MAX_LABEL) return null;

    var notes = raw.notes;
    if (notes === undefined || notes === null) notes = "";
    else if (typeof notes !== "string") return null;
    if (notes.length > MAX_NOTES) return null;

    var longitude = raw.longitude;
    if (!isFiniteNumber(longitude) || longitude < LON_MIN || longitude > LON_MAX) return null;

    var latitude = raw.latitude;
    if (!isFiniteNumber(latitude) || latitude < LAT_MIN || latitude > LAT_MAX) return null;

    return {
      id: id,
      label: label,
      notes: notes,
      longitude: longitude,
      latitude: latitude
    };
  }

  // Sanitizes a parsed persisted array into at most MAX_PINS valid pins.
  // Non-arrays yield []. Invalid entries are dropped, duplicate ids keep the
  // first occurrence, and the original value is never mutated. Coordinate
  // strings, NaN and Infinity are rejected. No geographic region is assumed
  // beyond the global coordinate ranges.
  function normalizeCustomPins(value) {
    try {
      if (!Array.isArray(value)) return [];

      var out = [];
      var seen = Object.create(null);

      for (var i = 0; i < value.length && out.length < MAX_PINS; i++) {
        var raw;
        try {
          raw = value[i];
        } catch (err) {
          continue;
        }
        if (raw === null || typeof raw !== "object") continue;

        var pin;
        try {
          pin = readPin(raw);
        } catch (err) {
          continue;
        }
        if (!pin) continue;
        if (seen[pin.id] === true) continue;

        seen[pin.id] = true;
        out.push(pin);
      }

      return out;
    } catch (err) {
      return [];
    }
  }

  return {
    clusterPoints: clusterPoints,
    normalizeCustomPins: normalizeCustomPins
  };
});