# Frontend GeoPlan AI

## Mã nguồn

- `src/app` định tuyến, khung trang và dữ liệu dùng chung của portal
- `src/pages/about` trang giới thiệu
- `src/pages/projects` danh sách và bản đồ dự án, component bản đồ riêng
- `src/pages/assessment` trang công cụ đánh giá và phiên CSV
- `src/pages/assessment/components` giao diện React cho thanh công cụ, bản đồ và dự đoán
- `src/pages/assessment/engine` bộ điều khiển DOM/Leaflet, tự lưu, chỉnh sửa layer, PDF và chatbot, có vòng đời khởi tạo và hủy
- `src/pages/assessment/csv` bảng dự đoán, lưu phiên và component riêng cho CSV
- `src/pages/ai-admin` trang quản trị AI và stylesheet của trang
- `src/shared` API, kiểu dữ liệu và component dùng ở nhiều trang
- `public` ảnh, Leaflet và tiện ích trình duyệt, được backend phục vụ tại /static
- `src/styles` CSS nền, bố cục và nhận diện dùng chung, giữ thứ tự import trong main.tsx
- `src/pages/about/content.json` nội dung giới thiệu và nhận diện dùng chung
- `src/pages/projects/catalog.json` cấu hình danh mục dự án
- `../quality/frontend` kiểm thử theo nhóm app và trang, setup nằm tại quality/frontend/setup.ts

## Chạy và kiểm tra

Chạy các lệnh sau trong thư mục frontend

```shell
npm ci
npm run dev
npm run build
npm test
```

Vitest tìm kiểm thử trong quality/frontend, TypeScript kiểm tra cả src và bộ kiểm thử này
Cấu hình nội dung nằm trong từng trang, cấu hình build và TypeScript nằm ở gốc frontend
Trang assessment dùng React trực tiếp, không có iframe hoặc thực thi mã bằng eval
IndexedDB và các khóa lưu phiên được giữ để khôi phục dữ liệu từ giao diện trước
