const test = require('node:test');
const assert = require('node:assert/strict');
const colors = require('../wwwroot/color_adjustments.js');

test('neutral settings preserve exact source colors', () => {
    for (const color of ['#000000', '#ffffff', '#AbCdEf', '#123', '#334155']) {
        assert.equal(colors.apply(color), color);
        assert.equal(colors.apply(color, colors.defaults), color);
    }
});

test('saturation zero produces known weighted grayscale values', () => {
    assert.equal(colors.apply('#ff0000', { saturation: 0 }), '#363636');
    assert.equal(colors.apply('#00ff00', { saturation: 0 }), '#b6b6b6');
    assert.equal(colors.apply('#0000ff', { saturation: 0 }), '#121212');
});

test('hue uses the reference matrix and gray remains gray', () => {
    assert.equal(colors.apply('#ff0000', { hue: 90 }), '#005b00');
    assert.equal(colors.apply('#ff0000', { hue: 180 }), '#006d6d');
    for (const color of ['#000000', '#444444', '#888888', '#ffffff']) {
        assert.equal(colors.apply(color, { hue: 127, saturation: 200 }), color);
    }
});

test('brightness scales colors and clamps at the channel limits', () => {
    assert.equal(colors.apply('#804020', { brightness: 50 }), '#402010');
    assert.equal(colors.apply('#804020', { brightness: 200 }), '#ff8040');
    assert.equal(colors.apply('#abcdef', { brightness: 0 }), '#000000');
});

test('contrast centers on middle gray and can lift black', () => {
    assert.equal(colors.apply('#abcdef', { contrast: 0 }), '#808080');
    assert.equal(colors.apply('#000000', { contrast: 50 }), '#404040');
    assert.equal(colors.apply('#ffffff', { contrast: 50 }), '#bfbfbf');
    assert.equal(colors.apply('#000000', { contrast: 200 }), '#000000');
    assert.equal(colors.apply('#ffffff', { contrast: 200 }), '#ffffff');
});

test('operation order is hue, saturation, brightness, contrast', () => {
    assert.equal(colors.apply('#ff0000', { hue: 90, saturation: 0, brightness: 0, contrast: 0 }), '#808080');
});

test('short hex expands correctly; unsupported values are left alone', () => {
    assert.equal(colors.apply('#f00', { saturation: 0 }), '#363636');
    for (const color of ['transparent', 'none', '#nothex', '', null, undefined]) {
        assert.equal(colors.apply(color, { hue: 90 }), color);
    }
});

test('normalization clamps values, handles missing/invalid settings and ignores extra keys', () => {
    assert.deepEqual(colors.normalize({ hue: 720, contrast: -10, brightness: '150', saturation: Infinity, ignored: 4 }),
        { hue: 180, saturation: 100, brightness: 150, contrast: 0, invert: 0 });
    assert.deepEqual(colors.normalize(null), colors.defaults);
    assert.deepEqual(colors.normalize({ hue: NaN }), colors.defaults);
});

test('source colors/settings are not mutated and repeated application from source is stable', () => {
    const settings = { hue: 45, saturation: 125, brightness: 110, contrast: 80 };
    const snapshot = JSON.stringify(settings);
    const source = '#a45b73';
    const first = colors.apply(source, settings);
    for (let index = 0; index < 100; ++index) assert.equal(colors.apply(source, settings), first);
    assert.equal(JSON.stringify(settings), snapshot);
    assert.equal(colors.apply(source, colors.defaults), source);
    assert.equal(Object.isFrozen(colors.defaults), true);
});

test('extreme combinations always generate bounded hex colors', () => {
    for (const hue of [-180, 0, 180]) {
        for (const amount of [0, 100, 200]) {
            assert.match(colors.apply('#d035a1', { hue, saturation: amount, brightness: amount, contrast: amount }), /^#[0-9a-f]{6}$/);
        }
    }
});

test('full inversion swaps black/white and complements every RGB channel', () => {
    assert.equal(colors.apply('#000000', { invert: 100 }), '#ffffff');
    assert.equal(colors.apply('#ffffff', { invert: 100 }), '#000000');
    assert.equal(colors.apply('#123456', { invert: 100 }), '#edcba9');
    assert.equal(colors.apply('#f00', { invert: 100 }), '#00ffff');
    assert.equal(colors.apply(colors.apply('#123456', { invert: 100 }), { invert: 100 }), '#123456');
});

test('partial inversion blends continuously and 50 percent gives middle gray', () => {
    assert.equal(colors.apply('#000000', { invert: 25 }), '#404040');
    assert.equal(colors.apply('#ffffff', { invert: 25 }), '#bfbfbf');
    for (const color of ['#000000', '#ffffff', '#123456', '#ff8000']) {
        assert.equal(colors.apply(color, { invert: 50 }), '#808080');
    }
});

test('inversion is clamped to 0..100 and defaults to zero', () => {
    assert.equal(colors.normalize({ invert: 200 }).invert, 100);
    assert.equal(colors.normalize({ invert: -20 }).invert, 0);
    assert.equal(colors.normalize({ invert: Infinity }).invert, 0);
    assert.equal(colors.normalize({}).invert, 0);
});

test('inversion runs after the existing adjustments', () => {
    assert.equal(colors.apply('#ff0000', { brightness: 0, invert: 100 }), '#ffffff');
    assert.equal(colors.apply('#abcdef', { contrast: 0, invert: 100 }), '#808080');
});
