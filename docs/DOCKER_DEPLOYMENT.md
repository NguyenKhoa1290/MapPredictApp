# Docker và Cloudflare Tunnel

Đã triển khai trên máy Windows hiện tại tại https://danhgiaquyhoach.top
Địa chỉ local tiếp tục là http://127.0.0.1:8765

## Cấu trúc

Docker Compose project `map-predict` định nghĩa năm service, khi bật chatbot chạy bốn container

- `app` là Nginx giữ cổng host cố định và chuyển tiếp tới slot đang hoạt động
- `app-blue` và `app-green` chạy Python bằng Gunicorn, chỉ mở cổng trong mạng Docker
- `cloudflared` dùng tunnel riêng, kết nối tới `http://app:8000`, không đi vòng qua cổng host
- `gemini` là adapter chatbot trong mạng Docker riêng, không mở cổng host, xem [hướng dẫn trợ lý](CV26_27_CHATBOT.md)

Chỉ một slot Python chạy thường xuyên với một Gunicorn worker và hai thread
Frontend được build thành file tĩnh trong image, không chạy thêm Node server
Slot còn lại chỉ chạy trong lúc cập nhật, sau khi request cũ kết thúc sẽ được dừng và gỡ container
Trước khi tích hợp chatbot stack chỉ chạy ba container, muốn tắt chatbot đặt `MAP_PREDICT_ASSISTANT_ENABLED=0`, triển khai lại và dừng riêng service gemini

Tunnel và Nginx không bị tạo lại khi cập nhật một slot ứng dụng
Không dùng network_mode host và không thay đổi stack Docker của các dự án khác

## Dữ liệu và thông tin riêng

- `models` được bind mount chỉ đọc, không bị ghi đè khi dựng lại image
- `wwwroot/image` và `config` mount chỉ đọc để thay ảnh hoặc sửa nội dung rồi tải lại trang, không cần rebuild image
- Nguồn ba dự án dưới `Tailieuthamkhao/Giaodienfrontend/luoi` được mount chỉ đọc vào `/app/project-data`
- `.env` giữ cổng host, đường dẫn dữ liệu và giới hạn upload local
- `.secrets/cloudflared-token` được Compose cấp riêng cho cloudflared dưới dạng secret file
- API token Cloudflare chỉ dùng khi cấu hình tunnel, không được đưa vào container ứng dụng, image hoặc Git
- Trạng thái slot ở `.secrets/deployment-state.json`, cấu hình Nginx được sinh ở `deploy/local/nginx`
- `.gitignore` và `.dockerignore` loại thông tin riêng khỏi repo và build context

Giới hạn upload mặc định của stack là 64 MiB, dự đoán CSV vẫn dùng giới hạn riêng đã có
Ứng dụng chạy bằng user không phải root, root filesystem chỉ đọc và có tmpfs riêng để xử lý file tạm
File và kết quả người dùng tiếp tục tự lưu trong IndexedDB trên trình duyệt
Địa chỉ localhost và tên miền HTTPS là hai origin khác nhau, bản lưu không tự chuyển giữa hai địa chỉ

## Khởi tạo trên máy khác

Clone mã nguồn từ GitHub, chuẩn bị pipeline và bộ dữ liệu riêng, cài Docker Desktop với Linux containers
Đặt API token vào `.secrets/cloudflare-api-token`, không nhập token vào lệnh được lưu trong lịch sử hoặc commit

```powershell
.\tools\initialize_docker.ps1
python tools/configure_cloudflare.py --account-id YOUR_ACCOUNT_ID --hostname YOUR_HOSTNAME --zone YOUR_ZONE
docker compose build app-blue
.\tools\start_docker.ps1
```

Script cấu hình Cloudflare từ chối thay bản ghi DNS của ứng dụng khác và không in token ra màn hình
Máy hiện tại đã có đủ file riêng, không cần cấu hình lại tunnel khi cập nhật code

## Cập nhật code

Windows và Linux dùng chung `python tools/docker_stack.py deploy`
Các file PowerShell là lệnh gọi tương thích với cách vận hành cũ, không còn giữ thuật toán triển khai riêng

Máy hiện tại đã cài tác vụ Windows `MapPredictApp-AutoDeploy`, tự kiểm tra mỗi năm phút và triển khai commit main được CI đánh dấu thành công
Không chạy thêm container updater, chi tiết và cách tạm dừng tại [GITHUB_ACTIONS.md](GITHUB_ACTIONS.md)
Nếu workspace có thay đổi chưa commit, tác vụ tự bỏ qua, vẫn có thể triển khai thủ công như dưới đây

```powershell
.\tools\deploy_docker.ps1 -Pull
```

Bỏ `-Pull` nếu muốn triển khai code local chưa push
Script khóa để tránh hai lần triển khai đồng thời, chờ các request cũ kết thúc trước khi dùng lại slot dự phòng
Sau đó build và khởi động lại slot không hoạt động, kiểm tra model cùng frontend trước khi đổi upstream Nginx
Nếu build hoặc kiểm tra model thất bại, slot cũ tiếp tục phục vụ
Nginx reload theo cách graceful, không dùng docker compose down để cập nhật code
Chờ request trên slot cũ hoàn thành rồi dừng và gỡ container đó để giải phóng RAM

Thay model hoặc dữ liệu mount có hiệu lực độc lập với image, blue/green không phải cơ chế sao lưu model hoặc dữ liệu gốc
Không xóa `.secrets`, `.env` hoặc `deploy/local` khi cập nhật
Khóa nội bộ assistant được tự sinh tại `.secrets/assistant-key`, chỉ cấp cho backend và Gemini, không dùng API token Cloudflare

## Vận hành

```powershell
docker compose ps
docker compose logs --tail 100 app app-blue app-green cloudflared
.\tools\start_docker.ps1
```

Docker Desktop và máy tính cần hoạt động để tên miền tiếp tục truy cập được
Các service có restart policy unless-stopped và log được giới hạn kích thước
Khởi động lại toàn stack chỉ dùng khi cần, cập nhật code dùng script blue/green
Không dùng `docker compose up` cho toàn bộ service vì sẽ bật cả slot dự phòng

## Chuyển sang VPS Linux

Cấu hình Compose và mã ứng dụng giữ nguyên, không cần thêm container updater
Trình cập nhật chạy một lần rồi thoát bằng systemd timer, chỉ triển khai SHA main đã được CI đánh dấu qua nhánh deploy-ready
Mặc định kiểm tra sau khi khởi động hai phút và năm phút sau khi lần kiểm tra trước kết thúc
Stack tự khởi động cùng VPS và chỉ bật slot ứng dụng đang hoạt động

Điều kiện ban đầu trên VPS dùng systemd, ví dụ Ubuntu hoặc Debian

- Cài Docker Engine cùng Compose plugin, Git và Python 3
- Clone repo vào thư mục do tài khoản triển khai sở hữu, tài khoản đó cần có quyền chạy Docker
- Chuyển `models`, thư mục dữ liệu dự án, ảnh, nội dung, `.env` và `.secrets/cloudflared-token` sang VPS theo đúng đường dẫn
- Không đưa API token Cloudflare lên VPS nếu chỉ chạy tunnel đã cấu hình
- Trong `.env`, dùng đường dẫn Linux hoặc giữ đường dẫn tương đối mặc định, không dùng đường dẫn ổ đĩa Windows
- Nếu chuyển thay cho máy Windows, dừng stack trên máy Windows để tunnel chỉ phục vụ bộ dữ liệu trên VPS

Không cần cài Node, venv hoặc thư viện GIS trên host Linux, Docker build đảm nhiệm các phần này
Chạy dưới tài khoản triển khai, từ thư mục repo

```bash
python3 tools/docker_stack.py initialize
sudo python3 tools/install_linux.py --user "$(id -un)"
```

Lần cài đầu có thể mất thời gian do build image, các lần cập nhật sau tự dùng cache Docker
Không cần cấu hình SSH từ GitHub, mở webhook hoặc cấp Docker socket cho container phụ

```bash
# Trạng thái và nhật ký
systemctl status map-predict-stack.service map-predict-update.timer
journalctl -u map-predict-update.service -n 50
tail -n 30 logs/auto-deploy.log
# Kiểm tra ngay hoặc tạm dừng tự cập nhật
sudo systemctl start map-predict-update.service
sudo systemctl disable --now map-predict-update.timer
# Cập nhật thủ công hoặc khởi động lại các container cần thiết
python3 tools/docker_stack.py deploy --pull
python3 tools/docker_stack.py start
```

Host Windows đã kiểm tra khởi động bằng Python, luồng triển khai được kiểm thử cả Windows và container Linux
Chưa cài thực tế trên VPS vì chưa có máy chủ Linux được cung cấp

Nguồn systemd: [timer](https://www.freedesktop.org/software/systemd/man/260/systemd.timer.html)

## Tối ưu tài nguyên ngày 2026-10-27

- Image ứng dụng giảm từ 837255739 byte xuống 617451381 byte, khoảng 26 phần trăm
- Bỏ test suite của thư viện và bytecode khỏi image bằng build nhiều giai đoạn
- Giới hạn luồng BLAS/OpenMP, một Nginx worker và một Gunicorn worker với hai thread
- Đo Docker stats sau khi nạp bản đồ và dự đoán cho tổng khoảng 224 MiB RAM, trước thay đổi khoảng 583 MiB
- Các số RAM là mẫu đo trên máy hiện tại, có thể tăng theo dữ liệu và số request đồng thời
- 84 kiểm thử Python đạt trong image production đã tinh gọn, gồm dữ liệu dự án thực tế
- CI chạy thêm bộ kiểm thử Python trực tiếp trong image production

Giữ image slot cũ để sử dụng lại cache khi cập nhật, không tự dọn cache Docker hoặc image của các dự án khác

## Xác minh thực tế ngày 2026-10-27

CI của bản cấu hình cuối cùng đã đạt tại [lần chạy 40478081017](https://github.com/NguyenKhoa1290/MapPredictApp/actions/runs/40478081017)
Các job Windows, Ubuntu, Docker image, Compose validation và delivery đều thành công

- Cả hai slot và Nginx đạt healthcheck, Cloudflare báo tunnel healthy
- HTTP qua proxy đọc đúng 1695 ô TP.HCM, 400 ô Bắc Kạn và 1676 ô Phú Quốc
- Cả API legacy và API v1 dự đoán được với Origin HTTPS qua proxy
- Trình duyệt mở tên miền HTTPS, nạp CSV tổng hợp và chạy dự đoán thành công
- Đã chuyển blue sang green, ID container proxy và tunnel không đổi
- 335 lần kiểm tra health liên tục quanh lần chuyển đều nhận HTTP 200, không ghi nhận lỗi trong mẫu kiểm tra này
- 84 kiểm thử Python đạt sau thay đổi cấu hình proxy
- Công cụ chụp ảnh trình duyệt không trả được ảnh trong bước này, bằng chứng truy cập và kết quả được kiểm tra qua DOM

Không thay đổi hoặc xác nhận lại CRS của ba dự án trong lần triển khai này

Nguồn chính thức: [mạng Compose](https://docs.docker.com/compose/how-tos/networking/), [Compose secrets](https://docs.docker.com/compose/how-tos/use-secrets/), [Cloudflare token-file](https://developers.cloudflare.com/tunnel/reference/run-parameters/)
