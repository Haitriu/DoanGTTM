from typing import Protocol, List, Optional
from voltrail_core.models import Coordinate, ChargingStation

class StationProvider(Protocol):
    def get_stations_along_route(
        self, 
        route_polyline: str, 
        max_distance_km: float = 5.0, 
        min_power_kw: float = 50.0
    ) -> List[ChargingStation]:
        """
        Lấy danh sách các trạm sạc nằm gần tuyến đường (dựa trên bounding box hoặc đường bao polyline).
        """
        ...
        
    def get_stations_in_radius(
        self, 
        center: Coordinate, 
        radius_km: float = 50.0, 
        min_power_kw: float = 50.0
    ) -> List[ChargingStation]:
        """
        Lấy danh sách các trạm sạc trong bán kính cho trước.
        """
        ...
