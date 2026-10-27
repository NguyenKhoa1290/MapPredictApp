# Chuyển zoom liền mạch

Cập nhật ngày 2026-10-26

Áp dụng cùng cấu hình cho bản đồ legacy và ba bản đồ dự án, giữ Leaflet và dữ liệu tọa độ hiện có

- Bỏ cờ ép tắt CSS 3D trong tài liệu legacy, vẫn cô lập và cắt phần vẽ trong vùng bản đồ để không tràn lên thanh bên
- Bật zoomAnimation, fadeAnimation và markerZoomAnimation khi người dùng không bật chế độ giảm chuyển động của hệ điều hành
- zoomSnap bằng 0 cho phép mức zoom lẻ, zoomDelta bằng 0,5 cho nút cộng trừ và bàn phím
- wheelPxPerZoomLevel bằng 120 và wheelDebounceTime bằng 40 để giảm độ nhạy của cuộn chuột
- Nền và layer dùng cùng phép chuyển của Leaflet trong lúc animation, cập nhật hình học sau khi kết thúc
- Canvas padding 0,3 giữ thêm phần hình học ngoài khung nhìn, tránh thiếu viền layer khi thu nhỏ nửa mức zoom
- Tile giữ buffer hai hàng/cột, không cập nhật từng mức zoom giữa cử chỉ zoom liên tục, giữ ảnh cũ trong lúc tải ảnh mới
- Giữ giới hạn ảnh nền, cắt/phóng đúng ảnh cha và retry có giới hạn của bộ nền hiện có

Cấu hình dùng chung ở `wwwroot/basemaps.js`, renderer của legacy ở `wwwroot/app.js` và trình xem dự án ở `frontend/src/shared/ui/ProjectMapCanvas.tsx`

Nguồn API tham khảo tại [Leaflet reference](https://leafletjs.com/reference) và [Leaflet zoom levels](https://leafletjs.com/examples/zoom-levels/)

Build đạt, 32 kiểm thử React/Leaflet và 16 kiểm thử Node cho nền/PDF đạt, kiểm thử route legacy đạt

Kiểm thử Leaflet thật trong jsdom có giả lập bề mặt canvas và khả năng CSS 3D, xác nhận tỷ lệ raster/canvas bằng nhau trong animation, ô lưới đúng kích thước sau khi kết thúc, viewport canvas đủ cho nửa bước thu nhỏ và điểm dưới chuột giữ vị trí khi zoom lẻ

Chưa đo FPS hoặc nghiệm thu chuyển động bằng Chrome thực, tốc độ tải ảnh vẫn phụ thuộc mạng và nguồn tile
