import httpx
from typing import List
from datetime import datetime, UTC
from voltrail_core.models import Coordinate, ChargingStation, Connector, Confidence
from voltrail_core.stations.protocols import StationProvider


class OpenChargeMapProvider(StationProvider):
    def __init__(self, api_key: str, base_url: str = "https://api.openchargemap.io/v3/poi"):
        self.api_key = api_key
        self.base_url = base_url

    def _parse_station(self, item: dict) -> ChargingStation | None:
        addr = item.get("AddressInfo", {})
        lat = addr.get("Latitude")
        lon = addr.get("Longitude")
        if not lat or not lon:
            return None

        connectors = []
        for conn in item.get("Connections", []):
            type_title = conn.get("ConnectionType", {}).get("Title", "Unknown")
            power = conn.get("PowerKW")
            if not power:
                continue
            qty = conn.get("Quantity", 1) or 1
            connectors.append(Connector(
                connector_type=str(type_title).lower(),
                max_power_kw=float(power),
                count=int(qty),
            ))

        operator = item.get("OperatorInfo", {}).get("Title") if item.get("OperatorInfo") else None

        return ChargingStation(
            id=f"OCM-{item['ID']}",
            location=Coordinate(float(lat), float(lon)),
            connectors=connectors,
            operator=operator,
            amenities=frozenset(),
            data_confidence=Confidence.MEDIUM,
            last_verified_at=datetime.now(UTC),
        )

    def get_stations_in_radius(
        self,
        center: Coordinate,
        radius_km: float = 50.0,
        min_power_kw: float = 22.0,
    ) -> List[ChargingStation]:
        params = {
            "key": self.api_key,
            "latitude": center.lat,
            "longitude": center.lon,
            "distance": radius_km,
            "distanceunit": "KM",
            "minpowerkw": min_power_kw,
            "maxresults": 100,
            "compact": "true",
            "verbose": "false",
            "countrycode": "VN",   # Giới hạn Việt Nam để tăng tốc
        }
        try:
            response = httpx.get(self.base_url, params=params, timeout=15.0)
            response.raise_for_status()
            stations = []
            for item in response.json():
                try:
                    station = self._parse_station(item)
                    if station and station.connectors:
                        stations.append(station)
                except Exception as e:
                    print(f"[OCM] Bỏ qua trạm do lỗi parse: {e}")
            return stations
        except Exception as e:
            print(f"[OCM] API Error tại ({center.lat:.2f},{center.lon:.2f}): {e}")
            return []

    def get_stations_along_corridor(
        self,
        waypoints: List[Coordinate],
        radius_km: float = 30.0,
        min_power_kw: float = 22.0,
    ) -> List[ChargingStation]:
        """
        Lấy tất cả trạm sạc dọc hành lang tuyến đường bằng cách query OCM
        tại từng waypoint trung gian. Loại bỏ trùng lặp theo ID.
        """
        seen_ids: set[str] = set()
        all_stations: List[ChargingStation] = []

        # Chỉ query tại các waypoints trung gian (không phải đầu/cuối)
        # để không bị trùng lặp quá nhiều
        sample_wps = waypoints[::2] if len(waypoints) > 4 else waypoints

        for wp in sample_wps:
            for station in self.get_stations_in_radius(wp, radius_km, min_power_kw):
                if station.id not in seen_ids:
                    seen_ids.add(station.id)
                    all_stations.append(station)

        print(f"[OCM] Tìm thấy {len(all_stations)} trạm sạc thực tế dọc hành lang.")
        return all_stations

    # Backward compatibility alias
    def get_stations_along_route(
        self,
        route_polyline: str,
        max_distance_km: float = 5.0,
        min_power_kw: float = 50.0,
    ) -> List[ChargingStation]:
        return []
