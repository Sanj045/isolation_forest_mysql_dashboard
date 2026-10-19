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
