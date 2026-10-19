import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta
import random
from pathlib import Path
from collections import defaultdict, deque

import numpy as np
import mysql.connector
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from mysql_log_importer import import_general_log
from evaluation import evaluate_labeled_rows

# Import mô hình Custom của Hiếu
from custom_iforest import CustomIsolationForest
from config import DB_CONFIG

FEATURE_COLUMNS = [
    "hour", "rows_affected", "duration_ms", "queries_last_5m",
    "is_delete", "is_write", "is_admin", "is_after_hours",
]


def get_connection():
    return mysql.connector.connect(**DB_CONFIG)


def ensure_table():
    # Database and table should first be created by running schema.sql.
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM activity_logs LIMIT 1")
        cur.fetchone()  # Consume the result to avoid MySQL's "Unread result found" error.
        # NULL means unknown label for real logs; do not silently treat it as normal.
        cur.execute("ALTER TABLE activity_logs MODIFY ground_truth_anomaly TINYINT(1) NULL DEFAULT NULL")
        cur.close()
    finally:
        conn.close()


def generate_demo_data():
    """Insert the deterministic dataset_v1.csv into MySQL as demo-only rows."""
    dataset_path = Path(__file__).resolve().parent / "dataset_v1.csv"
    if not dataset_path.exists():
        raise FileNotFoundError(
            f"Không tìm thấy {dataset_path}. Chạy `python generate_dataset.py` trước."
        )
    data = pd.read_csv(dataset_path)
    rows = []
    for _, row in data.iterrows():
        label = int(row["is_attack"])
        attack_type = str(row["attack_type"])
        details = f"DEMO_DATASET_V1; attack_type={attack_type}; {row['details']}"
        rows.append((
            pd.to_datetime(row["event_time"]).to_pydatetime(),
            str(row["db_user"]), str(row["user_role"]), str(row["client_host"]),
            str(row["operation"]), str(row["table_name"]), int(row["rows_affected"]),
            float(row["duration_ms"]), int(row["queries_last_5m"]), str(row["status"]),
            details, label,
        ))
    conn = get_connection()
    try:
        cur = conn.cursor()
        # XÓA DỮ LIỆU DEMO CŨ TRƯỚC KHI NẠP MỚI ĐỂ TRÁNH NHÂN ĐÔI
        cur.execute("DELETE FROM activity_logs WHERE details LIKE 'DEMO_DATASET_V1%'")
        
        cur.executemany(
            """INSERT INTO activity_logs
            (event_time, db_user, user_role, client_host, operation, table_name,
             rows_affected, duration_ms, queries_last_5m, status, details, ground_truth_anomaly)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", rows
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def load_data():
    conn = get_connection()
    try:
        return pd.read_sql(
            """SELECT id, event_time, db_user, user_role, client_host, operation,
                      table_name, rows_affected, duration_ms, queries_last_5m,
                      status, details, ground_truth_anomaly
               FROM activity_logs ORDER BY event_time DESC""", conn
        )
    finally:
        conn.close()


def add_features(df):
    out = df.copy()
    out["event_time"] = pd.to_datetime(out["event_time"])
    out["hour"] = out["event_time"].dt.hour
    out["is_delete"] = (out["operation"].str.upper() == "DELETE").astype(int)
    out["is_write"] = out["operation"].str.upper().isin(["INSERT", "UPDATE", "DELETE", "REPLACE", "DROP", "ALTER"]).astype(int)
    out["is_admin"] = (out["user_role"].str.lower() == "admin").astype(int)
    out["is_after_hours"] = ((out["hour"] < 7) | (out["hour"] >= 20)).astype(int)
    for col in ["rows_affected", "duration_ms", "queries_last_5m"]:
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)

    counts = {}
    windows = defaultdict(deque)
    ordered = out.sort_values("event_time")
    for idx, row in ordered.iterrows():
        user = str(row.get("db_user", "unknown"))
        timestamp = row["event_time"]
        window = windows[user]
        while window and (timestamp - window[0]).total_seconds() > 300:
            window.popleft()
        window.append(timestamp)
        counts[idx] = len(window)
    out["queries_last_5m"] = pd.Series(counts).reindex(out.index).fillna(1).astype(int)
    return out


class Dashboard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Database Access Anomaly Dashboard | Isolation Forest")
        self.geometry("1280x800")
        self.minsize(1050, 680)
        self.df = pd.DataFrame()
        self.results = pd.DataFrame()
        self._build_ui()
        self.load_logs(silent=True)

    def _build_ui(self):
        header = ttk.Frame(self, padding=(14, 12))
        header.pack(fill="x")
        ttk.Label(header, text="DATABASE SECURITY DASHBOARD", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(header, text="Phát hiện bất thường truy cập MySQL bằng Isolation Forest", font=("Segoe UI", 10)).pack(anchor="w", pady=(3, 0))

        toolbar = ttk.Frame(self, padding=(14, 0, 14, 10))
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="Tạo dữ liệu demo", command=self.seed_data).pack(side="left", padx=(0, 8))
        ttk.Button(toolbar, text="Tải dữ liệu", command=self.load_logs).pack(side="left", padx=(0, 8))
        ttk.Button(toolbar, text="Nhập MySQL General Log", command=self.import_mysql_logs).pack(side="left", padx=(0, 8))
        ttk.Button(toolbar, text="Phân tích Isolation Forest", command=self.analyze).pack(side="left", padx=(0, 8))
        ttk.Button(toolbar, text="Đánh giá mô hình", command=self.evaluate_model).pack(side="left", padx=(0, 8))
        ttk.Button(toolbar, text="Xuất CSV", command=self.export_csv).pack(side="left")
        self.status_var = tk.StringVar(value="Sẵn sàng")
        ttk.Label(toolbar, textvariable=self.status_var).pack(side="right")

        cards = ttk.Frame(self, padding=(14, 0, 14, 10))
        cards.pack(fill="x")
        self.kpi_total = self._kpi(cards, "TỔNG SỰ KIỆN", "—", 0)
        self.kpi_anomaly = self._kpi(cards, "BỊ GẮN CỜ", "—", 1)
        self.kpi_normal = self._kpi(cards, "BÌNH THƯỜNG", "—", 2)
        self.kpi_rate = self._kpi(cards, "TỶ LỆ BẤT THƯỜNG", "—", 3)
        for i in range(4):
            cards.columnconfigure(i, weight=1)

        body = ttk.Panedwindow(self, orient="vertical")
        body.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        chart_frame = ttk.Frame(body)
        table_frame = ttk.Frame(body)
        body.add(chart_frame, weight=3)
        body.add(table_frame, weight=2)

        self.figure = Figure(figsize=(10, 3.4), dpi=100, constrained_layout=True)
        self.ax1 = self.figure.add_subplot(121)
        self.ax2 = self.figure.add_subplot(122)
        self.canvas = FigureCanvasTkAgg(self.figure, master=chart_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self._empty_charts()
        
        # KẾT NỐI SỰ KIỆN DI CHUỘT ĐỂ HIỂN THỊ TOOLTIP
        self.canvas.mpl_connect("motion_notify_event", self._on_hover)

        ttk.Label(table_frame, text="NHẬT KÝ VÀ CẢNH BÁO", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(4, 6))
        columns = ("id", "time", "user", "role", "operation", "table", "rows", "duration", "score", "label", "details")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=10)
        headings = {"id":"ID", "time":"Thời gian", "user":"Tài khoản", "role":"Vai trò", "operation":"SQL", "table":"Bảng", "rows":"Số dòng", "duration":"ms", "score":"Điểm", "label":"Kết quả", "details":"Chi tiết"}
        widths = {"id":55, "time":145, "user":100, "role":75, "operation":75, "table":95, "rows":75, "duration":70, "score":70, "label":130, "details":300}
        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], minwidth=50, anchor="w")
        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        xscroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.tree.pack(side="top", fill="both", expand=True)
        xscroll.pack(side="bottom", fill="x")
        yscroll.place(relx=1.0, rely=0.15, relheight=0.75, anchor="ne")
        self.tree.tag_configure("anomaly", foreground="#b42318")
        self.tree.tag_configure("normal", foreground="#18794e")

    def _kpi(self, parent, title, value, column):
        frame = ttk.LabelFrame(parent, text=title, padding=12)
        frame.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 6, 0))
        label = ttk.Label(frame, text=value, font=("Segoe UI", 20, "bold"))
        label.pack(anchor="w")
        return label

    def _empty_charts(self):
        self.ax1.clear(); self.ax2.clear()
        self.ax1.set_title("Phân bố kết quả")
        self.ax1.text(0.5, 0.5, "Tải dữ liệu và chạy phân tích", ha="center", va="center", transform=self.ax1.transAxes)
        self.ax1.set_xticks([]); self.ax1.set_yticks([])
        self.ax2.set_title("Điểm bất thường")
        self.ax2.text(0.5, 0.5, "Chưa có kết quả", ha="center", va="center", transform=self.ax2.transAxes)
        self.ax2.set_xticks([]); self.ax2.set_yticks([])
        self.canvas.draw_idle()

    def load_logs(self, silent=False):
        try:
            self.df = load_data()
            self.results = pd.DataFrame()
            self._refresh_table(self.df, analyzed=False)
            self.kpi_total.config(text=str(len(self.df)))
            self.kpi_anomaly.config(text="—")
            self.kpi_normal.config(text="—")
            self.kpi_rate.config(text="—")
            self._empty_charts()
            self.status_var.set(f"Đã tải {len(self.df)} sự kiện")
            if not silent:
                messagebox.showinfo("Thành công", f"Đã tải {len(self.df)} sự kiện từ MySQL.")
        except mysql.connector.Error as exc:
            self.status_var.set("Không kết nối được MySQL")
            if not silent:
                messagebox.showerror("Lỗi MySQL", f"Không thể đọc dữ liệu. Hãy kiểm tra XAMPP, schema.sql và DB_CONFIG.\n\nChi tiết: {exc}")

    def import_mysql_logs(self):
        try:
            count = import_general_log(get_connection)
            self.load_logs(silent=True)
            messagebox.showinfo(
                "Nhập log MySQL hoàn tất",
                f"Đã nhập {count} sự kiện mới từ mysql.general_log.\n\n"
                "Các sự kiện log thật được gán nhãn ground_truth_anomaly = NULL "
                "vì chưa có xác minh bình thường/bất thường. Hãy nhấn Phân tích Isolation Forest."
            )
        except Exception as exc:
            messagebox.showerror("Không nhập được MySQL log", str(exc))

    def evaluate_model(self):
        if self.results.empty:
            messagebox.showwarning("Chưa phân tích", "Hãy tải dữ liệu và chạy Isolation Forest trước.")
            return
        metrics, error = evaluate_labeled_rows(self.results)
        if error:
            messagebox.showwarning("Chưa đủ nhãn để đánh giá", error)
            return
        messagebox.showinfo(
            "Đánh giá trên dữ liệu đã gán nhãn",
            f"Số bản ghi có nhãn: {metrics['sample_count']}\n\n"
            f"Accuracy: {metrics['accuracy']:.1%}\n"
            f"Precision: {metrics['precision']:.1%}\n"
            f"Recall: {metrics['recall']:.1%}\n"
            f"F1-score: {metrics['f1']:.1%}\n\n"
            f"Confusion matrix (nhãn thật × dự đoán):\n"
            f"TN={metrics['tn']}  FP={metrics['fp']}\n"
            f"FN={metrics['fn']}  TP={metrics['tp']}\n\n"
            "Chỉ các dòng có nhãn xác minh 0/1 mới được tính. Log mới nhập mặc định NULL, "
            "không được coi là bình thường chỉ vì chưa có nhãn."
        )
        
    def seed_data(self):
        try:
            count = generate_demo_data()
            self.load_logs(silent=True)
            messagebox.showinfo("Đã tạo dữ liệu demo", f"Đã thêm khoảng {count} sự kiện giả lập. Nhấn 'Phân tích Isolation Forest' để phân tích.")
        except mysql.connector.Error as exc:
            messagebox.showerror("Lỗi MySQL", f"Không thể thêm dữ liệu. Hãy kiểm tra XAMPP, schema.sql và DB_CONFIG.\n\nChi tiết: {exc}")

    def analyze(self):
        if self.df.empty:
            messagebox.showwarning("Chưa có dữ liệu", "Hãy tải dữ liệu hoặc tạo dữ liệu demo trước.")
            return
        if len(self.df) < 10:
            messagebox.showwarning("Thiếu dữ liệu", "Nên có ít nhất 10 sự kiện để minh họa Isolation Forest.")
            return
        try:
            # Strict source separation: fit ONLY on confirmed normal rows
            dataset_path = Path(__file__).resolve().parent / "dataset_v1.csv"
            baseline = pd.read_csv(dataset_path)
            baseline = baseline[baseline["is_attack"].astype(int) == 0].copy()
            baseline["ground_truth_anomaly"] = 0
            baseline_features = add_features(baseline)
            X_train = baseline_features[FEATURE_COLUMNS].astype(float)
            
            featured = add_features(self.df)
            X_current = featured[FEATURE_COLUMNS].astype(float)

            # SỬ DỤNG CUSTOM MODEL CỦA HIẾU
            model = CustomIsolationForest(n_estimators=100, max_samples=256)
            model.fit(X_train.values)
            
            # Lấy điểm bất thường (càng cao càng bất thường)
            scores = model.compute_anomaly_score(X_current.values)
            
            # Tự tìm ngưỡng cắt tương đương contamination=0.08
            threshold = np.percentile(scores, 100 * (1 - 0.08))
            
            # Dự đoán: 1 là bất thường, 0 là bình thường (map về -1 và 1 để đồng bộ code cũ)
            prediction = np.where(scores >= threshold, -1, 1)
            
            featured["prediction"] = prediction
            featured["result"] = featured["prediction"].map({-1: "BẤT THƯỜNG", 1: "Bình thường"})
            featured["anomaly_score"] = scores # Lưu điểm số vào DataFrame
            
            self.results = featured
            flagged = int((prediction == -1).sum())
            normal = int((prediction == 1).sum())
            
            self.kpi_total.config(text=str(len(featured)))
            self.kpi_anomaly.config(text=str(flagged))
            self.kpi_normal.config(text=str(normal))
            self.kpi_rate.config(text=f"{flagged / len(featured) * 100:.1f}%")
            self._refresh_table(featured, analyzed=True)
            self._draw_charts(featured)
            self.status_var.set(f"Phân tích xong: {flagged} sự kiện bị gắn cờ (Custom Model)")
            self._show_demo_metrics(featured)
        except Exception as exc:
            messagebox.showerror("Lỗi phân tích", str(exc))

    def _show_demo_metrics(self, featured):
        metrics, error = evaluate_labeled_rows(featured)
        if metrics:
            self.status_var.set(
                f"Phân tích xong (Custom Model): {int((featured['prediction'] == -1).sum())} bị gắn cờ; "
                f"đánh giá được {metrics['sample_count']} dòng có nhãn"
            )

    def _refresh_table(self, df, analyzed):
        for item in self.tree.get_children():
            self.tree.delete(item)
        if df.empty:
            return
        view = df.head(500)
        for _, row in view.iterrows():
            event_time = str(row.get("event_time", ""))[:19]
            result = row.get("result", "Chưa phân tích") if analyzed else "Chưa phân tích"
            is_anomaly = analyzed and row.get("prediction", 1) == -1
            
            # XỬ LÝ ĐIỂM SỐ ĐỂ HIỂN THỊ
            score_str = f"{float(row.get('anomaly_score', 0)):.3f}" if analyzed else "—"
            
            values = (
                row.get("id", ""), event_time, row.get("db_user", ""), row.get("user_role", ""),
                row.get("operation", ""), row.get("table_name", ""), row.get("rows_affected", 0),
                f"{float(row.get('duration_ms', 0)):.1f}", score_str, result, row.get("details", ""),
            )
            self.tree.insert("", "end", values=values, tags=("anomaly" if is_anomaly else "normal",))

    def _draw_charts(self, df):
        self.ax1.clear(); self.ax2.clear()
        
        # 1. Vẽ biểu đồ bên trái
        self.counts = df["result"].value_counts().reindex(["Bình thường", "BẤT THƯỜNG"], fill_value=0)
        colors_ax1 = ["#2471a3" if idx == "Bình thường" else "#b42318" for idx in self.counts.index]
        self.bars1 = self.ax1.bar(self.counts.index, self.counts.values, color=colors_ax1)
        self.ax1.set_title("Số sự kiện theo phân loại")
        self.ax1.set_ylabel("Số sự kiện")
        self.ax1.tick_params(axis="x", labelrotation=10)
        
        max_y1 = max(self.counts.values) if len(self.counts.values) > 0 else 10
        self.ax1.set_ylim(0, max_y1 * 1.25)
        
        # 2. Vẽ biểu đồ bên phải
        scores_df = df.sort_values("anomaly_score", ascending=False).head(50).copy()
        self.scores2 = scores_df["anomaly_score"].values
        self.scores2_pred = scores_df["prediction"].values
        colors_ax2 = ["#c0392b" if p == -1 else "#2471a3" for p in self.scores2_pred]
        self.bars2 = self.ax2.bar(range(len(scores_df)), self.scores2, color=colors_ax2)
        self.ax2.set_title("50 sự kiện có điểm khác thường cao nhất")
        self.ax2.set_xlabel("Sự kiện (xếp theo điểm)")
        self.ax2.set_ylabel("Điểm khác thường")
        
        max_y2 = max(self.scores2) if len(self.scores2) > 0 else 1.0
        self.ax2.set_ylim(0, max_y2 * 1.25)
        
        # 3. Tạo hộp thoại (annotation) ẩn
        bbox_props = dict(boxstyle="round,pad=0.3", fc="#ffffe0", ec="#d4af37", alpha=0.9)
        arrow_props = dict(arrowstyle="->", color="#555555")
        
        self.annot1 = self.ax1.annotate("", xy=(0,0), xytext=(0, 8), textcoords="offset points", 
                                        ha="center", bbox=bbox_props, arrowprops=arrow_props, annotation_clip=False)
        self.annot1.set_visible(False)
        
        self.annot2 = self.ax2.annotate("", xy=(0,0), xytext=(0, 8), textcoords="offset points", 
                                        ha="center", bbox=bbox_props, arrowprops=arrow_props, annotation_clip=False)
        self.annot2.set_visible(False)
        
        self.canvas.draw_idle()

    def _on_hover(self, event):
        # Hàm xử lý khi di chuột qua biểu đồ
        try:
            if not hasattr(self, 'annot1') or not hasattr(self, 'annot2'):
                return

            vis1 = self.annot1.get_visible()
            vis2 = self.annot2.get_visible()

            # Nếu chuột ở biểu đồ bên trái
            if event.inaxes == self.ax1:
                for i, bar in enumerate(self.bars1):
                    if bar.contains(event)[0]:
                        x_pos = bar.get_x() + bar.get_width()/2
                        self.annot1.xy = (x_pos, bar.get_height())
                        
                        # Đổi hướng tooltip dựa vào vị trí cột
                        if i >= len(self.bars1) / 2:
                            self.annot1.set_ha("right")
                            self.annot1.set_position((-10, 8))
                        else:
                            self.annot1.set_ha("left")
                            self.annot1.set_position((10, 8))
                            
                        self.annot1.set_text(f"{self.counts.index[i]}\n{int(self.counts.values[i])} sự kiện")
                        self.annot1.set_visible(True)
                        if vis2: self.annot2.set_visible(False)
                        self.canvas.draw_idle()
                        return
            # Nếu chuột ở biểu đồ bên phải
            elif event.inaxes == self.ax2:
                for i, bar in enumerate(self.bars2):
                    if bar.contains(event)[0]:
                        x_pos = bar.get_x() + bar.get_width()/2
                        self.annot2.xy = (x_pos, bar.get_height())
                        
                        # Đổi hướng tooltip để không bị tràn mép phải
                        if i >= len(self.bars2) / 2:
                            self.annot2.set_ha("right")
                            self.annot2.set_position((-10, 8))
                        else:
                            self.annot2.set_ha("left")
                            self.annot2.set_position((10, 8))
                            
                        status = "Bất thường" if self.scores2_pred[i] == -1 else "Bình thường"
                        self.annot2.set_text(f"Sự kiện top {i+1}\nĐiểm: {self.scores2[i]:.3f}\n({status})")
                        self.annot2.set_visible(True)
                        if vis1: self.annot1.set_visible(False)
                        self.canvas.draw_idle()
                        return

            # Nếu chuột di ra ngoài thì ẩn hộp thoại đi
            if vis1:
                self.annot1.set_visible(False)
                self.canvas.draw_idle()
            if vis2:
                self.annot2.set_visible(False)
                self.canvas.draw_idle()
        except Exception:
            pass # Bỏ qua lỗi nhỏ khi hover để không làm sập app

    def export_csv(self):
        data = self.results if not self.results.empty else self.df
        if data.empty:
            messagebox.showwarning("Không có dữ liệu", "Hãy tải dữ liệu trước khi xuất.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")], initialfile="anomaly_results.csv")
        if not path:
            return
        try:
            data.to_csv(path, index=False, encoding="utf-8-sig")
            messagebox.showinfo("Đã xuất CSV", f"Đã lưu kết quả tại:\n{path}")
        except Exception as exc:
            messagebox.showerror("Lỗi xuất CSV", str(exc))


if __name__ == "__main__":
    try:
        ensure_table()
    except mysql.connector.Error as exc:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Chưa kết nối được MySQL",
            "Hãy khởi động MySQL trong XAMPP và chạy schema.sql trước.\n"
            "Nếu tài khoản MySQL có mật khẩu, hãy sửa DB_CONFIG ở file config.py.\n\n"
            f"Chi tiết: {exc}"
        )
        root.destroy()
        raise SystemExit(1)
    Dashboard().mainloop()