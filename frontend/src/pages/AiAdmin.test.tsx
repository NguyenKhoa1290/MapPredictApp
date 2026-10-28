import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { AiAdmin } from './AiAdmin';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it('requires service authentication and never stores the password in browser storage', async () => {
  const fetch = vi.fn().mockResolvedValueOnce({ status: 401, ok: false });
  vi.stubGlobal('fetch', fetch);
  render(<AiAdmin />);
  await screen.findByRole('heading', { name: 'Đăng nhập quản trị' });
  expect(screen.queryByText('Công cụ embedding')).toBeNull();
  fetch.mockResolvedValueOnce({ status: 401, ok: false, json: async () => ({ error: { message: 'Mật khẩu không đúng' } }) });
  fireEvent.change(screen.getByLabelText('Mật khẩu'), { target: { value: 'wrong-password' } });
  fireEvent.click(screen.getByRole('button', { name: 'Đăng nhập' }));
  await screen.findByRole('alert');
  expect(screen.getByRole('alert').textContent).toContain('Mật khẩu không đúng');
  expect(localStorage.getItem('password')).toBeNull();
});

it('shows authenticated settings, then logs out through the service with CSRF', async () => {
  const model = { label: 'Nhanh', model: 'test-fast', provider: 'gemini', url: '', has_api_key: false };
  const data = { csrf: 'session-csrf', settings: { models: { fast: model, smart: { ...model, label: 'Thông minh' } }, embedding: { url: 'http://ai-embedding:11434', model: 'test-embedding' } }, gemini: { state: 'ready' }, services: ['ai-assistant'] };
  const fetch = vi.fn().mockResolvedValueOnce({ status: 200, ok: true, json: async () => ({ data }) });
  vi.stubGlobal('fetch', fetch);
  render(<AiAdmin />);
  await screen.findByRole('tab', { name: 'Model' });
  fireEvent.click(screen.getByRole('tab', { name: 'Embedding' }));
  expect(screen.getByRole('heading', { name: 'Công cụ embedding' })).toBeTruthy();
  fetch.mockResolvedValueOnce({ status: 200, ok: true, json: async () => ({ data: { logged_out: true } }) });
  fireEvent.click(screen.getByRole('button', { name: 'Đăng xuất' }));
  await screen.findByRole('heading', { name: 'Đăng nhập quản trị' });
  await waitFor(() => expect(fetch).toHaveBeenLastCalledWith('/api/v1/ai-admin/logout', expect.objectContaining({ headers: expect.objectContaining({ 'X-Admin-CSRF': 'session-csrf' }) })));
});

it('sets a separate Pro passcode only through the authenticated service', async () => {
  const model = { label: 'Nhanh', model: 'test-fast', provider: 'gemini', url: '', has_api_key: false };
  const data = { csrf: 'admin-csrf', settings: { models: { fast: model, smart: { ...model, label: 'Thông minh', model: 'gemini-4-argon' } }, embedding: { url: 'http://ai-embedding:11434', model: 'test-embedding' } }, gemini: { state: 'ready' }, services: ['ai-assistant'], pro_access: { configured: false }, account_pool: { accounts: [] } };
  const fetch = vi.fn().mockResolvedValueOnce({ status: 200, ok: true, json: async () => ({ data }) });
  vi.stubGlobal('fetch', fetch);
  render(<AiAdmin />);
  fireEvent.click(await screen.findByRole('tab', { name: 'Tài khoản Thông minh' }));
  await screen.findByRole('heading', { name: 'Quyền sử dụng Thông minh' });
  fireEvent.change(screen.getByLabelText('Passcode Thông minh mới'), { target: { value: 'new-pro-passcode' } });
  fetch.mockResolvedValueOnce({ status: 200, ok: true, json: async () => ({ data: { configured: true } }) });
  fireEvent.click(screen.getByRole('button', { name: 'Đặt passcode Thông minh' }));
  await screen.findByText('Đã đặt passcode, người dùng phải nhập khi gọi Thông minh');
  expect(fetch).toHaveBeenLastCalledWith('/api/v1/ai-admin/tools/pro-passcode', expect.objectContaining({
    body: JSON.stringify({ passcode: 'new-pro-passcode' }), headers: expect.objectContaining({ 'X-Admin-CSRF': 'admin-csrf' }),
  }));
  expect((screen.getByLabelText('Passcode Thông minh mới') as HTMLInputElement).value).toBe('');
});

it('navigates tabs by keyboard, preserves drafts and saves only the active configuration group', async () => {
  const model = { label: 'Nhanh', model: 'test-fast', provider: 'gemini', url: '', has_api_key: false };
  const data = { csrf: 'admin-csrf', settings: { models: { fast: model, smart: { ...model, label: 'Thông minh', model: 'gemini-4-argon' } },
    embedding: { url: 'http://ai-embedding:11434', model: 'saved-embedding' } }, gemini: { state: 'ready' }, services: ['ai-assistant'] };
  const fetch = vi.fn().mockResolvedValueOnce({ status: 200, ok: true, json: async () => ({ data }) });
  vi.stubGlobal('fetch', fetch);
  render(<AiAdmin />);
  const models = await screen.findByRole('tab', { name: 'Model' });
  expect(screen.getAllByRole('tab')).toHaveLength(4);
  expect(screen.getAllByRole('tabpanel')).toHaveLength(1);
  fireEvent.keyDown(models, { key: 'ArrowRight' });
  expect(screen.getByRole('tab', { name: 'Tài khoản Thông minh' }).getAttribute('aria-selected')).toBe('true');
  fireEvent.keyDown(screen.getByRole('tab', { name: 'Tài khoản Thông minh' }), { key: 'Home' });
  fireEvent.change(screen.getAllByLabelText('Tên model')[0], { target: { value: 'draft-fast' } });
  fireEvent.click(screen.getByRole('tab', { name: 'Embedding' }));
  fireEvent.change(screen.getByLabelText('Model embedding'), { target: { value: 'draft-embedding' } });
  fireEvent.click(models);
  expect((screen.getAllByLabelText('Tên model')[0] as HTMLInputElement).value).toBe('draft-fast');
  expect(fetch).toHaveBeenCalledTimes(1);
  const saved = { ...data.settings, models: { ...data.settings.models, fast: { ...model, model: 'draft-fast' } } };
  fetch.mockResolvedValueOnce({ status: 200, ok: true, json: async () => ({ data: saved }) });
  fireEvent.click(screen.getByRole('button', { name: 'Lưu cấu hình' }));
  await screen.findByText('Đã lưu cấu hình trên service AI');
  const body = JSON.parse(fetch.mock.calls.at(-1)![1].body);
  expect(body.models.fast.model).toBe('draft-fast');
  expect(body.embedding.model).toBe('saved-embedding');
  fireEvent.click(screen.getByRole('tab', { name: 'Embedding' }));
  expect((screen.getByLabelText('Model embedding') as HTMLInputElement).value).toBe('draft-embedding');
});
