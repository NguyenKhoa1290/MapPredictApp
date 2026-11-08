# CV-04 — Quy tắc ghép mã và màu hiển thị

Ngày chốt: 2026-10-26, theo bốn câu trả lời trực tiếp của người dùng. Đây là **đặc tả được duyệt**, chưa phải thông báo đã triển khai bộ ghép/renderer mới.

## 1. Ghép theo phần số, trong cùng dự án

- Giữ ghép chính xác khi khóa đối chiếu duy nhất; thêm chế độ đối chiếu phần số như `TP01 ↔ 1`, `BK21 ↔ 21`. Ở chế độ này `TP001 ↔ 1` cũng có khóa số 1; luôn giữ mã gốc để truy vết.
- Chỉ đối chiếu trong cùng một dự án/bộ dữ liệu được chọn. Không ghép ô TP.HCM với Bắc Kạn hoặc Phú Quốc chỉ vì cùng phần số.
- Phần số dùng để ghép là một nhóm chữ số nguyên liên tiếp. Mã có nhiều nhóm số như `A1B2` không được tự ghép với `12` hoặc `1`. Không ghép số gần nhất, không ghép theo thứ tự dòng hoặc vị trí polygon gần nhãn nhất.
- Với số nguyên có kiểu số Excel, chuẩn bị khóa số từ giá trị số (ví dụ raw `1.0` kiểu số → khóa 1); không coi chuỗi văn bản nhiều nhóm số là mã nguyên được phép sửa tùy ý.
- Nếu `A1` và `B1` cùng cạnh tranh ghép với `1`, không tự chọn bản đầu tiên. Xung đột Y hoặc nhiều mã khác nhau cùng khóa fallback cũng không tự ghép, kể cả khi các Y tình cờ bằng nhau.
- Không lấy số mẫu cột A của Excel làm ID thay cho tên ô cột B. Không tạo `TP267` hoặc điền kết quả còn thiếu.

## 2. Giữ bảng màu của code hiện tại

Đã đối chiếu trực tiếp hai luồng tô kết quả:

- `prediction_grid.py`, hàm `predicted_dxf_grid`: `colors = {0: "#ff0000", 1: "#ffa500", 2: "#008000"}`.
- `gis.py`, hàm `predicted_geojson`: cùng bảng màu cho GeoPackage.
- Cả hai đặt `fillOpacity=0.6` cho ô có kết quả; ô không khớp có `fillOpacity=0`.
- `wwwroot/layer_manager.js`, hàm `componentKey`: tên nhóm hiện tại là `Kết quả Y = …`; giá trị chưa có ghi `Chưa có`.

Chốt sử dụng:

- **Y=0:** đỏ `#ff0000`, nhãn **Kết quả Y = 0**.
- **Y=1:** cam `#ffa500`, nhãn **Kết quả Y = 1**.
- **Y=2:** xanh lá `#008000`, nhãn **Kết quả Y = 2**.
- Độ tô nguồn **0,6**, có thể chịu độ đậm layer theo chức năng hiện có. Không đổi màu cam thành vàng.

Code được kiểm tra chưa gán các mức bằng tên nghiệp vụ như “tốt/trung bình/kém” hoặc “phù hợp/không phù hợp”. Không tự thêm các tên đó. Trường `fillColor` dự phòng xám trong dữ liệu hiện tại không có nghĩa ô thiếu được tô xám: fillOpacity của ô thiếu là 0.

## 3. Ô không xét và ô không khớp

- Bắc Kạn `BK1`–`BK20`: **không xét điểm, chỉ hiện nét lưới, không tô màu**, không tự gán Y=0.
- Các ô không có kết quả ghép duy nhất: giữ đường bao, không tô; không coi là một lớp Y.
- Bộ hiển thị dự án phải giữ trạng thái không tô khi xử lý kiểu hiển thị; không để kiểu tô mặc định biến ô không xét thành một lớp kết quả.

## 4. Phú Quốc: gộp trùng và bỏ áp dụng mã 1232

- Người dùng đồng ý **gộp các polygon trùng hình học hoàn toàn trong bộ nhớ**, trong phạm vi layer lưới đã chọn của dự án. Không ghi ngược DXF, không xóa thực thể trong file gốc.
- Lưu danh sách handle gốc của mỗi nhóm để truy vết. Không lấy ID theo thứ tự sau gộp, không làm mất mối liên hệ nguồn.
- Không gộp các polygon chỉ chồng một phần. Nếu sau gộp vẫn có nhiều nhãn/mã xung đột, không tự gán Y.
- **Mã 1232: không áp dụng kết quả, không tô; không cần cảnh báo cho người xem.** Không tạo polygon mới, không di chuyển nhãn và không chọn ô gần nhất để có chỗ tô.
- Với dữ liệu hiện tại, nhãn 1232 nằm ngoài lưới, nên “không tô” là bỏ áp dụng kết quả đó, không giả định đã tồn tại một polygon có ID 1232 để hiển thị riêng.
- Không hiện popup/banner cảnh báo hoặc cộng trường hợp 1232 vào tổng cảnh báo cho người xem. Vẫn giữ ghi nhận trong chẩn đoán nội bộ để lần sau không nhầm là đã ghép thành công. Đây không phải yêu cầu tắt mọi cảnh báo khác.

## 5. Bằng chứng đối chiếu và giới hạn nghiệm thu

- CV-02 đã xác định các mã Excel gốc, vấn đề thiếu/trùng số mẫu và kiểu số; CV-03 đã ghi số lượng nhãn, trạng thái vị trí trong/biên/ngoài, hình học trùng và kết quả bộ đọc hiện tại.
- Về **phạm vi mã số ứng viên**, TP.HCM có nhãn 1–1695 bao trùm phần số của 297 mã Excel; Bắc Kạn có nhãn 1–400 tương ứng 400 mã Excel nhưng chỉ 380 mã được xét; Phú Quốc có nhãn 1–1677 và 1.677 mã Excel, riêng 1232 không áp dụng theo quyết định trên.
- Các số đó **không phải tỷ lệ ghép hình học thành công**. Điểm chèn MTEXT trên biên chưa được giải quyết; Phú Quốc có 58 đường bao dư và nhãn ngoài. Không công bố 100% chỉ vì mã số tồn tại trong hai tập dữ liệu.
- CV-04 hoàn thành phần chốt quy tắc. Kiểm chứng tỷ lệ ghép thực sau xử lý vị trí nhãn thuộc bước triển khai CV-12/CV-14, trước khi nghiệm thu bản đồ CV-16 đến CV-18.
- Phép chiếu VN-2000 chi tiết vẫn chờ xác nhận; “9201” là thông tin người dùng nhớ chưa chắc, chưa được áp dụng. Không coi việc duyệt ghép mã là duyệt CRS.

## 6. Đầu ra và bước thực hiện tiếp

- Đặc tả có cấu trúc: [cv04_join_render_policy.json](cv04_join_render_policy.json).
- Cập nhật quy tắc vào note và nhật ký; không sửa dữ liệu nguồn hoặc thay thuật toán sản xuất trong lần chốt yêu cầu này.
- Kế tiếp **CV-05: thiết kế tổ chức backend–frontend và hợp đồng API**. Khi triển khai CV-12/CV-14, cần kiểm thử đủ ví dụ ghép hợp lệ, mơ hồ, gộp trùng bảo toàn handle, BK1–BK20 không tô và 1232 không tô/không cảnh báo người xem.
