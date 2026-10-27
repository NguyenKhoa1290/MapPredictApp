# CV-05 — Đề xuất kiến trúc backend–frontend

Ngày soạn: 2026-10-26. Trạng thái: **đã chốt thiết kế nền tảng CV-05**. Người dùng đồng ý công nghệ/lưu trữ và xác nhận website sẽ **public**, cần hỗ trợ nhiều người truy cập. Chưa đổi stack, di chuyển mã hoặc triển khai lên mạng.

## 1. Phương án đề xuất

- **Backend:** giữ Python/Flask, tổ chức thành các module API, dịch vụ nghiệp vụ và kho lưu trữ. Tái sử dụng xử lý CAD, tọa độ, lưới, màu và mô hình hiện có, không viết lại thuật toán chỉ để tách frontend.
- **Frontend:** React + TypeScript + Vite, dùng Leaflet cho bản đồ. Tách trang Giới thiệu, Dự án, trình xem dự án và không gian Đánh giá quỹ đất; các tính năng dùng lại thành module.
- **Giao tiếp:** JSON/GeoJSON và multipart upload qua `/api/v1`. Không nhúng đường dẫn máy chủ hoặc mô hình vào frontend.
- **Lưu trữ ban đầu:** đề xuất SQLite cho metadata phiên và danh mục tài nguyên, filesystem riêng cho file/GeoJSON lớn; IndexedDB tiếp tục lưu phiên làm việc phía trình duyệt. Chưa chọn nhà cung cấp cloud, chưa tạo database hoặc cài thư viện mới.
- **Triển khai ban đầu:** cùng một origin cho giao diện và API; frontend có bước build riêng nhưng không bắt buộc cần hai máy chủ khi vận hành. Chưa chuyển sang microservices, SSR, Redis, hàng đợi hoặc dịch vụ AI bên ngoài.

**Phạm vi đã xác nhận:** website công khai, không thiết kế như ứng dụng chỉ một người dùng trên máy. Ba dự án có sẵn là dữ liệu xem chung; file/kết quả người dùng tự nạp hoặc tạo thuộc workspace riêng, không tự công khai vì website public. Chưa chốt số người đồng thời hoặc yêu cầu đăng nhập, nên chưa cam kết khả năng chịu tải hay cơ chế chia sẻ workspace.

Lý do chọn: dự án đã có Python/GIS/mô hình và các kiểm thử; yêu cầu mới chủ yếu tăng số trang, chế độ xem và phần mở rộng. Frontend có thể phát triển độc lập với API, trong khi backend giữ một hệ thống module để hạn chế độ phức tạp vận hành. Đây là lựa chọn thiết kế cho dự án, không phải yêu cầu bắt buộc của framework.

Flask có mẫu [application factory](https://flask.palletsprojects.com/en/stable/patterns/appfactories/) và [Blueprint](https://flask.palletsprojects.com/en/stable/blueprints/) cho việc phân module. React có hướng dẫn [dùng build tool như Vite](https://react.dev/learn/build-a-react-app-from-scratch); đổi lại, phương án SPA phải tự tổ chức routing/data fetching và không tự có SSR. Chưa có yêu cầu SEO/SSR đủ để thêm một backend JavaScript thứ hai.

## 2. Hiện trạng và điểm cần thay đổi

Đã đối chiếu trực tiếp `app.py`, `predict_pkl.py`, `wwwroot/workspace_store.js` và các chức năng hiện có:

- `app.py` đang gộp route, đọc upload, ghi kết quả và điều phối GIS. Có biến `RESULT_CSV` chung; `/api/results` đọc file đó, `/api/map` có fallback sang file đó, `/api/export` cũng xuất file chung. Đây là các điểm phải thay để không lấy kết quả mặc định hoặc lẫn phiên.
- API dự đoán đang cho upload `.pkl`, cần bỏ cả giao diện lẫn khả năng nhận upload phía backend, không chỉ ẩn trường nhập.
- JavaScript hiện dùng biến toàn cục và truy cập DOM theo ID. Chuyển sang React cần tách vòng đời Leaflet, quản lý state và các adapter; không nhúng toàn bộ script cũ vào React rồi coi là đã tách kiến trúc.
- IndexedDB hiện có `mapPredict.workspace`, DB version 1, snapshot schema 1. Mã mới phải có kế hoạch tương thích/khôi phục, không ghi đè bản lưu cũ bằng state rỗng.
- CRS của từng dự án công khai chưa xác nhận chi tiết. Việc tách frontend/backend không giải quyết được dữ liệu định vị chưa rõ.

## 3. Trách nhiệm từng phần

### Frontend

- Điều hướng header 3 mục; `/` hiển thị Giới thiệu. Trang Đánh giá vẫn có hai chế độ Bản đồ/Dự đoán bên trong, không biến chúng thành hai mục header mới.
- Trình xem Leaflet, nền/nhãn, inspector, bảng thuộc tính/kết quả, thanh trượt màu/độ đậm, form file và phản hồi trạng thái.
- Tự lưu/khôi phục state giao diện và bản sao dữ liệu người dùng ở IndexedDB; ghi rõ phạm vi trình duyệt/origin.
- Chuẩn bị bản xem trước PDF bằng dịch vụ chụp khung nhìn, dùng ref bản đồ thay cho biến toàn cục; giữ xuất đúng vùng nhìn và attribution.
- Chỉ hiển thị dữ liệu/khả năng do API cho phép. Không giải mã pickle, chạy mô hình, đọc thư mục máy chủ hoặc dùng mã số để tự đoán vị trí ô.

### Backend

- Kiểm tra/đọc CSV, DXF/GPKG; phân tích lưới và metadata, chuyển CRS sau khi được xác nhận; ghép theo chính sách CV-04.
- Chạy mô hình/scaler do chủ máy chủ đặt sẵn; ghi phiên bản mô hình gắn với từng kết quả.
- Chuẩn bị/cấp dữ liệu ba dự án công khai qua API chỉ đọc. Excel tham khảo được xử lý bằng công cụ quản trị/chuẩn bị dữ liệu, không qua form upload cho người xem.
- Quản lý asset/result/workspace, quyền truy cập theo phiên, giới hạn tài nguyên, lỗi và trace nội bộ.
- Giữ file nguồn bất biến. Gộp trùng trong bộ nhớ, bảo toàn handle; trường hợp Phú Quốc 1232 không tô/không cảnh báo người xem nhưng giữ chẩn đoán nội bộ.

## 4. Cấu trúc mã đích đề xuất

Đây là cấu trúc dự kiến, chưa tạo scaffold. Các file mã cũ vẫn giữ nguyên cho đến khi có bước chuyển đổi được kiểm thử.

```text
backend/
  map_predict/
    __init__.py             # create_app(config)
    config.py               # đường dẫn, giới hạn, cấu hình môi trường
    api/v1/
      public.py             # nội dung nhóm, danh sách và bản đồ dự án
      workspaces.py         # phiên, tài nguyên, lưu/khôi phục metadata
      datasets.py           # CSV đầu vào và CSV kết quả chủ động nạp
      maps.py               # CAD, lưới, phân tích tọa độ, tạo bản đồ
      predictions.py        # chạy mô hình đã cấu hình
      schemas.py            # kiểm tra request/response, mã lỗi
    services/
      cad.py, grids.py, crs.py, joins.py
      prediction.py, project_data.py
    repositories/
      workspaces.py, assets.py, results.py
    storage/
      database.py, files.py, migrations/
    cli/
      prepare_projects.py   # chuẩn bị dữ liệu công khai, không mở qua API người xem
  tests/
frontend/
  src/
    app/                    # router, header, providers
    pages/                  # About, Projects, ProjectMap, Assessment
    features/
      map/                  # vòng đời Leaflet, layer, inspector, PDF
      assessment/           # upload, bảng dữ liệu, dự đoán, ghép
      workspace/            # state, IndexedDB, chuyển đổi bản lưu
    shared/
      api/                  # API client và DTO TypeScript
      ui/                   # nút, bảng, trạng thái, form dùng chung
  tests/
  package.json, package-lock.json
config/
  public_content.json       # nhóm, tầm nhìn, thành viên, danh mục
  projects.json             # manifest nguồn công khai đã được duyệt
docs/
tests/integration/
app.py                      # điểm chạy tương thích, sẽ gọi create_app sau khi chuyển
```

Không đặt file mô hình, file người dùng, database hoặc dữ liệu tham khảo thô trong `frontend/public`, `wwwroot` hay thư mục được phục vụ tĩnh. `config/projects.json` là cấu hình nội bộ; chỉ cấp các trường công khai đã lọc qua API.

## 5. URL giao diện

- `/`: Giới thiệu mặc định.
- `/projects`: danh sách đúng 4 dự án.
- `/projects/hcm`, `/projects/bac-kan`, `/projects/phu-quoc`: bản đồ kết quả có sẵn, chỉ xem.
- `/assessment`: công cụ Đánh giá quỹ đất hiện tại, bên trong chuyển Bản đồ/Dự đoán.
- Thẻ dự án AI dẫn thẳng tới `/assessment`, không tạo bản sao giao diện/dữ liệu.

Reload URL con phải trả frontend và giữ đúng trang. URL `/api/...` hoặc file tĩnh không tồn tại phải trả lỗi đúng loại, không bị SPA fallback thành trang HTML với HTTP 200.

## 6. API v1 dự kiến

### Dữ liệu công khai — không tạo workspace, không nhận upload

- `GET /api/v1/site-content`: giới thiệu, 3 ý Tầm nhìn và thông tin 4 thành viên đã xác nhận/nội dung mẫu được đánh dấu.
- `GET /api/v1/projects`: 4 mục, slug, loại dự án, URL đích và trạng thái dữ liệu.
- `GET /api/v1/projects/{slug}`: thông tin dự án, chú giải, bbox, phiên bản dữ liệu và trạng thái sẵn sàng. Slug phải có trong manifest, không dùng làm đường dẫn tùy ý.
- `GET /api/v1/projects/{slug}/map`: các layer GeoJSON đã chuẩn bị, chỉ có dữ liệu được duyệt. Mục AI không có dữ liệu bản đồ tĩnh riêng.

Dự án chưa đủ CRS/dữ liệu: metadata báo `not_ready`; endpoint map trả lỗi `PROJECT_NOT_READY`, không gửi GeoJSON giả hoặc dùng EPSG phỏng đoán. Không phát cảnh báo cho trường hợp 1232 đã được người dùng duyệt bỏ qua.

### Workspace đánh giá — có kiểm tra quyền phiên

- `POST /api/v1/workspaces`: tạo vùng dữ liệu riêng khi người dùng thực sự vào luồng đánh giá; không tự đọc `KetQua.csv` cũ.
- `GET /api/v1/workspaces/{workspace_id}`: metadata tài nguyên/kết quả thuộc đúng phiên, không đọc file kết quả toàn cục.
- `PATCH /api/v1/workspaces/{workspace_id}`: cập nhật lựa chọn hiện hành; yêu cầu revision để phát hiện ghi đè từ tab cũ.
- `POST /api/v1/workspaces/{workspace_id}/assets`: multipart gồm `file`, `role` (`base_dxf`, `grid`, `input_csv`, `result_csv`). Máy chủ sinh `asset_id`; không nhận role mô hình/scaler hoặc đường dẫn file.
- `DELETE /api/v1/workspaces/{workspace_id}/assets/{asset_id}`: gỡ tài nguyên của phiên; không xóa file gốc trên máy người dùng. Chi tiết thời điểm thu hồi file server sẽ chốt theo chính sách lưu trữ.
- `GET /api/v1/workspaces/{workspace_id}/datasets/{asset_id}/preview`: cột, tổng dòng và trang xem trước; `result_csv` phải có Y hợp lệ theo quy tắc, không tự điền thiếu bằng 0.
- `POST /api/v1/workspaces/{workspace_id}/cad-diagnostics`: `asset_id`, EPSG nguồn đã chọn; chỉ đề xuất dịch, không tự áp dụng.
- `POST /api/v1/workspaces/{workspace_id}/predictions`: `input_asset_id`; chạy bộ mô hình phía máy chủ, trả `result_id`, cột, số dòng, thống kê và `model_version`. Không nhận đường dẫn/model file từ client.
- `POST /api/v1/workspaces/{workspace_id}/joins/preview`: danh sách grid asset, result reference, cột/chế độ ghép và CRS/offset; trả thống kê/mẫu đối chiếu, không thay kết quả đang áp dụng.
- `POST /api/v1/workspaces/{workspace_id}/maps`: tạo/cập nhật bản đồ từ asset ID, `source_crs`, offset và result reference rõ ràng. Không có result thì DXF có thể chỉ hiện lưới; không fallback sang kết quả máy chủ từ phiên khác.
- `GET /api/v1/workspaces/{workspace_id}/results/{result_id}`: một trang kết quả; `GET .../results/{result_id}/export`: CSV đúng kết quả đã chọn, không xuất file chung.

Result reference phân biệt `{kind: "uploaded_csv", asset_id: ...}` với `{kind: "prediction", result_id: ...}`; xác nhận cùng workspace trước khi đọc. Endpoint map không tự chạy mô hình; upload CSV không tự áp dụng kết quả lên layer nếu chưa qua thao tác hiển thị/áp dụng.

### Quy ước hợp đồng

- JSON thành công có `data`, `meta`; lỗi có `error: {code, message, details}` và `request_id`. Không trả traceback, đường dẫn ổ đĩa hoặc nội dung mô hình cho người xem.
- 400 request sai, 404 tài nguyên không có/không thuộc phiên, 409 revision xung đột hoặc dữ liệu chưa sẵn sàng, 413 vượt dung lượng, 422 nội dung/cột dữ liệu không hợp lệ, 500 lỗi nội bộ. Thông báo tiếng Việt, mã lỗi ổn định cho frontend/agent.
- DTO chính: `Project`, `Workspace`, `Asset`, `Result`, `MapLayer`, `JoinPreview`, `Diagnostics`. `MapLayer` giữ ID ổn định, loại, bbox, phiên bản nguồn và GeoJSON; các asset được tham chiếu bằng ID, không bằng tên/đường dẫn.
- GeoJSON xuất WGS84 với tọa độ lon/lat như luồng hiện tại; giữ metadata CRS nguồn riêng. Trong workspace người dùng, một lựa chọn CRS nguồn chung áp dụng các layer theo yêu cầu hiện tại. Ba dự án công khai có cấu hình CRS riêng từng dự án, không ép dùng CRS của workspace.
- Các route/hình dạng payload là đề xuất để duyệt; sẽ có contract tests và tài liệu schema khi triển khai, không tuyên bố các endpoint này đã tồn tại.

## 7. Phiên dữ liệu, tự lưu và chống lẫn kết quả

### Phía máy chủ

- SQLite lưu `workspace`, `asset`, `result` và revision/ownership. Dữ liệu file lớn đặt trong thư mục riêng theo ID, ví dụ `%LOCALAPPDATA%/MapPredictApp/data/workspaces/<id>/`, ngoài web root; đường dẫn gốc thay được bằng cấu hình.
- Thay `RESULT_CSV` toàn cục bằng tài nguyên/kết quả theo workspace. `KetQua.csv` cũ không bị xóa và không được tự nhập vào phiên mới.
- Đề xuất phiên ẩn danh bằng cookie HttpOnly gắn với quyền workspace; kiểm tra quyền ở mọi thao tác đọc/ghi, không coi ID khó đoán là cơ chế phân quyền. Khi triển khai mạng cần HTTPS/Secure cookie, CSRF/origin checks cho thao tác ghi, giới hạn tài nguyên và xác định có cần đăng nhập.
- Ghi upload qua vùng staging, kiểm tra trước, đổi tên vào vị trí chính rồi commit metadata ready. Nếu commit lỗi, file mồ côi được dọn có kiểm soát; không trả asset ready trỏ tới file chưa tồn tại. Không ghi đè dữ liệu đúng bằng upload lỗi.
- Revision/version áp dụng cho cập nhật lựa chọn và kết quả; thao tác chạy lâu phải gắn với snapshot đầu vào, không tự thay kết quả mới hơn vừa được tab khác tạo.
- Website sẽ public, do đó kiểm thử cách ly workspace là điều kiện bắt buộc trước khi cho truy cập thật. Thời hạn lưu, quota và việc phần Đánh giá cho dùng ẩn danh hay cần đăng nhập sẽ chốt trước triển khai CV-25; không tự thêm tài khoản/đăng ký hoặc xóa dữ liệu sau một số ngày giả định.
- Trước public phải có kiểm tra quyền mọi asset/result, CSRF/origin cho ghi dữ liệu, HTTPS/cookie phù hợp, giới hạn upload/khối lượng xử lý/tần suất, timeout và chính sách thu hồi dữ liệu đã duyệt. Không coi một workspace ID khó đoán hoặc autosave IndexedDB là đủ để bảo vệ dữ liệu server. Tham khảo [hướng dẫn bảo mật Flask](https://flask.palletsprojects.com/en/stable/web-security/).

### Phía trình duyệt

- Giữ autosave IndexedDB: file/Blob, kết quả người dùng nạp/tạo, GeoJSON, màu, layer bật/tắt, CRS/offset, tâm/zoom, inspector và bảng dữ liệu; chỉ báo lưu thành công sau commit.
- Phiên đánh giá tách khỏi trạng thái xem ba dự án công khai. Xem TP.HCM không được ghi đè workspace Bắc Kạn hoặc CSV đang làm việc.
- Dùng bản sao trình duyệt để khôi phục hiển thị mà không tự chạy mô hình hoặc gọi lại API map. Nếu tài nguyên server không còn, giữ bản lưu cục bộ; giải thích cần đồng bộ/nạp lại trước thao tác server kế tiếp, không âm thầm thay bằng phiên rỗng.
- Đề xuất store/snapshot mới có migration từ version 1, giữ nguyên bản cũ để quay lại. Các file mô hình upload cũ không được khôi phục thành đầu vào mô hình hợp lệ; dữ liệu/layer khác không bị bỏ chỉ vì phần mô hình đã thay đổi.
- Giữ origin vận hành `127.0.0.1:8765` trong giai đoạn chuyển để đọc được bản lưu cũ. Frontend dev ở origin/cổng khác không tự đọc được IndexedDB cũ. Không bắt người dùng xóa dữ liệu trình duyệt để nâng cấp.
- `/` vẫn vào Giới thiệu mặc định; bản lưu đánh giá được phục hồi khi vào `/assessment`, không tự chuyển trang mở đầu sang Bản đồ trái yêu cầu.

## 8. Quản lý mô hình

- Đề xuất thư mục riêng `%LOCALAPPDATA%/MapPredictApp/models/active/`, gồm mô hình, scaler và manifest phiên bản; chủ máy chủ có thể dán file đã huấn luyện vào, không có API upload công khai.
- Tên file/manifest được chốt khi làm CV-19; kiểm tra x1–x9, bộ mô hình/scaler và môi trường tương thích trước khi dùng. Giữ môi trường scikit-learn hiện tại của dự án cho tới khi có kiểm thử tương thích, không nâng phiên bản chỉ theo tài liệu mới.
- Ghi model/scaler fingerprint và version vào kết quả. Thay mô hình không đổi nghĩa kết quả cũ và không tự chạy lại các phiên đã lưu.
- Chỉ nạp pickle/joblib đáng tin cậy từ chủ máy chủ vì chúng có thể thực thi mã khi load; việc kiểm tra đuôi file hoặc hash không làm file không tin cậy trở nên an toàn. [Hướng dẫn model persistence của scikit-learn](https://scikit-learn.org/stable/model_persistence.html).

## 9. Đồng bộ, tác vụ dài và vận hành

- Ban đầu API xử lý đồng bộ với giới hạn kích thước/độ phức tạp/thời gian được đo khi tích hợp. Không trả trạng thái thành công trước khi có kết quả và không tự retry POST dự đoán khi mạng timeout.
- Tách `PredictionService`/`MapService` khỏi route ngay từ đầu để có thể thêm worker sau. Nếu benchmark vượt giới hạn request, cần bổ sung thiết kế job có trạng thái bền vững, API polling và worker riêng trước khi nhận file lớn; không dùng `async def` hoặc thread tạm như lời hứa job bền vững.
- Chưa cần Redis/Celery/PostgreSQL chỉ để có ba trang và bốn dự án. Chỉ chọn khi khối lượng/người dùng/triển khai thực sự yêu cầu; lớp repository giúp thay storage có kiểm soát.
- Dev: Vite và Flask chạy riêng, proxy `/api` về backend để giữ cách gọi cùng origin ở frontend. Production đề xuất build frontend thành static và cùng origin API; không bật CORS `*` kèm cookie. Vite có [hướng dẫn tích hợp backend](https://vite.dev/guide/backend-integration).
- Giữ giới hạn và cấu hình rõ cho upload, số đối tượng CAD, số dòng CSV, dung lượng GeoJSON và tốc độ request. Mức mặc định sẽ chốt bằng dữ liệu/benchmark, không coi giới hạn upload 600 MB hiện tại là mức an toàn cho triển khai công khai.
- Không phục vụ bằng Flask debug server khi triển khai thật. Máy chủ/hosting, cơ chế backup, thời hạn lưu và giới hạn đồng thời được chốt ở CV-25; chưa đặt mua dịch vụ.

## 10. Khả năng mở rộng agent/chatbot

- Frontend có label/role và ID ổn định, điều khiển bàn phím, trạng thái xử lý/lỗi; map có bảng/DOM đọc được để agent không phải đoán từ canvas.
- Agent tương lai dùng cùng tầng dịch vụ và API có quyền, không truy cập filesystem hoặc cookie tài khoản chỉ vì chúng nằm trong thư mục tham khảo.
- Popup chatbot là feature độc lập làm sau; chưa gắn nhà cung cấp. Hành động thay dữ liệu phải có phạm vi workspace và xác nhận theo đặc tả CV-26.
- Không thêm `/api/run-command`, endpoint tùy ý đọc đường dẫn, chạy Python hoặc nạp pickle qua agent.

## 11. Lộ trình chuyển đổi, không ngắt hệ thống cũ

1. Duyệt CV-05, chọn stack/phạm vi phiên, chốt mẫu giao diện CV-06.
2. Khi triển khai CV-07, tách Flask factory/Blueprint và scaffold frontend tối thiểu. Giữ điểm chạy `app.py`; giao diện cũ tiếp tục dùng để so sánh và quay lại trong giai đoạn phát triển.
3. Làm trang Giới thiệu/Dự án, route/header và API công khai trước. Chưa nối dữ liệu dự án chưa duyệt CRS vào bản đồ thật.
4. Triển khai đọc/ghép/chuẩn bị dữ liệu theo CV-11 đến CV-18, có bộ mẫu và trace, không sửa nguồn DXF/Excel.
5. Chuyển không gian đánh giá, thư mục mô hình và kết quả theo phiên ở CV-19 đến CV-22. Các endpoint cũ liên quan upload mô hình/fallback kết quả phải bị chặn hoặc loại bỏ trong bản triển khai mới; không để đường vòng legacy trên deployment công khai.
6. Chạy migration bản lưu trên cùng origin với bản cũ nguyên vẹn, kiểm thử khôi phục/rollback và các luồng PDF/CSV; chỉ đổi giao diện mặc định sau khi đạt kiểm thử tương ứng.
7. Hoàn tất CV-24/CV-25 trước triển khai cho người dùng khác. Khi rollback, dữ liệu v1 còn nguyên; phiên v2 phát sinh không bị tự xóa, nhưng giao diện cũ không được hứa đọc schema mới.

## 12. Điều kiện duyệt CV-05 và nghiệm thu khi triển khai

**Trạng thái duyệt của người dùng:**

1. **Đã đồng ý:** React + TypeScript + Vite cho frontend, Flask module hóa cho backend.
2. **Đã đồng ý:** SQLite metadata + filesystem riêng + IndexedDB autosave là phương án ban đầu; chưa cần dịch vụ cloud/database khác.
3. **Đã xác nhận:** website sẽ public, thiết kế cho nhiều người truy cập và cách ly dữ liệu đánh giá. Chưa mặc định yêu cầu đăng nhập; chính sách truy cập phần Đánh giá, quota, thời hạn lưu và tải đồng thời sẽ chốt trong CV-25 trước triển khai thật.

CV-05 hoàn thành phần thiết kế nền tảng, đủ để sang CV-06. Các quyết định vận hành public còn mở đã chuyển thành điều kiện bắt buộc ở CV-25, không coi hệ thống hiện tại đã sẵn sàng đưa lên Internet. Kiểm thử ở các bước triển khai phải chứng minh:

- Route đúng trang mặc định/header; reload URL con hoạt động và API không bị trả nhầm HTML.
- Ba dự án chỉ đọc không cần upload hoặc chạy AI; không trộn dữ liệu với workspace cá nhân.
- Phiên mới không tự nạp `KetQua.csv`; upload CSV kết quả được lưu/khôi phục và export đúng dữ liệu.
- Hai phiên không đọc/ghi/xuất được kết quả của nhau, ID giả/đường dẫn tùy ý bị từ chối; tab cũ không ghi đè revision mới.
- API từ chối upload mô hình kể cả khi gọi thẳng; model/scaler không xuất hiện trong static/frontend bundle.
- Bản lưu v1 được giữ; migration không mất layer/file người dùng hoặc khôi phục model upload đã bị loại bỏ.
- MTEXT, gộp trùng, ghép số, bảng màu, ô không xét và 1232 tuân thủ CV-04; EPSG chưa xác nhận không được âm thầm gán.
- PDF/CSV, hiển thị layer, màu/độ đậm và lỗi tile vẫn được kiểm thử, không chỉ kiểm tra giao diện khung.

Lần soạn này chỉ đọc mã/tài liệu và viết thiết kế. Chưa tạo API v1, frontend React, database, migration hay phiên server mới; chưa cài package hoặc khởi động lại ứng dụng.
