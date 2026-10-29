# Service AI và Qdrant

## Chỉnh sửa tài nguyên dự án qua chatbot

- Chatbot tự lấy dữ liệu của tab đang mở, không có bộ chọn file, layer hoặc phạm vi dòng trong chat
- Tab dự đoán chỉ gửi CSV đầu vào đang nạp, hoặc CSV kết quả nếu không có đầu vào
- Khi chưa có CSV, Agent có thể đề xuất tạo bảng tối đa 100 dòng, mã ô đất duy nhất, điểm chỉ được điền qua quy tắc đã kiểm chứng
- Tab bản đồ chỉ gửi DXF đã nạp, hiển thị theo hệ tọa độ hiện tại và đang tích bật, không gửi CSV
- Mỗi lượt tối đa 5 DXF, tổng 300 đối tượng mẫu, handle có tiền tố theo file để không lẫn đối tượng giữa các bản vẽ
- Không có DXF được bật vẫn trò chuyện bình thường, không cấp quyền sửa, vẽ hoặc tạo file DXF
- Cho phép đổi màu, layer, chữ, dịch đối tượng, thêm thuộc tính XDATA và vẽ LINE, LWPOLYLINE, CIRCLE, TEXT trong file có sẵn
- Thuộc tính riêng được ghi vào XDATA MAP_PREDICT và hiển thị với tiền tố attr: trong thông tin đối tượng
- Đề xuất hợp lệ được dựng thành bản nháp ngay trên bản đồ và bảng dữ liệu, tự lưu cùng trạng thái chờ xác nhận
- Xác nhận thay đổi, Bỏ bản nháp, Hoàn tác và Làm lại nằm trong cửa sổ chat
- Hoàn tác và Làm lại khôi phục cả DXF, bảng CSV, kết quả dự đoán và layer hiển thị của cùng một lần sửa AI
- Lịch sử tối đa 10 lần sửa cùng trước và sau được lưu nguyên tử với workspace trong IndexedDB, localStorage lưu vị trí lịch sử
- Tải lại trang vẫn có thể Hoàn tác và Làm lại để so sánh, bản nháp được khôi phục với nút Xác nhận hoặc Bỏ bản nháp
- CSV đầu vào và CSV kết quả có nút xóa riêng, thao tác xóa cũng được tự lưu trên trình duyệt
- Sửa điểm làm mất hiệu lực Y cũ và CSV kết quả cũ, cần chạy lại mô hình để tính kết quả mới
- Nếu không dựng được bản đồ, khôi phục cả bảng và DXF trước lần sửa, không giữ nửa thay đổi
- File gốc trên máy không bị ghi đè, DXF sửa tự thay vào tài nguyên cùng tên và hiện trên bản đồ
- Nút Xuất file ở danh sách tài nguyên và Xuất CSV ở bảng dữ liệu nằm ngoài chat
- Nếu tài nguyên đã được sửa bằng thao tác khác, không cho lịch sử AI ghi đè dữ liệu mới

## Cấu hình quản trị hiện tại

Trang `/portal/admin/ai` xác thực mật khẩu tại service AI, tách khỏi khóa nội bộ
Chatbot chỉ có Nhanh và Thông minh, Thông minh dùng 4 Argon với pool tài khoản cùng passcode do quản trị thiết lập
Thiếu cookie hoặc cookie hết hạn phải báo lỗi, không chuyển Thông minh sang Nhanh
Chatbot dùng RAGWire 1.6.1, embedding và bộ lọc metadata tự động theo dự án Thuchanh
Truy vấn x1 đến x9, số thứ tự tiếng Việt và tên tiêu chí được ánh xạ theo nội dung thực của đoạn
Chunk được tách theo tiêu đề tiêu chí trước khi chọn nguồn, không dùng nhãn metadata của cả chunk để lọc mọi nội dung bên trong
Giữ phần tiêu đề thang điểm đi kèm, gộp các phân nhóm thuộc cùng point và giữ nguyên Qdrant ID cùng source_ref
Lọc đúng phiên bản sửa ngày 1509 trước khi xếp hạng, không để bản cũ chiếm kết quả
Chatbot dùng hybrid retrieval, công cụ quản trị vẫn có kiểm tra embedding và dense retrieval riêng
Ollama chạy trong service ai-embedding, model được yêu cầu giải phóng sau mỗi lượt
Cookie Google được kiểm tra định kỳ trong gemini-session, có thể nhập lại qua quản trị
Xem [Quản trị AI](AI_ADMIN.md) cho cấu hình và giới hạn thực tế

Ngày 2026-10-28 đã kết nối collection `CSDL-Datdai` trong container Qdrant có sẵn
Collection có 5 point, vector dense không đặt tên, 1024 chiều, cùng sparse vector `langchain-sparse`
Dự án tham khảo dùng `qwen3-embedding:0.6b`, đã kiểm tra model đang có trên máy và trả vector 1024 chiều

## Cách tách service hiện tại

- Frontend tiếp tục gọi `/api/v1/assistant`, không giữ khóa hoặc địa chỉ nội bộ
- Backend web kiểm tra origin, hạn mức và chuyển request qua gateway mỏng
- `ai-assistant` là một tiến trình Gunicorn riêng, xử lý RAG, prompt, Gemini, DXF và bản xem trước
- Chỉ một bản web và một bản AI, không có slot dự phòng
- Gemini, Qdrant và Ollama là service trong cùng Compose
- Web và AI trao đổi bằng khóa nội bộ, các cổng AI không xuất ra host
- Khi triển khai, build rồi cập nhật trực tiếp web/AI và reload Nginx, chấp nhận gián đoạn ngắn trong thử nghiệm local

Code AI dùng chung lớp xử lý file, image AI và web chia sẻ các layer Docker để tránh nhân đôi thư viện trên ổ đĩa
Không nạp pandas và scikit-learn trong tiến trình AI chỉ để đọc CSV

## Truy xuất tài liệu

1. Đọc thông số collection có sẵn, không tạo hoặc ghi lại collection
2. RAGWire đọc metadata hiện có, chạy get_filter_context, kiểm tra bộ lọc theo trường và giá trị thực rồi gọi retrieve
3. Truy vấn embedding dùng model đã lưu trong quản trị, cùng vector dense và sparse BM25 của collection, mặc định lấy 5 point bằng hybrid search
4. Giữ ID point, record_id và ô nguồn từ nội dung thực, không đưa đường dẫn temp của máy nguồn ra giao diện
5. Đưa các đoạn vào prompt và xây danh mục quy tắc chấm điểm từ chính nội dung đã truy xuất
6. Nguồn Qdrant chứng minh ngưỡng chấm điểm, không thay thế bằng chứng hiện trạng từng ô đất

Metadata của một chunk có thể chỉ mô tả một trong nhiều tiêu chí nằm trong chunk
Vì vậy không lọc cứng theo metadata tiêu chí khi điều đó làm mất phần nội dung khác của cùng chunk
Parser giữ điểm nhóm và hỗ trợ cả bảng Markdown lẫn nhãn điểm ở từng đoạn văn như tiêu chí GPMB

RAGWire được khởi tạo ở chế độ chỉ truy xuất, bỏ bước ingestion và tạo index của constructor mặc định
Các alias x1 đến x9 được mở rộng tên tiêu chí trước khi tìm ngữ nghĩa, bộ lọc không khớp dữ liệu thực sẽ bị loại
Khi metadata của chunk gộp làm mất tiêu chí cần tìm, hệ thống nới bộ lọc và kiểm tra lại nội dung trước khi dùng làm nguồn
Nếu embedding hoặc RAGWire chưa sẵn sàng, API báo rõ chế độ dự phòng từ khóa trên cùng collection
API trả rõ chế độ truy xuất, không thay model và không tái lập chỉ mục
Nếu đã cấu hình Qdrant nhưng không đọc được collection thì báo lỗi, không âm thầm đổi sang bản local
Khi không cấu hình URL Qdrant, chế độ tài liệu local vẫn được giữ để chạy app độc lập

## Tách JSON khỏi nội dung và file xuất

- JSON chọn bộ lọc chỉ dùng nội bộ, không đưa Document hoặc metadata thô vào tin nhắn
- Bộ giải mã xử lý JSON chuẩn, code fence, phần giải thích bao quanh và JSON bị mã hóa hai lần
- Chỉ phần answer hiển thị trong chat, đề xuất sửa vẫn qua whitelist, chữ ký và bước xác nhận
- Phản hồi bị cắt, nhiều kế hoạch mâu thuẫn hoặc schema sai bị từ chối, không cố ghép lại thành thao tác
- CSV lấy từ bảng đã kiểm tra, DXF lấy từ đối tượng ezdxf đã áp dụng đề xuất, không xuất nguyên phản hồi model
- requirements-ai.txt chỉ được cài vào image AI, image web giữ bộ phụ thuộc hiện có

## Prompt có thể sửa

File `config/assistant/system_prompt.txt` được mount chỉ đọc vào AI, sửa trên host sẽ có hiệu lực từ lượt chat tiếp theo
Prompt đã bổ sung quyền đề xuất sửa DXF, handle/hình học thực tế, nguồn Qdrant và quy trình xuất bản sao
Code vẫn kiểm tra whitelist thao tác, điểm đơn, bằng chứng, hash file và chữ ký dù prompt được chỉnh
Không coi nội dung DXF, CSV hoặc tài liệu truy xuất là lệnh có quyền chạy code hay sửa dữ liệu máy chủ

## Xuất DXF

- Bản xem trước có nút **Xuất DXF từ bản xem trước**, chỉ tạo file tải xuống, không thay workspace
- Sau khi bấm **Áp dụng**, vùng File đã sửa giữ nút **Xuất DXF đã sửa**, không mất khi gửi tin tiếp theo
- API export trả file DXF nhị phân với Content-Disposition attachment qua cả gateway và service AI
- File được dựng từ đề xuất đã ký, kiểm tra nội dung file nguồn và thời hạn 15 phút
- Không ghi đè file gốc, không gọi lại LLM khi xuất

## Cấu hình trên máy hiện tại

Các giá trị kết nối nằm trong `.env`, không được đưa lên Git

```dotenv
AI_QDRANT_URL=http://qdrant:6333
AI_QDRANT_COLLECTION=CSDL-Datdai
AI_EMBEDDING_URL=http://ai-embedding:11434
AI_EMBEDDING_MODEL=qwen3-embedding:0.6b
```

Qdrant đã chuyển vào Compose với volume map-predict_qdrant_data, giữ nguyên 6 collection và 807 point
Đã đối chiếu hash toàn bộ payload/vector, không tạo lại collection hoặc thay embedding
Không tự tạo snapshot, snapshot do agent tạo ở lần trước đã được xóa theo yêu cầu
Backup do người dùng quản lý, không giữ nhiều phiên ứng dụng để dự phòng

Khi chuyển VPS, dùng cùng code/Compose và đưa bản backup của bạn vào volume dữ liệu
Ollama là dịch vụ host hoặc dịch vụ embedding khác có URL truy cập được từ container AI
Chỉ đổi kết nối và dữ liệu triển khai, không sửa code frontend/backend

## Kiểm tra đã thực hiện

- Truy xuất dense thật từ Qdrant qua service AI, trả đủ 5 đoạn, 1024 chiều và quy tắc L9 đúng cho x4
- Thử Gemini thật đề xuất x4 = 9 từ hiện trạng người dùng cung cấp, gắn ID point Qdrant đúng cho ô nguồn L9
- Kiểm thử gateway thay khóa client bằng khóa nội bộ và giữ đúng nội dung file binary
- Kiểm thử từ chối lấy mô tả quy tắc Qdrant làm bằng chứng hiện trạng
- Kiểm thử nút xuất từ bản xem trước không gọi commit workspace
- Đã chạy thật qua gateway web đến AI riêng: Qdrant dense trả 5 nguồn, Gemini đề xuất sửa màu và x4 = 9, API export trả attachment DXF hợp lệ 15380 byte, API apply cập nhật điểm và loại Y cũ

Nguồn: [Qdrant query](https://api.qdrant.tech/api-reference/search/query-points/), [Qdrant scroll](https://api.qdrant.tech/api-reference/points/scroll-points), [Qdrant snapshots](https://qdrant.tech/documentation/operations/snapshots/), [Ollama embeddings](https://docs.ollama.com/api/embed)
