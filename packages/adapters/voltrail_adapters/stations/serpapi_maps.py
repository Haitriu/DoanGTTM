from datetime import UTC, datetime
from typing import List

import httpx
from voltrail_core.models import ChargingStation, Confidence, Coordinate
from voltrail_core.stations.protocols import StationProvider


class SerpApiPlacesProvider(StationProvider):
    """
    Tìm điểm sạc xe điện qua SerpApi Google Maps engine
    (https://serpapi.com/google-maps-api, type=search).

    LƯU Ý QUAN TRỌNG: Google Maps local results KHÔNG cung cấp công suất sạc
    (kW) của trụ — đây là dữ liệu chỉ Open Charge Map / OCPI mới có. Vì vậy
    các ChargingStation trả về từ provider này luôn có connectors=[] và
    data_confidence=LOW: chúng chỉ dùng để hiển thị gợi ý vị trí trên bản đồ
    (điểm quan tâm), KHÔNG được dùng làm input cho graph lập kế hoạch sạc —
    bộ lọc `if station.connectors` ở tầng gọi sẽ tự loại các trạm này khỏi
    graph, tránh vi phạm bất biến "không bịa số liệu vật lý".
    """

    def __init__(self, api_key: str, base_url: str = "https://serpapi.com/search.json"):
        self.api_key = api_key
        self.base_url = base_url

    def _search(self, ll: str, query: str) -> List[dict]:
        params = {
            "engine": "google_maps",
            "type": "search",
            "q": query,
            "ll": ll,
            "api_key": self.api_key,
        }
        try:
            response = httpx.get(self.base_url, params=params, timeout=10.0)
            response.raise_for_status()
            return response.json().get("local_results", [])
        except Exception as e:
            print(f"[SerpApi] Lỗi tìm trạm sạc tại {ll}: {e}")
            return []

    def _parse_place(self, item: dict) -> ChargingStation | None:
        gps = item.get("gps_coordinates")
        place_id = item.get("place_id")
        if not gps or not place_id:
            return None
        return ChargingStation(
            id=f"SERPAPI-{place_id}",
            location=Coordinate(gps["latitude"], gps["longitude"]),
            connectors=[],
            operator=item.get("title"),
            amenities=frozenset(),
            data_confidence=Confidence.LOW,
            last_verified_at=datetime.now(UTC),
        )

    def get_stations_in_radius(
        self,
        center: Coordinate,
        radius_km: float = 50.0,
        min_power_kw: float = 22.0,
    ) -> List[ChargingStation]:
        # zoom xấp xỉ theo bán kính tìm kiếm — càng rộng thì zoom càng nhỏ
        zoom = 14 if radius_km <= 10 else 11 if radius_km <= 30 else 9
        ll = f"@{center.lat},{center.lon},{zoom}z"

        stations = []
        seen_ids: set[str] = set()
        for item in self._search(ll, "trạm sạc xe điện"):
            station = self._parse_place(item)
            if station and station.id not in seen_ids:
                seen_ids.add(station.id)
                stations.append(station)
        return stations

    def get_stations_along_corridor(
        self,
        waypoints: List[Coordinate],
        radius_km: float = 30.0,
        min_power_kw: float = 22.0,
    ) -> List[ChargingStation]:
        seen_ids: set[str] = set()
        all_stations: List[ChargingStation] = []
        sample_wps = waypoints[::2] if len(waypoints) > 4 else waypoints

        for wp in sample_wps:
            for station in self.get_stations_in_radius(wp, radius_km, min_power_kw):
                if station.id not in seen_ids:
                    seen_ids.add(station.id)
                    all_stations.append(station)
        return all_stations

    def get_stations_along_route(
        self,
        route_polyline: str,
        max_distance_km: float = 5.0,
        min_power_kw: float = 50.0,
    ) -> List[ChargingStation]:
        return []
