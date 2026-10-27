import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { predictionCSV, PredictionWorkspace } from './PredictionWorkspace';

const preview = { rows: [{ id: 'lot-1', x1: '0' }], columns: ['id', 'x1'], count: 1 };
const output = { rows: [{ id: 'lot-1', x1: '0', Y: 2 }], columns: ['id', 'x1', 'Y'], count: 1, model_version: 'fixed-v1' };
const reply = (data: unknown) => new Response(JSON.stringify({ data }));
const csv = (name = 'input.csv') => new File(['id,x1\nlot-1,0\n'], name, { type: 'text/csv' });

function mockAPI({ ready = true, previewError = false, predictError = false } = {}) {
  const fetcher = vi.fn(async (input: RequestInfo | URL, options?: RequestInit) => {
    if (String(input).endsWith('/model')) return reply({ ready, model_version: ready ? 'fixed-v1' : null,
      features: ['x1', 'x2', 'x3', 'x4', 'x5', 'x6', 'x7', 'x8', 'x9'], message: ready ? 'Đã có bộ mô hình trên máy chủ' : 'Mô hình trên máy chủ chưa sẵn sàng' });
    if (options?.method !== 'POST') throw new Error('Only explicit CSV requests may write');
    if (String(input).endsWith('/preview')) return previewError
      ? new Response(JSON.stringify({ error: { message: 'CSV chưa hợp lệ' } }), { status: 422 }) : reply(preview);
    if (String(input).endsWith('/predictions')) return predictError
      ? new Response(JSON.stringify({ error: { message: 'Bộ mô hình chưa tương thích' } }), { status: 503 }) : reply(output);
    throw new Error(`Unexpected request: ${input}`);
  });
  vi.stubGlobal('fetch', fetcher);
  return fetcher;
}

describe('fixed-model assessment workflow', () => {
  it('loads only model metadata initially and predicts only after the user submits CSV', async () => {
    const fetcher = mockAPI(); const user = userEvent.setup(); render(<PredictionWorkspace legacyAvailable={false} />);
    await screen.findByText('Đã có bộ mô hình trên máy chủ');
    expect(fetcher.mock.calls).toHaveLength(1);
    expect(document.querySelectorAll('input[type=file]')).toHaveLength(2);
    expect(screen.getByRole('button', { name: 'Chạy dự đoán' }).hasAttribute('disabled')).toBe(true);
    await user.upload(screen.getByLabelText('File dữ liệu CSV'), csv());
    expect(await screen.findByRole('table', { name: 'Dữ liệu CSV đã nạp' })).toBeTruthy();
    expect(fetcher.mock.calls.some(([url]) => String(url).endsWith('/predictions'))).toBe(false);
    await user.click(screen.getByRole('button', { name: 'Chạy dự đoán' }));
    const table = await screen.findByRole('table', { name: 'Kết quả đánh giá theo từng ô đất' });
    expect(within(table).getByRole('cell', { name: '2' })).toBeTruthy();
    expect(screen.getByText('Kết quả từ phiên bản fixed-v1')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Xuất CSV' })).toBeTruthy();
    for (const [, options] of fetcher.mock.calls.filter(([, request]) => request?.method === 'POST')) {
      const form = options!.body as FormData;
      expect([...form.keys()]).toEqual(['csv']);
      expect(form.get('csv')).toBeInstanceOf(File);
    }
  });

  it('supports preview when the fixed model is missing and disables prediction', async () => {
    mockAPI({ ready: false }); const user = userEvent.setup(); render(<PredictionWorkspace legacyAvailable={false} />);
    await screen.findByText('Mô hình trên máy chủ chưa sẵn sàng');
    await user.upload(screen.getByLabelText('File dữ liệu CSV'), csv());
    await screen.findByRole('table');
    expect(screen.getByRole('button', { name: 'Chạy dự đoán' }).hasAttribute('disabled')).toBe(true);
    expect(screen.getByRole('button', { name: 'Kiểm tra lại mô hình' })).toBeTruthy();
  });

  it('shows CSV errors without presenting a result or an export', async () => {
    mockAPI({ previewError: true }); const user = userEvent.setup(); render(<PredictionWorkspace legacyAvailable={false} />);
    await user.upload(screen.getByLabelText('File dữ liệu CSV'), csv());
    expect((await screen.findByRole('alert')).textContent).toBe('CSV chưa hợp lệ');
    expect(screen.queryByRole('table')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Xuất CSV' })).toBeNull();
  });

  it('reports an incompatible model without replacing preview with a fabricated result', async () => {
    mockAPI({ predictError: true }); const user = userEvent.setup(); render(<PredictionWorkspace legacyAvailable={false} />);
    await screen.findByText('Đã có bộ mô hình trên máy chủ');
    await user.upload(screen.getByLabelText('File dữ liệu CSV'), csv());
    await screen.findByRole('table');
    await user.click(screen.getByRole('button', { name: 'Chạy dự đoán' }));
    expect((await screen.findByRole('alert')).textContent).toBe('Bộ mô hình chưa tương thích');
    expect(screen.getByRole('table', { name: 'Dữ liệu CSV đã nạp' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Xuất CSV' })).toBeNull();
  });

  it('ignores a late preview from the previously selected file', async () => {
    const fetcher = mockAPI(); const original = fetcher.getMockImplementation()!;
    let finishFirst!: (response: Response) => void;
    fetcher.mockImplementation(async (input, options) => {
      const file = (options?.body as FormData | undefined)?.get('csv');
      if (String(input).endsWith('/preview') && file instanceof File && file.name === 'first.csv') return new Promise<Response>(resolve => { finishFirst = resolve; });
      return original(input, options);
    });
    const user = userEvent.setup(); render(<PredictionWorkspace legacyAvailable={false} />);
    await user.upload(screen.getByLabelText('File dữ liệu CSV'), csv('first.csv'));
    await user.upload(screen.getByLabelText('File dữ liệu CSV'), csv('second.csv'));
    await screen.findByRole('table');
    await act(async () => { finishFirst(reply({ ...preview, rows: [{ id: 'stale', x1: '1' }] })); });
    await waitFor(() => expect(screen.queryByRole('cell', { name: 'stale' })).toBeNull());
    expect(screen.getByRole('cell', { name: 'lot-1' })).toBeTruthy();
  });

  it('exports the actual columns, Unicode, quotes and multiline values as CSV', () => {
    const content = predictionCSV({ columns: ['id', 'note', 'Y'], count: 1, rows: [{ id: 'lô,1', note: 'a"b\nc', Y: 0 }] });
    expect(content).toBe('\ufeff"id","note","Y"\r\n"lô,1","a""b\nc","0"');
  });
});
