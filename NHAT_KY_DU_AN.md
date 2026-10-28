# Nhật ký dự án MapPredictApp

## 2026-10-28 Rút gọn cụm local theo yêu cầu

- Người dùng xác nhận chỉ thử nghiệm production giả lập trên máy, chưa dùng VPS, có backup riêng và không cần snapshot hoặc nhiều phiên chạy
- Bỏ blue/green, chỉ giữ một web và một AI, CI tiếp tục cập nhật trực tiếp sau khi kiểm thử đạt
- Đưa Qdrant vào cùng Compose project, chuyển dữ liệu sparse sang named volume thay cho writable layer của container ngoài
- Đối chiếu đầy đủ SHA-256 payload/vector của 807 point trong 6 collection, tất cả khớp
- Container Qdrant nguồn đã được xóa sau đối chiếu, snapshot do agent tạo lần trước cũng đã được xóa ở máy và Qdrant
- Không tạo snapshot mới, tệp truyền tạm được xóa sau khi chuyển xong, volume chiếm khoảng 54 MiB thực
- Cấu hình cập nhật mới chấp nhận gián đoạn ngắn, không giữ bản dự phòng và không tự rollback

## 2026-10-28 Service AI riêng, Qdrant và xuất DXF

- Đã đọc dự án Thuchanh, xác định CSDL-Datdai có 5 point, vector 1024 chiều và model qwen3-embedding:0.6b
- Khởi động Qdrant có sẵn, giữ nguyên collection, tạo snapshot riêng khoảng 2 MiB vì container cũ chưa có volume
- Tách gateway web và tiến trình AI theo slot blue/green, xác thực nội bộ và không mở cổng AI ra host
- Prompt chuyển thành file cấu hình, có quyền đề xuất sửa DXF và phân biệt quy tắc Qdrant với bằng chứng hiện trạng
- Truy xuất dense thật, fallback từ khóa có nhãn rõ ràng khi embedding không sẵn sàng, không thay model hoặc reindex
- Thêm xuất DXF binary từ bản xem trước và giữ liên kết xuất sau khi áp dụng, file gốc và workspace chỉ đổi theo thao tác được chọn
- 114 kiểm thử Python đã đạt trên Windows và Linux trước các kiểm thử bổ sung về kiểu số và căn cứ Qdrant
- Đã chạy thật xuyên qua gateway web và AI riêng, xuất DXF attachment hợp lệ 15380 byte, áp dụng đúng x4 = 9 và giữ ID point Qdrant cho L9

## 2026-10-27 Trợ lý GIS cho dự án thứ tư

- Người dùng chốt dùng server Gemini trong tài liệu tham khảo và xem trước rồi áp dụng
- Thêm cửa sổ nổi trong công cụ Đánh giá quỹ đất, chọn DXF/CSV, lịch sử riêng trên trình duyệt và dẫn nguồn
- Sửa màu/layer/chữ/dịch đối tượng trên bản sao, đề xuất điểm x1..x9 theo tiêu chí gốc, không tự chọn điểm từ ô gộp
- Xem trước có chữ ký và hash file, thay file hoặc hết hạn phải tạo lại, không lưu upload chung
- Thêm Gemini adapter vào mạng Docker riêng, không dùng cookie/tài khoản từ thư mục tham khảo
- Đã thử Gemini thật: đọc DXF tổng hợp, đề xuất và áp dụng màu, lấy nguồn ezdxf có trích dẫn đối chiếu được
- Đã thử đề xuất x4 = 9 theo ô L9 trên CSV tổng hợp và áp dụng đúng điểm, Y cũ được loại bỏ
- 106 kiểm thử Python và ba kiểm thử DOM assistant đã đạt, chưa kiểm tra trực quan do không có trình duyệt điều khiển khả dụng

## 2026-10-27 Chuẩn bị tự triển khai trên VPS Linux

- Giữ tác vụ Windows hiện có, chuyển initialize/start/deploy sang Python dùng chung cho Windows và Linux
- Trình cập nhật chỉ triển khai main trùng SHA deploy-ready sau khi CI đạt, giữ kiểm tra workspace sạch và fast-forward
- Bổ sung cài đặt systemd gồm stack khởi động theo VPS và timer cập nhật mỗi năm phút, không thêm container thường trực
- Các lệnh PowerShell cũ chuyển thành wrapper gọi Python, giữ nguyên cổng và cơ chế chuyển slot
- Kiểm thử lỗi candidate, rollback proxy và giữ slot cũ trong khi request đang xử lý
- Chưa có VPS để cài thực tế, hướng dẫn chuyển dữ liệu và cấp token tại docs/DOCKER_DEPLOYMENT.md
- 96 kiểm thử đạt trên Windows và 96 kiểm thử đạt trong container Linux, CI bổ sung xác minh cú pháp unit bằng systemd-analyze

## 2026-10-27 Tự triển khai sau CI

- Thêm job deploy-ready chỉ đánh dấu commit main sau khi kiểm thử và đóng gói thành công
- Cài Windows Task Scheduler MapPredictApp-AutoDeploy, kiểm tra mỗi năm phút rồi thoát, không thêm container thường trực
- Không cần API token hay webhook, kiểm tra tín hiệu CI bằng Git remote refs
- Chỉ triển khai main khớp tín hiệu CI, workspace sạch và Git fast-forward được tới đúng SHA
- Ghi revision đang chạy, xoay log và giữ quy trình chuyển slot, dữ liệu cùng tunnel hiện có
- Sáu kiểm thử mới cho điều kiện cho phép triển khai, bỏ qua code chưa commit và không ghi thành công khi build lỗi

## 2026-10-27 Tinh gọn stack Docker

- Bình thường chỉ chạy một backend cùng Nginx và Cloudflared, frontend là file tĩnh
- Slot dự phòng chỉ bật lúc triển khai, dừng và gỡ sau khi Nginx xử lý xong request cũ
- Một Gunicorn worker với hai thread, một Nginx worker, giới hạn luồng thư viện số học
- Image ứng dụng giảm từ 837255739 byte xuống 617451381 byte
- Mẫu đo RAM của ba container khoảng 224 MiB sau nạp bản đồ và dự đoán, trước thay đổi khoảng 583 MiB
- 84 kiểm thử Python đạt trong image production tinh gọn, giữ dữ liệu nguồn và cổng 8765
- Bổ sung tools/start_docker.ps1 để khởi động riêng slot đang hoạt động
- CI kiểm tra thêm toàn bộ test Python trong image production

## 2026-10-27 Xác minh bản Docker cuối cùng

- Mã nguồn cấu hình 31c2920472ba4a0c57828c06fe21409a0612f337 đã được push lên main
- Lần chạy GitHub Actions 40478081017 đạt đủ Windows, Ubuntu, Docker image, kiểm tra Compose và job delivery
- Artifact MapPredictApp-31c2920472ba4a0c57828c06fe21409a0612f337 đã được tạo thành công
- Slot đang phục vụ trên máy là blue sau lần thử chuyển về từ green, proxy và tunnel vẫn giữ nguyên ID container
- Bổ sung mount chỉ đọc cho config và wwwroot/image để sửa nội dung hoặc thay ảnh rồi reload mà không phải rebuild
- Kiểm tra cuối stack đang chạy, các slot và proxy healthy, Cloudflare báo tunnel healthy, cổng host chỉ bind 127.0.0.1:8765
- Không có API token, tunnel token, dotenv hoặc cấu hình sinh tự động nào được đưa vào Git

## 2026-10-27 Triển khai Docker và Cloudflare Tunnel trên máy hiện tại

- Người dùng cung cấp API token và tên miền danhgiaquyhoach.top, cho phép cấu hình tunnel và triển khai trên máy này
- Tạo tunnel riêng cho MapPredictApp cùng bản ghi DNS mới, không thay tunnel hoặc container của dự án khác
- Dùng Compose project map-predict gồm proxy Nginx cố định, hai slot Gunicorn blue/green và cloudflared
- Chuyển cổng 8765 từ tiến trình Flask cũ sang Nginx sau khi kiểm tra ứng dụng Docker tại cổng tạm 8766
- Mount model và nguồn ba dự án chỉ đọc, giữ dữ liệu trình duyệt, token riêng không nằm trong Git hoặc Docker image
- Thêm kiểm tra Origin cho legacy, hỗ trợ HTTPS qua proxy, cấu hình giới hạn upload cho stack và kiểm thử tương ứng
- Đã chạy dự đoán trên tên miền qua trình duyệt, đọc đúng số ô của cả ba dự án và xác minh hai API qua proxy
- Thử triển khai blue sang green, giữ nguyên container proxy/tunnel và cổng host, 335 lần kiểm tra health đều trả 200
- Thêm script khởi tạo và cập nhật có kiểm tra sức khỏe trước chuyển lưu lượng, không cần compose down khi đổi code
- 84 kiểm thử Python đạt, bổ sung job xác minh Docker image vào GitHub Actions
- Cấu hình và dữ liệu riêng giữ local, chi tiết vận hành ở docs/DOCKER_DEPLOYMENT.md

## 2026-10-27 Đã push GitHub và xác minh CI thành công

- Đã commit và push lên main của NguyenKhoa1290/MapPredictApp, commit mã nguồn 7acf8b4dced76650415d1ef9db41bf6275a91433
- Lần chạy Actions 40472565755 đã đạt cả Verify on windows-latest, Verify on ubuntu-latest và Deliver verified application
- Artifact MapPredictApp-7acf8b4dced76650415d1ef9db41bf6275a91433 đã được tạo, ID 12719492301, giữ 14 ngày
- Kiểm tra bản sao chỉ có file theo dõi Git đã đạt build, 38 kiểm thử frontend, 30 Node và bộ Python với hai kiểm thử dữ liệu riêng được bỏ qua rõ lý do
- Kiểm thử local có đủ nguồn dự án đã đạt toàn bộ 81 kiểm thử Python, gói ZIP giải nén chạy được với pipeline và nhận biết dữ liệu dự án chưa cấp riêng
- Không còn venv, node_modules, bộ ODA cài sẵn hoặc Tailieuthamkhao nằm trong Git index, các thư mục local vẫn nguyên vẹn
- Đây là tự động kiểm thử và phân phối gói build, chưa có máy chủ để tự triển khai web public
- Bản cập nhật nhật ký và tài liệu sau xác minh không đổi mã nguồn, dùng commit skip ci để tránh chạy lặp lại cùng bộ mã đã đạt

## 2026-10-27 Chuẩn bị đồng bộ GitHub và CI

- Theo yêu cầu đưa mã lên GitHub, dùng origin NguyenKhoa1290/MapPredictApp và nhánh main đã cấu hình
- Mở rộng gitignore, giữ nguyên quy tắc bỏ qua toàn bộ Tailieuthamkhao do người dùng vừa bổ sung
- Bỏ theo dõi venv, bytecode, bộ cài ODA và ảnh render cũ trên Git, không xóa môi trường đang dùng trên máy
- Thêm workflow kiểm thử và build Windows/Ubuntu, tạo artifact ZIP và kiểm tra ứng dụng sau giải nén
- Hai kiểm thử cần nguồn dự án thật báo skipped khi không có dữ liệu riêng, trên máy local vẫn kiểm tra đầy đủ
- Gói build chứa pipeline và giao diện, không chứa thư mục tham khảo, file cấu hình riêng, môi trường hoặc bộ chuyển đổi ODA
- Chưa thiết lập tự triển khai lên hosting vì người dùng đang ưu tiên bản local
- Chi tiết quy trình tại docs/GITHUB_ACTIONS.md

## 2026-10-27 Căn chữ theo chiều rộng ảnh thành viên

- Áp dụng chiều rộng 85% và giới hạn 220 px cho cả thẻ thành viên thay vì chỉ ảnh
- Ảnh vuông chiếm toàn bộ chiều rộng thẻ, tên và đoạn giới thiệu thẳng hai mép với ảnh

## 2026-10-27 Thu nhỏ ảnh thành viên và dùng khung vuông

- Khung avatar chiếm 85% chiều rộng thẻ, tối đa 220 px và có tỷ lệ 1:1
- Giữ object-fit contain để ảnh không bị cắt khi đổi kích thước màn hình
- Cập nhật hướng dẫn thay ảnh thành viên với kích thước khuyến nghị 600 × 600 px

## 2026-10-27 Dọn file không còn dùng

- Theo yêu cầu dọn dự án, chuyển 51 file cũ tổng 14 880 724 byte sang F:\APP\MapPredictApp_cleanup_20261027 để có thể khôi phục
- Lệnh xóa vĩnh viễn bị bộ kiểm duyệt tự động từ chối trước khi thực thi, đã dùng cách lưu trữ ngoài thư mục dự án
- Dọn ONNX, model/scaler cũ, pipeline trùng, prototype và kiểm thử prototype, bộ cài MSI cùng cache và ảnh render tạm
- Không còn mã nguồn C# hoặc project/solution .NET trong phạm vi mã dự án, giữ các DLL và chương trình ODA còn được GIS tham chiếu
- Giữ dữ liệu GIS và workbook gốc, Tailieuthamkhao, mô hình pipeline hiện hành, tài liệu và nhật ký, log máy chủ và các tính năng đang hoạt động
- Chuyển ảnh bằng chứng và PDF kiểm tra sang docs/verification, cập nhật đường dẫn tài liệu và kiểm thử mô hình
- Bản pipeline trùng có cùng SHA-256 với bản hiện hành trước khi chuyển, không đổi phiên bản mô hình
- Build đạt, 81 kiểm thử Python, 38 kiểm thử frontend và 30 kiểm thử Node đạt, API mô hình trên máy chủ trả ready
- Danh sách chi tiết tại docs/cleanup-20261027.json và hướng dẫn tại docs/CLEANUP_20261027.md

## 2026-10-27 Ưu tiên hoàn thiện bản local

- Người dùng chưa có hosting và chọn hoàn thiện bản local trước
- Đã ghi quyết định vào note, để việc triển khai public và lựa chọn hạ tầng sang giai đoạn sau
- Giữ quyết định dùng không cần đăng nhập, không thay đổi chức năng hoặc dữ liệu của ứng dụng trong lần cập nhật này

## 2026-10-27 Chốt sử dụng không cần đăng nhập

- Người dùng chọn phần Đánh giá quỹ đất dùng không cần đăng nhập
- Cập nhật CV-25 và các điểm còn mở trong note, tiếp tục giữ bản lưu riêng trên trình duyệt và xử lý file theo request
- Chưa thêm lưu chung trên máy chủ, chưa đồng bộ qua thiết bị, chưa triển khai public
- Các lựa chọn còn cần cho triển khai là môi trường, hạn mức, số người đồng thời và chính sách lưu/xóa

## 2026-10-27 Hoàn thiện ghép kết quả và tự lưu của công cụ chính

- Hoàn thành CV-21 trên giao diện legacy, chọn ghép chính xác hoặc phần số duy nhất, xem báo cáo rồi xác nhận áp dụng lên bản đồ
- DXF và GPKG dùng cùng bộ ghép bảo thủ, mã trùng hoặc mơ hồ không tự ghép, Y thiếu hoặc sai chỉ hiện đường lưới
- Giữ thuộc tính nguồn, thêm thông tin phương thức ghép và tối đa 20 mẫu đối chiếu, không sửa file người dùng
- Hủy bản xem trước khi nguồn hoặc thiết lập thay đổi, chặn phản hồi đến muộn và giữ layer đã áp dụng khi xem trước lỗi
- Sửa đường dùng kết quả vừa chạy dự đoán khi ghép, không cần reload trước
- Hoàn thành CV-22 trong phạm vi giữ legacy, bổ sung lưu cách ghép, giữ file và GeoJSON đã áp dụng cùng khung nhìn, không thay database phiên CSV riêng
- Kiểm thử đạt 84 Python, 37 frontend ở lần chạy toàn bộ và 6 kiểm thử workflow ở lần kiểm tra cuối sau bổ sung hồi quy đổi CRS, tổng cộng 38 frontend, cùng 36 Node
- HTTP máy chủ thực đi qua pipeline và ghép GPKG bằng phần số đạt, không tạo kết quả dùng chung
- Trình duyệt thực nạp lưới tổng hợp và CSV, xem trước không tạo layer, áp dụng tô đúng 1/3 ô và reload giữ layer cùng cách ghép, không ghi nhận lỗi JavaScript
- Kiểm tra DOM ở kích thước nhỏ không tràn ngang, avatar giữ contain, chụp toàn trang nhỏ chưa thành công nên chưa nghiệm thu trực quan đầy đủ
- Đã cập nhật note và docs/CV21_GHEP_KET_QUA.md, khởi động lại máy chủ local tại 127.0.0.1:8765
- Chưa xác nhận vị trí ba dự án, chưa triển khai public hoặc tích hợp chatbot khi chưa có lựa chọn tương ứng

## 2026-10-26 Avatar khi thay đổi kích thước trình duyệt

- Thay khung avatar có chiều cao cố định theo breakpoint bằng khung tỷ lệ 5:6 co theo chiều rộng thẻ
- Dùng object-fit contain để luôn giữ đầy đủ ảnh, không cắt chân dung khi đổi kích thước màn hình

## 2026-10-26 Chuyển nội dung nháp sang thành viên

- Khôi phục hai đoạn giới thiệu ban đầu, giữ cách căn đều hai lề
- Thêm đoạn Lorem ipsum dưới từng thành viên, chỉnh tại members[].bio trong config/public_content.json
- Build và 32 kiểm thử đạt, API trả đủ nội dung giới thiệu cho bốn thành viên

## 2026-10-26 Căn đều đoạn văn giới thiệu

- Căn đều hai lề cho nội dung giới thiệu, mô tả đầu trang và ba ý tầm nhìn, dòng cuối giữ căn trái
- Thêm khoảng cách đoạn và tăng giãn dòng để văn bản dễ đọc
- Nội dung giới thiệu gồm ba đoạn, hai đoạn Lorem ipsum để thay sau tại trường intro trong config/public_content.json
- Dùng ký tự \n\n trong chuỗi JSON để tách đoạn, không cần chèn thẻ HTML
- Build và 32 kiểm thử đạt, API trả đủ ba đoạn nội dung

## 2026-10-26 Ảnh giao diện thay trực tiếp và nội dung hiển thị

- Chuyển mũi tên Về trang giới thiệu sang trái và đặt trước nhãn
- Bỏ nhãn bản thử nghiệm cùng các dòng thông báo nội dung đang chờ hoàn thiện trên trang giới thiệu và footer
- Tạo 9 ảnh JPG nháp trong wwwroot/image, nối vào ảnh đầu trang, bốn dự án và bốn thành viên
- Giữ URL ảnh cố định, máy chủ trả no-cache để thay file cùng tên rồi tải lại trang mà không cần build lại
- Hướng dẫn thay ảnh tại wwwroot/image/README.md
- Build và 32 kiểm thử đạt, cả 9 ảnh trả HTTP 200 với kiểu image/jpeg

## 2026-10-26 Điều chỉnh mũi tên, số lượng và nút

- Bỏ mũi tên chéo ở các hành động phụ, giữ cạnh Đánh giá quỹ đất và Về trang giới thiệu với khoảng cách ngắn hơn
- Bỏ số lượng khỏi các nút lọc, chuyển thành dòng chữ dưới cùng danh sách dự án
- Thêm viền cho hành động nền trong suốt và bỏ gạch chân khi rê chuột lên nút ở portal và tên layer legacy

## 2026-10-26 Cải thiện chuyển zoom của bản đồ

- Bật lại chuyển động zoom và phép biến đổi CSS 3D trong vùng bản đồ, cấu hình dùng chung cho legacy và trình xem dự án
- Cho zoom lẻ, giảm nửa mức khi bấm nút, giảm độ nhạy cuộn và giữ thêm vùng canvas để thu nhỏ không hụt viền lưới
- Giữ nền cũ trong lúc tải nền mới, buffer có giới hạn và cập nhật tile ở cuối cử chỉ zoom
- Kiểm thử raster và canvas dùng cùng tỷ lệ trong animation, giữ điểm dưới chuột và cập nhật hình học đúng sau zoom
- Build đạt, 32 kiểm thử React/Leaflet, 16 kiểm thử Node nền/PDF và kiểm thử route legacy đạt, chi tiết tại [MAP_MOTION.md](docs/MAP_MOTION.md)

## 2026-10-26 Ẩn trạng thái tự lưu thường lệ

- Theo yêu cầu, ẩn dòng thông báo đang lưu, đã lưu và khôi phục phiên của công cụ Đánh giá, không chiếm thêm hàng trong thanh công cụ
- Cơ chế tự lưu ngầm giữ nguyên, chỉ hiện thông báo khi lưu hoặc khôi phục gặp lỗi

## 2026-10-26 Giữ công cụ legacy và dùng pipeline một file

- Theo yêu cầu mới, Đánh giá quỹ đất dùng lại công cụ legacy trong phần nội dung, giữ header luôn hiện và footer chung của website
- Nhúng legacy cùng origin để giữ nguyên CSS, Leaflet và các chức năng layer, CSV, dự đoán, tự lưu và PDF, không trộn script toàn cục với trình xem dự án React
- `/` mở trang Giới thiệu, `/legacy/` dẫn về `/portal/assessment`, tài liệu nội bộ trong trang dùng `/legacy/?embedded=1`
- Giữ database `mapPredict.workspace` của công cụ legacy, database CSV giao diện trước được giữ và còn truy cập ở `/portal/assessment/csv`
- Kiểm tra file `rf_model_rating_pipeline.pkl` là sklearn Pipeline với StandardScaler và RandomForestClassifier, nhận x1 đến x9 và trả nhãn 0, 1, 2
- Dùng bản sao cố định tại `models/rf_model_rating_pipeline.pkl`, gọi pipeline.predict trên dữ liệu gốc, không chuẩn hóa thêm lần nữa ở API
  - Build đạt, 76 kiểm thử Python và 30 kiểm thử React đạt, HTTP dự đoán ở API legacy và v1 đều trả 200 cùng phiên bản pipeline mới
  - Iframe được giữ khi chuyển mục rồi quay về để phiên làm việc liền mạch, chi tiết tại [LEGACY_PIPELINE.md](docs/LEGACY_PIPELINE.md)
- Tiếp tục giữ ba dự án riêng và EPSG:9208 ở trạng thái xem thử, người dùng sẽ chốt vị trí sau

## 2026-10-26 Header luôn hiện và khung trang thống nhất

- Theo yêu cầu, header của các trang React bám trên cùng khi cuộn, dùng chung xuyên suốt Giới thiệu, Dự án và Đánh giá
- Đo chiều cao header khi đổi kích thước màn hình để nội dung neo và bản đồ chừa đúng khoảng, header nằm ngoài viewport Leaflet và không che thanh điều khiển
- Khung trang có chiều cao tối thiểu theo màn hình, footer nối với phần nội dung, chuyển trang giữ nguyên header và trạng thái điều hướng

## 2026-10-26 Hoàn thành CV-20 và phần tự lưu CSV của CV-22

- Có nạp CSV kết quả do người dùng chủ động chọn, giữ Y trống là Chưa có dữ liệu, không chạy AI khi nạp kết quả
- Tự lưu file, bảng đầu vào/kết quả, nguồn kết quả, phiên bản mô hình, tab và trang bảng vào database IndexedDB riêng, reload không POST lại dữ liệu hoặc tự dự đoán
- CSV lỗi giữ kết quả tốt trước đó, gỡ file/kết quả được lưu, giao dịch lỗi rollback và tab cũ không ghi đè revision mới
- Bỏ đọc, ghi và export file kết quả mặc định từ máy chủ ở cả luồng cũ, file thật trên đĩa được giữ nguyên
- Build đạt, 75 kiểm thử Python, 30 kiểm thử React/Leaflet/IndexedDB và 34 kiểm thử Node đạt
- Việc chốt vị trí ba lưới vẫn để người dùng quyết định sau, bước tiếp theo là CV-21 ghép dữ liệu với lưới đánh giá
- Giới hạn kiểm tra và phạm vi chuyển bản lưu tại [CV20_KET_QUA_VA_TU_LUU.md](docs/CV20_KET_QUA_VA_TU_LUU.md)

## 2026-10-26 Hoàn thành CV-19

- Giữ việc chốt vị trí ba lưới để người dùng quyết định sau, tiếp tục dùng 9208 ở trạng thái xem thử
- Đặt bộ mô hình cố định tại `models`, chặn upload model/scaler và đường dẫn qua API mới lẫn API cũ, bỏ ô chọn mô hình và không khôi phục ô đó từ bản lưu cũ
- Trang Đánh giá mới có nạp CSV, xem trước, chạy dự đoán, bảng kết quả phân trang và xuất CSV đúng kết quả hiện tại, kèm mã phiên bản mô hình
- API dự đoán mới xử lý riêng từng request và không ghi file kết quả chung, có giới hạn CSV/request/số dòng và lỗi rõ ràng
- Chưa nối ghép lưới ở trang Đánh giá và chưa tự lưu kết quả mới qua reload, tiếp tục ở CV-20/CV-21/CV-22
- Chi tiết tại [CV19_MO_HINH_CO_DINH.md](docs/CV19_MO_HINH_CO_DINH.md)

## 2026-10-26 Hoãn chốt vị trí ba lưới và tiếp tục CV-19

- Người dùng sẽ chốt vị trí và hệ tọa độ của ba lưới dự án sau
- Giữ EPSG:9208 ở trạng thái xem thử, chưa đánh dấu nghiệm thu vị trí và không tự suy đoán thêm phép dịch
- Tiếp tục CV-19 với mô hình cố định trên máy chủ và nối luồng dự đoán vào trang Đánh giá quỹ đất

## 2026-10-26 Cập nhật cách trình bày chữ và nhãn dữ liệu

- Đổi nhãn Không tô màu, Không tô và nhóm không có Y thành Chưa có dữ liệu ở chú giải, danh sách ô và phần thông tin ô
- Bỏ letter-spacing âm ở tiêu đề và giãn rộng ở nhãn nhỏ, thống nhất font Segoe UI với font dự phòng Arial cho các trang mới và công cụ hiện tại
- Thêm stylesheet chữ dùng chung cho Giới thiệu, Dự án và Đánh giá, tăng cỡ chữ chú thích và nhãn nhỏ để dễ đọc hơn
- Rút gọn nội dung hiển thị, bỏ dấu chấm ở tiêu đề và nhiều nhãn, thay em-dash và dấu chấm phẩy trong các thông báo đã rà soát
- Nhãn của nhóm thiếu dữ liệu ở công cụ cũ được đổi ở lớp hiển thị, giữ khóa nội bộ để bản lưu và cách tô đã chỉnh không mất liên kết

## 2026-10-26 — Về layer và tải lại nền

- Đổi điều khiển zoom toàn lưới thành nút nổi bật “Về layer”, luôn ở góc bản đồ; dừng chuyển động và đưa khung nhìn về toàn bộ lưới ở mức tối đa 18. Thêm “Tải lại nền” để thử tải lại các tile, không nạp lại dữ liệu lưới/nhãn.
- Trình xem React dùng lại `wwwroot/basemaps.js`: ảnh vệ tinh thiếu tại mức hiện tại thử ảnh mức thấp hơn có giới hạn; zoom sâu cắt/phóng đúng phần ảnh thay vì yêu cầu tile ngoài mức 19. Cảnh báo tile được cập nhật khi tải được hoặc tile rời khung nhìn.
- Build đạt, 12 kiểm thử React/Leaflet và 9 kiểm thử ảnh nền đạt. Kiểm thử mới đưa map ra xa/zoom 22 rồi quay về đúng bounds, và bảo đảm tải lại nền không tạo lại map hoặc bỏ layer. Kiểm thử tile mô phỏng, không bảo đảm kết nối mạng thực tế.

## 2026-10-26 — Đồng bộ zoom layer ở trang dự án mới

- Theo phản hồi người dùng, tắt animation zoom của trình xem mới và cập nhật lại hình học các ô đang hiển thị khi `zoomend`/`viewreset`; nền và lưới tiếp tục dùng cùng Leaflet map/CRS.
- Chặn CSS SVG tổng quát làm đổi kích thước renderer dự phòng của Leaflet. Giữ popup tên lô và thông tin thanh bên.
- Thêm kiểm thử tích hợp với Leaflet thật trong jsdom (kích thước DOM/canvas được giả lập): phóng/thu kích thước ô, ẩn–zoom–hiện, popup/chọn ô và zoom vượt mức ảnh nền 19. Không dùng kết quả này để khẳng định đã kiểm tra trực quan trên máy người dùng.
  - Kết quả: build TypeScript/Vite đạt; 10 kiểm thử React/Leaflet đạt. Bản build mới được phục vụ ở `/portal/projects/hcm` với HTTP 200.

## 2026-10-26 — Popup tên lô đất và thông tin thanh bên

- Bấm ô ở bản đồ dự án mở popup nhỏ hiển thị mã dữ liệu (hoặc mã lưới khi chưa ghép), đồng thời vẫn chọn ô và cập nhật thông tin chi tiết ở thanh bên.
- Tên hiển thị bằng text DOM; không diễn giải tên lô thành HTML. Popup không tự dịch khung nhìn, có nút đóng, chỉ xuất hiện khi chọn ô.

## 2026-10-26 — Sửa trang dự án thành bản đồ xem dữ liệu có sẵn

- Người dùng xác nhận ba dự án là trang bản đồ riêng, khác luồng AI ở chỗ không thêm layer/Excel hoặc chạy mô hình. Đã thay placeholder chi tiết bằng trình xem Leaflet, tự đọc DXF–Excel trên máy chủ và tô màu theo Y.
- Có nền đường phố/vệ tinh, bật/tắt lưới, độ đậm, chú giải lọc nhãn, zoom toàn lưới và thông tin ô. Header/thanh bên nằm ngoài phần viewport Leaflet.
- Đã xử lý MTEXT theo attachment cho nguồn số thuần, khóa ghép số duy nhất, BK1–20 không tô, gộp hình học Phú Quốc trùng hoàn toàn và giữ handles; không sửa nguồn hoặc chạy AI.
- Người dùng yêu cầu thử 9208: mặc định EPSG:9208 ở trình xem và API, vẫn ghi rõ chưa xác nhận phép chiếu thực tế. Cho đổi CRS/lưới gốc để kiểm tra; chưa khẳng định đúng địa phương.
- Cấu trúc, số ô, API và giới hạn: [PROJECT_MAP_VIEWER.md](docs/PROJECT_MAP_VIEWER.md). Thông tin khung/409 trong bản ghi CV-07 bên dưới mô tả giai đoạn trước thay đổi này.

## 2026-10-26 — Triển khai khung CV-07

- Thêm React/TypeScript/Vite tại `frontend`, Flask factory và API đọc `/api/v1` tại `backend/map_predict`. Nội dung và danh mục lấy từ JSON cấu hình; không đưa file nguồn/mô hình vào API công khai.
- Giao diện tại `/portal/`: header ba mục, Giới thiệu, danh sách bốn dự án/bộ lọc, chi tiết địa phương và khung Đánh giá hai tab. Các URL trực tiếp/reload và JS/CSS đã kiểm tra HTTP 200.
- Chuyển các route cũ sang Blueprint tương thích; `/` và `/legacy/` vẫn mở công cụ cũ. Factory độc lập không đăng ký API cũ. Đã khởi động lại các tiến trình ứng dụng local đã xác minh để phục vụ mã mới.
- Build TypeScript đạt; 61 kiểm thử Python, 6 React và 34 Node đạt. Chưa QA trực quan/responsive, chưa nối bản đồ thật hoặc luồng dự đoán mới; không tuyên bố CV-06/CV-07 đã nghiệm thu.
- Hướng dẫn và phạm vi còn lại: [CV07_TRIEN_KHAI_KHUNG.md](docs/CV07_TRIEN_KHAI_KHUNG.md). Chưa triển khai public, SQLite/workspace, chuyển đổi bản lưu hoặc chính sách mô hình/kết quả mới.

## 2026-10-26 — Dựng bản xem trước CV-06

- Theo yêu cầu bắt đầu, tạo `wwwroot/preview/index.html`, `preview.css`, `preview.js`: giao diện trắng/xanh lá theo định hướng, header 3 mục, trang Giới thiệu, danh sách 4 dự án có lọc, 4 vị trí thành viên và mẫu Đánh giá với 2 tab.
- Dùng sơ đồ SVG tự vẽ, ghi rõ minh họa; không dùng dữ liệu địa phương giả để khẳng định kết quả thật. Các thông tin nhóm/thành viên đang chờ được đánh dấu rõ.
- Prototype không gọi API/ghi IndexedDB, không nhận file/chạy AI; nút công cụ cũ mở tab riêng. Không sửa app.py/giao diện cũ, không cài React/Vite trong bước duyệt mẫu.
- Đã kiểm tra cú pháp JS, HTTP/static assets, 6 kiểm thử logic DOM giả lập và 3 kiểm thử Python. Chưa có kết nối trình duyệt để kiểm tra trực quan; chưa tuyên bố đã QA responsive. CV-06 chờ người dùng duyệt.
- Khởi động ứng dụng cục bộ ở `127.0.0.1:8765`; bản xem trước tại `/static/preview/index.html`. Không mở dịch vụ public hoặc đổi mạng/hosting.

## 2026-10-26 — Tham khảo được DC Solution cho CV-06

- Theo yêu cầu thử lại, đã đọc được nội dung trang chủ `https://dcsolution.vn/`, trang Sứ mệnh và Dự án; HTTP trang chủ trả 200. Trang giới thiệu chi tiết có lần timeout. Chưa xác nhận bằng ảnh chụp/toàn bộ thao tác responsive.
- Tham khảo cách chia nội dung và danh mục, đối chiếu style trắng/xanh lá và font Inter trong CSS ứng dụng. Soạn [định hướng CV-06](docs/CV06_DINH_HUONG_GIAO_DIEN.md), cập nhật note ở trạng thái chờ duyệt mẫu.
- Không sao chép nguyên layout/ảnh/thương hiệu, không gửi form hoặc sửa website tham khảo. Chưa sửa ứng dụng, tạo frontend React hoặc đánh dấu CV-06 hoàn thành.

## 2026-10-26 — Chốt phạm vi public, hoàn thành thiết kế CV-05

- Người dùng xác nhận website sẽ public. Kiến trúc cần hỗ trợ nhiều người truy cập: dữ liệu ba dự án xem chung, file/kết quả đánh giá thuộc workspace riêng, không tự công khai.
- Đã ghi quyết định vào CV-05 và note, đánh dấu hoàn thành phần thiết kế nền tảng. Chính sách đăng nhập/ẩn danh, hạn mức, thời hạn lưu và tải đồng thời phải được chốt trước triển khai CV-25; chưa tự thêm yêu cầu tài khoản.
- Bổ sung điều kiện kiểm thử cách ly phiên và kiểm soát tài nguyên trước khi public. Chỉ sửa tài liệu; chưa triển khai lên mạng, thuê hosting hoặc thay ứng dụng. Tiếp theo CV-06: mẫu giao diện.

## 2026-10-26 — Người dùng đồng ý phương án CV-05

- Đã ghi nhận đồng ý frontend React/TypeScript/Vite, backend Flask module hóa và phương án SQLite metadata + filesystem + IndexedDB.
- Câu trả lời chưa xác định dùng cá nhân hay chia sẻ nhiều người; giữ mục này chờ xác nhận, không tự chọn cơ chế đăng nhập/phân quyền. CV-05 chưa đóng hoàn toàn.
- Chỉ cập nhật note và trạng thái thiết kế; chưa chuyển đổi mã, cài package hoặc thay dữ liệu.

## 2026-10-26 — Soạn đề xuất CV-05, chờ duyệt

- Viết [CV05_KIEN_TRUC_BACKEND_FRONTEND.md](docs/CV05_KIEN_TRUC_BACKEND_FRONTEND.md): đề xuất frontend React/TypeScript/Vite, backend Python/Flask module hóa; cấu trúc thư mục, route/API v1, dữ liệu riêng theo workspace, quản lý mô hình và khôi phục bản lưu cũ.
- Đề xuất SQLite cho metadata và filesystem riêng cho file lớn, IndexedDB cho tự lưu phía trình duyệt; chưa tạo database hay chọn dịch vụ cloud. Phạm vi cá nhân/nhiều người và stack vẫn chờ người dùng duyệt.
- Đọc code hiện tại và tài liệu chính thức, ghi rõ điểm phải bỏ: fallback `RESULT_CSV` chung và nhận model upload qua API. Không tự nâng thư viện hoặc thay mô hình.
- Hoàn tất đối chiếu bảng màu CV-04 với AST code, sửa tham chiếu tên hàm GPKG đúng là `gis.py:predicted_geojson`. Chỉ cập nhật tài liệu/cấu hình đặc tả, chưa sửa app hoặc renderer.

## 2026-10-26 — Chốt CV-04: ghép mã và bảng màu

- Người dùng đồng ý ghép phần số trong cùng dự án, không ghép khóa mơ hồ/trùng hoặc số gần nhất.
- Đối chiếu code hiện tại: Y=0 đỏ #ff0000, Y=1 cam #ffa500, Y=2 xanh #008000; fillOpacity nguồn 0,6, tên nhóm chỉ là “Kết quả Y = …”. Giữ nguyên, không tự thêm ý nghĩa nghiệp vụ.
- Phú Quốc được gộp hình học trùng hoàn toàn trong bộ nhớ, giữ file gốc/handle. Mã 1232 không tô, không áp dụng kết quả và không cảnh báo người xem; giữ chẩn đoán nội bộ.
- Tạo [biên bản CV-04](docs/CV04_QUY_TAC_GHEP_VA_MAU.md) và đặc tả JSON, cập nhật note. Hoàn thành chốt quy tắc; không công bố tỷ lệ ghép hình học chỉ từ tập mã. Triển khai/kiểm chứng MTEXT, ghép và gộp trùng ở CV-12/CV-14; chưa sửa bộ ghép/renderer hoặc áp dụng CRS.
- Tiếp theo CV-05: tổ chức backend–frontend và hợp đồng API.

## 2026-10-26 — Kiểm tra mã hệ tọa độ người dùng nhớ là 9201

- Người dùng cho biết dùng chung phép chiếu với DXF trước, nhớ không chắc mã 9201. Đã kiểm tra pyproj/PROJ: `CRS.from_epsg(9201)` báo không tìm thấy CRS; đối chiếu dữ liệu đơn vị PROJ, 9201 là đơn vị tỷ lệ unity.
- Ảnh giao diện trước đó có EPSG:9208; chưa coi đó là xác nhận cho các file mới. Cập nhật note/biên bản CV-03, giữ EPSG xác nhận là null, không chuyển tọa độ hoặc sửa dữ liệu.

## 2026-10-26 — CV-03 và quy tắc ô không xét

- Người dùng chốt `BK1`–`BK20` không xét điểm: giữ nét lưới, không tô màu, không tự điền Y=0. Đã cập nhật note và cấu hình tham khảo CV-02/CV-03; chưa thay renderer.
- Khảo sát ba DXF, xác định layer lưới và loại nhãn: TP.HCM `DTL-1D`/MTEXT, Bắc Kạn `00.Ranh gioi`/MTEXT, Phú Quốc `Docao`/TEXT; nhãn đều trên layer `0`.
- Tái hiện các vấn đề: MTEXT đặt điểm chèn trên biên và nhiễu nhãn nền; Phú Quốc có 58 polygon trùng dư, nhãn 1232 ngoài lưới và header đơn vị mm. Không tự snap/gộp/xóa hoặc ghép gần nhất.
- Người dùng xác nhận VN-2000; chưa xác nhận EPSG hoặc kinh tuyến trục/múi chiếu từng nguồn. Đã hỏi thông số chi tiết, không tự gán EPSG chung.
- Tạo [biên bản CV-03](docs/CV03_KHAO_SAT_DXF.md), cấu hình nguồn, công cụ chỉ đọc và 5 kiểm thử DXF. 13 kiểm thử DXF/Excel đạt; hash nguồn không đổi. Đánh dấu hoàn thành phần khảo sát CV-03, giữ rõ các vướng mắc trước khi xử lý dữ liệu công khai.

## 2026-10-26 — Hoàn thành CV-02: kiểm kê Excel tham khảo

- Đọc toàn bộ ba sheet dự án: TP.HCM 297 dòng, Bắc Kạn 400 dòng, Phú Quốc 1.677 dòng. Định vị cột B tên ô, C:K là x1–x9, L là Y; cột A chỉ là số mẫu.
- Bắc Kạn có 20 mã BK1–BK20 thiếu x1–x9 và Y; 380 mã còn lại đủ dữ liệu. TP.HCM thiếu mã TP267 trong dãy tên và công thức tổng kết L302 bỏ qua L4 nên đếm thiếu 1 dòng Y=0. Không sửa nguồn hoặc tự tạo kết quả.
- Tạo [biên bản CV-02](docs/CV02_KIEM_KE_EXCEL.md), cấu hình tham khảo `docs/cv02_excel_sources.json`, công cụ kiểm kê chỉ đọc và 8 kiểm thử dữ liệu giả. Đối chiếu cấu hình với kiểm kê thực tế; xác nhận hash workbook không thay đổi.
- Cập nhật [note công việc](NOTE_CONG_VIEC.md), đánh dấu CV-02 hoàn thành. Chưa tích hợp bộ đọc Excel vào ứng dụng, chưa khảo sát DXF/CRS hoặc tự ghép ô. Tiếp theo CV-03.

## 2026-10-26 — Hoàn thành CV-01

- Chốt trang Giới thiệu mặc định, điều hướng ở header (đính chính footer), một phần Giới thiệu và 3 ý Tầm nhìn.
- Excel tham khảo chỉ cung cấp dữ liệu có sẵn cho ba dự án địa phương, không dùng cho dự án thứ tư.
- Không tự lấy `ketqua.csv` mặc định trên máy chủ; người dùng chủ động nạp file kết quả và kết quả đó được lưu/khôi phục theo phiên.
- Cho phép kiến trúc backend–frontend để mở rộng. CV-05 sẽ đề xuất công nghệ, hợp đồng API và phương án chuyển đổi, chưa triển khai hoặc tự chọn stack mới.
- Đã cập nhật [NOTE_CONG_VIEC.md](NOTE_CONG_VIEC.md), đánh dấu CV-01 hoàn thành. Chỉ sửa tài liệu, chưa đổi chức năng ứng dụng. Đề mục tiếp theo: CV-02.

## 2026-10-26 — Lập kế hoạch theo tài liệu tham khảo mới

- Đã đọc `Tailieuthamkhao/Giaodienfrontend/yeucau.txt` và `link.txt`, kiểm kê ba DXF và đọc cấu trúc Excel tham khảo ở chế độ chỉ đọc.
- Tạo [NOTE_CONG_VIEC.md](NOTE_CONG_VIEC.md): 27 đầu việc, 8 giai đoạn, có phụ thuộc, tiêu chí hoàn thành và các lựa chọn cần người dùng xác nhận. Chatbot tách thành giai đoạn sau.
- Trang mẫu `https://dcsolution.vn/` chưa tải được qua công cụ tại lần kiểm tra này; chưa xác nhận bố cục trang mẫu. Chưa kiểm chứng đầy đủ phép ghép dữ liệu hoặc hệ tọa độ của ba DXF.
- Chỉ cập nhật tài liệu; không đổi chức năng ứng dụng, không sửa dữ liệu gốc, không chạy mã trong thư mục tham khảo.

## 2026-10-26 — Chốt hiện trạng trước thiết kế hệ thống mới

Mục đích: lưu mốc bàn giao để tiếp tục làm việc khi người dùng cung cấp thiết kế mới. Chưa triển khai hoặc suy đoán kiến trúc mới. Nội dung đối chiếu với mã nguồn, README và kết quả kiểm thử đã ghi nhận trong phiên làm việc trước.

### Nền tảng hiện tại

- Ứng dụng Python/Flask, điểm chạy `app.py`; chạy `python -m app` hoặc `run_python.bat`, cổng mặc định 8765.
- Mô hình và scaler `.pkl` được nạp trực tiếp bằng Python; luồng hiện tại không cần chạy C#. File `.onnx` vẫn có trong thư mục, chưa xóa.
- Giao diện HTML/CSS/JavaScript trong `templates/index.html` và `wwwroot/`; Leaflet được lưu cục bộ tại `wwwroot/leaflet`.
- Kết quả dự đoán trên máy chủ: `%LOCALAPPDATA%\MapPredictApp\KetQua.csv`. Bản lưu phiên trình duyệt tách biệt với file kết quả này.

### Chức năng đã triển khai

- Hai tab Bản đồ / Dự đoán; trang dự đoán có điều khiển bên trái, bảng dữ liệu và kết quả bên phải, xuất CSV.
- CSV đầu vào sử dụng `x1` đến `x9`, kết quả có cột `Y`; hỗ trợ chọn mô hình/scaler riêng.
- Lần đầu mở chưa có bản lưu: không tự nạp layer người dùng; người dùng chọn file để hiển thị.
- Nạp nhiều DXF nền và nhiều lưới dự đoán DXF/GPKG; thêm nhiều đợt, gỡ riêng từng file.
- Chọn một EPSG nguồn dùng chung cho các layer trong web; chuyển tọa độ để hiển thị, không ghi ngược vào file gốc.
- Nhập độ dịch X/Y; phân tích phép chèn block DXF để đề xuất dịch ngược khi đủ bằng chứng. Có xem trước, xác nhận áp dụng; không tự đoán vị trí theo tên file.
- Nền vệ tinh Esri, nhãn đường/địa danh và nền đường phố OpenStreetMap; đường phố không phải dữ liệu ùn tắc trực tiếp.
- Zoom vector đến 22; ảnh nền phóng/cắt theo tile và thử mức ảnh cha khi thiếu ảnh, có thông báo lỗi mạng.
- Quản lý hiển thị/độ đậm từng layer; bấm layer hoặc đối tượng để xem thành phần, thuộc tính, tìm kiếm và phân trang.
- Tùy chỉnh nét, tô, độ dày, kiểu nét, cỡ điểm theo layer/thành phần; hiệu chỉnh hue, contrast, brightness, saturation và đảo màu.
- Đã bỏ phần chỉnh màu mặc định và tô màu hàng loạt theo nhiều giá trị thuộc tính theo yêu cầu trước.
- Nhãn TEXT/MTEXT từ DXF không hiển thị trên bản đồ. Trong lưới dự đoán, nhãn có thể được đọc để suy ra mã ô.
- Lưới DXF đọc polyline kín, hỗ trợ ghép qua `grid_id`, `handle`, `layer`. Không giả lập thuộc tính `tenlodat`; mã phải thực sự đối ứng với CSV.

### Thay đổi gần nhất: tự lưu và xuất PDF

- Tự động lưu thao tác sau khoảng 180 ms không có thao tác mới, không cần nút lưu thủ công.
- Đã bỏ nút “Lưu ngay”; thanh trạng thái báo “Đã tự lưu trên trình duyệt” khi giao dịch hoàn tất.
- IndexedDB lưu file/Blob, GeoJSON, kết quả, thông số layer, màu, bật/tắt, độ đậm, tọa độ, độ dịch, cột ghép, tâm/zoom và tab đang mở.
- Reload khôi phục trạng thái hoàn chỉnh gần nhất; không tự chạy lại mô hình hoặc gửi lại API nạp bản đồ. Đây không phải lịch sử undo/redo.
- Lưu snapshot và asset trong cùng giao dịch; kiểm tra xung đột nhiều tab, lỗi dung lượng và bản lưu thiếu dữ liệu để tránh ghi đè bản tốt bằng trạng thái rỗng.
- Nút “Xuất PDF bản đồ” nằm ngay dưới “Hiển thị trên bản đồ” ở thanh bên trái, là `type="button"` nên không gửi form bản đồ.
- Xuất đúng khung nhìn hiện tại: giữ layer đang bật, kiểu hiển thị, tâm/zoom; không đưa thanh bên/bảng thuộc tính/nút điều khiển vào bản in.
- Mở trang xem trước và hộp thoại in của trình duyệt; chọn Save as PDF, mặc định A4 ngang. Không phải GeoPDF.
- Khi nền chưa tải đủ, cần xác nhận và có cảnh báo; không tự tải hàng loạt ảnh nền.

### Vị trí mã nguồn cần tiếp tục theo dõi

- `app.py`: giao diện Flask, API dự đoán, đọc file và tạo dữ liệu bản đồ.
- `predict_pkl.py`: xử lý dự đoán bằng mô hình Python.
- `gis.py`, `cad_to_geojson.py`, `cad_diagnostics.py`, `prediction_grid.py`: tọa độ, hình học CAD, đề xuất độ dịch, lưới và ghép kết quả.
- `wwwroot/app.js`, `layer_manager.js`, `color_adjustments.js`, `basemaps.js`: điều phối giao diện, quản lý layer, màu và nền.
- `wwwroot/workspace_store.js`, `workspace.js`: lưu/khôi phục phiên trình duyệt.
- `wwwroot/pdf_export.js`: chụp khung nhìn và chuẩn bị trang in.
- `templates/index.html`, `wwwroot/app.css`: bố cục và kiểu giao diện.
- `README.md`: hướng dẫn vận hành, giới hạn và cách chạy kiểm thử.

### Kiểm thử đã ghi nhận ở phiên triển khai trước

- Python: 38 bài kiểm thử đạt; có cảnh báo ResourceWarning về file tạm chưa đóng, không làm bài kiểm thử thất bại.
- JavaScript: 28 bài kiểm thử đạt cho nền bản đồ, hiệu chỉnh màu và logic xuất PDF.
- Kiểm thử trình duyệt xác nhận khôi phục file, mô hình, dữ liệu, layer, ký hiệu, độ dịch, hệ tọa độ và vị trí bản đồ sau reload mà không gọi lại API.
- Xác nhận tự lưu khi sửa input mà không bấm lưu; gỡ layer không xuất hiện lại; lỗi quota, rollback, xung đột và snapshot thiếu asset được xử lý.
- Xác nhận nút PDF nằm ngay dưới nút hiển thị, mở bản xem trước mà không POST `/api/map`, không có lỗi JavaScript trong luồng kiểm tra.
- Các kết quả trên là kết quả đã chạy ở phiên trước, không phải lần chạy kiểm thử mới ngày 2026-10-26. Lần ghi nhật ký này chỉ đọc mã/tài liệu, không đổi chức năng hay dữ liệu người dùng.

### Giới hạn cần giữ rõ khi thiết kế lại

- VN-2000 có nhiều phép chiếu/EPSG; không thể xác nhận chính xác chỉ từ tên “VN-2000”. Dữ liệu CAD cục bộ có thể cần điểm mốc hoặc xử lý QGIS.
- Các layer hiện dùng một EPSG nguồn chung. Chưa có lựa chọn EPSG riêng cho từng layer trong cùng phiên.
- Phân tích độ dịch chỉ dựa trên bằng chứng block và phép tịnh tiến nhất quán; không bảo đảm khớp thực địa hoặc tự giải bài toán xoay/co giãn.
- Bản lưu gắn với trình duyệt/profile và origin (host/cổng); không đồng bộ nhiều máy, không phải bản sao lưu độc lập, có thể mất khi xóa dữ liệu trình duyệt.
- Tile nền cần Internet và phụ thuộc nhà cung cấp; kiểm thử với tile giả không chứng minh mạng thực tế luôn tải đủ.
- Không bảo đảm đọc mọi loại thực thể CAD; phải giữ cảnh báo loại chưa hỗ trợ và lỗi hình học.
- Kiểm thử trình duyệt có chạy dự đoán/tải kết quả phải dùng máy chủ với `RESULT_CSV`/`DATA_DIR` tách biệt, tránh ghi đè kết quả thật.
- Trước khi đổi cấu trúc lưu trữ, cần xác định phương án tương thích/chuyển đổi bản lưu hiện tại: IndexedDB `mapPredict.workspace`, phiên bản DB 1, snapshot schema 1.

### Bước tiếp theo

Chờ thiết kế hệ thống mới từ người dùng. Sau khi nhận, đối chiếu phạm vi giữ lại/thay thế, luồng dữ liệu, định dạng lưu trữ và phương án chuyển đổi; chưa xóa mã nguồn, mô hình, dữ liệu hoặc bản lưu hiện có.

## 2026-10-28 Quản trị AI, chế độ model và service embedding

- Thêm trang /portal/admin/ai trong giao diện chung, mật khẩu băm được lưu ngoài Git
- Service AI kiểm tra khóa nội bộ, phiên quản trị, CSRF, thời hạn và giới hạn đăng nhập
- Thêm hai chế độ Nhanh và Thông minh, mỗi chế độ có nguồn Gemini Web hoặc API tương thích riêng
- Khóa API lưu trong volume riêng, không trả lại trình duyệt hoặc gửi khóa nội bộ sang nhà cung cấp ngoài
- Theo xác nhận người dùng, embedding chỉ dùng trong quản trị, chatbot tìm từ khóa trong Qdrant
- Thêm ai-embedding chạy Ollama với một yêu cầu đồng thời, yêu cầu giải phóng model sau công cụ quản trị
- Chuyển cơ chế khóa file của google_session.py trong server tham khảo sang Windows và Linux
- Gemini kiểm tra phiên mỗi 20 phút, thử xoay cookie sau 12 giờ và lưu cookie mới trong volume riêng
- Nhập thử hồ sơ server tham khảo, Google yêu cầu đăng nhập lại nên quản trị báo cần nhập cookie mới
- Đặt tên service web-portal, ai-assistant, gemini-session, ai-embedding, qdrant, web-gateway, cloudflare-tunnel
- Giữ nguyên dữ liệu Qdrant, không tạo snapshot và không khôi phục blue/green
- Kiểm tra hiện tại 125 test Python, 40 test frontend và 5 test bong bóng trợ lý đều đạt
- Kiểm tra thực tế HTTPS đăng nhập với cookie Secure, lưu cấu hình và nhận phản hồi của cả hai chế độ model
- Công cụ embedding trả vector 1024 chiều, dense retrieval trả 5 nguồn từ collection hiện có
- Sau công cụ, ollama ps không còn model nạp và service embedding dùng khoảng 14 MiB RAM tại lần đo local này
- Model được chép từ kho Ollama có sẵn, đối chiếu SHA-256 từng blob trước khi đưa vào volume riêng
## 2026-10-28 Pro 4 Argon, passcode và định tuyến tài khoản

- Đối chiếu accounts.py, gemini_usage.py, quota_guard.py và server/gemini_web2api.py trong dự án tham khảo
- Xác định model gemini-4-argon và header riêng được khám phá từ tài khoản, không gán nhầm sang gemini-3.1-pro
- Thêm pool tối đa tám tài khoản, thử tài khoản còn quota với cùng Argon và kiểm tra quota trước cùng sau generation
- Model không hỗ trợ bị từ chối, không tự về model mặc định, Pro không có nhánh ẩn danh
- Thêm passcode riêng do quản trị đặt, hash lưu trên service và kiểm tra trước khi đọc file hoặc gọi model
- Quản trị có phần xem quota, thêm tài khoản và cập nhật cookie cho từng tài khoản Pro
- Nhập hai hồ sơ nguồn vào pool, cả hai đang cần đăng nhập lại nên chưa xác minh được generation Argon thật
- Kiểm tra HTTP thực tế mã sai trả 403, mã tạm hợp lệ với tài khoản chưa xác minh trả 503 QUOTA_UNVERIFIED và không trả câu trả lời model khác
- Passcode thử nghiệm đã được vô hiệu hóa, người dùng tự đặt passcode Pro trong trang quản trị
- Tách cache cookie theo đường dẫn và metadata file để không lẫn tài khoản có cùng thời gian sửa
- Header Argon không được gửi nếu cookie hoặc XSRF thiếu, kể cả khi lỗi đọc cookie xảy ra sau bước kiểm tra quota
- 135 kiểm thử Python, 41 kiểm thử frontend và 6 kiểm thử bong bóng trợ lý đã đạt
## 2026-10-28 Tên miền quản trị

- Thêm admin.danhgiaquyhoach.top vào tunnel hiện có và tạo CNAME được proxy qua Cloudflare
- Giữ nguyên ingress của danhgiaquyhoach.top, không thêm container hoặc tunnel mới
- Host admin chuyển từ đường dẫn gốc tới /portal/admin/ai, tên miền chính tiếp tục mở portal
- Theo xác nhận cuối, trang chính không có nút hoặc liên kết quản trị, header trên trang quản trị dẫn về tên miền chính
- Trang cùng API quản trị chỉ phục vụ trên host admin và localhost, tên miền chính trả 404
- Đăng nhập tiếp tục được kiểm tra tại service AI, cookie được giữ riêng theo hostname
- Bổ sung kiểm thử chuyển hướng theo hostname, giữ nguyên ingress và không ghi đè route xung đột
## 2026-10-28 Chốt hai chế độ Nhanh và Thông minh

- Bỏ lựa chọn Pro riêng, gán Thông minh cố định vào gemini-4-argon
- Chuẩn hóa cấu hình ba chế độ cũ thành hai chế độ khi đọc, không khôi phục model thinking ẩn danh cho Thông minh
- Thiếu cookie hoặc cookie hết hạn được báo COOKIE_REQUIRED trước bước passcode, không chuyển sang Nhanh
- Giữ pool tài khoản cùng model, kiểm tra quota trước và sau generation, giữ passcode Thông minh theo yêu cầu trước
- Đổi tên các mục quản trị tương ứng, giữ nguyên cookie và hash passcode đã lưu
- Kiểm thử 141 test Python, 41 test giao diện và 7 test bong bóng trợ lý đã đạt

## 2026-10-28 Chatbot dùng tài nguyên dự án và lịch sử hai chiều

- Bỏ ô gửi DXF riêng trong chat, tự nhận DXF và CSV đang nạp trong dự án
- Hiển thị bản sửa nháp trên tab bản đồ và bảng dữ liệu trước khi xác nhận
- Thêm Xác nhận thay đổi, Bỏ bản nháp, Hoàn tác và Làm lại dùng chung cho hai tab
- Tạm dừng tự lưu bản nháp, chỉ lưu khi xác nhận, bản nháp bị bỏ khi tải lại trang
- Gộp thay đổi DXF và CSV thành một thao tác, lỗi dựng bản đồ sẽ phục hồi cả hai
- Lịch sử giữ tối đa 10 thao tác trong bộ nhớ tab, không tạo file sao lưu hoặc phiên service
- Sửa điểm loại kết quả dự đoán cũ, giữ xuất file từ tài nguyên đã xác nhận
- Đã đạt 141 kiểm thử Python, 41 kiểm thử frontend và 41 kiểm thử JavaScript, gồm 11 kiểm thử chatbot cùng lịch sử tài nguyên

## 2026-10-28 Agent tự nhận dữ liệu theo tab và lưu lịch sử so sánh

- Bỏ bộ chọn file, layer, dòng dữ liệu và thông tin truy xuất kỹ thuật trong cửa sổ chat
- Tab dự đoán chỉ lấy CSV đang nạp, cho phép đề xuất tạo CSV mới khi chưa có file
- Bảng mới có mã ô đất duy nhất, x1 đến x9 chỉ được chấm qua căn cứ đã kiểm chứng, không tự tạo Y
- Tab bản đồ chỉ lấy DXF đã hiển thị theo hệ tọa độ hiện tại và đang tích bật, không tự tạo file DXF
- Thêm xử lý tối đa 5 DXF cùng lượt với handle có phạm vi file, tránh nhầm đối tượng trùng handle
- Bổ sung vẽ LINE, LWPOLYLINE, CIRCLE, TEXT trong file sẵn có và thuộc tính XDATA MAP_PREDICT
- DXF sửa tự nạp cùng tên tài nguyên, người dùng duyệt giữ lại hoặc bỏ để khôi phục
- Chuyển thanh Hoàn tác và Làm lại vào cửa sổ chat, chuyển xuất file về danh sách tài nguyên và bảng dữ liệu
- Lưu nguyên tử tối đa 10 thao tác trước và sau cùng workspace trong IndexedDB, localStorage giữ vị trí lịch sử
- Tải lại trang vẫn quay lại trước và sau để so sánh, không lưu bản nháp chưa duyệt
- Kiểm thử đạt 145 test Python, 41 test frontend và 46 test JavaScript, gồm kiểm tra đóng mở lại IndexedDB với DXF và lịch sử đầy đủ

## 2026-10-28 Cố định khung chat và phím gửi

- Giữ kích thước cửa sổ chat theo viewport, cuộn riêng tin nhắn và bản duyệt, không cuộn toàn khung
- Ô nhập có chiều cao cố định và cuộn nội dung, không kéo giãn bằng chuột
- Enter gửi, Shift Enter xuống dòng, không gửi khi đang gõ IME hoặc giữ phím Enter
- 18 kiểm thử chatbot và lịch sử tài nguyên đã đạt
