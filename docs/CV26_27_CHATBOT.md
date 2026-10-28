# Trợ lý GIS tại dự án thứ tư

Người dùng xác nhận ngày 2026-10-27 dùng server Gemini trong tài liệu tham khảo và xem trước trước khi áp dụng thay đổi
Chatbot nằm trong cửa sổ nổi Trợ lý GIS của công cụ Đánh giá quỹ đất, bao gồm cả trang legacy được nhúng tại `/portal/assessment`

## Nguồn đã sử dụng

- Mã adapter Gemini từ `Tailieuthamkhao/gemini-agent/server/gemini_web2api`, bản ghi phiên bản 1.1.0 trong mã nguồn
- Bản sao chạy được nằm trong `integrations/gemini_web2api`, giữ giấy phép MIT tại `integrations/GEMINI_LICENSE`
- Ngữ cảnh chấm điểm từ `Tailieuthamkhao/Thuchanh/data/Tieuchi.md`, bản triển khai tại `config/assistant/rubric.md`
- Tài liệu ghi nguồn bảng sửa ngày 1509, phạm vi A1:T14, giữ record_id, ô nguồn và ngưỡng gốc

Không tích hợp Chainlit hoặc LangChain trong bản này, từ ngày 2026-10-28 có truy xuất Qdrant và service AI riêng, xem [hướng dẫn service AI](AI_SERVICE_QDRANT.md)
Server tham khảo chuyển giao diện web Gemini thành API tương thích OpenAI, không phải API chính thức của Google
Chỉ sao chép mã Python cần chạy và giấy phép, không sao chép cookie, tài khoản, nhật ký hoặc cấu hình riêng từ tài liệu tham khảo

## Cách dùng

1. Mở dự án Đánh giá quỹ đất rồi bấm Trợ lý GIS ở góc dưới bên phải
2. Mở Dữ liệu gửi cho trợ lý, chọn một DXF đã nạp hoặc chọn file riêng
3. Có thể gửi thêm CSV đầu vào hiện tại, lọc layer và chọn dòng bắt đầu
4. Nhập yêu cầu đọc bản vẽ, chỉnh đối tượng, tạo bảng từ lưới có mã rõ ràng hoặc đề xuất điểm
5. Kiểm tra nguồn, giá trị trước/sau và từng dòng đề xuất rồi bấm Áp dụng
6. DXF sửa được thay vào nguồn đang dùng, bảng tiêu chí cập nhật bên phải và tự lưu qua workspace hiện có
7. Có liên kết tải DXF sửa và CSV tiêu chí, file gốc trên ổ đĩa không bị ghi đè

Ví dụ yêu cầu

- Đọc DXF và cho biết các layer cùng số lượng đối tượng
- Đổi màu các chữ trong layer đang lọc sang ACI 1
- Dịch đối tượng handle 2F theo X 5 và Y 0 đơn vị bản vẽ
- Tạo bảng tiêu chí cho các ô lưới có mã xác định trong DXF
- Ô A1 là đất nông nghiệp xen kẹt, đề xuất x4 theo ô L9 của bảng sửa ngày 1509

## Phạm vi và quy tắc

- Đọc modelspace, tóm tắt tối đa 300 đối tượng theo bộ lọc layer và 100 dòng bảng từ vị trí đã chọn, hiển thị số đã gửi trên tổng số
- Chỉ hỗ trợ thay màu ACI, đổi layer, sửa TEXT/MTEXT và dịch đối tượng hiện có theo handle đã gửi
- Không chạy mã hoặc lệnh shell do LLM sinh, không sửa block/xref hoặc đổi CRS bằng suy đoán
- Khi không có CSV, chỉ tạo dòng từ ô lưới có một mã được xác định theo thuật toán DXF hiện tại, không gán theo thứ tự hình học
- Chỉ ghi điểm x1 đến x9 khi ô nguồn ghi duy nhất một điểm và có trích dẫn đối chiếu từ dữ liệu DXF, yêu cầu người dùng hoặc nguồn web
- Ô gộp thể hiện nhiều điểm được giữ là nhóm điểm, không tự chọn một điểm để điền
- LLM đề xuất điểm, người dùng vẫn kiểm tra quan hệ giữa căn cứ và ô đất trong bước xem trước
- Không suy ra cao độ DEM, độ dốc hoặc pháp lý từ một bản vẽ không có dữ liệu đó
- Sau khi thay tiêu chí, loại bỏ Y cũ để người dùng chạy lại pipeline hiện có
- Tra cứu mạng dùng khả năng tìm kiếm của Gemini, backend đọc tối đa ba URL HTTPS để đối chiếu nguyên văn trích dẫn
- Chỉ nhãn đã đối chiếu trích dẫn mới được dùng làm căn cứ điền điểm, nhãn này không xác nhận tính đúng của nhận định hay pháp lý
- Adapter không cung cấp grounding metadata theo chuẩn API Google, không coi URL trong câu trả lời là bằng chứng đã đọc được nguồn

## Dữ liệu và vận hành

DXF tối đa 12 MiB, CSV tối đa 5 MiB và 10000 dòng, mỗi lượt tối đa 50 sửa DXF và 100 điểm
Bản xem trước có chữ ký, gắn với nội dung file và hết hạn sau 15 phút, thay file sẽ cần xem trước lại
File upload chỉ tồn tại trong request, không có thư mục upload dùng chung giữa khách
Chỉ tóm tắt DXF và các dòng CSV đã chọn cùng tối đa sáu tin nhắn trước được gửi tới Gemini
Lịch sử trò chuyện tối đa 20 tin nằm trên trình duyệt, có nút xóa hội thoại
Mỗi địa chỉ tối đa sáu yêu cầu mỗi phút và chỉ một yêu cầu assistant chạy đồng thời trên backend

Gemini là service riêng trong Compose, không mở cổng host, dùng khóa nội bộ tự sinh và không dùng cookie tài khoản có sẵn
`MAP_PREDICT_ASSISTANT_ENABLED=1` bật assistant, đặt 0 trong `.env` để tắt API
`MAP_PREDICT_ASSISTANT_MODEL` chọn tên model mà adapter đang hỗ trợ
Khởi động bằng `python tools/docker_stack.py start`, triển khai dùng script hiện có trên cả Windows và Linux
Ứng dụng chạy thường xuyên với năm container khi bật AI và Gemini, cùng container Qdrant tham khảo hiện có, slot dự phòng vẫn chỉ bật trong lúc cập nhật

Trường hợp Gemini hết hạn mức, mất mạng hoặc trả sai JSON, giao diện báo lỗi và giữ nguyên dữ liệu
Không tự chuyển sang tài khoản hoặc cookie khác

## Kiểm tra

- Đã thử server Gemini thật với DXF tổng hợp, nhận đề xuất màu và áp dụng thành bản sao DXF
- Đã thử trích dẫn từ tài liệu ezdxf công khai, đối chiếu được nguyên văn trên trang gốc
- Đã thử Gemini thật đề xuất x4 = 9 theo ô L9 cho A1 từ thông tin người dùng, áp dụng đúng điểm và loại Y cũ
- Kiểm thử API bao gồm cách ly upload, từ chối token bị sửa, file bị thay, điểm nhóm, nguồn không đủ căn cứ, nguồn mạng nội bộ và origin khác
- Kiểm thử DOM bao gồm nút mở popup, không tự áp dụng, giữ nội dung trả lời dạng text và vô hiệu bản xem trước cũ
- Chưa có trình duyệt điều khiển khả dụng trong phiên làm việc để chụp ảnh và kiểm tra trực quan

Nguồn kỹ thuật: [DXFEntity](https://ezdxf.readthedocs.io/en/stable/dxfentities/dxfentity.html), [grounding metadata của API Google](https://ai.google.dev/gemini-api/docs/google-search)
