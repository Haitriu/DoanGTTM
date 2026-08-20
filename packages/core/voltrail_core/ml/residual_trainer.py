import numpy as np
from sklearn.ensemble import RandomForestRegressor
from typing import List, Dict, Any
import pickle

class ResidualTrainer:
    """
    Huấn luyện mô hình Machine Learning để dự đoán phần dư (Residual Error).
    Error = Actual Energy - Physics Energy
    Model(Temperature, Speed, Headwind) -> Error
    """
    def __init__(self):
        self.model = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42)
        self.is_trained = False
        self.X_train: List[List[float]] = []
        self.y_train: List[float] = []
        
    def add_training_data(self, temp_c: float, speed_mps: float, headwind_mps: float, physics_kwh: float, actual_kwh: float):
        """
        Thu thập dữ liệu từ Telemetry để chuẩn bị huấn luyện.
        """
        features = [temp_c, speed_mps, headwind_mps]
        residual = actual_kwh - physics_kwh
        
        self.X_train.append(features)
        self.y_train.append(residual)
        
    def train(self):
        """
        Huấn luyện mô hình trên dữ liệu đã thu thập.
        """
        if len(self.X_train) < 10:
            print("[ML] Chưa đủ dữ liệu để huấn luyện (Cần >= 10 mẫu).")
            return
            
        X = np.array(self.X_train)
        y = np.array(self.y_train)
        
        self.model.fit(X, y)
        self.is_trained = True
        
        score = self.model.score(X, y)
        print(f"[ML] Đã huấn luyện mô hình Random Forest. R^2 Score (Training): {score:.3f}")
        
    def predict_residual(self, temp_c: float, speed_mps: float, headwind_mps: float) -> float:
        """
        Dự đoán sai số năng lượng (kWh) do các yếu tố môi trường.
        """
        if not self.is_trained:
            return 0.0
            
        X_test = np.array([[temp_c, speed_mps, headwind_mps]])
        predicted_error = self.model.predict(X_test)[0]
        return float(predicted_error)
        
    def save_model(self, filepath: str):
        if self.is_trained:
            with open(filepath, 'wb') as f:
                pickle.dump(self.model, f)
                
    def load_model(self, filepath: str):
        try:
            with open(filepath, 'rb') as f:
                self.model = pickle.load(f)
                self.is_trained = True
        except FileNotFoundError:
            print(f"[ML] File model không tồn tại: {filepath}")
