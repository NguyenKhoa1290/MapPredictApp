# Trang bản đồ dự án có sẵn

Cập nhật cách gọi trên giao diện: nhóm ô không có kết quả Y hiển thị là **Chưa có dữ liệu**, áp dụng cho chú giải, danh sách chọn và thông tin ô

Ngày cập nhật: 2026-10-26, theo đính chính của người dùng sau CV-07.

## Hành vi

Ba dự án địa phương mở thành trang bản đồ riêng tại `/portal/projects/hcm`, `/portal/projects/bac-kan`, `/portal/projects/phu-quoc`. Mỗi trang tự đọc bộ DXF–Excel đã có trên máy chủ, hiển thị layer lưới trên nền OpenStreetMap hoặc vệ tinh Esri; có bật/tắt, thanh độ đậm, chú giải lọc theo Y, zoom toàn lưới và thông tin ô khi bấm. Có tìm/chọn mã bằng điều khiển HTML để đọc thông tin mà không cần bấm canvas.

Không có chức năng thêm layer, nạp Excel hay chạy mô hình ở ba trang này. Dự án AI vẫn dẫn sang trang Đánh giá, là luồng riêng.

Bấm ô đất đồng thời mở popup nhỏ tên/mã lô và cập nhật thông tin chi tiết ở thanh bên. Popup ưu tiên mã dữ liệu đã ghép, sau đó mã lưới; ô không có cả hai hiện “Lô đất chưa có tên”. Không hiện nhãn thường trực trên toàn bộ lưới.

Zoom dùng chuyển động Leaflet cho nền và layer cùng tỷ lệ, cập nhật hình học tại `zoomend`/`viewreset`. Cho phép mức zoom lẻ và nửa bước ở nút cộng trừ, xem [MAP_MOTION.md](MAP_MOTION.md). Kích thước renderer không bị CSS SVG minh họa ép về 100% và layer vẫn tiếp tục zoom khi ảnh nền đã tới mức chi tiết gốc.

Góc bản đồ có **Về layer** để dừng di chuyển, đưa khung nhìn về toàn bộ lưới (zoom tối đa 18) và **Tải lại nền** để tải lại tile khi mạng lỗi mà vẫn giữ layer/nhãn. Trình xem dùng cùng bộ `wwwroot/basemaps.js` với công cụ cũ: khi vệ tinh thiếu ảnh, thử mức thấp hơn có giới hạn và cắt/phóng đúng vùng ảnh. Không tải trước hàng loạt hoặc tự đổi nhà cung cấp.

## Phép chiếu đang thử

Người dùng yêu cầu thử **EPSG:9208**. Client mặc định gửi mã này; API cũng dùng 9208 nếu không có query. Có thể chọn một CRS trong danh sách VN-2000 hiện có, hoặc chọn lưới gốc để xem tọa độ CAD không có nền địa lý. Chỉ chuyển trong bộ nhớ; không sửa DXF/Excel, không áp dụng độ dịch hay xoay/scale suy đoán.

Mọi kết quả vẫn có `crs_confirmed=false`. 9208 là phép thử được người dùng yêu cầu, không phải xác nhận cả ba file thực sự cùng phép chiếu. Vị trí cần được người dùng đối chiếu trước nghiệm thu. Chưa lưu lựa chọn CRS của trình xem mới qua reload.

## Đọc lưới và ghép nhãn

Service `backend/map_predict/services/project_maps.py` chọn đúng layer/loại nhãn đã khảo sát. TEXT dùng điểm chèn nằm trong duy nhất một ô. MTEXT số thuần một dòng dùng tâm khung tham chiếu theo width, char_height, attachment và rotation; điểm chèn cũng phải chạm cùng ô (dung sai rất nhỏ chỉ cho số thực). Đây là cách đọc attachment cho ba nguồn này, không phải renderer chữ tổng quát hoặc phép ghép nhãn gần nhất. Chữ có định dạng không hỗ trợ/mơ hồ để trống mã.

Ghép chính xác trước, phần số duy nhất sau; chỉ trong cùng dự án, từ cột B của Excel, không từ số thứ tự cột A. Khóa fallback trùng/mơ hồ không tự ghép. Chỉ nhãn Y=0/1/2 được tô đỏ/cam/xanh theo quy tắc đã chốt; ô chưa có kết quả giữ đường bao. Phú Quốc gộp hình học trùng hoàn toàn trong bộ nhớ, giữ tất cả handles; không gộp chồng lấn một phần. Mã 1232 không được tạo polygon/ghép gần nhất hoặc đưa thành cảnh báo cho người xem.

Kết quả đối chiếu thực tế:

- TP.HCM: 1.695 ô; 297 có Y (135 đỏ, 162 cam), 1.398 chỉ đường bao.
- Bắc Kạn: 400 ô; 380 có Y (12 cam, 368 xanh), BK1–BK20 chỉ đường bao.
- Phú Quốc: 1.676 ô duy nhất từ 1.734 đường bao; 1.676 có Y (90 đỏ, 57 cam, 1.529 xanh).

## API và giới hạn

`GET /api/v1/projects/<slug>/map?source_crs=EPSG:9208` trả dữ liệu hình học, thuộc tính, thống kê và danh sách CRS. Query rỗng trả `mode=native`, tọa độ bản vẽ gốc; chỉ `mode=geographic` được chồng tile nền. Dự án AI/slug không tồn tại trả 404, thiếu file cố định trả 409, CRS không hợp lệ trả 422. Không nhận POST/file hoặc chạy AI. Cache dữ liệu nguồn đọc dựa trên đường dẫn cố định, mtime và kích thước; thao tác xem không ghi kết quả hoặc đổi file nguồn.

Ảnh nền vẫn cần Internet; nếu tile lỗi, lưới không bị bỏ. Bộ tile dùng `nativeMaxZoom=19` và cắt/phóng ảnh ở mức cao hơn thay vì yêu cầu tile vượt mức đó. Nguồn kỹ thuật: [Leaflet GeoJSON](https://leafletjs.com/examples/geojson/), [Leaflet reference](https://leafletjs.com/reference), [MTEXT attachment và rotation](https://ezdxf.readthedocs.io/en/stable/tutorials/mtext.html).

Kiểm thử mới đối chiếu cả ba nguồn thật và SHA-256 trước/sau, nhãn thiếu/mơ hồ, attachment/xoay, gộp trùng/giữ handles, API chỉ đọc và chuyển 9208. Kiểm thử React xác nhận trang riêng, không có upload/chạy AI, đổi CRS/nền/bộ lọc và xem thông tin ô. Kiểm thử component dùng canvas giả; không chứng minh tile mạng thực hoặc vị trí thực địa chính xác.
