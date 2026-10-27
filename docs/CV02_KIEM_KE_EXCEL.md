# CV-02 — Kiểm kê Excel của ba dự án

Ngày kiểm tra: 2026-10-26. Trạng thái: **hoàn thành kiểm kê**, không đồng nghĩa dữ liệu đã sẵn sàng để tô lên lưới.

## Nguồn và cách kiểm tra

- Nguồn: [File ex.xlsx](../Tailieuthamkhao/Giaodienfrontend/luoi/File%20ex.xlsx).
- SHA-256 trước và sau khi đọc: `b7373684cb05ee3dc91308f0fd97523e714e785fbd6ad7e5a2a6aa925ad48b0f`; file không thay đổi.
- Đọc toàn bộ ô có giá trị/công thức của đúng ba sheet `data tp. HCM`, `bắc kan`, `data Phú Quốc`; không lấy dữ liệu huấn luyện hoặc Yên Bái.
- Dùng ZIP/XML chuẩn của Python để giữ kiểu ô, mã gốc, công thức và giá trị cache. Không chạy Excel, không tính lại công thức, không chạy AI, không sửa workbook. Artifact Tool không có ở vị trí dependency được cung cấp trong môi trường này.
- Công cụ tái kiểm tra: `tools/audit_reference_excel.py`, chỉ xuất JSON ra stdout. Phạm vi dòng là phạm vi của phiên bản nguồn trên, không phải bộ tự nhận diện mọi workbook. Nguồn thay đổi cần kiểm kê lại.
- Định nghĩa đọc cho từng sheet: [cv02_excel_sources.json](cv02_excel_sources.json), là cấu hình tham khảo cho CV-11, chưa được nối vào API ứng dụng.

## Quy tắc đọc chung đã xác định

- Hàng 1–3 là tiêu đề nhiều tầng; dữ liệu bắt đầu ở hàng 4, không dùng hàng 1 làm header CSV trực tiếp.
- Cột A là **Mẫu / số thứ tự mẫu**, không được tự coi là ID ô đất.
- Cột B là **TÊN Ô ĐẤT**, là nguồn mã để khảo sát ghép ở CV-03/CV-04.
- Cột C, D, E, F, G, H, I, J, K lần lượt là **x1 đến x9**; L là **Y**. Không dịch cột theo vị trí các sheet khác.
- Phân loại Y hợp lệ cho kiểm kê: số nguyên 0, 1, 2 theo mô tả ở hàng 3. Chưa suy diễn tên hoặc bảng màu cho các lớp.
- Ô trống không bằng số 0. Không áp dụng cách điền thiếu bằng 0 của luồng dự đoán cũ cho dữ liệu dự án cố định.
- Giữ tên/mã gốc và số dòng nguồn để truy vết. Không ghép theo thứ tự dòng, tự bù mã bị thiếu hoặc tự lấy mã A thay B.

## TP.HCM

- Sheet: `data tp. HCM`; dữ liệu **A4:L300**, tổng **297 dòng**.
- B có 297 mã văn bản không thiếu, không trùng sau khi bỏ khoảng trắng đầu/cuối và không phân biệt hoa/thường. Không có trùng phần số trong phạm vi sheet.
- Mã trải từ `TP01` đến `TP298`, **không có `TP267`**. Đây là khoảng trống trong nguồn, chưa thể kết luận lưới DXF có thiếu ô tương ứng hay không.
- Ví dụ: B4=`TP01`, A4=1, L4=0; B270=`TP268` nhưng A270=267; B300=`TP298` nhưng A300=297. Có **31 dòng** số mẫu A khác phần số của tên B.
- Tất cả 297 dòng đủ x1–x9 dạng số và Y hợp lệ; không có lỗi ô Excel hay công thức trong vùng dữ liệu.
- Phân bố tính trực tiếp từ **L4:L300**: **Y=0: 135; Y=1: 162; Y=2: 0**.
- Loại khỏi dữ liệu ô đất các dòng tổng kết **301–303**. M301 là ghi chú tên sheet, không phải mã ô.
- Phát hiện lỗi tổng kết: L302 dùng `COUNTIF(L5:L301,0)`, giá trị cache 134. Phạm vi này bỏ qua L4=0 nên thiếu một dòng so với 135 trong vùng dữ liệu thật. L301 dùng `COUNTIF(L4:L300,1)` (cache 162); L303 dùng `COUNTIF(L6:L302,2)` (cache 0). Không lấy các dòng COUNTIF làm kết quả ô đất và không dùng tổng kết cache thay cho việc đếm vùng dữ liệu.
- Chưa sửa công thức hoặc tạo thêm `TP267`.

## Bắc Kạn

- Sheet chính xác: `bắc kan`; dữ liệu **A4:L403**, tổng **400 dòng**, mã `BK1` đến `BK400`.
- B có 400 mã văn bản không thiếu, không trùng; không có trùng phần số trong phạm vi sheet.
- **20 dòng 4–23 (`BK1`–`BK20`) chỉ có số mẫu và tên ô; thiếu toàn bộ C:L, tức x1–x9 và Y.** Mỗi cột x thiếu 20 giá trị, tổng 180 ô x bị thiếu; thêm 20 ô Y bị thiếu. Không phải Y=0.
- **380 dòng 24–403 (`BK21`–`BK400`) đủ x1–x9 và Y hợp lệ**. Phân bố từ L4:L403, chỉ tính ô có Y: **Y=0: 0; Y=1: 12; Y=2: 368**.
- Không có Y khác 0/1/2 trong các ô đã có kết quả, không có lỗi ô Excel/công thức trong vùng dữ liệu.
- Cột A bị đánh số lại từ 1 ở hàng 24: A4=1/B4=`BK1`; A24=1/B24=`BK21`; A403=380/B403=`BK400`. Số mẫu **1–20 xuất hiện hai lần mỗi số**; có 380 dòng A khác phần số của B. Không dùng A làm khóa ghép mặc định.
- Giá trị x6 (H24:H403) đều bằng 0. Đây là số 0 có thật trong nguồn, không phải ô trống; chưa có đặc tả để kết luận là giá trị sai nghiệp vụ.
- Loại khỏi dữ liệu ô đất các dòng tổng kết **404–406**. Công thức: L404=`COUNTIF(L4:L403,1)` cache 12; L405=`COUNTIF(L4:L404,0)` cache 0; L406=`COUNTIF(L4:L405,2)` cache 368. Hai công thức cuối mở rộng sang vùng tổng kết; không dùng các giá trị này thay cho việc đọc từng Y.
- Người dùng đã xác nhận: `BK1`–`BK20` **không xét điểm**, vẫn **hiện đường lưới, không tô màu**. Không yêu cầu bổ sung kết quả cho các ô này, không gán Y=0, không xóa khỏi lưới hoặc tự chạy dự đoán để điền. Quy tắc sẽ được triển khai ở luồng hiển thị dự án; lần khảo sát này chỉ ghi quyết định, chưa sửa renderer.

## Phú Quốc

- Sheet: `data Phú Quốc`; dữ liệu **A4:L1680**, tổng **1.677 dòng**.
- B có 1.677 mã **kiểu số Excel**, các số nguyên liên tiếp từ 1 đến 1677; không thiếu/trùng mã, không thiếu số trong dãy. A và B trùng giá trị trong toàn bộ vùng dữ liệu.
- Ví dụ: B4 có raw OOXML `1.0`, kiểu `n`, giá trị số 1; B1680 có raw `1677.0`, kiểu `n`, giá trị số 1677. Đây không phải chuỗi văn bản có hai cụm mã `1` và `0`.
- Tất cả 1.677 dòng đủ x1–x9 và Y hợp lệ; không có lỗi ô Excel hay công thức. Không có dòng tổng kết có giá trị sau vùng dữ liệu.
- Phân bố từ **L4:L1680**: **Y=0: 90; Y=1: 57; Y=2: 1.530**.
- Khi chuẩn bị khóa đọc Excel, có thể biểu diễn số nguyên kiểu số thành `1`, `2`, … và vẫn giữ giá trị/kiểu gốc để truy vết. Không áp dụng chuyển đổi này vô điều kiện cho mã văn bản như `001` hoặc `1.0`; quy tắc ghép với DXF vẫn chờ CV-04.

## Kết luận cho các bước sau

- Có **2.374 dòng mang mã ô** ở ba dự án; **2.354 dòng đủ dữ liệu x1–x9 và Y hợp lệ**, 20 dòng còn lại thuộc Bắc Kạn và thiếu dữ liệu. Không có mã B thiếu hoặc trùng trong từng sheet.
- Có 6 công thức COUNTIF ở vùng tổng kết, không công thức trong vùng dữ liệu. Công cụ đọc giá trị lưu, không bảo đảm đã tính lại công thức trong Excel; các số phân bố nêu trên được đếm độc lập từ các ô Y của từng dòng.
- Thiếu `TP267`, số mẫu Bắc Kạn trùng và kiểu số Phú Quốc là lý do phải dùng khóa có nguồn gốc và kiểm tra mơ hồ, không ghép theo chỉ số hàng. Phần số lặp giữa các địa phương không được dùng làm khóa chung toàn hệ thống.
- Chưa xác nhận vị trí, CRS hoặc số lượng polygon của các DXF; chưa tuyên bố tỷ lệ ghép Excel–lưới. Đó là CV-03/CV-04.
- Chưa chốt ý nghĩa và màu của Y; không kết luận giá trị x=0 là sai khi chưa có quy định nghiệp vụ.
- CV-02 hoàn thành vì đã kiểm kê và định vị được vấn đề; **không đánh dấu dữ liệu Bắc Kạn là đầy đủ**.

## Kiểm tra và tái lập

Chạy tại thư mục dự án:

```powershell
.\venv\Scripts\python.exe tools\audit_reference_excel.py
.\venv\Scripts\python.exe -m unittest tests.test_reference_excel_audit -v
```

Bộ kiểm thử dùng dữ liệu giả trong bộ nhớ để kiểm tra ô 0/ô trống, mã số/văn bản, trùng mã/trùng số mẫu, Y và tiêu chí không hợp lệ, công thức thiếu cache và loại dòng tổng kết. Không gọi API, không ghi file kết quả người dùng. Chi tiết JSON có đủ số dòng, ô lỗi và giá trị/công thức gốc để tái kiểm tra.
