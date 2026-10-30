import { useEffect, useRef, useState } from 'react';
import '../styles/ai-admin.css';

type Model = { label: string; provider: 'gemini' | 'compatible'; model: string; url: string; api_key?: string; has_api_key?: boolean; clear_api_key?: boolean };
type Settings = { models: Record<'fast' | 'smart', Model>; embedding: { url: string; model: string } };
type Pool = { accounts: { id: string; label: string; email?: string | null; checked_at?: number; rotated_at?: number; rotation_checked_at?: number; renewal_state?: 'renewed' | 'not_renewed' | null; refresh_attempt_at?: number; status: string; usage?: { current_5h?: { used_percent: number | null; reset_at?: string }; weekly?: { used_percent: number | null; reset_at?: string } } }[]; unavailable?: boolean;
  maintenance?: { poll_interval_seconds: number; rotate_interval_seconds: number; repair_cooldown_seconds: number } };
type State = { csrf: string; settings: Settings; gemini: { state: string; checked_at?: number; rotated_at?: number }; account_pool?: Pool; pro_access?: { configured: boolean }; services: string[]; embedding_enabled?: boolean };
const accountLabels: Record<string, string> = { ready: 'Còn quota', exhausted: 'Hết quota', not_checked: 'Chưa kiểm tra', needs_login: 'Cần đăng nhập lại', needs_attention: 'Cần kiểm tra cookie và quyền Argon', unavailable: 'Chưa xác minh được quota', model_unavailable: 'Chưa xác minh quyền dùng Argon' };
const date = (value?: number) => value ? new Date(value * 1000).toLocaleString('vi-VN') : 'Chưa có';
const adminTabs = [
  { id: 'models', label: 'Model' },
  { id: 'accounts', label: 'Tài khoản Thông minh' },
  { id: 'session', label: 'Phiên Gemini' },
  { id: 'embedding', label: 'Kho tri thức' },
] as const;
type AdminTab = typeof adminTabs[number]['id'];

export function AiAdmin() {
  const [tab, setTab] = useState<AdminTab>('models');
  const [state, setState] = useState<State | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [password, setPassword] = useState('');
  const [accountLabel, setAccountLabel] = useState('Tài khoản Thông minh');
  const [updateAccount, setUpdateAccount] = useState('');
  const [proPasscode, setProPasscode] = useState('');
  const [proCookie, setProCookie] = useState('');
  const [accountEditor, setAccountEditor] = useState(false);
  const cookieReadVersion = useRef(0);
  const [text, setText] = useState('Quy tắc chấm điểm hiện trạng sử dụng đất');
  const [notice, setNotice] = useState('');
  const [result, setResult] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  function clearSession() {
    cookieReadVersion.current++;
    setState(null); setSettings(null); setProCookie(''); setProPasscode('');
    setPassword(''); setResult(''); setAccountEditor(false);
  }
  function editAccount(identifier = '') {
    cookieReadVersion.current++;
    setUpdateAccount(identifier); setAccountEditor(true); setProCookie('');
    setAccountLabel(state?.account_pool?.accounts.find(row => row.id === identifier)?.label || 'Tài khoản Thông minh');
  }
  async function api(path: string, body?: unknown, csrf = state?.csrf) {
    const response = await fetch('/api/v1/ai-admin/' + path, {
      method: body === undefined ? 'GET' : 'POST', credentials: 'same-origin', cache: 'no-store',
      headers: { 'Content-Type': 'application/json', ...(csrf ? { 'X-Admin-CSRF': csrf } : {}) },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    const payload = await response.json();
    if (response.status === 401) clearSession();
    if (!response.ok) throw new Error(payload.error?.message || 'Không thực hiện được yêu cầu');
    return payload.data;
  }
  useEffect(() => {
    let active = true;
    fetch('/api/v1/ai-admin/state', { cache: 'no-store', credentials: 'same-origin' })
      .then(async response => {
        if (response.status === 401) return;
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error?.message || 'Chưa kết nối service AI');
        if (active) { setState(payload.data); setSettings(payload.data.settings); }
      }).catch(error => { if (active) setNotice(error.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  const pollSeconds = state?.account_pool?.maintenance?.poll_interval_seconds;
  useEffect(() => {
    if (!state?.csrf || !pollSeconds || busy) return;
    let active = true;
    let polling = false;
    const controller = new AbortController();
    const timer = window.setInterval(async () => {
      if (polling) return;
      polling = true;
      try {
        const response = await fetch('/api/v1/ai-admin/state', { cache: 'no-store', credentials: 'same-origin', signal: controller.signal });
        if (!active) return;
        if (response.status === 401) { clearSession(); return; }
        if (!response.ok) return;
        const payload = await response.json();
        if (active) setState(previous => previous ? { ...previous, account_pool: payload.data.account_pool, gemini: payload.data.gemini } : null);
      } catch { /* Keep the last state during a transient connection failure. */ }
      finally { polling = false; }
    }, pollSeconds * 1000);
    return () => { active = false; controller.abort(); window.clearInterval(timer); };
  }, [state?.csrf, pollSeconds, busy]);
  async function action(work: () => Promise<void>) {
    if (busy) return;
    setBusy(true); setNotice('');
    try { await work(); } catch (error) { setNotice(error instanceof Error ? error.message : 'Có lỗi khi xử lý'); }
    finally { setBusy(false); }
  }
  const editModel = (mode: 'fast' | 'smart', change: Partial<Model>) => setSettings(previous => previous ? {
    ...previous, models: { ...previous.models, [mode]: { ...previous.models[mode], ...change } },
  } : null);
  async function tool(name: string, body: object = {}) {
    const data = await api('tools/' + name, body);
    setResult(JSON.stringify(data, null, 2));
    if (name.startsWith('accounts-')) {
      setState(previous => previous ? { ...previous, account_pool: data } : null);
      if (name === 'accounts-import') { cookieReadVersion.current++; setProCookie(''); setAccountEditor(false); }
    }
    if (name === 'pro-passcode') {
      setState(previous => previous ? { ...previous, pro_access: data } : null); setProPasscode('');
      setNotice(data.configured ? 'Đã đặt passcode Thông minh' : 'Đã khóa quyền gọi Thông minh');
    }
  }
  async function saveSettings(part: keyof Settings) {
    if (!state || !settings) return;
    const data: Settings = await api('settings', { ...state.settings, [part]: settings[part] });
    setState(previous => previous ? { ...previous, settings: data } : null);
    setSettings(previous => previous ? { ...previous, [part]: data[part] } : null);
    setNotice('Đã lưu cấu hình trên service AI');
  }
  if (loading) return <section className="container inner-page" role="status">Đang kết nối trang quản trị</section>;
  return <section className="container inner-page ai-admin" aria-busy={busy}>
    <div className="admin-heading"><div><p className="eyebrow">CẤU HÌNH HỆ THỐNG</p><h1>Quản trị AI</h1><p>Quản lý model, phiên Gemini và tra cứu tài liệu trong Qdrant</p></div>
      {state ? <button className="button" disabled={busy} onClick={() => action(async () => { await api('logout', {}); clearSession(); })}>Đăng xuất</button> : null}</div>
    {notice ? <p className="admin-notice" role="alert">{notice}</p> : null}
    {!state || !settings ? <form className="admin-login admin-card" onSubmit={event => { event.preventDefault(); action(async () => {
      const login = await api('login', { password }); setPassword('');
      const data = await api('state', undefined, login.csrf); setState(data); setSettings(data.settings);
    }); }}><h2>Đăng nhập quản trị</h2><label>Mật khẩu<input type="password" autoComplete="current-password" value={password} maxLength={256} required onChange={event => setPassword(event.target.value)} /></label>
      <button className="button primary" disabled={busy}>Đăng nhập</button></form> : <>
      <div className="admin-tabs" role="tablist" aria-label="Chức năng quản trị AI">
        {adminTabs.map((item, index) => <button key={item.id} type="button" role="tab"
          id={`admin-tab-${item.id}`} aria-controls={`admin-panel-${item.id}`} aria-selected={tab === item.id}
          tabIndex={tab === item.id ? 0 : -1} onClick={() => setTab(item.id)}
          onKeyDown={event => {
            const next = event.key === 'ArrowRight' ? (index + 1) % adminTabs.length
              : event.key === 'ArrowLeft' ? (index + adminTabs.length - 1) % adminTabs.length
                : event.key === 'Home' ? 0 : event.key === 'End' ? adminTabs.length - 1 : null;
            if (next === null) return;
            event.preventDefault(); setTab(adminTabs[next].id);
            document.getElementById(`admin-tab-${adminTabs[next].id}`)?.focus();
          }}>{item.label}</button>)}
      </div>
      <div role="tabpanel" id="admin-panel-models" aria-labelledby="admin-tab-models" hidden={tab !== 'models'}>
      <form onSubmit={event => { event.preventDefault(); action(async () => {
        await saveSettings('models');
      }); }}>
        <div className="admin-models">{(['fast', 'smart'] as const).map(mode => {
          const model = settings.models[mode];
          if (!model) return null;
          return <section className="admin-card" key={mode}><h2>{model.label}</h2>
            <label>Nguồn chạy<select value={model.provider} onChange={event => editModel(mode, { provider: event.target.value as Model['provider'] })} disabled={busy || mode === 'smart'}>
              <option value="gemini">Gemini Web trong Docker</option><option value="compatible">API tương thích OpenAI</option></select></label>
            <label>Tên model<input required maxLength={150} value={model.model} onChange={event => editModel(mode, { model: event.target.value })} disabled={busy || mode === 'smart'} /></label>
            {mode === 'smart' ? <p className="admin-help">Thông minh dùng 4 Argon, cần cookie hợp lệ và quota, thiếu cookie thì báo lỗi và không chuyển sang Nhanh</p> : null}
            {model.provider === 'compatible' ? <><label>Địa chỉ API, gồm /v1<input type="url" required value={model.url} onChange={event => editModel(mode, { url: event.target.value })} disabled={busy} /></label>
              <label>Khóa API mới<input type="password" autoComplete="new-password" value={model.api_key || ''} onChange={event => editModel(mode, { api_key: event.target.value })} placeholder={model.has_api_key ? 'Đã lưu khóa, để trống để giữ lại' : 'Nhập nếu API yêu cầu'} disabled={busy} /></label>
              <label className="admin-check"><input type="checkbox" checked={model.clear_api_key || false} onChange={event => editModel(mode, { clear_api_key: event.target.checked })} />Xóa khóa API đã lưu</label></> : <p className="admin-help">Tên model theo adapter được cung cấp, Thông minh dùng gemini-4-argon</p>}
            <button type="button" className="button" disabled={busy} onClick={() => action(() => tool('model-test', { mode }))}>Kiểm tra cấu hình đã lưu</button>
          </section>;
        })}</div>
        <button className="button primary" disabled={busy}>Lưu cấu hình</button>
      </form>
      </div>
      <div role="tabpanel" id="admin-panel-accounts" aria-labelledby="admin-tab-accounts" hidden={tab !== 'accounts'}>
      <section className="admin-card"><h2>Quyền sử dụng Thông minh</h2>
        <p>{state.pro_access?.configured ? 'Đã đặt passcode, người dùng phải nhập khi gọi Thông minh' : 'Chưa đặt passcode, Thông minh đang khóa với người dùng'}</p>
        <form noValidate onSubmit={event => {
          event.preventDefault();
          const passcode = new FormData(event.currentTarget).get('passcode');
          if (typeof passcode !== 'string' || passcode.length < 8 || passcode.length > 128) { setNotice('Passcode cần từ 8 đến 128 ký tự'); return; }
          action(() => tool('pro-passcode', { passcode }));
        }}>
        <label>Passcode Thông minh mới<input name="passcode" type="password" required minLength={8} maxLength={128} aria-describedby="passcode-help" autoComplete="new-password" value={proPasscode} disabled={busy} onChange={event => setProPasscode(event.target.value)} /></label>
        <p id="passcode-help" className="admin-help">Passcode cần từ 8 đến 128 ký tự, nhấn Enter hoặc nút bên dưới để lưu</p>
        <p className="admin-help">Passcode riêng để cấp quyền gọi Thông minh, không phải mật khẩu đăng nhập quản trị và không lưu trên trình duyệt</p>
        <div className="admin-actions"><button type="submit" className="button primary" disabled={busy}>Đặt passcode Thông minh</button>
          <button type="button" className="button" disabled={busy || !state.pro_access?.configured} onClick={() => action(() => tool('pro-passcode', { disable: true }))}>Khóa quyền gọi Thông minh</button></div>
        </form>
      </section>
      <section className="admin-card"><h2>Tài khoản và quota Thông minh</h2><p>Chuyển lần lượt qua tài khoản còn quota, thiếu cookie thì báo lỗi và không chuyển sang Nhanh</p>
        <div className="admin-actions"><button className="button" disabled={busy} onClick={() => action(() => tool('accounts-scan'))}>Kiểm tra tài khoản và quota</button>
          <button className="button" disabled={busy} onClick={() => editAccount()}>Thêm tài khoản</button></div>
        {state.account_pool?.unavailable ? <p>Chưa kết nối được pool tài khoản</p> : null}
        {(state.account_pool?.accounts || []).map(row => <div className="admin-account" key={row.id}><strong>{row.label}</strong><p>Trạng thái {accountLabels[row.status] || row.status}</p>
          <p>Gmail {row.email || 'Chưa xác định'}</p>
          <p>Quota 5 giờ đã dùng {row.usage?.current_5h?.used_percent ?? 'Chưa xác minh'}{row.usage?.current_5h?.used_percent != null ? '%' : ''}<br />Quota tuần đã dùng {row.usage?.weekly?.used_percent ?? 'Chưa xác minh'}{row.usage?.weekly?.used_percent != null ? '%' : ''}</p>
          {row.usage?.current_5h?.reset_at ? <p>Đặt lại quota 5 giờ {row.usage.current_5h.reset_at}</p> : null}
          {row.usage?.weekly?.reset_at ? <p>Đặt lại quota tuần {row.usage.weekly.reset_at}</p> : null}
          <button className="button" disabled={busy} aria-label={`Cập nhật cookie ${row.email || row.label}`} onClick={() => editAccount(row.id)}>Cập nhật cookie</button>
        </div>)}
        {accountEditor ? <div className="admin-cookie-editor"><h3>{updateAccount ? `Cập nhật cookie ${state.account_pool?.accounts.find(row => row.id === updateAccount)?.email || accountLabel}` : 'Thêm tài khoản mới'}</h3>
        <label>Tên tài khoản<input maxLength={80} value={accountLabel} disabled={busy} onChange={event => setAccountLabel(event.target.value)} /></label>
        <label>File cookie tài khoản Thông minh<input key={updateAccount} type="file" accept=".json,.txt" disabled={busy} onChange={event => {
          const file = event.target.files?.[0]; if (!file) return;
          if (file.size > 60000) { setNotice('File cookie tối đa 60 KB'); return; }
          const version = ++cookieReadVersion.current;
          file.text().then(value => { if (version === cookieReadVersion.current) setProCookie(value); })
            .catch(() => { if (version === cookieReadVersion.current) setNotice('Không đọc được file cookie'); });
          event.target.value = '';
        }} /></label>
        <label>Nội dung cookie tài khoản Thông minh<textarea rows={3} maxLength={60000} autoComplete="off" value={proCookie} disabled={busy} onChange={event => setProCookie(event.target.value)} /></label>
        <div className="admin-actions"><button className="button primary" disabled={busy || !proCookie.trim() || !accountLabel.trim()} onClick={() => action(() => tool('accounts-import', { cookie: proCookie, label: accountLabel, account_id: updateAccount }))}>Lưu cookie tài khoản</button>
          <button className="button" disabled={busy} onClick={() => { cookieReadVersion.current++; setAccountEditor(false); setProCookie(''); }}>Hủy</button></div>
        </div> : null}
      </section>
      </div>
      <div role="tabpanel" id="admin-panel-session" aria-labelledby="admin-tab-session" hidden={tab !== 'session'}>
      <section className="admin-card"><h2>Phiên Gemini</h2>
        {state.account_pool?.maintenance ? <p>Kiểm tra phiên và quota mỗi {state.account_pool.maintenance.poll_interval_seconds} giây<br />
          Tự thử gia hạn mỗi {state.account_pool.maintenance.rotate_interval_seconds / 60} phút<br />
          Giãn lần thử sửa phiên lỗi ít nhất {state.account_pool.maintenance.repair_cooldown_seconds / 60} phút</p> : <p>Chưa đọc được lịch gia hạn từ server</p>}
        <p className="admin-help">Thời gian lấy từ cấu hình service, việc gia hạn chạy cả khi không có người dùng chatbot</p>
        <p className="admin-help">Cập nhật cookie tại từng tài khoản trong tab Tài khoản Thông minh</p>
        {(state.account_pool?.accounts || []).map(row => <div className="admin-account" key={row.id}>
          <strong>{row.email || row.label}</strong><p>{accountLabels[row.status] || row.status}</p>
          <p>Kiểm tra gần nhất {date(row.checked_at)}<br />Cookie thời hạn phiên đổi gần nhất {date(row.rotated_at)}<br />Kiểm tra gia hạn gần nhất {date(row.rotation_checked_at)}<br />Lần thử gia hạn {date(row.refresh_attempt_at)}</p>
          {row.renewal_state === 'not_renewed' && <p role="status">Google chưa cấp cookie thời hạn phiên mới, phản hồi HTTP thành công chưa xác nhận gia hạn. Nếu tiếp tục bị đăng xuất, đăng nhập mới bằng Firefox rồi cập nhật cookie cho tài khoản này</p>}
        </div>)}
        <div className="admin-actions"><button className="button primary" disabled={busy || !state.account_pool?.accounts.length} onClick={() => action(() => tool('accounts-refresh'))}>Gia hạn phiên</button>
          <button className="button" disabled={busy} onClick={() => action(async () => { const data = await api('state'); setState(data); })}>Cập nhật trạng thái</button></div>
      </section>
      </div>
      <div role="tabpanel" id="admin-panel-embedding" aria-labelledby="admin-tab-embedding" hidden={tab !== 'embedding'}>
      <p className="admin-help">Chatbot tra cứu trực tiếp nội dung Qdrant theo mã tiêu chí, tên tiêu chí và từ khóa</p>
      {state.embedding_enabled && <form onSubmit={event => { event.preventDefault(); action(() => saveSettings('embedding')); }}>
        <section className="admin-card"><h2>Cấu hình embedding tùy chọn</h2>
          <div className="admin-models"><label>Địa chỉ Ollama<input type="url" required value={settings.embedding.url} disabled={busy} onChange={event => setSettings({ ...settings, embedding: { ...settings.embedding, url: event.target.value } })} /></label>
          <label>Model embedding<input required value={settings.embedding.model} disabled={busy} onChange={event => setSettings({ ...settings, embedding: { ...settings.embedding, model: event.target.value } })} /></label></div>
          <p className="admin-help">Chỉ dùng cho công cụ kiểm tra vector của quản trị</p>
          <button className="button primary" disabled={busy}>Lưu cấu hình embedding</button>
        </section>
      </form>}
      <section className="admin-card"><h2>Công cụ tra cứu</h2><label>Nội dung kiểm tra<textarea rows={3} maxLength={2000} value={text} onChange={event => setText(event.target.value)} disabled={busy} /></label>
        <div className="admin-actions">{state.embedding_enabled && <button className="button" disabled={busy || !text.trim()} onClick={() => action(() => tool('embedding-test', { text }))}>Kiểm tra vector</button>}
          <button className="button" disabled={busy || !text.trim()} onClick={() => action(() => tool('retrieval-test', { text }))}>Tìm tài liệu trong Qdrant</button></div>
        <p className="admin-help">Dùng cấu hình đã lưu, chỉ đọc Qdrant, không ghi lại vector hay thay đổi dữ liệu</p>
      </section>
      </div>
      <section className="admin-card"><h2>Kết quả kiểm tra</h2>{busy ? <p role="status">Đang xử lý yêu cầu</p> : null}<pre tabIndex={0}>{result || 'Chưa thực hiện kiểm tra'}</pre></section>
      <p className="admin-help">Service {state.services.join(', ')}</p>
    </>}
  </section>;
}
