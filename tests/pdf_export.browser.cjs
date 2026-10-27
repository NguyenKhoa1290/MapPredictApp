// Isolated local server only; Playwright creates one test PDF, not user output.
const assert = require("node:assert/strict");
const path = require("node:path");
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const serverUrl = process.env.PDF_TEST_URL;
if (!serverUrl) throw new Error("PDF_TEST_URL must point to an isolated Flask test server.");
const url = new URL('/legacy/?embedded=1', serverUrl).href;

(async()=>{
    const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||"C:/Program Files/Google/Chrome/Application/chrome.exe",headless:true});
    try {
        const context=await browser.newContext({viewport:{width:1500,height:950},deviceScaleFactor:2});
        const failed=[];context.on("requestfailed",request=>failed.push({url:request.url().slice(0,140),error:request.failure()}));
        // Deliberately no CORS headers: DOM printing must still include the raster.
        await context.route(/https:\/\/.*(arcgisonline\.com|tile\.openstreetmap\.org)\/.*/,route=>route.fulfill({
            status:200,contentType:"image/svg+xml",body:'<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"><rect width="256" height="256" fill="#e5ecd6"/><path d="M0 256L256 0M0 128L128 0M128 256L256 128" stroke="#d4debd" stroke-width="4"/></svg>'
        }));
        const page=await context.newPage();const errors=[];page.on("pageerror",e=>errors.push(e.message));
        await page.goto(url);await page.waitForFunction(()=>workspacePersistence.ready);
        await page.selectOption("#project-crs","EPSG:9208");
        await page.evaluate(()=>{
            const poly=(x,y,s=.003)=>({type:"Polygon",coordinates:[[[x,y],[x+s,y],[x+s,y+s],[x,y+s],[x,y]]]});
            const item=(id,geometry,color)=>({source_id:id,name:id,kind:"prediction",crs:"EPSG:9208",data:{type:"FeatureCollection",features:[{type:"Feature",geometry,properties:{grid_id:id,Y:2,fillColor:color,fillOpacity:.65}}]}});
            renderMap([item("VisibleGrid",poly(104.8965,21.7185),"#008000"),item("HiddenGrid",poly(104.900,21.72),"#ff0000")]);
        });
        await page.locator(".layer-select").first().click();
        await page.uncheck("#layer-visible-1");
        await page.selectOption("#basemap-select","streets");
        await page.evaluate(()=>{map.stop();map.setView([21.72,104.90],17,{animate:false});L.popup().setLatLng([21.72,104.90]).setContent("HIDDEN_POPUP").openOn(map);});
        await page.waitForFunction(()=>Object.values(basemapLayers.streets._tiles).filter(t=>t.current).every(t=>t.loaded&&t.el.firstChild.naturalWidth>0));
        const before=await page.evaluate(()=>({center:map.getCenter(),zoom:map.getZoom(),visible:overlays.map(o=>o.visible),count:overlays.length}));
        const popupPromise=page.waitForEvent("popup");await page.click("#map-export-pdf");const popup=await popupPromise;
        try { await popup.waitForFunction(()=>document.documentElement.dataset.pdfReady==="true",null,{timeout:15000}); }
        catch(error) {
            console.error("PRINT_DIAGNOSTIC",await popup.locator("body").textContent(),await page.locator("#map-export-status").textContent(),errors);
            throw error;
        }
        assert.equal(await popup.locator("[data-map-snapshot]").count(),1);
        assert.ok(await popup.locator("[data-map-canvas]").count()>0);
        assert.equal(await popup.locator("canvas,.leaflet-control-container,.leaflet-popup-pane,#layer-inspector,.map-sidebar").count(),0);
        assert.ok((await popup.locator(".source-credits").textContent()).includes("OpenStreetMap"));
        assert.ok((await popup.locator(".map-meta").textContent()).includes("9208"));
        if(await popup.locator(".map-warning").textContent()) console.error("IMAGE_DIAGNOSTIC",await popup.evaluate(()=>[...document.images].filter(image=>!image.naturalWidth).slice(0,5).map(image=>({src:image.src.slice(0,100),complete:image.complete}))),failed.slice(-8));
        assert.equal(await popup.locator(".map-warning").textContent(),"");
        await popup.pdf({path:path.join(__dirname,"../tmp/pdfs/map-visible-test.pdf"),preferCSSPageSize:true,printBackground:true,displayHeaderFooter:false});
        assert.deepEqual(await page.evaluate(()=>({center:map.getCenter(),zoom:map.getZoom(),visible:overlays.map(o=>o.visible),count:overlays.length})),before);
        await popup.close();
        console.log("PASS: one-page export snapshot retains raster without CORS, visible canvas layers and attribution, excludes sidebar/controls, leaves live map unchanged");

        // Missing background must require consent, then carry a visible warning.
        await page.evaluate(()=>{
            const tile=Object.values(basemapLayers.streets._tiles).find(t=>t.current);
            tile.el.firstChild.onload=tile.el.firstChild.onerror=null;tile.el.firstChild.removeAttribute("src");
        });
        page.once("dialog",dialog=>dialog.dismiss());await page.click("#map-export-pdf");assert.equal(context.pages().length,1);
        page.once("dialog",dialog=>dialog.accept());const partialPromise=page.waitForEvent("popup");await page.click("#map-export-pdf");const partial=await partialPromise;
        await partial.waitForFunction(()=>document.documentElement.dataset.pdfReady==="true");
        assert.ok((await partial.locator(".map-warning").textContent()).includes("chưa tải đủ"));await partial.close();
        await page.evaluate(()=>{window.testOriginalOpen=window.open;window.open=()=>null;});
        page.once("dialog",dialog=>dialog.accept());await page.click("#map-export-pdf");
        assert.ok((await page.locator("#map-export-status").textContent()).includes("chặn"));
        await page.evaluate(()=>{window.open=window.testOriginalOpen;});
        await page.click("#predict-tab");assert.equal(await page.locator("#map-export-pdf").isDisabled(),true);
        await page.click("#map-tab");assert.equal(await page.locator("#map-export-pdf").isDisabled(),false);
        assert.deepEqual(errors,[]);
        console.log("PASS: missing-tile cancel/consent, PDF warning and blocked-popup feedback; export disabled outside map tab; no JS errors");
        await context.close();
    }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
