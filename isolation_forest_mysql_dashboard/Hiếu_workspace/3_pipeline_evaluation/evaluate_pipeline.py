import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, precision_recall_curve, auc
from pathlib import Path
import sys

# Import Custom Model của Hiếu
from custom_iforest import CustomIsolationForest

# Đường dẫn tới dataset (lùi 2 cấp để ra thư mục gốc)
DATASET_PATH = Path(__file__).resolve().parent.parent.parent / "Quân&Vương" / "dataset_v1.csv"

def extract_features(df):
    """Trích xuất 8 đặc trưng giống hệt app.py"""
    df = df.copy()
    df['event_time'] = pd.to_datetime(df['event_time'])
    df['hour'] = df['event_time'].dt.hour
    
    df['is_delete'] = (df['operation'] == 'DELETE').astype(int)
    df['is_write'] = df['operation'].isin(['INSERT', 'UPDATE', 'DELETE', 'GRANT']).astype(int)
    df['is_admin'] = (df['user_role'] == 'Admin').astype(int)
    df['is_after_hours'] = ((df['hour'] < 7) | (df['hour'] >= 20)).astype(int)
    
    features = ['hour', 'rows_affected', 'duration_ms', 'queries_last_5m', 
                'is_delete', 'is_write', 'is_admin', 'is_after_hours']
    return df[features].values, df['is_attack'].values

def evaluate_models():
    print(f"Đang đọc dữ liệu từ: {DATASET_PATH}")
    df = pd.read_csv(DATASET_PATH)
    X, y_true = extract_features(df)
    
    # Tách dữ liệu: Chỉ fit trên các dòng bình thường (is_attack = 0)
    X_normal = X[y_true == 0]
    
    results = []
    seeds = [42, 2026, 20261016]
    contaminations = [0.05, 0.08, 0.10, 0.15]
    
    print(f"Bắt đầu chạy đánh giá: {len(seeds)} seeds x {len(contaminations)} mức contamination...\n")

    for seed in seeds:
        for cont in contaminations:
            # ---------------------------------------------------------
            # 1. MÔ HÌNH SKLEARN
            # ---------------------------------------------------------
            clf_sk = IsolationForest(n_estimators=200, contamination=cont, random_state=seed)
            clf_sk.fit(X_normal)
            
            y_pred_sk = clf_sk.predict(X)  # -1 (bất thường), 1 (bình thường)
            y_pred_sk_bin = (y_pred_sk == -1).astype(int) # Đổi về 1 (bất thường), 0 (bình thường)
            
            # Điểm của sklearn: càng thấp càng bất thường -> Đảo dấu để tính ROC-AUC (càng cao càng bất thường)
            scores_sk = -clf_sk.decision_function(X) 
            
            # ---------------------------------------------------------
            # 2. MÔ HÌNH CUSTOM (CỦA HIẾU)
            # ---------------------------------------------------------
            clf_custom = CustomIsolationForest(n_estimators=100, max_samples=256)
            # Seed cho numpy để Custom model tái tạo được kết quả
            np.random.seed(seed) 
            clf_custom.fit(X_normal)
            
            # Custom model trả về điểm s (càng cao càng bất thường)
            scores_custom = clf_custom.compute_anomaly_score(X)
            
            # Tự tìm ngưỡng (threshold) dựa trên contamination cho Custom model
            # Ví dụ contamination=0.08 -> Lấy top 8% điểm cao nhất làm bất thường
            threshold = np.percentile(scores_custom, 100 * (1 - cont))
            y_pred_custom_bin = (scores_custom >= threshold).astype(int)

            # ---------------------------------------------------------
            # 3. TÍNH TOÁN METRICS CHO CẢ 2
            # ---------------------------------------------------------
            for name, y_pred, scores in [
                ("Sklearn", y_pred_sk_bin, scores_sk),
                ("Custom", y_pred_custom_bin, scores_custom)
            ]:
                acc = accuracy_score(y_true, y_pred)
                prec = precision_score(y_true, y_pred, zero_division=0)
                rec = recall_score(y_true, y_pred, zero_division=0)
                f1 = f1_score(y_true, y_pred, zero_division=0)
                
                # ROC-AUC và PR-AUC
                roc_auc = roc_auc_score(y_true, scores)
                p_curve, r_curve, _ = precision_recall_curve(y_true, scores)
                pr_auc = auc(r_curve, p_curve)
                
                results.append({
                    "Model": name, "Seed": seed, "Contamination": cont,
                    "Accuracy": round(acc, 4), "Precision": round(prec, 4), 
                    "Recall": round(rec, 4), "F1-Score": round(f1, 4),
                    "ROC-AUC": round(roc_auc, 4), "PR-AUC": round(pr_auc, 4)
                })

    # Lưu kết quả
    df_results = pd.DataFrame(results)
    out_file = Path(__file__).resolve().parent / "evaluation_results.csv"
    df_results.to_csv(out_file, index=False)
    
    # In bảng tóm tắt (Lấy trung bình cộng qua các seed)
    print("=== BẢNG TÓM TẮT KẾT QUẢ (TRUNG BÌNH QUA CÁC SEED) ===")
    summary = df_results.groupby(["Model", "Contamination"])[["Accuracy", "Precision", "Recall", "F1-Score", "ROC-AUC", "PR-AUC"]].mean().round(4)
    print(summary.to_string())
    print(f"\nĐã lưu toàn bộ kết quả chi tiết vào: {out_file}")

if __name__ == "__main__":
    evaluate_models()