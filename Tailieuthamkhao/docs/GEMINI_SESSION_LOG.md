# Log chẩn đoán phiên Gemini

Log JSON từng dòng nằm trong volume `gemini_session`, đường dẫn trong container

```text
/var/lib/gemini-session/diagnostics/session.jsonl
```

Xem các sự kiện gần nhất trên VPS

```sh
cd /opt/map-predict
docker compose exec -T gemini-session tail -n 80 /var/lib/gemini-session/diagnostics/session.jsonl
```

Mỗi file tối đa 2 MiB và giữ 4 bản xoay vòng, tổng khoảng 10 MiB. Log tồn tại qua việc thay container. File mới chỉ chủ sở hữu đọc được, không đưa vào Git, không có endpoint public đọc log. Việc ghi log lỗi không làm dừng gia hạn hoặc đổi kết quả HTTP

`ts_utc` là giờ UTC, cộng 7 giờ khi đối chiếu thời gian Việt Nam. `account` là mã tài khoản nội bộ, không phải Gmail. `run_id` thay đổi khi tiến trình khởi động lại. `generation` là mã ngẫu nhiên mới mỗi lần nhập cookie, không được tạo từ nội dung cookie

## Dấu vết được ghi

- Khởi động service, mốc kiểm tra và xoay thành công gần nhất của từng tài khoản
- Nhịp vòng bảo trì, thời điểm đến hạn xoay, mức trễ, bắt đầu và hoàn tất chu kỳ
- Bắt đầu gia hạn, chờ cooldown, HTTP từ trang Gemini, RotateCookies, quota và phát hiện model
- Phân loại chuyển hướng về đăng nhập, thiếu XSRF, không khớp danh tính, RPC từ chối xác thực dù HTTP 200
- Tên cố định của các cookie xác thực được Google đổi hoặc xóa, ghi file thành công hoặc nhường cho lần cập nhật thủ công
- Nhập cookie mới, xoay và xác thực thành công, trạng thái tài khoản
- Bắt đầu gọi model, HTTP trả về, tên cookie xác thực nhận kèm, có hay không câu trả lời, loại lỗi và thời gian xử lý

Không ghi giá trị cookie, XSRF, Authorization, email, mật khẩu, passcode, prompt, câu trả lời, dữ liệu CSV/DXF, nội dung HTTP hoặc URL chuyển hướng đầy đủ. Chỉ các trường và giá trị trong danh sách cho phép được ghi, không ghi nguyên văn exception. Các sự kiện bình thường lặp lại được lấy mẫu mỗi 5 phút, các lỗi xác thực vẫn được ghi để giữ thời điểm chuyển trạng thái

## Đọc chuỗi lỗi

`rotation_due` và `refresh_start` cho biết tác vụ có thực sự đến hạn và bắt đầu. `google_response` ở endpoint `rotate_cookies` chỉ ghi mã HTTP và tên cookie thay đổi, HTTP 200 chưa đủ chứng minh phiên đã được gia hạn thành công

Từ bản sửa ngày 30/10/2026 sau sự cố đăng xuất, `rotation_cookie_renewed` xác nhận giá trị `__Secure-1PSIDTS` đã đổi và được lưu. `rotation_success` còn yêu cầu kiểm tra trang Gemini thành công sau đó. `rotation_no_renewal` cho biết Google không cấp giá trị PSIDTS mới, kể cả khi HTTP 200, SIDCC đã đổi và trang vẫn tạm đăng nhập được. Các sự kiện `rotation_success` ghi trước bản sửa này chưa phân biệt được trường hợp SIDCC đổi nhưng PSIDTS giữ nguyên

Trang quản trị tách thời điểm kiểm tra gia hạn khỏi thời điểm cookie thời hạn phiên thực sự đổi. Mốc cũ `session_rotated_at` không được coi là bằng chứng đổi PSIDTS, mốc mới là `session_cookie_renewed_at`. Một lần thử không cấp cookie mới vẫn giữ lịch thử định kỳ 10 phút, không quét lại ở mọi lần kiểm tra 30 giây khi phiên còn dùng được

`auth_failure` cho biết bước xác thực cụ thể bị từ chối, `network_error` ghi loại timeout hoặc lỗi kết nối, `cookie_save_conflict` cho biết có cập nhật cookie khác trong lúc ghi. Một `run_id` mới giúp đối chiếu việc container hoặc tiến trình vừa khởi động lại. Log chỉ cung cấp dấu vết quan sát được, không tự kết luận nguyên nhân nội bộ của Google

## Sự cố ngày 30/10/2026

Hai tài khoản nhập lúc 15:47:09 và 15:47:39 giờ Việt Nam, bị RPC từ chối lúc 17:46:52 và 17:47:22. Mỗi tài khoản có 11 lần kiểm tra xoay được code cũ ghi nhận thành công, nhưng chỉ đổi SIDCC, không có bằng chứng PSIDTS được cấp mới. Sau đó trang Gemini thiếu XSRF và các lần RotateCookies tiếp theo không khôi phục được xác thực

Tác vụ bảo trì vẫn hoạt động, không có sự kiện khởi động lại service giữa lần nhập và thời điểm lỗi. Người dùng xác nhận lấy cookie từ Chrome/Edge. Đây là khả năng phù hợp với cookie ràng buộc thiết bị, chưa đủ để khẳng định chính sách nội bộ Google. [Gemini WebAPI hướng dẫn thử cookie từ Firefox khi cookie Chromium hết hạn sau vài giờ](https://github.com/HanaokaYuzu/Gemini-API#initialization). Cần cookie phiên mới từ người dùng để kiểm tra khả năng gia hạn thực tế, server không thể tự tạo lại phiên đăng nhập đã bị từ chối
