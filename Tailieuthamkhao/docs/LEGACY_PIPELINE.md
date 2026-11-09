# Đánh giá quỹ đất React và pipeline

Cập nhật ngày 2026-11-09 theo yêu cầu chuyển công cụ sang frontend React

## Giao diện chính

`/portal/assessment` hiển thị công cụ React trực tiếp, gồm bản đồ, layer, bảng thuộc tính, nạp CSV, dự đoán, tự lưu, chatbot và xuất PDF

Giao diện nằm trong `frontend/src/pages/assessment`, các component React dựng thanh công cụ và hai panel, các module engine quản lý Leaflet, DOM động, lịch sử và lưu phiên. CSS được giới hạn trong assessment-root để không ảnh hưởng ba trình xem dự án

Sau lần mở đầu, công cụ được giữ trong Layout khi chuyển sang trang khác và chỉ ẩn đi, quay lại giữ nguyên file và bản đồ. Khi hủy trang, bộ điều khiển lưu phiên, gỡ sự kiện, dừng yêu cầu mạng, xóa bản đồ và thu hồi URL tạm

`/` dẫn tới Giới thiệu tại `/portal/`, cả `/legacy/` và `/legacy/?embedded=1` đều chuyển tới `/portal/assessment`. Trang đánh giá giữ thanh công cụ riêng và không hiển thị header/footer của portal

Database `mapPredict.workspace` của công cụ legacy không đổi. Phiên CSV của giao diện trước vẫn nằm ở `mapPredict.assessment` và có thể mở tại `/portal/assessment/csv`, không tự gộp hoặc ghi đè hai phiên

## Mô hình đang dùng

Nguồn do người dùng cung cấp là `rf_model_rating_pipeline.pkl`, bản hoạt động ở `backend/models/rf_model_rating_pipeline.pkl`

Đã kiểm tra trực tiếp file

- Loại sklearn.pipeline.Pipeline
- Bước scaler là StandardScaler
- Bước rf là RandomForestClassifier
- Cột đầu vào x1 đến x9 theo đúng thứ tự
- Nhãn đầu ra 0, 1, 2
- SHA-256 f58d3ac1a1e84927fca2a911cf8bc19b4119bcfff14dedf8d8cec918304fa5cd

API cũ và API v1 cùng đọc pipeline cố định. Chuẩn bị DataFrame theo x1 đến x9 rồi gọi pipeline.predict trực tiếp, không chạy scaler lần thứ hai. Không fallback về bộ hai file cũ và không nhận upload mô hình từ trình duyệt

Mã phiên bản mặc định có tiền tố pipeline-v1 và dấu vân tay của file pipeline. Kết quả đã lưu từ phiên trước vẫn được giữ, chỉ dự đoán lại khi người dùng bấm nút

CLI cũng hỗ trợ `python -m backend.map_predict.services.pipeline <pipeline.pkl> <data.json>`, lời gọi ba tham số model/scaler/data cũ chỉ giữ để tương thích ngoài API

## Kiểm tra

Build đạt, 76 kiểm thử Python và 30 kiểm thử React/Leaflet/IndexedDB đạt. Kiểm thử mới so kết quả với pipeline.predict trực tiếp, xác nhận StandardScaler.transform chạy đúng một lần và thư mục chỉ có pipeline vẫn dự đoán được

Kiểm thử React xác nhận header/footer bao quanh iframe legacy và tài liệu iframe không bị tạo lại khi chuyển mục rồi quay về. Bộ kiểm thử browser cũ đã đổi URL mục tiêu sang tài liệu legacy nhúng, chưa chạy browser thực trong bước này

HTTP local đã xác nhận `/` dẫn về Giới thiệu, `/legacy/` dẫn về trang Đánh giá, tài liệu legacy nhúng và phiên CSV cũ đều tải được. API dự đoán legacy và v1 cùng trả 200 với mã phiên bản `pipeline-v1-f58d3ac1a1e84927`

Việc xác nhận phép chiếu và vị trí ba dự án vẫn để người dùng chốt sau, giữ 9208 ở trạng thái xem thử
