import { useEffect, useRef, useState } from 'react';
import type * as Leaflet from 'leaflet';
import type { CellProperties, ProjectMapData } from '../api/types';

declare global {
  interface Window {
    L?: typeof Leaflet;
    Basemaps?: {
      motionOptions: (reducedMotion?: boolean) => Leaflet.MapOptions;
      createFallbackLayer: (L: typeof Leaflet, url: string, options: Leaflet.GridLayerOptions & { nativeMaxZoom?: number; fallbackDepth?: number }) => Leaflet.GridLayer;
    };
  }
}
type Props = {
  data: ProjectMapData; basemap: string; opacity: number; visible: boolean;
  activeLabels: (number | null)[]; selectedId: string | null; onSelect: (cell: CellProperties) => void;
};
const color = (y: number | null) => y === 0 ? '#ff0000' : y === 1 ? '#ffa500' : y === 2 ? '#008000' : '#52666a';

export function ProjectMapCanvas({ data, basemap, opacity, visible, activeLabels, selectedId, onSelect }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<Leaflet.Map | null>(null);
  const grid = useRef<Leaflet.GeoJSON | null>(null);
  const raster = useRef<Leaflet.GridLayer | null>(null);
  const selection = useRef(onSelect);
  const [error, setError] = useState('');
  const [tileError, setTileError] = useState(false);
  useEffect(() => { selection.current = onSelect; }, [onSelect]);
  useEffect(() => {
    const L = window.L;
    if (!L || !container.current) { setError('Không tải được bản đồ, bạn hãy tải lại trang'); return; }
    setError('');
    const instance = L.map(container.current, { ...window.Basemaps?.motionOptions(), preferCanvas: true,
      renderer: L.canvas({ padding: 0.3 }),
      minZoom: data.mode === 'native' ? -12 : 0,
      maxZoom: 22, crs: data.mode === 'native' ? L.CRS.Simple : L.CRS.EPSG3857 });
    map.current = instance;
    const layer = L.geoJSON(data.collection, {
      style: feature => ({ color: color(feature?.properties.Y ?? null), weight: 1, fillOpacity: 0.6 }),
      onEachFeature: (feature, cell) => {
        const name = document.createElement('span');
        name.className = 'project-cell-name';
        name.textContent = feature.properties.code || feature.properties.grid_id || 'Lô đất chưa có tên';
        cell.bindPopup(name, { className: 'project-cell-popup', minWidth: 70, maxWidth: 220, autoPan: false });
        cell.on('click', () => selection.current(feature.properties));
      },
    }).addTo(instance);
    grid.current = layer;
    // Reproject visible cells at the final map zoom, including canvas renderers
    // that missed a redraw while the view or layer visibility was changing.
    const syncGrid = () => layer.eachLayer(cell => {
      if (instance.hasLayer(cell)) (cell as Leaflet.Path).redraw();
    });
    instance.on('zoomend viewreset', syncGrid);
    if (layer.getBounds().isValid()) instance.fitBounds(layer.getBounds(), { padding: [28, 28], maxZoom: 19 });
    const observer = new ResizeObserver(() => instance.invalidateSize());
    observer.observe(container.current);
    return () => {
      observer.disconnect(); instance.off('zoomend viewreset', syncGrid);
      instance.remove(); map.current = null; grid.current = null;
    };
  }, [data]);
  useEffect(() => {
    const L = window.L, instance = map.current;
    setTileError(false);
    if (!L || !instance || data.mode !== 'geographic' || basemap === 'none') return;
    const satellite = basemap === 'satellite';
    if (!window.Basemaps) { setTileError(true); return; }
    const tiles = window.Basemaps.createFallbackLayer(L, satellite
      ? 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}?blankTile=false'
      : 'https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      nativeMaxZoom: 19, maxZoom: 22, fallbackDepth: satellite ? 4 : 0,
      attribution: satellite ? 'Tiles © Esri | Sources: Esri, Maxar, Earthstar Geographics, and the GIS User Community' : '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    });
    const failed = new Set<string>();
    const key = (event: Leaflet.TileEvent) => `${event.coords.z}:${event.coords.x}:${event.coords.y}`;
    tiles.on('tileerror', (event: Leaflet.TileErrorEvent) => {
      failed.add(key(event)); setTileError(true);
    });
    const settled = (event: Leaflet.TileEvent) => {
      failed.delete(key(event)); setTileError(failed.size > 0);
    };
    tiles.on('tileload', settled); tiles.on('tileunload', settled);
    tiles.addTo(instance); raster.current = tiles;
    return () => { tiles.remove(); tiles.off(); raster.current = null; };
  }, [data, basemap]);
  useEffect(() => {
    grid.current?.setStyle(feature => {
      const cell = feature?.properties as CellProperties;
      const shown = visible && activeLabels.includes(cell.Y);
      return { color: color(cell.Y), weight: cell.handles[0] === selectedId ? 3 : 1,
        opacity: shown ? opacity : 0, fillOpacity: shown && cell.Y !== null ? opacity * 0.6 : 0 };
    });
    grid.current?.eachLayer(layer => {
      const path = layer as Leaflet.Path & { feature?: { properties: CellProperties } };
      const properties = path.feature?.properties;
      if (properties) {
        const shown = visible && activeLabels.includes(properties.Y);
        if (shown && map.current && !map.current.hasLayer(path)) path.addTo(map.current);
        else if (!shown) path.remove();
      }
    });
  }, [data, visible, opacity, activeLabels, selectedId]);
  return <div className="project-map-stage">
    <div ref={container} className="project-map-canvas" aria-label="Bản đồ lưới dự án" />
    <div className="project-map-actions" aria-label="Điều hướng bản đồ">
      <button type="button" className="map-fit-button" title="Đưa bản đồ về toàn bộ layer lưới" onClick={() => {
        const instance = map.current, layer = grid.current;
        if (!instance || !layer?.getBounds().isValid()) return;
        instance.stop(); instance.invalidateSize({ animate: false });
        instance.fitBounds(layer.getBounds(), { padding: [28, 28], maxZoom: 18, animate: false });
      }}>Về layer</button>
      {data.mode === 'geographic' && basemap !== 'none' ? <button type="button" className="map-reload-button" onClick={() => {
        raster.current?.redraw();
      }}>Tải lại nền</button> : null}
    </div>
    {error ? <p className="map-message" role="alert">{error}</p> : null}
    {tileError ? <p className="map-message" role="status">Ảnh nền chưa tải đủ, bấm Tải lại nền hoặc chọn nền khác</p> : null}
  </div>;
}
