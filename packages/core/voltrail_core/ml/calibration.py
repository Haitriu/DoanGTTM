from typing import Dict

class DriverCalibration:
    """
    Hệ thống tự động học thói quen lái xe.
    Lưu trữ "Driver Factor" (Hệ số bù trừ) cho từng xe dựa trên chênh lệch
    giữa mức tiêu thụ năng lượng thực tế (từ Telemetry) và mức tính toán vật lý.
    """
    def __init__(self):
        # vehicle_id -> driver_factor (1.0 = chuẩn, >1 = hao hơn, <1 = tiết kiệm)
        self.factors: Dict[str, float] = {}
        # vehicle_id -> số lượng dữ liệu đã học (để tính trung bình động)
        self.data_points: Dict[str, int] = {}
        
    def get_factor(self, vehicle_id: str) -> float:
        """Lấy hệ số của tài xế. Mặc định là 1.0"""
        return self.factors.get(vehicle_id, 1.0)
        
    def calibrate(self, vehicle_id: str, physics_energy_kwh: float, actual_energy_kwh: float):
        """
        Cập nhật hệ số tài xế sau mỗi chặng đường (hoặc qua telemetry).
        Sử dụng Exponential Moving Average (EMA) để hệ số học dần dần.
        """
        if physics_energy_kwh <= 0 or actual_energy_kwh <= 0:
            return
            
        current_factor = self.get_factor(vehicle_id)
        points = self.data_points.get(vehicle_id, 0)
        
        # Tỷ lệ tiêu hao thực tế so với lý thuyết
        observed_factor = actual_energy_kwh / physics_energy_kwh
        
        # Giới hạn outlier (chỉ chấp nhận hệ số từ 0.5 đến 2.0)
        observed_factor = max(0.5, min(2.0, observed_factor))
        
        alpha = 0.2 # Tốc độ học (20% từ dữ liệu mới, 80% giữ cũ)
        if points == 0:
            new_factor = observed_factor
        else:
            new_factor = (current_factor * (1 - alpha)) + (observed_factor * alpha)
            
        self.factors[vehicle_id] = new_factor
        self.data_points[vehicle_id] = points + 1
        
        print(f"[Calibration] Xe {vehicle_id}: Factor cập nhật thành {new_factor:.3f} (Dữ liệu thực tế: {actual_energy_kwh:.1f} kWh, Lý thuyết: {physics_energy_kwh:.1f} kWh)")
