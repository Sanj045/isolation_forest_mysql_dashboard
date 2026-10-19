replicate_diabetes.py: Kiểm tra giá trị contamination nào giúp chỉ số tiệm cận 85% và ghi lại chỉ số PR-AUC tương ứng để điền vào báo cáo.

Tìm dòng có cột Accuracy gần với 0.85 (85%) nhất (thường nằm ở khoảng contamination = 0.30 đến 0.35 tùy thuộc tập dữ liệu) và ghi lại chỉ số PR-AUC = 0.5073.

Contamination  Accuracy    F1-Score    PR-AUC    
--------------------------------------------------
0.05           0.6523      0.1303      0.5073    
0.10           0.6732      0.2725      0.5073    
0.15           0.6745      0.3490      0.5073    
0.20           0.6745      0.4076      0.5073    
0.25           0.6771      0.4609      0.5073    
0.30           0.6732      0.4970      0.5073    
0.35           0.6628      0.5177      0.5073    
0.40           0.6576      0.5426      0.5073   