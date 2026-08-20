import httpx
import polyline
from typing import List
from voltrail_core.models import Coordinate, RouteSegment, RoadClass
from voltrail_core.routing.protocols import RoutingProvider

class OSRMRoutingProvider(RoutingProvider):
    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url.rstrip("/")
        
    def get_route(self, origin: Coordinate, destination: Coordinate) -> List[RouteSegment]:
        url = f"{self.base_url}/route/v1/driving/{origin.lon},{origin.lat};{destination.lon},{destination.lat}"
        
        params = {
            "overview": "full",
            "geometries": "polyline",
            "annotations": "distance,duration,speed", # Note: standard OSRM might not have speed, we might have to derive it
            "steps": "true"
        }
        
        # Simple HTTP request
        response = httpx.get(url, params=params, timeout=10.0)
        response.raise_for_status()
        data = response.json()
        
        if data.get("code") != "Ok":
            raise ValueError(f"OSRM Error: {data.get('message')}")
            
        route = data["routes"][0]
        geom = route["geometry"]
        coords = polyline.decode(geom) # list of (lat, lon)
        
        segments = []
        # Fallback simplistic segment generation if annotations are missing
        # In a real app, we parse steps and annotations to get precise data
        total_dist = route["distance"]
        total_dur = route["duration"]
        avg_speed = total_dist / total_dur if total_dur > 0 else 25.0
        
        # OSRM annotations might give us distance per segment, but polyline decoding gives us nodes.
        # Let's create simplistic segments between polyline nodes
        from math import radians, cos, sin, asin, sqrt
        
        def haversine(lon1, lat1, lon2, lat2):
            lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
            dlon = lon2 - lon1 
            dlat = lat2 - lat1 
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * asin(sqrt(a)) 
            r = 6371000 
            return c * r
            
        for i in range(len(coords) - 1):
            lat1, lon1 = coords[i]
            lat2, lon2 = coords[i+1]
            dist = haversine(lon1, lat1, lon2, lat2)
            
            seg = RouteSegment(
                distance_m=dist,
                start=Coordinate(lat1, lon1),
                end=Coordinate(lat2, lon2),
                elevation_gain_m=0.0, # Handled separately by ElevationProvider usually
                grade=0.0,
                speed_limit_mps=avg_speed, # Simplified
                expected_speed_mps=avg_speed,
                road_class=RoadClass.UNKNOWN
            )
            segments.append(seg)
            
        return segments
