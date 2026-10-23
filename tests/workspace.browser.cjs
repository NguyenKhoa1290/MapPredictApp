// Run against an isolated Flask server: WORKSPACE_TEST_URL and PLAYWRIGHT_MODULE.
const assert = require("node:assert/strict");
const path = require("node:path");
const { execFileSync } = require("node:child_process");
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const root = path.resolve(__dirname, "..");
const url = process.env.WORKSPACE_TEST_URL;
if (!url) throw new Error("WORKSPACE_TEST_URL must point to a disposable test server, not user data.");
const python = process.env.PYTHON || path.join(root, "venv", "Scripts", "python.exe");
const dxf = execFileSync(python, ["-c", `
import ezdxf,io
d=ezdxf.new(); d.layers.new('a'); d.layers.new('b'); m=d.modelspace()
for i in range(4):
 x=515100+i*20; y=2402100
 m.add_lwpolyline([(x,y),(x+20,y),(x+20,y+20),(x,y+20)],close=True,dxfattribs={'layer':'a' if i%2==0 else 'b'})
 m.add_text(str(i+1),dxfattribs={'insert':(x+5,y+5)})
s=io.StringIO(); d.write(s); print(s.getvalue())
`]);

async function initialized(page) {
    await page.waitForFunction(() => window.workspacePersistence?.ready);
}
async function save(page) {
    assert.equal(await page.evaluate(async () => {
        workspacePersistence.schedule(); return workspacePersistence.flush();
    }), true);
}
async function state(page) {
    return page.evaluate(() => ({
        cad: cadFiles.map(e => ({ id: e.id, name: e.file.name, size: e.file.size })),
        prediction: predictionFiles.map(e => ({ id: e.id, name: e.file.name, columns: e.columns })),
        inputs: ["csv-file", "model-file", "scaler-file", "result-file"].map(id => [...$(id).files].map(f => f.name)),
        offsets: [...document.querySelectorAll('[name="cad_offset_x"], [name="cad_offset_y"]')].map(e => e.value),
        predictionOffsets: [$("prediction-offset-x").value, $("prediction-offset-y").value],
        joins: [$("gpkg-join").value, $("csv-join").value],
        layers: overlays.map(o => ({ id: o.id, features: o.item.data.features, opacity: o.opacity, visible: o.visible,
            style: o.style, adjustments: o.adjustments, groups: [...o.groups].map(([k,g]) => [k,{visible:g.visible,style:g.style}]),
            colors: o.records.map(r => [r.layer.options.color,r.layer.options.fillColor]) })),
        table: predictionView, results: predictionRows, crs: sharedSourceCrs(),
        center: [map.getCenter().lat,map.getCenter().lng], zoom: map.getZoom(),
        tab: $("map-panel").hidden, basemap: activeBasemap, labels: $("basemap-labels").checked,
        selectedLayerId, inspectorScope,
    }));
}

(async () => {
    const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || "C:/Program Files/Google/Chrome/Application/chrome.exe", headless: true });
    try {
        const context = await browser.newContext({ viewport: { width: 1500, height: 1000 } });
        const page = await context.newPage();
        const errors = [];
        const apiCalls = [];
        page.on("pageerror", error => errors.push(error.message));
        page.on("request", request => { if (request.url().includes("/api/")) apiCalls.push(new URL(request.url()).pathname); });
        await page.goto(url);
        await initialized(page);
        assert.equal(await page.evaluate(() => overlays.length), 0);
        await page.selectOption("#project-crs", "EPSG:9208");
        await page.setInputFiles("#cad-file", { name: "base.dxf", mimeType: "application/dxf", buffer: dxf });
        await page.locator('[name="cad_offset_x"]').fill("12.5");
        await page.locator('[name="cad_offset_y"]').fill("-3.25");
        await page.locator(".prediction-layer-options summary").click();
        await page.setInputFiles("#layer-file", { name: "grid.dxf", mimeType: "application/dxf", buffer: dxf });
        await page.waitForFunction(() => predictionFiles[0]?.columns);
        await page.locator("#prediction-offset-x").fill("25");
        await page.locator("#prediction-offset-y").fill("30");
        await page.click("#predict-tab");
        const csv = "id,x1,x2,x3,x4,x5,x6,x7,x8,x9\n" + [1,2,3,4].map(i=>`${i},0,0,0,0,0,0,0,0,0`).join("\n");
        await page.setInputFiles("#csv-file", { name: "input.csv", mimeType: "text/csv", buffer: Buffer.from(csv) });
        await page.setInputFiles("#model-file", path.join(root, "rf_model_rating.pkl"));
        await page.setInputFiles("#scaler-file", path.join(root, "scaler_bds.pkl"));
        await page.click("#predict-button");
        await page.waitForFunction(() => predictionRows.length === 4 && predictionView?.isResult);
        await page.click("#map-tab");
        await page.selectOption("#csv-join", "id");
        await page.click("#map-button");
        await page.waitForFunction(() => overlays.length === 2);
        await page.locator(".layer-select").first().click();
        await page.selectOption("#style-scope", "a");
        await page.uncheck("#style-source");
        await page.locator("#style-stroke").fill("#123456");
        await page.locator("#style-stroke").dispatchEvent("input");
        await page.locator("#style-weight").fill("3.5");
        await page.locator("#style-weight").dispatchEvent("input");
        await page.locator("#adjust-invert").fill("70");
        await page.locator("#adjust-invert").dispatchEvent("input");
        await page.locator("#component-list input[type=checkbox]").first().uncheck();
        await page.locator("#layer-opacity-0").fill("42");
        await page.locator("#layer-opacity-0").dispatchEvent("input");
        await page.uncheck("#layer-visible-1");
        await page.selectOption("#basemap-select", "streets");
        assert.equal(await page.locator("#basemap-labels").isDisabled(),true);
        await page.evaluate(() => { map.stop(); map.setView([21.72,104.90],18,{animate:false}); });
        await page.click("#predict-tab");
        await save(page);
        const before = await state(page);
        const countBeforeReload = apiCalls.length;
        await page.reload();
        await initialized(page);
        assert.deepEqual(await state(page), before);
        assert.deepEqual(apiCalls.slice(countBeforeReload), []); // No automatic model/map POST or server results overwrite.
        assert.deepEqual(errors, []);
        console.log("PASS: files/models, data, offsets, CRS, groups/colors/hue/invert, visibility, view and active tab survive reload without API calls");

        // A new tab in the same browser sees the saved workspace too.
        const newTab = await context.newPage();
        await newTab.goto(url); await initialized(newTab);
        assert.deepEqual(await state(newTab), before);
        await newTab.close();

        await page.click("#map-tab");
        // Restored model result rows are supplied explicitly on the next map update.
        await page.evaluate(() => {
            const original = window.fetch;
            window.fetch = (input, options) => {
                if (String(input) === "/api/map") window.testResultFilename = options.body.get("result")?.name;
                return original(input, options);
            };
        });
        const responsePromise = page.waitForResponse(r => r.url().endsWith("/api/map"));
        await page.click("#map-button");
        const response = await responsePromise;
        assert.equal(response.status(),200);
        assert.equal(await page.evaluate(()=>window.testResultFilename),"KetQua.csv");
        await page.waitForFunction(() => overlays.length === 2 && overlays[1].item.data.join_summary.matched === 4);
        console.log("PASS: restored source blobs can be uploaded again and cached prediction results remain joinable");

        // Persist an explicit result file, remove one source, and do not resurrect it.
        const columnsResponse = page.waitForResponse(r => r.url().endsWith("/api/result-columns"));
        await page.setInputFiles("#result-file", { name:"results.csv", mimeType:"text/csv", buffer:Buffer.from("id,Y\n1,0\n2,1\n3,2\n4,2\n") });
        await columnsResponse;
        await page.locator("#cad-options .source-remove").click();
        await save(page); await page.reload(); await initialized(page);
        assert.equal(await page.evaluate(() => cadFiles.length),0);
        assert.equal(await page.evaluate(() => overlays.length),1);
        assert.equal(await page.locator("#result-file").evaluate(e=>e.files[0].name),"results.csv");
        console.log("PASS: removed layers stay removed; explicit result CSV is restored");

        // Failure paths: quota errors retain the last committed snapshot.
        await save(page);
        const committed = await state(page);
        await page.evaluate(() => { WorkspaceStore.prototype.write = () => Promise.reject(new DOMException("forced", "QuotaExceededError")); });
        await page.evaluate(() => { predictionFiles[0].joinColumn="handle"; workspacePersistence.schedule(); });
        assert.equal(await page.evaluate(()=>workspacePersistence.flush()),false);
        assert.ok((await page.locator("#workspace-save-status").textContent()).includes("dung lượng"));
        await page.reload(); await initialized(page);
        assert.deepEqual(await state(page),committed);
        console.log("PASS: quota failure reports unsaved changes and keeps last good snapshot");

        await page.locator("#prediction-offset-x").fill("44");
        await page.waitForFunction(() => $("workspace-save-status").textContent === "Đã lưu trên trình duyệt");
        await page.reload(); await initialized(page);
        assert.equal(await page.locator("#prediction-offset-x").inputValue(),"44");
        console.log("PASS: autosave persists input changes without pressing Save");

        const storageTests = await page.evaluate(async () => {
            const first = new WorkspaceStore(indexedDB,"workspace-test-atomic");
            await first.read();
            const original = new Map([["blob",new Blob(["original"])]]);
            await first.write({schema:1,value:"good"},original);
            const stale = new WorkspaceStore(indexedDB,"workspace-test-atomic"); await stale.read();
            let assetWrites=0;
            const put=IDBObjectStore.prototype.put;
            IDBObjectStore.prototype.put=function(...args){if(this.name==="assets")assetWrites++;return put.apply(this,args);};
            await first.write({schema:1,value:"new"},original);
            IDBObjectStore.prototype.put=put;
            let conflict=false;try{await stale.write({value:"stale"},original);}catch(e){conflict=e.name==="WorkspaceConflictError";}
            let aborted=false;try{await first.write({value:"bad"},new Map([["bad",()=>{}]]));}catch{aborted=true;}
            const final=await first.read();
            return {assetWrites,conflict,aborted,value:final.state.value,blob:await final.assets.get("blob").text()};
        });
        assert.deepEqual(storageTests,{assetWrites:0,conflict:true,aborted:true,value:"new",blob:"original"});
        console.log("PASS: atomic rollback, cross-tab revision protection, and no repeated large-asset writes");

        const lastRevision = await page.evaluate(async()=>{
            const store=new WorkspaceStore(); const saved=await store.read();
            const tx=store.db.transaction("assets","readwrite");
            tx.objectStore("assets").delete(`layer:${saved.state.layers[0].id}`);
            await new Promise((resolve,reject)=>{tx.oncomplete=resolve;tx.onabort=reject;});
            return saved.state.revision;
        });
        await page.reload();
        await page.waitForFunction(()=>$("workspace-save-status").classList.contains("text-danger"));
        assert.equal(await page.evaluate(()=>workspacePersistence.ready),false);
        assert.equal(await page.evaluate(async()=>{const s=new WorkspaceStore();return(await s.read()).state.revision;}),lastRevision);
        console.log("PASS: incomplete/corrupt snapshots are not replaced by an empty workspace");
        await context.close();
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode=1; });
