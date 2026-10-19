import numpy as np

# 1. Hàm tính c(n): Chiều cao trung bình của cây BST thất bại (dùng để chuẩn hóa điểm số)
def c(n):
    if n <= 1:
        return 0.0
    if n == 2:
        return 1.0
    # Hằng số Euler-Mascheroni ≈ 0.5772156649
    return 2.0 * (np.log(n - 1) + 0.5772156649) - (2.0 * (n - 1) / n)

# 2. Định nghĩa cấu trúc Nút (Node) trên cây iTree
class Node:
    def __init__(self, left=None, right=None, split_feature=None, split_val=None, size=None, is_leaf=False):
        self.left = left
        self.right = right
        self.split_feature = split_feature
        self.split_val = split_val
        self.size = size        # Số lượng mẫu dừng lại tại nút lá này
        self.is_leaf = is_leaf

# 3. Thuật toán dựng iTree đệ quy
def build_itree(X, current_height, height_limit):
    n_samples, n_features = X.shape
    
    # Điều kiện dừng: Đạt độ sâu giới hạn, số mẫu <= 1, hoặc tất cả giá trị thuộc tính giống hệt nhau
    if current_height >= height_limit or n_samples <= 1:
        return Node(size=n_samples, is_leaf=True)
    
    # Chọn ngẫu nhiên 1 thuộc tính (feature)
    feat_idx = np.random.randint(0, n_features)
    feat_min = X[:, feat_idx].min()
    feat_max = X[:, feat_idx].max()
    
    if feat_min == feat_max:
        return Node(size=n_samples, is_leaf=True)
    
    # Chọn ngẫu nhiên điểm cắt p nằm giữa min và max
    split_val = np.random.uniform(feat_min, feat_max)
    
    left_mask = X[:, feat_idx] < split_val
    right_mask = ~left_mask
    
    left_child = build_itree(X[left_mask], current_height + 1, height_limit)
    right_child = build_itree(X[right_mask], current_height + 1, height_limit)
    
    return Node(left=left_child, right=right_child, split_feature=feat_idx, split_val=split_val, is_leaf=False)

# 4. Tính độ dài đường đi h(x) của 1 điểm dữ liệu x trên cây
def path_length(x, node, current_height):
    if node.is_leaf:
        # Nếu dừng ở nút lá có size > 1, cộng thêm giá trị kỳ vọng c(size)
        return current_height + c(node.size)
    
    if x[node.split_feature] < node.split_val:
        return path_length(x, node.left, current_height + 1)
    else:
        return path_length(x, node.right, current_height + 1)

# 5. Lớp IsolationForest hoàn chỉnh
class CustomIsolationForest:
    def __init__(self, n_estimators=100, max_samples=256):
        self.n_estimators = n_estimators
        self.max_samples = max_samples
        self.trees = []
        
    def fit(self, X):
        n_samples = X.shape[0]
        subsample_size = min(self.max_samples, n_samples)
        # Chiều cao tối đa của cây h_limit = ceil(log2(subsample_size))
        height_limit = int(np.ceil(np.log2(max(subsample_size, 2))))
        
        self.trees = []
        for _ in range(self.n_estimators):
            # Rút mẫu ngẫu nhiên (Sub-sampling)
            indices = np.random.choice(n_samples, size=subsample_size, replace=False)
            tree = build_itree(X[indices], 0, height_limit)
            self.trees.append(tree)
        return self

    def compute_anomaly_score(self, X):
        paths = np.zeros((X.shape[0], self.n_estimators))
        for i, tree in enumerate(self.trees):
            for j in range(X.shape[0]):
                paths[j, i] = path_length(X[j], tree, 0)
        
        E_h = np.mean(paths, axis=1)  # Độ sâu đường đi trung bình E(h(x))
        c_factor = c(self.max_samples)
        
        # Công thức tính điểm s = 2^(-E_h / c(n))
        scores = 2 ** (- (E_h / c_factor))
        return scores