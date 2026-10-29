# Triển khai Linux

Checkout tại `/opt/map-predict`, chạy bằng tài khoản `admin` có quyền Docker

## Dữ liệu riêng

- `.env` và `.secrets` được chuyển qua SSH, không đưa lên GitHub
- File dự án đặt tại `data/projects`, model dự đoán tại `models`
- Volume `ai_settings` chứa cấu hình quản trị và hash passcode
- Volume `gemini_session` chứa cookie và trạng thái gia hạn
- Volume `embedding_models` chứa model `qwen3-embedding:0.6b`
- Volume `qdrant_data` chứa dữ liệu Qdrant
- CSV/DXF của khách đang tự lưu trong trình duyệt, dùng cùng tên miền để giữ origin lưu trữ

## Cấu hình VPS 2 CPU và 1 GB RAM

Máy hiện có khoảng 890 MB RAM sử dụng được, cần swap để chạy embedding

`.env` của VPS thêm hai dòng sau, giữ các cấu hình riêng đã có

```dotenv
COMPOSE_FILE=compose.yaml:compose.vps.yaml
PROJECT_DATA_PATH=./data/projects
```

`compose.vps.yaml` giới hạn bộ nhớ từng service và dùng image embedding CPU
`Dockerfile.embedding-cpu` giữ binary cùng thư viện CPU của phiên bản Ollama đang dùng, bỏ thư viện GPU
Image CPU đã thử trả embedding 1024 chiều trên máy local
Độ trễ và bộ nhớ trên VPS cần kiểm tra trực tiếp trước khi chuyển tunnel

## Khởi động và cập nhật

Nạp các image ứng dụng đã được kiểm tra, đặt dữ liệu riêng và khôi phục volume trước khi chạy

```bash
python3 -B tools/docker_stack.py start --no-build
sudo python3 -B tools/install_linux.py --user admin
```

Service systemd khởi động image có sẵn, không build lại khi reboot
Timer kiểm tra GitHub mỗi 5 phút và chỉ triển khai khi `main` trùng `deploy-ready`
Luồng cập nhật hiện build web, AI và Gemini, giữ nguyên volume

## Di chuyển Qdrant

Xuất point cùng payload và vector qua API, không sao chép trực tiếp thư mục database đang chạy
File trung chuyển chỉ dùng trong lúc di chuyển và phải giữ riêng

```bash
python3 -B tools/import_qdrant_migration.py --input .secrets/qdrant-migration.json
python3 -B tools/import_qdrant_migration.py --input .secrets/qdrant-migration.json --verify-only
```

Tool chỉ nhập vào collection trống hoặc xác nhận collection đã khớp hoàn toàn
Kiểm tra SHA-256 của tất cả payload và vector, dừng khi đích đã có dữ liệu khác

## Chuyển tunnel

Kiểm tra gateway nội bộ, model, bản đồ dự án và truy xuất AI trên VPS trước
Sau đó khởi động tunnel VPS và dừng connector trên máy Windows để chỉ còn một nơi phục vụ
Không cần đổi DNS khi giữ nguyên tunnel và hostname

## Tiến độ ngày 2026-10-29

Đã cài Docker trên Ubuntu 22.04, thêm swap 4 GB, clone repository và chuyển file dự án, cấu hình riêng, bản xuất 6 collection với 807 point cùng gói image ứng dụng
Chưa xác nhận khôi phục volume hoặc khởi động ứng dụng, chưa chuyển tunnel
SSH mới đang timeout ở bước nhận banner sau khi khởi tạo Docker, cần kiểm tra bằng Console/VNC của nhà cung cấp
