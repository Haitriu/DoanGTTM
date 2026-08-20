import httpx
from typing import List
from voltrail_core.models import Coordinate
from voltrail_core.routing.protocols import ElevationProvider

class OpenElevationProvider(ElevationProvider):
    def __init__(self, base_url: str = "https://api.open-elevation.com/api/v1/lookup"):
        self.base_url = base_url
        
    def get_elevation(self, coordinates: List[Coordinate]) -> List[float]:
        """
        Fetches elevation data for a list of coordinates from Open-Elevation API.
        Open-Elevation expects a JSON POST with:
        {"locations": [{"latitude": ..., "longitude": ...}]}
        """
        if not coordinates:
            return []
            
        locations = [{"latitude": c.lat, "longitude": c.lon} for c in coordinates]
        
        try:
            # Simple HTTP request
            response = httpx.post(self.base_url, json={"locations": locations}, timeout=15.0)
            response.raise_for_status()
            data = response.json()
            
            results = data.get("results", [])
            elevations = [float(res["elevation"]) for res in results]
            
            # Ensure we return exactly the same number of elevations as requested coordinates
            if len(elevations) != len(coordinates):
                raise ValueError("Mismatch between requested coordinates and returned elevations")
                
            return elevations
        except Exception as e:
            # Fallback to 0.0 if elevation API fails in Phase 1
            # In a robust implementation, we might retry or circuit-break
            print(f"Warning: Open-Elevation failed ({e}). Returning 0.0 for elevations.")
            return [0.0] * len(coordinates)
