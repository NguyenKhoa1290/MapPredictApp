# Quản trị AI

Trang quản trị tại `/portal/admin/ai`, có liên kết ở footer
Web chỉ chuyển tiếp yêu cầu, service ai-assistant xác thực mật khẩu và phiên quản trị

## Mật khẩu

```bash
python tools/set_ai_admin_password.py
```

Lệnh hỏi mật khẩu trực tiếp, không ghi mật khẩu vào lịch sử lệnh
Mật khẩu băm nằm trong `.secrets/ai-admin-password.hash`, không đưa vào Git hoặc image
Cookie đăng nhập HttpOnly, SameSite Strict, có Secure khi truy cập HTTPS và hết hạn sau 8 giờ
Các thao tác thay đổi cần CSRF, đăng nhập giới hạn 5 lần mỗi phút
Thay mật khẩu làm phiên cũ mất hiệu lực

## Hai chế độ chatbot

- Nhanh mặc định dùng gemini-3.6-flash theo tên adapter được cung cấp
- Thông minh mặc định dùng gemini-3.5-flash-thinking theo chế độ thinking của adapter
- Có thể đổi từng chế độ sang API tương thích OpenAI, nhập URL gồm /v1, model và khóa riêng
- Chỉ client gửi fast hoặc smart, không cho client chỉ định endpoint hoặc model tùy ý
- Lưu cấu hình trước khi bấm kiểm tra, thay đổi có hiệu lực ở lượt chat tiếp theo
- Tên và khả năng của model Gemini Web phụ thuộc server tham khảo và tài khoản, không phải cam kết model API chính thức

Cài đặt và khóa API lưu trong volume ai_settings
API quản trị chỉ trả dấu hiệu đã có khóa, không trả khóa lại trình duyệt
Để trống ô khóa giữ khóa cũ, chọn xóa khóa nếu muốn bỏ
Khóa nội bộ của cụm không được gửi sang API bên ngoài

## Phiên Gemini

Service gemini-session chạy liên tục, kiểm tra phiên mỗi 20 phút và thử RotateCookies sau 12 giờ
Cơ chế dựa trên google_session.py của dự án tham khảo, khóa file đã hỗ trợ Windows và Linux
Cookie mới và XSRF được lưu nguyên tử trong volume gemini_session, tồn tại qua việc thay container
Có thể nhập cookie JSON hoặc header Cookie từ quản trị và bấm gia hạn ngay
Chỉ số tài khoản là số trong /u/0, /u/1 nếu dùng tài khoản không mặc định

Healthcheck của container chỉ xác nhận adapter HTTP đang chạy
Trạng thái phiên Google hiển thị riêng trong quản trị, không đồng nghĩa container healthy là cookie còn hạn
Google vẫn có thể thu hồi phiên hoặc yêu cầu đăng nhập lại, không có bảo đảm gia hạn vĩnh viễn
Hồ sơ cookie tham khảo trên máy đã nhập thử nhưng hiện Google yêu cầu đăng nhập lại, cần nhập cookie mới
Cookie chưa được xác thực không được gắn vào request chatbot

## Embedding chỉ cho quản trị

Theo xác nhận người dùng, chatbot không gọi embedding
Chatbot đọc tối đa 200 point trong collection để xếp hạng từ khóa, vẫn giữ bước xác minh nguồn trước khi chấm điểm
Hai công cụ embedding chỉ hoạt động khi có phiên quản trị hợp lệ

```bash
docker compose exec ai-embedding ollama pull qwen3-embedding:0.6b
```

Model được lưu trong volume embedding_models, không nạp sẵn vào RAM khi khởi động
Chỉ chạy một yêu cầu công cụ mỗi lần, gửi keep_alive bằng 0 sau yêu cầu embedding
Công cụ kiểm tra vector chỉ trả số chiều, công cụ tìm tài liệu chỉ đọc Qdrant
Không tự ghi lại vector, thay collection hay đổi model nhúng của dữ liệu cũ
Nên giữ qwen3-embedding:0.6b cùng dữ liệu 1024 chiều hiện tại
Cấu hình URL có thể trỏ tới Ollama máy khác, không cần sửa code

Service embedding không mở cổng ra host và không mount Docker socket
Giới hạn RAM 1 GB và RAM cộng swap 2 GB chỉ là giới hạn container, không tự tạo swap trên host
Chưa xác nhận toàn bộ cụm phù hợp VPS 1 GB RAM, cần đo tải khi có VPS

Nguồn kỹ thuật [Ollama embed](https://docs.ollama.com/api/embed), [Docker memory và swap](https://docs.docker.com/engine/containers/resource_constraints/)
