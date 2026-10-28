const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { JSDOM } = require('../frontend/node_modules/jsdom');
const script = fs.readFileSync(require('node:path').join(__dirname, '../wwwroot/assistant.js'), 'utf8');
const tick = () => new Promise(resolve => setTimeout(resolve, 5));

function fixture(status = { enabled: true }) {
    const dom = new JSDOM('<!doctype html><body></body>', { url: 'http://localhost/legacy/', runScripts: 'outside-only' });
    const window = dom.window;
    let sourceFile = new window.File(['DXF'], 'test.dxf');
    const calls = [], commits = [];
    const proposal = { answer: '<img src=x onerror=alert(1)>', sources: [],
        edits: [{ handle: 'AB', operation: 'color', before: 7, value: 1 }], scores: [],
        token: 'signed-preview', rejected: [], scope: '1/1 đối tượng' };
    window.assistantWorkspace = { sources: () => [{ id: 'dxf-1', file: sourceFile }],
        csv: () => null, version: () => 1, crs: () => 'EPSG:9208', commit: async value => commits.push(value) };
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

test('chat is collapsed initially and never sends DXF until explicitly submitted', async () => {
    const f = fixture();
    try {
        await tick();
        assert.equal(f.get('window').hidden, true);
        assert.deepEqual(f.calls.map(c => c.url), ['/api/v1/assistant/status']);
        await f.submit();
        assert.equal(f.get('preview').hidden, false);
        assert.equal(f.commits.length, 0);
        assert.equal(f.calls.filter(c => c.url.endsWith('/apply')).length, 0);
        assert.equal(f.get('messages').querySelector('img'), null);
    } finally { f.close(); }
});

test('apply occurs only after the explicit button and carries the signed token', async () => {
    const f = fixture();
    try {
        await f.submit();
        f.get('preview').querySelector('button').click();
        await tick();
        assert.equal(f.calls.filter(c => c.url.endsWith('/apply')).length, 1);
        assert.equal(f.calls.find(c => c.url.endsWith('/apply')).options.body.get('token'), 'signed-preview');
        assert.equal(f.commits.length, 1);
        assert.equal(f.commits[0].dxf.name, 'test_edited.dxf');
        assert.equal(f.get('preview').hidden, true);
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

test('a changed attachment invalidates preview and prevents any apply request', async () => {
    const f = fixture();
    try {
        await f.submit(); f.changeFile();
        f.get('preview').querySelector('button').click();
        await tick();
        assert.equal(f.calls.filter(c => c.url.endsWith('/apply')).length, 0);
        assert.match(f.get('notice').textContent, /đã thay đổi/);
        assert.equal(f.commits.length, 0);
    } finally { f.close(); }
});

test('export creates a download from preview without modifying the workspace', async () => {
    const f = fixture();
    try {
        await f.submit();
        [...f.get('preview').querySelectorAll('button')].find(button => button.textContent.includes('Xuất DXF')).click();
        await tick();
        assert.equal(f.calls.filter(call => call.url.endsWith('/export')).length, 1);
        assert.equal(f.commits.length, 0);
        assert.equal(f.get('exports').querySelector('a').download, 'test_edited.dxf');
        assert.equal(f.get('exports').hidden, false);
    } finally { f.close(); }
});
