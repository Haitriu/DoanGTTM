from typing import Protocol, Callable
from dataclasses import dataclass
from voltrail_core.models import Coordinate

@dataclass
class TelemetryMessage:
    vehicle_id: str
    location: Coordinate
    speed_mps: float
    soc_pct: float
    ambient_temp_c: float
    instant_power_kw: float
    timestamp: float

class TelemetrySubscriber(Protocol):
    def connect(self) -> None:
        ...
        
    def disconnect(self) -> None:
        ...
        
    def on_message(self, callback: Callable[[TelemetryMessage], None]) -> None:
        ...
