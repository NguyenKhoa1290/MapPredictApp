# Service AI và Qdrant

## Cấu hình quản trị hiện tại

Trang `/portal/admin/ai` xác thực mật khẩu tại service AI, tách khỏi khóa nội bộ
Chatbot chỉ có Nhanh và Thông minh, Thông minh dùng 4 Argon với pool tài khoản cùng passcode do quản trị thiết lập
Thiếu cookie hoặc cookie hết hạn phải báo lỗi, không chuyển Thông minh sang Nhanh
Theo quyết định người dùng, chatbot chỉ tìm từ khóa trong Qdrant và không gọi embedding
Dense retrieval mô tả bên dưới chỉ dành cho công cụ quản trị đã đăng nhập
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
2. Gửi câu hỏi tới Ollama `/api/embed` bằng đúng model `qwen3-embedding:0.6b`
3. Kiểm tra số chiều rồi gọi Qdrant `/points/query`, lấy tối đa 5 đoạn
4. Giữ ID point, record_id và ô nguồn từ nội dung thực, không đưa đường dẫn temp của máy nguồn ra giao diện
5. Đưa các đoạn vào prompt và xây danh mục quy tắc chấm điểm từ chính nội dung đã truy xuất
6. Nguồn Qdrant chứng minh ngưỡng chấm điểm, không thay thế bằng chứng hiện trạng từng ô đất

Metadata của một chunk có thể chỉ mô tả một trong nhiều tiêu chí nằm trong chunk
Vì vậy không lọc cứng theo metadata tiêu chí khi điều đó làm mất phần nội dung khác của cùng chunk
Parser giữ điểm nhóm và hỗ trợ cả bảng Markdown lẫn nhãn điểm ở từng đoạn văn như tiêu chí GPMB

Bản này dùng dense retrieval, không tuyên bố dùng bộ sparse/hybrid của dự án tham khảo
Nếu embedding chưa sẵn sàng hoặc sai số chiều, dùng dự phòng xếp hạng từ khóa trên tối đa 200 point đọc bằng scroll
Giao diện ghi rõ chế độ dự phòng, không thay model và không tái lập chỉ mục
Nếu đã cấu hình Qdrant nhưng không đọc được collection thì báo lỗi, không âm thầm đổi sang bản local
Khi không cấu hình URL Qdrant, chế độ tài liệu local vẫn được giữ để chạy app độc lập

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
