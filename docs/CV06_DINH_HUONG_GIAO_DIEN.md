# CV-06 — Định hướng giao diện từ mẫu DC Solution

Ghi chú ngày 2026-10-27: đây là tài liệu lịch sử, prototype và các kiểm thử riêng của prototype đã được chuyển sang thư mục lưu trữ ngoài dự án khi dọn dẹp
Giao diện đang dùng ở `/portal/`, nội dung bên dưới giữ lại để tham khảo, các đường dẫn và lệnh chạy prototype cũ không còn áp dụng trong thư mục làm việc

Ngày: 2026-10-26. Trạng thái: **đã dựng bản xem trước cục bộ, chờ người dùng duyệt**. Đây là prototype HTML/CSS/JS riêng, chưa chuyển ứng dụng sang React hoặc thay trang đang chạy.

## Bản xem trước CV-06

- Địa chỉ prototype trước đây là `http://127.0.0.1:8765/static/preview/index.html`, mã nguồn trước đây ở `wwwroot/preview/index.html`
- Đã có header 3 mục; trang Giới thiệu với mở đầu, giới thiệu, 3 ý Tầm nhìn, 4 dự án, 4 vị trí thành viên; trang Dự án có lọc; trang mẫu Đánh giá có tab Bản đồ/Dự đoán.
- Ba nút dự án địa phương mở hộp xem bố cục; dự án AI dẫn tới mục Đánh giá. Sơ đồ tự vẽ SVG được ghi rõ là minh họa, không phải bản đồ/kết quả địa phương thật.
- Nút “Mở công cụ hiện tại” mở ứng dụng cũ ở tab mới. Prototype không gọi API, nhận file, chạy AI, ghi IndexedDB hoặc thay dữ liệu phiên.
- Chưa cài React/Vite hoặc dựng API v1: đây là bước duyệt bố cục CV-06, công nghệ đã chốt được áp dụng khi triển khai CV-07 trở đi.
- Prototype đang dùng header thường, không sticky; có CSS cho màn hình nhỏ và giảm chuyển động. Chưa coi responsive là đã nghiệm thu chỉ vì có media query.
- Đã kiểm tra cú pháp JS, HTTP 200 cho trang/assets và trang cũ; 6 kiểm thử logic bằng DOM giả lập, 3 kiểm thử Python cho cấu trúc/static assets đạt. Chưa có kết nối trình duyệt để kiểm tra trực quan/kích thước thực; không có ảnh chụp QA desktop/mobile và chưa tuyên bố đã đạt kiểm thử trình duyệt.
- Chạy lại kiểm tra: `node --test tests/preview.test.cjs` và `.\venv\Scripts\python.exe -m unittest tests.test_preview_assets -v`.

## 1. Nguồn đã tham khảo và mức độ kiểm chứng

- [Trang chủ DC Solution](https://dcsolution.vn/): lần thử lại đã đọc được nội dung qua công cụ web; HTTP trực tiếp trả 200. Có ảnh minh họa, phần mở đầu, ba khối Công ty / Thiết kế / Kết quả, danh mục dự án, quy trình và liên hệ.
- HTML trang chủ xác nhận các khối giới thiệu dùng nhóm cột có class `medium-4 small-12 large-4`. Đây là căn cứ tham khảo cấu trúc 3 cột, không phải kết quả kiểm tra giao diện thực tế trên từng thiết bị.
- [Sứ mệnh bền vững](https://dcsolution.vn/su-menh-ben-vung/): nội dung chia thành các nhóm mục tiêu/giá trị và triết lý thiết kế. Chỉ tham khảo cách phân cấp nội dung, không lấy số liệu hay cam kết của công ty làm thành tích của nhóm.
- [Dự án](https://dcsolution.vn/du-an/): có phần danh mục và nội dung dẫn người xem khám phá dự án. Chỉ dùng làm nguồn cấu trúc, không sao chép dự án sân vườn.
- Trang giới thiệu chi tiết có lần tải bị timeout; không tuyên bố đã đọc toàn bộ website. Lần này đã đọc nội dung/HTML, chưa xác nhận bằng ảnh chụp toàn trang hoặc test tương tác desktop/mobile.
- Website là của bạn người dùng theo thông tin người dùng cung cấp. Việc này không tự có nghĩa phải lấy logo, ảnh, liên hệ hoặc mã nguồn trang mẫu sang dự án.

## 2. Cách áp dụng vào MapPredictApp

Giữ yêu cầu đã chốt: **tham khảo khuôn mẫu nội dung, dùng phong cách Đánh giá quỹ đất**, không sao chép nguyên layout, CSS hoặc chức năng kinh doanh của trang mẫu.

- Tham khảo cách chia trang thành các phần có tiêu đề rõ, hình minh họa và lối dẫn tới dự án.
- Thay khối giới thiệu doanh nghiệp bằng phần giới thiệu nhóm/nghiên cứu và mục đích công cụ.
- Chuyển cách trình bày các ý giá trị thành **3 ý Tầm nhìn** của nhóm, không đổi lại thành ba mục Giới thiệu / Sứ mệnh / Tầm nhìn.
- Thay danh mục cảnh quan bằng đúng 4 dự án đã thống nhất.
- Thêm 4 thẻ thành viên theo yêu cầu riêng của người dùng; đây là phần đề xuất cho dự án, không khẳng định đã thấy mẫu 4 thành viên trên nguồn.
- Không thêm dịch vụ, bảng giá, giỏ hàng, tin tức, form thu số điện thoại, hotline nổi hoặc cam kết số liệu chỉ vì trang mẫu có chúng. Chatbot vẫn làm sau.

## 3. Bố cục trang Giới thiệu đề xuất

Theo thứ tự từ trên xuống:

1. **Header:** logo/tên nhóm bên trái; Giới thiệu / Dự án / Đánh giá quỹ đất bên phải. Đúng 3 mục, có trạng thái đang chọn. Chưa thêm Đăng nhập khi chính sách truy cập chưa chốt.
2. **Phần mở đầu:** tên đề tài/công cụ, mô tả ngắn về đánh giá quỹ đất theo quy hoạch chi tiết; nút chính “Đánh giá quỹ đất”, nút phụ “Xem dự án”. Ảnh hoặc hình minh họa bản đồ nằm cạnh nội dung trên desktop, xếp dưới trên màn hình nhỏ.
3. **Giới thiệu nhóm:** đoạn ngắn về lĩnh vực, mục tiêu và phạm vi nghiên cứu; nội dung lấy từ báo cáo khi có, không bịa thành tích hoặc tên tổ chức.
4. **Tầm nhìn:** 3 ý ngang trên desktop, dọc trên điện thoại. Gợi ý nội dung để người dùng duyệt: hỗ trợ phân tích quy hoạch bằng dữ liệu; trình bày đánh giá trực quan; phát triển công cụ ứng dụng AI. Đây là bản nháp nội dung, không phải tuyên bố đã trích từ báo cáo.
5. **Dự án:** 4 thẻ có ảnh/khung minh họa, tên và nút mở. Ba địa phương mở trình xem kết quả; thẻ AI dẫn tới cùng trang Đánh giá quỹ đất.
6. **Thành viên:** 4 thẻ ảnh, tên, vai trò và liên hệ. Chưa có dữ liệu thì ghi rõ nội dung mẫu/chờ cập nhật, không dùng thông tin của công ty mẫu hoặc liên hệ giả.
7. **Cuối trang:** thông tin nhóm/liên hệ đã được xác nhận và dòng bản quyền phù hợp. Không biến footer thành thanh điều hướng chính, vì người dùng đã sửa yêu cầu thành header.

Không bắt buộc thêm phần quy trình dài của trang mẫu. Nếu cần giải thích cách dùng công cụ, chỉ bổ sung khi được duyệt để tránh làm trang Giới thiệu quá dài.

## 4. Phong cách chung lấy từ giao diện hiện tại

Đã đối chiếu `wwwroot/app.css`, đặc biệt nhóm style `workspace-mode`, header, sidebar và bảng dữ liệu:

- Nền trắng, chữ xanh đậm, điểm nhấn xanh lá; không mang nền gradient/chuyển động và hiệu ứng glass cũ vào toàn bộ trang giới thiệu mới.
- Font **Inter** như code hiện tại, có fallback sans-serif; không đổi sang cặp font của trang mẫu chỉ để giống nguồn. Khi triển khai public sẽ xác định cách đóng gói font để giao diện vẫn đọc được khi nguồn font ngoài lỗi.
- Màu chính `#0d914f`, hover `#087b43`, tiêu đề `#193b2a`, nền nhấn nhẹ `#e8f5ec`, viền `#cddbd1`. Đây là màu trong code dự án, không khẳng định là màu thương hiệu DC Solution.
- Nút/thẻ bo góc nhẹ 8–10 px, viền mảnh; dùng khoảng trắng để phân cấp, hạn chế bóng và chuyển động trang trí.
- Đề xuất cỡ chữ nội dung khoảng 16 px; tiêu đề trang lớn hơn, các heading có phân cấp nhất quán. Màu chữ và cỡ chữ phải được xem lại trên mẫu thực tế trước khi duyệt.
- Màu kết quả Y giữ đúng CV-04: đỏ/cam/xanh lá, không dùng màu thương hiệu để thay nghĩa của lớp kết quả.

## 5. Trang Dự án và hai chế độ bản đồ

- **Danh sách Dự án:** 4 thẻ dùng cùng dữ liệu với danh sách trên Giới thiệu, không quản lý hai bộ tên/liên kết riêng. Đề xuất 2 cột desktop và 1 cột màn hình nhỏ.
- **Bản đồ dự án chỉ xem:** header gọn, panel thông tin/chú giải bên trái, bản đồ chiếm vùng còn lại; click ô mở thông tin. Không có upload Excel/layer hoặc nút chạy mô hình.
- **Đánh giá quỹ đất:** giữ bố cục công cụ hiện tại, có hai tab Bản đồ/Dự đoán bên trong. Bản đồ: điều khiển trái, bản đồ phải; dự đoán: điều khiển trái, bảng dữ liệu phải.
- Inspector không che thanh điều khiển; PDF nằm ngay dưới “Hiển thị trên bản đồ”. Không thêm phần mở đầu/ảnh trang trí vào không gian làm việc khiến bản đồ bị thu hẹp.
- Các ô không xét, gộp trùng Phú Quốc và ngoại lệ 1232 theo CV-04. Mẫu giao diện không được dùng dữ liệu giả để tuyên bố đã định vị đúng khi CRS còn chờ xác nhận.

## 6. Header, responsive và khả năng thao tác

- Đề xuất header sticky gọn, nhưng **hành vi sticky chưa được người dùng duyệt**. Nếu chọn sticky, phải dành chỗ trong layout thay vì phủ lên bản đồ/bảng dữ liệu.
- Trang giới thiệu có thể cuộn dọc; vùng công cụ bản đồ dùng chiều cao còn lại sau header, không áp chiều cao nội dung marketing vào bản đồ.
- 4 thẻ thành viên: đề xuất 4 cột trên desktop rộng, 2 cột màn hình vừa, 1 cột điện thoại. Ba ý Tầm nhìn xếp dọc khi thiếu chỗ. Đây là mục tiêu thiết kế, chưa phải breakpoint đã kiểm thử.
- Trên màn hình nhỏ, panel bản đồ có nút mở/đóng có tên rõ; không tự biến mất chỉ vì zoom hoặc phóng to bản đồ. Không dùng nút chỉ có biểu tượng mà thiếu label/aria-label.
- Header, nút mở dự án, bảng thuộc tính, trạng thái lỗi/đang xử lý và lựa chọn file phải truy cập được bằng bàn phím và có tên cho agent đọc. Không thêm thao tác tải lên hoặc gửi dữ liệu vào website tham khảo.

## 7. Hình ảnh và nội dung còn cần cung cấp

- Tên nhóm/logo, báo cáo chuyên môn và thông tin/ảnh/liên hệ 4 thành viên vẫn chưa có nguồn được xác định trong dự án.
- Ưu tiên hình bản đồ/quy hoạch hoặc ảnh người dùng có quyền sử dụng; không tự lấy ảnh cảnh quan/logo của DC Solution cho giao diện mới. Khi chưa có ảnh, dùng khung nội dung mẫu được ghi rõ, không giả ảnh kết quả thực địa.
- Chưa xác nhận đầy đủ CRS ba dự án; ảnh bản đồ dùng làm kết quả thực phải chờ dữ liệu được kiểm chứng. Có thể làm mẫu bố cục với hình minh họa được đánh dấu riêng.

## 8. Đề nghị duyệt và bước tiếp theo

- Duyệt hướng bố cục: **header → mở đầu → giới thiệu → 3 ý Tầm nhìn → 4 dự án → 4 thành viên → thông tin cuối trang**.
- Duyệt phong cách: trắng/xanh lá, Inter, thẻ viền nhẹ, thống nhất công cụ Đánh giá quỹ đất; không sao chép nguyên website mẫu.
- Chốt header có sticky không và nguồn hình ảnh/nội dung khi làm mẫu.
- CV-06 vẫn chưa đánh dấu hoàn thành cho đến khi người dùng duyệt mẫu nhất quán. Bản xem trước đã được dựng tách riêng; sau khi duyệt mới sang CV-07 để tích hợp bộ khung/header và cấu trúc React.

Giai đoạn tham khảo chỉ đọc website và CSS; sau khi người dùng yêu cầu bắt đầu, đã thêm prototype trong `wwwroot/preview/`, không sửa app.py hoặc giao diện công cụ hiện tại. Không sao chép ảnh/mã nguồn website mẫu, gửi form liên hệ hoặc thay đổi website bên thứ ba. Máy chủ ứng dụng được khởi động ở loopback 127.0.0.1:8765 để phục vụ bản xem trước, không triển khai public.
