# GitHub và quy trình CI

Repo: https://github.com/NguyenKhoa1290/MapPredictApp

Lần xác minh đầu tiên ngày 2026-10-27 đã thành công trên cả Windows, Ubuntu và job delivery
Mã nguồn đã kiểm tra là `7acf8b4dced76650415d1ef9db41bf6275a91433`
Xem [lần chạy và artifact](https://github.com/NguyenKhoa1290/MapPredictApp/actions/runs/40472565755)

## Nội dung đưa lên Git

Giữ mã nguồn backend và frontend, cấu hình, bộ kiểm thử đang dùng, pipeline hiện hành, ảnh giao diện, nhật ký và tài liệu
Không đưa venv, node_modules, cache, bản build sinh tự động, bộ chuyển đổi ODA cài sẵn, log, file cấu hình riêng hoặc Tailieuthamkhao lên repo
Các thư mục này vẫn nằm trên máy, bỏ theo dõi Git không xóa file local
Các file đã nằm trong commit cũ vẫn còn trong lịch sử Git, lần cập nhật này không viết lại lịch sử

Repo là public, vì vậy thư mục tham khảo và các file cấu hình riêng được bỏ qua toàn bộ
Không dùng git add -f để đưa chúng trở lại nếu chưa kiểm tra nội dung

## Khi push hoặc mở pull request

Workflow `.github/workflows/ci.yml` chạy trên Windows và Ubuntu với Python 3.11 và Node 24.21.0

1. Cài Python từ requirements.txt và Node từ frontend/package-lock.json
2. Build frontend và chạy bộ kiểm thử frontend
3. Chạy unittest backend cùng các kiểm thử Node cho bản đồ, màu và PDF
4. Tạo gói ZIP và kiểm tra ứng dụng sau khi giải nén ở thư mục riêng
5. Sau khi cả Windows và Ubuntu đạt, job delivery đóng gói trên Ubuntu và lưu artifact có tên MapPredictApp kèm SHA commit, giữ 14 ngày

Pull request chỉ chạy xác minh, push main hoặc chạy thủ công mới thực hiện job delivery

Các job kiểm thử và đóng gói chỉ có quyền đọc nội dung repo, các action được khóa theo commit SHA
Job cuối `deploy-ready` có quyền ghi nội dung để cập nhật riêng nhánh tín hiệu `deploy-ready` sau khi các job trước thành công
Workflow có thể chạy thủ công từ Actions → CI and delivery → Run workflow
Các lần chạy mới trên cùng nhánh sẽ thay thế lần cũ đang chờ

Hai kiểm thử đối chiếu ba dự án với dữ liệu thật chỉ chạy khi máy có đủ bộ nguồn trong Tailieuthamkhao
CI không có dữ liệu này nên báo skipped rõ lý do, các kiểm thử ghép mã và hình học tổng hợp vẫn chạy
Trên máy hiện tại có dữ liệu thật, bộ kiểm thử này vẫn phải đạt

## Dùng gói đã build

Mở tab Actions, chọn lần chạy thành công và tải artifact MapPredictApp tương ứng
Giải nén gói, tạo venv và cài requirements.txt, sau đó chạy run_python.bat
Gói đã có frontend build và pipeline, không cần Node để chạy ứng dụng

Các nguồn ba bản đồ dự án được cấp riêng, không nằm trong Git hoặc artifact
Đặt lại đúng bốn file dưới `Tailieuthamkhao/Giaodienfrontend/luoi` trên máy chạy để dùng ba dự án
Nếu chưa có, API trả PROJECT_NOT_READY, công cụ đánh giá vẫn dùng được với file người dùng nạp
Chức năng DWG cần cài ODA riêng, DXF không cần bộ cài này

CI kiểm tra thêm Docker image trên Ubuntu trước khi tạo artifact
Ứng dụng đã có triển khai Docker local và tunnel riêng theo yêu cầu mới, xem [DOCKER_DEPLOYMENT.md](DOCKER_DEPLOYMENT.md)
Máy cá nhân kiểm tra nhánh tín hiệu CI mỗi năm phút bằng Windows Task Scheduler rồi gọi Python tools/docker_stack.py deploy
VPS Linux dùng cùng mã cập nhật qua systemd timer, hướng dẫn cài tại [DOCKER_DEPLOYMENT.md](DOCKER_DEPLOYMENT.md)
VS Code và đăng nhập Git giúp commit/push, không tự tạo một môi trường chạy web public
Không mở cổng webhook, không cần GitHub API token, không đưa quyền điều khiển Docker vào container khác

## Tự cập nhật Docker trên máy hiện tại

Đã cài tác vụ `MapPredictApp-AutoDeploy`, chạy mỗi năm phút và khi người dùng đăng nhập Windows
Tác vụ chạy một lần rồi thoát, không có container hoặc tiến trình polling thường trực
Docker Desktop phải hoạt động, người dùng cài tác vụ phải đang đăng nhập

1. Push code lên main, CI chạy kiểm thử và đóng gói
2. Job cuối cập nhật nhánh `deploy-ready` tới commit đã qua đủ các job
3. Máy local chỉ cập nhật khi main và deploy-ready trùng SHA, workspace sạch và đang ở nhánh main
4. Git chỉ fast-forward tới đúng SHA đã xác nhận, sau đó build và chuyển slot bằng quy trình Docker hiện có
5. Bản đang chạy được giữ khi build hoặc kiểm tra bản mới thất bại, lần kiểm tra sau thử lại

Không dùng nhánh deploy-ready để phát triển hoặc push thủ công, nhánh này là tín hiệu do CI ghi
Nếu có code chưa commit trong workspace, tác vụ bỏ qua để tránh ảnh hưởng công việc đang làm
Giữ image slot cũ và dữ liệu mount, không tự xóa cache Docker

```powershell
# Cài lại trên workspace hiện tại, cần venv đã có Python
.\tools\install_auto_deploy.ps1
# Xem trạng thái và log
Get-ScheduledTaskInfo -TaskName MapPredictApp-AutoDeploy
Get-Content logs/auto-deploy.log -Tail 30
# Tạm dừng hoặc bật lại
Disable-ScheduledTask -TaskName MapPredictApp-AutoDeploy
Enable-ScheduledTask -TaskName MapPredictApp-AutoDeploy
```

Log tự xoay khi đạt 1 MiB và giữ hai bản cũ, revision đang chạy được ghi ở `.secrets/deployment-state.json`
GitHub cần cho phép GITHUB_TOKEN của job cuối ghi nội dung, nếu quyền này bị chặn thì nhánh tín hiệu không đổi và máy giữ bản cũ

Nguồn: [workflow runs](https://docs.github.com/en/rest/actions/workflow-runs), [thiết lập Scheduled Tasks](https://learn.microsoft.com/en-us/powershell/module/scheduledtasks/new-scheduledtasksettingsset)

Tài liệu chính thức: [Python trên GitHub Actions](https://docs.github.com/en/actions/tutorials/build-and-test-code/python), [lưu artifact](https://github.com/actions/upload-artifact)
