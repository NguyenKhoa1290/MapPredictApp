import { isAssessmentResult, isDataset } from '../../shared/api/client';
import type { AssessmentResult, Dataset } from '../../shared/api/types';

export interface AssessmentState {
  inputFile: File | null; resultFile: File | null;
  preview: Dataset | null; result: AssessmentResult | null;
  tab: 'map' | 'data'; view: 'input' | 'result'; page: number;
}
export const emptyAssessment = (): AssessmentState => ({ inputFile: null, resultFile: null, preview: null,
  result: null, tab: 'map', view: 'input', page: 0 });
interface Snapshot { state: Record<string, unknown>; assets: Map<string, unknown> }
interface AtomicStore {
  db?: IDBDatabase;
  read(): Promise<Snapshot | null>;
  write(state: object, assets: Map<string, unknown>): Promise<unknown>;
}
declare global {
  interface Window { WorkspaceStore?: new (factory?: IDBFactory, name?: string) => AtomicStore }
}
const metadata = (file: File | null) => file ? { name: file.name, type: file.type, lastModified: file.lastModified } : null;
const record = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null;

export class AssessmentStorage {
  private store: AtomicStore;
  constructor(factory = window.indexedDB, name = 'mapPredict.assessment') {
    if (!window.WorkspaceStore || !factory) throw new Error('Browser storage unavailable');
    this.store = new window.WorkspaceStore(factory, name);
  }
  async read(): Promise<AssessmentState | null> {
    const snapshot = await this.store.read();
    if (!snapshot) return null;
    const { state, assets } = snapshot;
    if (state.schema !== 1 || !['map', 'data'].includes(String(state.tab)) || !['input', 'result'].includes(String(state.view))
      || !Number.isInteger(state.page) || Number(state.page) < 0) throw new Error('Unsupported assessment snapshot');
    const file = (key: string, info: unknown): File | null => {
      if (info === null) return null;
      const blob = assets.get(key);
      if (!record(info) || typeof info.name !== 'string' || typeof info.type !== 'string'
        || typeof info.lastModified !== 'number' || !(blob instanceof Blob)) throw new Error('Missing assessment file');
      return new File([blob], info.name, { type: info.type, lastModified: info.lastModified });
    };
    const preview = assets.get('preview') ?? null, result = assets.get('result') ?? null;
    if ((preview !== null && !isDataset(preview)) || (result !== null && !isAssessmentResult(result))) throw new Error('Invalid assessment data');
    const inputFile = file('input-file', state.input), resultFile = file('result-file', state.resultInput);
    if ((state.hasPreview !== (preview !== null)) || (state.hasResult !== (result !== null))
      || Boolean(inputFile) !== Boolean(preview) || (resultFile && (!result || (result as AssessmentResult).source !== 'uploaded'))
      || (result && (result as AssessmentResult).source === 'uploaded' && !resultFile)
      || (result && (result as AssessmentResult).source === 'prediction' && !inputFile)
      || (state.view === 'result' && !result)) throw new Error('Incomplete assessment snapshot');
    const dataset = state.view === 'result' ? result as AssessmentResult : preview as Dataset | null;
    return { inputFile, resultFile, preview: preview as Dataset | null, result: result as AssessmentResult | null,
      tab: state.tab as AssessmentState['tab'], view: state.view as AssessmentState['view'],
      page: Math.min(Number(state.page), Math.max(0, Math.ceil((dataset?.rows.length || 0) / 50) - 1)) };
  }
  write(value: AssessmentState) {
    const assets = new Map<string, unknown>();
    if (value.inputFile) assets.set('input-file', value.inputFile);
    if (value.resultFile) assets.set('result-file', value.resultFile);
    if (value.preview) assets.set('preview', value.preview);
    if (value.result) assets.set('result', value.result);
    return this.store.write({ schema: 1, input: metadata(value.inputFile), resultInput: metadata(value.resultFile),
      hasPreview: Boolean(value.preview), hasResult: Boolean(value.result), tab: value.tab, view: value.view, page: value.page }, assets);
  }
  close() { this.store.db?.close(); }
}
