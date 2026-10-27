# Mô hình pipeline cố định

Ứng dụng chỉ đọc file `rf_model_rating_pipeline.pkl` trong thư mục này

File hiện tại là sklearn Pipeline gồm StandardScaler và RandomForestClassifier, nhận các cột x1 đến x9 và trả nhãn 0, 1, 2

Backend gửi dữ liệu gốc vào pipeline.predict để pipeline tự chuẩn hóa, không nạp scaler riêng trong API

Có thể cấu hình thư mục khác bằng `MAP_PREDICT_MODEL_DIR` trước khi khởi động, nên dùng đường dẫn tuyệt đối

`MAP_PREDICT_MODEL_RELEASE` mặc định là `pipeline-v1`, kết quả kèm dấu vân tay SHA-256 của đúng file đã chạy

Để cập nhật, dừng ứng dụng, sao lưu file cũ và đặt pipeline mới vào tên cố định rồi khởi động lại

Đã dọn hai file mô hình và scaler cũ cùng bản pipeline trùng ở thư mục gốc, chỉ giữ pipeline hoạt động trong thư mục này

Chỉ dùng file do chủ ứng dụng tin cậy, không có API upload mô hình hoặc phục vụ file này như tài nguyên tĩnh

Nguồn kỹ thuật về định dạng mô hình tại [scikit-learn](https://scikit-learn.org/stable/model_persistence.html)
