# Ghép kết quả với lưới dự đoán

Cập nhật ngày 2026-10-27, áp dụng trong công cụ legacy tại `/portal/assessment`

## Cách sử dụng

1. Thêm một hoặc nhiều lưới DXF hoặc GPKG
2. Nạp CSV kết quả hoặc chạy dự đoán với pipeline trên máy chủ
3. Chọn cột mã trong CSV và lưới, có thể chọn riêng từng file khi cột khác nhau
4. Chọn Mã chính xác hoặc Mã chính xác rồi phần số duy nhất
5. Bấm Xem trước ghép kết quả để kiểm tra thống kê và mẫu đối chiếu
6. Bấm Áp dụng kết quả lên bản đồ sau khi kiểm tra

Nút Hiển thị trên bản đồ cũng thực hiện bước xem trước khi có kết quả
Nếu chưa có kết quả, lưới vẫn hiển thị đường ô và không tô màu
PDF xuất vùng bản đồ đã áp dụng, không xuất trạng thái đang xem trước

## Quy tắc

- Ghép chính xác bỏ khoảng trắng đầu cuối và không phân biệt hoa thường
- Ghép phần số chỉ dùng một cụm chữ số nguyên, bỏ số 0 đầu để đối chiếu
- `TP001` có thể ghép `1`, `A1B2` không ghép `12`, chuỗi `1.0` không được coi là số ô `1`
- Khóa trùng ở một trong hai bên không tự ghép, kể cả cùng Y
- Mã khớp chính xác không bị thay bằng ứng viên ghép phần số
- Y trống hoặc khác 0, 1, 2 không tô màu, không tự điền Y bằng 0
- Đối chiếu riêng từng file lưới, giữ nguyên thuộc tính nguồn và không sửa DXF hoặc GPKG gốc

Mỗi ô trả `join_status`, `join_method`, `result_key` để kiểm tra trong bảng thuộc tính
Báo cáo trả số ô khớp chính xác, khớp phần số, mơ hồ, thiếu mã hoặc thiếu Y, cùng tối đa 20 mẫu

## Tự lưu và yêu cầu đang chạy

Khi thay file, cột, cách ghép, CRS, độ dịch hoặc kết quả dự đoán, bản xem trước cũ bị hủy
Phản hồi đến muộn không thể bật lại nút áp dụng cho dữ liệu cũ
Bản đồ đã áp dụng được giữ trong lúc xem trước hoặc khi gặp lỗi

Snapshot `mapPredict.workspace` giữ file, GeoJSON đã áp dụng, kết quả, cách ghép và mức zoom
Snapshot cũ chưa có `joins.mode` được đọc ở chế độ chính xác
Không chuyển hoặc xóa dữ liệu trong database `mapPredict.assessment` của phiên CSV riêng
Bản xem trước chưa xác nhận không được lưu thành layer đã áp dụng

## Xác minh

- Bộ kiểm thử Python kiểm tra khóa số, mã trùng, Y không hợp lệ và hai client nhận kết quả riêng theo request
- Kiểm thử DOM chạy mã legacy thật và module xem trước, xác nhận cần bấm áp dụng, hủy kết quả cũ, xử lý lỗi và khôi phục snapshot không gọi lại API
- Bộ lưu IndexedDB có kiểm thử giao dịch và xung đột riêng ở frontend
- Kiểm thử DOM không thay thế đo tải nền mạng thật hoặc kiểm tra trực quan trên trình duyệt

Đã kiểm tra trực tiếp bằng trình duyệt local với lưới tổng hợp ba ô và CSV có mã mơ hồ
Báo cáo trả 1 ô khớp phần số, 1 ô mơ hồ và 1 ô chưa khớp, trước áp dụng chưa tạo layer
Sau áp dụng chỉ ô khớp được tô màu, reload khôi phục một layer và chế độ numeric, console không ghi nhận lỗi JavaScript
Ảnh bằng chứng tại [join-restored-20261027.png](verification/join-restored-20261027.png), chuyển khỏi tmp khi dọn dự án
Ở kích thước thử 390 × 844, DOM không tràn ngang và cả bốn avatar dùng contain, bước chụp ảnh toàn trang nhỏ không thành công nên chưa coi là nghiệm thu trực quan đầy đủ

Chưa thay EPSG hoặc xác nhận vị trí ba dự án địa phương
Chưa triển khai public, phân quyền tài khoản hoặc chatbot
