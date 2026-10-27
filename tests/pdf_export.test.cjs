const test = require("node:test");
const assert = require("node:assert/strict");
const { fitPage, intersects, missingTiles } = require("../wwwroot/pdf_export.js");

test("landscape map fits a single printable A4 area without changing aspect", () => {
    const size = fitPage(1600, 900);
    assert.ok(size.width <= 281 && size.height <= 166);
    assert.equal(size.width / size.height, 1600 / 900);
    assert.ok(Math.abs(size.scale * 1600 * 25.4 / 96 - size.width) < 1e-9);
});
test("portrait and square viewports remain fully visible rather than cropped", () => {
    for (const [width, height] of [[800, 1400], [900, 900]]) {
        const size = fitPage(width, height);
        assert.equal(size.height, 166);
        assert.ok(size.width <= 281);
        assert.ok(Math.abs(size.width / size.height - width / height) < 1e-9);
    }
});
test("invalid or hidden map sizes are rejected", () => {
    for (const [w,h] of [[0,1],[1,0],[-1,4],[NaN,2],[2,Infinity]]) assert.throws(()=>fitPage(w,h));
});
test("tile bounds intersect only the visible viewport", () => {
    const viewport = {left:0,top:0,right:100,bottom:100};
    assert.equal(intersects({left:90,top:90,right:110,bottom:110},viewport),true);
    assert.equal(intersects({left:100,top:0,right:120,bottom:20},viewport),false);
    assert.equal(intersects({left:-50,top:10,right:-1,bottom:20},viewport),false);
});
test("missing tile warning counts only missing visible tiles, not keepBuffer", () => {
    const tile = (left,complete,naturalWidth) => ({
        matches:()=>false, querySelector:()=>({complete,naturalWidth}),
        getBoundingClientRect:()=>({left,top:0,right:left+20,bottom:20}),
    });
    const container = {getBoundingClientRect:()=>({left:0,top:0,right:100,bottom:100}),
        querySelectorAll:()=>[tile(0,true,256),tile(20,false,0),tile(40,true,0),tile(120,false,0)]};
    assert.equal(missingTiles(container),2);
});
