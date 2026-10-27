import { beforeEach, afterEach, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { waitFor } from '@testing-library/dom';

const source = (path: string) => readFileSync(resolve('..', path), 'utf8');
const payload = { source_crs: 'EPSG:9208', layers: [{ name: 'grid.dxf', data: {
  features: [{ properties: { grid_id: '1', Y: 2 } }],
  join_summary: { total: 2, matched: 1, unmatched: 1, exact: 0, numeric: 1, ambiguous: 0,
    no_data: 1, invalid_y: 0, unused_results: 0, results_applied: true,
    samples: [{ layer_key: '1', result_key: 'TP01', status: 'matched', method: 'numeric' }] },
} }] };
type Harness = { rendered: unknown[]; setup: () => void; setResults: () => void; startWorkspace: () => void; setLoaded: () => void };
const harness = () => (window as unknown as { legacyHarness: Harness }).legacyHarness;
const element = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const submit = () => element('map-form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));

beforeEach(() => {
  document.body.innerHTML = source('templates/index.html').split('<body')[1].replace(/^[^>]*>/, '').split('</body>')[0];
  window.eval(source('wwwroot/join_preview.js'));
  window.eval(source('wwwroot/app.js').replace(/\ninitializeMap\(\);\s*$/, '') + `
    let selectedLayerId = null, inspectorScope = null, componentPage = 0, attributePage = 0;
    window.legacyHarness = {
      rendered: [],
      setup() {
        sharedSourceCrs = () => $('project-crs').value || 'EPSG:9208';
        renderMap = (layers) => window.legacyHarness.rendered.push(layers);
        predictionFiles = [{id:'grid',file:new File(['grid'],'grid.dxf'),columns:['grid_id']}];
        updatePredictionSources();
        renderResults([{code:'TP01',Y:2}], false);
        $('join-mode').value = 'numeric';
      },
      setResults() { renderResults([{code:'TP02',Y:0}], false); },
      setLoaded() { overlays = [{id:'grid'}]; },
      startWorkspace() {
        initializeMap = () => {};
        map = {getCenter:()=>({lat:21.7,lng:104.9}),getZoom:()=>16.5,on:()=>{},stop:()=>{},
          invalidateSize:()=>{},setView:(center,zoom)=>{window.restoredView={center,zoom}}};
        applySharedCrs = () => {};
        selectBasemap = (key) => { activeBasemap = key; };
        activeBasemap = 'streets';
        renderMap = (layers, styles) => {
          window.legacyHarness.rendered.push(layers);
          overlays = layers.map((item,index)=>({...styles?.[index],id:item.source_id,item,
            groups:styles?.[index]?.groups || new Map(), adjustments:styles?.[index]?.adjustments || {},
            style:styles?.[index]?.style || {},visible:true,opacity:.7}));
        };
        ${source('wwwroot/workspace.js')}
      }
    };
  `);
  harness().setup();
});
afterEach(() => { vi.unstubAllGlobals(); document.body.innerHTML = ''; });

it('previews freshly predicted rows, waits for confirmation and applies only once', async () => {
  const fetcher = vi.fn(async () => new Response(JSON.stringify(payload)));
  vi.stubGlobal('fetch', fetcher);
  submit();
  await waitFor(() => expect(element('join-apply').hidden).toBe(false));
  expect(harness().rendered).toHaveLength(0);
  const body = (fetcher.mock.calls as unknown as [string, RequestInit][])[0][1].body as FormData;
  expect((body.get('result') as File).name).toBe('KetQua.csv');
  expect(body.get('join_mode')).toBe('numeric');
  expect(element('join-preview').textContent).toContain('1/2 ô khớp');
  expect(element('join-preview').textContent).toContain('TP01');
  element('join-apply').click(); element('join-apply').click();
  expect(harness().rendered).toHaveLength(1);
});

it('changing a join choice invalidates a preview instead of applying stale colors', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(payload))));
  submit();
  await waitFor(() => expect(element('join-apply').hidden).toBe(false));
  element<HTMLSelectElement>('join-mode').value = 'exact';
  element('join-mode').dispatchEvent(new Event('change', { bubbles: true }));
  element('join-apply').click();
  expect(harness().rendered).toHaveLength(0);
  expect(element('join-preview').hidden).toBe(true);
});

it('ignores a late response after new predictions or user input', async () => {
  let resolveResponse!: (value: Response) => void;
  vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(resolve => { resolveResponse = resolve; })));
  submit();
  harness().setResults();
  resolveResponse(new Response(JSON.stringify(payload)));
  await new Promise(resolve => setTimeout(resolve, 0));
  expect(element('join-apply').hidden).toBe(true);
  expect(harness().rendered).toHaveLength(0);
  expect(element<HTMLButtonElement>('map-button').disabled).toBe(false);
});

it('keeps the current map intact when a preview request fails', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ error: 'CSV không hợp lệ' }), { status: 400 })));
  submit();
  await waitFor(() => expect(element('map-message').textContent).toContain('CSV không hợp lệ'));
  expect(harness().rendered).toHaveLength(0);
  expect(element('join-apply').hidden).toBe(true);
});

it('changing CRS invalidates first and allows its new preview request to complete', async () => {
  const fetcher = vi.fn(async () => new Response(JSON.stringify(payload)));
  vi.stubGlobal('fetch', fetcher);
  harness().setLoaded();
  const select = element<HTMLSelectElement>('project-crs');
  select.add(new Option('EPSG:9209', 'EPSG:9209'));
  select.value = 'EPSG:9209';
  select.dispatchEvent(new Event('change', { bubbles: true }));
  await waitFor(() => expect(element('join-apply').hidden).toBe(false));
  expect(fetcher).toHaveBeenCalledTimes(1);
  const init = (fetcher.mock.calls as unknown as [string, RequestInit][])[0][1];
  expect(init.signal?.aborted).toBe(false);
  expect((init.body as FormData).get('source_crs')).toBe('EPSG:9209');
});

it('restores join mode, grid geometry, results and fractional view without another request', async () => {
  let snapshot: { state: Record<string, unknown>; assets: Map<string, unknown> } | null = null;
  const writes = vi.fn();
  const cache = window as unknown as { WorkspaceStore: unknown; workspacePersistence: { ready: boolean; schedule: () => void; flush: () => Promise<boolean> }; restoredView: unknown };
  cache.WorkspaceStore = class {
    async read() { return snapshot; }
    async write(state: Record<string, unknown>, assets: Map<string, unknown>) { snapshot = { state, assets }; writes(); }
  };
  const fetcher = vi.fn(async () => new Response(JSON.stringify(payload)));
  vi.stubGlobal('fetch', fetcher);
  harness().startWorkspace();
  await waitFor(() => expect(cache.workspacePersistence.ready).toBe(true));
  submit();
  await waitFor(() => expect(element('join-apply').hidden).toBe(false));
  element('join-apply').click();
  cache.workspacePersistence.schedule();
  expect(await cache.workspacePersistence.flush()).toBe(true);
  expect(writes).toHaveBeenCalled();
  const saved = snapshot as unknown as { state: { joins: { mode: string } }; assets: Map<string, unknown> };
  expect(saved.state.joins.mode).toBe('numeric');
  expect(saved.assets.get('table:results')).toEqual([{ code: 'TP01', Y: 2 }]);
  element<HTMLSelectElement>('join-mode').value = 'exact';
  harness().rendered.length = 0;
  harness().startWorkspace();
  await waitFor(() => expect(cache.workspacePersistence.ready).toBe(true));
  expect(element<HTMLSelectElement>('join-mode').value).toBe('numeric');
  expect(harness().rendered[0]).toEqual(payload.layers);
  expect(cache.restoredView).toEqual({ center: [21.7, 104.9], zoom: 16.5 });
  expect(fetcher).toHaveBeenCalledTimes(1);
});
