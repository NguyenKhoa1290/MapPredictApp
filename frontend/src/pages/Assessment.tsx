import { usePublicData } from '../app/PublicData';
import { Link, useNavigate } from 'react-router';
import { useEffect, useRef } from 'react';

export function Assessment({ active = true }: { active?: boolean }) {
  const { content } = usePublicData();
  const frame = useRef<HTMLIFrameElement>(null);
  const navigate = useNavigate();
  useEffect(() => {
    if (!active) return;
    const token = requestAnimationFrame(() => frame.current?.contentWindow?.dispatchEvent(new Event('resize')));
    const onMessage = (event: MessageEvent) => {
      if (event.origin === window.location.origin && event.source === frame.current?.contentWindow
          && event.data?.type === 'map-predict:navigate-projects') navigate('/projects');
    };
    window.addEventListener('message', onMessage);
    return () => { cancelAnimationFrame(token); window.removeEventListener('message', onMessage); };
  }, [active, navigate]);
  if (!content?.legacy_available) return <section className="container inner-page"><h1>Đánh giá quỹ đất</h1><p>Công cụ bản đồ chưa khả dụng trong phiên bản này</p><Link className="text-link" to="/assessment/csv">Mở phiên CSV đã lưu</Link></section>;
  return <section className="legacy-assessment" aria-label="Đánh giá quỹ đất">
    <iframe ref={frame} className="legacy-assessment-frame" src="/legacy/?embedded=1" title="Công cụ đánh giá quỹ đất" />
  </section>;
}
