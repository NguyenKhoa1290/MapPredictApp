# Trình duyệt Gemini trên VPS

Đây là bản thử một Chromium với profile lưu lâu dài, chưa thay adapter Gemini hay tự nhập cookie từ các tài khoản đang có

## Kết quả thử ngày 30/10/2026

VPS có 890 MiB RAM hệ điều hành sử dụng được và 4 GiB swap. Ở mức 256 MiB RAM cộng 128 MiB swap, trình duyệt chạm trần swap, Gemini trắng và điều khiển CDP timeout. Ở mức 384 MiB RAM cộng 128 MiB swap, giao diện Gemini tải được nhưng lại chạm cả hai trần bộ nhớ, hai phép kiểm tra website liên tiếp thất bại sau 8,173 và 7,443 giây

Bộ giám sát đã dừng riêng browser sau hai lần kiểm tra lỗi, website phản hồi health thành công sau khi dừng. Không ghi nhận OOM kill trong cgroup tại các mẫu đã đo. Chưa đăng nhập Google, chưa xác nhận tính ổn định khi có tài khoản. Browser đang dừng, không tự khởi động cùng VPS hoặc CI/CD mặc định, không nâng ngân sách bộ nhớ thêm trên VPS này

## Chạy thử

```sh
docker compose -f compose.yaml -f compose.vps.yaml -f compose.browser.yaml --profile gemini-browser up -d --build gemini-browser
```

Giới hạn 384 MiB RAM, tổng RAM và swap tối đa 512 MiB, 1 CPU và 192 tiến trình hoặc luồng. Phép thử đầu ở 256 MiB RAM và 128 MiB swap đã chạm trần swap, Gemini vẫn trắng và CDP timeout, do đó đã dừng container trước khi nâng giới hạn thử. Container không tự khởi động lại khi lỗi hoặc khi VPS khởi động lại trong giai đoạn thử. Profile nằm trong volume `gemini_browser_profile`, không xóa volume khi dừng thử

Container chạy bằng UID 10001, filesystem chỉ đọc, bỏ Linux capabilities và không được cấp secret của ứng dụng. Chromium dùng `--no-sandbox` trong container đã giới hạn quyền, do đó không dùng browser này để duyệt các website không liên quan. Trình quản lý mật khẩu và đồng bộ Chrome bị tắt

## Đăng nhập trực tiếp

Trên máy cá nhân mở chuyển tiếp SSH, giữ terminal này mở

```sh
ssh -N -L 127.0.0.1:9222:127.0.0.1:9222 admin@47.236.146.89
```

Mở `chrome://inspect/#devices`, chọn Configure và thêm `localhost:9222`, sau đó chọn inspect tại trang Gemini. Trong DevTools bật screencast nếu chưa thấy trang. Người dùng tự nhập tài khoản, mật khẩu và hoàn tất xác minh Google

Profile được tạo ngay trên VPS, không chỉ sao chép cookie vào một trình duyệt mới. Không gửi mật khẩu hoặc cookie qua chat. Cổng CDP có quyền điều khiển đầy đủ profile nên chỉ bind 127.0.0.1, không cấu hình tunnel Cloudflare cho cổng này

Nguồn hướng dẫn điều khiển headless: [Chrome DevTools](https://developer.chrome.com/docs/automation-and-testing/debug-headless). Google vẫn có thể yêu cầu đăng nhập lại hoặc từ chối một môi trường đăng nhập, chưa coi thử tải trang thành công là xác thực thành công

## Kiểm tra và dừng

```sh
docker stats --no-stream map-predict-gemini-browser-1
docker inspect --format '{{.State.OOMKilled}} {{.State.Health.Status}}' map-predict-gemini-browser-1
docker compose -f compose.yaml -f compose.vps.yaml -f compose.browser.yaml --profile gemini-browser stop gemini-browser
```

Sau khi xác nhận đăng nhập và mức dùng RAM, mới nối tài khoản tương ứng vào browser và tắt cơ chế RotateCookies HTTP cho tài khoản đó để tránh hai nơi thay đổi cùng phiên
