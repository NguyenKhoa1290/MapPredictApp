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
        assert.ok((await page.locator('.assistant-window').boundingBox()).width >= 550);
        const messagesBefore = await page.locator('.assistant-messages').boundingBox();
        await page.locator('.assistant-model-picker summary').click();
        assert.deepEqual(await page.locator('.assistant-messages').boundingBox(), messagesBefore);
        assert.equal(await page.locator('.assistant-model-bolt, .assistant-effort-reset').count(), 0);
        await page.locator('.assistant-effort-slider').focus();
        await page.keyboard.press('ArrowRight');
        assert.equal(await page.locator('.assistant-effort').inputValue(), 'low');
        await page.selectOption('.assistant-mode', 'smart');
        await page.locator('.assistant-effort-slider').focus();
        await page.keyboard.press('End');
        assert.equal(await page.locator('.assistant-effort').inputValue(), 'high');
        assert.equal(await page.locator('.assistant-passcode-label').isVisible(), true);
        await page.keyboard.press('Home');
        assert.equal(await page.locator('.assistant-effort-slider').inputValue(), '0');
        await page.screenshot({ path: 'tmp/assistant-model-picker.png' });
        await page.setViewportSize({ width: 390, height: 844 });
        const card = await page.locator('.assistant-model-card').boundingBox();
        assert.ok(card.width < 390 && card.x >= 0 && card.x + card.width <= 390);
        assert.equal(card.width, 250);
        const trigger = await page.locator('.assistant-model-picker summary').boundingBox();
        const send = await page.locator('.assistant-form button[type="submit"]').boundingBox();
        assert.ok(Math.abs(trigger.y - send.y) < 10);
        await page.keyboard.press('Escape');
        assert.equal(await page.locator('.assistant-effort-slider').isVisible(), false);
        assert.equal(await page.locator('#assistant-window').isVisible(), true);
        await page.locator('.assistant-model-picker summary').click();
        await page.locator('.assistant-header strong').click();
        assert.equal(await page.locator('.assistant-effort-slider').isVisible(), false);
        assert.deepEqual(errors, []);
        console.log('PASS compact popup beside Send, wider chat, keyboard effort, passcode, mobile, Escape and outside click');
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
