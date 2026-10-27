# Đánh giá quỹ đất dùng legacy và pipeline

Cập nhật ngày 2026-10-26 theo quyết định giữ công cụ legacy

## Giao diện chính

`/portal/assessment` hiển thị công cụ legacy bên trong header và footer chung của portal, giữ bản đồ, layer, bảng thuộc tính, nạp CSV, dự đoán, tự lưu và xuất PDF đã có

Phần legacy chạy trong tài liệu iframe cùng origin tại `/legacy/?embedded=1` để CSS và Leaflet cũ không ảnh hưởng ba trình xem dự án mới. Không sandbox hạn chế popup PDF hoặc thao tác chọn file của công cụ

Sau lần mở đầu, tài liệu công cụ được giữ trong Layout khi chuyển sang trang khác và chỉ ẩn đi, quay lại không tạo iframe mới. Có gửi resize khi hiện lại để Leaflet nhận đúng kích thước khung nhìn

`/` dẫn tới Giới thiệu tại `/portal/`, mở `/legacy/` trực tiếp dẫn tới `/portal/assessment`. Header luôn ở phía trên, footer nằm dưới công cụ, chiều cao phần làm việc theo chiều cao header thực tế

Database `mapPredict.workspace` của công cụ legacy không đổi. Phiên CSV của giao diện trước vẫn nằm ở `mapPredict.assessment` và có thể mở tại `/portal/assessment/csv`, không tự gộp hoặc ghi đè hai phiên

## Mô hình đang dùng

Nguồn do người dùng cung cấp là `rf_model_rating_pipeline.pkl`, bản hoạt động ở `models/rf_model_rating_pipeline.pkl`

Đã kiểm tra trực tiếp file

- Loại sklearn.pipeline.Pipeline
- Bước scaler là StandardScaler
- Bước rf là RandomForestClassifier
- Cột đầu vào x1 đến x9 theo đúng thứ tự
- Nhãn đầu ra 0, 1, 2
- SHA-256 f58d3ac1a1e84927fca2a911cf8bc19b4119bcfff14dedf8d8cec918304fa5cd

API cũ và API v1 cùng đọc pipeline cố định. Chuẩn bị DataFrame theo x1 đến x9 rồi gọi pipeline.predict trực tiếp, không chạy scaler lần thứ hai. Không fallback về bộ hai file cũ và không nhận upload mô hình từ trình duyệt

Mã phiên bản mặc định có tiền tố pipeline-v1 và dấu vân tay của file pipeline. Kết quả đã lưu từ phiên trước vẫn được giữ, chỉ dự đoán lại khi người dùng bấm nút

CLI cũng hỗ trợ `python predict_pkl.py <pipeline.pkl> <data.json>`, lời gọi ba tham số model/scaler/data cũ chỉ giữ để tương thích ngoài API

## Kiểm tra

Build đạt, 76 kiểm thử Python và 30 kiểm thử React/Leaflet/IndexedDB đạt. Kiểm thử mới so kết quả với pipeline.predict trực tiếp, xác nhận StandardScaler.transform chạy đúng một lần và thư mục chỉ có pipeline vẫn dự đoán được

Kiểm thử React xác nhận header/footer bao quanh iframe legacy và tài liệu iframe không bị tạo lại khi chuyển mục rồi quay về. Bộ kiểm thử browser cũ đã đổi URL mục tiêu sang tài liệu legacy nhúng, chưa chạy browser thực trong bước này

HTTP local đã xác nhận `/` dẫn về Giới thiệu, `/legacy/` dẫn về trang Đánh giá, tài liệu legacy nhúng và phiên CSV cũ đều tải được. API dự đoán legacy và v1 cùng trả 200 với mã phiên bản `pipeline-v1-f58d3ac1a1e84927`

Việc xác nhận phép chiếu và vị trí ba dự án vẫn để người dùng chốt sau, giữ 9208 ở trạng thái xem thử
