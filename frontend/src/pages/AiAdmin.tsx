import { useEffect, useState } from 'react';
import '../styles/ai-admin.css';

type Model = { label: string; provider: 'gemini' | 'compatible'; model: string; url: string; api_key?: string; has_api_key?: boolean; clear_api_key?: boolean };
type Settings = { models: Record<'fast' | 'smart', Model>; embedding: { url: string; model: string } };
type State = { csrf: string; settings: Settings; gemini: { state: string; checked_at?: number; rotated_at?: number }; services: string[] };
const labels: Record<string, string> = { ready: 'Phiên đã xác thực', not_configured: 'Chưa nhập cookie', pending: 'Đang kiểm tra phiên', needs_attention: 'Cần kiểm tra hoặc nhập lại cookie', unavailable: 'Chưa kết nối được service' };
const date = (value?: number) => value ? new Date(value * 1000).toLocaleString('vi-VN') : 'Chưa có';

export function AiAdmin() {
  const [state, setState] = useState<State | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [password, setPassword] = useState('');
  const [cookie, setCookie] = useState('');
  const [account, setAccount] = useState('');
  const [text, setText] = useState('Quy tắc chấm điểm hiện trạng sử dụng đất');
  const [notice, setNotice] = useState('');
  const [result, setResult] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  async function api(path: string, body?: unknown, csrf = state?.csrf) {
    const response = await fetch('/api/v1/ai-admin/' + path, {
      method: body === undefined ? 'GET' : 'POST', credentials: 'same-origin', cache: 'no-store',
      headers: { 'Content-Type': 'application/json', ...(csrf ? { 'X-Admin-CSRF': csrf } : {}) },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    const payload = await response.json();
    if (response.status === 401) { setState(null); setSettings(null); setCookie(''); setResult(''); }
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
    if (name.startsWith('session-')) {
      setState(previous => previous ? { ...previous, gemini: data } : null);
      setCookie('');
    }
  }
  if (loading) return <section className="container inner-page" role="status">Đang kết nối trang quản trị</section>;
  return <section className="container inner-page ai-admin" aria-busy={busy}>
    <div className="admin-heading"><div><p className="eyebrow">CẤU HÌNH HỆ THỐNG</p><h1>Quản trị AI</h1><p>Quản lý model, phiên Gemini và công cụ embedding</p></div>
      {state ? <button className="button" disabled={busy} onClick={() => action(async () => { await api('logout', {}); setState(null); setSettings(null); setCookie(''); setResult(''); })}>Đăng xuất</button> : null}</div>
    {notice ? <p className="admin-notice" role="alert">{notice}</p> : null}
    {!state || !settings ? <form className="admin-login admin-card" onSubmit={event => { event.preventDefault(); action(async () => {
      const login = await api('login', { password }); setPassword('');
      const data = await api('state', undefined, login.csrf); setState(data); setSettings(data.settings);
    }); }}><h2>Đăng nhập quản trị</h2><label>Mật khẩu<input type="password" autoComplete="current-password" value={password} maxLength={256} required onChange={event => setPassword(event.target.value)} /></label>
      <button className="button primary" disabled={busy}>Đăng nhập</button></form> : <>
      <form onSubmit={event => { event.preventDefault(); action(async () => {
        const data = await api('settings', settings); setSettings(data); setNotice('Đã lưu cấu hình trên service AI');
      }); }}>
        <div className="admin-models">{(['fast', 'smart'] as const).map(mode => {
          const model = settings.models[mode];
          return <section className="admin-card" key={mode}><h2>{model.label}</h2>
            <label>Nguồn chạy<select value={model.provider} onChange={event => editModel(mode, { provider: event.target.value as Model['provider'] })} disabled={busy}>
              <option value="gemini">Gemini Web trong Docker</option><option value="compatible">API tương thích OpenAI</option></select></label>
            <label>Tên model<input required maxLength={150} value={model.model} onChange={event => editModel(mode, { model: event.target.value })} disabled={busy} /></label>
            {model.provider === 'compatible' ? <><label>Địa chỉ API, gồm /v1<input type="url" required value={model.url} onChange={event => editModel(mode, { url: event.target.value })} disabled={busy} /></label>
              <label>Khóa API mới<input type="password" autoComplete="new-password" value={model.api_key || ''} onChange={event => editModel(mode, { api_key: event.target.value })} placeholder={model.has_api_key ? 'Đã lưu khóa, để trống để giữ lại' : 'Nhập nếu API yêu cầu'} disabled={busy} /></label>
              <label className="admin-check"><input type="checkbox" checked={model.clear_api_key || false} onChange={event => editModel(mode, { clear_api_key: event.target.checked })} />Xóa khóa API đã lưu</label></> : <p className="admin-help">Dùng tên model do adapter khai báo, ví dụ gemini-3.6-flash, gemini-3.5-flash-thinking hoặc gemini-3.1-pro</p>}
            <button type="button" className="button" disabled={busy} onClick={() => action(() => tool('model-test', { mode }))}>Kiểm tra cấu hình đã lưu</button>
          </section>;
        })}</div>
        <section className="admin-card"><h2>Embedding cho quản trị</h2><p>Chatbot không gọi embedding, chỉ dùng tìm kiếm từ khóa trong Qdrant</p>
          <div className="admin-models"><label>Địa chỉ Ollama<input type="url" required value={settings.embedding.url} disabled={busy} onChange={event => setSettings({ ...settings, embedding: { ...settings.embedding, url: event.target.value } })} /></label>
          <label>Model embedding<input required value={settings.embedding.model} disabled={busy} onChange={event => setSettings({ ...settings, embedding: { ...settings.embedding, model: event.target.value } })} /></label></div>
          <p className="admin-help">Mô hình chỉ nạp khi dùng công cụ quản trị, gửi yêu cầu giải phóng model sau mỗi lượt</p></section>
        <button className="button primary" disabled={busy}>Lưu cấu hình</button>
      </form>
      <section className="admin-card"><h2>Phiên Gemini</h2><p><strong>{labels[state.gemini.state] || state.gemini.state}</strong></p>
        <p>Kiểm tra gần nhất {date(state.gemini.checked_at)}<br />Xoay cookie gần nhất {date(state.gemini.rotated_at)}</p>
        <p className="admin-help">Service kiểm tra phiên mỗi 20 phút, thử xoay cookie sau 12 giờ ngay cả khi không có người dùng chatbot</p>
        <p className="admin-help">Phiên bị Google thu hồi cần nhập cookie mới, việc gia hạn không bảo đảm duy trì đăng nhập vĩnh viễn</p>
        <label>Nhập file cookie JSON<input type="file" accept=".json,.txt" disabled={busy} onChange={event => { const file = event.target.files?.[0]; if (!file) return; if (file.size > 60000) { setNotice('File cookie tối đa 60 KB'); return; } file.text().then(setCookie).catch(() => setNotice('Không đọc được file cookie')); event.target.value = ''; }} /></label>
        <label>Hoặc dán nội dung cookie<textarea rows={3} autoComplete="off" value={cookie} maxLength={60000} onChange={event => setCookie(event.target.value)} disabled={busy} /></label>
        <label>Chỉ số tài khoản Google, để trống nếu mặc định<input inputMode="numeric" pattern="[0-9]{1,2}" maxLength={2} value={account} onChange={event => setAccount(event.target.value)} disabled={busy} /></label>
        <div className="admin-actions"><button className="button primary" disabled={busy || !cookie.trim()} onClick={() => action(() => tool('session-import', { cookie, account }))}>Lưu cookie và kiểm tra</button>
          <button className="button" disabled={busy} onClick={() => action(() => tool('session-refresh'))}>Gia hạn ngay</button>
          <button className="button" disabled={busy} onClick={() => action(async () => { const data = await api('state'); setState(data); })}>Cập nhật trạng thái</button></div>
      </section>
      <section className="admin-card"><h2>Công cụ embedding</h2><label>Nội dung kiểm tra<textarea rows={3} maxLength={2000} value={text} onChange={event => setText(event.target.value)} disabled={busy} /></label>
        <div className="admin-actions"><button className="button" disabled={busy || !text.trim()} onClick={() => action(() => tool('embedding-test', { text }))}>Kiểm tra vector</button>
          <button className="button" disabled={busy || !text.trim()} onClick={() => action(() => tool('retrieval-test', { text }))}>Tìm tài liệu bằng embedding</button></div>
        <p className="admin-help">Dùng cấu hình đã lưu, chỉ đọc Qdrant, không ghi lại vector hay thay đổi dữ liệu</p>
      </section>
      <section className="admin-card"><h2>Kết quả kiểm tra</h2>{busy ? <p role="status">Đang xử lý yêu cầu</p> : null}<pre tabIndex={0}>{result || 'Chưa thực hiện kiểm tra'}</pre></section>
      <p className="admin-help">Service {state.services.join(', ')}</p>
    </>}
  </section>;
}
