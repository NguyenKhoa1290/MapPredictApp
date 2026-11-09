import { memo } from 'react';

export const PredictionPanel = memo(function PredictionPanel() {
  return (<section id="predict-panel" className="workspace-panel" role="tabpanel" aria-labelledby="predict-tab" hidden>
                <div className="prediction-workspace">
                    <aside className="map-sidebar prediction-sidebar" aria-label="Điều khiển dự đoán">
                        <h1>Dự đoán dữ liệu</h1>
                        <p className="sidebar-intro">Nạp CSV và chạy mô hình trên máy chủ, xem dữ liệu và kết quả ở bên phải</p>
                        <form id="predict-form">
                            <h2>Dữ liệu đầu vào</h2>
                            <label htmlFor="csv-file">File dữ liệu (.csv)</label>
                            <input id="csv-file" name="csv" type="file" accept=".csv" required />
                            <button type="button" className="cad-action" data-remove-csv="csv-file" hidden>Xóa CSV</button>
                            <p className="field-note" data-file-label="csv-file" data-default-label="Chọn CSV để xem trước dữ liệu.">Chọn CSV để xem trước dữ liệu.</p>
                            <p className="field-note">Các cột đầu vào: x1 đến x9.</p>
                            <h2>Mô hình dự đoán</h2>
                            <p className="field-note">Dùng mô hình pipeline trên máy chủ, đã gộp bộ chuẩn hóa</p>
                            <button id="predict-button" className="glass-btn-primary" type="submit">Bắt đầu dự đoán</button>
                        </form>
                        <p id="predict-message" className="status-message" role="status" aria-live="polite"></p>
                    </aside>
                    <div id="prediction-result" className="prediction-data" aria-label="Bảng dữ liệu dự đoán">
                        <div className="prediction-toolbar">
                            <div>
                                <h2 id="prediction-title">Bảng dữ liệu</h2>
                                <p id="prediction-count">Chưa có dữ liệu để hiển thị.</p>
                            </div>
                            <a id="prediction-export" className="prediction-export" href="#" hidden>Xuất CSV</a>
                        </div>
                        <div id="prediction-empty" className="prediction-empty">
                            <svg width="48" height="48" viewBox="0 0 48 48" fill="none" aria-hidden="true"><rect x="6" y="8" width="36" height="32" rx="5" stroke="currentColor" strokeWidth="2"></rect><path d="M6 18h36M6 29h36M18 18v22M30 18v22" stroke="currentColor" strokeWidth="2"></path></svg>
                            <h3>Chưa có dữ liệu</h3>
                            <p>Chọn file CSV ở bên trái để xem trước.<br />Kết quả sẽ xuất hiện tại đây sau khi dự đoán.</p>
                        </div>
                        <div id="prediction-table-scroll" className="prediction-table-scroll" role="region" aria-label="Dữ liệu CSV và kết quả" tabIndex={0} hidden>
                            <table id="prediction-table" className="prediction-table"></table>
                        </div>
                        <div id="prediction-pager" className="prediction-pager" aria-label="Chuyển trang bảng dữ liệu" hidden>
                            <button id="prediction-page-prev" type="button">Trước</button>
                            <label htmlFor="prediction-page-number">Trang</label>
                            <input id="prediction-page-number" type="number" min="1" defaultValue="1" inputMode="numeric" />
                            <span id="prediction-page-total"></span>
                            <button id="prediction-page-next" type="button">Sau</button>
                        </div>
                    </div>
                </div>
            </section>);
});
