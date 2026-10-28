// Decoder for the quantized-delta geometry produced by scripts/build-geometry.py.
//
// The encoder puts every coordinate on an integer grid and stores the change
// from the previous point instead of the point itself. That is what makes the
// file compress: small integers that mostly repeat. Decoding is just running
// the deltas back up and undoing the grid.
//
// Keep this in step with the reference decoder in scripts/build-geometry.py.
// A node test compares the two against the original GeoJSON.

(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.GeometryDecode = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var RING_DEPTH = { Polygon: 1, MultiPolygon: 2 };

  function decodeRing(flat, sx, sy, tx, ty) {
    var ring = new Array(flat.length / 2);
    var x = 0;
    var y = 0;
    for (var i = 0, j = 0; i < flat.length; i += 2, j++) {
      x += flat[i];
      y += flat[i + 1];
      ring[j] = [x * sx + tx, y * sy + ty];
    }
    return ring;
  }

  function decodeCoords(node, depth, sx, sy, tx, ty) {
    if (depth === 0) return decodeRing(node, sx, sy, tx, ty);
    var out = new Array(node.length);
    for (var i = 0; i < node.length; i++) {
      out[i] = decodeCoords(node[i], depth - 1, sx, sy, tx, ty);
    }
    return out;
  }

  // Returns a normal GeoJSON FeatureCollection, so nothing downstream needs to
  // know the file was encoded.
  function decode(doc) {
    if (!doc || doc.format !== "quantized-delta-v1") {
      throw new Error("Unsupported geometry format: " + (doc && doc.format));
    }
    var tx = doc.translate[0];
    var ty = doc.translate[1];
    var sx = doc.scale[0];
    var sy = doc.scale[1];
    var keys = doc.properties;

    var features = new Array(doc.features.length);
    for (var i = 0; i < doc.features.length; i++) {
      var item = doc.features[i];
      var depth = RING_DEPTH[item.t];
      if (depth === undefined) throw new Error("Unsupported geometry type: " + item.t);
      var props = {};
      for (var k = 0; k < keys.length; k++) props[keys[k]] = item.p[k];
      features[i] = {
        type: "Feature",
        properties: props,
        geometry: { type: item.t, coordinates: decodeCoords(item.c, depth, sx, sy, tx, ty) }
      };
    }
    return { type: "FeatureCollection", features: features };
  }

  return { decode: decode };
});
