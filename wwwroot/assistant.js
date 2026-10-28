/* Floating assistant, explicit preview/apply, no model-generated HTML or code. */
(() => {
    'use strict';
    const root = document.createElement('div');
    root.className = 'assistant-root';
    root.innerHTML = `<button class="assistant-launcher" type="button" aria-expanded="false" aria-controls="assistant-window">Trợ lý GIS</button>
      <section id="assistant-window" class="assistant-window" role="dialog" aria-label="Trợ lý GIS" hidden>
        <header class="assistant-header"><div><strong>Trợ lý GIS</strong><small>DXF và tiêu chí đánh giá</small></div><button type="button" class="assistant-close" aria-label="Thu nhỏ trợ lý">×</button></header>
        <div class="assistant-messages" role="log" aria-live="polite"></div>
        <label class="assistant-mode-label">Chế độ trả lời<select class="assistant-mode"><option value="fast">Nhanh</option><option value="smart">Thông minh</option><option value="pro">Pro · 4 Argon</option></select></label>
        <label class="assistant-passcode-label" hidden>Passcode Pro<input class="assistant-passcode" type="password" maxlength="128" autocomplete="off" placeholder="Passcode do quản trị cấp"></label>
        <details class="assistant-context"><summary>Dữ liệu gửi cho trợ lý</summary>
          <label>DXF đang dùng<select class="assistant-source"><option value="">Chưa chọn DXF</option></select></label>
          <label>Hoặc chọn một DXF<input class="assistant-upload" type="file" accept=".dxf"></label>
          <label><input class="assistant-table" type="checkbox">Gửi bảng CSV đầu vào đang nạp</label>
          <label>Lọc tên layer<input class="assistant-layer" maxlength="100" placeholder="Để trống để xem các layer"></label>
          <label>Bắt đầu từ dòng dữ liệu<input class="assistant-start" type="number" min="1" max="10000" value="1"></label>
          <label><input class="assistant-web" type="checkbox" checked>Tra cứu mạng qua Gemini</label>
          <p>Mỗi lượt gửi tối đa 300 đối tượng DXF và 100 dòng bảng, file gốc giữ nguyên</p>
          <p>Chỉ phần tóm tắt đã chọn được gửi đến Gemini, lịch sử lưu trên trình duyệt này</p>
        </details>
        <div class="assistant-preview" hidden></div>
        <div class="assistant-knowledge" hidden></div>
        <div class="assistant-exports" hidden aria-label="File đã sửa"></div>
        <div class="assistant-notice" role="status"></div>
        <form class="assistant-form"><label class="sr-only" for="assistant-question">Yêu cầu với trợ lý</label><textarea id="assistant-question" rows="2" maxlength="4000" placeholder="Đọc DXF, chỉnh layer hoặc đề xuất điểm cho ô đất" required></textarea><div><button type="submit">Gửi</button><button class="assistant-stop" type="button" hidden>Dừng chờ</button><button class="assistant-clear" type="button">Xóa hội thoại</button></div></form>
      </section>`;
    document.body.append(root);
    const get = selector => root.querySelector('.assistant-' + selector);
    const launcher = get('launcher'), panel = get('window'), source = get('source');
    const messages = get('messages'), notice = get('notice'), preview = get('preview');
    const historyKey = 'mapPredict.assistant.history.v1';
    let history = [], pending = null, controller = null, urls = [], busy = false;
    let protectedModes = new Set(['pro']);
    get('mode').addEventListener('change', () => {
        get('passcode-label').hidden = !protectedModes.has(get('mode').value);
        get('passcode').value = '';
    });
    try { history = JSON.parse(localStorage.getItem(historyKey) || '[]').filter(item => item && ['user', 'assistant'].includes(item.role) && typeof item.content === 'string').slice(-20); } catch { history = []; }
    function element(tag, text, className) {
        const node = document.createElement(tag);
        node.textContent = text;
        if (className) node.className = className;
        return node;
    }
    function message(role, text, save = true, sources = []) {
        const item = element('div', '', 'assistant-message ' + role);
        item.append(element('strong', role === 'user' ? 'Bạn' : 'Trợ lý'), element('p', text));
        messages.append(item);
        while (messages.children.length > 20) messages.firstElementChild.remove();
        messages.scrollTop = messages.scrollHeight;
        if (save) {
            history = [...history, { role, content: text, sources }].slice(-20);
            try { localStorage.setItem(historyKey, JSON.stringify(history)); } catch { /* Chat still works without persistence. */ }
        }
        return item;
    }
    history.forEach(item => showSources(message(item.role, item.content, false), Array.isArray(item.sources) ? item.sources : []));
    if (!history.length) message('assistant', 'Tôi có thể đọc cấu trúc DXF, đề xuất chỉnh đối tượng và tra cứu căn cứ cho 9 tiêu chí\nChọn dữ liệu trong mục bên dưới rồi nhập yêu cầu', false);
    function refreshSources() {
        const selected = source.value;
        source.replaceChildren(new Option('Chưa chọn DXF', ''));
        for (const entry of window.assistantWorkspace.sources()) source.add(new Option(entry.file.name + (entry.kind === 'prediction' ? ' · Lưới' : ' · Nền'), entry.id));
        source.value = selected;
        if (!source.value) source.value = '';
    }
    launcher.addEventListener('click', () => {
        panel.hidden = !panel.hidden;
        launcher.setAttribute('aria-expanded', String(!panel.hidden));
        if (!panel.hidden) { refreshSources(); get('form').querySelector('textarea').focus(); }
    });
    get('close').addEventListener('click', () => { panel.hidden = true; launcher.setAttribute('aria-expanded', 'false'); launcher.focus(); });
    panel.addEventListener('keydown', event => { if (event.key === 'Escape') get('close').click(); });
    document.addEventListener('fullscreenchange', () => (document.fullscreenElement || document.body).append(root));
    source.addEventListener('change', () => { get('upload').value = ''; clearPreview(); });
    get('upload').addEventListener('change', () => { source.value = ''; clearPreview(); });
    get('table').addEventListener('change', clearPreview);
    function snapshot() {
        const entry = window.assistantWorkspace.sources().find(item => item.id === source.value);
        return { sourceId: entry?.id || '', dxf: get('upload').files[0] || entry?.file || null,
            csv: get('table').checked ? window.assistantWorkspace.csv() : null,
            version: window.assistantWorkspace.version() };
    }
    function sameFiles(before) {
        const current = snapshot();
        return current.dxf === before.dxf && current.csv === before.csv && current.version === before.version && current.sourceId === before.sourceId;
    }
    function formData(files) {
        const form = new FormData();
        if (files.dxf) form.append('dxf', files.dxf);
        if (files.csv) form.append('csv', files.csv);
        return form;
    }
    async function request(action, form, signal) {
        const result = await fetch('/api/v1/assistant/' + action, { method: 'POST', body: form, signal });
        const payload = await result.json();
        if (!result.ok) throw new Error(payload.error?.message || 'Không thể xử lý yêu cầu');
        return payload.data;
    }
    function clearPreview() { pending = null; preview.hidden = true; preview.replaceChildren(); }
    function setBusy(value) {
        busy = value;
        get('form').querySelector('[type="submit"]').disabled = value;
        get('stop').hidden = !value || !controller;
        panel.setAttribute('aria-busy', String(value));
    }
    function showSources(item, sources) {
        for (const cited of sources) {
            try {
                const url = new URL(cited.url);
                if (url.protocol !== 'https:') continue;
                const link = element('a', cited.title || url.hostname);
                link.href = url.href; link.target = '_blank'; link.rel = 'noopener noreferrer';
                item.append(link, element('small', cited.status), element('blockquote', cited.quote));
            } catch { /* Invalid model URLs are never rendered as links. */ }
        }
    }
    function showPreview(result, files) {
        clearPreview();
        if (!result.token) return;
        pending = { token: result.token, files };
        preview.hidden = false;
        const count = result.edits.length + result.scores.length;
        preview.append(element('strong', 'Xem trước thay đổi'));
        if (result.create_table) preview.append(element('p', 'Tạo bảng cho ' + result.row_count + ' ô có mã xác định'));
        const list = document.createElement('ul');
        for (const action of result.edits) list.append(element('li', `${action.handle} · ${action.operation}: ${JSON.stringify(action.before)} → ${JSON.stringify(action.value)}${action.reason ? '\n' + action.reason : ''}`));
        for (const score of result.scores) list.append(element('li', `Dòng ${score.row_index + 1} · ${score.column}: ${score.before || 'Trống'} → ${score.value}\nÔ nguồn ${score.rule} · ${score.evidence}${score.qdrant_id ? '\nQdrant ' + score.qdrant_id : ''}\n${score.quote}\n${score.reason}`));
        preview.append(list);
        const apply = element('button', 'Áp dụng' + (count ? ' ' + count + ' thay đổi' : ' tạo bảng'));
        apply.type = 'button'; apply.addEventListener('click', () => applyPreview(apply));
        const cancel = element('button', 'Bỏ đề xuất'); cancel.type = 'button'; cancel.addEventListener('click', clearPreview);
        preview.append(apply, cancel);
        if (result.edits.length && files.dxf) {
            const exportButton = element('button', 'Xuất DXF từ bản xem trước');
            exportButton.type = 'button';
            exportButton.addEventListener('click', () => exportPreview(exportButton));
            preview.append(exportButton);
        }
    }
    get('form').addEventListener('submit', async event => {
        event.preventDefault();
        if (busy) return;
        const textarea = get('form').querySelector('textarea'), question = textarea.value.trim();
        if (!question) return;
        const files = snapshot();
        if (get('table').checked && !files.csv) { notice.textContent = 'Nạp CSV đầu vào trước khi gửi bảng cho trợ lý'; return; }
        const form = formData(files);
        if (protectedModes.has(get('mode').value)) {
            if (!get('passcode').value) { notice.textContent = 'Nhập passcode Pro do quản trị cấp'; get('passcode').focus(); return; }
            form.append('passcode', get('passcode').value);
        }
        form.append('message', question); form.append('history', JSON.stringify(history.slice(-6)));
        form.append('mode', get('mode').value);
        form.append('start', get('start').value); form.append('layer', get('layer').value);
        form.append('web', String(get('web').checked)); form.append('crs', window.assistantWorkspace.crs() || '');
        clearPreview(); message('user', question); textarea.value = '';
        controller = new AbortController(); setBusy(true); notice.textContent = 'Gemini đang phân tích dữ liệu và đối chiếu nguồn';
        try {
            const result = await request('preview', form, controller.signal);
            const item = message('assistant', result.answer, true, result.sources);
            showSources(item, result.sources);
            showKnowledge(result.knowledge);
            if (!sameFiles(files)) { notice.textContent = 'Dữ liệu đã thay đổi trong khi phân tích, hãy gửi lại để tạo đề xuất mới'; return; }
            showPreview(result, files);
            notice.textContent = result.scope + (result.rejected.length ? '\nĐã giữ lại ' + result.rejected.length + ' đề xuất chưa đủ điều kiện, không áp dụng' : '');
        } catch (error) { notice.textContent = error.name === 'AbortError' ? 'Đã dừng chờ phản hồi' : error.message; }
        finally { setBusy(false); controller = null; }
    });
    function decodeFile(base64, name) {
        return new File([Uint8Array.from(atob(base64), char => char.charCodeAt(0))], name, { type: 'application/dxf' });
    }
    function download(file, name) {
        const url = URL.createObjectURL(file); urls.push(url);
        const link = element('a', name); link.href = url; link.download = file.name;
        get('exports').hidden = false;
        get('exports').append(link);
    }
    function clearExports() {
        urls.forEach(url => URL.revokeObjectURL(url)); urls = [];
        get('exports').replaceChildren(); get('exports').hidden = true;
    }
    function showKnowledge(knowledge) {
        const area = get('knowledge'); area.replaceChildren(); area.hidden = !knowledge;
        if (!knowledge) return;
        const mode = knowledge.mode === 'dense' ? 'Truy xuất vector Qdrant' : knowledge.mode === 'keyword_fallback'
            ? 'Truy xuất từ khóa Qdrant' : 'Tài liệu tiêu chí local';
        const details = document.createElement('details');
        details.append(element('summary', mode));
        if (knowledge.message) details.append(element('p', knowledge.message));
        for (const record of knowledge.records || []) details.append(element('p', `${record.file} · ${record.id}\n${record.source_refs.join(', ')}`));
        area.append(details);
    }
    async function exportPreview(button) {
        if (!pending || busy) return;
        if (!sameFiles(pending.files)) { clearPreview(); notice.textContent = 'File đã thay đổi, cần xem trước lại'; return; }
        const plan = pending, form = formData(plan.files); form.append('token', plan.token);
        setBusy(true); button.disabled = true;
        try {
            const response = await fetch('/api/v1/assistant/export', { method: 'POST', body: form });
            if (!response.ok) {
                const payload = await response.json();
                throw new Error(payload.error?.message || 'Không thể xuất DXF');
            }
            const blob = await response.blob();
            if (!sameFiles(plan.files)) throw new Error('File đã thay đổi trong lúc xuất, hãy xem trước lại');
            const file = new File([blob], plan.files.dxf.name.replace(/\.dxf$/i, '_edited.dxf'), { type: 'application/dxf' });
            clearExports(); download(file, 'Xuất DXF đã sửa');
            notice.textContent = 'Đã tạo DXF sửa từ bản xem trước, workspace và file gốc giữ nguyên';
            get('exports').querySelector('a').click();
        } catch (error) { notice.textContent = error.message; }
        finally { setBusy(false); button.disabled = false; }
    }
    async function applyPreview(button) {
        if (!pending || busy) return;
        if (!sameFiles(pending.files)) { clearPreview(); notice.textContent = 'File hoặc bảng đã thay đổi, cần tạo lại bản xem trước'; return; }
        const plan = pending, form = formData(plan.files);
        form.append('token', plan.token); setBusy(true); button.disabled = true;
        try {
            const result = await request('apply', form);
            if (!sameFiles(plan.files)) throw new Error('Dữ liệu vừa thay đổi, chưa đưa kết quả vào workspace');
            const dxf = result.dxf ? decodeFile(result.dxf, plan.files.dxf.name.replace(/\.dxf$/i, '_edited.dxf')) : null;
            await window.assistantWorkspace.commit({ sourceId: plan.files.sourceId, original: plan.files.dxf, dxf, rows: result.rows });
            clearPreview(); get('upload').value = ''; refreshSources();
            if (dxf) source.value = window.assistantWorkspace.sources().find(entry => entry.file === dxf)?.id || '';
            clearExports();
            notice.textContent = 'Đã áp dụng vào workspace, file gốc trên máy giữ nguyên';
            if (dxf) download(dxf, 'Xuất DXF đã sửa');
            if (result.rows) download(new File([await resultsCsvFile(result.rows).arrayBuffer()], 'TieuChi.csv', { type: 'text/csv;charset=utf-8' }), 'Tải bảng tiêu chí');
        } catch (error) { notice.textContent = error.message; button.disabled = false; }
        finally { setBusy(false); }
    }
    get('stop').addEventListener('click', () => controller?.abort());
    get('clear').addEventListener('click', () => {
        if (busy) return;
        history = []; messages.replaceChildren(); clearPreview(); notice.textContent = '';
        try { localStorage.removeItem(historyKey); } catch { /* Storage can be disabled. */ }
    });
    window.addEventListener('pagehide', () => urls.forEach(url => URL.revokeObjectURL(url)));
    fetch('/api/v1/assistant/status').then(response => response.json()).then(payload => {
        if (!payload.data?.enabled) notice.textContent = 'Chatbot chưa được bật trên máy chủ';
        if (Array.isArray(payload.data?.modes)) {
            protectedModes = new Set(payload.data.modes.filter(mode => mode.requires_passcode).map(mode => mode.id));
            get('passcode-label').hidden = !protectedModes.has(get('mode').value);
        }
    }).catch(() => { notice.textContent = 'Chưa kết nối được máy chủ'; });
})();
