// Uses a fresh browser context so existing user workspaces are never changed.
const assert = require('node:assert/strict');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname, '..');
const server = process.env.WORKSPACE_TEST_URL;
if (!server) throw new Error('WORKSPACE_TEST_URL is required');
const dxf = execFileSync(process.env.PYTHON || path.join(root, 'venv/Scripts/python.exe'), ['-c', `
import ezdxf,io
d=ezdxf.new();m=d.modelspace();m.add_lwpolyline([(515100,2402100),(515120,2402100),(515120,2402120),(515100,2402120)],close=True)
s=io.StringIO();d.write(s);print(s.getvalue())
`]);
const ready = page => page.waitForFunction(() => window.workspacePersistence?.ready);
const reload = async page => { await page.reload(); await ready(page); };
const textOf = (page, id) => page.evaluate(async id => $(id).files[0]?.text(), id);
(async () => {
    const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true });
    try {
        const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
        const page = await context.newPage();
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.goto(new URL('/legacy/?embedded=1', server).href);
        await ready(page);
        // Repeated clean flushes used to permanently block subsequent writes.
        await page.evaluate(async () => { await workspacePersistence.flush(); await workspacePersistence.flush(); });
        await page.selectOption('#project-crs', 'EPSG:9208');
        await page.setInputFiles('#cad-file', { name: 'base.dxf', mimeType: 'application/dxf', buffer: dxf });
        await page.click('#map-button');
        await page.waitForFunction(() => overlays.length === 1);
        await page.evaluate(async () => {
            const original = cadFiles[0].file;
            const edited = new File([(await original.text()).replaceAll('515120', '515140')], 'edited.dxf', { type: 'application/dxf' });
            await assistantWorkspace.stage({ sourceId: cadFiles[0].id, original, dxf: edited });
        });
        await reload(page);
        assert.equal(await page.evaluate(() => cadFiles[0].file.name), 'edited.dxf');
        assert.equal(await page.evaluate(() => assistantWorkspace.hasDraft()), true);
        assert.equal(await page.evaluate(() => overlays.length), 1);
        await page.click('.assistant-launcher');
        await page.click('[data-review="discard"]');
        await page.waitForFunction(() => !assistantWorkspace.hasDraft() && !assistantWorkspace.historyState().busy);
        await reload(page);
        assert.equal(await page.evaluate(() => cadFiles[0].file.name), 'base.dxf');
        console.log('PASS DXF draft survives reload and can be discarded');
        await page.evaluate(async () => {
            const original = cadFiles[0].file;
            await assistantWorkspace.stage({ sourceId: cadFiles[0].id, original,
                dxf: new File([(await original.text()).replaceAll('515120', '515140')], 'edited.dxf') });
            await assistantWorkspace.confirm();
        });
        await reload(page);
        assert.equal(await page.evaluate(() => cadFiles[0].file.name), 'edited.dxf');
        assert.match(await page.evaluate(() => cadFiles[0].file.text()), /515140/);
        assert.equal(await page.evaluate(() => assistantWorkspace.hasDraft()), false);
        await page.evaluate(() => assistantWorkspace.travel('undo'));
        await reload(page);
        assert.equal(await page.evaluate(() => cadFiles[0].file.name), 'base.dxf');
        await page.evaluate(() => assistantWorkspace.travel('redo'));
        await reload(page);
        assert.equal(await page.evaluate(() => cadFiles[0].file.name), 'edited.dxf');
        assert.equal(await page.evaluate(() => overlays.length), 1);
        console.log('PASS edited DXF and rendered layer survive confirmation, undo, redo and reload');

        await page.click('#predict-tab');
        await page.setInputFiles('#csv-file', { name: 'input.csv', mimeType: 'text/csv', buffer: Buffer.from('id,x1\n1,2\n') });
        await page.waitForFunction(() => predictionView.rows[0]?.x1 === '2');
        await page.evaluate(async () => {
            await assistantWorkspace.stage({ rows: [{ id: '1', x1: 7 }], columns: ['id', 'x1'] });
        });
        await reload(page);
        assert.equal(await page.evaluate(() => predictionView.rows[0].x1), 7);
        assert.match(await textOf(page, 'csv-file'), /"1","7"/);
        assert.equal(await page.evaluate(() => assistantWorkspace.hasDraft()), true);
        await page.click('.assistant-launcher');
        await page.click('[data-review="confirm"]');
        await page.waitForFunction(() => !assistantWorkspace.hasDraft());
        await reload(page);
        assert.equal(await page.evaluate(() => predictionView.rows[0].x1), 7);
        assert.equal(await page.evaluate(() => assistantWorkspace.hasDraft()), false);
        await page.evaluate(() => assistantWorkspace.travel('undo'));
        await reload(page);
        assert.equal(await page.evaluate(() => predictionView.rows[0].x1), '2');
        await page.evaluate(() => assistantWorkspace.travel('redo'));
        await reload(page);
        assert.equal(await page.evaluate(() => predictionView.rows[0].x1), 7);
        console.log('PASS CSV draft, confirmation, undo and redo survive reload');

        await page.click('[data-remove-csv="csv-file"]');
        await page.waitForFunction(() => !$('csv-file').files.length);
        await reload(page);
        assert.equal(await page.evaluate(() => $('csv-file').files.length), 0);
        assert.equal(await page.evaluate(() => predictionView.rows.length), 0);
        assert.equal(await page.locator('[data-remove-csv="csv-file"]').isVisible(), false);
        await page.click('#map-tab');
        await page.locator('.prediction-layer-options summary').click();
        await page.setInputFiles('#result-file', { name: 'result.csv', mimeType: 'text/csv', buffer: Buffer.from('id,Y\n1,2\n') });
        await page.waitForFunction(() => !resultColumnsLoading);
        await page.click('[data-remove-csv="result-file"]');
        await reload(page);
        assert.equal(await page.evaluate(() => $('result-file').files.length), 0);
        assert.deepEqual(errors, []);
        console.log('PASS CSV removal survives reload, no browser JavaScript errors');
        await page.click('#predict-tab');
        await page.route('**/api/v1/assistant/preview', route => route.fulfill({ json: { data: {
            answer: 'Tạo bảng YB1', sources: [], edits: [], scores: [], table_edits: [],
            token: 'browser-test', create_table: true, row_count: 1, rejected: [], scope: 'prediction',
        } } }));
        await page.route('**/api/v1/assistant/apply', route => route.fulfill({ json: { data: {
            dxfs: [], rows: [{ id: 'YB1', x1: '' }], columns: ['id', 'x1'],
        } } }));
        await page.click('.assistant-launcher');
        await page.fill('#assistant-question', 'Tạo bảng YB1');
        await page.press('#assistant-question', 'Enter');
        await page.waitForFunction(() => assistantWorkspace.hasDraft() && !assistantWorkspace.historyState().busy);
        await page.locator('.assistant-preview button').first().click({ timeout: 10000 });
        await page.waitForFunction(() => !assistantWorkspace.hasDraft());
        console.log('PASS chat-created CSV draft can be confirmed immediately without reload');
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
