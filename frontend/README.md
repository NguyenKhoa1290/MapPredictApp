# Frontend GeoPlan AI

## Mã nguồn

- `src/app` định tuyến, khung trang và dữ liệu dùng chung của portal
- `src/pages/about` trang giới thiệu
- `src/pages/projects` danh sách và bản đồ dự án, component bản đồ riêng
- `src/pages/assessment` trang công cụ đánh giá và phiên CSV
- `src/pages/assessment/csv` bảng dự đoán, lưu phiên và component riêng cho CSV
- `src/pages/ai-admin` trang quản trị AI và stylesheet của trang
- `src/shared` API, kiểu dữ liệu và component dùng ở nhiều trang
- `src/styles` CSS nền, bố cục và nhận diện dùng chung, giữ thứ tự import trong main.tsx
- `src/pages/about/content.json` nội dung giới thiệu và nhận diện dùng chung
- `src/pages/projects/catalog.json` cấu hình danh mục dự án
- `tests` kiểm thử theo nhóm app và trang, setup nằm tại tests/setup.ts

## Chạy và kiểm tra

Chạy các lệnh sau trong thư mục frontend

```shell
npm ci
npm run dev
npm run build
npm test
```

Vitest chỉ tìm file kiểm thử trong tests, TypeScript kiểm tra cả src và tests
Cấu hình nội dung nằm trong từng trang, cấu hình build và TypeScript nằm ở gốc frontend
