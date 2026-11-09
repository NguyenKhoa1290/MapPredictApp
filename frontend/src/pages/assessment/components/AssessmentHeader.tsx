import { memo } from 'react';

export const AssessmentHeader = memo(function AssessmentHeader({ crsOptions }: { crsOptions: { code: string; name: string }[] }) {
  return (<header className="workspace-header" role="group" aria-label="Điều khiển đánh giá">
                <div className="workspace-save">
                    <span id="workspace-save-status" role="status" aria-live="polite">Đang mở bản lưu trên trình duyệt…</span>
                </div>
                <div className="workspace-navigation">
                <a id="back-to-projects" className="workspace-back" href="/portal/projects" target="_top">← Quay lại dự án</a>
                <div className="tabs-glass" role="tablist" aria-label="Chức năng">
                    <button id="map-tab" className="glass-tab-btn active" type="button" role="tab" aria-selected="true" aria-controls="map-panel">Bản đồ</button>
                    <button id="predict-tab" className="glass-tab-btn" type="button" role="tab" aria-selected="false" aria-controls="predict-panel">Dự đoán</button>
                </div>
                </div>
                <div className="workspace-crs">
                    <label htmlFor="project-crs">Hệ tọa độ chung</label>
                    <select id="project-crs" form="map-form" required><option value="">Chọn hệ tọa độ nguồn</option>{crsOptions.map(crs => <option key={crs.code} value={crs.code}>{crs.code} · {crs.name}</option>)}<option value="custom">Nhập EPSG khác…</option></select>
                    <input id="project-crs-custom" form="map-form" type="text" placeholder="EPSG:9208" aria-label="Mã EPSG khác" pattern="[Ee][Pp][Ss][Gg]:[0-9]{4,6}" hidden disabled />
                    <input id="source-crs" name="source_crs" form="map-form" type="hidden" />
                </div>
            </header>);
});
