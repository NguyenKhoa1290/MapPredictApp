# Hiệu năng DXF trong trợ lý

## Kết quả đo trước thay đổi

Với danhso_1.dxf, dung lượng 10.350.869 byte, trên VPS phần đọc bản vẽ, mô tả và tra cứu tài liệu mất 2,697 giây, trong đó đọc DXF 2,180 giây và tra cứu 0,342 giây. Thử chuyển cùng file qua SSH mất 11,64 giây, đây là số đo đường truyền SSH, không phải số đo HTTP qua Cloudflare

Bản vẽ có 359 đối tượng modelspace, 21.097 phần tử entitydb và tóm tắt 300 đối tượng. Ngữ cảnh model cũ có khoảng 82.000 ký tự trong cấu hình VPS khi dùng source_id ngắn để đo. Phép đo tách xử lý dữ liệu đã thay lời gọi model bằng phản hồi rỗng hợp lệ, không đo tốc độ sinh câu trả lời Gemini

## Tái sử dụng file

Trình duyệt dùng CompressionStream gzip cho DXF lớn khi API status xác nhận hỗ trợ dxf_gzip. Chỉ dùng bản nén khi nhỏ hơn ít nhất 10 phần trăm, giữ nguyên tên và dữ liệu gốc. Nếu không hỗ trợ hoặc nén thất bại thì gửi file bình thường. Server giải nén có giới hạn 12 MiB, từ chối file hỏng hoặc file nở vượt giới hạn trước khi gọi model. Hash, cache và sửa DXF đều dùng byte gốc sau giải nén

Sau khi nhận file đúng giới hạn dung lượng và nguồn, AI service cấp tham chiếu có chữ ký cho đúng source_id, tên file và SHA-256 của dữ liệu đã nhận. Tham chiếu cũng được trả về khi model báo lỗi để lần thử sau không cần tải lại file. Trình duyệt giữ tham chiếu trong WeakMap gắn với chính File hiện tại, không lưu token vào localStorage. Các lượt tiếp theo và bước apply dùng tham chiếu thay vì tải lại DXF

File được lưu riêng trong thư mục dxf-cache cạnh AI_SETTINGS_FILE, quyền thư mục 700 và file 600. Mặc định tối đa 64 MiB và 16 file cho worker hiện tại. Tham chiếu hết hạn sau 15 phút. Healthcheck dọn file hết hạn khi service hoạt động, đồng thời loại các tóm tắt hết hạn. Khi vượt ngân sách, file cũ nhất được loại, không tạo snapshot hoặc lưu lịch sử dữ liệu trên server

Khi tham chiếu hết hạn hoặc file đã bị dọn, server trả ASSISTANT_RESOURCE_EXPIRED trước khi gọi model. Trình duyệt tự gửi lại File hiện tại một lần, giữ nguyên token preview và các tham số yêu cầu. Tham chiếu sai chữ ký hoặc source_id bị từ chối. Việc kiểm tra hash bản gốc và chữ ký trước khi áp dụng vẫn giữ nguyên

AI service có AI_SETTINGS_FILE nên mặc định dùng cache trên volume. Chạy local không cấu hình kho settings tiếp tục dùng tải file trực tiếp. Có thể chỉ định ASSISTANT_DXF_CACHE_DIR trong cấu hình Flask để kiểm thử thư mục riêng

## Tóm tắt và ngữ cảnh

Tóm tắt được lưu trong RAM theo hash nội dung, tối đa 16 mục và tổng 2 MiB, không giữ Drawing đầy đủ giữa các lượt. Chỉ nạp lại Drawing khi cần kiểm tra chính xác một đề xuất sửa. Bước apply vẫn đọc bản gốc để giữ cấu trúc DXF đầy đủ

Giữ nguyên giới hạn 300 đối tượng và 16 đỉnh lấy mẫu. Không giảm hình học hay số đối tượng được gửi. JSON được viết gọn và mỗi file có handle_prefix để xác định source_id, tránh lặp mã file ở từng đối tượng. Với mã source_id dạng UUID trên file đo, phần JSON ngữ cảnh giảm từ 69.463 xuống 48.755 ký tự

Preview trả thêm timings với dxf_ms, retrieval_ms, model_ms, total_ms, summary_cache_hits và input_chars. AI service ghi request_id, action, tổng byte DXF, số file tái sử dụng và timings vào log container, không ghi nội dung bản vẽ, tên file, token tham chiếu, câu hỏi hoặc câu trả lời

Lần tải file đầu tiên và thời gian Gemini sinh câu trả lời vẫn còn. Số đo phần chuẩn bị dữ liệu không được coi là thời gian phản hồi toàn bộ chatbot

## Kiểm tra sau thay đổi

Đo cùng file trên VPS, gọi API bằng test client trong tiến trình riêng và thay lời gọi LLM bằng phản hồi thử, lượt đầu mất 3,401 giây và lượt dùng lại file mất 0,158 giây. Phần DXF tương ứng là 2.786,3 ms và 30,7 ms, tra cứu Qdrant thật là 405,7 ms và 19,7 ms. Đây là phép đo trước khi bổ sung nén đường truyền, không bao gồm tải file qua HTTP hoặc sinh câu trả lời Gemini

Kiểm tra Chrome trên máy local với file gốc, giao diện thật và API Flask riêng, thay LLM và tra cứu bằng phản hồi thử. Body HTTP thực nhận ở server là 2.878.067 byte cho lượt đầu có gzip và 1.563 byte cho lượt tiếp theo dùng tham chiếu. Cùng cấu hình khi chưa nén có body đầu 10.352.105 byte. Phạm vi tóm tắt vẫn là 300 trong 359 đối tượng, lượt thứ hai có summary_cache_hits=1. Thời gian chuẩn bị tương ứng trong phép thử gzip là 2.766 ms và 78 ms

Kiểm thử bao gồm ràng buộc chữ ký với nguồn, hash và tên file, tham chiếu hết hạn, ngân sách và dọn cache, sửa đúng file khi trộn file đã lưu với file mới, trả lại tham chiếu khi model lỗi, nén và giải nén, từ chối gzip hỏng hoặc nở vượt giới hạn. Kiểm thử trình duyệt xác nhận khóa nút gửi trước khi nén bất đồng bộ, giữ model đã chọn và không xóa phần người dùng vừa gõ tiếp
