# Toàn bộ CSV trong ngữ cảnh trợ lý

Trợ lý nhận đủ mọi dòng và cột của CSV hiện tại, bao gồm dữ liệu tùy chỉnh và Y nếu bảng đang là kết quả dự đoán. Giới hạn nạp vẫn là 10.000 dòng và 5 MiB. Không lấy mẫu 100 dòng đầu và không dùng tham số start để bỏ qua phần đầu bảng

Ngữ cảnh gửi model có columns và rows, mỗi dòng có row_index gốc bắt đầu từ 0 cùng values theo thứ tự columns. Tên cột chỉ xuất hiện một lần để giảm dung lượng khi gửi đủ bảng. Giữ nguyên giá trị rỗng, thứ tự dòng và các cột gốc

scores và table_edits không còn bị cắt ở 100 và 200 phần tử. Mọi đề xuất được kiểm tra dòng có tồn tại, cột hợp lệ, căn cứ chấm điểm, giá trị người dùng nêu rõ và xung đột thao tác. Trạng thái các ô đã sửa được lập chỉ mục để tránh quét lại toàn bộ thao tác đã nhận cho từng đề xuất mới

Xem trước và áp dụng vẫn cần chữ ký gắn với toàn bộ file gốc. File thay đổi sau khi xem trước bị từ chối. Y được loại khi điểm đầu vào thay đổi để người dùng chạy lại mô hình

CSV có ngân sách ngữ cảnh JSON tối đa 32 Mi ký tự, không dùng ngưỡng 150.000 ký tự dành cho tóm tắt bản vẽ. Phản hồi HTTP từ model tối đa 16 MiB và JSON kết quả tối đa 8 Mi ký tự. Vượt giới hạn hoặc JSON chưa hoàn chỉnh phải báo lỗi, không cắt lấy một phần đề xuất. Bộ giải mã JSON truy xuất bộ lọc vẫn giữ giới hạn riêng 500.000 ký tự

Việc gửi đủ dữ liệu không bảo đảm model luôn trả đủ mọi thay đổi trong một câu trả lời. Độ dài đầu ra và khả năng xử lý của nhà cung cấp vẫn áp dụng, dữ liệu chỉ được thay đổi sau khi người dùng duyệt

Kiểm thử tự động xác nhận bảng 10.000 dòng được gửi đủ, nhận đúng dữ liệu dòng cuối và mọi cột, sửa dòng cuối rồi áp dụng, từ chối file đã thay đổi, áp dụng 250 điểm và 252 thao tác bảng, tạo bảng 501 dòng, đọc phản hồi trên 500.000 ký tự và từ chối JSON bị cắt
