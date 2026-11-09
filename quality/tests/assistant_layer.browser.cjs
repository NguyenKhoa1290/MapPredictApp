// Optional real-browser regression: WORKSPACE_TEST_URL and DXF_TEST_FILE required.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

(async () => {
    const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true });
    try {
        const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
        page.setDefaultTimeout(60000);
        const errors = [], requests = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.route('**/api/v1/assistant/status', route => route.fulfill({ json: { data: { enabled: true, modes: [{ id: 'fast', efforts: ['auto', 'low'] }] } } }));
        await page.route('**/api/v1/assistant/preview', route => {
            const body = route.request().postDataBuffer().toString(); requests.push(body);
            const compact = /name="compact"\r\n\r\ntrue/.test(body);
            return route.fulfill({ json: { data: {
                answer: compact ? 'Summary of green layer styling' : 'Change selected component width and color',
                layer_patch: compact ? null : { style: { color: '#ff0000', weight: 4, east: 20, north: -10 } },
                context: { used: 1800, limit: 30000, estimated: true },
                edits: [], scores: [], sources: [], table_edits: [], rejected: [], token: null, scope: 'Selected layer'
            } } });
        });
        await page.goto(new URL('/portal/assessment', process.env.WORKSPACE_TEST_URL).href);
        await page.waitForFunction(() => window.workspacePersistence?.ready);
        await page.selectOption('#project-crs', 'EPSG:9208');
        const filename = process.env.DXF_TEST_FILE;
        assert.ok(filename && fs.existsSync(filename), 'Set DXF_TEST_FILE to the real drawing');
        await page.setInputFiles('#cad-file', filename);
        await page.click('#map-button');
        await page.waitForFunction(() => window.assessmentRuntime.state.overlays.length > 0);
        await page.locator('.layer-select').first().click();
        await page.locator('#component-list button').filter({ hasText: /^net \(/ }).click();
        assert.equal(await page.locator('#assistant-window').isVisible(), true);
        assert.match(await page.locator('.assistant-header small').innerText(), /net/);
        const before = await page.evaluate(() => {
            const c = assistantWorkspace.context();
            return { c, style: structuredClone(assessmentRuntime.state.overlays[0].groups.get('net').style),
                fileSize: assessmentRuntime.state.cadFiles[0].file.size,
                other: structuredClone(assessmentRuntime.state.overlays[0].groups.get('KYHIEU').style),
                coordinate: assessmentRuntime.state.overlays[0].records.find(r => r.group === 'net').layer.getLatLngs()[0],
                sourceGeometry: structuredClone(assessmentRuntime.state.overlays[0].records.find(r => r.group === 'net').feature.geometry),
                otherCoordinate: assessmentRuntime.state.overlays[0].records.find(r => r.group === 'KYHIEU').layer.getLatLngs()[0] };
        });
        assert.equal(before.c.resources.length, 0);
        assert.equal(before.c.layerContext.component, 'net');
        assert.ok(before.c.layerContext.count > 0); // A CAD polyline may become multiple rendered records.
        assert.ok(JSON.stringify(before.c).length < 16000);
        await page.fill('#assistant-question', 'Change net to red and width 4');
        await page.locator('.assistant-form button[type="submit"]').click();
        await page.waitForFunction(() => assistantWorkspace.hasDraft() && !assistantWorkspace.historyState().busy);
        assert.equal(await page.evaluate(() => assessmentRuntime.state.overlays[0].groups.get('net').style.color), '#ff0000');
        assert.deepEqual(await page.evaluate(() => assessmentRuntime.state.overlays[0].groups.get('KYHIEU').style), before.other);
        assert.equal(await page.evaluate(() => assessmentRuntime.state.cadFiles[0].file.size), before.fileSize);
        const position = await page.evaluate(before => {
            const overlay = assessmentRuntime.state.overlays[0];
            const current = overlay.records.find(r => r.group === 'net').layer.getLatLngs()[0];
            const start = L.CRS.EPSG3857.project(L.latLng(before.coordinate));
            const moved = L.CRS.EPSG3857.project(current);
            const scale = Math.cos(overlay.translationLatitude * Math.PI / 180);
            return { east: (moved.x - start.x) * scale, north: (moved.y - start.y) * scale,
                current, other: overlay.records.find(r => r.group === 'KYHIEU').layer.getLatLngs()[0] };
        }, before);
        assert.ok(Math.abs(position.east - 20) < 0.00001);
        assert.ok(Math.abs(position.north + 10) < 0.00001);
        assert.deepEqual(position.other, before.otherCoordinate);
        await page.evaluate(() => {
            const ctx = assessmentRuntime.state;
            ctx.refreshManagedLayer(ctx.overlays[0]);
            ctx.refreshManagedLayer(ctx.overlays[0]);
        });
        assert.deepEqual(await page.evaluate(() => assessmentRuntime.state.overlays[0].records.find(r => r.group === 'net').layer.getLatLngs()[0]), position.current);
        assert.deepEqual(await page.evaluate(() => assessmentRuntime.state.overlays[0].records.find(r => r.group === 'net').feature.geometry), before.sourceGeometry);
        assert.doesNotMatch(requests[0], /filename=|name="dxf"/);
        assert.ok(requests[0].length < 20000);
        await page.locator('.assistant-preview button').first().click();
        await page.waitForFunction(() => !assistantWorkspace.hasDraft() && !assistantWorkspace.historyState().busy);
        await page.evaluate(() => assistantWorkspace.travel('undo'));
        assert.deepEqual(await page.evaluate(() => assessmentRuntime.state.overlays[0].groups.get('net').style), before.style);
        assert.deepEqual(await page.evaluate(() => assessmentRuntime.state.overlays[0].records.find(r => r.group === 'net').layer.getLatLngs()[0]), before.coordinate);
        await page.evaluate(() => assistantWorkspace.travel('redo'));
        await page.locator('.assistant-context').click();
        await page.waitForFunction(() => document.querySelector('.assistant-messages').textContent.includes('Summary'));
        assert.equal(await page.locator('.assistant-message').count(), 1);
        const circle = await page.locator('.assistant-context').boundingBox();
        assert.equal(circle.width, circle.height);
        await page.reload();
        await page.waitForFunction(() => window.workspacePersistence?.ready);
        assert.equal(await page.evaluate(() => assessmentRuntime.state.overlays[0].groups.get('net').style.color), '#ff0000');
        assert.deepEqual(await page.evaluate(() => assessmentRuntime.state.overlays[0].records.find(r => r.group === 'net').layer.getLatLngs()[0]), position.current);
        assert.equal(await page.locator('.assistant-message').count(), 1);
        assert.deepEqual(errors, []);
        console.log(`PASS ${path.basename(filename)}: selected component only, no DXF upload, preview/undo/redo/reload, circular context and compact`);
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
