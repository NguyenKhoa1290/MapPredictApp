import { describe, expect, it, vi } from 'vitest';
import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { App } from './App';
import contentFile from '../../../config/public_content.json';
import catalogFile from '../../../config/projects.json';

vi.mock('../shared/ui/ProjectMapCanvas', () => ({
  ProjectMapCanvas: ({ data, visible, opacity, basemap, activeLabels, onSelect }: {
    data: import('../shared/api/types').ProjectMapData; visible: boolean; opacity: number; basemap: string;
    activeLabels: (number | null)[]; onSelect: (cell: import('../shared/api/types').CellProperties) => void;
  }) => <div aria-label="Bản đồ lưới dự án" data-visible={String(visible)} data-opacity={opacity} data-basemap={basemap} data-labels={JSON.stringify(activeLabels)}>
    <button onClick={() => onSelect(data.collection.features[0].properties)}>Chọn ô trên bản đồ</button>
  </div>,
}));

const mapFixture = {
  project_id: 'phu-quoc', mode: 'geographic', source_crs: 'EPSG:9208', crs_confirmed: false,
  crs_options: [{ code: 'EPSG:9208', name: 'VN-2000 / TM-3 104-45' }, { code: 'EPSG:3405', name: 'VN-2000 / UTM zone 48N' }],
  counts: { total: 2, scored: 1, unscored: 1, Y: { '0': 1, '1': 0, '2': 0 } },
  collection: { type: 'FeatureCollection', features: [
    { type: 'Feature', id: 'A', geometry: { type: 'Polygon', coordinates: [[[104, 10], [104.01, 10], [104.01, 10.01], [104, 10]]] }, properties: { grid_id: '1', code: 'PQ1', Y: 0, handles: ['A'], label_status: 'valid', fillColor: '#ff0000', fillOpacity: 0.6 } },
    { type: 'Feature', id: 'B', geometry: { type: 'Polygon', coordinates: [[[104.01, 10], [104.02, 10], [104.02, 10.01], [104.01, 10]]] }, properties: { grid_id: '2', code: null, Y: null, handles: ['B'], label_status: 'valid', fillColor: null, fillOpacity: 0 } },
  ] },
};

function mockAPI({ legacy = true, fail = false } = {}) {
  const fetcher = vi.fn(async (input: RequestInfo | URL, _options?: RequestInit) => {
    const url = String(input);
    if (fail) return new Response(JSON.stringify({ error: { message: 'Không tải được nội dung thử nghiệm.' } }), { status: 503 });
    if (url === '/api/v1/site-content') return new Response(JSON.stringify({ data: { ...contentFile, legacy_available: legacy } }));
    if (url === '/api/v1/projects') return new Response(JSON.stringify({ data: catalogFile.projects }));
    if (url === '/api/v1/predictions/model') return new Response(JSON.stringify({ data: { ready: true, model_version: 'test-v1', features: ['x1'], message: 'Đã có bộ mô hình trên máy chủ' } }));
    if (url.includes('/map?source_crs=')) return new Response(JSON.stringify({ data: mapFixture }));
    throw new Error(`Unexpected request: ${url}`);
  });
  vi.stubGlobal('fetch', fetcher);
  vi.stubGlobal('scrollTo', vi.fn());
  return fetcher;
}

function mount(path = '/') { return render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>); }

describe('React portal shell', () => {
  it('loads the introduction through read-only APIs with three main destinations', async () => {
    const fetcher = mockAPI(); mount();
    expect(await screen.findByRole('heading', { name: /Hiểu không gian/ })).toBeTruthy();
    const header = screen.getByRole('banner');
    const footer = screen.getByRole('contentinfo');
    expect(within(header).getByRole('link', { name: 'GeoPlan AI | Trang giới thiệu' }).textContent).toContain('GeoPlan AI');
    expect(header.querySelector('.brand-mark img')?.getAttribute('src')).toBe('/static/image/logo%201.png');
    expect(footer.querySelector('.brand-mark img')?.getAttribute('src')).toBe('/static/image/logo%202.png');
    expect(document.title).toBe('Giới thiệu | GeoPlan AI');
    const nav = screen.getByRole('navigation', { name: 'Điều hướng chính' });
    expect(within(nav).getAllByRole('link')).toHaveLength(3);
    expect(within(nav).getByRole('link', { name: 'Giới thiệu' }).getAttribute('aria-current')).toBe('page');
    expect(screen.queryByRole('link', { name: 'Quản trị AI' })).toBeNull();
    expect(document.querySelector('a[href*="admin"]')).toBeNull();
    expect(screen.queryByRole('heading', { name: /Những người/ })).toBeNull();
    expect(fetcher.mock.calls.every(([url]) => String(url).startsWith('/api/v1/'))).toBe(true);
    expect(fetcher.mock.calls).toHaveLength(2);
  });

  it('navigates and filters using the same project catalog', async () => {
    mockAPI(); const user = userEvent.setup(); mount();
    await screen.findByRole('heading', { name: /Hiểu không gian/ });
    const header = screen.getByRole('banner');
    await user.click(within(screen.getByRole('navigation')).getByRole('link', { name: 'Dự án' }));
    expect(await screen.findByRole('heading', { name: 'Khám phá các dự án' })).toBeTruthy();
    expect(screen.getByRole('banner')).toBe(header);
    await user.click(screen.getByRole('button', { name: /Bản đồ dự án/ }));
    expect(screen.getByRole('button', { name: 'Bản đồ dự án' })).toBeTruthy();
    expect(screen.getByRole('status').textContent).toBe('Đang hiển thị 3 trên 4 dự án');
    expect(screen.getAllByRole('link', { name: /^Khám phá dự án:/ })).toHaveLength(3);
    await user.click(screen.getByRole('button', { name: /Công cụ AI/ }));
    expect(screen.queryAllByRole('link', { name: /^Khám phá dự án:/ })).toHaveLength(0);
    await user.click(screen.getByRole('link', { name: /Đi đến công cụ đánh giá:/ }));
    expect(await screen.findByTitle('Công cụ đánh giá quỹ đất')).toBeTruthy();
    expect(screen.queryByRole('banner')).toBeNull();
    expect(screen.getByTitle('Công cụ đánh giá quỹ đất').getAttribute('src')).toBe('/legacy/?embedded=1');
    expect(screen.queryByRole('contentinfo')).toBeNull();
    expect(document.documentElement.style.getPropertyValue('--site-header-height')).toBe('0px');
    const frame = screen.getByTitle('Công cụ đánh giá quỹ đất');
    act(() => {
      window.dispatchEvent(new MessageEvent('message', { origin: 'https://invalid.example', source: (frame as HTMLIFrameElement).contentWindow,
        data: { type: 'map-predict:navigate-projects' } }));
    });
    expect(screen.queryByRole('heading', { name: 'Khám phá các dự án' })).toBeNull();
    act(() => {
      window.dispatchEvent(new MessageEvent('message', { origin: window.location.origin, source: (frame as HTMLIFrameElement).contentWindow,
        data: { type: 'map-predict:navigate-projects' } }));
    });
    expect(await screen.findByRole('heading', { name: 'Khám phá các dự án' })).toBeTruthy();
    expect(screen.getByRole('banner')).toBeTruthy();
    expect(screen.getByRole('contentinfo')).toBeTruthy();
    expect(screen.getByTitle('Công cụ đánh giá quỹ đất')).toBe(frame);
    await user.click(within(screen.getByRole('navigation')).getByRole('link', { name: /Đánh giá quỹ đất/ }));
    expect(screen.getByTitle('Công cụ đánh giá quỹ đất')).toBe(frame);
  });

  it('opens a dedicated map page, loads existing labels and offers only viewer controls', async () => {
    const fetcher = mockAPI(); mount('/projects/phu-quoc');
    expect(await screen.findByRole('heading', { name: 'Thành phố Phú Quốc' })).toBeTruthy();
    expect(await screen.findByLabelText('Bản đồ lưới dự án')).toBeTruthy();
    expect(screen.queryByRole('banner')).toBeNull();
    expect(screen.queryByRole('contentinfo')).toBeNull();
    expect(screen.getByText('2 ô lưới · 1 ô có nhãn Y')).toBeTruthy();
    expect(fetcher.mock.calls.some(([url]) => String(url).includes('/projects/phu-quoc/map?source_crs=EPSG%3A9208'))).toBe(true);
    expect(screen.queryByRole('button', { name: /dự đoán/i })).toBeNull();
    expect(document.querySelector('input[type=file]')).toBeNull();
  });

  it('changes map visibility, legend, background, selected cell and source CRS', async () => {
    const fetcher = mockAPI(); const user = userEvent.setup(); mount('/projects/phu-quoc');
    const map = await screen.findByLabelText('Bản đồ lưới dự án');
    await user.click(screen.getByRole('checkbox', { name: 'Hiển thị lưới' }));
    expect(map.getAttribute('data-visible')).toBe('false');
    await user.click(screen.getByRole('checkbox', { name: /Kết quả Y = 0/ }));
    expect(map.getAttribute('data-labels')).toBe('[1,2,null]');
    await user.selectOptions(screen.getByLabelText('Nền bản đồ'), 'satellite');
    expect(map.getAttribute('data-basemap')).toBe('satellite');
    await user.click(screen.getByRole('button', { name: 'Chọn ô trên bản đồ' }));
    expect(screen.getByText('PQ1', { selector: 'dd' })).toBeTruthy();
    expect(screen.getByText('Y = 0', { selector: 'dd' })).toBeTruthy();
    await user.selectOptions(screen.getByRole('listbox'), 'B');
    expect(within(screen.getByRole('region', { name: 'Thông tin ô' })).getByText('Chưa có dữ liệu', { selector: 'dd' })).toBeTruthy();
    expect(screen.getByRole('checkbox', { name: /Chưa có dữ liệu/ })).toBeTruthy();
    await user.selectOptions(screen.getByLabelText('Hệ tọa độ nguồn'), 'EPSG:3405');
    await waitFor(() => expect(fetcher.mock.calls.some(([url]) => String(url).endsWith('source_crs=EPSG%3A3405'))).toBe(true));
    expect(fetcher.mock.calls.every(([, options]) => !(options as RequestInit | undefined)?.method)).toBe(true);
  });

  it('switches assessment tabs with click and keyboard without API writes', async () => {
    const fetcher = mockAPI({ legacy: false }); const user = userEvent.setup(); mount('/assessment/csv');
    await screen.findByRole('heading', { name: 'Phiên CSV đã lưu' });
    expect(screen.queryByRole('link', { name: /Mở công cụ hiện tại/ })).toBeNull();
    await user.click(screen.getByRole('tab', { name: 'Dự đoán' }));
    expect(screen.getByRole('heading', { name: 'Bảng dữ liệu' })).toBeTruthy();
    await user.keyboard('{Home}');
    expect(screen.getByRole('tab', { name: 'Bản đồ' }).getAttribute('aria-selected')).toBe('true');
    expect(document.activeElement).toBe(screen.getByRole('tab', { name: 'Bản đồ' }));
    expect(fetcher.mock.calls).toHaveLength(3);
    expect(fetcher.mock.calls.every(([, options]) => !options?.method)).toBe(true);
  });

  it('reports failed API requests and retries without silently showing made-up content', async () => {
    const fetcher = mockAPI({ fail: true }); const user = userEvent.setup(); mount();
    expect(await screen.findByRole('alert')).toBeTruthy();
    expect(screen.queryByRole('heading', { name: /Hiểu không gian/ })).toBeNull();
    fetcher.mockImplementation(async input => new Response(JSON.stringify({ data: String(input).endsWith('site-content')
      ? { ...contentFile, legacy_available: true } : catalogFile.projects })));
    await user.click(screen.getByRole('button', { name: 'Thử lại' }));
    await waitFor(() => expect(screen.getByRole('heading', { name: /Hiểu không gian/ })).toBeTruthy());
  });

  it('rejects malformed successful JSON rather than rendering an empty application', async () => {
    mockAPI(); vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ data: {} }))));
    mount();
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain('không đúng cấu trúc');
  });
});
