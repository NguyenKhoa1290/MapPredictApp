# Trình duyệt Gemini trên VPS

Đây là bản thử một Chromium với profile lưu lâu dài, chưa thay adapter Gemini hay tự nhập cookie từ các tài khoản đang có

## Chạy thử

```sh
docker compose -f compose.yaml -f compose.vps.yaml -f compose.browser.yaml --profile gemini-browser up -d --build gemini-browser
```

Giới hạn 256 MiB RAM, tổng RAM và swap tối đa 384 MiB, 0,5 CPU và 192 tiến trình hoặc luồng. Container không tự khởi động lại khi lỗi hoặc khi VPS khởi động lại trong giai đoạn thử. Profile nằm trong volume `gemini_browser_profile`, không xóa volume khi dừng thử

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
