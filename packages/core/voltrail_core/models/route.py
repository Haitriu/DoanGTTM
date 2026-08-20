from dataclasses import dataclass
from enum import Enum
from .coordinate import Coordinate

class RoadClass(Enum):
    HIGHWAY = "highway"
    RURAL = "rural"
    URBAN = "urban"
    UNKNOWN = "unknown"

@dataclass(frozen=True)
class RouteSegment:
    """Một đoạn ~100-500m của tuyến, đơn vị nguyên tử để tính năng lượng."""
    distance_m: float
    start: Coordinate
    end: Coordinate
    elevation_gain_m: float
    grade: float
    speed_limit_mps: float
    expected_speed_mps: float
    road_class: RoadClass
