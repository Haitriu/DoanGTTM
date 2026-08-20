from voltrail_core.models import RouteSegment, Vehicle, EnergyEstimate
from voltrail_core.constants import AIR_DENSITY_KG_PER_M3, GRAVITY_M_PER_S2, JOULES_PER_KWH
from .temperature import get_capacity_derate, get_efficiency_derate, get_hvac_power_kw
from .confidence import apply_uncertainty

def compute_segment_energy(
    segment: RouteSegment,
    vehicle: Vehicle,
    temperature_c: float,
    wind_mps: float = 0.0,
    extra_load_kg: float = 0.0,
    confidence_level: str = "medium",
) -> EnergyEstimate:
    """
    Computes energy consumption for a single route segment based on physical forces.
    """
    # 1. Khối lượng
    m = vehicle.physics.curb_mass_kg + extra_load_kg
    g = GRAVITY_M_PER_S2
    
    # 2. Lượng giác cho độ dốc
    grade = segment.grade
    sin_theta = grade / (1 + grade**2)**0.5
    cos_theta = 1 / (1 + grade**2)**0.5
    
    # 3. Tính lực
    f_rolling = vehicle.physics.rolling_resistance_coeff * m * g * cos_theta
    
    v = segment.expected_speed_mps
    v_eff = max(0.0, v + wind_mps)
    rho = AIR_DENSITY_KG_PER_M3
    f_aero = 0.5 * rho * vehicle.physics.drag_coefficient * vehicle.physics.frontal_area_m2 * (v_eff ** 2)
    
    f_grade = m * g * sin_theta
    f_total = f_rolling + f_aero + f_grade
    
    # 4. Năng lượng tại bánh xe (Joule)
    e_wheels_j = f_total * segment.distance_m
    
    # 5. Suy hao do nhiệt độ và hiệu suất
    eff_derate = get_efficiency_derate(temperature_c)
    drivetrain_eff = vehicle.physics.drivetrain_efficiency * eff_derate
    regen_eff = vehicle.physics.regen_efficiency * eff_derate
    
    regen_kwh = 0.0
    if e_wheels_j > 0:
        e_battery_j = e_wheels_j / drivetrain_eff
    else:
        e_battery_j = e_wheels_j * regen_eff
        regen_kwh = e_battery_j / JOULES_PER_KWH
    
    propulsion_kwh = e_battery_j / JOULES_PER_KWH
    
    # 6. Tiêu hao phụ tải (Auxiliary / HVAC)
    p_aux_kw = vehicle.auxiliary.base_power_kw + get_hvac_power_kw(temperature_c)
    duration_s = segment.distance_m / v if v > 0 else 0
    aux_kwh = p_aux_kw * (duration_s / 3600.0)
    
    # 7. Phân rã (thể hiện tương đối khi hiển thị)
    rolling_kwh = (f_rolling * segment.distance_m / drivetrain_eff) / JOULES_PER_KWH if f_total > 0 else 0
    aero_kwh = (f_aero * segment.distance_m / drivetrain_eff) / JOULES_PER_KWH if f_total > 0 else 0
    grade_kwh_val = (f_grade * segment.distance_m / drivetrain_eff) / JOULES_PER_KWH if f_total > 0 else 0
    
    # Nếu regen, gán các lực kia = 0 để tổng phân rã = propulsion (âm) + aux
    if e_wheels_j <= 0:
        rolling_kwh = aero_kwh = grade_kwh_val = 0.0
    
    # Đảm bảo bất biến: propulsion_kwh = rolling_kwh + aero_kwh + grade_kwh_val + regen_kwh
    
    # 8. Tổng năng lượng
    total_kwh = propulsion_kwh + aux_kwh
    
    p10, p90 = apply_uncertainty(total_kwh, confidence_level)
    
    return EnergyEstimate(
        total_kwh=total_kwh,
        rolling_kwh=rolling_kwh,
        aero_kwh=aero_kwh,
        grade_kwh=grade_kwh_val,
        auxiliary_kwh=aux_kwh,
        regen_kwh=regen_kwh,
        p10_kwh=p10,
        p90_kwh=p90,
    )
