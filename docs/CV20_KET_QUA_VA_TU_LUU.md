# CV-20 CSV kết quả và khôi phục phiên

Quyết định mới ưu tiên công cụ legacy tại `/portal/assessment`, phiên CSV được mô tả dưới đây vẫn còn tại `/portal/assessment/csv`, xem [LEGACY_PIPELINE.md](LEGACY_PIPELINE.md)

Cập nhật ngày 2026-10-26

## Trang Đánh giá mới

- Có ô **CSV kết quả có sẵn**, nhận file người dùng chủ động nạp qua `POST /api/v1/predictions/results`
- Cần cột Y, chỉ nhận nhãn 0, 1, 2 hoặc để trống, ô Y trống hiện **Chưa có dữ liệu** và không đổi thành 0
- Giữ nguyên mã dạng chuỗi và các cột khác, chẳng hạn mã 001 không bị đổi thành 1
- Nạp kết quả không chạy AI, không đọc file kết quả mặc định và không ghi kết quả chung lên máy chủ
- Bảng cho chuyển giữa Dữ liệu đầu vào và Kết quả, xuất CSV lấy đúng bảng kết quả hiện tại
- CSV lỗi không thay file hoặc kết quả hợp lệ đang dùng, request cũ trả về muộn không thay dữ liệu mới
- Có Gỡ dữ liệu đầu vào và Gỡ kết quả, việc gỡ được tự lưu

## Tự lưu trong trình duyệt

Dùng lại bộ ghi giao dịch `wwwroot/workspace_store.js`, với database riêng `mapPredict.assessment`, DB version 1 và snapshot schema 1

Lưu file đầu vào, file kết quả đã nạp, bảng xem trước, toàn bộ kết quả, nguồn kết quả, mã phiên bản mô hình, tab, bảng đang xem và trang bảng. File và bảng lớn nằm trong asset store, chỉ ghi lại khi thay đổi. Đổi tab hoặc trang không ghi lại toàn bộ file

Không lưu trạng thái đang chạy, lỗi request, model/scaler hoặc file chưa qua kiểm tra. Khôi phục không POST lại CSV hay chạy mô hình, chỉ có thể GET tình trạng bộ mô hình trên máy chủ

Tự lưu gộp sau 180 ms không có thay đổi mới, chỉ báo **Đã tự lưu trên trình duyệt** sau khi giao dịch hoàn tất. Có thử lưu khi pagehide hoặc tab bị ẩn, nhưng cần chờ thông báo lưu xong trước khi đóng trang để bảo đảm thao tác cuối đã được ghi

Nếu lỗi quota hoặc ghi dữ liệu, giao dịch rollback và bản trước đó được giữ. Nếu phiên bản snapshot không được hỗ trợ hoặc đọc thất bại, trang không ghi đè bản cũ bằng trạng thái rỗng. Nếu tab khác lưu trước, tab cũ bị chặn ghi và yêu cầu reload để đọc phiên mới

Database này tách khỏi `mapPredict.workspace` của công cụ cũ, không tự di chuyển hoặc ghi đè bản lưu cũ. Phần chuyển toàn bộ layer/GeoJSON và ghép lưới sang giao diện mới vẫn thuộc CV-21/CV-22

Bản lưu gắn với trình duyệt, profile và origin hiện tại, không đồng bộ máy khác hoặc giữ được khi người dùng xóa dữ liệu website

## Bỏ kết quả mặc định ở công cụ cũ

- `/api/predict` không còn ghi `KetQua.csv` dùng chung
- `/api/map` chỉ dùng CSV gửi trong request, không fallback sang file trên máy chủ và không ghi ngược file kết quả đã nạp
- `/api/results` chỉ trả danh sách rỗng để tương thích với client cũ, không đọc file mặc định
- `/api/export` trả 410, giao diện xuất CSV từ đúng dữ liệu đang có trong trình duyệt
- Bỏ lời gọi lấy kết quả mặc định khi khởi tạo công cụ cũ

File `KetQua.csv` có sẵn trên đĩa không bị xóa hoặc thay đổi. Các phép kiểm tra ghi dữ liệu đều dùng thư mục tạm, không ghi đè kết quả thật của người dùng

## Kiểm tra

Build TypeScript/Vite đạt, 75 kiểm thử Python, 30 kiểm thử React/Leaflet/IndexedDB và 34 kiểm thử Node đạt

HTTP thực tế sau khi khởi động lại máy chủ local: trang Đánh giá và script bộ lưu trả 200, nạp CSV kết quả trả 200 với Y trống được giữ, API kết quả cũ trả danh sách rỗng và API export chung trả 410

Kiểm thử IndexedDB dùng fake-indexeddb với giao dịch thực của bộ lưu, bao phủ file Blob, metadata, rollback khi ghi thất bại, conflict revision và giữ schema chưa hỗ trợ. Kiểm thử vòng đời React dùng bộ lưu mô phỏng để kiểm tra tương tác và khôi phục khi remount. Đây chưa phải kiểm thử reload trên Chrome thực

Kiểm thử backend đặt sẵn file kết quả cũ trong thư mục tạm, xác nhận dự đoán, nạp kết quả và tải lưới đều không đọc hoặc ghi đè file đó
