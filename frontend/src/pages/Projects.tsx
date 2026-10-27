import { useState } from 'react';
import { usePublicData } from '../app/PublicData';
import { ProjectCards } from '../shared/ui/ProjectCards';

export function Projects() {
  const { projects } = usePublicData();
  const [filter, setFilter] = useState<'all' | 'map' | 'ai'>('all');
  const selected = filter === 'all' ? projects : projects.filter(project => project.kind === filter);
  return <section className="container inner-page" aria-labelledby="projects-title"><div className="page-intro"><p className="eyebrow">DANH MỤC DỰ ÁN</p><h1 id="projects-title">Khám phá các dự án</h1><p>Ba bản đồ đánh giá quy hoạch chi tiết và một công cụ để làm việc với dữ liệu của bạn</p></div>
    <div className="project-filter" role="group" aria-label="Lọc loại dự án">{([
      ['all', 'Tất cả'], ['map', 'Bản đồ dự án'], ['ai', 'Công cụ AI'],
    ] as const).map(([value, label]) => <button key={value} type="button" aria-pressed={filter === value} onClick={() => setFilter(value)}>{label}</button>)}</div>
    <ProjectCards projects={selected} />
    <p className="project-list-summary" role="status" aria-live="polite">Đang hiển thị {selected.length} trên {projects.length} dự án</p>
  </section>;
}
