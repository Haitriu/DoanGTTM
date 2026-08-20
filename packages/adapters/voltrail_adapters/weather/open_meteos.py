import httpx
from typing import List
from datetime import datetime
from voltrail_core.models import Coordinate
from voltrail_core.weather.protocols import WeatherProvider, WeatherConditions

class OpenMeteoProvider(WeatherProvider):
    def __init__(self, base_url: str = "https://api.open-meteo.com/v1/forecast"):
        self.base_url = base_url
        
    def get_forecast(self, location: Coordinate, time: datetime) -> WeatherConditions:
        # Simplistic implementation for Phase 2
        # In a real app, we query the forecast hourly data and interpolate
        params = {
            "latitude": location.lat,
            "longitude": location.lon,
            "current": "temperature_2m,wind_speed_10m",
            "wind_speed_unit": "ms"
        }
        
        try:
            response = httpx.get(self.base_url, params=params, timeout=5.0)
            response.raise_for_status()
            data = response.json()
            
            current = data.get("current", {})
            temp = current.get("temperature_2m", 25.0)
            wind = current.get("wind_speed_10m", 0.0)
            
            return WeatherConditions(temperature_c=temp, wind_speed_mps=wind, headwind_mps=0.0)
        except Exception as e:
            print(f"Open-Meteo failed: {e}. Fallback to 25C, 0m/s")
            return WeatherConditions(temperature_c=25.0, wind_speed_mps=0.0, headwind_mps=0.0)
            
    def get_route_forecast(self, coordinates: List[Coordinate], start_time: datetime) -> List[WeatherConditions]:
        # For simplicity in Phase 2, we just return the same conditions for all points 
        # based on the first point's current weather. 
        if not coordinates:
            return []
        
        base_condition = self.get_forecast(coordinates[0], start_time)
        return [base_condition for _ in coordinates]
