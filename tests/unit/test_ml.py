import pytest
from voltrail_core.ml import DriverCalibration, ResidualTrainer

def test_driver_calibration():
    calib = DriverCalibration()
    vid = "TEST_VF8"
    
    # Lúc đầu hệ số là 1.0
    assert calib.get_factor(vid) == 1.0
    
    # Tài xế chạy hao hơn (thực tế 20kWh, vật lý tính 15kWh) -> factor = 1.333
    calib.calibrate(vid, physics_energy_kwh=15.0, actual_energy_kwh=20.0)
    
    # Do alpha = 0.2 và điểm đầu tiên (points == 0) nên nhận luôn giá trị observed
    assert calib.get_factor(vid) == pytest.approx(1.333, 0.01)
    
    # Lần 2 tài xế chạy tiết kiệm hơn (thực tế 15, vật lý 15) -> factor = 1.0
    # EMA: current * 0.8 + observed * 0.2
    calib.calibrate(vid, physics_energy_kwh=15.0, actual_energy_kwh=15.0)
    expected = 1.333 * 0.8 + 1.0 * 0.2
    assert calib.get_factor(vid) == pytest.approx(expected, 0.01)

def test_residual_trainer():
    trainer = ResidualTrainer()
    
    # Giả lập dữ liệu: Nếu chạy nhanh (speed_mps > 25) và gió ngược (headwind > 5), xe luôn tốn thêm 2kWh.
    # Ngược lại, tốn thêm 0.5kWh
    for _ in range(20):
        # Mẫu tốn thêm 2kWh
        trainer.add_training_data(temp_c=30, speed_mps=30, headwind_mps=10, physics_kwh=15, actual_kwh=17)
        # Mẫu tốn thêm 0.5kWh
        trainer.add_training_data(temp_c=30, speed_mps=15, headwind_mps=2, physics_kwh=10, actual_kwh=10.5)
        
    trainer.train()
    assert trainer.is_trained
    
    # Dự đoán
    err_high = trainer.predict_residual(temp_c=30, speed_mps=30, headwind_mps=10)
    assert err_high == pytest.approx(2.0, 0.1)
    
    err_low = trainer.predict_residual(temp_c=30, speed_mps=15, headwind_mps=2)
    assert err_low == pytest.approx(0.5, 0.1)
