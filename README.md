# MapPredictApp (Python)

Ứng dụng web chạy bằng Python. Mô hình `.pkl` được nạp trực tiếp trong tiến trình Python; không cần chạy dự án C#.

## Chạy trên Windows

```powershell
py -3.11 -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\run_python.bat
```

Mở `http://127.0.0.1:8765`. Nếu môi trường `venv` đã có và đã cài thư viện, chỉ cần chạy `run_python.bat`. Có thể đặt biến môi trường `PORT` để dùng cổng khác.

Tab **Dự đoán** có bảng điều khiển bên trái và bảng dữ liệu/kết quả bên phải. Chọn CSV để xem trước tối đa 200 dòng; nút **Xuất CSV** tải toàn bộ kết quả sau khi dự đoán. CSV dùng các cột `x1` đến `x9`; nếu thiếu giá trị, ứng dụng dùng `0` như luồng cũ. Có thể chọn mô hình và scaler `.pkl` riêng, hoặc dùng `rf_model_rating.pkl` và `scaler_bds.pkl` đi kèm. Kết quả có cột `Y`, lưu tại `%LOCALAPPDATA%\MapPredictApp\KetQua.csv`.

Tab **Bản đồ** ban đầu chỉ hiển thị ảnh vệ tinh Esri World Imagery, danh sách layer trống. Layer nền được tải từ một hoặc nhiều file **DXF**; **GeoPackage chỉ dùng cho layer dự đoán**, ghép với kết quả CSV. Chọn **Hệ tọa độ chung** ở thanh trên, sau đó nhấn **Hiển thị trên bản đồ**. EPSG nguồn đã chọn được áp dụng cho toàn bộ DXF và GeoPackage, kể cả khi khai báo CRS trong GeoPackage khác với lựa chọn này. Giá trị được nhớ trong trình duyệt, dùng chung giữa hai tab; đổi EPSG sẽ tự nạp lại các layer đang hiển thị. Vì vậy, dữ liệu nạp cùng nhau cần dùng chung hệ tọa độ nguồn; nếu khác nhau, hãy chuyển về cùng hệ trong QGIS trước.

Độ dịch X/Y theo mét (mặc định 0) vẫn có thể nhập riêng cho từng layer. Ứng dụng dịch hình học trong bộ nhớ, chuyển sang WGS84 để hiển thị trên nền vệ tinh và không ghi ngược vào file. Mỗi layer có công tắc hiển thị và thanh trượt độ đậm ở bảng bên trái; các giá trị này được giữ khi đổi hệ tọa độ chung. Leaflet được lưu cục bộ trong `wwwroot/leaflet`. Nhãn chữ từ DXF vẫn được ẩn.

Nền vệ tinh có thêm nhãn đường và địa danh từ Esri World Transportation / World Boundaries and Places, mặc định bật. Công tắc **Tên đường và địa danh** ở thanh bên chỉ bật/tắt nhãn nền, không ảnh hưởng layer người dùng. Lựa chọn được nhớ trong trình duyệt. Độ chi tiết phụ thuộc mức phóng to và dữ liệu của nhà cung cấp; không bảo đảm mọi đường hoặc địa giới hành chính mới đều có nhãn. Ảnh vệ tinh và nhãn nền cần kết nối Internet.

Nút **Phân tích độ dịch** ở từng DXF đọc các block lồng nhau và tổng hợp phép chèn, không sửa file gốc. Khi block còn giữ tọa độ lớn trong phạm vi EPSG đã chọn, đủ đỉnh không thẳng hàng và chỉ có phép tịnh tiến nhất quán, ứng dụng đề xuất độ dịch ngược. **Xem trước vị trí** vẽ khung phạm vi dự kiến, chưa thay đổi layer hay X/Y. **Áp dụng độ dịch** thay thế X/Y riêng cho file đó; sau đó nhấn **Hiển thị trên bản đồ** để nạp lại. Không cộng lặp độ dịch, không thay EPSG chung và không tự áp dụng cho file khác. Thay EPSG hoặc chọn lại file sẽ hủy đề xuất cũ. Nếu có xoay/co giãn, độ dịch mâu thuẫn, tọa độ trộn hoặc không còn bằng chứng gốc, ứng dụng không đề xuất áp dụng và yêu cầu điểm mốc/QGIS. Sai lệch đối chiếu đỉnh chỉ đo tính nhất quán của phép dịch, không phải độ chính xác định vị thực địa; EPSG vẫn cần người dùng xác nhận.

Ứng dụng không tự đọc layer từ đường dẫn cố định và không tự áp dụng phép dịch riêng theo tên file. Chỉ đổi EPSG sẽ không đặt đúng hình học có tọa độ CAD cục bộ. File `layer_du_doan.gpkg` đi kèm được giữ để kiểm thử, không tự xuất hiện trên bản đồ.

Kiểm tra luồng chính:

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -v
```

Điểm khởi chạy ứng dụng là `app.py`.
