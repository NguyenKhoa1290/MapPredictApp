const test = require("node:test");
const assert = require("node:assert/strict");
const { MAX_ZOOM, tileRequest, createFallbackLayer } = require("../wwwroot/basemaps.js");
const url = "https://example.test/{z}/{y}/{x}?blankTile=false";

function fixture(options = {}, coords = { z: 19, x: 414917, y: 229730 }) {
    const events = [];
    const listeners = {};
    const L = { GridLayer: { extend(methods) {
        return class {
            constructor(options) { this.options = options; Object.assign(this, methods); }
            getTileSize() { return { x: 256, y: 256 }; }
            on(name, handler) { listeners[name] = handler; }
            fire(name, data) { events.push({ name, ...data }); }
        };
    } } };
    global.document = { createElement(tag) {
        return { tag, style: {}, children: [], append(child) { this.children.push(child); },
            removeAttribute(key) { delete this[key]; } };
    } };
    const layer = createFallbackLayer(L, url, options);
    const completions = [];
    const tile = layer.createTile(coords, (...args) => completions.push(args));
    return { layer, tile, image: tile.children[0], events, listeners, completions };
}

test("native tile URL preserves Esri missing-coverage detection", () => {
    assert.deepEqual(tileRequest(url, { z: 19, x: 414917, y: 229730 }), {
        url: "https://example.test/19/229730/414917?blankTile=false",
        size: 256, left: -0, top: -0,
    });
});
test("parent fallback crops the correct half rather than repeating a tile", () => {
    assert.deepEqual(tileRequest(url, { z: 19, x: 414917, y: 229730 }, 1), {
        url: "https://example.test/18/114865/207458?blankTile=false",
        size: 512, left: -256, top: -0,
    });
});
test("deeper ancestor cropping keeps the same geographic position", () => {
    const request = tileRequest(url, { z: 19, x: 414919, y: 229731 }, 2);
    assert.equal(request.size, 1024);
    assert.equal(request.left, -768);
    assert.equal(request.top, -768);
    assert.equal(request.url, "https://example.test/17/57432/103729?blankTile=false");
});
test("raster native zoom is capped while vectors may zoom to 22", () => {
    const { layer } = fixture();
    assert.equal(layer.options.nativeMaxZoom, 19);
    assert.equal(layer.options.maxNativeZoom, undefined);
    assert.equal(layer.options.maxZoom, MAX_ZOOM);
    assert.equal(MAX_ZOOM, 22);
});
test("zoom 22 is cropped in display tiles even with Leaflet 3D disabled", () => {
    const { image } = fixture({}, { z: 22, x: 3319342, y: 1837842 });
    assert.equal(image.src, "https://example.test/19/229730/414917?blankTile=false");
    assert.equal(image.style.width, "2048px");
    assert.equal(image.style.left, "-1536px");
    assert.equal(image.style.top, "-512px");
    image.onerror();
    assert.equal(image.src, "https://example.test/18/114865/207458?blankTile=false");
    assert.equal(image.style.width, "4096px");
    assert.equal(image.style.left, "-3584px");
});
test("available native tile loads without fallback", () => {
    const { image, tile, completions, events } = fixture();
    image.onload();
    assert.deepEqual(completions, [[null, tile]]);
    assert.deepEqual(events, []);
});
test("missing tile retries parent and reports successful fallback", () => {
    const { image, tile, completions, events } = fixture();
    image.onerror();
    assert.equal(image.src, "https://example.test/18/114865/207458?blankTile=false");
    assert.equal(image.style.width, "512px");
    assert.equal(image.style.left, "-256px");
    image.onload();
    assert.equal(events[0].name, "tilefallback");
    assert.equal(events[0].depth, 1);
    assert.deepEqual(completions, [[null, tile]]);
});
test("failed network is bounded, not an infinite retry", () => {
    const { image, tile, completions } = fixture({ fallbackDepth: 2 });
    image.onerror(); image.onerror(); image.onerror();
    assert.equal(completions.length, 1);
    assert.ok(completions[0][0] instanceof Error);
    assert.equal(completions[0][1], tile);
});
test("unloaded tiles cancel retries and ignore late callbacks", () => {
    const { image, tile, listeners, completions } = fixture();
    const lateError = image.onerror;
    const lateLoad = image.onload;
    listeners.tileunload({ tile });
    assert.equal(image.src, undefined);
    assert.equal(image.onload, null);
    assert.equal(image.onerror, null);
    lateError(); lateLoad();
    assert.equal(image.src, undefined);
    assert.equal(completions.length, 0);
});
