import { Route, Routes, Link } from 'react-router';
import { PublicDataProvider } from './PublicData';
import { Layout } from './Layout';
import { About } from '../pages/About';
import { Projects } from '../pages/Projects';
import { ProjectDetail } from '../pages/ProjectDetail';
import { SavedAssessment } from '../pages/SavedAssessment';
import { AiAdmin } from '../pages/AiAdmin';

export function App() {
  return <PublicDataProvider><Routes><Route element={<Layout />}>
    <Route index element={<About />} />
    <Route path="projects" element={<Projects />} />
    <Route path="projects/:slug" element={<ProjectDetail />} />
    <Route path="assessment" element={null} />
    <Route path="assessment/csv" element={<SavedAssessment />} />
    <Route path="admin/ai" element={<AiAdmin />} />
    <Route path="*" element={<section className="container inner-page"><h1>Không tìm thấy trang</h1><Link className="text-link" to="/">Về trang giới thiệu</Link></section>} />
  </Route></Routes></PublicDataProvider>;
}
