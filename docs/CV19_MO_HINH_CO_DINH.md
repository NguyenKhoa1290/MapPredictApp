# CV-19 Mô hình cố định và dự đoán trên giao diện mới

Cấu hình hiện tại đã chuyển sang pipeline một file và giao diện Đánh giá dùng legacy theo yêu cầu mới, xem [LEGACY_PIPELINE.md](LEGACY_PIPELINE.md). Phần mô hình hai file bên dưới là ghi nhận giai đoạn trước

Cập nhật CV-20 đã có nạp CSV kết quả, tự lưu/khôi phục và bỏ file kết quả mặc định ở cả công cụ cũ, xem [CV20_KET_QUA_VA_TU_LUU.md](CV20_KET_QUA_VA_TU_LUU.md). Các giới hạn chưa tự lưu bên dưới ghi nhận giai đoạn CV-19 trước thay đổi này

Ngày cập nhật 2026-10-26

## Phần đã thực hiện

- Bộ mô hình cố định đặt tại `models/rf_model_rating.pkl` và `models/scaler_bds.pkl`, sao chép nguyên trạng từ bộ đang dùng
- Backend tái sử dụng `predict_pkl.predict_rows`, giữ thứ tự x1 đến x9 và cách điền 0 khi cột hoặc giá trị trống
- Không nhận file mô hình, scaler hoặc đường dẫn mô hình từ request ở cả API mới lẫn `/api/predict` của công cụ cũ
- API mới trả kết quả trực tiếp cho đúng request, không ghi hoặc đọc file `KetQua.csv` dùng chung
- Mã phiên bản gồm tên bản phát hành và dấu vân tay của cả hai file đúng lúc chạy, dùng byte snapshot để mã và kết quả không lệch khi file trên đĩa thay đổi
- Trạng thái mô hình chỉ kiểm tra sự có mặt của bộ file, không tự chạy dự đoán khi mở trang. File lỗi hoặc không tương thích được báo rõ khi chạy

## Trang Đánh giá

Mở `/portal/assessment`, chọn CSV để xem trước tối đa 200 dòng. Bấm Chạy dự đoán để xử lý bằng mô hình trên máy chủ, bảng bên phải hiển thị kết quả và phiên bản. Xuất CSV lấy đúng các dòng kết quả trong trình duyệt

Mỗi trang bảng có 50 dòng. Đổi file sẽ bỏ kết quả đang hiển thị của file trước, hủy request cũ và không nhận kết quả trả về muộn. API không lưu kết quả chung giữa hai người dùng

Phần bản đồ của trang Đánh giá vẫn là khung minh họa, ghép lưới thuộc CV-21. Chưa tự lưu CSV/kết quả của giao diện mới qua reload, phần lưu và khôi phục thuộc CV-20/CV-22. Công cụ cũ vẫn có cơ chế tự lưu trước đây

## API mới

- `GET /api/v1/predictions/model` trả tình trạng file mô hình, các cột đầu vào và mã phiên bản
- `POST /api/v1/predictions/preview` nhận duy nhất một file ở trường `csv`, trả dữ liệu xem trước và tổng số dòng
- `POST /api/v1/predictions` nhận CSV và trả kết quả, không ghi dữ liệu người dùng xuống đĩa

API có cấu trúc `{data, meta}` hoặc `{error, request_id}`, trả `Cache-Control: no-store`. Thiếu file mô hình hoặc không tương thích trả 503, CSV sai trả 422, vượt giới hạn trả 413, nạp mô hình hoặc đường dẫn qua form trả 400. Request POST có Origin khác website bị chặn

Giới hạn local ban đầu là CSV 5 MiB, request 8 MiB và 10.000 dòng mỗi lần, cấu hình trong `backend/map_predict/config.py`. Đây chưa phải nghiệm thu tải đồng thời hoặc chính sách hosting public

## Tương thích với công cụ cũ

Đã bỏ ô chọn mô hình và scaler, API cũ dùng cùng bộ mô hình cố định. Không khôi phục hai ô model/scaler từ bản lưu trình duyệt cũ, dữ liệu CSV và layer vẫn dùng cơ chế khôi phục hiện tại

`/api/predict` cũ vẫn ghi file kết quả chung theo luồng cũ, và API bản đồ cũ vẫn còn fallback kết quả. Việc bỏ hoàn toàn các hành vi đó thuộc CV-20, không xem ứng dụng tương thích hiện tại là bản sẵn sàng public

## Kiểm tra

Build TypeScript/Vite đạt, 73 kiểm thử Python và 18 kiểm thử React/Leaflet đạt. HTTP thực tế trên máy chủ local: trạng thái mô hình, xem trước, dự đoán và trang Đánh giá đều trả 200, kết quả có Y và mã phiên bản, không ghi kết quả dùng chung qua API mới

Kiểm thử backend đối chiếu Y với thuật toán cũ bằng bộ mô hình thật, kiểm tra trạng thái/preview không chạy mô hình, từ chối model/scaler/đường dẫn upload, lỗi thiếu hoặc hỏng mô hình, CSV sai và giá trị không hữu hạn, giới hạn dung lượng/số dòng, request độc lập và model không được phục vụ tĩnh

Kiểm thử React bao phủ nạp CSV, chỉ dự đoán sau khi bấm nút, tình trạng thiếu mô hình, lỗi CSV và mô hình, request trả về muộn và xuất CSV đúng nội dung. Bài kiểm thử browser cũ được cập nhật để không thao tác ô model/scaler, chưa chạy browser thực trong bước này
