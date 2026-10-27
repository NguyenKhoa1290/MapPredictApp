import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type * as Leaflet from 'leaflet';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { ProjectMapCanvas } from './ProjectMapCanvas';
import type { CellProperties, ProjectMapData } from '../api/types';

const leafletSource = readFileSync(resolve('..', 'wwwroot/leaflet/leaflet.js'), 'utf8');
const basemapsSource = readFileSync(resolve('..', 'wwwroot/basemaps.js'), 'utf8');

const data: ProjectMapData = {
  project_id: 'test', mode: 'geographic', source_crs: 'EPSG:9208', crs_confirmed: false, crs_options: [],
  counts: { total: 1, scored: 1, unscored: 0, Y: { '0': 1, '1': 0, '2': 0 } },
  collection: { type: 'FeatureCollection', features: [{ type: 'Feature', id: 'A',
    properties: { grid_id: '1', code: 'TP01', Y: 0, handles: ['A'], label_status: 'valid', fillColor: '#ff0000', fillOpacity: 0.6 },
    geometry: { type: 'Polygon', coordinates: [[[105, 21], [105.001, 21], [105.001, 21.001], [105, 21.001], [105, 21]]] },
  }] },
};

describe('real Leaflet vector zoom integration (jsdom, no network)', () => {
  let map: Leaflet.Map;
  let grid: Leaflet.GeoJSON;
  beforeEach(() => {
    vi.useFakeTimers();
    // Only DOM size and drawing surface are simulated; map, projection and renderer are real Leaflet.
    vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockReturnValue(900);
    vi.spyOn(HTMLElement.prototype, 'clientHeight', 'get').mockReturnValue(600);
    const context = new Proxy({}, { get: () => vi.fn(), set: () => true });
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(context as CanvasRenderingContext2D);
    vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} });
    window.eval(leafletSource);
    window.eval(basemapsSource);
    const L = window.L!;
    const originalMap = L.map, originalGeoJSON = L.geoJSON;
    vi.spyOn(L, 'map').mockImplementation((container, options) => {
      map = originalMap(container, options); return map;
    });
    vi.spyOn(L, 'geoJSON').mockImplementation((source, options) => {
      grid = originalGeoJSON(source, options); return grid;
    });
  });
  afterEach(() => {
    // Leaflet schedules canvas drawing in RAF; dispose those jsdom callbacks with the map.
    cleanup(); vi.clearAllTimers(); vi.useRealTimers();
    Reflect.deleteProperty(window, 'L');
    Reflect.deleteProperty(window, 'Basemaps');
  });

  function renderedWidth() {
    // Canvas screen geometry after Leaflet has projected and clipped the polygon.
    const cell = grid.getLayers()[0] as Leaflet.Polygon & { _parts: Leaflet.Point[][] };
    const points = cell._parts.flat();
    return Math.max(...points.map(point => point.x)) - Math.min(...points.map(point => point.x));
  }
  const props = { data, basemap: 'none', visible: true, opacity: 0.85, activeLabels: [0, 1, 2, null], selectedId: null, onSelect: vi.fn<(cell: CellProperties) => void>() };

  it('scales rendered cells with the map when zooming in and out, including after hiding/restoring', () => {
    const view = render(<ProjectMapCanvas {...props} />);
    act(() => { map.setView([21.0005, 105.0005], 16, { animate: false }); });
    const initialWidth = renderedWidth();
    expect(initialWidth).toBeGreaterThan(20);
    act(() => { map.setZoom(17, { animate: false }); });
    expect(renderedWidth() / initialWidth).toBeCloseTo(2, 1);
    act(() => { map.setZoom(16, { animate: false }); });
    expect(renderedWidth()).toBe(initialWidth);
    view.rerender(<ProjectMapCanvas {...props} visible={false} />);
    act(() => { map.setZoom(17, { animate: false }); });
    view.rerender(<ProjectMapCanvas {...props} />);
    expect(renderedWidth() / initialWidth).toBeCloseTo(2, 1);
    expect(window.L!.map).toHaveBeenCalledTimes(1);
  });

  it('updates canvas geometry immediately for default zoom controls and retains popup/selection', () => {
    render(<ProjectMapCanvas {...props} />);
    act(() => { map.setView([21.0005, 105.0005], 16, { animate: false }); });
    const initialWidth = renderedWidth();
    act(() => { map.zoomIn(); });
    expect(map.getZoom()).toBe(17);
    expect(renderedWidth() / initialWidth).toBeCloseTo(2, 1);
    const cell = grid.getLayers()[0] as Leaflet.Polygon;
    act(() => { cell.fire('click', { latlng: cell.getBounds().getCenter() }); });
    expect(props.onSelect).toHaveBeenCalledWith(data.collection.features[0].properties);
    expect(cell.isPopupOpen()).toBe(true);
    expect(cell.getPopup()!.getContent()).toBeInstanceOf(HTMLElement);
    expect((cell.getPopup()!.getContent() as HTMLElement).textContent).toBe('TP01');
    act(() => { map.zoomOut(); });
    expect(renderedWidth()).toBe(initialWidth);
  });

  it('keeps vector scale increasing beyond the raster native zoom level', () => {
    const small: ProjectMapData = { ...data, collection: { ...data.collection, features: [{
      ...data.collection.features[0], geometry: { type: 'Polygon', coordinates: [
        [[105, 21], [105.0001, 21], [105.0001, 21.0001], [105, 21.0001], [105, 21]],
      ] },
    }] } };
    render(<ProjectMapCanvas {...props} data={small} />);
    act(() => { map.setView([21.00005, 105.00005], 19, { animate: false }); });
    const width = renderedWidth();
    act(() => { map.setZoom(20); });
    // Leaflet rounds projected vertices to whole pixels before drawing.
    expect(Math.abs(renderedWidth() - width * 2)).toBeLessThanOrEqual(2);
    act(() => { map.setZoom(21); });
    expect(Math.abs(renderedWidth() - width * 4)).toBeLessThanOrEqual(4);
    expect((grid.getLayers()[0] as Leaflet.Polygon).getBounds().getWest()).toBe(105);
  });

  it('returns to the actual layer after panning away and zooming deeply', () => {
    render(<ProjectMapCanvas {...props} />);
    act(() => { map.setView([1, 110], 22); });
    expect(map.getBounds().intersects(grid.getBounds())).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: 'Về layer' }));
    expect(map.getBounds().contains(grid.getBounds())).toBe(true);
    expect(map.getZoom()).toBeLessThanOrEqual(18);
    expect(map.getCenter().distanceTo(grid.getBounds().getCenter())).toBeLessThan(1);
  });

  it('reloads only the raster background after tile failure, keeping the layer and selection', () => {
    render(<ProjectMapCanvas {...props} basemap="satellite" />);
    let raster: Leaflet.GridLayer | undefined;
    map.eachLayer(layer => { if (layer instanceof window.L!.GridLayer) raster = layer; });
    expect(raster).toBeTruthy();
    const redraw = vi.spyOn(raster!, 'redraw');
    const count = grid.getLayers().length;
    act(() => { raster!.fire('tileerror', { coords: { x: 1, y: 1, z: 18 } }); });
    expect(screen.getByRole('status').textContent).toContain('Ảnh nền chưa tải đủ');
    fireEvent.click(screen.getByRole('button', { name: 'Tải lại nền' }));
    expect(redraw).toHaveBeenCalledTimes(1);
    expect(grid.getLayers()).toHaveLength(count);
    expect(map.hasLayer(grid)).toBe(true);
    expect(window.L!.map).toHaveBeenCalledTimes(1);
  });

  it('animates raster and canvas with the same scale before final reprojection', () => {
    Object.assign(window.L!.Browser, { any3d: true });
    render(<ProjectMapCanvas {...props} basemap="satellite" />);
    act(() => { map.setView([21.0005, 105.0005], 16, { animate: false }); });
    const initialWidth = renderedWidth();
    let raster: Leaflet.GridLayer | undefined;
    map.eachLayer(layer => { if (layer instanceof window.L!.GridLayer) raster = layer; });
    const oldTiles = (raster as unknown as { _levels: Record<number, { el: HTMLElement }> })._levels[16].el;
    const canvas = map.getContainer().querySelector('canvas')!;
    act(() => { map.zoomIn(undefined, { animate: true }); vi.advanceTimersByTime(20); });
    expect(map.getPane('mapPane')!.classList.contains('leaflet-zoom-anim')).toBe(true);
    const scale = (element: HTMLElement) => Number(/scale\(([^)]+)\)/.exec(element.style.transform)?.[1]);
    expect(scale(canvas)).toBeCloseTo(Math.SQRT2, 6);
    expect(scale(oldTiles)).toBeCloseTo(scale(canvas), 6);
    act(() => { vi.advanceTimersByTime(300); });
    expect(map.getZoom()).toBe(16.5);
    expect(map.getPane('mapPane')!.classList.contains('leaflet-zoom-anim')).toBe(false);
    expect(Math.abs(renderedWidth() - initialWidth * Math.SQRT2)).toBeLessThanOrEqual(2);
    expect(window.L!.map).toHaveBeenCalledTimes(1);
    act(() => { map.zoomOut(undefined, { animate: true }); vi.advanceTimersByTime(20); });
    expect(scale(canvas)).toBeCloseTo(1 / Math.SQRT2, 6);
    expect(parseFloat(canvas.style.width) * scale(canvas)).toBeGreaterThanOrEqual(map.getSize().x);
    expect(parseFloat(canvas.style.height) * scale(canvas)).toBeGreaterThanOrEqual(map.getSize().y);
    act(() => { vi.advanceTimersByTime(300); });
    expect(map.getZoom()).toBe(16);
    expect(renderedWidth()).toBe(initialWidth);
  });

  it('wheel zoom accepts fractional levels and keeps the pointer location anchored', () => {
    Object.assign(window.L!.Browser, { any3d: true });
    render(<ProjectMapCanvas {...props} />);
    act(() => { map.setView([21.0005, 105.0005], 16, { animate: false }); });
    const point = window.L!.point(300, 200);
    const before = map.containerPointToLatLng(point);
    act(() => {
      map.getContainer().dispatchEvent(new WheelEvent('wheel', { deltaY: -30, clientX: 300, clientY: 200, bubbles: true, cancelable: true }));
      vi.advanceTimersByTime(400);
    });
    expect(map.getZoom()).toBeGreaterThan(16);
    expect(map.getZoom()).toBeLessThan(17);
    expect(map.containerPointToLatLng(point).distanceTo(before)).toBeLessThan(3);
  });
});
