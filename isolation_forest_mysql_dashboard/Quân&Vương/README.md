# Database Access Anomaly Dashboard — Isolation Forest + MySQL General Log

Project học tập gồm Python, MySQL, scikit-learn Isolation Forest, Tkinter và Matplotlib. Giao diện `app.py` hiện có được giữ lại và bổ sung chức năng nhập MySQL General Log cùng đánh giá mô hình trên những bản ghi có nhãn đã xác minh.

## 1. Cài đặt

1. Dùng MySQL80 đang chạy trên máy (không cần khởi động MySQL của XAMPP nếu cùng dùng cổng 3306).
2. Mở MySQL Workbench hoặc `mysql` client và chạy `schema.sql`.
3. Mở `app.py`, sửa `DB_CONFIG` cho khớp host, port, user, password và database `security_demo` của máy bạn. Không chia sẻ mật khẩu và không đưa mật khẩu vào ảnh chụp báo cáo.
4. Mở terminal trong thư mục project và chạy:

   ```bash
   python -m pip install -r requirements.txt
   python app.py
   ```

Nếu bảng `activity_logs` đã tồn tại, ứng dụng sẽ đổi cột `ground_truth_anomaly` sang cho phép `NULL`; các giá trị nhãn cũ không bị tự đổi. Bản ghi nhập từ log thật được lưu với nhãn `NULL` để tránh nhầm lẫn rằng chưa biết nghĩa là bình thường.

## 2. Thu thập MySQL General Log an toàn trong lab

General Log có thể ghi lại câu lệnh SQL và dữ liệu nhạy cảm. Chỉ bật tạm thời trên MySQL cục bộ/lab, không bật kéo dài trên máy chủ sản xuất. Dùng tài khoản quản trị được phép thực hiện các lệnh này.

1. Mở MySQL Workbench hoặc MySQL client và kiểm tra cấu hình:

   ```sql
   SHOW VARIABLES LIKE 'general_log';
   SHOW VARIABLES LIKE 'log_output';
   ```

2. Bật ghi log vào bảng cho một phiên thực hành ngắn:

   ```sql
   SET GLOBAL log_output = 'TABLE';
   SET GLOBAL general_log = 'ON';
   ```

3. Trong vài phút, thực hiện các truy vấn hợp lệ trên cơ sở dữ liệu lab mà bạn được phép kiểm tra. Không chạy lệnh phá hoại hoặc truy vấn dữ liệu nhạy cảm chỉ để tạo bất thường.
4. Tắt General Log sau khi thu thập xong:

   ```sql
   SET GLOBAL general_log = 'OFF';
   ```

   Có thể khôi phục `log_output` về giá trị trước đó nếu bạn đã ghi lại nó.

5. Chạy `python app.py`. Nhấn **Nhập MySQL General Log** rồi nhấn **Phân tích Isolation Forest**. Chức năng nhập đọc tối đa 10.000 sự kiện Query/Execute gần nhất, bỏ qua các lệnh không thuộc nhóm phân tích và dùng khóa SHA-256 để hạn chế nhập trùng.

Nếu báo lỗi quyền truy cập `mysql.general_log`, tài khoản kết nối trong `DB_CONFIG` cần quyền đọc phù hợp. Không cấp quyền rộng hơn mức cần thiết cho tài khoản ứng dụng chỉ để bỏ qua kiểm soát bảo mật; trong lab có thể dùng tài khoản quản trị cục bộ rồi hạn chế lại sau đó.

## 3. Các nút trong dashboard

- **Tạo dữ liệu demo**: thêm dữ liệu giả lập có nhãn để thử giao diện và minh họa đánh giá.
- **Tải dữ liệu**: đọc bảng `security_demo.activity_logs`.
- **Nhập MySQL General Log**: chuyển các câu lệnh quan sát được thành sự kiện phân tích. Nội dung SQL thô không được lưu vào `details`.
- **Phân tích Isolation Forest**: phân loại các sự kiện theo đặc trưng đã tạo.
- **Đánh giá mô hình**: tính Accuracy, Precision, Recall, F1-score và confusion matrix chỉ trên các bản ghi có nhãn 0/1 đã xác minh.
- **Xuất CSV**: xuất các dòng và điểm phân tích hiện tại.

## 4. Đặc trưng và giới hạn của General Log

Mô hình sử dụng giờ trong ngày, số dòng ảnh hưởng, thời gian truy vấn, tần suất truy vấn trong 5 phút, loại thao tác, vai trò và hoạt động ngoài giờ. Tần suất 5 phút được suy ra từ các sự kiện đã thu thập.

MySQL General Log ghi thời điểm, tài khoản/host, loại lệnh và nội dung lệnh, nhưng không cung cấp trực tiếp số dòng bị tác động hay thời gian thực thi cho mỗi truy vấn. Vì vậy các sự kiện nhập từ General Log được gán `rows_affected = 0` và `duration_ms = 0`; các trường này không phải số đo thực tế. Nếu cần các số đo đó, hãy bổ sung instrument tại ứng dụng hoặc dùng Performance Schema/slow query log phù hợp, sau khi kiểm tra quyền riêng tư và cấu hình.

Isolation Forest là mô hình không giám sát: nó gắn cờ các điểm khác biệt so với phần còn lại, không chứng minh một sự kiện là tấn công. `contamination` hiện là tham số ước lượng tỷ lệ điểm bị gắn cờ, cần hiệu chỉnh với dữ liệu thực tế.

## 5. Đánh giá đúng cách

`ground_truth_anomaly` có ba trạng thái:

- `0`: đã được kiểm tra và xác nhận bình thường.
- `1`: đã được kiểm tra và xác nhận bất thường.
- `NULL`: chưa xác minh (mặc định cho log thật vừa nhập).

Để tính các chỉ số có ý nghĩa, cần có cả nhãn 0 và 1 đã được xác minh. Có thể gán nhãn trong một quy trình kiểm tra riêng rồi cập nhật cột này cho các ID đã rà soát. Không gán nhãn 1 chỉ vì Isolation Forest đã gắn cờ; như vậy sẽ đánh giá mô hình bằng chính dự đoán của nó. Nếu không có nhãn xác thực, dashboard vẫn hiển thị số sự kiện bị gắn cờ nhưng không thể báo cáo Accuracy/Precision/Recall/F1 đáng tin cậy.

## 6. SQL kiểm tra nhanh

```sql
USE security_demo;
SELECT COUNT(*) AS total_events FROM activity_logs;
SELECT operation, COUNT(*) AS total
FROM activity_logs
GROUP BY operation
ORDER BY total DESC;
SELECT id, event_time, db_user, operation, table_name, ground_truth_anomaly
FROM activity_logs
ORDER BY event_time DESC
LIMIT 20;
```


## 7. Dataset cố định `dataset_v1.csv`

Trong thư mục này chỉ có một dataset chính dùng chung cho cả nhóm: `dataset_v1.csv`. Dataset được tạo bởi `generate_dataset.py` với seed `20261016`; 542 dòng gồm 500 normal và 42 dòng thuộc kịch bản tấn công. Các cột nhãn là `is_attack` và `attack_type` (các cột còn lại là đặc trưng/ngữ cảnh). Để tái tạo cùng nội dung:

```powershell
python generate_dataset.py
```

Không sửa seed nếu cần các thành viên có cùng dataset. CSV có các kịch bản ngoài giờ, `duration_ms` bình thường theo phân bố log-normal, và `low_and_slow` trong giờ làm việc. Tấn công low-and-slow cố ý có thời lượng/số dòng chồng lấn với hoạt động bình thường; các nhãn là nhãn kịch bản sinh dữ liệu, không phải dự đoán mô hình.

Nút **Tạo dữ liệu demo** đọc chính `dataset_v1.csv` rồi chèn vào MySQL. Để tránh nhân bản dataset nhiều lần, chỉ nhấn nút một lần trên database trống hoặc làm sạch dữ liệu demo theo quy trình của nhóm trước khi nạp lại. Không xóa log thật.

## 8. Tách nguồn khi huấn luyện

`app.py` không fit Isolation Forest trên hỗn hợp demo + log thật. Mỗi lần phân tích, mô hình được fit chỉ trên các dòng `is_attack=0` của `dataset_v1.csv`; sau đó dùng mô hình đó để dự đoán các dòng đang hiển thị từ MySQL. Các log thật không tham gia bước `fit`. Chỉ các dòng có nhãn `ground_truth_anomaly` đã xác minh mới được dùng để tính chỉ số đánh giá.

Lưu ý: các sự kiện demo được chèn vào MySQL có nhãn ground truth từ kịch bản dataset; log thật nhập từ General Log mặc định vẫn `NULL`.

## 9. Đo thời gian thực thi và số dòng thật

General Log không đo thời gian chạy hay số dòng. Script `performance_metrics.py` đọc số đo do server ghi trong `performance_schema.events_statements_history_long` (nếu tính năng được bật và tài khoản có quyền đọc):

```powershell
python performance_metrics.py --limit 1000 --out performance_metrics.jsonl
```

Đầu ra JSONL gồm `ROWS_AFFECTED`, `ROWS_SENT`, `ROWS_EXAMINED` và `duration_ms` tính từ `TIMER_WAIT`. Đây là số đo server, không phải giá trị mô phỏng. Bảng history có thể bị ghi đè theo dung lượng cấu hình; cần bật consumer/instrument phù hợp và quyền `SELECT` trên `performance_schema`. Nếu MariaDB/XAMPP không cung cấp hoặc không bật bảng history này, dùng slow query log trong lab như phương án thay thế. Không bật `long_query_time=0` trên máy chủ sản xuất vì nó ghi mọi truy vấn và có thể gây overhead/ghi dữ liệu nhạy cảm.

## 10. Ground-truth cho log thật theo khung thời gian lab

Trước khi chạy kịch bản, ghi lại thời gian bắt đầu/kết thúc, tài khoản DB, `client_host` mà dashboard lưu, loại kịch bản và ghi chú. Sau khi nhập log, chạy script sau để gán nhãn theo **khung thời gian + tài khoản + client host đã ghi nhận**, không dựa vào dự đoán Isolation Forest:

```powershell
python label_lab_window.py --start "2026-10-16T10:00:00" --end "2026-10-16T10:05:00" --account "student01" --client-host "127.0.0.1" --is-attack 1 --attack-type "low_and_slow" --notes "Lab run 01"
```

Thay các giá trị bằng dữ liệu thật của lần chạy. Script chỉ cập nhật các dòng khớp thời gian, tài khoản và host; đồng thời ghi một bản ghi manifest vào `lab_ground_truth_manifest.jsonl`. Để gán nhãn bình thường đã xác minh, dùng `--is-attack 0 --attack-type normal`. mysql_log_importer.py hiện tại đã tự động trích xuất IP thật từ trường user_host của MySQL General Log và gán vào cột client_host. Do đó, bạn có thể yên tâm sử dụng IP thực tế này để chạy script gán nhãn theo khung thời gian lab.

Nhãn thủ công là nhãn ground-truth; dự đoán của mô hình không bao giờ được dùng để sinh nhãn. Manifest lưu thông tin vận hành lab, không lưu câu SQL thô hoặc mật khẩu.

## 11. Lưu ý về số đo hiệu năng

Với `performance_schema`, kiểm tra trước:

```sql
SHOW VARIABLES LIKE 'performance_schema';
SELECT NAME, ENABLED
FROM performance_schema.setup_consumers
WHERE NAME LIKE '%statements%';
```

Nếu cần dùng slow query log, chỉ thực hiện trên instance lab, ghi lại cấu hình hiện tại trước khi thay đổi và khôi phục sau khi đo. `long_query_time=0` ghi mọi câu lệnh; theo dõi kích thước log và không thu thập dữ liệu nhạy cảm. XAMPP/MariaDB có thể khác nhau về bảng Performance Schema sẵn có, vì vậy script báo lỗi rõ ràng nếu bảng đo không khả dụng.
