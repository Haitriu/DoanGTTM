from math import asin, cos, radians, sin, sqrt
from typing import List

import httpx
from voltrail_core.models import Coordinate, RoadClass, RouteSegment
from voltrail_core.routing.protocols import RoutingProvider


def _haversine_m(a: Coordinate, b: Coordinate) -> float:
    lon1, lat1, lon2, lat2 = map(radians, [a.lon, a.lat, b.lon, b.lat])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * asin(sqrt(h)) * 6371000


class SerpApiDirectionsProvider(RoutingProvider):
    """
    Lấy tuyến đường lái xe thật qua SerpApi Google Maps Directions engine
    (https://serpapi.com/google-maps-directions-api).

    LƯU Ý: response của engine này không có polyline/geometry tổng, chỉ có
    toạ độ GPS rời rạc cho từng bước chỉ đường (details[].gps_coordinates).
    Ta nối các điểm đó thành các RouteSegment, tương tự cách OSRMRoutingProvider
    nối các điểm polyline. Nếu SerpApi trả về thiếu dữ liệu cần thiết, provider
    raise ValueError để tầng gọi (apps/api) fallback sang nguồn khác — không
    bao giờ tự chế toạ độ.
    """

    def __init__(self, api_key: str, base_url: str = "https://serpapi.com/search.json"):
        self.api_key = api_key
        self.base_url = base_url

    def get_route(self, origin: Coordinate, destination: Coordinate) -> List[RouteSegment]:
        params = {
            "engine": "google_maps_directions",
            "start_coords": f"{origin.lat},{origin.lon}",
            "end_coords": f"{destination.lat},{destination.lon}",
            "travel_mode": 0,  # driving
            "api_key": self.api_key,
        }
        response = httpx.get(self.base_url, params=params, timeout=15.0)
        response.raise_for_status()
        data = response.json()

        directions = data.get("directions")
        if not directions:
            raise ValueError(f"SerpApi Directions: không có tuyến đường ({data.get('error')})")

        route = directions[0]
        points: List[Coordinate] = [origin]
        step_distances_m: List[float] = []

        for trip in route.get("trips", []):
            for step in trip.get("details", []):
                gps = step.get("gps_coordinates")
                if not gps:
                    continue
                points.append(Coordinate(gps["latitude"], gps["longitude"]))
                step_distances_m.append(float(step.get("distance", 0.0)))

        if len(points) < 2:
            raise ValueError("SerpApi Directions: không đủ toạ độ để dựng tuyến đường")

        if points[-1] != destination:
            points.append(destination)

        total_duration_s = float(route.get("duration", 0.0))
        total_distance_m = float(route.get("distance", 0.0))
        avg_speed_mps = total_distance_m / total_duration_s if total_duration_s > 0 else 20.0

        segments: List[RouteSegment] = []
        for i in range(len(points) - 1):
            seg_distance_m = _haversine_m(points[i], points[i + 1])
            segments.append(RouteSegment(
                distance_m=seg_distance_m,
                start=points[i],
                end=points[i + 1],
                elevation_gain_m=0.0,  # Elevation lấy riêng qua ElevationProvider
                grade=0.0,
                speed_limit_mps=avg_speed_mps,
                expected_speed_mps=avg_speed_mps,
                road_class=RoadClass.UNKNOWN,
            ))

        return segments
