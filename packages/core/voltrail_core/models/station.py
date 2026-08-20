from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, List, Optional
from datetime import datetime
from .coordinate import Coordinate

class Confidence(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class Amenity(Enum):
    RESTROOM = "restroom"
    FOOD = "food"
    SHELTER = "shelter"
    WIFI = "wifi"

@dataclass(frozen=True)
class Connector:
    connector_type: str
    max_power_kw: float
    count: int

@dataclass(frozen=True)
class ChargingStation:
    id: str
    location: Coordinate
    connectors: List[Connector]
    operator: Optional[str]
    amenities: FrozenSet[Amenity]
    data_confidence: Confidence
    last_verified_at: Optional[datetime]
