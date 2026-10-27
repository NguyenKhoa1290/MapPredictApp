import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PredictionWorkspace } from './PredictionWorkspace';
import type { AssessmentState } from './persistence';

const saved = vi.hoisted(() => ({ value: null as AssessmentState | null, readError: null as Error | null,
  writeError: null as Error | null, attempts: 0 }));
vi.mock('./persistence', async importOriginal => {
  const actual = await importOriginal<typeof import('./persistence')>();
  return { ...actual, AssessmentStorage: class {
    async read() { if (saved.readError) throw saved.readError; return saved.value; }
    async write(value: AssessmentState) { saved.attempts++; if (saved.writeError) throw saved.writeError; saved.value = value; }
    close() {}
  } };
});
const imported = { columns: ['id', 'Y'], rows: [{ id: 'existing', Y: 2 }], count: 1, source: 'uploaded', model_version: null };
const reply = (data: unknown) => new Response(JSON.stringify({ data }));
const file = (name: string) => new File(['id,Y\nexisting,2\n'], name, { type: 'text/csv' });
function mockAPI() {
  const fetcher = vi.fn(async (input: RequestInfo | URL, options?: RequestInit) => {
    if (String(input).endsWith('/model')) return reply({ ready: true, model_version: 'fixed-v1', features: ['x1'], message: 'Mô hình có sẵn' });
    if (String(input).endsWith('/results')) {
      const source = (options?.body as FormData).get('csv') as File;
      if (source.name === 'bad.csv') return new Response(JSON.stringify({ error: { message: 'CSV kết quả cần có cột Y' } }), { status: 422 });
      return reply(imported);
    }
    if (String(input).endsWith('/preview')) return reply({ columns: ['id', 'x1'], rows: [{ id: 'input', x1: '0' }], count: 1 });
    if (String(input).endsWith('/predictions')) return reply({ columns: ['id', 'x1', 'Y'], rows: [{ id: 'input', x1: '0', Y: 1 }], count: 1, model_version: 'fixed-v1' });
    throw new Error(`Unexpected request: ${input}`);
  });
  vi.stubGlobal('fetch', fetcher); return fetcher;
}
const savedStatus = () => waitFor(() => expect(screen.getByRole('status', { name: 'Trạng thái tự lưu' }).textContent).toBe('Đã tự lưu trên trình duyệt'));
async function importFile(user: ReturnType<typeof userEvent.setup>, name: string) {
  const input = screen.getByLabelText('CSV kết quả có sẵn');
  await waitFor(() => expect(input.hasAttribute('disabled')).toBe(false));
  await user.upload(input, file(name));
}
beforeEach(() => { saved.value = null; saved.readError = null; saved.writeError = null; saved.attempts = 0; });

describe('assessment save and restore lifecycle', () => {
  it('restores predicted results and the input file without any automatic POST', async () => {
    const fetcher = mockAPI(); const user = userEvent.setup(); const first = render(<PredictionWorkspace legacyAvailable={false} />);
    await screen.findByText('Mô hình có sẵn');
    await user.upload(screen.getByLabelText('File dữ liệu CSV'), file('input.csv'));
    await screen.findByRole('table'); await user.click(screen.getByRole('button', { name: 'Chạy dự đoán' }));
    await screen.findByRole('table', { name: 'Kết quả đánh giá theo từng ô đất' }); await savedStatus();
    first.unmount(); const previous = fetcher.mock.calls.length;
    render(<PredictionWorkspace legacyAvailable={false} />);
    await screen.findByText('Đã khôi phục phiên đã lưu');
    expect(screen.getByText('Đang dùng input.csv')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Xuất CSV' })).toBeTruthy();
    expect(within(screen.getByRole('table')).getByRole('cell', { name: '1' })).toBeTruthy();
    expect(fetcher.mock.calls.slice(previous).every(([, options]) => !options?.method)).toBe(true);
  });

  it('imports result CSV without running AI and restores table page and active tab', async () => {
    const fetcher = mockAPI(); const original = fetcher.getMockImplementation()!;
    fetcher.mockImplementation(async (input, options) => String(input).endsWith('/results') ? reply({ ...imported,
      count: 70, rows: Array.from({ length: 70 }, (_, index) => ({ id: 'lot-' + (index + 1), Y: index === 0 ? '' : 2 })) }) : original(input, options));
    const user = userEvent.setup(); const first = render(<PredictionWorkspace legacyAvailable={false} />);
    await importFile(user, 'ketqua.csv');
    await screen.findByRole('table');
    expect(screen.getByRole('cell', { name: 'Chưa có dữ liệu' })).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Sau' }));
    expect(screen.getByRole('cell', { name: 'lot-51' })).toBeTruthy();
    await user.click(screen.getByRole('tab', { name: 'Bản đồ' })); await savedStatus(); first.unmount();
    const previous = fetcher.mock.calls.length; render(<PredictionWorkspace legacyAvailable={false} />);
    await screen.findByText('Đã khôi phục phiên đã lưu');
    expect(screen.getByRole('tab', { name: 'Bản đồ' }).getAttribute('aria-selected')).toBe('true');
    await user.click(screen.getByRole('tab', { name: 'Dự đoán' }));
    expect(screen.getByRole('cell', { name: 'lot-51' })).toBeTruthy();
    expect(fetcher.mock.calls.slice(previous).every(([, options]) => !options?.method)).toBe(true);
    expect(fetcher.mock.calls.some(([url]) => String(url).endsWith('/predictions'))).toBe(false);
  });

  it('keeps the good result and saved file when a new result CSV is invalid', async () => {
    mockAPI(); const user = userEvent.setup(); render(<PredictionWorkspace legacyAvailable={false} />);
    await importFile(user, 'good.csv');
    await screen.findByRole('table'); await savedStatus(); const previous = saved.value;
    await importFile(user, 'bad.csv');
    expect((await screen.findByRole('alert')).textContent).toBe('CSV kết quả cần có cột Y');
    expect(screen.getByText('Đang dùng good.csv')).toBeTruthy();
    expect(screen.getByRole('cell', { name: 'existing' })).toBeTruthy();
    expect(saved.value).toBe(previous);
  });

  it('persists a result removal instead of restoring the removed result', async () => {
    mockAPI(); const user = userEvent.setup(); const first = render(<PredictionWorkspace legacyAvailable={false} />);
    await importFile(user, 'good.csv');
    await screen.findByRole('table'); await savedStatus();
    await user.click(screen.getByRole('button', { name: 'Gỡ kết quả' })); await savedStatus(); first.unmount();
    render(<PredictionWorkspace legacyAvailable={false} />); await screen.findByText('Đã khôi phục phiên đã lưu');
    expect(screen.queryByRole('table')).toBeNull(); expect(screen.queryByRole('button', { name: 'Xuất CSV' })).toBeNull();
    expect(saved.value?.result).toBeNull();
  });

  it('retains the previous save on storage failure and retries on a later change', async () => {
    mockAPI(); saved.writeError = new DOMException('Full', 'QuotaExceededError');
    const user = userEvent.setup(); render(<PredictionWorkspace legacyAvailable={false} />);
    await importFile(user, 'good.csv');
    await screen.findByRole('table');
    await waitFor(() => expect(screen.getByRole('status', { name: 'Trạng thái tự lưu' }).textContent).toContain('Chưa lưu được thay đổi'));
    expect(saved.value).toBeNull();
    saved.writeError = null; await user.click(screen.getByRole('tab', { name: 'Bản đồ' })); await savedStatus();
    expect(saved.value?.result?.rows[0].id).toBe('existing');
  });

  it('does not overwrite a snapshot when restoration fails or another tab saved first', async () => {
    mockAPI(); saved.readError = new Error('Unsupported schema');
    const user = userEvent.setup(); const first = render(<PredictionWorkspace legacyAvailable={false} />);
    await importFile(user, 'good.csv');
    await screen.findByRole('table'); expect(saved.attempts).toBe(0); first.unmount();
    saved.readError = null; saved.writeError = Object.assign(new Error('Conflict'), { name: 'WorkspaceConflictError' });
    render(<PredictionWorkspace legacyAvailable={false} />);
    await importFile(user, 'good.csv');
    await waitFor(() => expect(screen.getByRole('status', { name: 'Trạng thái tự lưu' }).textContent).toContain('Tab khác đã lưu phiên mới'));
    const attempts = saved.attempts;
    await user.click(screen.getByRole('tab', { name: 'Bản đồ' }));
    await user.click(screen.getByRole('tab', { name: 'Dự đoán' }));
    expect(saved.attempts).toBe(attempts); expect(saved.value).toBeNull();
  });
});
