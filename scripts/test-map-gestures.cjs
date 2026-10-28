'use strict';
// Exercise the shipped functions without a production-only test interface.
// Browser touch/capture behavior is checked separately against the rendered UI.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../dist/app.js'), 'utf8');
function section(start, end) {
  const a = source.indexOf(`  function ${start}`);
  const b = source.indexOf(`  function ${end}`, a);
  assert.ok(a >= 0 && b > a, `missing gesture section ${start}`);
  return source.slice(a, b);
}
function setup(stateFips = '') {
  const captures = new Set(), classes = new Set();
  const calls = { setState: [], announce: [] };
  const app = { geo: {}, path: { bounds: () => [[0, 0], [1100, 650]] },
    stateFips, nationalZoom: { x: 0, y: 0, k: 1 }, statePan: { x: 0, y: 0, k: 1 },
    mapPointers: new Map(), mapDrag: null, panActive: false, suppressMapClick: false,
    mapBackgroundPress: false };
  const map = { hasPointerCapture: id => captures.has(id),
    setPointerCapture: id => captures.add(id), releasePointerCapture: id => captures.delete(id),
    classList: { add: x => classes.add(x), remove: x => classes.delete(x) } };
  const context = { app, elements: { map, focus: {} }, WIDTH: 1100, HEIGHT: 650,
    // A 550px map uses two SVG units per CSS pixel.
    d3: { pointer: e => [e.clientX * 2, e.clientY * 2], select: () => ({ style() { return this; } }) },
    hideTooltip() {}, stopStateZoom() {}, stopNationalZoom() {},
    focusBaseTransform: () => ({ x: 0, y: 0, k: 1, bounds: [[0, 0], [1100, 650]] }),
    setNationalZoomTransform: t => { app.nationalZoom = t; },
    setStatePanTransform: t => { app.statePan = t; },
    setState: (fips, animate) => { calls.setState.push([fips, animate]); app.stateFips = fips; },
    announce: message => { calls.announce.push(message); } };
  vm.createContext(context);
  vm.runInContext(section('constrainNationalZoom', 'setNationalZoomTransform') +
    section('constrainStatePan', 'focusTransform') + section('mapGesturePoints', 'fitCurrentMap'), context);
  const event = (id, x, y, type = 'touch', button = 0, target = map) => ({ pointerId: id, pointerType: type,
    clientX: x, clientY: y, button, target, preventDefault() { this.prevented = true; } });
  const press = (id, x, y, type, button, target) => context.beginMapDrag(event(id, x, y, type, button, target));
  const move = (id, x, y) => context.continueMapDrag(event(id, x, y));
  const end = (id, cancelled = false) => context.endMapDrag(event(id, 0, 0), cancelled);
  const mapClick = (target = map) => ({ detail: 1, clientX: 0, clientY: 0, button: 0,
    target, preventDefault() {}, stopImmediatePropagation() {} });
  const view = () => stateFips ? app.statePan : app.nationalZoom;
  return { app, captures, classes, calls, context, event, press, move, end, mapClick, view };
}

test('touch jitter remains a tap; drag threshold uses CSS pixels', () => {
  const h = setup(); h.press(1, 200, 150); h.move(1, 203, 152);
  assert.equal(h.app.panActive, false); assert.equal(h.captures.size, 0);
  h.end(1); assert.equal(h.app.suppressMapClick, false);
  h.press(2, 200, 150); h.move(2, 206, 150);
  assert.equal(h.view().x, 12); assert.equal(h.app.panActive, true);
  h.end(2); assert.equal(h.app.panActive, false); assert.equal(h.captures.size, 0);
  assert.equal(h.app.suppressMapClick, true);
});

for (const stateFips of ['', '06']) {
  test(`${stateFips || 'national'} pinch anchors its midpoint and follows centroid translation`, () => {
    const h = setup(stateFips); h.press(1, 200, 150); h.press(2, 300, 150);
    h.move(1, 170, 160); h.move(2, 370, 160);
    assert.equal(h.view().k, 2); assert.equal(h.view().x, -460); assert.equal(h.view().y, -280);
    assert.equal(h.app.panActive, true); assert.equal(h.captures.size, 2);
    h.end(2); const before = { ...h.view() }; h.move(1, 180, 165);
    assert.equal(h.view().k, before.k); assert.equal(h.view().x, before.x + 20);
    assert.equal(h.view().y, before.y + 10); h.end(1);
    assert.equal(h.app.suppressMapClick, true); assert.equal(h.classes.size, 0);
  });
  test(`${stateFips || 'national'} pinch clamps scale at 1 and 8`, () => {
    const h = setup(stateFips); h.press(1, 200, 150); h.press(2, 300, 150);
    h.move(1, -5000, 150); assert.equal(h.view().k, 8);
    h.move(1, 299, 150); assert.equal(h.view().k, 1);
    assert.ok(Number.isFinite(h.view().x)); assert.ok(Number.isFinite(h.view().y));
  });
}

test('one-to-two-to-one and a third finger rebase without jumps', () => {
  const h = setup(); h.press(1, 200, 150); h.move(1, 220, 150);
  let before = JSON.stringify(h.view()); h.press(2, 300, 150);
  assert.equal(JSON.stringify(h.view()), before);
  h.move(2, 330, 150); h.press(3, 260, 180); before = JSON.stringify(h.view());
  h.move(3, 270, 185); assert.equal(JSON.stringify(h.view()), before);
  h.end(1); assert.equal(JSON.stringify(h.view()), before);
  h.move(2, 340, 150); assert.ok(Number.isFinite(h.view().k)); h.end(2); h.end(3);
  assert.equal(h.app.mapPointers.size, 0); assert.equal(h.app.panActive, false);
});

test('cancellation and view changes release captures and ignore stale moves', () => {
  for (const cancel of [h => h.end(1, true), h => h.context.cancelMapGesture(),
    h => { h.app.stateFips = '06'; h.move(1, 250, 150); }]) {
    const h = setup(); h.press(1, 200, 150); h.press(2, 300, 150); h.move(1, 180, 150);
    cancel(h); const before = JSON.stringify(h.view()); h.move(2, 400, 150);
    assert.equal(JSON.stringify(h.view()), before); assert.equal(h.captures.size, 0);
    assert.equal(h.app.mapPointers.size, 0); assert.equal(h.app.mapDrag, null);
    assert.equal(h.app.panActive, false); assert.equal(h.classes.size, 0);
  }
});

test('late pointer clicks stay suppressed until a fresh press; keyboard clicks work', () => {
  const h = setup(); h.press(1, 200, 150); h.move(1, 220, 150); h.end(1);
  function click(detail) { const e = { detail, prevented: false,
    preventDefault() { this.prevented = true; }, stopImmediatePropagation() {} };
    h.context.suppressClickAfterDrag(e); return e.prevented; }
  assert.equal(click(1), true); assert.equal(click(1), true); assert.equal(click(0), false);
  h.press(2, 200, 150); h.end(2); assert.equal(click(1), false);
});

test('left mouse dragging remains supported; right mouse and mixed input are ignored', () => {
  const h = setup(); h.press(1, 200, 150, 'mouse', 2); assert.equal(h.app.mapPointers.size, 0);
  h.press(1, 200, 150, 'mouse'); h.press(2, 220, 150, 'touch');
  assert.equal(h.app.mapPointers.size, 1); h.move(1, 220, 160);
  assert.equal(h.view().x, 40); assert.equal(h.view().y, 20); h.end(1);
  assert.equal(h.app.panActive, false);
});

test('coincident touch points do not create an invalid transform', () => {
  const h = setup(); h.press(1, 200, 150); h.press(2, 200, 150);
  h.move(2, 220, 150); h.move(2, 230, 150);
  assert.ok(Number.isFinite(h.view().k)); assert.ok(Number.isFinite(h.view().x));
});

test('empty background press then click returns a focused state to the national view', () => {
  const h = setup('06'); h.press(1, 200, 150, 'mouse'); h.end(1);
  assert.equal(h.app.mapBackgroundPress, true);
  h.context.handleMapBackgroundClick(h.mapClick());
  assert.deepEqual(h.calls.setState, [['', false]]);
  assert.deepEqual(h.calls.announce, ['The map now shows the national county view.']);
  assert.equal(h.app.mapBackgroundPress, false);
});

test('a county press and release never navigates back', () => {
  const h = setup('06'); const county = { fips: '06075' };
  h.press(1, 200, 150, 'mouse', 0, county); h.end(1);
  assert.equal(h.app.mapBackgroundPress, false);
  h.context.handleMapBackgroundClick(h.mapClick());
  assert.equal(h.calls.setState.length, 0); assert.equal(h.calls.announce.length, 0);
});

test('a stale background flag cannot return on a county click', () => {
  const h = setup('06'); h.press(1, 200, 150, 'mouse'); h.end(1);
  h.context.handleMapBackgroundClick(h.mapClick({ fips: '06075' }));
  assert.equal(h.app.mapBackgroundPress, false);
  assert.equal(h.calls.setState.length, 0); assert.equal(h.calls.announce.length, 0);

  h.press(2, 210, 160, 'mouse'); h.end(2);
  h.context.handleMapBackgroundClick(h.mapClick());
  assert.deepEqual(h.calls.setState, [['', false]]);
  assert.deepEqual(h.calls.announce, ['The map now shows the national county view.']);
});

test('empty background clicks in the national view are harmless', () => {
  const h = setup(''); h.press(1, 200, 150, 'mouse'); h.end(1);
  h.context.handleMapBackgroundClick(h.mapClick());
  assert.equal(h.calls.setState.length, 0);
});

test('drag, pinch, cancellation and delayed clicks suppress the background return', () => {
  const drag = setup('06'); drag.press(1, 200, 150, 'mouse'); drag.move(1, 260, 150);
  assert.equal(drag.app.panActive, true); assert.equal(drag.app.mapBackgroundPress, false);
  drag.end(1); drag.context.handleMapBackgroundClick(drag.mapClick());
  assert.equal(drag.calls.setState.length, 0);

  const pinch = setup('06'); pinch.press(1, 200, 150); pinch.press(2, 300, 150);
  assert.equal(pinch.app.mapBackgroundPress, false);
  pinch.end(2); pinch.end(1); pinch.context.handleMapBackgroundClick(pinch.mapClick());
  assert.equal(pinch.calls.setState.length, 0);

  const cancelled = setup('06'); cancelled.press(1, 200, 150, 'mouse');
  cancelled.end(1, true); cancelled.context.handleMapBackgroundClick(cancelled.mapClick());
  assert.equal(cancelled.calls.setState.length, 0);

  const blurred = setup('06'); blurred.press(1, 200, 150, 'mouse');
  blurred.context.cancelMapGesture(); blurred.context.handleMapBackgroundClick(blurred.mapClick());
  assert.equal(blurred.calls.setState.length, 0);
});

test('a fresh deliberate empty press works after an interruption', () => {
  const h = setup('06'); h.press(1, 200, 150, 'mouse'); h.move(1, 260, 150); h.end(1);
  h.context.handleMapBackgroundClick(h.mapClick());
  assert.equal(h.calls.setState.length, 0);
  h.press(2, 210, 160, 'mouse'); h.end(2);
  assert.equal(h.app.mapBackgroundPress, true);
  h.context.handleMapBackgroundClick(h.mapClick());
  assert.deepEqual(h.calls.setState, [['', false]]);
});
