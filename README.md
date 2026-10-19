# Đồ án: Phát hiện truy cập bất thường vào Cơ sở dữ liệu MySQL bằng Isolation Forest

Dự án này là sự kết hợp giữa việc tái hiện bài báo khoa học *"Enhancing Security of Databases through Anomaly Detection in Structured Workloads"* và phát triển một hệ thống thực tế hoàn chỉnh. Nhóm đã tự cài đặt thuật toán Isolation Forest từ đầu, xây dựng Dashboard trực quan, và đánh giá nghiêm túc trên dữ liệu log giả lập lẫn log thật của MySQL.

## 🌟 Điểm nổi bật của dự án (So với bài báo gốc)

1. **Tự cài đặt thuật toán (Custom Isolation Forest):** Thay vì chỉ dùng thư viện `scikit-learn`, nhóm đã tự viết mã nguồn thuật toán Isolation Forest (iTree) từ đầu bằng Python.
2. **Đánh giá đa chiều:** Không chỉ dừng ở Accuracy, nhóm đánh giá mô hình qua 3 seeds, 4 mức `contamination` khác nhau và tính cả ROC-AUC, PR-AUC.
3. **Hệ thống hoàn chỉnh:** Dashboard Tkinter kết nối trực tiếp MySQL, cho phép nạp log thật, phân tích và trực quan hóa điểm bất thường (Tooltip, biểu đồ màu).
4. **Trung thực khoa học:** Nhóm đã phát hiện ra lỗi mâu thuẫn số liệu trong bài báo gốc (báo cáo đạt 85% nhưng thực tế khi tái hiện chỉ đạt 65-68%) và ghi nhận rõ ràng.

## 📂 Cấu trúc thư mục

```text
├── Hiếu_workspace/                  # Phần nghiên cứu lý thuyết và thuật toán
│   ├── 1_diabetes_replication/      # Tái hiện thí nghiệm bài báo trên dữ liệu tiểu đường
│   ├── 2_theory_and_custom_itree/   # Cơ sở lý thuyết & Code thuật toán Custom Isolation Forest
│   └── 3_pipeline_evaluation/       # Script đánh giá mô hình (ROC-AUC, đa seed)
├── Quân&Vương/                      # Phần ứng dụng thực tế và giao diện
│   ├── app.py                       # Dashboard chính (Tkinter + Custom Isolation Forest)
│   ├── dataset_v1.csv               # Dataset giả lập (542 dòng, 42 ca tấn công)
│   ├── config.py                    # Cấu hình kết nối MySQL (đã tách riêng)
│   ├── evaluation.py                # Tính toán metric (Precision, Recall, F1)
│   ├── mysql_log_importer.py        # Script nhập log thật từ MySQL
│   ├── performance_metrics.py       # Đo lường thời gian chạy từ performance_schema
│   └── schema.sql                   # Tạo Database và bảng
└── README.md                        # File mô tả dự án
```
# 🚀 Hướng dẫn cài đặt và chạy Demo
1. Yêu cầu hệ thống
Đã cài đặt Python 3.9+.

Đã cài đặt MySQL Server (Khuyến nghị dùng XAMPP).

Các thư viện Python: pip install -r Quân&Vương/requirements.txt

## 2. Thiết lập Cơ sở dữ liệu
Mở XAMPP, bật module MySQL.

Mở MySQL Workbench hoặc phpMyAdmin, copy toàn bộ nội dung file Quân&Vương/schema.sql và chạy để tạo Database security_demo.

Mở file Quân&Vương/config.py, kiểm tra lại thông tin user và password cho khớp với MySQL trên máy bạn (mặc định XAMPP là user root, pass trống).

## 3. Khởi chạy Dashboard
Mở Terminal tại thư mục Quân&Vương và chạy lệnh sau:

bash
python app.py
Nhấn Tạo dữ liệu demo để nạp 542 dòng dữ liệu mẫu vào MySQL.

Nhấn Phân tích Isolation Forest để chạy thuật toán của Hiếu và xem điểm bất thường.

Rê chuột vào các cột biểu đồ để xem chi tiết điểm số.

## 4. Chạy Script Đánh giá tự động (Dành cho báo cáo)
Mở Terminal tại thư mục Hiếu_workspace/3_pipeline_evaluation và chạy lệnh sau:

```text
python evaluate_pipeline.py
```
Script sẽ tự động chạy so sánh giữa Custom Model và Sklearn qua nhiều seed, sau đó xuất kết quả ra file evaluation_results.csv.

## 📊 Kết quả Đánh giá nổi bật
Dựa trên kết quả chạy script đánh giá trên tập dataset_v1.csv:

Custom Isolation Forest (của nhóm): ROC-AUC đạt 0.8392, PR-AUC đạt 0.3765.

Sklearn Isolation Forest: ROC-AUC đạt 0.8311, PR-AUC đạt 0.3084.

Kết luận: Thuật toán tự viết của nhóm không chỉ hoạt động chính xác mà còn có khả năng xếp hạng rủi ro (ROC-AUC) tốt hơn thư viện chuẩn.

## ⚠️ Hạn chế và Hướng phát triển
Khả năng mở rộng (Scalability): Thuật toán Custom hiện dùng vòng lặp Python nên sẽ chạy chậm nếu dữ liệu tăng lên 10.000+ dòng. Hướng khắc phục: Vector hóa bằng NumPy hoặc dùng phân trang (Pagination) trên giao diện.

Chỉ số đo lường từ MySQL: Log thật của MySQL không cung cấp rows_examined trực tiếp cho mỗi câu lệnh trong bảng log. Hệ thống hiện tại chỉ hiển thị được duration_ms. Hướng khắc phục: Tích hợp sâu hơn với performance_schema và đồng bộ dữ liệu real-time.
