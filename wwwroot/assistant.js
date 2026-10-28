/* Floating assistant, explicit preview/apply, no model-generated HTML or code. */
(() => {
    'use strict';
    const root = document.createElement('div');
    root.className = 'assistant-root';
    root.innerHTML = `<button class="assistant-launcher" type="button" aria-expanded="false" aria-controls="assistant-window">Trợ lý GIS</button>
      <section id="assistant-window" class="assistant-window" role="dialog" aria-label="Trợ lý GIS" hidden>
        <header class="assistant-header"><div><strong>Trợ lý GIS</strong><small>DXF và tiêu chí đánh giá</small></div><button type="button" class="assistant-close" aria-label="Thu nhỏ trợ lý">×</button></header>
        <div class="assistant-messages" role="log" aria-live="polite"></div>
        <label class="assistant-mode-label">Chế độ trả lời<select class="assistant-mode"><option value="fast">Nhanh</option><option value="smart">Thông minh</option></select></label>
        <label class="assistant-passcode-label" hidden>Passcode Thông minh<input class="assistant-passcode" type="password" maxlength="128" autocomplete="off" placeholder="Passcode do quản trị cấp"></label>
        <div class="assistant-preview" hidden></div>
        <div class="assistant-history-slot"></div>
        <div class="assistant-notice" role="status"></div>
        <form class="assistant-form"><label class="sr-only" for="assistant-question">Yêu cầu với trợ lý</label><textarea id="assistant-question" rows="2" maxlength="4000" placeholder="Đọc DXF, chỉnh layer hoặc đề xuất điểm cho ô đất" required></textarea><div><button type="submit">Gửi</button><button class="assistant-stop" type="button" hidden>Dừng chờ</button><button class="assistant-clear" type="button">Xóa hội thoại</button></div></form>
      </section>`;
    document.body.append(root);
    const get = selector => root.querySelector('.assistant-' + selector);
    const launcher = get('launcher'), panel = get('window');
    const messages = get('messages'), notice = get('notice'), preview = get('preview');
    const historyKey = 'mapPredict.assistant.history.v1';
    let history = [], pending = null, controller = null, busy = false;
    let protectedModes = new Set(['smart']);
    let unavailableModes = new Map();
    get('mode').addEventListener('change', () => {
        get('passcode-label').hidden = !protectedModes.has(get('mode').value) || unavailableModes.has(get('mode').value);
        get('passcode').value = '';
        notice.textContent = unavailableModes.get(get('mode').value) || '';
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
    if (!history.length) message('assistant', 'Tôi làm việc với dữ liệu của tab đang mở\nTab dự đoán dùng CSV hoặc tạo bảng mới, tab bản đồ dùng DXF đã nạp và đang bật hiển thị', false);
    const historyBar = document.querySelector('.assistant-history-bar');
    if (historyBar) get('history-slot').append(historyBar);
    launcher.addEventListener('click', () => {
        panel.hidden = !panel.hidden;
        launcher.setAttribute('aria-expanded', String(!panel.hidden));
        if (!panel.hidden) { get('form').querySelector('textarea').focus(); }
    });
    get('close').addEventListener('click', () => { panel.hidden = true; launcher.setAttribute('aria-expanded', 'false'); launcher.focus(); });
    panel.addEventListener('keydown', event => { if (event.key === 'Escape') get('close').click(); });
    document.addEventListener('fullscreenchange', () => (document.fullscreenElement || document.body).append(root));
    function snapshot() { return window.assistantWorkspace.context(); }
    function sameFiles(before) {
        const current = snapshot();
        return current.scope === before.scope && current.csv === before.csv && current.version === before.version
            && current.resources.length === before.resources.length
            && current.resources.every((item, index) => item.id === before.resources[index].id && item.file === before.resources[index].file);
    }
    function formData(files) {
        const form = new FormData();
        for (const item of files.resources) form.append('dxf', item.file);
        form.append('scope', files.scope);
        if (files.scope === 'map') form.append('resource_ids', JSON.stringify(files.resources.map(item => item.id)));
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
        get('form').querySelector('[type="submit"]').disabled = value || window.assistantWorkspace.hasDraft();
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
        const apply = element('button', 'Xác nhận' + (count ? ' ' + count + ' thay đổi' : ' tạo bảng'));
        apply.disabled = true;
        apply.type = 'button'; apply.addEventListener('click', () => {
            try { window.assistantWorkspace.confirm(); notice.textContent = 'Đã xác nhận và tự lưu, dùng Hoàn tác và Làm lại để so sánh trước và sau'; }
            catch (error) { notice.textContent = error.message; }
        });
        const cancel = element('button', 'Bỏ bản nháp'); cancel.type = 'button'; cancel.disabled = true;
        cancel.addEventListener('click', async () => {
            try { await window.assistantWorkspace.discard(); notice.textContent = 'Đã khôi phục dữ liệu trước bản nháp'; }
            catch (error) { notice.textContent = error.message; }
        });
        preview.append(apply, cancel);

    }
    get('form').addEventListener('submit', async event => {
        event.preventDefault();
        if (busy || window.assistantWorkspace.hasDraft()) return;
        const textarea = get('form').querySelector('textarea'), question = textarea.value.trim();
        if (!question) return;
        const files = snapshot();
        if (files.scope === 'map' && !files.resources.length) {
            notice.textContent = 'Hãy nạp DXF, hiển thị trên bản đồ và tích bật file cần sửa trước khi gửi';
            return;
        }
        if (files.resources.length > 5) {
            notice.textContent = 'Mỗi lượt sửa tối đa 5 DXF, hãy tắt bớt file trên bản đồ';
            return;
        }
        const form = formData(files);
        if (unavailableModes.has(get('mode').value)) { notice.textContent = unavailableModes.get(get('mode').value); return; }
        if (protectedModes.has(get('mode').value)) {
            if (!get('passcode').value) { notice.textContent = 'Nhập passcode Thông minh do quản trị cấp'; get('passcode').focus(); return; }
            form.append('passcode', get('passcode').value);
        }
        form.append('message', question); form.append('history', JSON.stringify(history.slice(-6)));
        form.append('mode', get('mode').value);
        form.append('start', '1');
        form.append('web', 'true'); form.append('crs', window.assistantWorkspace.crs() || '');
        clearPreview(); message('user', question); textarea.value = '';
        controller = new AbortController(); setBusy(true); notice.textContent = 'Gemini đang phân tích dữ liệu và đối chiếu nguồn';
        try {
            const result = await request('preview', form, controller.signal);
            const item = message('assistant', result.answer, true, result.sources);
            showSources(item, result.sources);
            if (!sameFiles(files)) { notice.textContent = 'Dữ liệu đã thay đổi trong khi phân tích, hãy gửi lại để tạo đề xuất mới'; return; }
            showPreview(result, files);
            if (pending) await applyPreview(applyButton());
            notice.textContent = (pending?.staged ? 'Bản sửa nháp đã hiển thị, hãy kiểm tra rồi Xác nhận hoặc Bỏ bản nháp\n' : '')
                + result.scope + (result.rejected.length ? '\nĐã giữ lại ' + result.rejected.length + ' đề xuất chưa đủ điều kiện, không áp dụng' : '');
        } catch (error) { notice.textContent = error.name === 'AbortError' ? 'Đã dừng chờ phản hồi' : error.message; }
        finally { setBusy(false); controller = null; }
    });
    function applyButton() { return preview.querySelector('button'); }
    function decodeFile(base64, name) {
        return new File([Uint8Array.from(atob(base64), char => char.charCodeAt(0))], name, { type: 'application/dxf' });
    }
    async function applyPreview(button) {
        if (!pending) return;
        if (!sameFiles(pending.files)) { clearPreview(); notice.textContent = 'File hoặc bảng đã thay đổi, cần tạo lại bản xem trước'; return; }
        const plan = pending, form = formData(plan.files);
        form.append('token', plan.token); setBusy(true); button.disabled = true;
        get('stop').hidden = true;
        try {
            const result = await request('apply', form);
            if (!sameFiles(plan.files)) throw new Error('Dữ liệu vừa thay đổi, chưa đưa kết quả vào workspace');
            const dxfs = (result.dxfs || []).map(item => {
                const original = plan.files.resources.find(resource => resource.id === item.source_id);
                if (!original) throw new Error('DXF trả về không thuộc tài nguyên đang bật');
                return { sourceId: original.id, original: original.file, file: decodeFile(item.dxf, original.file.name) };
            });
            if (plan.files.scope === 'map' && result.rows || plan.files.scope === 'prediction' && (dxfs.length || result.dxf)) {
                throw new Error('Kết quả AI vượt phạm vi tab đang mở');
            }
            await window.assistantWorkspace.stage({ dxfs, rows: result.rows, csvId: plan.files.csvId });
            plan.staged = true;
            for (const control of preview.querySelectorAll('button')) control.disabled = false;
            notice.textContent = 'Bản sửa nháp đã hiển thị, hãy kiểm tra rồi Xác nhận hoặc Bỏ bản nháp';
        } catch (error) { clearPreview(); notice.textContent = error.message; throw error; }
        finally { setBusy(false); }
    }
    get('stop').addEventListener('click', () => controller?.abort());
    get('clear').addEventListener('click', () => {
        if (busy || window.assistantWorkspace.hasDraft()) return;
        history = []; messages.replaceChildren(); clearPreview(); notice.textContent = '';
        try { localStorage.removeItem(historyKey); } catch { /* Storage can be disabled. */ }
    });
    window.addEventListener('assistant-workspace-change', () => {
        if (pending?.staged && !window.assistantWorkspace.hasDraft()) {
            clearPreview();
        }
        get('form').querySelector('[type="submit"]').disabled = busy || window.assistantWorkspace.hasDraft();
    });
    fetch('/api/v1/assistant/status').then(response => response.json()).then(payload => {
        if (!payload.data?.enabled) notice.textContent = 'Chatbot chưa được bật trên máy chủ';
        if (Array.isArray(payload.data?.modes)) {
            protectedModes = new Set(payload.data.modes.filter(mode => mode.requires_passcode).map(mode => mode.id));
            unavailableModes = new Map(payload.data.modes.filter(mode => mode.availability === 'cookie_required').map(mode => [mode.id, mode.message || 'Thông minh chưa có cookie hợp lệ, hãy cập nhật trong quản trị']));
            get('passcode-label').hidden = !protectedModes.has(get('mode').value) || unavailableModes.has(get('mode').value);
            if (unavailableModes.has(get('mode').value)) notice.textContent = unavailableModes.get(get('mode').value);
        }
    }).catch(() => { notice.textContent = 'Chưa kết nối được máy chủ'; });
})();
