import { Link } from 'react-router';
import type { Project } from '../api/types';

export function ProjectCards({ projects }: { projects: Project[] }) {
  return <div className="project-grid">{projects.map(project => <article className="project-card" key={project.id}>
    <div className={`project-image${project.kind === 'ai' ? ' ai-cover' : ''}`}>
      <img src={`/static/image/project-${project.id}.jpg`} alt={project.region} loading="lazy" />
      <span className="project-number">DỰ ÁN {project.index}</span>
    </div>
    <div className="project-body"><p className="project-meta">{project.category}</p>
      <h3>{project.kind === 'map' && <small>Đánh giá quy hoạch chi tiết</small>}{project.region}</h3>
      <div className="project-bottom"><span>{project.kind === 'ai' ? 'Dựa trên quy hoạch chi tiết' : 'Bản đồ và kết quả có sẵn'}</span>
        <Link className="project-open" to={project.kind === 'ai' ? '/assessment' : `/projects/${project.id}`}
          aria-label={`${project.kind === 'ai' ? 'Đi đến công cụ đánh giá' : 'Khám phá dự án'}: ${project.region}`}>
          {project.kind === 'ai' ? 'Đi đến công cụ đánh giá' : 'Khám phá dự án'}
        </Link>
      </div>
    </div>
  </article>)}</div>;
}
