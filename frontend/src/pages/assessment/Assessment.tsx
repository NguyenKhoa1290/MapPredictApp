import { usePublicData } from '../../app/PublicData';
import { Link, useNavigate } from 'react-router';
import { useEffect, useRef, useState } from 'react';
import { AssessmentHeader } from './components/AssessmentHeader';
import { MapPanel } from './components/MapPanel';
import { PredictionPanel } from './components/PredictionPanel';
import { createAssessmentRuntime } from './engine/index.js';
import type { AssessmentRuntime } from './engine/index.js';
import './assessment.css';
import './assistant.css';

type CoordinateSystem = { code: string; name: string };

export function Assessment({ active = true }: { active?: boolean }) {
  const { content } = usePublicData();
  const root = useRef<HTMLDivElement>(null);
  const runtime = useRef<AssessmentRuntime | null>(null);
  const navigate = useNavigate();
  const navigateRef = useRef(navigate);
  navigateRef.current = navigate;
  const [coordinateSystems, setCoordinateSystems] = useState<CoordinateSystem[] | null>(null);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!content?.legacy_available) return;
    const controller = new AbortController();
    setError('');
    fetch('/api/v1/coordinate-systems', { signal: controller.signal }).then(async response => {
      const payload = await response.json();
      if (!response.ok || !Array.isArray(payload.data)) throw new Error('Không tải được danh sách hệ tọa độ');
      if (!controller.signal.aborted) setCoordinateSystems(payload.data);
    }).catch(reason => { if (!controller.signal.aborted) setError(reason.message); });
    return () => controller.abort();
  }, [content?.legacy_available, attempt]);
  useEffect(() => {
    if (!root.current || !coordinateSystems) return;
    try {
      const instance = createAssessmentRuntime(root.current, path => navigateRef.current(path));
      runtime.current = instance;
      return () => { runtime.current = null; instance.dispose(); };
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
  }, [coordinateSystems]);
  useEffect(() => { runtime.current?.setActive(active); }, [active, coordinateSystems]);
  if (!content?.legacy_available) return <section className="container inner-page"><h1>Đánh giá quỹ đất</h1><p>Công cụ bản đồ chưa khả dụng trong phiên bản này</p><Link className="text-link" to="/assessment/csv">Mở phiên CSV đã lưu</Link></section>;
  if (error) return <section className="container inner-page" role="alert"><h1>Chưa mở được công cụ đánh giá</h1><p>{error}</p><button className="button" onClick={() => { setCoordinateSystems(null); setAttempt(value => value + 1); }}>Thử lại</button></section>;
  if (!coordinateSystems) return <section className="container inner-page" role="status">Đang mở công cụ đánh giá…</section>;
  return <section aria-label="Đánh giá quỹ đất" className="assessment-page">
    <div ref={root} className="assessment-root workspace-mode map-mode">
      <div className="glass-page"><div className="glass-content-wrapper px-4"><div className="glass-container">
        <AssessmentHeader crsOptions={coordinateSystems} />
        <PredictionPanel />
        <MapPanel />
      </div></div></div>
    </div>
  </section>;
}
