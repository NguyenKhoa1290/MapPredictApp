const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

(async () => {
    const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true });
    try {
        const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.route('**/api/v1/assistant/status', route => route.fulfill({ json: { data: { enabled: true,
            modes: [{ id: 'fast', efforts: ['auto', 'low'] }, { id: 'smart', efforts: ['auto', 'low', 'medium', 'high'], requires_passcode: true }]
        } } }));
        await page.goto(new URL('/portal/assessment', process.env.WORKSPACE_TEST_URL).href);
        await page.waitForFunction(() => window.workspacePersistence?.ready);
        await page.locator('.assistant-launcher').click();
        await page.locator('.assistant-model-picker summary').click();
        await page.locator('.assistant-effort-slider').focus();
        await page.keyboard.press('ArrowRight');
        assert.equal(await page.locator('.assistant-effort').inputValue(), 'low');
        await page.selectOption('.assistant-mode', 'smart');
        await page.locator('.assistant-effort-slider').focus();
        await page.keyboard.press('End');
        assert.equal(await page.locator('.assistant-effort').inputValue(), 'high');
        assert.equal(await page.locator('.assistant-passcode-label').isVisible(), true);
        await page.locator('.assistant-effort-reset').click();
        assert.equal(await page.locator('.assistant-effort-slider').inputValue(), '0');
        await page.screenshot({ path: 'tmp/assistant-model-picker.png' });
        await page.setViewportSize({ width: 390, height: 844 });
        const card = await page.locator('.assistant-model-card').boundingBox();
        assert.ok(card.width < 390 && card.x >= 0 && card.x + card.width <= 390);
        await page.locator('.assistant-model-picker summary').click();
        assert.equal(await page.locator('.assistant-effort-slider').isVisible(), false);
        assert.deepEqual(errors, []);
        console.log('PASS model card, keyboard effort, reset, passcode, mobile and collapse');
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
