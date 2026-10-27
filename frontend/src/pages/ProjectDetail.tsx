import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router';
import { usePublicData } from '../app/PublicData';
import { getProjectMap } from '../shared/api/client';
import type { CellProperties, ProjectMapData } from '../shared/api/types';
import { ProjectMapCanvas } from '../shared/ui/ProjectMapCanvas';

const LABELS = [0, 1, 2, null] as const;
const COLORS = ['#ff0000', '#ffa500', '#008000', '#52666a'];

function ProjectViewer({ slug }: { slug: string }) {
  const [crs, setCrs] = useState('EPSG:9208');
  const [data, setData] = useState<ProjectMapData | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  const [basemap, setBasemap] = useState('streets');
  const [visible, setVisible] = useState(true);
  const [opacity, setOpacity] = useState(0.85);
  const [labels, setLabels] = useState<(number | null)[]>([0, 1, 2, null]);
  const [selected, setSelected] = useState<CellProperties | null>(null);
  const [search, setSearch] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError(''); setSelected(null);
    getProjectMap(slug, crs, controller.signal).then(value => {
      if (!controller.signal.aborted) { setData(value); setLoading(false); }
    }).catch(reason => {
      if (!controller.signal.aborted) { setData(null); setError(reason instanceof Error ? reason.message : 'Không tải được bản đồ'); setLoading(false); }
    });
    return () => controller.abort();
  }, [slug, crs, attempt]);
  const matching = data?.collection.features.filter(feature => {
    const cell = feature.properties;
    return labels.includes(cell.Y) && (!search || ((cell.grid_id || '') + ' ' + (cell.code || '')).toLowerCase().includes(search.toLowerCase()));
  }) || [];
  return <div className="project-viewer">
    <aside className="project-map-sidebar" aria-label="Điều khiển bản đồ dự án">
      <p className="eyebrow">LAYER DỰ ÁN</p><h2>Lưới đánh giá</h2>
      <label className="map-check"><input type="checkbox" checked={visible} onChange={event => setVisible(event.target.checked)} />Hiển thị lưới</label>
      <label className="map-field">Độ đậm layer <output>{Math.round(opacity * 100)}%</output><input aria-label="Độ đậm layer" type="range" min="0" max="100" value={opacity * 100} onChange={event => setOpacity(Number(event.target.value) / 100)} /></label>
      <label className="map-field">Nền bản đồ<select value={basemap} onChange={event => setBasemap(event.target.value)}><option value="streets">Đường phố OpenStreetMap</option><option value="satellite">Vệ tinh Esri</option><option value="none">Không ảnh nền</option></select></label>
      <label className="map-field">Hệ tọa độ nguồn<select value={crs} onChange={event => setCrs(event.target.value)}><option value="">Lưới gốc · chưa định vị</option>{(data?.crs_options || [{ code: 'EPSG:9208', name: 'VN-2000 / TM-3 104-45' }]).map(item => <option key={item.code} value={item.code}>{item.code} · {item.name}</option>)}</select></label>
      <p className="map-crs-note">{crs ? crs + ' đang được dùng để xem thử, cần đối chiếu vị trí thực địa' : 'Chọn hệ tọa độ để hiển thị lưới bản vẽ gốc trên bản đồ'}</p>
      <fieldset className="map-legend"><legend>Chú giải theo nhãn</legend>{LABELS.map((label, index) => <label key={String(label)}><input type="checkbox" checked={labels.includes(label)} onChange={event => setLabels(current => event.target.checked ? [...current, label] : current.filter(value => value !== label))} /><span style={{ borderColor: COLORS[index], background: label === null ? 'transparent' : COLORS[index] }} />{label === null ? 'Chưa có dữ liệu' : 'Kết quả Y = ' + label}<small>{data ? label === null ? data.counts.unscored : data.counts.Y[String(label)] : ''}</small></label>)}</fieldset>
      {data ? <p className="map-summary">{data.counts.total.toLocaleString('vi-VN')} ô lưới · {data.counts.scored.toLocaleString('vi-VN')} ô có nhãn Y</p> : null}
      <section className="cell-detail" aria-labelledby="cell-title"><h3 id="cell-title">Thông tin ô</h3>{selected ? <dl><dt>Mã trên lưới</dt><dd>{selected.grid_id || 'Chưa xác định'}</dd><dt>Mã dữ liệu</dt><dd>{selected.code || 'Chưa ghép'}</dd><dt>Nhãn kết quả</dt><dd>{selected.Y === null ? 'Chưa có dữ liệu' : 'Y = ' + selected.Y}</dd><dt>Đối tượng CAD</dt><dd>{selected.handles.join(', ')}</dd></dl> : <p>Bấm ô trên bản đồ hoặc chọn mã trong danh sách bên dưới</p>}</section>
      <label className="map-field">Tìm mã ô<input value={search} onChange={event => setSearch(event.target.value)} placeholder="Ví dụ: TP01, BK21…" /></label>
      <label className="map-field">Chọn ô ({matching.length})<select size={5} value={selected?.handles[0] || ''} onChange={event => setSelected(data?.collection.features.find(feature => feature.properties.handles[0] === event.target.value)?.properties || null)}><option value="">Chưa chọn ô</option>{matching.map(feature => <option key={String(feature.id)} value={feature.properties.handles[0]}>{feature.properties.grid_id || 'CAD ' + feature.id} · {feature.properties.Y === null ? 'Chưa có dữ liệu' : 'Y=' + feature.properties.Y}</option>)}</select></label>
    </aside>
    <div className="project-map-main" aria-busy={loading}>
      {loading ? <div className="project-map-state" role="status">Đang tải lưới và nhãn dự án…</div> : error ? <div className="project-map-state" role="alert"><p>{error}</p><button type="button" className="button primary" onClick={() => setAttempt(value => value + 1)}>Tải lại bản đồ</button></div> : data ? <ProjectMapCanvas data={data} basemap={basemap} visible={visible} opacity={opacity} activeLabels={labels} selectedId={selected?.handles[0] || null} onSelect={setSelected} /> : null}
    </div>
  </div>;
}

export function ProjectDetail() {
  const { slug } = useParams();
  const { projects } = usePublicData();
  const project = projects.find(item => item.id === slug && item.kind === 'map');
  if (!project) return <section className="container inner-page"><h1>Không tìm thấy dự án</h1><Link className="text-link" to="/projects">Về danh sách dự án</Link></section>;
  return <section className="project-map-page" aria-labelledby="project-title"><div className="project-map-heading"><Link className="text-link" to="/projects">← Danh sách dự án</Link><div><p className="eyebrow">BẢN ĐỒ DỰ ÁN</p><h1 id="project-title">{project.region}</h1><p>{project.name}</p></div></div><ProjectViewer key={project.id} slug={project.id} /></section>;
}
