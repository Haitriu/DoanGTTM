import random
from dataclasses import dataclass

from voltrail_core.energy import compute_segment_energy
from voltrail_core.models import Coordinate, RoadClass, RouteSegment, Vehicle

# Giả định tốc độ trung bình cao tốc/quốc lộ — khớp với giả định phẳng trong
# ChargingGraph.build_from_stations (Phase 2 rút gọn, xem packages/core/.../graph.py).
ASSUMED_CRUISE_SPEED_KMH = 80.0

# Điều kiện "kế hoạch giả định" khi lập plan ban đầu (không tải phụ, không gió,
# nhiệt độ tiêu chuẩn) — dùng làm mốc so sánh với điều kiện "thực tế" khi mô phỏng.
PLANNED_TEMPERATURE_C = 25.0
PLANNED_WIND_MPS = 0.0
PLANNED_EXTRA_LOAD_KG = 0.0


@dataclass(frozen=True)
class TripConditions:
    """Điều kiện thực tế của một chuyến đi cụ thể — sinh ngẫu nhiên một lần khi
    bắt đầu mô phỏng, giữ cố định suốt chuyến (giống việc chất thêm hành lý/người
    ngồi hoặc gặp một kiểu thời tiết nhất định trong ngày hôm đó)."""
    extra_load_kg: float
    temperature_c: float
    wind_mps: float  # dương = ngược gió (cản), âm = xuôi gió


def generate_real_world_conditions(rng: random.Random) -> TripConditions:
    """
    Sinh điều kiện thực tế ngẫu nhiên nhưng trong khoảng vật lý hợp lý:
    - Trọng tải phụ: 0–320kg (2-4 người + hành lý, ước lượng thô).
    - Nhiệt độ: lệch dự báo ±8°C.
    - Gió: -4..+6 m/s dọc hướng đi (ước lượng thô, không mô hình hướng gió thật).
    """
    return TripConditions(
        extra_load_kg=rng.uniform(0.0, 320.0),
        temperature_c=PLANNED_TEMPERATURE_C + rng.uniform(-8.0, 8.0),
        wind_mps=rng.uniform(-4.0, 6.0),
    )


def _make_leg_segment(distance_m: float) -> RouteSegment:
    speed_mps = ASSUMED_CRUISE_SPEED_KMH * 1000 / 3600
    dummy = Coordinate(0.0, 0.0)
    return RouteSegment(
        distance_m=distance_m,
        start=dummy,
        end=dummy,
        elevation_gain_m=0.0,
        grade=0.0,
        speed_limit_mps=speed_mps,
        expected_speed_mps=speed_mps,
        road_class=RoadClass.HIGHWAY,
    )


def compute_leg_energy_kwh(
    vehicle: Vehicle,
    distance_m: float,
    temperature_c: float = PLANNED_TEMPERATURE_C,
    wind_mps: float = PLANNED_WIND_MPS,
    extra_load_kg: float = PLANNED_EXTRA_LOAD_KG,
) -> float:
    """
    Năng lượng thật (kWh) cho một chặng đường, tính qua compute_segment_energy
    của core (không bịa số) — coi chặng như một RouteSegment phẳng, tốc độ
    trung bình ASSUMED_CRUISE_SPEED_KMH, khớp giả định của ChargingGraph.
    """
    segment = _make_leg_segment(distance_m)
    estimate = compute_segment_energy(
        segment, vehicle,
        temperature_c=temperature_c,
        wind_mps=wind_mps,
        extra_load_kg=extra_load_kg,
    )
    return estimate.total_kwh


def leg_duration_s(distance_m: float) -> float:
    speed_mps = ASSUMED_CRUISE_SPEED_KMH * 1000 / 3600
    return distance_m / speed_mps
