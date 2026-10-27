# GitHub và quy trình CI

Repo: https://github.com/NguyenKhoa1290/MapPredictApp

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

GitHub Actions chỉ có quyền đọc nội dung repo, các action được khóa theo commit SHA
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

Đây là CI và phân phối bản build, chưa có bước tự triển khai lên máy chủ vì hiện chưa chọn hosting
VS Code và đăng nhập Git giúp commit/push, không tự tạo một môi trường chạy web public
Khi có máy chủ, bổ sung bước triển khai và cấu hình quyền, không đặt khóa SSH hoặc token vào mã nguồn

Tài liệu chính thức: [Python trên GitHub Actions](https://docs.github.com/en/actions/tutorials/build-and-test-code/python), [lưu artifact](https://github.com/actions/upload-artifact)
