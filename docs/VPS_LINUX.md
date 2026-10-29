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
Embedding giới hạn RAM 256 MB, tổng RAM cùng swap 2 GB, CPU 0,75 core
Model giữ nguyên trọng số, dùng mặc định `num_batch=32`, `num_thread=1`, yêu cầu unload sau mỗi lượt
Đã kiểm tra trên VPS trả embedding 1024 chiều trong khoảng 45 giây, toàn luồng RAG và Gemini khoảng 75 giây, website vẫn trả 200 trong suốt lượt thử

VPS này từng có `vm.swappiness=0` tại `/etc/sysctl.conf` và liên kết `99-sysctl.conf`, ghi đè file cấu hình swap thêm sau đó
Đã sửa mục đang có cùng cấu hình riêng về 60, giữ các thiết lập sysctl khác
Theo [tài liệu kernel](https://docs.kernel.org/admin-guide/sysctl/vm.html#swappiness), mức 0 trì hoãn swap tới khi bộ nhớ xuống thấp, không tương đương việc không có swap
Không xác nhận OOM nếu chưa có log kernel hoặc cgroup

## Khởi động và cập nhật

Nạp các image ứng dụng đã được kiểm tra, đặt dữ liệu riêng và khôi phục volume trước khi chạy

```bash
python3 -B tools/docker_stack.py start --no-build
sudo python3 -B tools/install_linux.py --user admin --low-memory
```

Service systemd khởi động image có sẵn, không build lại khi reboot
Timer kiểm tra GitHub mỗi 5 phút và chỉ triển khai khi `main` trùng `deploy-ready`
Luồng cập nhật hiện build web, AI và Gemini, giữ nguyên volume

`--low-memory` yêu cầu có ít nhất 2 GB swap, sửa mục swappiness đang có và xác nhận kernel đọc được 60
Máy hiện đã có swap 4 GB
Khi chuẩn bị volume model mới, áp dụng mặc định đã kiểm tra qua API nội bộ, không tải hoặc đổi trọng số

```bash
docker compose exec -T ai-assistant python - <<'PY'
import json
from urllib.request import Request, urlopen
body = {'model': 'qwen3-embedding:0.6b', 'from': 'qwen3-embedding:0.6b',
        'parameters': {'num_batch': 32, 'num_thread': 1}, 'stream': False}
request = Request('http://ai-embedding:11434/api/create', data=json.dumps(body).encode(),
                  headers={'Content-Type': 'application/json'})
with urlopen(request, timeout=30) as response:
    assert json.load(response)['status'] == 'success'
PY
```

API tạo cấu hình dựa trên model đã có được mô tả tại [Ollama Create](https://docs.ollama.com/api/create)
Đã đối chiếu đường dẫn blob trọng số trước và sau, giữ nguyên 1024 chiều và Qdrant hiện có

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
Sau đó dừng connector trên máy Windows trước khi khởi động tunnel VPS để chỉ còn một nơi phục vụ
Không cần đổi DNS khi giữ nguyên tunnel và hostname

## Tiến độ ngày 2026-10-29

Đã khôi phục volume AI, Gemini và nhập đủ 6 collection với 807 point, checksum payload và vector đạt
Đã nạp image CPU, tải model qwen3-embedding:0.6b và chạy đủ 7 service trên VPS
Gateway nội bộ, model dự đoán và cả ba bản đồ dự án trả 200
Đã mở tên miền chính và admin bằng Chrome, kiểm tra CSV/DXF thật qua tên miền đạt lưu bản nháp, xác nhận, bỏ nháp, hoàn tác, làm lại và xóa CSV qua reload
Service systemd và timer cập nhật 5 phút đã được xác nhận active và enabled
Đã dừng cả 7 container local, đặt restart=no và vô hiệu hóa Scheduled Task MapPredictApp-AutoDeploy
Cloudflare từng xác nhận chỉ một connector từ IP VPS, không có connector local

Sau khi sửa cấu hình swap và giới hạn embedding, thử riêng vector và toàn bộ API chatbot đều đạt, website giữ phản hồi trong suốt hai lượt
RAGWire hybrid lấy đúng point 59929946-642c-45bb-a3a0-5b7a4e8394cd, trả đúng nhóm điểm cùng ô nguồn, không tự chọn điểm trong ô gộp
Đăng nhập quản trị qua tên miền đã kiểm tra thành công
Đã thử gia hạn hai tài khoản Gemini nhưng đều needs_login, Thông minh vẫn cookie_required và cần người dùng cập nhật cookie qua trang admin, Nhanh đã trả lời thật thành công
Đã bỏ profile chẩn đoán, bật lại cả 7 service với cấu hình đã kiểm tra, embedding tự khởi động và giữ model unload khi không dùng
Timer cập nhật và service khởi động đã bật lại, chạy kiểm tra cập nhật thành công
Đã kiểm tra lại đủ 6 collection và 807 point sau RAG, checksum vẫn khớp
Đã dọn gói trung chuyển trên VPS, giữ nguyên các volume bền vững và dữ liệu local
Cloudflare xác nhận một connector từ VPS, cả 7 container local vẫn dừng và AutoDeploy Windows bị vô hiệu hóa

Nếu cần tạm ngừng stack để kiểm tra qua Console/VNC, dừng cả timer để nó không tự bật Docker lại

```bash
sudo systemctl stop map-predict-update.timer map-predict-stack.service docker.service docker.socket
sudo systemctl restart ssh
free -h
sudo journalctl -k -b --no-pager | grep -Ei 'oom|out of memory|killed process'
```
