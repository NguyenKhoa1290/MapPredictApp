import { memo } from 'react';

export const MapPanel = memo(function MapPanel() {
  return (<section id="map-panel" className="workspace-panel" role="tabpanel" aria-labelledby="map-tab">
                <div className="map-workspace">
                    <aside className="map-sidebar" aria-label="Điều khiển lớp bản đồ">
                        <h1>Bản đồ lớp dữ liệu</h1>
                        <p className="sidebar-intro">Nạp DXF làm layer nền; lưới DXF hoặc GeoPackage cho dự đoán. Tất cả dùng hệ tọa độ chung ở thanh trên.</p>
                        <div className="basemap-controls">
                            <label className="basemap-select-label" htmlFor="basemap-select">Nền bản đồ</label>
                            <select id="basemap-select" aria-describedby="basemap-zoom-note">
                                <option value="satellite">Vệ tinh · Esri</option>
                                <option value="streets">Đường phố / giao thông · OpenStreetMap</option>
                            </select>
                            <label htmlFor="basemap-labels"><input id="basemap-labels" type="checkbox" defaultChecked aria-describedby="basemap-labels-note" />Tên đường và địa danh</label>
                            <p id="basemap-labels-note" className="field-note">Nhãn nền Esri; phóng to để xem chi tiết. Không bật nhãn chữ trong DXF.</p>
                            <p id="basemap-zoom-note" className="field-note">Zoom sâu dùng ảnh nền phóng lớn; vệ tinh thiếu ảnh sẽ thử mức thấp hơn. Layer vẫn zoom độc lập. Đường phố không phải giao thông trực tiếp.</p>
                            <p id="basemap-message" className="field-note text-danger" role="status" aria-live="polite"></p>
                        </div>
                        <div className="layer-heading"><h2>Layer đã nạp</h2><span id="layer-count">0</span></div>
                        <button id="fit-all-layers" className="cad-action" type="button" disabled>Xem tất cả layer</button>
                        <p className="field-note">Bấm tên layer hoặc đối tượng trên bản đồ để xem thành phần, thuộc tính và bảng màu.</p>
                        <div id="layer-list" className="layer-list"><p className="empty-layers">Chưa có layer. Chọn file bên dưới rồi nhấn Hiển thị trên bản đồ.</p></div>
                        <form id="map-form">
                            <h2>Dữ liệu bản đồ</h2>
                            <label htmlFor="cad-file">Thêm layer nền (.dxf)</label>
                            <input id="cad-file" name="cad" type="file" accept=".dxf" multiple />
                            <p className="field-note">Chọn nhiều DXF cùng lúc hoặc thêm nhiều lần. File đã thêm vẫn được giữ; dùng Gỡ file để bỏ khỏi danh sách.</p>
                            <div id="cad-options" className="cad-options"></div>
                            <p className="field-note">Với tọa độ cục bộ, chọn Phân tích độ dịch ở từng file để xem đề xuất từ block. Chỉ áp dụng sau khi kiểm tra vị trí; EPSG vẫn do bạn chọn.</p>
                            <details className="prediction-layer-options">
                                <summary>Lưới dự đoán · DXF / GeoPackage</summary>
                                <label htmlFor="layer-file">Thêm lưới dự đoán (.dxf, .gpkg)</label>
                                <input id="layer-file" name="layer" type="file" accept=".dxf,.gpkg" multiple />
                                <p className="field-note">DXF: đọc ô polyline kín và mã từ nhãn TEXT/MTEXT bên trong thành grid_id. Không cần chuyển sang GPKG; không tự tạo tenlodat. Ghép CSV bằng mã thực tế, không theo thứ tự dòng.</p>
                                <div id="prediction-sources"></div>
                                <p id="prediction-crs-info" className="field-note"></p>
                                <div className="offset-fields">
                                    <label htmlFor="prediction-offset-x">Dịch X (m)<input id="prediction-offset-x" name="prediction_offset_x" type="number" step="any" defaultValue="0" /></label>
                                    <label htmlFor="prediction-offset-y">Dịch Y (m)<input id="prediction-offset-y" name="prediction_offset_y" type="number" step="any" defaultValue="0" /></label>
                                </div>
                                <label htmlFor="result-file">Kết quả (.csv), nếu chưa chạy dự đoán</label>
                                <input id="result-file" name="result" type="file" accept=".csv" />
                                <p className="field-note" data-file-label="result-file" data-default-label="Chưa chọn file">Chưa chọn file</p>
                                <button type="button" className="cad-action" data-remove-csv="result-file" hidden>Xóa CSV kết quả</button>
                                <div id="join-controls" hidden>
                                    <div id="common-layer-join">
                                        <label htmlFor="gpkg-join">Cột ghép trong lưới dự đoán</label>
                                        <select id="gpkg-join" className="glass-select" name="gpkg_join"></select>
                                    </div>
                                    <label htmlFor="csv-join">Cột ghép trong CSV</label>
                                    <select id="csv-join" className="glass-select" name="csv_join"></select>
                                    <label htmlFor="join-mode">Cách ghép mã ô</label>
                                    <select id="join-mode" className="glass-select" name="join_mode">
                                        <option value="exact">Mã chính xác</option>
                                        <option value="numeric">Mã chính xác rồi phần số duy nhất</option>
                                    </select>
                                    <p className="field-note">Ghép phần số chỉ dùng khi mã duy nhất ở cả hai bên, không tự ghép mã trùng hoặc mã có nhiều cụm số</p>
                                </div>
                            </details>
                            <button id="join-preview-button" className="cad-action" type="button" hidden>Xem trước ghép kết quả</button>
                            <section id="join-preview" className="join-preview" aria-label="Xem trước ghép kết quả" aria-live="polite" hidden></section>
                            <button id="join-apply" className="cad-action" type="button" hidden>Áp dụng kết quả lên bản đồ</button>
                            <button id="map-button" className="glass-btn-primary" type="submit">Hiển thị trên bản đồ</button>
                            <button id="map-export-pdf" className="cad-action map-export-button" type="button" title="Xuất vùng bản đồ đang nhìn thấy, không kèm thanh bên">Xuất PDF bản đồ</button>
                            <p id="map-export-status" className="status-message" role="status" aria-live="polite"></p>
                        </form>
                        <p id="map-message" className="status-message" role="status" aria-live="polite"></p>
                    </aside>
                    <div className="map-canvas">
                        <div id="leafletMap" aria-label="Bản đồ địa lý và các layer dữ liệu"></div>
                        <aside id="layer-inspector" className="layer-inspector" aria-label="Thông tin và ký hiệu layer" hidden>
                            <header className="inspector-heading"><h2 id="inspector-title">Thông tin layer</h2><button id="inspector-close" type="button" aria-label="Đóng thông tin layer">Đóng</button></header>
                            <div className="inspector-body">
                                <p id="inspector-meta" className="field-note"></p>
                                <p id="inspector-warnings" className="inspector-warnings" role="status"></p>
                                <fieldset className="style-editor">
                                    <legend>Màu sắc và cách hiển thị</legend>
                                    <label>Áp dụng cho<select id="style-scope"></select></label>
                                    <label className="inline-control"><input id="style-source" type="checkbox" />Màu nguồn / kế thừa</label>
                                    <div id="style-palette" className="style-palette" aria-label="Bảng màu nhanh"></div>
                                    <div className="style-colors"><label>Màu nét<input id="style-stroke" type="color" /></label><label>Màu vùng tô<input id="style-fill" type="color" /></label></div>
                                    <label>Độ dày nét <output id="style-weight-value"></output><input id="style-weight" type="range" min="0" max="8" step="0.5" /></label>
                                    <label>Độ đậm vùng tô <output id="style-fill-opacity-value"></output><input id="style-fill-opacity" type="range" min="0" max="100" /></label>
                                    <label>Cỡ điểm <output id="style-radius-value"></output><input id="style-radius" type="range" min="1" max="16" /></label>
                                    <label>Kiểu nét<select id="style-dash"><option value="">Liền</option><option value="8 5">Đứt</option><option value="2 5">Chấm</option></select></label>
                                    <div className="style-colors"><label>Dịch Đông (m)<input id="style-east" type="number" min="-100000" max="100000" step="any" defaultValue="0" /></label><label>Dịch Bắc (m)<input id="style-north" type="number" min="-100000" max="100000" step="any" defaultValue="0" /></label></div>
                                    <p className="field-note">Số âm để dịch Tây hoặc Nam, độ dịch hiển thị tính từ vị trí gốc và không sửa file DXF</p>
                                    <button id="style-reset" className="cad-action" type="button">Khôi phục kiểu nguồn</button>
                                    <p className="field-note">Thiết lập thành phần ưu tiên hơn cả layer. Hiệu chỉnh hue/contrast bên dưới được áp dụng sau màu nguồn hoặc màu tự chọn, không sửa file gốc.</p>
                                </fieldset>
                                <fieldset className="style-editor color-adjustments-editor">
                                    <legend>Hiệu chỉnh màu layer</legend>
                                    <label>Hue (sắc độ) <output id="adjust-hue-value">0°</output><input id="adjust-hue" type="range" min="-180" max="180" defaultValue="0" step="1" /></label>
                                    <label>Contrast (tương phản) <output id="adjust-contrast-value">100%</output><input id="adjust-contrast" type="range" min="0" max="200" defaultValue="100" /></label>
                                    <label>Brightness (độ sáng) <output id="adjust-brightness-value">100%</output><input id="adjust-brightness" type="range" min="0" max="200" defaultValue="100" /></label>
                                    <label>Saturation (bão hòa) <output id="adjust-saturation-value">100%</output><input id="adjust-saturation" type="range" min="0" max="200" defaultValue="100" /></label>
                                    <label>Invert (đảo ngược màu) <output id="adjust-invert-value">0%</output><input id="adjust-invert" type="range" min="0" max="100" defaultValue="0" /></label>
                                    <button id="adjust-reset" className="cad-action" type="button">Đặt lại hiệu chỉnh</button>
                                    <p className="field-note">Áp dụng ngay cho nét, vùng tô và điểm của riêng layer này, không đổi nền vệ tinh hay layer khác. Không phụ thuộc mục “Áp dụng cho”.</p>
                                    <p className="field-note">Đảo ngược 0% giữ nguyên, 100% đổi sang màu đối lập (đen ↔ trắng). Hue không đổi màu đen/trắng/xám. Các thanh màu bên trên vẫn chọn màu gốc trước hiệu chỉnh.</p>
                                </fieldset>
                                <section className="inspector-section"><h3>Thành phần trong layer</h3>
                                    <input id="component-search" type="search" placeholder="Tìm tên thành phần…" aria-label="Tìm thành phần" />
                                    <div id="component-list"></div><div id="component-pager" className="inspector-pager"></div>
                                </section>
                                <section className="inspector-section"><h3>Thuộc tính đối tượng</h3>
                                    <p className="field-note">Xem toàn bộ đối tượng đã đọc, phân trang 50 dòng. Đối tượng DXF chưa hỗ trợ được báo ở phần thông tin trên.</p>
                                    <input id="attribute-search" type="search" placeholder="Tìm trong thuộc tính…" aria-label="Tìm thuộc tính" />
                                    <div className="attribute-scroll" tabIndex={0} role="region" aria-label="Bảng thuộc tính layer"><table id="attribute-table"></table></div>
                                    <div id="attribute-pager" className="inspector-pager"></div>
                                </section>
                                <section id="feature-details" className="feature-details" aria-live="polite"></section>
                            </div>
                        </aside>
                        <div className="map-tip"><span id="map-basemap-status">Vệ tinh Esri</span> · <span id="map-crs-status">Chưa chọn hệ tọa độ chung</span></div>
                    </div>
                </div>
            </section>);
});
