export interface Vision { title: string; description: string }
export interface Member { id: string; name: string | null; role: string | null; bio?: string | null; contact: string | null; photo: string | null }
export interface SiteContent {
  brand: string;
  intro: string;
  visions: Vision[];
  members: Member[];
  content_status: 'draft' | 'published';
  legacy_available: boolean;
}
export interface Project {
  id: string;
  name: string;
  region: string;
  kind: 'map' | 'ai';
  category: string;
  index: string;
  variant: number;
  status: 'not_ready' | 'preview' | 'shell';
}

export interface CellProperties {
  grid_id: string | null; code: string | null; Y: 0 | 1 | 2 | null;
  handles: string[]; label_status: string; fillColor: string | null; fillOpacity: number;
}
export interface ProjectMapData {
  project_id: string; mode: 'native' | 'geographic'; source_crs: string | null; crs_confirmed: boolean;
  crs_options: { code: string; name: string }[];
  collection: import('geojson').FeatureCollection<import('geojson').Polygon, CellProperties>;
  counts: { total: number; scored: number; unscored: number; Y: Record<string, number> };
}

export type DataRow = Record<string, string | number>;
export interface Dataset { rows: DataRow[]; columns: string[]; count: number }
export interface PredictionOutput extends Dataset { model_version: string }
export interface ModelStatus { ready: boolean; model_version: string | null; features: string[]; message: string }
export interface AssessmentResult extends Dataset { model_version: string | null; source: 'prediction' | 'uploaded' }
