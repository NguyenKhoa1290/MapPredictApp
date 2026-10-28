const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { JSDOM } = require('../frontend/node_modules/jsdom');
const script = fs.readFileSync(require('node:path').join(__dirname, '../wwwroot/assistant.js'), 'utf8');
const tick = () => new Promise(resolve => setTimeout(resolve, 5));
const vm = require('node:vm');
const historyContext = vm.createContext({ Blob, structuredClone });
vm.runInContext(fs.readFileSync(require('node:path').join(__dirname, '../wwwroot/workspace_store.js'), 'utf8'), historyContext);
const WorkspaceHistory = historyContext.WorkspaceHistory;

test('real workspace restores DXF, empty CSV input and table across confirm undo redo', async () => {
    const path = require('node:path');
    const read = name => fs.readFileSync(path.join(__dirname, '..', name), 'utf8');
    const html = read('templates/index.html').replace(/<script\b[^>]*>[\s\S]*?<\/script>/g, '')
        .replace(/{%[^%]*%}/g, '');
    const dom = new JSDOM(html, { url: 'http://localhost/legacy/', runScripts: 'outside-only' });
    const w = dom.window;
    try {
        w.structuredClone = function clone(value) {
            if (!value || typeof value !== 'object' || value instanceof w.Blob) return value;
            if (value instanceof w.Map) return new w.Map([...value].map(([key, item]) => [key, clone(item)]));
            if (Array.isArray(value)) return value.map(clone);
            return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, clone(item)]));
        };
        const files = new WeakMap();
        Object.defineProperty(w.HTMLInputElement.prototype, 'files', {
            get() { return files.get(this) || []; }, set(value) { files.set(this, value); } });
        w.DataTransfer = class { constructor() { this.files = []; this.items = { add: file => this.files.push(file) }; } };
        w.File.prototype.arrayBuffer = function () {
            return new Promise(resolve => { const reader = new w.FileReader(); reader.onload = () => resolve(reader.result); reader.readAsArrayBuffer(this); });
        };
        w.HTMLElement.prototype.scrollTo = () => {};
        w.URL.createObjectURL = () => 'blob:test'; w.URL.revokeObjectURL = () => {};
        w.fetch = async () => { throw new Error('Unexpected network request'); };
        const code = [read('wwwroot/workspace_store.js'),
            `window.WorkspaceStore = class { async read() { return null; } async write(state, assets) { window.savedWorkspace = structuredClone({state, assets}); } };`,
            read('wwwroot/join_preview.js'), read('wwwroot/color_adjustments.js'), read('wwwroot/app.js'),
            read('wwwroot/layer_manager.js'), read('wwwroot/workspace.js'),
            `window.seedResources = () => { cadFiles = [{id:'cad-1',key:'original',file:new File(['old DXF'],'base.dxf')}]; updateCadOptions(); };
             window.inspectResources = () => ({name:cadFiles[0].file.name, table:predictionView, csv:$('csv-file').files[0]});`].join('\n');
        w.eval(code);
        for (let i = 0; i < 40 && !w.workspacePersistence.ready; i++) await tick();
        assert.equal(w.workspacePersistence.ready, true);
        w.seedResources();
        const originalCheckpoint = w.workspacePersistence.checkpoint();
        await w.assistantWorkspace.stage({ sourceId: 'cad-1', original: w.assistantWorkspace.sources()[0].file,
            dxf: new w.File(['new DXF'], 'base_edited.dxf'), rows: [{ id: '1', x1: 5 }] });
        assert.equal(w.inspectResources().table.rows[0].x1, 5);
        assert.equal(w.inspectResources().name, 'base_edited.dxf');
        assert.equal(w.savedWorkspace.state.inputs['csv-file'], undefined);
        assert.equal(w.document.querySelector('.map-sidebar').inert, true);
        w.assistantWorkspace.confirm();
        await w.workspacePersistence.flush();
        assert.equal(w.savedWorkspace.assets.get('table:view').rows[0].x1, 5);
        w.document.querySelector('[data-action="undo"]').click();
        await tick();
        assert.equal(w.inspectResources().name, 'base.dxf');
        assert.equal(w.inspectResources().csv, undefined);
        assert.equal(w.inspectResources().table.rows.length, 0);
        const undoCheckpoint = w.workspacePersistence.checkpoint();
        for (const key of Object.keys(originalCheckpoint.state)) {
            if (['view', 'tab', 'details', 'inspector', 'basemap', 'labels'].includes(key)) continue;
            assert.equal(JSON.stringify(undoCheckpoint.state[key]), JSON.stringify(originalCheckpoint.state[key]), key);
        }
        w.document.querySelector('[data-action="redo"]').click();
        await tick();
        assert.equal(w.inspectResources().name, 'base_edited.dxf', w.document.querySelector('.assistant-history-bar').textContent);
        assert.equal(w.inspectResources().table.rows[0].x1, 5);
        assert.equal(w.document.querySelector('.map-sidebar').inert, false);
    } finally { w.close(); }
});

function historyFixture() {
    let value = { state: { crs: 'EPSG:9208', layers: [{ color: 'black' }], view: { zoom: 10 } },
        assets: new Map([['dxf', new Blob(['original'])], ['rows', [{ x1: 0 }]]]) };
    let saved = structuredClone(value), paused = false;
    const history = new WorkspaceHistory({ capture: () => structuredClone(value),
        restore: snapshot => { value = structuredClone(snapshot); },
        pause: async () => { paused = true; },
        resume: () => { paused = false; saved = structuredClone(value); } });
    const edit = () => { value.state.layers[0].color = 'red'; value.assets.set('dxf', new Blob(['edited DXF'])); value.assets.get('rows')[0].x1 = 5; };
    return { history, edit, get value() { return value; }, get saved() { return saved; }, get paused() { return paused; } };
}

test('DXF and CSV draft confirm, undo and redo as one transaction without regenerating', async () => {
    const f = historyFixture();
    await f.history.stage(f.edit);
    assert.equal(f.value.assets.get('rows')[0].x1, 5);
    assert.equal(f.saved.assets.get('rows')[0].x1, 0);
    assert.equal(f.paused, true);
    f.history.confirm();
    assert.equal(f.saved.assets.get('rows')[0].x1, 5);
    // Panning and zooming must not prevent undo.
    f.value.state.view.zoom = 17;
    await f.history.travel('undo');
    assert.equal(f.value.state.layers[0].color, 'black');
    assert.equal(await f.value.assets.get('dxf').text(), 'original');
    assert.equal(f.value.assets.get('rows')[0].x1, 0);
    await f.history.travel('redo');
    assert.equal(await f.value.assets.get('dxf').text(), 'edited DXF');
    assert.equal(f.value.assets.get('rows')[0].x1, 5);
});

test('discard and a failed map render restore both resources and resume autosave', async () => {
    const f = historyFixture();
    await f.history.stage(f.edit);
    await f.history.travel('discard');
    assert.equal(f.value.assets.get('rows')[0].x1, 0);
    assert.equal(f.history.past.length, 0);
    await assert.rejects(f.history.stage(async () => { f.edit(); throw new Error('map failed'); }), /map failed/);
    assert.equal(await f.value.assets.get('dxf').text(), 'original');
    assert.equal(f.value.assets.get('rows')[0].x1, 0);
    assert.equal(f.paused, false);
    assert.equal(f.history.pending, null);
});

test('history refuses to overwrite newer CSV edits and drops redo after a new confirmation', async () => {
    const f = historyFixture();
    await f.history.stage(f.edit); f.history.confirm();
    f.value.assets.get('rows')[0].x1 = 9;
    await assert.rejects(f.history.travel('undo'), /đã thay đổi/);
    f.value.assets.get('rows')[0].x1 = 5;
    await f.history.travel('undo');
    await f.history.stage(f.edit); f.history.confirm();
    assert.equal(f.history.future.length, 0);
});

function fixture(status = { enabled: true }) {
    const dom = new JSDOM('<!doctype html><body></body>', { url: 'http://localhost/legacy/', runScripts: 'outside-only' });
    const window = dom.window;
    let sourceFile = new window.File(['DXF'], 'test.dxf');
    const csvFile = new window.File(['id,x1\n1,0'], 'input.csv');
    let draft = false;
    const calls = [], commits = [];
    const proposal = { answer: '<img src=x onerror=alert(1)>', sources: [],
        edits: [{ handle: 'AB', operation: 'color', before: 7, value: 1 }], scores: [],
        token: 'signed-preview', rejected: [], scope: '1/1 đối tượng' };
    window.assistantWorkspace = { sources: () => [{ id: 'dxf-1', file: sourceFile }],
        tables: () => [{ id: 'csv-file', file: csvFile }],
        csv: () => csvFile, version: () => 1, crs: () => 'EPSG:9208',
        hasDraft: () => draft,
        stage: async value => { commits.push(value); draft = true; },
        confirm: () => { draft = false; window.dispatchEvent(new window.Event('assistant-workspace-change')); },
        discard: async () => { draft = false; window.dispatchEvent(new window.Event('assistant-workspace-change')); } };
    window.URL.createObjectURL = () => 'blob:test'; window.URL.revokeObjectURL = () => {};
    window.fetch = async (url, options) => {
        calls.push({ url, options });
        return { ok: true, blob: async () => new window.Blob(['DXF edited']), json: async () => ({ data: url.endsWith('/status') ? status
            : url.endsWith('/apply') ? { dxf: window.btoa('DXF edited'), rows: null } : proposal }) };
    };
    window.HTMLAnchorElement.prototype.click = function () {};
    window.eval(script);
    const get = name => window.document.querySelector('.assistant-' + name);
    const submit = async () => {
        get('launcher').click(); get('source').value = 'dxf-1';
        get('form').querySelector('textarea').value = 'Đổi màu nét';
        get('form').dispatchEvent(new window.Event('submit', { cancelable: true }));
        await tick();
    };
    return { window, get, calls, commits, submit, close: () => window.close(),
        changeFile: () => { sourceFile = new window.File(['CHANGED'], 'test.dxf'); } };
}

test('chat uses project resources only when submitted and stages a signed draft', async () => {
    const f = fixture();
    try {
        await tick();
        assert.equal(f.get('window').hidden, true);
        assert.deepEqual(f.calls.map(c => c.url), ['/api/v1/assistant/status']);
        await f.submit();
        assert.equal(f.get('preview').hidden, false);
        assert.equal(f.commits.length, 1);
        assert.equal(f.calls.filter(c => c.url.endsWith('/apply')).length, 1);
        const form = f.calls.find(c => c.url.endsWith('/preview')).options.body;
        assert.equal(form.get('dxf').name, 'test.dxf');
        assert.equal(form.get('csv').name, 'input.csv');
        assert.equal(f.window.document.querySelector('input[type="file"]'), null);
        assert.equal(f.get('messages').querySelector('img'), null);
    } finally { f.close(); }
});

test('confirmation accepts the already rendered draft without generating it twice', async () => {
    const f = fixture();
    try {
        await f.submit();
        assert.equal(f.window.assistantWorkspace.hasDraft(), true);
        f.get('preview').querySelector('button').click();
        await tick();
        assert.equal(f.calls.filter(c => c.url.endsWith('/apply')).length, 1);
        assert.equal(f.calls.find(c => c.url.endsWith('/apply')).options.body.get('token'), 'signed-preview');
        assert.equal(f.commits.length, 1);
        assert.equal(f.commits[0].dxf.name, 'test_edited.dxf');
        assert.equal(f.get('preview').hidden, true);
        assert.equal(f.window.assistantWorkspace.hasDraft(), false);
        assert.equal(f.get('exports').querySelector('a').download, 'test.dxf');
    } finally { f.close(); }
});

test('chat sends the chosen model mode without an arbitrary model or endpoint', async () => {
    const f = fixture();
    try {
        f.get('mode').value = 'smart';
        f.get('passcode').value = 'temporary-smart-code';
        await f.submit();
        const request = f.calls.find(call => call.url.endsWith('/preview'));
        assert.equal(request.options.body.get('mode'), 'smart');
        assert.equal(request.options.body.get('model'), null);
        assert.equal(request.options.body.get('url'), null);
    } finally { f.close(); }
});

test('Smart asks for a passcode and never stores it in localStorage', async () => {
    const f = fixture();
    try {
        f.get('mode').value = 'smart';
        f.get('mode').dispatchEvent(new f.window.Event('change'));
        assert.equal(f.get('passcode-label').hidden, false);
        await f.submit();
        assert.equal(f.calls.filter(call => call.url.endsWith('/preview')).length, 0);
        f.get('passcode').value = 'temporary-pro-code';
        await f.submit();
        const form = f.calls.find(call => call.url.endsWith('/preview')).options.body;
        assert.equal(form.get('mode'), 'smart');
        assert.equal(form.get('passcode'), 'temporary-pro-code');
        assert.equal(JSON.stringify(f.window.localStorage).includes('temporary-pro-code'), false);
    } finally { f.close(); }
});

test('only Fast and Smart exist and missing cookies never route Smart to Fast', async () => {
    const f = fixture({ enabled: true, modes: [
        { id: 'fast', requires_passcode: false, availability: 'ready' },
        { id: 'smart', requires_passcode: true, availability: 'cookie_required', message: 'Thông minh chưa có cookie hợp lệ' },
    ] });
    try {
        await tick();
        assert.deepEqual([...f.get('mode').options].map(option => option.value), ['fast', 'smart']);
        f.get('mode').value = 'smart';
        f.get('mode').dispatchEvent(new f.window.Event('change'));
        await f.submit();
        assert.match(f.get('notice').textContent, /chưa có cookie/);
        assert.equal(f.get('mode').value, 'smart');
        assert.equal(f.calls.filter(call => call.url.endsWith('/preview')).length, 0);
    } finally { f.close(); }
});

test('resource changes during model analysis prevent staging stale edits', async () => {
    const f = fixture();
    try {
        const fetch = f.window.fetch;
        f.window.fetch = async (url, options) => {
            const result = await fetch(url, options);
            if (url.endsWith('/preview')) f.changeFile();
            return result;
        };
        await f.submit();
        await tick();
        assert.equal(f.calls.filter(c => c.url.endsWith('/apply')).length, 0);
        assert.match(f.get('notice').textContent, /đã thay đổi/);
        assert.equal(f.commits.length, 0);
    } finally { f.close(); }
});

test('discard restores the project and allows a new request', async () => {
    const f = fixture();
    try {
        await f.submit();
        [...f.get('preview').querySelectorAll('button')].find(button => button.textContent.includes('Bỏ bản nháp')).click();
        await tick();
        assert.equal(f.window.assistantWorkspace.hasDraft(), false);
        assert.equal(f.get('preview').hidden, true);
        assert.equal(f.get('form').querySelector('[type="submit"]').disabled, false);
    } finally { f.close(); }
});
