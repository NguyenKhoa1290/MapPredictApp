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

Tab **Bản đồ** ở lần đầu (chưa có bản lưu) chỉ hiển thị ảnh vệ tinh Esri World Imagery, danh sách layer trống. Sau khi làm việc, reload khôi phục phiên đã lưu trong trình duyệt. Layer nền dùng một hoặc nhiều file **DXF**; mục **Lưới dự đoán · DXF / GeoPackage** nhận cả **DXF** và **GPKG** để ghép kết quả CSV. DXF lưới có thể xem đường ô khi chưa có kết quả; GeoPackage vẫn yêu cầu kết quả dự đoán. Chọn **Hệ tọa độ chung** ở thanh trên, sau đó nhấn **Hiển thị trên bản đồ**. EPSG nguồn áp dụng cho toàn bộ DXF và GeoPackage, kể cả khi khai báo CRS trong GeoPackage khác lựa chọn. Giá trị được nhớ trong trình duyệt, dùng chung giữa hai tab; đổi EPSG sẽ tự nạp lại các layer đang hiển thị. Dữ liệu nạp cùng nhau cần dùng chung hệ tọa độ nguồn; nếu khác nhau, hãy chuyển về cùng hệ trong QGIS trước.

Độ dịch X/Y theo mét (mặc định 0) vẫn có thể nhập riêng cho từng layer. Ứng dụng dịch hình học trong bộ nhớ, chuyển sang WGS84 để hiển thị trên nền vệ tinh và không ghi ngược vào file. Mỗi layer có công tắc hiển thị và thanh trượt độ đậm ở bảng bên trái; các giá trị này được giữ khi đổi hệ tọa độ chung. Leaflet được lưu cục bộ trong `wwwroot/leaflet`. Nhãn chữ từ DXF vẫn được ẩn.

Chọn **Nền bản đồ** bên trái để đổi giữa **Vệ tinh · Esri** và **Đường phố / giao thông · OpenStreetMap** (đường, địa danh; không có ùn tắc trực tiếp). Ghi nhớ lựa chọn trong trình duyệt. Đổi nền không đổi vị trí, zoom, hệ tọa độ chung hoặc ký hiệu/layer đã nạp; không gọi lại API chuyển tọa độ. Lần đầu dùng vệ tinh và danh sách layer người dùng vẫn trống.

Nền vệ tinh có thêm nhãn đường và địa danh từ Esri World Transportation / World Boundaries and Places, mặc định bật. Công tắc **Tên đường và địa danh** chỉ áp dụng cho vệ tinh; nền đường phố đã có nhãn riêng nên không chồng nhãn Esri. Ghi nhớ lựa chọn bật/tắt khi chuyển qua lại. Không bật nhãn chữ DXF. Chi tiết phụ thuộc nhà cung cấp; không bảo đảm mọi đường hoặc địa giới mới đều có nhãn. Các nền cần Internet. OpenStreetMap dùng URL HTTPS chính thức, attribution hiển thị trên bản đồ và bộ nhớ đệm HTTP mặc định của trình duyệt; không tải trước/offline. Khi triển khai nhiều người dùng cần đánh giá [chính sách máy chủ tile OSM](https://operations.osmfoundation.org/policies/tiles/).

Cho phép zoom đến 22 để xem vector. Ảnh raster yêu cầu tối đa zoom 19 (nhãn Esri 18), sau đó phóng lớn, không tạo thêm chi tiết ảnh. Với vệ tinh/nhãn Esri, dùng [`blankTile=false`](https://developers.arcgis.com/rest/services-reference/enterprise/map-tile/) để phát hiện ảnh thiếu thay vì hiện ô xám “Map data not yet available”; thử tối đa 4 mức thấp hơn và cắt đúng phần ảnh cha tương ứng. Mỗi ô độc lập, không đổi vị trí layer hoặc giảm zoom cả bản đồ. Hủy retry khi ô rời màn hình/đổi nền. Nếu vẫn lỗi tải nền, thông báo kiểm tra Internet/đổi nền; không xóa vector. Dùng [GridLayer tùy biến của Leaflet](https://leafletjs.com/examples/extending-2-layers/), giữ lưới ở zoom hiển thị và phóng/cắt ảnh trong từng ô; không phụ thuộc phép scale 3D hay `maxNativeZoom` mặc định (không scale khi `L_DISABLE_3D=true`), giữ cách chống tile tràn che thanh bên của ứng dụng.

Nút **Phân tích độ dịch** ở từng DXF đọc các block lồng nhau và tổng hợp phép chèn, không sửa file gốc. Khi block còn giữ tọa độ lớn trong phạm vi EPSG đã chọn, đủ đỉnh không thẳng hàng và chỉ có phép tịnh tiến nhất quán, ứng dụng đề xuất độ dịch ngược. **Xem trước vị trí** vẽ khung phạm vi dự kiến, chưa thay đổi layer hay X/Y. **Áp dụng độ dịch** thay thế X/Y riêng cho file đó; sau đó nhấn **Hiển thị trên bản đồ** để nạp lại. Không cộng lặp độ dịch, không thay EPSG chung và không tự áp dụng cho file khác. Thay EPSG hoặc chọn lại file sẽ hủy đề xuất cũ. Nếu có xoay/co giãn, độ dịch mâu thuẫn, tọa độ trộn hoặc không còn bằng chứng gốc, ứng dụng không đề xuất áp dụng và yêu cầu điểm mốc/QGIS. Sai lệch đối chiếu đỉnh chỉ đo tính nhất quán của phép dịch, không phải độ chính xác định vị thực địa; EPSG vẫn cần người dùng xác nhận.

Ứng dụng không tự đọc layer từ đường dẫn cố định và không tự áp dụng phép dịch riêng theo tên file. Chỉ đổi EPSG sẽ không đặt đúng hình học có tọa độ CAD cục bộ. File `layer_du_doan.gpkg` đi kèm được giữ để kiểm thử, không tự xuất hiện trên bản đồ.

Kiểm tra luồng chính:

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -v
node --test tests/color_adjustments.test.cjs
node --test tests/basemaps.test.cjs
```

Điểm khởi chạy ứng dụng là `app.py`.

## Quản lý nhiều layer và ký hiệu

**Hiệu chỉnh màu layer** thay thế phần tô màu hàng loạt theo giá trị thuộc tính. Các thanh **Hue** (−180° đến 180°), **Contrast**, **Brightness**, **Saturation** (0–200%) và **Invert — đảo ngược màu** (0–100%) áp dụng ngay cho nét, vùng tô và điểm của riêng layer đang chọn, không phụ thuộc phạm vi thành phần trong **Áp dụng cho**. Nền vệ tinh, nhãn địa danh, layer khác, độ dày và độ trong suốt không đổi. Hiệu chỉnh từ màu nguồn hoặc màu tự chọn mỗi lần (không cộng dồn sai lệch khi kéo thanh), có bộ nhớ đệm cho các màu trùng nhau. Dùng các phép biến đổi màu sRGB theo [W3C Filter Effects](https://www.w3.org/TR/filter-effects-1/#FilterFunctions), theo thứ tự hue → saturation → brightness → contrast → invert, không đặt bộ lọc lên toàn bộ canvas bản đồ. Invert 0% giữ nguyên; 100% đảo màu (đen ↔ trắng), 50% cho màu xám trung tính. Hue/saturation không đổi màu đen/trắng/xám; giảm contrast để làm nhạt màu đen. **Đặt lại hiệu chỉnh** trở về 0°/100%/100%/100% và Invert 0%, giữ nguyên màu tự chọn, bật/tắt và độ đậm layer. **Khôi phục kiểu nguồn** cho cả layer đặt lại cả hiệu chỉnh lẫn ký hiệu, còn cho một thành phần chỉ đặt lại ký hiệu thành phần đó. Giữ các giá trị khi thêm/gỡ file, đổi EPSG và sau reload thông qua bản lưu trình duyệt. Không sửa thuộc tính hay file gốc.

- Có thể chọn nhiều DXF hoặc nhiều GeoPackage cùng lúc, hoặc thêm nhiều đợt. Danh sách file được tự lưu để khôi phục sau reload; cùng tên/kích thước/thời gian sửa không bị thêm trùng. Gỡ file bỏ riêng file đó khỏi danh sách, bản đồ và bản lưu tiếp theo, không xóa file gốc. Nhấn **Hiển thị trên bản đồ** để nạp/cập nhật danh sách. Lần đầu chưa có bản lưu thì không có layer người dùng.
- Lưới DXF/GPKG dùng chung CSV và độ dịch dự đoán. Khi trộn hai định dạng hoặc không có cột chung, chọn cột ghép riêng ở từng file; các file cùng định dạng có cột chung vẫn dùng bộ chọn chung. Cột ghép GPKG phải có trong mọi bảng hình học của file đó. Tất cả bảng hình học GPKG được đọc, không chỉ bảng đầu. Giữ thuộc tính nguồn để kiểm tra đối tượng.
- Bấm tên layer bên trái hoặc đối tượng trên bản đồ để mở bảng thông tin bên phải. Có số lượng, loại hình học, các thành phần CAD (hoặc nhóm kết quả Y), màu nguồn, bảng thuộc tính có tìm kiếm và phân trang 50 dòng; không cắt tổng số đối tượng theo số dòng bảng. Bấm số thứ tự để xem thuộc tính đầy đủ và đi đến đối tượng.
- Chỉnh màu nét, màu tô, độ dày nét, kiểu nét, độ đậm vùng tô và cỡ điểm cho toàn bộ layer hoặc từng thành phần. Mỗi thành phần có bật/tắt và bảng màu riêng; thiết lập riêng ưu tiên thiết lập chung. **Khôi phục kiểu nguồn** cho toàn bộ layer xóa các ghi đè ký hiệu, còn áp dụng cho một thành phần chỉ xóa ghi đè của thành phần đó. Màu/ký hiệu/độ đậm và trạng thái ẩn được giữ khi thêm/gỡ file, đổi EPSG và sau reload thông qua bản lưu trình duyệt.
- **Xem tất cả layer** phóng vừa các layer đang bật; **Đến layer** đi đến toàn bộ phạm vi một layer. Phạm vi không bị giới hạn theo bảng thuộc tính hay phần đang nhìn thấy trên màn hình.
- DXF bổ sung POINT, ARC, CIRCLE, ELLIPSE, SPLINE, polyline có cung, SOLID/3DFACE và vùng tô HATCH (giữ lỗ). Đường cong được lấy mẫu với sai số xấp xỉ 0,1 đơn vị bản vẽ để hiển thị, không dùng làm dữ liệu đo đạc. Đọc màu ACI/True Color và kế thừa layer/màu từ block. Nhãn TEXT/MTEXT vẫn ẩn theo cấu hình trước. Không bảo đảm mọi đối tượng CAD đều được hỗ trợ: loại chưa đọc được và lỗi hình học được báo trong bảng thông tin, không âm thầm coi là đã hiển thị đầy đủ. Mọi tùy chỉnh chỉ ảnh hưởng trình xem, không ghi vào file DXF/GPKG gốc.

## Tự lưu phiên làm việc khi reload

Thanh trên cùng báo **Đã lưu trên trình duyệt** sau khi tự lưu, hoặc bấm **Lưu ngay** trước khi reload. Tự lưu được gộp sau khoảng 180 ms không có thao tác mới; chỉ thông báo thành công sau khi giao dịch lưu hoàn tất. Nếu đóng/reload ngay khi còn báo chưa lưu/đang lưu, thay đổi cuối cùng chưa được bảo đảm. Khôi phục dùng bản lưu hoàn chỉnh cuối cùng, không tự nạp file từ đường dẫn cố định.

- Nhớ file DXF/GPKG, CSV đầu vào/kết quả và mô hình/scaler người dùng đã chọn; độ dịch X/Y, hệ tọa độ, cột ghép và metadata lưới.
- Nhớ GeoJSON đã hiển thị, màu/ký hiệu toàn layer và từng thành phần, hue/contrast/brightness/saturation/invert, bật/tắt và độ đậm; không đọc/chuyển lại toàn bộ CAD khi reload.
- Nhớ tâm/zoom, nền và nhãn, tab đang mở, layer/thành phần đang chọn, bộ lọc và trang thuộc tính, bảng dữ liệu/kết quả dự đoán. Không lưu trạng thái đang chạy, khung xem trước hay đề xuất phân tích độ dịch chưa áp dụng.
- Khôi phục không POST lại `/api/map`, không tự chạy mô hình và không ghi kết quả lên máy chủ. Nếu người dùng chủ động cập nhật bản đồ sau khôi phục, kết quả dự đoán đã lưu được gửi kèm khi chưa chọn CSV kết quả riêng. Xuất CSV dùng đúng bảng kết quả hiện tại, kể cả bảng khôi phục, không tải nhầm kết quả khác trên máy chủ.

Dùng [IndexedDB để lưu Blob/file và dữ liệu có cấu trúc](https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API), không nhét GeoJSON lớn vào localStorage. Dữ liệu lớn chỉ ghi khi thay đổi; chỉnh thanh trượt không ghi lại toàn bộ file/GeoJSON. Snapshot và các asset ghi trong cùng giao dịch; lỗi lưu không thay bản tốt trước đó, file/layer gỡ khỏi phiên không xuất hiện trở lại. Có kiểm tra phiên bản để tab cũ không ghi đè phiên mới do tab khác lưu; khi báo xung đột cần tải lại tab cũ.

Bản lưu chỉ thuộc **trình duyệt/profile và địa chỉ đang dùng**, ví dụ `http://127.0.0.1:8765`; đổi sang `localhost`, cổng khác hay trình duyệt khác không dùng chung. Đây không phải bản sao lưu độc lập hay đồng bộ nhiều máy. Xóa dữ liệu trang web, đóng phiên ẩn danh hoặc cơ chế [giới hạn/thu hồi dung lượng của trình duyệt](https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria) có thể làm mất bản lưu. Ảnh nền không được tải/cache offline hàng loạt; vẫn cần mạng để tải tile. File gốc không bị sửa. Lần cập nhật đầu tiên cần khởi động lại ứng dụng/tải phiên bản trang mới; phiên trang cũ chưa có tính năng tự lưu nên cần nạp file lại một lần.

Kiểm thử trình duyệt ở `tests/workspace.browser.cjs` cần Playwright và Chrome, đặt `PLAYWRIGHT_MODULE` nếu Playwright không nằm trong node_modules dự án. `WORKSPACE_TEST_URL` bắt buộc trỏ tới Flask **kiểm thử với RESULT_CSV/DATA_DIR tách biệt**, vì bài kiểm thử chủ động chạy dự đoán và tải CSV; không dùng máy chủ đang chứa kết quả thật. Kiểm tra khôi phục sau reload/tab mới, sửa file/ghép lại, tự lưu, gỡ layer, lỗi quota, giao dịch rollback, xung đột nhiều tab và bản lưu thiếu asset.

## Lưới dự đoán DXF

Chọn DXF trong **Lưới dự đoán**, không phải ô **Thêm layer nền**. Đọc LWPOLYLINE/POLYLINE kín trực tiếp trong modelspace thành Polygon để tô kết quả; không tự polygonize LINE rời, suy đoán block hay coi HATCH/POINT là ô. Polyline hở, đường bao lỗi và loại hình học không dùng được được báo cảnh báo. TEXT/MTEXT không vẽ nhãn, chỉ đọc chuỗi để gắn mã cho ô chứa duy nhất nhãn đó. [Polyline kín của ezdxf](https://ezdxf.readthedocs.io/en/stable/dxfentities/lwpolyline.html) và [STRtree của Shapely](https://shapely.readthedocs.io/en/2.1.2/strtree.html) được dùng để đọc đường bao và đối chiếu vị trí nhãn.

Các trường ghép hỗ trợ là **grid_id** (suy ra từ nhãn trong ô), **handle** (mã đối tượng CAD), **layer** (tên lớp CAD). `grid_id` không phải thuộc tính `tenlodat` gốc và không được đổi tên giả thành `tenlodat`. Không ghép theo thứ tự entity, thứ tự dòng CSV, nhãn gần nhất hoặc cao độ Z của POINT. Không tự thêm tiền tố như `YB`, bỏ số 0 đầu hay chuyển mã `1.0` thành `1`. Mã chỉ bỏ khoảng trắng đầu/cuối và không phân biệt hoa/thường. Ví dụ: nếu CSV có cột `tenlodat` với các giá trị `1`, `2`, … trùng nhãn, chọn **grid_id ↔ tenlodat**; nếu mã khác thì cần bảng đối chiếu hoặc chỉnh dữ liệu trong QGIS, không suy đoán tương ứng.

Ô không có nhãn, có nhiều nhãn, nhãn trên biên/thuộc nhiều ô hoặc mã bị trùng vẫn hiển thị nhưng không tự gán kết quả bằng `grid_id`. Inspector giữ `id_status`, `id_source`, `id_text_handle`, `handle` và mã đã đọc để kiểm tra. CSV có cùng mã nhưng Y khác nhau bị từ chối; Y không thuộc 0/1/2 được bỏ qua và báo số dòng lỗi. Các ô không khớp vẫn giữ đường bao, không tô nhầm; thông báo số ô khớp/tổng số sau khi tải. Không sửa DXF gốc. Kết quả CSV tải lên chỉ được lưu sau khi toàn bộ layer hợp lệ, tránh thay kết quả đã lưu khi nhập lỗi.
