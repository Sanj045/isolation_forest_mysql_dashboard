"""Evaluation helpers for Isolation Forest predictions on manually labelled rows."""
import pandas as pd
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix


def evaluate_labeled_rows(results):
    """Return metrics only for rows whose ground_truth_anomaly label is known.

    ground_truth_anomaly: 1 = confirmed anomaly, 0 = confirmed normal, NULL = unknown.
    Isolation Forest prediction: -1 = flagged anomaly, 1 = normal.
    """
    if results is None or results.empty or "ground_truth_anomaly" not in results.columns:
        return None, "Chưa có dữ liệu có nhãn để đánh giá."

    labeled = results[results["ground_truth_anomaly"].notna()].copy()
    if len(labeled) < 2:
        return None, "Cần ít nhất 2 bản ghi đã gán nhãn (0 hoặc 1)."

    y_true = pd.to_numeric(labeled["ground_truth_anomaly"], errors="coerce")
    valid = y_true.isin([0, 1])
    labeled = labeled.loc[valid]
    y_true = y_true.loc[valid].astype(int)
    if len(labeled) < 2 or y_true.nunique() < 2:
        return None, (
            "Cần có cả hai loại nhãn: 0 = bình thường đã xác minh, "
            "1 = bất thường đã xác minh. Log thật mới nhập có nhãn NULL, "
            "vì mô hình không thể tự biết sự kiện nào chắc chắn là tấn công."
        )

    y_pred = (labeled["prediction"] == -1).astype(int)
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    metrics = {
        "sample_count": int(len(labeled)),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "tn": int(cm[0, 0]), "fp": int(cm[0, 1]),
        "fn": int(cm[1, 0]), "tp": int(cm[1, 1]),
    }
    return metrics, None
