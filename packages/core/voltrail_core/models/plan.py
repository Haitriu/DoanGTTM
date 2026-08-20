from dataclasses import dataclass
from enum import Enum
from typing import List, Optional
from .station import ChargingStation
from .route import RouteSegment
from .energy import EnergyEstimate

class RiskLevel(Enum):
    SAFE = "safe"
    AWARE = "aware"
    REST_RECOMMENDED = "rest_recommended"
    CHARGING_RECOMMENDED = "charging_recommended"
    CRITICAL = "critical"

@dataclass(frozen=True)
class SocEstimate:
    p10: float
    p50: float
    p90: float

@dataclass(frozen=True)
class StopReason:
    code: str
    text: str

@dataclass(frozen=True)
class Warning:
    code: str
    message: str

@dataclass(frozen=True)
class PlanStop:
    station: ChargingStation
    arrival_soc: SocEstimate
    departure_soc_frac: float
    charge_duration_s: int
    is_rest_stop: bool
    reason: StopReason

@dataclass(frozen=True)
class PlanLeg:
    segments: List[RouteSegment]
    energy: EnergyEstimate
    duration_s: int
    distance_m: float

@dataclass(frozen=True)
class TripPlan:
    legs: List[PlanLeg]
    stops: List[PlanStop]
    total_duration_s: int
    total_drive_s: int
    total_charge_s: int
    total_energy_kwh: float
    estimated_cost: Optional[float]  # Should ideally be a Money object
    risk: RiskLevel
    alternatives: List['TripPlan']
    warnings: List[Warning]
