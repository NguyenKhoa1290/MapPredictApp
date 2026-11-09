// Optional full flow against the running local server and user-provided fixtures.
const assert = require('node:assert/strict');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

(async () => {
    const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true });
    try {
        const page = await browser.newPage({ viewport: { width: 1500, height: 1000 } });
        page.setDefaultTimeout(60000);
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.goto(new URL('/portal/assessment', process.env.WORKSPACE_TEST_URL).href);
        await page.waitForFunction(() => window.workspacePersistence?.ready);
        await page.selectOption('#project-crs', 'EPSG:9208');
        await page.locator('details').filter({ has: page.locator('#layer-file') }).evaluate(element => { element.open = true; });
        await page.setInputFiles('#layer-file', process.env.DXF_TEST_FILE);
        await page.waitForFunction(() => window.assessmentRuntime.state.predictionFiles.every(file => file.columns));
        await page.click('#map-button');
        await page.waitForFunction(() => window.assessmentRuntime.state.overlays.length === 1);
        assert.equal(await page.evaluate(() => window.assessmentRuntime.state.overlays[0].records.every(record => record.layer.options.fillOpacity === 0)), true);
        await page.click('#predict-tab');
        await page.setInputFiles('#csv-file', process.env.CSV_TEST_FILE);
        await page.waitForFunction(() => window.assessmentRuntime.state.predictionView?.rows.length > 0);
        await page.click('#predict-button');
        await page.waitForFunction(() => window.assessmentRuntime.state.predictionRows.some(row => row.Y != null));
        await page.click('#map-tab');
        await page.selectOption('#csv-join', 'TenLoDat');
        await page.selectOption('#join-mode', 'numeric');
        await page.click('#map-button');
        await page.locator('#join-apply').waitFor({ state: 'visible' });
        await page.click('#join-apply');
        const inspect = () => page.evaluate(() => {
            const overlay = window.assessmentRuntime.state.overlays[0];
            const matched = overlay.records.filter(record => record.feature.properties.Y != null);
            const blank = overlay.records.filter(record => record.feature.properties.Y == null);
            return { matched: matched.length, blank: blank.length,
                painted: matched.every(record => record.layer.options.fillOpacity === 0.6 && record.layer.options.fillColor === record.feature.properties.fillColor),
                outline: blank.every(record => record.layer.options.fillOpacity === 0) };
        });
        assert.deepEqual(await inspect(), { matched: 338, blank: 19, painted: true, outline: true });
        await page.evaluate(() => window.workspacePersistence.flush());
        await page.reload();
        await page.waitForFunction(() => window.workspacePersistence?.ready && window.assessmentRuntime?.state.overlays.length === 1);
        assert.deepEqual(await inspect(), { matched: 338, blank: 19, painted: true, outline: true });
        await page.screenshot({ path: path.join('tmp', 'prediction-fill.png') });
        assert.deepEqual(errors, []);
        console.log('PASS real DXF upload, CSV prediction, join preview, 338 painted cells, 19 outlines and reload persistence');
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
