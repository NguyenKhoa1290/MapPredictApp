# Hiệu năng DXF trong trợ lý

## Kết quả đo trước thay đổi

Với danhso_1.dxf, dung lượng 10.350.869 byte, trên VPS phần đọc bản vẽ, mô tả và tra cứu tài liệu mất 2,697 giây, trong đó đọc DXF 2,180 giây và tra cứu 0,342 giây. Thử chuyển cùng file qua SSH mất 11,64 giây, đây là số đo đường truyền SSH, không phải số đo HTTP qua Cloudflare

Bản vẽ có 359 đối tượng modelspace, 21.097 phần tử entitydb và tóm tắt 300 đối tượng. Ngữ cảnh model cũ có khoảng 82.000 ký tự trong cấu hình VPS khi dùng source_id ngắn để đo. Phép đo tách xử lý dữ liệu đã thay lời gọi model bằng phản hồi rỗng hợp lệ, không đo tốc độ sinh câu trả lời Gemini

## Tái sử dụng file

Sau khi nhận file đúng giới hạn dung lượng và nguồn, AI service cấp tham chiếu có chữ ký cho đúng source_id, tên file và SHA-256 của dữ liệu đã nhận. Tham chiếu cũng được trả về khi model báo lỗi để lần thử sau không cần tải lại file. Trình duyệt giữ tham chiếu trong WeakMap gắn với chính File hiện tại, không lưu token vào localStorage. Các lượt tiếp theo và bước apply dùng tham chiếu thay vì tải lại DXF

File được lưu riêng trong thư mục dxf-cache cạnh AI_SETTINGS_FILE, quyền thư mục 700 và file 600. Mặc định tối đa 64 MiB và 16 file cho worker hiện tại. Tham chiếu hết hạn sau 15 phút. Healthcheck dọn file hết hạn khi service hoạt động, đồng thời loại các tóm tắt hết hạn. Khi vượt ngân sách, file cũ nhất được loại, không tạo snapshot hoặc lưu lịch sử dữ liệu trên server

Khi tham chiếu hết hạn hoặc file đã bị dọn, server trả ASSISTANT_RESOURCE_EXPIRED trước khi gọi model. Trình duyệt tự gửi lại File hiện tại một lần, giữ nguyên token preview và các tham số yêu cầu. Tham chiếu sai chữ ký hoặc source_id bị từ chối. Việc kiểm tra hash bản gốc và chữ ký trước khi áp dụng vẫn giữ nguyên

AI service có AI_SETTINGS_FILE nên mặc định dùng cache trên volume. Chạy local không cấu hình kho settings tiếp tục dùng tải file trực tiếp. Có thể chỉ định ASSISTANT_DXF_CACHE_DIR trong cấu hình Flask để kiểm thử thư mục riêng

## Tóm tắt và ngữ cảnh

Tóm tắt được lưu trong RAM theo hash nội dung, tối đa 16 mục và tổng 2 MiB, không giữ Drawing đầy đủ giữa các lượt. Chỉ nạp lại Drawing khi cần kiểm tra chính xác một đề xuất sửa. Bước apply vẫn đọc bản gốc để giữ cấu trúc DXF đầy đủ

Giữ nguyên giới hạn 300 đối tượng và 16 đỉnh lấy mẫu. Không giảm hình học hay số đối tượng được gửi. JSON được viết gọn và mỗi file có handle_prefix để xác định source_id, tránh lặp mã file ở từng đối tượng. Với mã source_id dạng UUID trên file đo, phần JSON ngữ cảnh giảm từ 69.463 xuống 48.755 ký tự

Preview trả thêm timings với dxf_ms, retrieval_ms, model_ms, total_ms, summary_cache_hits và input_chars. AI service ghi request_id, action, tổng byte DXF, số file tái sử dụng và timings vào log container, không ghi nội dung bản vẽ, tên file, token tham chiếu, câu hỏi hoặc câu trả lời

Lần tải file đầu tiên và thời gian Gemini sinh câu trả lời vẫn còn. Số đo phần chuẩn bị dữ liệu không được coi là thời gian phản hồi toàn bộ chatbot
