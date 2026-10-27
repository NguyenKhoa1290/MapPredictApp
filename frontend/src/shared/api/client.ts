import type { Project, ProjectMapData, SiteContent } from './types';
import type { AssessmentResult, Dataset, ModelStatus, PredictionOutput } from './types';

const record = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null;
const text = (value: unknown): value is string => typeof value === 'string';
const nullableText = (value: unknown) => value === null || text(value);

export function isSiteContent(value: unknown): value is SiteContent {
  return record(value) && text(value.brand) && text(value.intro)
    && typeof value.legacy_available === 'boolean' && ['draft', 'published'].includes(String(value.content_status))
    && Array.isArray(value.visions) && value.visions.length === 3
    && value.visions.every(item => record(item) && text(item.title) && text(item.description))
    && Array.isArray(value.members) && value.members.length === 4
    && value.members.every(item => record(item) && text(item.id)
      && nullableText(item.name) && nullableText(item.role) && (item.bio === undefined || nullableText(item.bio))
      && nullableText(item.contact) && nullableText(item.photo));
}

export function isProjects(value: unknown): value is Project[] {
  if (!Array.isArray(value) || value.length !== 4) return false;
  const valid = value.every(item => record(item) && text(item.id) && /^[a-z0-9-]+$/.test(item.id)
    && text(item.name) && text(item.region) && text(item.category) && text(item.index)
    && Number.isInteger(item.variant) && ['map', 'ai'].includes(String(item.kind))
    && ['not_ready', 'preview', 'shell'].includes(String(item.status)));
  return valid && new Set(value.map(item => item.id)).size === 4;
}

async function read<T>(path: string, check: (data: unknown) => data is T, signal: AbortSignal, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/v1/${path}`, { ...init, signal, credentials: 'same-origin', headers: { Accept: 'application/json' } });
  let envelope: unknown;
  try { envelope = await response.json(); }
  catch { throw new Error('Không đọc được nội dung từ máy chủ'); }
  if (!response.ok) {
    const message = record(envelope) && record(envelope.error) && text(envelope.error.message)
      ? envelope.error.message : 'Không tải được nội dung, vui lòng thử lại';
    throw new Error(message);
  }
  if (!record(envelope) || !check(envelope.data)) throw new Error('Dữ liệu từ máy chủ không đúng cấu trúc yêu cầu');
  return envelope.data;
}

export const getSiteContent = (signal: AbortSignal) => read('site-content', isSiteContent, signal);
export const getProjects = (signal: AbortSignal) => read('projects', isProjects, signal);

export function isProjectMap(value: unknown): value is ProjectMapData {
  if (!record(value) || !text(value.project_id) || !['native', 'geographic'].includes(String(value.mode))
    || !nullableText(value.source_crs) || typeof value.crs_confirmed !== 'boolean'
    || !Array.isArray(value.crs_options) || !value.crs_options.every(item => record(item) && text(item.code) && text(item.name))
    || !record(value.counts) || !record(value.counts.Y)
    || !['total', 'scored', 'unscored'].every(key => Number.isInteger((value.counts as Record<string, unknown>)[key]))
    || !record(value.collection) || value.collection.type !== 'FeatureCollection' || !Array.isArray(value.collection.features)) return false;
  return value.collection.features.every(feature => record(feature) && feature.type === 'Feature'
    && record(feature.properties) && nullableText(feature.properties.grid_id) && nullableText(feature.properties.code)
    && [null, 0, 1, 2].includes(feature.properties.Y as number | null)
    && Array.isArray(feature.properties.handles) && feature.properties.handles.every(text)
    && record(feature.geometry) && feature.geometry.type === 'Polygon' && Array.isArray(feature.geometry.coordinates)
    && feature.geometry.coordinates.every(ring => Array.isArray(ring) && ring.length >= 4
      && ring.every(point => Array.isArray(point) && point.length >= 2 && point.every(n => typeof n === 'number' && Number.isFinite(n)))));
}
export const getProjectMap = (slug: string, crs: string, signal: AbortSignal) =>
  read(`projects/${encodeURIComponent(slug)}/map?source_crs=${encodeURIComponent(crs)}`, isProjectMap, signal);

export function isDataset(value: unknown): value is Dataset {
  return record(value) && Number.isInteger(value.count) && Number(value.count) > 0
    && Array.isArray(value.columns) && value.columns.length > 0 && value.columns.every(text)
    && new Set(value.columns).size === value.columns.length
    && Array.isArray(value.rows) && value.rows.length > 0 && value.rows.length <= Number(value.count)
    && value.rows.every(row => record(row) && Object.values(row).every(item => text(item) || (typeof item === 'number' && Number.isFinite(item))));
}
const isPrediction = (value: unknown): value is PredictionOutput => isDataset(value)
  && text((value as unknown as Record<string, unknown>).model_version)
  && value.rows.every(row => [0, 1, 2].includes(Number(row.Y)) && row.Y !== '');
const isModelStatus = (value: unknown): value is ModelStatus => record(value)
  && typeof value.ready === 'boolean' && nullableText(value.model_version)
  && Array.isArray(value.features) && value.features.every(text) && text(value.message);

export const getModelStatus = (signal: AbortSignal) => read('predictions/model', isModelStatus, signal);
function csvRequest<T>(path: string, file: File, signal: AbortSignal, check: (data: unknown) => data is T) {
  const form = new FormData(); form.append('csv', file);
  return read(path, check, signal, { method: 'POST', body: form });
}
export const previewPredictionCSV = (file: File, signal: AbortSignal) => csvRequest('predictions/preview', file, signal, isDataset);
export const runPrediction = (file: File, signal: AbortSignal) => csvRequest('predictions', file, signal, isPrediction);

export function isAssessmentResult(value: unknown): value is AssessmentResult {
  if (!isDataset(value)) return false;
  const item = value as unknown as Record<string, unknown>;
  return ['uploaded', 'prediction'].includes(String(item.source)) && nullableText(item.model_version)
    && (item.source !== 'prediction' || text(item.model_version)) && value.columns.includes('Y')
    && value.rows.length === value.count && value.rows.every(row => row.Y === '' || [0, 1, 2].includes(row.Y as number));
}
export const importResultCSV = (file: File, signal: AbortSignal) => csvRequest('predictions/results', file, signal, isAssessmentResult);
