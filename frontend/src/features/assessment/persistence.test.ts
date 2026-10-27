import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { Blob as NativeBlob, File as NativeFile } from 'node:buffer';
import { IDBFactory, IDBObjectStore as FakeObjectStore } from 'fake-indexeddb';
import { AssessmentStorage, emptyAssessment } from './persistence';
import type { AssessmentState } from './persistence';

const source = readFileSync(resolve('..', 'wwwroot/workspace_store.js'), 'utf8');
let factory: IDBFactory;
let opened: AssessmentStorage[];
const open = () => { const store = new AssessmentStorage(factory); opened.push(store); return store; };
function state(): AssessmentState {
  return { ...emptyAssessment(), inputFile: new File(['id,x1\nA1,0'], 'input.csv', { type: 'text/csv', lastModified: 1 }),
    resultFile: new File(['id,Y\nA1,0'], 'result.csv', { type: 'text/csv', lastModified: 2 }),
    preview: { columns: ['id', 'x1'], rows: [{ id: 'A1', x1: '0' }], count: 1 },
    result: { columns: ['id', 'Y'], rows: [{ id: 'A1', Y: 0 }], count: 1, source: 'uploaded', model_version: null },
    tab: 'data', view: 'result' };
}

beforeEach(() => {
  vi.stubGlobal('Blob', NativeBlob); vi.stubGlobal('File', NativeFile);
  window.eval(source); factory = new IDBFactory(); opened = [];
});
afterEach(() => { opened.forEach(store => store.close()); Reflect.deleteProperty(window, 'WorkspaceStore'); });

describe('assessment IndexedDB persistence', () => {
  it('round-trips files, results and view without changing the old workspace database', async () => {
    const legacy = new window.WorkspaceStore!(factory, 'mapPredict.workspace');
    await legacy.read(); await legacy.write({ marker: 'legacy' }, new Map());
    const first = open(); expect(await first.read()).toBeNull(); await first.write(state());
    const restored = await open().read();
    expect(restored?.result?.rows[0].Y).toBe(0);
    expect(restored?.inputFile?.name).toBe('input.csv');
    expect(await restored?.inputFile?.text()).toBe('id,x1\nA1,0');
    expect(restored?.resultFile?.lastModified).toBe(2);
    expect(restored?.tab).toBe('data'); expect(restored?.view).toBe('result');
    expect((await legacy.read())?.state.marker).toBe('legacy'); legacy.db?.close();
  });

  it('does not rewrite file and table assets for a tab-only change', async () => {
    const store = open(); await store.read(); const value = state(); await store.write(value);
    const put = vi.spyOn(FakeObjectStore.prototype, 'put');
    await store.write({ ...value, tab: 'map' });
    expect(put.mock.contexts.filter(context => (context as IDBObjectStore).name === 'assets')).toHaveLength(0);
    expect(put.mock.contexts.filter(context => (context as IDBObjectStore).name === 'state')).toHaveLength(1);
  });

  it('rejects a stale tab write instead of overwriting the newer saved state', async () => {
    const first = open(), stale = open(); await first.read(); await stale.read();
    await first.write(state());
    await expect(stale.write(emptyAssessment())).rejects.toHaveProperty('name', 'WorkspaceConflictError');
    expect((await open().read())?.result?.rows[0].id).toBe('A1');
  });

  it('rolls back both metadata and assets if a write fails', async () => {
    const store = open(); await store.read(); const good = state(); await store.write(good);
    const original = FakeObjectStore.prototype.put;
    const put = vi.spyOn(FakeObjectStore.prototype, 'put').mockImplementation(function (this: IDBObjectStore, value, key) {
      if (this.name === 'assets' && key === 'result') throw new DOMException('Full', 'QuotaExceededError');
      return original.call(this, value, key);
    });
    await expect(store.write({ ...good, result: { ...good.result!, rows: [{ id: 'new', Y: 2 }] } })).rejects.toHaveProperty('name', 'QuotaExceededError');
    put.mockRestore();
    expect((await open().read())?.result?.rows[0].id).toBe('A1');
  });

  it('removes discarded file assets so they do not reappear after restoration', async () => {
    const store = open(); await store.read(); await store.write(state()); await store.write(emptyAssessment());
    const restored = await open().read();
    expect(restored?.inputFile).toBeNull(); expect(restored?.result).toBeNull();
    const raw = new window.WorkspaceStore!(factory, 'mapPredict.assessment');
    expect((await raw.read())?.assets.size).toBe(0); raw.db?.close();
  });

  it('does not rewrite snapshots with a newer unsupported schema', async () => {
    const raw = new window.WorkspaceStore!(factory, 'mapPredict.assessment');
    await raw.read(); await raw.write({ schema: 999 }, new Map());
    await expect(open().read()).rejects.toThrow('Unsupported assessment snapshot');
    expect((await raw.read())?.state.schema).toBe(999); raw.db?.close();
  });
});
