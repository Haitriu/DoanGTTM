from dataclasses import dataclass
from typing import List, Tuple

@dataclass(frozen=True)
class BatterySpec:
    nominal_capacity_kwh: float
    usable_capacity_kwh: float
    reserve_soc_frac: float

@dataclass(frozen=True)
class PhysicsSpec:
    curb_mass_kg: float
    drag_coefficient: float
    frontal_area_m2: float
    rolling_resistance_coeff: float
    drivetrain_efficiency: float
    regen_efficiency: float

@dataclass(frozen=True)
class AuxiliarySpec:
    base_power_kw: float
    hvac_max_power_kw: float

@dataclass(frozen=True)
class ChargingCurve:
    points: List[Tuple[float, float]]  # List of (soc_frac, max_power_kw)

    def at(self, soc_frac: float) -> float:
        """Linear interpolation of max power for a given SOC fraction."""
        if not self.points:
            return 0.0
        
        # Sort points by SOC fraction just in case
        sorted_points = sorted(self.points, key=lambda p: p[0])
        
        if soc_frac <= sorted_points[0][0]:
            return sorted_points[0][1]
        if soc_frac >= sorted_points[-1][0]:
            return sorted_points[-1][1]
            
        for i in range(len(sorted_points) - 1):
            x0, y0 = sorted_points[i]
            x1, y1 = sorted_points[i + 1]
            if x0 <= soc_frac <= x1:
                if x1 == x0:
                    return y0
                return y0 + (y1 - y0) * (soc_frac - x0) / (x1 - x0)
                
        return 0.0

@dataclass(frozen=True)
class ChargingSpec:
    max_dc_power_kw: float
    max_ac_power_kw: float
    connectors: List[str]
    curve: ChargingCurve

@dataclass(frozen=True)
class Vehicle:
    id: str
    name: str
    battery: BatterySpec
    physics: PhysicsSpec
    auxiliary: AuxiliarySpec
    charging: ChargingSpec
