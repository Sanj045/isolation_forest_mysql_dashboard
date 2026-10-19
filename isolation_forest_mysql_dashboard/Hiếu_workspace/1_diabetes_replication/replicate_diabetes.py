import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.metrics import precision_recall_curve, auc, accuracy_score, f1_score

# 1. Đọc dữ liệu
df = pd.read_csv('diabetes.csv')
X = df.drop('Outcome', axis=1)
y = df['Outcome'] #1: là bệnh nhân bị tiểu đường coi là anomaly; 0 là:bình thường

contaminations = np.arange(0.05, 0.45, 0.05)

# Tính PR-AUC cố định theo decision_function
clf_base = IsolationForest(random_state=42).fit(X)
scores = -clf_base.decision_function(X)
precision, recall, _ = precision_recall_curve(y, scores)
pr_auc = auc(recall, precision)

#Tại sao PR-AUC không thay đổi theo contamination? 
#Bởi vì PR-AUC đánh giá khả năng xếp hạng của mô hình trên dãy điểm liên tục, không bị ảnh hưởng bởi việc ta đặt ngưỡng nhãn phân loại cứng là bao nhiêu.

print(f"{'Contamination':<15}{'Accuracy':<12}{'F1-Score':<12}{'PR-AUC':<10}")
print("-" * 50)

for c in contaminations:
    clf = IsolationForest(contamination=c, random_state=42)
    preds = clf.fit_predict(X)
    # IsolationForest trả về -1 (anomaly), đổi thành 1 để so sánh với y (Outcome)
    y_pred = np.where(preds == -1, 1, 0)
    
    acc = accuracy_score(y, y_pred)
    f1 = f1_score(y, y_pred)
    
    print(f"{c:<15.2f}{acc:<12.4f}{f1:<12.4f}{pr_auc:<10.4f}")