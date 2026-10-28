# Note công việc — thiết kế hệ thống mới

## Trạng thái mới nhất ngày 2026-10-27

- Theo yêu cầu mới đã triển khai Docker Compose blue/green và tunnel riêng trên máy hiện tại tại danhgiaquyhoach.top, hướng dẫn tại [DOCKER_DEPLOYMENT.md](docs/DOCKER_DEPLOYMENT.md)
- Token và cấu hình riêng nằm ngoài Git, model và nguồn dự án mount chỉ đọc, cổng local 8765 được giữ cố định

- Đã đưa mã nguồn lên origin GitHub, CI Windows/Ubuntu và job phân phối ZIP đều đạt ở lần chạy [40472565755](https://github.com/NguyenKhoa1290/MapPredictApp/actions/runs/40472565755), chưa tự triển khai lên hosting, hướng dẫn tại [GITHUB_ACTIONS.md](docs/GITHUB_ACTIONS.md)

- Đã dọn 51 file không còn dùng ra thư mục lưu trữ ngoài dự án, giữ nhật ký, tài liệu và dữ liệu gốc, chi tiết tại [CLEANUP_20261027.md](docs/CLEANUP_20261027.md)

- Giao diện Giới thiệu, bốn dự án và bốn thành viên đã có, nội dung và ảnh thay qua cấu hình hoặc wwwroot/image
- CV-21 đã nối vào công cụ legacy theo quyết định giữ công cụ hiện tại, có chọn cách ghép, xem trước và áp dụng riêng
- CV-22 cho công cụ chính giữ database legacy và bổ sung lưu cách ghép, không tiếp tục di chuyển GIS sang phiên React CSV riêng
- Đã kiểm tra hồi quy API, mô hình, lưới và lưu phiên ở mức kiểm thử tự động, các checkbox nghiệm thu trực quan hoặc vị trí bản đồ bên dưới chưa tự đánh dấu
- Vị trí ba dự án vẫn chờ người dùng chốt, không mặc định xem thử EPSG:9208 là đã xác nhận
- Đã chốt phần Đánh giá dùng không cần đăng nhập, người dùng chưa có hosting và ưu tiên hoàn thiện bản local trước, phần public cùng các quyết định môi trường và hạn mức để sau
- Chatbot đã được yêu cầu và duyệt phạm vi dùng server Gemini, xem trước rồi áp dụng, triển khai tại CV-26 và CV-27
- Chi tiết luồng mới tại [CV21_GHEP_KET_QUA.md](docs/CV21_GHEP_KET_QUA.md)

Cập nhật: 2026-10-26. Đây là kế hoạch làm lần lượt, chưa phải các chức năng đã triển khai.

## 1. Cách cùng thực hiện

- Mỗi lần chọn một mã việc, ví dụ “Làm CV-01”. Chỉ triển khai phạm vi đó và các phụ thuộc đã thống nhất.
- `[ ]` là chưa làm, `[x]` là đã hoàn thành và kiểm tra. Nếu đang làm hoặc bị chặn, ghi lý do ngay dưới mục tương ứng.
- Mỗi việc kết thúc bằng: thay đổi gì, kiểm thử gì, còn thiếu gì; cập nhật note và nhật ký.
- Không xóa hoặc viết lại toàn bộ hệ thống cũ. Giữ dữ liệu gốc, mô hình và bản lưu trình duyệt; có phương án chuyển đổi trước khi thay cấu trúc lưu.
- Không tự bịa thông tin nhóm, thành viên, thành tích, hệ tọa độ, mã ghép hoặc ý nghĩa các mức điểm.

## 2. Tài liệu và kết quả đọc ban đầu

- Yêu cầu chính: [yeucau.txt](Tailieuthamkhao/Giaodienfrontend/yeucau.txt), đã đọc toàn bộ.
- Link tham khảo: [link.txt](Tailieuthamkhao/Giaodienfrontend/link.txt), trỏ tới https://dcsolution.vn/. Các lần đầu lỗi tải; lần thử lại ngày 2026-10-26 đã đọc được trang chủ, trang Sứ mệnh và Dự án, HTTP trang chủ 200. Đã kiểm tra nội dung/HTML, chưa xác nhận bằng ảnh chụp toàn trang hoặc test responsive. Xem [định hướng CV-06](docs/CV06_DINH_HUONG_GIAO_DIEN.md).
- Thư mục lưới: `Tailieuthamkhao/Giaodienfrontend/luoi/`, có `luoi_hcm.dxf`, `bắc kan.dxf`, `phú quốc.dxf` và `File ex.xlsx`.
- Workbook có 10 sheet; ba sheet dự án là `data tp. HCM`, `bắc kan`, `data Phú Quốc`, tiêu đề nhiều dòng. CV-02 đã kiểm kê toàn bộ dữ liệu ba sheet, mã trùng, giá trị thiếu và Y; xem [biên bản CV-02](docs/CV02_KIEM_KE_EXCEL.md). Chưa kiểm tra tỷ lệ khớp với DXF (CV-03/CV-04).
- CV-03 đã khảo sát hình học, layer, nhãn và metadata ba DXF; xem [biên bản CV-03](docs/CV03_KHAO_SAT_DXF.md). Người dùng xác nhận VN-2000; chưa có EPSG/kinh tuyến trục/múi chiếu từng file, không mặc định dùng EPSG của Yên Bái.
- Yêu cầu có nhắc “báo cáo” để lấy nội dung nhóm, nhưng chưa xác định tài liệu báo cáo chuyên môn tương ứng. Không coi báo cáo vận hành server là báo cáo nhóm.
- `Tailieuthamkhao/gemini-agent/` là nguồn tham khảo riêng cho giai đoạn agent sau này; chưa chạy script, chưa đọc thông tin tài khoản/cookie và chưa tích hợp vào ứng dụng.
- Mốc hệ thống cũ: [NHAT_KY_DU_AN.md](NHAT_KY_DU_AN.md). Chi tiết vận hành: [README.md](README.md).

## 3. Phạm vi đích theo yêu cầu

- Điều hướng ở **header** gồm: **Giới thiệu**, **Dự án**, **Đánh giá quỹ đất**. Người dùng đã đính chính “footer” trong tài liệu gốc thành “header”. Trang mở đầu mặc định là **Giới thiệu**.
- Giới thiệu: một phần giới thiệu nhóm và **3 ý Tầm nhìn**, danh sách dự án, 4 thẻ thành viên có ảnh và liên hệ khuôn mẫu. Không tách thành Giới thiệu / Sứ mệnh / Tầm nhìn. Nội dung tham khảo trang mẫu/báo cáo, nhưng dùng phong cách của trang Đánh giá quỹ đất hiện tại.
- Dự án: đúng 4 mục. Ba dự án địa phương (TP.HCM, Bắc Kạn, Phú Quốc) mở bản đồ kết quả có sẵn. Dự án thứ tư “Ứng dụng AI vào đánh giá quỹ đất dựa trên quy hoạch chi tiết” dẫn tới cùng trang Đánh giá quỹ đất.
- Ba bản đồ địa phương: có lưới, ô màu chấm điểm và thông tin kết quả; không có nạp layer, nạp Excel hoặc chạy AI cho người xem.
- Các ô Bắc Kạn `BK1`–`BK20` thiếu dữ liệu **không xét điểm, chỉ hiện đường lưới, không tô màu**, theo xác nhận trực tiếp của người dùng. Không tự tạo hoặc điền Y=0.
- Đánh giá quỹ đất: kế thừa ứng dụng hiện tại, không tự dùng kết quả mặc định, không cho tải mô hình/scaler từ giao diện. Chủ ứng dụng đặt mô hình đã huấn luyện trong thư mục máy chủ cố định.
- Người dùng chủ động nạp file `ketqua.csv`; kết quả đã nạp được lưu để khôi phục. Không tự đọc file kết quả mặc định trên máy chủ. Không xóa file kết quả gốc; luồng chạy dự đoán hiện có không bị loại bỏ bởi quyết định này.
- Excel tham khảo chỉ cung cấp dữ liệu cố định cho ba dự án địa phương, không dùng làm dữ liệu của dự án thứ tư và không bổ sung upload Excel vào trang đánh giá trong phạm vi hiện tại.
- Người dùng cho phép kiến trúc **backend–frontend** để hỗ trợ mở rộng. CV-05 sẽ chốt ranh giới API, cấu trúc mã và công nghệ cụ thể; chưa coi là đã chọn framework, database hoặc cách triển khai.
- Ghép kết quả/lưới linh hoạt hơn: cho phép đối chiếu phần số trong tên/mã, nhưng phải kiểm soát trùng và mơ hồ, không ghép gần đúng tùy tiện.
- Chatbot popup làm sau. Ngay từ đầu giao diện cần có tên điều khiển rõ ràng và cấu trúc để agent đọc/thao tác.

## 4. Các quyết định đã chốt và điểm còn cần xác nhận

### CV-01 đã chốt với người dùng

1. Trang mở đầu mặc định: **Giới thiệu**.
2. Điều hướng 3 mục nằm ở **header**, không phải footer. Người dùng đã chốt header luôn hiện khi cuộn vào ngày 2026-10-26
3. Nội dung: **một phần Giới thiệu + 3 ý Tầm nhìn**.
4. Workbook tham khảo chỉ dùng cho **ba dự án địa phương**, không phải dự án AI thứ tư; chưa thêm tính năng upload `.xlsx` vào trang đánh giá.
5. Không tự lấy `ketqua.csv` mặc định từ máy chủ. Người dùng **nạp file kết quả và kết quả được lưu/khôi phục** theo phiên. CV-20/CV-22 phải thực hiện chính sách này, không chỉ ẩn dữ liệu trên giao diện.
6. Cho phép tổ chức kiến trúc **backend–frontend** vì hệ thống có nhiều phần mở rộng. Thiết kế chi tiết ở CV-05; tận dụng logic GIS/dự đoán đã có, không tự viết lại toàn bộ hoặc tự chọn stack mới.

### Quyết định sau CV-02/CV-03

- `BK1`–`BK20`: không xét điểm, giữ đường bao, không tô màu. Đã chốt, không còn chờ bổ sung điểm cho các ô này.
- Ba lưới dùng VN-2000 theo người dùng. Vẫn cần mã EPSG hoặc thông số kinh tuyến trục/múi chiếu của từng file để duyệt phép chuyển tọa độ. Không tự gán EPSG chung hoặc tự sửa đơn vị mm trong header Phú Quốc.
- Người dùng nhớ không chắc mã dùng chung trước đây là 9201. Đã kiểm tra: pyproj/PROJ không nhận EPSG:9201 làm CRS; mã 9201 trong danh mục đơn vị PROJ là `unity`. Ảnh trước đó hiển thị EPSG:9208, chỉ dùng làm đầu mối xác nhận lại. Chưa áp dụng mã nào cho ba DXF; cần ảnh chụp hệ tọa độ hoặc thông số chính xác.

### CV-04 đã chốt với người dùng

- Đồng ý ghép phần số trong cùng dự án: `TP01 ↔ 1`, `BK21 ↔ 21`; khóa mơ hồ/trùng hoặc xung đột Y không tự ghép, không lấy số gần nhất.
- Giữ bảng màu từ code hiện tại: Y=0 đỏ `#ff0000`, Y=1 cam `#ffa500`, Y=2 xanh lá `#008000`, độ tô nguồn 0,6. Chú giải dùng `Kết quả Y = 0/1/2`; code chưa có tên mức nghiệp vụ nên không tự đặt thêm.
- Phú Quốc: được gộp hình học trùng hoàn toàn trong bộ nhớ, giữ handle nguồn và không sửa DXF. Không gộp chồng lấn một phần.
- Mã Phú Quốc `1232`: không áp dụng kết quả, không tô, **không hiển thị cảnh báo cho người xem**, giữ chẩn đoán nội bộ. Không tự tạo ô, dịch nhãn hoặc ghép với ô gần nhất.
- Chi tiết và ví dụ: [biên bản CV-04](docs/CV04_QUY_TAC_GHEP_VA_MAU.md), [đặc tả có cấu trúc](docs/cv04_join_render_policy.json). Đây là quyết định triển khai, chưa phải thuật toán mới đã được tích hợp.

### Các điểm chốt ở đề mục tiếp theo

Không chặn CV-01; sẽ hỏi khi đến đúng đề mục.

- Tên nhóm, báo cáo nguồn, tên/ảnh/liên hệ của 4 thành viên. Khi chưa có, dùng ô nội dung mẫu được ghi rõ, không giả là thông tin thật.
- Với mỗi DXF: EPSG hoặc thông số phép chiếu VN-2000, đơn vị thực/độ dịch nếu có. Quy tắc gộp trùng, không áp dụng 1232 và bảng màu đã chốt tại CV-04; phần xác định vị trí MTEXT và tỷ lệ ghép hình học thực phải được kiểm thử khi triển khai CV-12/CV-14.
- Đã xác nhận website sẽ public, cần cách ly workspace nhiều người. Công nghệ/lưu trữ CV-05 đã duyệt. Ngày 2026-10-27 người dùng chốt phần Đánh giá dùng không cần đăng nhập, bản lưu tiếp tục ở trình duyệt từng người và máy chủ xử lý theo request. Hạn mức, thời hạn lưu và tải đồng thời sẽ chốt trước triển khai CV-25, chưa chọn dịch vụ agent

## 5. Danh sách đầu việc theo thứ tự

Quyết định mới ngày 2026-10-26: trang Đánh giá quỹ đất ưu tiên giữ giao diện legacy trong header và footer chung, không tiếp tục thay công cụ này bằng khung React mới. Bộ mô hình hoạt động chuyển sang một file `rf_model_rating_pipeline.pkl` đã gồm chuẩn hóa. Phiên CSV của giao diện trước được giữ riêng và còn truy cập ở `/portal/assessment/csv`

Quyết định ngày 2026-10-26: người dùng sẽ chốt vị trí ba lưới sau, tiếp tục CV-19 trước để hoàn thiện luồng dự đoán với mô hình cố định trên máy chủ

### Giai đoạn A — Chốt yêu cầu và dữ liệu

- [x] **CV-01 — Chốt các lựa chọn chức năng còn mơ hồ.**
  - Đã xác nhận header, trang Giới thiệu mặc định, 3 ý Tầm nhìn, Excel chỉ cho ba dự án, kết quả CSV do người dùng nạp được lưu và định hướng backend–frontend.
  - Kết quả: ghi đầy đủ 6 quyết định tại mục 4; các câu hỏi dữ liệu, nội dung và kiến trúc chi tiết chuyển đúng đề mục liên quan.
  - Kiểm tra: đối chiếu với 6 câu trả lời trực tiếp của người dùng; chỉ sửa kế hoạch, chưa triển khai chức năng.
  - Phụ thuộc: không.

- [x] **CV-02 — Kiểm kê đầy đủ Excel cho ba địa phương.**
  - Đọc toàn bộ 3 sheet liên quan; xác định dòng dữ liệu, cột tên ô/ID, x1–x9, Y; đếm thiếu, trùng và Y không hợp lệ. Không lấy nhầm sheet huấn luyện hoặc sheet Yên Bái.
  - Hoàn thành khi: có cấu hình đọc riêng từng sheet và ví dụ mã thực tế; các dòng không dùng được có lý do.
  - Phụ thuộc: không; không sửa file gốc.
  - Kết quả: [biên bản kiểm kê](docs/CV02_KIEM_KE_EXCEL.md), [định nghĩa nguồn từng sheet](docs/cv02_excel_sources.json) và công cụ chỉ đọc `tools/audit_reference_excel.py`.
  - TP.HCM: 297 dòng đủ dữ liệu; tổng trực tiếp Y=0/1/2 là 135/162/0. Công thức L302 đếm thiếu 1 dòng Y=0; mã `TP267` không có trong nguồn.
  - Bắc Kạn: 400 mã, 380 dòng đủ dữ liệu; `BK1`–`BK20` (hàng 4–23) thiếu x1–x9 và Y. Số mẫu cột A bị trùng, không dùng làm ID ghép mặc định. Không tự gán Y=0 cho ô thiếu.
  - Phú Quốc: 1.677 dòng đủ dữ liệu; mã B là số Excel, cần giữ kiểu gốc khi chuẩn bị khóa.
  - Kiểm tra: đọc hết ba sheet, xác nhận SHA-256 trước/sau không đổi; đối chiếu cấu hình với kết quả kiểm kê; 8 kiểm thử bộ kiểm kê đạt. Không sửa Excel, không chạy AI hay ghép DXF.
  - Người dùng đã chốt `BK1`–`BK20` không xét, hiện nét lưới và không tô màu. Còn lại: quy tắc ghép/màu Y ở CV-04 và phép chiếu chi tiết theo biên bản CV-03. Không tự điền các giá trị thiếu.

- [x] **CV-03 — Khảo sát ba lưới DXF.**
  - Kiểm tra polyline kín, block, TEXT/MTEXT, mã ô, extent và tọa độ. Đối chiếu địa phương để xác nhận EPSG/độ dịch với người dùng khi thiếu bằng chứng.
  - Hoàn thành khi: từng dự án có kết luận về cách đọc, trường ghép, CRS đã xác nhận hoặc vướng mắc cụ thể. Không đánh dấu đúng vị trí chỉ vì hình học đã vẽ được.
  - Phụ thuộc: không.
  - Kết quả: [biên bản khảo sát](docs/CV03_KHAO_SAT_DXF.md), [định nghĩa nguồn](docs/cv03_dxf_sources.json), công cụ chỉ đọc `tools/audit_reference_dxf.py` và 5 kiểm thử không sửa DXF.
  - Chọn hình học/nhãn ứng viên: TP.HCM `DTL-1D` + MTEXT layer `0` (1.695 ô); Bắc Kạn `00.Ranh gioi` + MTEXT layer `0` (400 ô); Phú Quốc `Docao` + TEXT layer `0` (1.734 polygon, 1.676 hình học khác nhau, 58 bản trùng dư).
  - Đã tái hiện vấn đề bộ đọc hiện tại: lẫn đường bao/nhãn nền, điểm chèn MTEXT trên biên, hình học Phú Quốc trùng và nhãn 1232 ngoài lưới. Chưa áp dụng snap, gộp trùng, ghép gần nhất hoặc sửa nguồn.
  - Người dùng xác nhận VN-2000; chưa có EPSG/phép chiếu cụ thể. Cả ba không có GEODATA; Phú Quốc có header đơn vị mm và XREF ngoài chưa được cung cấp. Đã hỏi thêm EPSG/kinh tuyến trục/múi chiếu; chưa duyệt chuyển tọa độ.
  - Kiểm tra: hash nguồn trước/sau không đổi; 5 kiểm thử DXF + 8 Excel đạt. Hoàn thành khảo sát với vướng mắc cụ thể, không đánh dấu dữ liệu đã định vị/ghép đúng.

- [x] **CV-04 — Chốt quy tắc ghép mã và bảng màu.**
  - So khớp Excel/DXF từng dự án; thống kê ghép chính xác, ghép bằng phần số, không khớp và mơ hồ. Chốt quy tắc với ví dụ được/không được ghép, ý nghĩa Y và màu chú giải.
  - Hoàn thành khi: có mẫu đối chiếu người dùng kiểm tra được; không tự chọn một kết quả khi nhiều ô cùng phần số.
  - Phụ thuộc: CV-02, CV-03.
  - Bổ sung từ khảo sát: chốt cách xác định vị trí nhãn MTEXT và xử lý trùng/nhãn ngoài Phú Quốc trước khi hứa tỷ lệ ghép. `BK1`–`BK20` đã được duyệt không xét, hiện lưới không tô; không cần hỏi lại quy tắc này.
  - Đã chốt bốn quyết định của người dùng: ghép phần số trong từng dự án, dùng bảng màu hiện có, gộp polygon trùng trong bộ nhớ, không tô/không cảnh báo mã 1232. Chi tiết tại [biên bản CV-04](docs/CV04_QUY_TAC_GHEP_VA_MAU.md).
  - Đã kiểm tra bảng màu trong `prediction_grid.py`/`gis.py` và nhãn nhóm trong `wwwroot/layer_manager.js`; đặc tả JSON được đối chiếu với code, không tự thêm tên mức đánh giá.
  - Phạm vi mã số ứng viên đủ chứa 297 mã Excel TP.HCM, 400 mã Bắc Kạn (380 được xét), 1.677 mã Phú Quốc (1232 không áp dụng). Không coi số lượng mã là tỷ lệ ghép hình học thành công.
  - Hoàn thành phần chốt quy tắc; xác định vị trí MTEXT và kiểm chứng tỷ lệ ghép thực được chuyển thành tiêu chí triển khai CV-12/CV-14. Chưa sửa bộ ghép/renderer, chưa áp dụng CRS chưa xác nhận.

### Giai đoạn B — Khung ứng dụng và giao diện chung

- [x] **CV-05 — Chốt cách tổ chức trang và dữ liệu dự án.**
  - Đề xuất kiến trúc backend–frontend: trách nhiệm từng phần, route cho 3 trang/bản đồ chi tiết và hợp đồng API. Phân tách dữ liệu công khai cố định, phiên đánh giá và thư mục mô hình riêng; đánh giá tận dụng Python/GIS/Leaflet hiện tại, chốt framework với người dùng trước khi chuyển đổi.
  - Hoàn thành khi: có cấu trúc mã backend/frontend, danh sách route, nơi đặt cấu hình dự án, hợp đồng API chỉ đọc/đánh giá và phương án chuyển đổi từ ứng dụng hiện tại được duyệt.
  - Phụ thuộc: CV-01.
  - **Đã được đồng ý về công nghệ/lưu trữ:** [kiến trúc CV-05](docs/CV05_KIEN_TRUC_BACKEND_FRONTEND.md). Frontend React + TypeScript + Vite; backend Python/Flask theo factory/Blueprint; API `/api/v1`; SQLite metadata + file riêng + IndexedDB autosave. Chưa áp dụng vào ứng dụng.
  - Có cấu trúc thư mục, route, trách nhiệm từng module, hợp đồng API dự kiến, quyền workspace, loại bỏ fallback kết quả chung/upload mô hình, migration bản lưu và lộ trình chuyển đổi không xóa mã/dữ liệu cũ.
  - Người dùng đã xác nhận sẽ public. Chốt phạm vi nhiều người truy cập: dự án xem chung, file/kết quả đánh giá tách riêng từng workspace; public không có nghĩa tự chia sẻ dữ liệu người dùng.
  - Hoàn thành thiết kế nền tảng để sang CV-06. Cập nhật 2026-10-27 đã chốt dùng ẩn danh, quota, thời hạn lưu và tải đồng thời còn mở ở CV-25. Ghi chú chưa tạo frontend/API/database ở giai đoạn thiết kế không còn phản ánh trạng thái triển khai hiện tại

- [ ] **CV-06 — Chốt mẫu giao diện chung.**
  - Tham khảo trang mẫu khi truy cập được hoặc dùng ảnh chụp người dùng cung cấp. Chọn màu, chữ, khoảng cách, thẻ dự án/thành viên theo phong cách Đánh giá quỹ đất hiện tại.
  - Hoàn thành khi: người dùng duyệt một mẫu nhất quán; không sao chép layout trang mẫu trái yêu cầu.
  - Phụ thuộc: CV-05; nguồn trang mẫu/ảnh tham khảo.
  - Đã đọc lại được website tham khảo, đối chiếu CSS hiện tại và soạn [định hướng CV-06](docs/CV06_DINH_HUONG_GIAO_DIEN.md). Chỉ tham khảo cấu trúc nội dung, không sao chép thương hiệu, ảnh hoặc toàn bộ layout.
  - Đề xuất trang Giới thiệu: header 3 mục → phần mở đầu → giới thiệu nhóm → 3 ý Tầm nhìn → 4 dự án → 4 thành viên → thông tin cuối trang. Dùng Inter, nền trắng/xanh lá theo công cụ hiện tại; không bịa thông tin nhóm.
  - Đã dựng prototype riêng tại `wwwroot/preview/index.html`, xem ở `http://127.0.0.1:8765/static/preview/index.html`: 3 mục header, Giới thiệu đầy đủ các khối, 4 dự án với bộ lọc/hộp thông tin, 4 thành viên mẫu, bố cục Đánh giá hai tab.
  - Prototype HTML/CSS/JS không gọi API/ghi dữ liệu, không thay app.py hoặc giao diện cũ. Sơ đồ SVG có nhãn minh họa; thông tin thành viên/nội dung nhóm chưa được giả làm thông tin thật. React/API triển khai ở CV-07 trở đi sau khi duyệt.
  - Kiểm tra: JS hợp lệ, HTTP 200 trang/assets và trang cũ, 6 kiểm thử logic DOM giả lập + 3 kiểm thử Python đạt. Kết nối trình duyệt hiện chưa có, chưa QA trực quan hoặc nghiệm thu responsive.
  - Chờ người dùng xem và duyệt mẫu; header mẫu hiện không sticky. CV-06 chưa đánh dấu hoàn thành khi chưa được duyệt.

- [ ] **CV-07 — Làm bộ khung và header 3 mục.**
  - 2026-10-26 người dùng chốt header luôn hiện khi cuộn, đã thêm sticky header dùng chung và tính chiều cao động để chừa khoảng cho bản đồ và nội dung
  - 2026-10-26: đã triển khai khung React/TypeScript và Flask factory/API v1 theo yêu cầu tiếp tục. Xem `/portal/`; ba mục header, danh mục/bộ lọc, trang chi tiết và khung Đánh giá đã nối API nội dung. Reload các route hợp lệ được phục vụ đúng bản build.
  - Đã đạt build TypeScript, 6 kiểm thử React, 61 kiểm thử Python và 34 kiểm thử Node. Chưa QA trực quan/responsive; CV-06 vẫn chờ duyệt. Chế độ tương thích giữ công cụ cũ tại `/` và `/legacy/`, chưa chuyển trang gốc sang giao diện mới. Chi tiết: [CV07_TRIEN_KHAI_KHUNG.md](docs/CV07_TRIEN_KHAI_KHUNG.md).
  - Hiển thị trạng thái đang chọn, điều hướng bàn phím, tên truy cập rõ ràng; header không che bản đồ, thanh bên hoặc bảng dữ liệu.
  - Hoàn thành khi: mở địa chỉ gốc vào Giới thiệu; chuyển đủ 3 mục, reload trang đang mở được, bố cục không tràn ở màn hình nhỏ.
  - Phụ thuộc: CV-05, CV-06.

### Giai đoạn C — Trang Giới thiệu và danh sách dự án

- [ ] **CV-08 — Làm phần giới thiệu và 3 ý Tầm nhìn.**
  - Xây một khối Giới thiệu và ba ý Tầm nhìn theo quyết định CV-01; để nội dung trong cấu hình/template dễ sửa. Dẫn nguồn báo cáo khi đã được cung cấp.
  - Hoàn thành khi: đủ các khối được chốt, nội dung mẫu và thông tin đã xác nhận được phân biệt.
  - Phụ thuộc: CV-06, CV-07; báo cáo nếu dùng nội dung thật.

- [ ] **CV-09 — Làm 4 thẻ thành viên.**
  - Ảnh, tên, vai trò và liên hệ; có ảnh thay thế/alt text khi chưa có ảnh thật, không dùng liên hệ giả có thể gây nhầm.
  - Hoàn thành khi: đủ 4 vị trí, đọc được trên điện thoại và thay nội dung không phải sửa logic.
  - Phụ thuộc: CV-08; thông tin thành viên có thể bổ sung sau.

- [ ] **CV-10 — Làm danh mục chung 4 dự án.**
  - Một nguồn dữ liệu dùng lại cho danh sách trên Giới thiệu và trang Dự án. Ba mục địa phương dẫn đúng bản đồ; mục AI dẫn tới đúng trang Đánh giá quỹ đất, không tạo bản sao trang đó.
  - Hoàn thành khi: đủ 4 mục, đúng tên/liên kết và trạng thái dữ liệu chưa sẵn sàng được thông báo rõ.
  - Phụ thuộc: CV-05, CV-07.

### Giai đoạn D — Dữ liệu và ghép mã dùng chung

- [ ] **CV-11 — Làm bộ đọc Excel tham khảo phía máy chủ.**
  - Đọc đúng sheet/dòng/cột đã xác nhận, giữ mã gốc, chuyển Y hợp lệ sang dữ liệu nội bộ. Xử lý ô trống, công thức thiếu giá trị lưu và tiêu đề nhiều dòng, không tự tính ra kết quả giả.
  - Hoàn thành khi: số dòng đầu ra khớp biên bản CV-02; file gốc không bị sửa.
  - Phụ thuộc: CV-02, CV-05.

- [ ] **CV-12 — Làm chế độ ghép phần số có kiểm soát.**
  - Giữ ghép chính xác hiện có; thêm chế độ tách số theo quy tắc CV-04. Bảo toàn khóa gốc, tách theo phạm vi dự án và trả trạng thái ghép. Không dùng số gần nhất, thứ tự dòng hay khoảng cách chuỗi để gán Y.
  - Hoàn thành khi: mã khác chữ nhưng cùng số được ghép theo quy tắc; mã nhiều cụm số, trùng khóa và xung đột Y không bị ghép âm thầm; kiểm thử quy tắc số 0 đầu.
  - Phụ thuộc: CV-04.
  - Thực hiện theo `docs/cv04_join_render_policy.json`; giữ ghép chính xác duy nhất trước fallback số và khóa theo từng dự án. Không để xung đột bị ẩn bằng cách chọn bản ghi đầu.

- [ ] **CV-13 — Thêm xem trước và báo cáo chất lượng ghép.**
  - Hiển thị khóa gốc, khóa đối chiếu, phương thức ghép, số ô khớp/không khớp/mơ hồ và ví dụ lỗi. Cho chọn chế độ/cột ghép phù hợp trong trang đánh giá.
  - Hoàn thành khi: người dùng kiểm tra trước khi áp dụng; ô chưa khớp có kiểu “chưa có dữ liệu”, không mặc định Y=0.
  - Phụ thuộc: CV-12.
  - Ngoại lệ đã duyệt cho bản đồ Phú Quốc: bỏ kết quả 1232, không hiện cảnh báo hoặc cộng trường hợp này vào tổng cảnh báo cho người xem; vẫn giữ trace nội bộ. Không tắt cảnh báo lỗi khác.

- [ ] **CV-14 — Chuẩn bị cấu hình và dữ liệu bản đồ công khai.**
  - Mỗi dự án có mã, tên, DXF, sheet Excel, CRS/độ dịch, quy tắc ghép, bảng màu và phạm vi. Chuẩn bị/cache dữ liệu đã kiểm tra để người xem không phải upload hay chạy AI.
  - Hoàn thành khi: dữ liệu thiếu/sai làm dự án báo chưa sẵn sàng, không trả nhầm dữ liệu dự án khác; không cung cấp đường dẫn file tùy ý qua API.
  - Phụ thuộc: CV-03, CV-04, CV-11, CV-12.
  - Điều kiện bổ sung: có phép chiếu/đơn vị đã xác nhận cho từng DXF; bộ đọc chọn đúng layer/loại nhãn, hiểu MTEXT attachment và xử lý nguồn trùng/ngoài ô theo quyết định được duyệt. Giữ mã/handle để truy vết và không tự sửa file gốc.
  - Phú Quốc: gộp trùng hoàn toàn trong bộ nhớ và giữ danh sách handle, không merge chồng lấn một phần; không áp dụng 1232. Tính lại thống kê ghép hình học thực và so mẫu trước khi nghiệm thu, không chỉ đếm khóa số.

### Giai đoạn E — Ba bản đồ dự án chỉ xem

- [ ] **CV-15 — Làm trình xem bản đồ dự án dùng chung.**
  - 2026-10-26: theo đính chính, đã thay trang chi tiết thông tin bằng trang Leaflet có lưới thật/tô Y, nền đường phố/vệ tinh, chú giải, thanh độ đậm và thông tin ô. Tự nạp bộ DXF–Excel có sẵn; không có upload hoặc chạy AI. Người dùng yêu cầu thử EPSG:9208; đã mặc định xem thử và cho chọn CRS, chưa duyệt vị trí thực địa. Chi tiết: [PROJECT_MAP_VIEWER.md](docs/PROJECT_MAP_VIEWER.md). Các mục CV-16/17/18 chưa nghiệm thu chỉ vì đã tải được lưới.
  - Lưới tô màu theo kết quả có sẵn, chú giải, nền bản đồ, zoom và thông tin khi bấm ô. Không có form nạp layer/Excel hoặc nút chạy AI; API dữ liệu dự án cũng không dựa vào upload từ người xem.
  - Hoàn thành khi: route chi tiết tự mở dữ liệu dự án và chỉ gọi API đọc; thiếu dữ liệu/mạng có thông báo.
  - Phụ thuộc: CV-07, CV-10, CV-14.
  - Quy tắc đã duyệt: các ô không xét `BK1`–`BK20` chỉ hiện nét lưới, fill tắt; không dùng màu lớp Y=0 cho ô thiếu. Kiểm thử bật/tắt và chú giải không làm mất đường bao các ô này.

- [ ] **CV-16 — Hoàn thiện dự án TP.HCM.**
  - Gắn `luoi_hcm.dxf` và sheet `data tp. HCM`; kiểm tra vị trí, tổng ô, màu và một số mã đối chiếu thủ công.
  - Hoàn thành khi: người dùng duyệt vị trí và mẫu kết quả; có số ô không khớp rõ ràng.
  - Phụ thuộc: CV-15.

- [ ] **CV-17 — Hoàn thiện dự án Bắc Kạn.**
  - Gắn `bắc kan.dxf` và sheet `bắc kan`; lặp kiểm tra dữ liệu/vị trí riêng, không sao chép EPSG từ TP.HCM.
  - Hoàn thành khi: đạt các tiêu chí như CV-16 bằng dữ liệu Bắc Kạn.
  - Phụ thuộc: CV-16 để tái sử dụng luồng đã duyệt.

- [ ] **CV-18 — Hoàn thiện dự án Phú Quốc.**
  - Gắn `phú quốc.dxf` và sheet `data Phú Quốc`; kiểm tra và duyệt độc lập.
  - Hoàn thành khi: đạt các tiêu chí như CV-16 bằng dữ liệu Phú Quốc.
  - Phụ thuộc: CV-17.

### Giai đoạn F — Điều chỉnh trang Đánh giá quỹ đất

- [x] **CV-19 — Chuyển mô hình sang thư mục máy chủ cố định.**
  - Đã có bộ cố định trong `models`, API mới và API cũ từ chối nạp model/scaler từ trình duyệt, có mã phiên bản và lỗi thiếu/không tương thích rõ ràng
  - Trang Đánh giá mới đã nạp CSV, xem trước, chạy dự đoán và xuất CSV trực tiếp, không dùng file kết quả chung trong API mới. Lưu/khôi phục qua reload và bỏ fallback của công cụ cũ vẫn thuộc CV-20/CV-22. Chi tiết tại [CV19_MO_HINH_CO_DINH.md](docs/CV19_MO_HINH_CO_DINH.md)
  - Chốt thư mục, tên file mô hình/scaler và cách thay phiên bản; bỏ trường upload và chặn nhận mô hình qua API. Chỉ chủ máy chủ được đặt file đáng tin cậy vì `.pkl` có thể thực thi mã khi nạp.
  - Hoàn thành khi: đặt bộ mô hình hợp lệ thì dự đoán được; thiếu/không tương thích báo lỗi rõ; mô hình không được phục vụ như file tĩnh.
  - Phụ thuộc: CV-05.

- [x] **CV-20 — Bỏ tự dùng kết quả mặc định.**
  - Đã có nạp CSV kết quả riêng, giữ Y trống, xuất đúng kết quả và tự lưu/khôi phục phiên Đánh giá mới qua IndexedDB
  - Đã bỏ đọc/ghi/fallback file kết quả chung ở công cụ cũ, không xóa file thật có sẵn. Kiểm thử giao dịch, xung đột tab và lỗi CSV đã đạt. Chi tiết tại [CV20_KET_QUA_VA_TU_LUU.md](docs/CV20_KET_QUA_VA_TU_LUU.md)
  - Không tự đọc `KetQua.csv` mặc định trên máy chủ. Nhận file kết quả CSV người dùng chủ động nạp, lưu và khôi phục đúng phiên; tách khỏi kết quả phiên khác. Không xóa `KetQua.csv` thật và không để API export tải nhầm kết quả.
  - Hoàn thành khi: mở phiên mới không nạp kết quả mặc định; nạp CSV hợp lệ thì hiển thị/ghép được, reload giữ đúng dữ liệu đã nạp. Luồng dự đoán chủ động hiện có vẫn hoạt động, không tự chạy mô hình khi mở trang.
  - Phụ thuộc: CV-01, CV-05, CV-19.

- [x] **CV-21 — Gắn luồng ghép linh hoạt vào trang đánh giá.**
  - Hoàn thành cho công cụ legacy ngày 2026-10-27, ghép chính xác hoặc phần số duy nhất, báo cáo và xác nhận áp dụng, ô thiếu dữ liệu không tô màu
  - Tích hợp chọn khóa/chế độ, xem trước, xác nhận ghép rồi tô lưới; giữ dữ liệu đầu vào/kết quả và thống kê khớp nhất quán.
  - Hoàn thành khi: đi trọn luồng nạp dữ liệu → dự đoán → ghép lưới → xem kết quả, không nhầm giữa tên ô và ID chỉ vì cùng chứa số.
  - Phụ thuộc: CV-13, CV-19, CV-20.

- [x] **CV-22 — Điều chỉnh tự lưu theo cấu trúc mới.**
  - Hoàn thành theo phạm vi đã đổi sang giữ legacy, snapshot giữ nguồn, layer đã áp dụng, kết quả, cách ghép và khung nhìn, database phiên CSV React không bị thay thế
  - Ghi chú di chuyển GeoJSON sang React dưới đây là kế hoạch cũ, không còn là bước bắt buộc sau quyết định giữ legacy
  - Database công cụ chính mapPredict.workspace giữ file, layer/GeoJSON đã áp dụng, bảng kết quả, cách ghép và khung nhìn, khôi phục không chạy lại mô hình hoặc gửi lại file
  - Database mapPredict.assessment của phiên CSV riêng được giữ nguyên, không còn yêu cầu chuyển GIS sang phiên này theo quyết định ưu tiên legacy
  - Tách phiên đánh giá khỏi ba dự án công khai; không lưu lại mô hình upload cũ để lách chính sách mới. Xác định cách đọc/chuyển schema cũ, giữ dữ liệu người dùng hoặc yêu cầu xác nhận khi không thể chuyển.
  - Hoàn thành khi: reload đúng trang/phiên, qua lại dự án không lẫn layer/kết quả; bản lưu cũ không bị ghi đè rỗng và không khôi phục đầu vào mô hình đã bị loại bỏ.
  - Phụ thuộc: CV-07, CV-15, CV-19, CV-20, CV-21.

### Giai đoạn G — Sẵn sàng cho agent và triển khai

- [ ] **CV-23 — Kiểm tra khả năng đọc/thao tác của agent.**
  - Rà soát HTML ngữ nghĩa, label/role/tên nút, ID ổn định, bàn phím và thông báo đang xử lý/thành công/lỗi. Cung cấp nội dung tương đương cho đối tượng canvas qua bảng/DOM và dữ liệu có cấu trúc có phạm vi.
  - Hoàn thành khi: có kịch bản tự động mở dự án, đọc thông tin ô và thao tác đánh giá bằng các điều khiển có tên, không phụ thuộc tọa độ màn hình.
  - Phụ thuộc: áp dụng từ CV-07; nghiệm thu sau CV-21, CV-22. Chưa kết nối agent thật hoặc cấp quyền điều khiển.

- [ ] **CV-24 — Kiểm thử hồi quy và kiểm tra tách dữ liệu.**
  - Kiểm thử 3 trang/4 dự án, ba bộ DXF–Excel, ghép mã/mơ hồ, thiếu mô hình, không nạp kết quả mặc định, tự lưu, PDF và CSV. Kiểm tra zoom/header/thanh bên trên desktop/mobile; vì website public, bắt buộc kiểm thử hai phiên không đọc/ghi/xuất được dữ liệu của nhau.
  - Hoàn thành khi: lỗi chặn được xử lý; báo cáo phân biệt tile giả trong test với tải nền mạng thực; chạy test ghi dữ liệu trên máy chủ tách biệt.
  - Phụ thuộc: CV-16 đến CV-23.

- [ ] **CV-25 — Chuẩn bị cấu hình và hướng dẫn triển khai.**
  - Quyết định 2026-10-27 ưu tiên hoàn thiện local, chưa có hosting và chưa triển khai public, các yêu cầu phát hành dưới đây dành cho giai đoạn sau
  - Tài liệu thư mục mô hình, dữ liệu công khai, biến cấu hình, khởi động, cập nhật dự án và sao lưu. Chốt giới hạn upload, thông báo lỗi, quyền ghi/đọc và chính sách tile cho môi trường triển khai.
  - Hoàn thành khi: cài trên môi trường sạch theo hướng dẫn được; không lộ file mô hình, bí mật hoặc thư mục tham khảo qua web. Chưa tự triển khai dịch vụ trả phí.
  - Phụ thuộc: CV-24, quyết định môi trường/số người dùng ở mục 4.
  - Website đã được xác nhận sẽ public, phần Đánh giá dùng không cần đăng nhập theo quyết định 2026-10-27. Trước triển khai còn cần chốt hạn mức upload/chạy mô hình, thời hạn lưu/quyền xóa, số người đồng thời dự kiến và sao lưu. Chưa chọn hoặc thuê hosting
  - Giữ bản lưu IndexedDB theo trình duyệt, không tự bổ sung lưu file hoặc kết quả chung trên máy chủ, không tự chia sẻ phiên hoặc đồng bộ giữa thiết bị
  - Điều kiện phát hành: HTTPS, kiểm tra quyền workspace/asset/result, CSRF/origin checks cho thao tác ghi, giới hạn tài nguyên/tần suất và kiểm thử cách ly. Không dùng nguyên máy chủ Flask local hoặc endpoint fallback/upload model cũ làm bản public.

### Giai đoạn H — Trợ lý GIS

- [x] **CV-26 — Chốt phạm vi và quyền của chatbot popup.**
  - Chốt 2026-10-27 dùng server Gemini được cung cấp, đọc/sửa DXF và hỗ trợ điểm có nguồn, xem trước rồi áp dụng. Đặc tả và giới hạn tại docs/CV26_27_CHATBOT.md
  - Xác định chỉ hỏi đáp hay được thao tác, nguồn tri thức, nhà cung cấp, dữ liệu được gửi ra ngoài và hành động cần xác nhận. Rà soát chọn lọc mã tham khảo `gemini-agent`, không tự dùng cookie/tài khoản có sẵn.
  - Hoàn thành khi: người dùng duyệt đặc tả và quyền; chưa chạy agent khi chưa thống nhất.
  - Phụ thuộc: CV-23, CV-25; chỉ bắt đầu khi người dùng yêu cầu.

- [ ] **CV-27 — Triển khai và kiểm thử chatbot theo phạm vi đã duyệt.**
  - Đã dựng popup, API request-scoped và service Gemini, đang kiểm tra bản triển khai và CI. Kiểm thử trực quan còn cần trình duyệt khả dụng
  - Popup thống nhất style; xử lý đang trả lời/lỗi/ngắt kết nối. Nếu có thao tác, giới hạn công cụ và yêu cầu xác nhận hành động thay đổi dữ liệu.
  - Hoàn thành khi: các kịch bản được duyệt chạy đúng, không tự suy diễn kết quả đánh giá hoặc thực hiện hành động ngoài quyền.
  - Phụ thuộc: CV-26.

## 6. Mốc nghiệm thu để làm từng phần

1. **Mốc 1:** CV-01 đến CV-04 — đủ quyết định và dữ liệu để không xây trên giả định sai.
2. **Mốc 2:** CV-05 đến CV-10 — duyệt khung giao diện và nội dung trước khi tích hợp toàn bộ dữ liệu.
3. **Mốc 3:** CV-11 đến CV-18 — xem được cả ba bản đồ dự án có kết quả kiểm chứng.
4. **Mốc 4:** CV-19 đến CV-22 — trang đánh giá hoạt động theo chính sách mô hình/kết quả mới.
5. **Mốc 5:** CV-23 đến CV-25 — kiểm thử và sẵn sàng triển khai.
6. **Mốc 6:** CV-26 đến CV-27 — chatbot, tách riêng và làm sau.

**CV-01, CV-02, phần khảo sát CV-03, phần chốt quy tắc CV-04 và thiết kế nền tảng CV-05 đã hoàn thành. CV-06 đã có định hướng từ website mẫu, đang chờ duyệt mẫu giao diện.** Website sẽ public; chính sách truy cập/vận hành phải chốt tại CV-25 trước triển khai. Còn chờ phép chiếu chi tiết VN-2000 trước khi duyệt định vị dữ liệu; thuật toán MTEXT/ghép/gộp trùng sẽ được triển khai và kiểm chứng ở CV-12/CV-14.

## 7. Nhật ký cập nhật note

- 2026-10-28: theo yêu cầu chỉ mô phỏng production local, bỏ snapshot và blue/green, gom Qdrant vào cùng Compose bằng named volume, giữ nguyên 6 collection/807 point đã đối chiếu hash. Chỉ một bản chạy mỗi service, backup do người dùng quản lý

- 2026-10-28: tiếp tục CV-27 theo yêu cầu Qdrant, tách service AI riêng, prompt có thể chỉnh từ config, bổ sung xuất DXF từ preview và nguồn RAG có ID/ô tham chiếu. Giữ collection cũ và tạo snapshot, chi tiết docs/AI_SERVICE_QDRANT.md

- 2026-10-27: bổ sung triển khai tự động dùng chung Windows/Linux bằng Python, Linux dùng systemd timer và dịch vụ khởi động stack. Không tăng container thường trực, không đổi mã khi chuyển VPS. Cần cấp máy Linux, dữ liệu riêng và token tunnel trong lần cài đầu

- 2026-10-27: thêm tự triển khai sau CI bằng Windows Task Scheduler mỗi năm phút, không thêm container, chỉ cập nhật commit main khớp nhánh tín hiệu deploy-ready và workspace sạch. Đã cài tác vụ trên máy hiện tại, chi tiết vận hành trong docs/GITHUB_ACTIONS.md

- 2026-10-27: tối ưu Docker còn ba container chạy thường xuyên, một backend với frontend tĩnh, Nginx và tunnel giữ cổng cố định. Slot dự phòng chỉ bật khi cập nhật rồi gỡ sau khi request cũ hoàn thành. Image 837 MB còn 617 MB, mẫu RAM khoảng 583 MiB còn 224 MiB, 84 kiểm thử production đạt. Hướng dẫn khởi động tại docs/DOCKER_DEPLOYMENT.md

- 2026-10-26: bắt đầu CV-06 theo yêu cầu, dựng prototype local riêng và giữ nguyên công cụ đang chạy; 3 mục điều hướng, các khối Giới thiệu/Dự án/thành viên và mẫu Đánh giá. 6 kiểm thử logic + 3 kiểm thử static đạt; chưa QA trực quan và chưa được duyệt mẫu.
- 2026-10-26: thử lại dcsolution.vn thành công qua web/HTTP, đọc trang chủ/Sứ mệnh/Dự án và đối chiếu CSS dự án. Viết định hướng CV-06, chưa tạo mẫu hoặc sửa frontend; không sao chép ảnh/thương hiệu và không thay đổi website tham khảo.
- 2026-10-26: người dùng xác nhận website sẽ public. Chốt CV-05 nền tảng cho nhiều người, cách ly workspace; chuyển chi tiết đăng nhập/ẩn danh, hạn mức và thời hạn lưu thành điều kiện CV-25 trước triển khai. Chưa public ứng dụng hoặc mua dịch vụ.
- 2026-10-26: người dùng đồng ý phương án công nghệ/lưu trữ CV-05. Còn chờ câu trả lời dùng cá nhân hay nhiều người, chưa tự chọn đăng nhập/phân quyền và chưa triển khai chuyển đổi.
- 2026-10-26: viết tiếp bản đề xuất CV-05, đối chiếu API hiện tại và tài liệu chính thức Flask/React/Vite; đề xuất tách frontend/backend, dữ liệu theo workspace và lộ trình migration. Chưa duyệt stack, chưa chuyển đổi ứng dụng hoặc cài package.
- 2026-10-26: chốt CV-04 theo bốn quyết định của người dùng; kiểm tra bảng màu từ code, ghi đặc tả ghép/gộp trùng và không tô/không cảnh báo 1232. Chưa thay thuật toán ứng dụng; tiếp theo CV-05.
- 2026-10-26: ghi quyết định ô Bắc Kạn không xét chỉ hiện nét lưới; hoàn thành khảo sát CV-03, phát hiện layer nguồn/nhãn MTEXT trên biên, 58 polygon Phú Quốc trùng và nhãn 1232 ngoài lưới. Người dùng xác nhận VN-2000; đang chờ phép chiếu cụ thể. Nguồn không đổi, chưa sửa renderer.
- 2026-10-26: hoàn thành CV-02; có biên bản và định nghĩa đọc từng sheet, phát hiện 20 dòng Bắc Kạn thiếu dữ liệu và lỗi phạm vi tổng kết TP.HCM. Giữ nguyên workbook và ứng dụng hiện tại; tiếp theo CV-03.
- 2026-10-26: hoàn thành CV-01 theo 6 câu trả lời của người dùng; sửa footer thành header, Giới thiệu mặc định, 3 ý Tầm nhìn, Excel chỉ cho ba dự án, lưu CSV kết quả do người dùng nạp và cho phép kiến trúc backend–frontend. Chưa đổi mã ứng dụng.
- 2026-10-26: đọc yêu cầu, xác định tài liệu/dữ liệu tham khảo, kiểm tra cấu trúc Excel chỉ đọc; lập 27 đầu việc trong 8 giai đoạn. Chưa thay mã chức năng, chưa sửa DXF/Excel, chưa chạy mã tham khảo hoặc tích hợp chatbot.

## Quản trị AI ngày 2026-10-28

Đã làm trang quản trị xác thực phía service, hai chế độ model, embedding riêng cho quản trị và duy trì phiên Gemini
Cần người dùng nhập cookie Google mới tại /portal/admin/ai vì hồ sơ tham khảo đang yêu cầu đăng nhập lại
Không đổi embedding của collection, không tạo snapshot
