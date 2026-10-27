# CV-03 — Khảo sát ba lưới DXF

Ngày kiểm tra: 2026-10-26. **Hoàn thành khảo sát nguồn; chưa xác nhận CRS hoặc duyệt phép sửa/ghép tự động.**

## Quyết định bổ sung của người dùng

Các ô Bắc Kạn `BK1`–`BK20` thiếu dữ liệu **không xét điểm**, vẫn **hiện đường lưới, không tô màu**. Không gán Y=0, không tự chạy mô hình để điền, không yêu cầu bổ sung kết quả cho các ô này. Quy tắc đã được ghi vào cấu hình tham khảo CV-02/CV-03; chưa thay mã hiển thị ứng dụng trong bước khảo sát này.

Người dùng xác nhận các lưới dùng **VN-2000**. Đã ghi nhận hệ quy chiếu người dùng cung cấp; **chưa xác nhận EPSG hoặc kinh tuyến trục/múi chiếu cho từng file**. Không đồng nhất “VN-2000” với một mã EPSG chung và không gán mã theo tên địa phương. Danh sách CRS VN-2000 trong `gis.py` hiện cũng có nhiều phép chiếu khác nhau.

Bổ sung: người dùng cho biết dùng chung phép chiếu với DXF trước, nhớ không chắc là **9201**. Đã kiểm tra `CRS.from_epsg(9201)` bằng pyproj/PROJ đang cài: trả `crs not found`. Trong [dữ liệu đơn vị chính thức của PROJ](https://raw.githubusercontent.com/OSGeo/PROJ/master/data/sql/unit_of_measure.sql), EPSG 9201 là mã đơn vị tỷ lệ `unity`, không phải bằng chứng CRS VN-2000 cho ba nguồn. Ảnh giao diện người dùng gửi trước đó hiển thị **EPSG:9208 — VN-2000 / TM-3 104-45**; đây chỉ là đầu mối kiểm tra lại, chưa được tự thay cho 9201 hoặc áp dụng cho các lưới mới. Giữ `confirmed_epsg=null` và chờ ảnh/thông số chính xác.

## Phương pháp và giới hạn

- Đọc trực tiếp cả ba file trong `Tailieuthamkhao/Giaodienfrontend/luoi/` bằng ezdxf; khảo sát modelspace, header, block/XREF, loại đối tượng, layer và nhãn. Không save DXF, không mở XREF ngoài, không sửa tọa độ.
- Các lưới được khảo sát là LWPOLYLINE kín trực tiếp trong modelspace, không cần suy ra ô từ block, POINT hoặc cao độ Z.
- Đối chiếu riêng kết quả bộ đọc hiện tại `read_dxf_grid`, rồi khảo sát bộ lọc layer/loại nhãn. Bộ lọc này mới là ứng viên có căn cứ, chưa được tích hợp vào renderer/API.
- Dùng contains/intersects trên **điểm chèn** để phát hiện vị trí cần xử lý; không coi đây là tâm chữ hiển thị. Không ghép nhãn gần nhất, không đẩy nhãn vào ô, không loại trùng hoặc đánh lại ID.
- Kiểm tra hình học trùng bằng polygon đã chuẩn hóa thứ tự đỉnh, không sửa tọa độ. Đếm cặp chồng diện tích trên `1e-5` đơn vị bản vẽ bình phương chỉ để bỏ nhiễu số trong chẩn đoán, không phải dung sai trắc địa.
- Tọa độ/kích thước bên dưới là **đơn vị bản vẽ gốc**, không mặc định đều là mét. `GEODATA` có thể lưu định nghĩa CRS/EPSG; cả ba file không có đối tượng này. [Tài liệu GeoData của ezdxf](https://ezdxf.readthedocs.io/en/stable/dxfobjects/geodata.html).
- Tìm chuỗi EPSG/VN-2000/PROJCS/GEOGCS/GEODATA trong ba file không có kết quả. Đây là chưa tìm thấy bằng chứng CRS, không phải chứng minh file không thể có thông tin địa lý gián tiếp.
- Công cụ tái lập: `tools/audit_reference_dxf.py`; cấu hình tham khảo: [cv03_dxf_sources.json](cv03_dxf_sources.json).

## 1. TP.HCM — luoi_hcm.dxf

- SHA-256 không đổi trước/sau đọc: `8c8e87c8acde6c7a9fa9b2cc02919c9d1d5c69bd23f818a51a5132c64270a1fe`.
- Modelspace: 1.696 LWPOLYLINE, 1.695 MTEXT, 208 TEXT, 1 INSERT.
- **Layer ô lưới: `DTL-1D`**, 1.695 LWPOLYLINE kín hợp lệ. Mỗi ô khoảng 20 × 20, diện tích 400 đơn vị gốc². Không có hình học trùng hoặc cặp chồng diện tích vượt ngưỡng khảo sát.
- Phạm vi riêng lưới: X từ 605297.1579945065 đến 606637.1579945066; Y từ 1201707.933088194 đến 1202567.933088194.
- **Nhãn mã: MTEXT trên layer `0`**, 1.695 mã số duy nhất, liên tiếp 1–1695. Không lấy 208 TEXT khác làm mã lưới.
- Tất cả nhãn có `attachment_point=1` (top-left), width khoảng 20, rotation=0. Điểm chèn nằm trên cạnh ô: kiểm tra strict chứa 0 nhãn duy nhất trong lòng ô, 1.695 trường hợp trên biên. Ví dụ nhãn 1, handle `1D68`, nằm ở X=605337.1579945065, Y=1202561.058678549; điểm này nằm trên cạnh trái polygon handle `16B9`.
- Không thể sửa bằng việc tùy tiện chọn một trong hai ô chạm nhãn. Cần bộ đọc hiểu khung chữ/attachment MTEXT, kiểm tra độ tin cậy và chỉ chốt mã khi duy nhất. Điểm chèn top-left không phải tâm chữ; quy định này có trong [tài liệu MTEXT của Autodesk](https://help.autodesk.com/cloudhelp/2020/ENU/AutoCAD-DXF/files/GUID-5E5DB93B-F8D3-4433-ADF7-E92E250D2BAB.htm).
- Bộ đọc không lọc hiện tại: 1.695 ô, 0 mã hợp lệ, 1.695 ambiguous. Đã tái hiện nguyên nhân, chưa thay đổi thuật toán.
- Header `$INSUNITS=6` (mét), INSBASE=(0,0,0), UCS chuẩn; không có GEODATA/EPSG. Đơn vị header không đủ xác định phép chiếu. Chưa chốt EPSG/độ dịch.
- Excel TP.HCM có 297 mã TP…, lưới có 1.695 nhãn số. Khác số lượng không tự chứng minh sai lưới: phải ghép theo mã đã xác nhận ở CV-04; ô không có kết quả không được tự tô Y=0.

## 2. Bắc Kạn — bắc kan.dxf

- SHA-256 không đổi: `b5548c2b21bbfa34569ba9eb0156934fd484a06fee2caf73e0f33704d043c086`.
- Modelspace: 1.467 LWPOLYLINE, 3.087 LINE, 2.794 TEXT, 400 MTEXT, 84 INSERT, 981 CIRCLE, 5 ARC, 1 SOLID, 2 ACAD_PROXY_ENTITY. Không coi các thực thể nền/đo cao là ô dự đoán.
- **Layer ô lưới: `00.Ranh gioi`**, đúng 400 LWPOLYLINE kín hợp lệ, không trùng hình học hoặc chồng diện tích vượt ngưỡng khảo sát. Không chọn layer `LUOI` chỉ dựa vào tên: layer đó chứa nhiều nhãn/đối tượng đo đạc và một đường bao lớn, không phải bộ 400 ô.
- Mỗi ô khoảng 20.503159 × 20, diện tích 410.063179 đơn vị gốc². Không ép thành ô 20 × 20 hoặc tự scale dữ liệu.
- Phạm vi riêng lưới: X từ 430322.6316250477 đến 430732.6948040225; Y từ 2448825.0828811 đến 2449225.082881099.
- **Nhãn mã: MTEXT trên layer `0`**, 400 mã duy nhất liên tiếp 1–400. Layer `0` còn có 20 TEXT số 241–260; không trộn chúng với MTEXT mã ô. Các layer đo cao khác cũng có nhiều số lặp.
- MTEXT đều top-left, width khoảng 20.503159, rotation=0. Sau khi lọc đúng nguồn, strict điểm chèn: **185** nhãn nằm duy nhất trong ô, **213** trên biên, **2** ngoài theo so sánh số thực chính xác.
- Hai nhãn ngoài là `361` (handle `67EDE`) và `381` (`67EF2`), khoảng cách tới lưới khoảng `1.164e-10` đơn vị gốc. Ghi nhận đây là tình huống sát biên/sai số số thực; chưa tự snap hoặc chọn ô gần nhất.
- Bộ đọc hiện tại không lọc: 405 đường bao được coi là ô, chỉ 45 mã hợp lệ, 356 ambiguous, 2 missing, 2 duplicate. Chọn đúng layer/loại nhãn loại được nền nhiễu nhưng chưa giải quyết hết MTEXT sát biên.
- Header `$INSUNITS=6` (mét), `$MEASUREMENT=0`; INSBASE=0, UCS chuẩn, không GEODATA/EPSG. `$MEASUREMENT` điều khiển hệ mẫu hatch/linetype, không phải bằng chứng để chuyển tọa độ sang inch. [Tài liệu đơn vị ezdxf](https://ezdxf.readthedocs.io/en/stable/concepts/units.html).
- Khi ghép sau này, Excel `BK1`–`BK20` thuộc nhóm không xét, chỉ hiện nét lưới như quyết định người dùng. Nhãn DXF 1–20 chưa tự coi là đã ghép BK1–BK20 cho tới khi quy tắc phần số được duyệt ở CV-04.

## 3. Phú Quốc — phú quốc.dxf

- SHA-256 không đổi: `22853f6e3701e2b116a3dbf2116af4c5e33ad0f02d801b37335f9105a74ff7cf`.
- Modelspace: 1.829 LWPOLYLINE, 1.689 TEXT, 16 MTEXT, 1.677 POINT, 24 LINE, 19 INSERT, 59 HATCH, 36 ARC.
- **Layer ô lưới: `Docao`**, 1.734 LWPOLYLINE kín hợp lệ, mỗi ô khoảng 20 × 20, diện tích 400 đơn vị gốc². Không lấy các polygon hiện trạng/ranh quy hoạch ở layer khác vào lưới dự đoán.
- Phạm vi riêng lưới: X từ 444246.9646409321 đến 444906.9646409322; Y từ 1117726.938829461 đến 1119586.938829461.
- Chỉ có **1.676 hình học khác nhau**: 58 nhóm hình học trùng, mỗi nhóm thêm một đường bao, tổng 58 đường bao dư. Có 75 cặp chồng diện tích vượt ngưỡng, gồm 58 cặp trùng toàn bộ và 17 cặp chồng nhỏ không trùng toàn bộ. Chưa xóa/gộp hoặc sửa các đường bao này.
- **Nhãn mã: TEXT số trên layer `0`**, 1.677 mã duy nhất liên tiếp 1–1677. POINT có thể chứa Z nhưng không dùng Z để tạo ID.
- Strict điểm chèn trên lưới đã lọc: 1.618 nhãn duy nhất trong lòng ô, 58 gặp hình học trùng, 1 ngoài lưới. Có 116 thực thể polygon chưa có nhãn chứa duy nhất trong phép kiểm tra này; số này bao gồm các bản trùng, không phải 116 mã ô đất chắc chắn bị mất.
- Nhãn **1232**, handle **`2D74`**, tại (444828.9990884083, 1118274.460080197), nằm ngoài các polygon `Docao`; khoảng cách nhỏ nhất khoảng **2.0344474762 đơn vị gốc**. Không đủ căn cứ gán cho polygon gần nhất, tự tạo ô mới hoặc coi đây là lỗi CRS.
- Bộ đọc không lọc hiện tại: 1.801 polygon, 131 mã hợp lệ, 1.659 ambiguous và 11 missing; số ô lớn hơn lưới `Docao` do lẫn đường bao nền.
- Header `$INSUNITS=4` là **mm**, trong khi tọa độ/kích thước gốc vẫn như trên. Không tự nhân/chia 1000: cần người dùng xác nhận đơn vị thực dùng để định vị và EPSG. [Tài liệu đơn vị ezdxf](https://ezdxf.readthedocs.io/en/stable/concepts/units.html).
- Không GEODATA/EPSG. Có XREF `.\\SR62HA_XREF_NENDIAHINHTTHCPQ.dwg`, block không có thực thể nhúng; file DWG đó chưa thấy trong thư mục tham khảo hiện có. Lưới/nhãn khảo sát nằm trực tiếp trong DXF nên vẫn đọc được; không hứa nền XREF sẽ hiển thị đầy đủ.

## Kết luận và việc cần chốt

1. Đủ căn cứ chọn layer/loại thực thể cho khảo sát; chưa đủ căn cứ dùng bộ đọc hiện tại để tự tô kết quả ba dự án.
2. Cần xử lý MTEXT dựa trên attachment/khung chữ, chỉ nhận kết quả không mơ hồ. Khung MTEXT tính bằng thư viện không luôn chính xác như CAD, nên cần test và xem mẫu thực tế. [Giới hạn bbox của ezdxf](https://ezdxf.readthedocs.io/en/stable/disassemble.html).
3. Cập nhật theo CV-04: người dùng đã duyệt gộp hình học trùng hoàn toàn trong bộ nhớ, giữ DXF gốc; mã 1232 không áp dụng kết quả và không hiện cảnh báo người xem, vẫn giữ trace nội bộ. Chưa triển khai các thay đổi này; không suy ra vị trí mã từ thứ tự polygon hoặc mã số lân cận. Xem [đặc tả CV-04](CV04_QUY_TAC_GHEP_VA_MAU.md).
4. **Đã xác nhận VN-2000 theo người dùng, nhưng chưa xác nhận EPSG/phép chiếu, đơn vị thực và độ dịch cho từng dự án.** Cần thông số chi tiết từ QGIS/CAD, file dự án QGIS hoặc điểm mốc. Đã hỏi bổ sung mã EPSG hoặc kinh tuyến trục/múi chiếu, có thể cung cấp ảnh khai báo. Không mặc định EPSG của dữ liệu Yên Bái hoặc tự tìm phép dịch để ép vào tên địa phương.
5. Bổ sung các yêu cầu này vào CV-04/CV-14. CV-03 hoàn thành phần khảo sát theo tiêu chí “CRS đã xác nhận hoặc vướng mắc cụ thể”; trạng thái định vị vẫn chưa được duyệt.

## Tái kiểm tra

```powershell
.\venv\Scripts\python.exe tools\audit_reference_dxf.py
.\venv\Scripts\python.exe -m unittest tests.test_reference_dxf_audit tests.test_reference_excel_audit -v
```

13 kiểm thử đạt (5 DXF + 8 Excel), kiểm tra nhãn trong ô/trên biên/ngoài rất nhỏ, hình học trùng, ô không có nhãn, cùng các kiểm tra Excel trước đó. Công cụ nguồn xác nhận hash DXF không đổi và giữ `applied_transform=null`. Không gọi API hoặc sửa app.py/renderer trong bước này.
