import dataclasses
import os
import random
from datetime import datetime, UTC
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from pathlib import Path

from voltrail_core.models import (
    Coordinate, ChargingStation, Connector, Confidence,
)
from voltrail_core.models.vehicle_loader import load_vehicle_from_yaml
from voltrail_core.planner import ChargingGraph, find_optimal_plan, RestRules, RiskEngine

# Đọc API keys từ biến môi trường (tải từ file .env nếu có)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

OCM_KEY = os.environ.get("OPEN_CHARGE_MAP_KEY", "")
MAPBOX_TOKEN = os.environ.get("MAPBOX_ACCESS_TOKEN", "")

# Khởi tạo OCM provider nếu có key
_ocm_provider = None
if OCM_KEY and not OCM_KEY.startswith("your_"):
    try:
        from voltrail_adapters.stations.open_charge_map import OpenChargeMapProvider
        _ocm_provider = OpenChargeMapProvider(api_key=OCM_KEY)
        print(f"[API] ✅ Open Charge Map đã được kết nối (sử dụng trạm sạc thực tế).")
    except Exception as e:
        print(f"[API] ⚠️ Không thể khởi tạo OCM: {e}")
else:
    print("[API] ℹ️ Chế độ Demo: Dùng trạm sạc giả lập (chưa có OCM key).")

app = FastAPI(title="Voltrail API", version="0.2.0")

# Serve the static web assets
web_dir = Path("apps/web")
if web_dir.exists():
    app.mount("/static", StaticFiles(directory=web_dir / "static"), name="static")

    @app.get("/")
    async def index():
        return FileResponse(web_dir / "index.html")


@app.get("/config")
async def get_config():
    """Trả về config công khai cho frontend (token map)."""
    return {
        "mapbox_token": MAPBOX_TOKEN if MAPBOX_TOKEN and not MAPBOX_TOKEN.startswith("pk.your_") else "",
        "has_real_stations": _ocm_provider is not None,
    }
class PlanRequest(BaseModel):
    origin: Coordinate
    destination: Coordinate
    vehicle_id: str
    start_soc_pct: float = 100.0


class StopInfo(BaseModel):
    lat: float
    lon: float
    operator: Optional[str]
    charge_minutes: float
    departure_soc_pct: float


class PlanResponse(BaseModel):
    total_duration_minutes: float
    total_drive_minutes: float
    total_charge_minutes: float
    total_energy_kwh: float
    risk_level: str
    warnings: List[str]
    stops: List[StopInfo]
    route_waypoints: List[List[float]]  # [[lon, lat], ...] để vẽ đường trên bản đồ


# Bảng hành lang đường bộ thực tế (QL1A) cho các cung đường phổ biến
# Nguồn: Tọa độ xấp xỉ các thành phố dọc QL1A Việt Nam
_QL1A_WAYPOINTS = [
    (21.0285, 105.8542),  # Hà Nội
    (20.5388, 105.9647),  # Phủ Lý (Hà Nam)
    (20.2522, 105.9745),  # Ninh Bình
    (19.8074, 105.7770),  # Thanh Hoá
    (19.3365, 105.5836),  # Tĩnh Gia
    (18.6796, 105.6814),  # Vinh (Nghệ An)
    (18.3376, 105.8904),  # Nghi Xuân
    (17.9700, 106.1100),  # Hà Tĩnh
    (17.4667, 106.6000),  # Đồng Hới (Quảng Bình)
    (16.9745, 107.0234),  # Đông Hà (Quảng Trị)
    (16.4637, 107.5909),  # Huế (Thừa Thiên Huế)
    (16.0471, 108.2062),  # Đà Nẵng
    (15.8800, 108.3387),  # Hội An
    (15.5736, 108.4736),  # Tam Kỳ
    (15.1195, 108.8048),  # Quảng Ngãi
    (14.1666, 108.8685),  # Quy Nhơn (Bình Định)
    (13.0827, 109.0968),  # Tuy Hoà (Phú Yên)
    (12.2388, 109.1968),  # Nha Trang (Khánh Hoà)
    (11.5640, 108.9881),  # Phan Rang
    (11.0033, 108.2622),  # Phan Thiết
    (10.8231, 106.6297),  # TP.HCM
]


def _find_corridor_waypoints(origin: Coordinate, dest: Coordinate) -> List[tuple]:
    """
    Trả về danh sách waypoints theo QL1A nằm giữa origin và dest.
    Tính bằng cách tìm điểm bắt đầu/kết thúc gần nhất trong bảng QL1A.
    """
    def dist_sq(lat1, lon1, lat2, lon2):
        return (lat1 - lat2) ** 2 + (lon1 - lon2) ** 2

    # Tìm điểm QL1A gần origin và dest nhất
    idx_origin = min(range(len(_QL1A_WAYPOINTS)),
                     key=lambda i: dist_sq(origin.lat, origin.lon, *_QL1A_WAYPOINTS[i]))
    idx_dest = min(range(len(_QL1A_WAYPOINTS)),
                   key=lambda i: dist_sq(dest.lat, dest.lon, *_QL1A_WAYPOINTS[i]))

    if idx_origin > idx_dest:
        idx_origin, idx_dest = idx_dest, idx_origin

    # Trả về đoạn QL1A nằm giữa 2 điểm (kèm điểm đầu/cuối thực tế)
    segment = [(origin.lat, origin.lon)]
    segment += _QL1A_WAYPOINTS[idx_origin: idx_dest + 1]
    segment.append((dest.lat, dest.lon))
    return segment


def _make_mock_station(sid: str, lat: float, lon: float, power_kw: float) -> ChargingStation:
    """Tạo trạm sạc giả lập dọc theo tuyến đường."""
    return ChargingStation(
        id=sid,
        location=Coordinate(lat, lon),
        connectors=[Connector("ccs2", power_kw, 2)],
        operator=random.choice(["Charge+ VN", "E-Boost", "VinFast"]),
        amenities=frozenset(),
        data_confidence=Confidence.MEDIUM,
        last_verified_at=datetime.now(UTC),
    )


def _build_corridor_graph(
    origin: Coordinate,
    dest: Coordinate,
    vehicle,
    waypoints: List[tuple],
    real_stations: Optional[List[ChargingStation]] = None,
) -> ChargingGraph:
    """
    Xây dựng đồ thị với Origin, Destination và các trạm sạc.
    - Ưu tiên dùng real_stations (từ OCM) nếu có đủ.
    - Fallback sang mock stations trên corridor QL1A nếu không có key.
    """
    origin_station = ChargingStation(
        id="O", location=origin, connectors=[],
        operator=None, amenities=frozenset(),
        data_confidence=Confidence.HIGH, last_verified_at=datetime.now(UTC),
    )
    dest_station = ChargingStation(
        id="D", location=dest, connectors=[],
        operator=None, amenities=frozenset(),
        data_confidence=Confidence.HIGH, last_verified_at=datetime.now(UTC),
    )

    if real_stations and len(real_stations) >= 3:
        # Dùng trạm thật từ OCM — đặt ID tránh trùng "O"/"D"
        intermediate = [s for s in real_stations if s.id not in {"O", "D"}]
        print(f"[Graph] Dùng {len(intermediate)} trạm sạc thực tế.")
    else:
        # Fallback: sinh mock stations trên corridor waypoints (jitter ±0.03° ≈ 3km)
        intermediate = []
        mid_wps = waypoints[1:-1]
        for i, (lat, lon) in enumerate(mid_wps):
            jitter = random.uniform(-0.03, 0.03)
            power = random.choice([50.0, 150.0, 250.0])
            intermediate.append(_make_mock_station(f"MOCK-{i}", lat + jitter, lon + jitter, power))
        print(f"[Graph] Dùng {len(intermediate)} trạm sạc giả lập (không có OCM key).")

    all_stations = [origin_station, dest_station] + intermediate
    graph = ChargingGraph()
    graph.build_from_stations("O", "D", all_stations, vehicle)
    return graph



@app.post("/api/plan", response_model=PlanResponse)
async def create_plan(req: PlanRequest):
    vehicle_path = Path(f"data/vehicles/{req.vehicle_id}.yaml")
    if not vehicle_path.exists():
        raise HTTPException(status_code=404, detail=f"Xe '{req.vehicle_id}' không tồn tại.")

    vehicle = load_vehicle_from_yaml(vehicle_path)

    # Tìm waypoints QL1A dọc tuyến đường
    waypoints = _find_corridor_waypoints(req.origin, req.destination)
    wp_coords = [Coordinate(lat, lon) for lat, lon in waypoints]

    # Lấy trạm sạc: dùng OCM thật nếu có key, ngược lại dùng mock
    if _ocm_provider is not None:
        real_stations = _ocm_provider.get_stations_along_corridor(
            waypoints=wp_coords,
            radius_km=30.0,
            min_power_kw=22.0,
        )
        print(f"[API] Dùng {len(real_stations)} trạm sạc thực tế từ Open Charge Map.")
    else:
        real_stations = []  # sẽ dùng mock bên dưới

    # Xây đồ thị với trạm sạc thật (hoặc mock nếu không có)
    graph = _build_corridor_graph(req.origin, req.destination, vehicle, waypoints, real_stations)

    try:
        plan = find_optimal_plan(graph, "O", "D", vehicle, req.start_soc_pct / 100.0)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Thu thập warnings từ rules và risk engine (không mutate plan)
    rest_warnings = RestRules.apply_rest_rules(plan)
    risk, risk_warnings = RiskEngine.evaluate(plan)

    # Tạo plan mới với đầy đủ warnings (frozen-safe dùng dataclasses.replace)
    all_warnings = list(plan.warnings) + rest_warnings + risk_warnings
    final_plan = dataclasses.replace(plan, warnings=all_warnings, risk=risk)

    # Build response stops
    stops_out = []
    for stop in final_plan.stops:
        stops_out.append(StopInfo(
            lat=stop.station.location.lat,
            lon=stop.station.location.lon,
            operator=stop.station.operator,
            charge_minutes=stop.charge_duration_s / 60,
            departure_soc_pct=stop.departure_soc_frac * 100,
        ))

    # Chuyển waypoints sang format [[lon, lat]] để MapLibre hiểu
    route_waypoints = [[lon, lat] for lat, lon in waypoints]

    return PlanResponse(
        total_duration_minutes=final_plan.total_duration_s / 60,
        total_drive_minutes=final_plan.total_drive_s / 60,
        total_charge_minutes=final_plan.total_charge_s / 60,
        total_energy_kwh=final_plan.total_energy_kwh,
        risk_level=risk.value,
        warnings=[w.message for w in all_warnings],
        stops=stops_out,
        route_waypoints=route_waypoints,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
