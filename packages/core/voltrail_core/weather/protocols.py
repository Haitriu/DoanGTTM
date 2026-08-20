from typing import Protocol, List
from datetime import datetime
from voltrail_core.models import Coordinate

class WeatherConditions:
    def __init__(self, temperature_c: float, wind_speed_mps: float, headwind_mps: float = 0.0):
        self.temperature_c = temperature_c
        self.wind_speed_mps = wind_speed_mps
        self.headwind_mps = headwind_mps

class WeatherProvider(Protocol):
    def get_forecast(self, location: Coordinate, time: datetime) -> WeatherConditions:
        """
        Lấy dự báo thời tiết cho một địa điểm và thời điểm cụ thể.
        """
        ...
    
    def get_route_forecast(self, coordinates: List[Coordinate], start_time: datetime) -> List[WeatherConditions]:
        """
        Lấy chuỗi dự báo thời tiết dọc theo một tuyến đường dựa trên thời gian bắt đầu dự kiến.
        """
        ...
