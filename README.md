# GeoPlan AI

Ứng dụng bản đồ, đánh giá quỹ đất và trợ lý GIS

## Cấu trúc thư mục

- `backend/map_predict/api` các API của web và trang quản trị
- `backend/map_predict/services` xử lý đánh giá, pipeline dự đoán và kết nối tới AI service
- `ai_service` API, cấu hình, prompt, chatbot và quản trị của service AI
- `shared` đọc CSV, xử lý GIS và cấu hình kết nối dùng chung
- `frontend` giao diện React của portal và trang quản trị
- `templates`, `wwwroot` giao diện bản đồ và dự đoán đang dùng trong công cụ đánh giá
- `integrations` kết nối và duy trì phiên Gemini
- `frontend/config` nội dung website và danh mục dự án, backend đọc để phục vụ API
- `models` pipeline dự đoán đang dùng
- `deploy`, `tools`, `.github` cấu hình triển khai, công cụ vận hành và CI/CD
- `tests` kiểm thử, dữ liệu mẫu nằm trong `tests/fixtures`
- `Tailieuthamkhao/docs` tài liệu, nhật ký, kế hoạch công việc và bằng chứng kiểm tra

`app.py` là điểm khởi động web, `ai_service/app.py` là điểm khởi động service AI
Trong Docker, backend web gọi AI qua mạng nội bộ, image AI chỉ chứa `ai_service` và `shared`

## Chạy trên máy

Dùng Python 3.11 và Node 24 từ phiên bản 24.15 trở lên

```powershell
py -3.11 -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
npm --prefix frontend ci
npm --prefix frontend run build
.\venv\Scripts\python.exe -m app
```

Mở http://127.0.0.1:8765/portal/

## Kiểm tra

```powershell
.\venv\Scripts\python.exe -B -W ignore::ResourceWarning -m unittest discover -s tests -p "test_*.py"
npm --prefix frontend test
node --test tests/basemaps.test.cjs tests/color_adjustments.test.cjs tests/pdf_export.test.cjs tests/assistant.test.cjs
```

## Tài liệu

- [Hướng dẫn sử dụng](Tailieuthamkhao/docs/USER_GUIDE.md)
- [Nhật ký dự án](Tailieuthamkhao/docs/NHAT_KY_DU_AN.md)
- [Kế hoạch công việc](Tailieuthamkhao/docs/NOTE_CONG_VIEC.md)
- [Docker](Tailieuthamkhao/docs/DOCKER_DEPLOYMENT.md)
- [VPS Linux](Tailieuthamkhao/docs/VPS_LINUX.md)
- [CI/CD](Tailieuthamkhao/docs/GITHUB_ACTIONS.md)
- [Quản trị AI](Tailieuthamkhao/docs/AI_ADMIN.md)

Các tài liệu trong `Tailieuthamkhao/docs` được quản lý bằng Git, các nguồn tham khảo khác trong `Tailieuthamkhao` chỉ lưu trên máy
Môi trường Python, thư viện Node, file build, cấu hình riêng, cookie và dữ liệu người dùng không đưa vào Git
