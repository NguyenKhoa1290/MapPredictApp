import { Link } from 'react-router';
import { usePublicData } from '../app/PublicData';
import { PredictionWorkspace } from '../features/assessment/PredictionWorkspace';

/** Retains access to previously saved CSV sessions without changing their database. */
export function SavedAssessment() {
  const { content } = usePublicData();
  return <section className="container inner-page" aria-labelledby="saved-assessment-title">
    <Link className="text-link" to="/assessment">Về công cụ đánh giá</Link>
    <div className="page-intro"><h1 id="saved-assessment-title">Phiên CSV đã lưu</h1><p>Xem lại dữ liệu và kết quả trong phiên CSV trước đây</p></div>
    <PredictionWorkspace legacyAvailable={Boolean(content?.legacy_available)} />
  </section>;
}
