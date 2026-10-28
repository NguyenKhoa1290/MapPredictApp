# Docker local cho MapPredictApp

Từ ngày 2026-10-28 dùng một bản chạy cho mỗi service để thử nghiệm local
Không dùng blue/green, không giữ slot dự phòng và không tự tạo snapshot
Khi cập nhật có thể gián đoạn ngắn, chưa yêu cầu cơ chế production HA

## Cụm Docker

Cùng Compose project `map-predict` gồm bảy service

- `web-portal` là backend Flask và frontend tĩnh
- `ai-assistant` xử lý chat, quản trị và chỉnh DXF
- `gemini-session` là adapter model và duy trì phiên Google
- `ai-embedding` là Ollama dành cho công cụ quản trị
- `qdrant` giữ dữ liệu trong volume `map-predict_qdrant_data`
- `web-gateway` là Nginx, giữ cổng local 127.0.0.1:8765
- `cloudflare-tunnel` giữ kết nối tên miền hiện có

Qdrant dùng đúng image 1.19.1 đã có trên máy, cổng quản trị chỉ bind 127.0.0.1:6333
AI truy cập Qdrant tại http://qdrant:6333, không khởi động container ngoài project
Ollama embedding chạy trong ai-embedding, có thể đổi URL trong quản trị để dùng máy khác
Chatbot chỉ tìm từ khóa trong Qdrant, không gọi embedding theo lựa chọn của người dùng
Xem [Quản trị AI](AI_ADMIN.md) để thiết lập mật khẩu, cookie và model

## Khởi động và cập nhật

```powershell
.\tools\start_docker.ps1
.\tools\deploy_docker.ps1 -Pull
```

Cùng lệnh trên Linux

```bash
python3 tools/docker_stack.py start
python3 tools/docker_stack.py deploy --pull
```

Script build trước khi cập nhật các container hiện có, chờ healthcheck rồi kiểm tra model, frontend và gateway AI
Chỉ ghi revision thành công sau khi các bước kiểm tra đạt
Build lỗi không restart container, healthcheck lỗi cần sửa rồi thử lại
Không có tự động quay về phiên bản cũ

Tác vụ tự cập nhật sau CI vẫn kiểm tra mỗi năm phút, chỉ cập nhật main đã được CI đánh dấu
Nếu workspace có thay đổi chưa commit, tác vụ bỏ qua

## Dữ liệu và cấu hình

- models, config, ảnh và dữ liệu ba dự án vẫn mount từ workspace
- File người dùng và kết quả tiếp tục tự lưu riêng trong trình duyệt
- Qdrant thuộc Compose và giữ nguyên dữ liệu trong named volume qua các lần thay container
- Khóa nội bộ assistant và token tunnel nằm trong .secrets, không đưa vào Git hay image
- Backup do người dùng quản lý, không tạo snapshot hoặc giữ nhiều bản chạy tự động
- Không dùng docker compose down -v khi chỉ muốn dừng hoặc cập nhật, vì lệnh đó xóa volume dữ liệu

## Chuyển dữ liệu ngày 2026-10-28

Đã chuyển toàn bộ dữ liệu từ container qdrant cũ sang volume trong cụm
Đã đối chiếu SHA-256 trên payload và vector của từng collection, đủ 807 point trong 6 collection
Dữ liệu sparse được giữ nguyên, dung lượng vật lý của volume khoảng 54 MiB
Container nguồn và snapshot do agent tạo lần trước đã được xóa sau khi đối chiếu
Không tạo snapshot mới trong lần chuyển này

## Khi chuẩn bị VPS

Giữ cùng code và Compose, chỉ cấp dữ liệu, khóa và cấu hình kết nối phù hợp
Cài Docker Engine với Compose plugin, Python 3 và Git
Cấp dữ liệu Qdrant từ bản backup do bạn quản lý vào volume trước khi dùng RAG
Có thể cài systemd bằng tools/install_linux.py khi thực sự cần đưa lên VPS
Hiện chưa triển khai VPS

Nguồn kỹ thuật: [Docker volumes](https://docs.docker.com/engine/storage/volumes/)
