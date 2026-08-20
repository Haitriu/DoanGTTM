from dataclasses import dataclass

@dataclass(frozen=True)
class EnergyEstimate:
    total_kwh: float
    rolling_kwh: float
    aero_kwh: float
    grade_kwh: float
    auxiliary_kwh: float
    regen_kwh: float  # Giá trị âm khi thu hồi năng lượng
    p10_kwh: float
    p90_kwh: float
