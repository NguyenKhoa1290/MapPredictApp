# CV-07 — Khung React và Flask

Cập nhật CV-19: trang Đánh giá đã nạp CSV, chạy bộ mô hình cố định và xuất CSV, xem [CV19_MO_HINH_CO_DINH.md](CV19_MO_HINH_CO_DINH.md)

Cập nhật sau đính chính: trang chi tiết địa phương đã chuyển thành bản đồ thật, API map không còn luôn trả 409. Xem trạng thái hiện tại tại [PROJECT_MAP_VIEWER.md](PROJECT_MAP_VIEWER.md); phần dưới ghi nhận phạm vi khung ban đầu.

Cập nhật: 2026-10-26. Triển khai local theo yêu cầu tiếp tục; chưa phát hành public. Mẫu CV-06 vẫn chờ duyệt trực quan.

## Phần đã triển khai

- `frontend/`: React, TypeScript, Vite; header Giới thiệu / Dự án / Đánh giá quỹ đất, trạng thái đang chọn và thao tác bàn phím.
- `/portal/` mở Giới thiệu; `/portal/projects`, `/portal/projects/hcm`, `/portal/projects/bac-kan`, `/portal/projects/phu-quoc` và `/portal/assessment` hỗ trợ truy cập trực tiếp/reload.
- Nội dung nhóm, ba ý Tầm nhìn và bốn thành viên nằm trong `config/public_content.json`. Nội dung dự thảo được ghi rõ; chưa có tên, ảnh hoặc liên hệ thật.
- Bốn thẻ dự án đọc từ `config/projects.json`; dự án AI dẫn sang Đánh giá. Hình SVG chỉ minh họa, không phải dữ liệu địa lý.
- `backend/map_predict/`: application factory, Blueprint API v1, dịch vụ đọc danh mục và phục vụ bản build React. API trả JSON có mã request; route/asset không tồn tại trả 404, không trả nhầm HTML của SPA.
- Frontend tải song song nội dung và danh mục, kiểm tra cấu trúc JSON, hủy request khi unmount, có trạng thái lỗi/thử lại. Không đọc hoặc ghi bản lưu IndexedDB cũ.

## API hiện có

- `GET /api/v1/health`: trạng thái dịch vụ.
- `GET /api/v1/site-content`: nội dung giới thiệu và khả năng mở công cụ cũ.
- `GET /api/v1/projects`: danh mục công khai đã lọc trường.
- `GET /api/v1/projects/<slug>`: thông tin dự án và bảng màu đã chốt.
- `GET /api/v1/projects/<slug>/map`: hiện trả 409 `PROJECT_NOT_READY`; chưa chuyển DXF hoặc giả định CRS. Không đưa đường dẫn nguồn, mô hình hay tài liệu tham khảo vào danh mục trả về.

## Chạy local

Yêu cầu Python theo `requirements.txt`, Node 24.15 trở lên thuộc nhánh 24 và npm. Có `package-lock.json` để cài cùng phiên bản.

```powershell
cd frontend
npm ci
npm run build
cd ..
.\venv\Scripts\python.exe -m app
```

Mở `http://127.0.0.1:8765/portal/`. Chế độ phát triển: chạy Flask như trên, sau đó `npm run dev` trong `frontend`, mở `http://127.0.0.1:5173/portal/`. Vite chuyển tiếp `/api`, `/legacy`, `/static` tới Flask. Các origin khác nhau không dùng chung bản lưu trình duyệt.

`python -m app` đăng ký Blueprint tương thích: công cụ cũ vẫn ở `/` và `/legacy/`. Khung mới chưa thay trang gốc của chế độ này. Factory độc lập `create_app()` không đăng ký API cũ và chuyển `/` sang `/portal/`.

## Phạm vi còn lại

- Chưa nối ba bản đồ thật, chưa xác nhận phép chiếu VN-2000 chi tiết; xử lý dữ liệu thuộc CV-12/CV-14 trở đi.
- Trang Đánh giá mới là khung hai tab, chưa có luồng nạp file/chạy mô hình. Chưa triển khai SQLite, workspace hoặc chuyển đổi bản lưu.
- Chính sách mô hình cố định và bỏ kết quả mặc định còn thuộc CV-19/CV-20. Công cụ cũ vẫn có hành vi upload/fallback trước đây; không dùng nguyên cấu hình tương thích này để public.
- CV-07 chưa nghiệm thu hoàn toàn: cần QA trực quan desktop/mobile và duyệt mẫu CV-06 trước khi chuyển giao diện mới thành trang gốc.

## Kiểm tra

- `npm run build` trong `frontend`: TypeScript và bản build production đạt.
- `npm test` trong `frontend`: 6 kiểm thử component React bằng jsdom đạt.
- `.\venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"`: 61 kiểm thử đạt, gồm 7 kiểm thử factory/API/route/asset mới. Bộ kiểm thử cũ còn phát ResourceWarning về file tạm; không có assertion thất bại.
- `node --test tests/preview.test.cjs tests/pdf_export.test.cjs tests/basemaps.test.cjs tests/color_adjustments.test.cjs`: 34 kiểm thử đạt.
- HTTP thực tế: API, các trang React, JS/CSS bản build và công cụ cũ trả 200 sau khi khởi động lại máy chủ local.
- Các kiểm thử DOM/jsdom không thay thế kiểm tra trình duyệt thực hoặc nghiệm thu responsive.
