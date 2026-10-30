# Quản trị AI

Trang quản trị tại https://admin.danhgiaquyhoach.top
Trang chính không hiển thị nút hoặc liên kết quản trị
Tên miền chính trả 404 cho trang và API quản trị, chỉ subdomain admin phục vụ các đường dẫn này
Tên miền admin mở trực tiếp `/portal/admin/ai`, header dẫn về portal trên tên miền chính
Khi chạy local vẫn dùng `/portal/admin/ai`, cookie đăng nhập được giữ riêng theo hostname
Web chỉ chuyển tiếp yêu cầu, service ai-assistant xác thực mật khẩu và phiên quản trị

## Các tab quản trị

- Model cấu hình Nhanh và xem cấu hình Thông minh
- Tài khoản Thông minh quản lý passcode, cookie tài khoản và quota
- Phiên Gemini xem trạng thái và gia hạn các phiên đã lưu
- Kho tri thức kiểm tra tìm tài liệu trực tiếp trong Qdrant

Đổi tab giữ nguyên nội dung đang nhập
Tab hỗ trợ phím trái, phải, Home và End, màn hình nhỏ cuộn ngang thanh tab

## Mật khẩu

```bash
python tools/set_ai_admin_password.py
```

Lệnh hỏi mật khẩu trực tiếp, không ghi mật khẩu vào lịch sử lệnh
Mật khẩu băm nằm trong `.secrets/ai-admin-password.hash`, không đưa vào Git hoặc image
Cookie đăng nhập HttpOnly, SameSite Strict, có Secure khi truy cập HTTPS và hết hạn sau 8 giờ
Các thao tác thay đổi cần CSRF, đăng nhập giới hạn 5 lần mỗi phút
Thay mật khẩu làm phiên cũ mất hiệu lực

## Các chế độ chatbot

Gia hạn phiên chạy trên service khi không có tab trình duyệt nào mở, kiểm tra mỗi 30 giây và xoay cookie mỗi 10 phút. Mốc `refresh_attempt_at` chỉ dành cho lần gọi RotateCookies, không bị thay đổi bởi kiểm tra trang thông thường. Cookie trả về từ RotateCookies được ghi ngay trước bước kiểm tra trang Gemini, đồng thời lưu các cookie mới từ RPC. Cookie bị Google xóa không được khôi phục từ bản cũ. Cập nhật cookie thủ công được ưu tiên hơn lượt gia hạn đang chạy.

Đối chiếu `Tailieuthamkhao/gemini-agent/google_session.py` và `server_terminal.py`: bản tham khảo dùng RotateCookies, kiểm tra quota mỗi 30 giây và chu kỳ xoay 12 giờ. Bản triển khai dùng chu kỳ 10 phút theo yêu cầu người dùng. Có phản hồi HTTP 200 từ RotateCookies chưa đủ xác nhận đăng nhập, chỉ ghi thời điểm xoay thành công sau khi kiểm tra lại phiên Gemini.

Tham khảo cơ chế lưu cookie ngay sau RotateCookies trong [Gemini-API](https://github.com/HanaokaYuzu/Gemini-API/blob/master/src/gemini_webapi/utils/rotate_1psidts.py). Không thể đảm bảo Google không thu hồi phiên, khi Google không chấp nhận cookie sau cả bước gia hạn cần cập nhật cookie mới trong quản trị.

Trạng thái kiểm tra ngày 29/10/2026: cookie đăng nhập được không đồng nghĩa model trả lời được. Adapter hiện còn dùng StreamGenerate. Quan sát trực tiếp giao diện Google xác nhận tài khoản đang dùng processSession qua WebChannel, model được chỉ định trong payload protobuf. Chưa hoàn tất nâng adapter sang giao thức này nên chưa xác nhận khôi phục 3.8 Flash. Các phép thử cũ chỉ xác nhận category và effort, không đủ chứng minh hash model thực tế.

Nguồn đối chiếu: [báo lỗi của gemini-web2api](https://github.com/Sophomoresty/gemini-web2api/issues/110) và [mô tả giao thức processSession](https://github.com/stevensuna/gemini-web-mcp-cli/blob/main/docs/research/transport/processSession.md)

- Nhanh dùng gemini-3.5-flash-lite qua phiên tài khoản đã đăng nhập, cùng hàm gọi Gemini và giao thức với Argon, không yêu cầu passcode
- Nhanh chỉ mở effort mặc định và thấp, dùng mã định tuyến Flash-Lite được phát hiện từ tài khoản, không chuyển sang ẩn danh hay model khác khi lỗi
- Thông minh cố định dùng gemini-4-argon, mã định tuyến và header lấy từ tài khoản Google đã xác minh
- Chỉ có hai lựa chọn Nhanh và Thông minh, không còn lựa chọn Pro riêng
- Nhanh có thể đổi sang API tương thích OpenAI, nhập URL gồm /v1, model và khóa riêng
- Client chỉ gửi fast hoặc smart, không cho client chỉ định endpoint hoặc model tùy ý
- Lưu cấu hình trước khi bấm kiểm tra, thay đổi có hiệu lực ở lượt chat tiếp theo
- Tên và khả năng của model Gemini Web phụ thuộc server tham khảo và tài khoản, không phải cam kết model API chính thức

Cài đặt và khóa API lưu trong volume ai_settings
API quản trị chỉ trả dấu hiệu đã có khóa, không trả khóa lại trình duyệt
Để trống ô khóa giữ khóa cũ, chọn xóa khóa nếu muốn bỏ
Khóa nội bộ của cụm không được gửi sang API bên ngoài

## Passcode và tài khoản Thông minh

Trong mục Quyền sử dụng Thông minh, quản trị đặt passcode riêng từ 8 đến 128 ký tự
Đây là passcode cấp cho người dùng gọi Thông minh, không phải mật khẩu đăng nhập quản trị
Chưa đặt passcode hoặc bấm Khóa quyền gọi Thông minh thì service từ chối gọi model
Hash passcode lưu trong volume ai_settings, không trả hash hoặc passcode cho client
Người dùng nhập passcode tại bong bóng chatbot khi chọn Thông minh, passcode không lưu trong localStorage và không gửi vào prompt model
Service kiểm tra cookie trước passcode, thiếu hoặc hết hạn cookie trả lỗi COOKIE_REQUIRED
Không chuyển sang Nhanh khi cookie lỗi, hết quota hoặc model không khả dụng
Service kiểm tra trước khi đọc DXF, truy xuất tài liệu hoặc gọi model
Kể cả khi quản trị gán Argon vào chế độ Nhanh hay Thông minh, service vẫn yêu cầu passcode

Mục Tài khoản và quota Thông minh cho phép thêm tài khoản, cập nhật cookie theo tài khoản và kiểm tra quota
Mỗi tài khoản hiển thị Gmail từ hồ sơ Google và có nút Cập nhật cookie riêng, không cần nhập chỉ số tài khoản
Thêm tài khoản mở biểu mẫu riêng, cập nhật tài khoản có sẵn giữ lại chỉ số định tuyến đã lưu
Cookie thay thế khác tài khoản Google đã xác minh bị từ chối, Gmail được giữ sau khi kiểm tra danh tính
Giới hạn tám tài khoản, mỗi tài khoản giữ cookie, XSRF, header định tuyến và quota riêng
Quota lấy từ RPC jSf9Qc và quyền Argon khám phá bằng RPC otAQ7b theo code server tham khảo
Vòng định tuyến kiểm tra tài khoản theo thứ tự, bỏ qua tài khoản hết quota hoặc không xác minh được
Chỉ gọi đúng Argon với header đã khám phá, không dùng Gemini 3.1 Pro hay Flash thay thế
Kiểm tra quota trước và sau generation, giữ câu trả lời trong bộ nhớ đến khi kiểm tra sau đạt
Nếu kiểm tra sau thất bại, bỏ câu trả lời rồi thử tài khoản kế tiếp với cùng model
Hết quota ở mọi tài khoản trả lỗi 429, không xác minh được tài khoản/quota trả lỗi 503
Adapter cũng từ chối tên model không hỗ trợ thay vì tự chuyển sang model mặc định
Thông minh không có nhánh gọi ẩn danh, không có cấu hình hạ model khi lỗi

Đã nhập hai hồ sơ từ server tham khảo vào pool trên máy, cả hai hiện yêu cầu đăng nhập lại
Cần quản trị cập nhật cookie và đặt passcode trước khi cấp quyền sử dụng Thông minh
Tải lại trang chatbot sau khi cập nhật cookie để nhận trạng thái mới
Các trường hợp chuyển tài khoản và hết quota đã kiểm thử bằng dữ liệu giả lập, chưa xác nhận generation Argon thật vì cookie hiện không hợp lệ

## Phiên Gemini

Service gemini-session chạy liên tục, kiểm tra phiên và quota mỗi 30 giây và thử RotateCookies mỗi 10 phút
Giãn lần tự sửa phiên lỗi ít nhất 300 giây, dùng các mốc trong google_session.py và server_terminal.py của server tham khảo
Trang quản trị đọc các mốc thời gian từ service và cập nhật trạng thái theo cùng chu kỳ, không làm mất bản nháp cấu hình đang nhập
Cơ chế dựa trên google_session.py của dự án tham khảo, khóa file đã hỗ trợ Windows và Linux
Cookie mới và XSRF được lưu nguyên tử trong volume gemini_session, tồn tại qua việc thay container
Chỉ nhập cookie tại từng tài khoản trong tab Tài khoản Thông minh, tab Phiên Gemini không có ô nhập cookie trùng
Nút Gia hạn phiên thực hiện RotateCookies trên các tài khoản đã lưu rồi kiểm tra lại, tương đương refresh_auth.py --all trong server tham khảo
Gia hạn song song tối đa 4 tài khoản theo cơ chế tham khảo, mọi generation vẫn dùng khóa chung để không lẫn tài khoản
API phiên đơn cũ giữ để tương thích, giao diện quản trị dùng pool tài khoản thống nhất

Healthcheck của container chỉ xác nhận adapter HTTP đang chạy
Trạng thái phiên Google hiển thị riêng trong quản trị, không đồng nghĩa container healthy là cookie còn hạn
Google vẫn có thể thu hồi phiên hoặc yêu cầu đăng nhập lại, không có bảo đảm gia hạn vĩnh viễn
Hồ sơ cookie tham khảo trên máy đã nhập thử nhưng hiện Google yêu cầu đăng nhập lại, cần nhập cookie mới
Cookie chưa được xác thực không được gắn vào request chatbot

## Truy xuất trực tiếp Qdrant

Chatbot tìm theo mã tiêu chí, tên tiêu chí và xếp hạng từ khóa trên payload Qdrant
Không gọi embedding hoặc LLM để tạo bộ lọc, không dùng tìm kiếm vector ngữ nghĩa trong triển khai mặc định
Giữ nguyên collection, vector và nội dung đã có, không nhập lại hay sửa dữ liệu
Đọc qua các trang thay vì chỉ xét 200 đoạn đầu, giới hạn an toàn 10000 point và 20 triệu ký tự nội dung
Kho tri thức trong quản trị có nút tìm tài liệu, chỉ đọc và vẫn yêu cầu đăng nhập

Service ai-embedding thuộc profile tùy chọn embedding-admin, không tự chạy khi khởi động hoặc CI/CD
AI_EMBEDDING_ENABLED mặc định bằng 0, công cụ vector bị tắt và không gọi Ollama
Volume embedding_models được giữ để tránh mất model cũ

Nếu cần công cụ vector của quản trị về sau, bật AI_EMBEDDING_ENABLED=1 và profile embedding-admin trong .env rồi khởi động lại service
Việc bật công cụ vector không đổi chatbot khỏi chế độ tìm trực tiếp Qdrant
