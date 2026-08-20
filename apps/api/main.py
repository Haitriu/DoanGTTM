import asyncio
import dataclasses
import math
import os
import random
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from voltrail_core.charging.time import compute_charge_time_s
from voltrail_core.models import (
    ChargingStation,
    Confidence,
    Connector,
    Coordinate,
    Vehicle,
)
from voltrail_core.models.vehicle_loader import load_vehicle_from_yaml
from voltrail_core.planner import ChargingGraph, RestRules, RiskEngine, find_optimal_plan
from voltrail_simulator.trip_simulator import (
    TripConditions,
    compute_leg_energy_kwh,
    generate_real_world_conditions,
    leg_duration_s,
)

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
        print("[API] ✅ Open Charge Map đã được kết nối (sử dụng trạm sạc thực tế).")
    except Exception as e:
        print(f"[API] ⚠️ Không thể khởi tạo OCM: {e}")
else:
    print("[API] ℹ️ Chế độ Demo: Dùng trạm sạc giả lập (chưa có OCM key).")

# GHI CHÚ: packages/adapters/voltrail_adapters/stations/serpapi_maps.py và
# routing/serpapi_directions.py là adapter Google Maps (qua SerpApi), đã viết
# và test bằng key thật nhưng KHÔNG nối vào đây:
# - serpapi_maps: chỉ tìm được vị trí, không có công suất (kW) nên không dùng
#   để lập kế hoạch; hiển thị "toàn bộ trạm dọc corridor" trên bản đồ gây rối
#   hơn là giúp ích (phản hồi người dùng), nên đã bỏ khỏi luồng chính.
# - serpapi_directions: đã xác nhận engine google_maps_directions của SerpApi
#   không trả toạ độ từng bước cho driving mode, không đủ để dựng polyline
#   tuyến đường thật. Xem OSRM (osrm.py, chạy qua `make dev`) cho routing thật.

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
    order: int
    lat: float
    lon: float
    operator: Optional[str]
    is_rest_stop: bool
    reason: str
    arrival_soc_pct: float
    departure_soc_pct: float
    charge_minutes: float


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


def _get_candidate_stations(
    waypoints: List[tuple],
    real_stations: Optional[List[ChargingStation]] = None,
) -> List[ChargingStation]:
    """
    Trả về danh sách trạm sạc trung gian dùng làm ứng viên cho graph lập kế
    hoạch — ưu tiên trạm thật (OCM), fallback sinh mock trên corridor QL1A.
    Danh sách này được tái sử dụng cả khi lập kế hoạch ban đầu lẫn khi lập
    lại kế hoạch (re-plan) giữa chuyến mô phỏng, vì các trạm không "di chuyển".
    """
    if real_stations and len(real_stations) >= 3:
        intermediate = [s for s in real_stations if s.id not in {"O", "D"}]
        print(f"[Graph] Dùng {len(intermediate)} trạm sạc thực tế.")
    else:
        intermediate = []
        mid_wps = waypoints[1:-1]
        for i, (lat, lon) in enumerate(mid_wps):
            jitter = random.uniform(-0.03, 0.03)
            power = random.choice([50.0, 150.0, 250.0])
            intermediate.append(_make_mock_station(f"MOCK-{i}", lat + jitter, lon + jitter, power))
        print(f"[Graph] Dùng {len(intermediate)} trạm sạc giả lập (không có OCM key).")
    return intermediate


def _solve_trip(
    vehicle: Vehicle,
    origin: Coordinate,
    destination: Coordinate,
    start_soc_frac: float,
    intermediate_stations: List[ChargingStation],
):
    """Dựng graph Origin/Destination + trạm ứng viên rồi tìm kế hoạch tối ưu."""
    origin_station = ChargingStation(
        id="O", location=origin, connectors=[],
        operator=None, amenities=frozenset(),
        data_confidence=Confidence.HIGH, last_verified_at=datetime.now(UTC),
    )
    dest_station = ChargingStation(
        id="D", location=destination, connectors=[],
        operator=None, amenities=frozenset(),
        data_confidence=Confidence.HIGH, last_verified_at=datetime.now(UTC),
    )
    all_stations = [origin_station, dest_station] + intermediate_stations
    graph = ChargingGraph()
    graph.build_from_stations("O", "D", all_stations, vehicle)

    plan = find_optimal_plan(graph, "O", "D", vehicle, start_soc_frac)

    rest_warnings = RestRules.apply_rest_rules(plan)
    risk, risk_warnings = RiskEngine.evaluate(plan)
    all_warnings = list(plan.warnings) + rest_warnings + risk_warnings
    final_plan = dataclasses.replace(plan, warnings=all_warnings, risk=risk)
    return final_plan, risk


def _stops_to_response(stops) -> List[StopInfo]:
    return [
        StopInfo(
            order=i + 1,
            lat=stop.station.location.lat,
            lon=stop.station.location.lon,
            operator=stop.station.operator,
            is_rest_stop=stop.is_rest_stop,
            reason=stop.reason.text,
            arrival_soc_pct=stop.arrival_soc.p50 * 100,
            departure_soc_pct=stop.departure_soc_frac * 100,
            charge_minutes=stop.charge_duration_s / 60,
        )
        for i, stop in enumerate(stops)
    ]



@app.post("/api/plan", response_model=PlanResponse)
async def create_plan(req: PlanRequest):
    vehicle_path = Path(f"data/vehicles/{req.vehicle_id}.yaml")
    if not vehicle_path.exists():
        raise HTTPException(status_code=404, detail=f"Xe '{req.vehicle_id}' không tồn tại.")

    vehicle = load_vehicle_from_yaml(vehicle_path)

    # Tìm waypoints QL1A dọc tuyến đường
    waypoints = _find_corridor_waypoints(req.origin, req.destination)
    wp_coords = [Coordinate(lat, lon) for lat, lon in waypoints]

    # Lấy trạm sạc dùng cho lập kế hoạch: chỉ nguồn có công suất (kW) đã biết —
    # OCM thật nếu có key, ngược lại dùng mock. SerpApi Places KHÔNG có kW nên
    # không bao giờ được đưa vào graph lập kế hoạch (xem SerpApiPlacesProvider).
    if _ocm_provider is not None:
        real_stations = _ocm_provider.get_stations_along_corridor(
            waypoints=wp_coords,
            radius_km=30.0,
            min_power_kw=22.0,
        )
        print(f"[API] Dùng {len(real_stations)} trạm sạc thực tế từ Open Charge Map.")
    else:
        real_stations = []  # sẽ dùng mock bên dưới

    # Trạm ứng viên (thật hoặc mock) + giải bài toán tối ưu
    intermediate_stations = _get_candidate_stations(waypoints, real_stations)
    try:
        final_plan, risk = _solve_trip(
            vehicle, req.origin, req.destination,
            req.start_soc_pct / 100.0, intermediate_stations,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    stops_out = _stops_to_response(final_plan.stops)

    # Chuyển waypoints sang format [[lon, lat]] để MapLibre hiểu
    route_waypoints = [[lon, lat] for lat, lon in waypoints]

    return PlanResponse(
        total_duration_minutes=final_plan.total_duration_s / 60,
        total_drive_minutes=final_plan.total_drive_s / 60,
        total_charge_minutes=final_plan.total_charge_s / 60,
        total_energy_kwh=final_plan.total_energy_kwh,
        risk_level=risk.value,
        warnings=[w.message for w in final_plan.warnings],
        stops=stops_out,
        route_waypoints=route_waypoints,
    )


def _prepare_stations_and_waypoints(origin: Coordinate, destination: Coordinate):
    waypoints = _find_corridor_waypoints(origin, destination)
    wp_coords = [Coordinate(lat, lon) for lat, lon in waypoints]
    if _ocm_provider is not None:
        real_stations = _ocm_provider.get_stations_along_corridor(
            waypoints=wp_coords, radius_km=30.0, min_power_kw=22.0,
        )
    else:
        real_stations = []
    intermediate_stations = _get_candidate_stations(waypoints, real_stations)
    return waypoints, intermediate_stations


# ---------------------------------------------------------------------------
# Mô phỏng xe chạy live (demo cho "dữ liệu xe trực tiếp" thay vì nhập tay).
#
# Đây LÀ một bộ giả lập (simulator), không phải dữ liệu xe thật — production
# thật sẽ nhận TelemetryMessage qua MQTT (packages/adapters/.../telemetry/mqtt.py,
# đã có sẵn interface TelemetrySubscriber). Bộ giả lập ở đây đóng vai trò nguồn
# telemetry: sinh vị trí + SOC cập nhật liên tục, có nhiễu tiêu hao thực tế
# (trọng tải phụ, chênh lệch nhiệt độ, gió) so với điều kiện chuẩn dùng khi lập
# kế hoạch ban đầu — rồi tự động lập lại kế hoạch (re-plan) khi SOC thực tế
# lệch đáng kể so với dự báo, giống một hệ thống dẫn đường EV thật phải làm.
# ---------------------------------------------------------------------------

SIM_TIME_SCALE = 120.0  # 1 giây thật = 120 giây mô phỏng (~1 chuyến 8h chạy trong ~4 phút)
SIM_TICK_S = 0.5  # tần suất cập nhật vị trí/SOC (giây thật)
REPLAN_ENERGY_DEVIATION = 1.15  # tiêu hao thực tế > 15% so với chuẩn -> lập lại kế hoạch
REPLAN_SAFETY_MARGIN_FRAC = 0.03  # thêm đệm 3% trên reserve khi phát hiện nguy hiểm
MAX_CONSECUTIVE_REPLANS = 3  # chặn vòng lặp vô hạn nếu lập lại kế hoạch vẫn không đủ an toàn
MAX_SIM_WALLCLOCK_S = 120.0  # lưới an toàn tuyệt đối: huỷ phiên nếu chạy quá 2 phút thời gian thực
# (một chuyến 8h ở SIM_TIME_SCALE=120 chỉ mất ~4 phút thực; 120s là dư dả cho trường
# hợp bình thường, đồng thời đảm bảo một lỗi logic không lường trước không bao giờ
# làm task chạy vô hạn và ngốn CPU của event loop).


def _haversine_m(a: Coordinate, b: Coordinate) -> float:
    lon1, lat1, lon2, lat2 = map(math.radians, [a.lon, a.lat, b.lon, b.lat])
    dlon, dlat = lon2 - lon1, lat2 - lat1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * math.asin(math.sqrt(h)) * 6371000


class SimSession:
    def __init__(self, vehicle: Vehicle, origin: Coordinate, destination: Coordinate,
                 start_soc_frac: float, intermediate_stations: List[ChargingStation],
                 conditions: TripConditions):
        self.vehicle = vehicle
        self.destination = destination
        self.intermediate_stations = intermediate_stations
        self.conditions = conditions

        self.status = "planning"  # planning -> driving -> charging -> arrived / failed
        self.lat = origin.lat
        self.lon = origin.lon
        self.soc_frac = start_soc_frac
        self.elapsed_sim_s = 0.0
        self.replan_count = 0
        self.warnings: List[str] = []
        self.stops_out: List[StopInfo] = []
        self.error: Optional[str] = None
        self.cancelled = False

        self._hops: List[dict] = []  # [{to: Coordinate, target_soc_frac, is_destination, label}]
        self._hop_index = 0
        self._consecutive_replans = 0
        self._deviation_warned = False
        self.deviation_ratio = 1.0  # actual_kwh / planned_kwh quan sát gần nhất

    def load_plan(self, final_plan) -> None:
        """Nạp một TripPlan (mới lập hoặc lập lại) thành chuỗi hop để chạy mô phỏng."""
        self.stops_out = _stops_to_response(final_plan.stops)
        hops = []
        for stop in final_plan.stops:
            hops.append({
                "to": stop.station.location,
                "target_soc_frac": stop.departure_soc_frac,
                "is_destination": False,
                "label": stop.station.operator or "Trạm sạc",
            })
        hops.append({
            "to": self.destination, "target_soc_frac": None,
            "is_destination": True, "label": "Điểm đến",
        })
        self._hops = hops
        self._hop_index = 0


_sim_sessions: Dict[str, SimSession] = {}


class SimulateStartRequest(BaseModel):
    origin: Coordinate
    destination: Coordinate
    vehicle_id: str
    start_soc_pct: float = 100.0


class SimulateStateResponse(BaseModel):
    status: str
    lat: float
    lon: float
    soc_pct: float
    elapsed_minutes: float
    replan_count: int
    warnings: List[str]
    stops: List[StopInfo]
    conditions: dict
    error: Optional[str] = None


def _warn_deviation_once(session: SimSession, planned_kwh: float, actual_kwh: float) -> None:
    """Cảnh báo lệch tiêu hao — thông tin, chỉ hiện một lần mỗi phiên. Bộ lập kế
    hoạch dùng mô hình tiêu hao chuẩn hoá (flat-rate) nên độ lệch so với vật lý
    thực (có nhiễu) gần như luôn tồn tại; không dùng làm điều kiện lập lại kế
    hoạch liên tục (sẽ không hội tụ) — chỉ báo 1 lần là đủ.
    """
    if session._deviation_warned or actual_kwh <= planned_kwh * REPLAN_ENERGY_DEVIATION:
        return
    session._deviation_warned = True
    pct = (actual_kwh / planned_kwh - 1) * 100
    c = session.conditions
    session.warnings.append(
        f"⚠️ Tiêu hao thực tế cao hơn dự kiến ~{pct:.0f}% do trọng tải/thời tiết "
        f"(tải phụ {c.extra_load_kg:.0f}kg, {c.temperature_c:.0f}°C, gió {c.wind_mps:+.1f}m/s)."
    )


def _try_replan(session: SimSession, origin_pt: Coordinate) -> bool:
    """Lập lại kế hoạch từ vị trí hiện tại khi SOC sắp chạm reserve. Trả về
    True nếu đã lập lại thành công (vòng lặp gọi nên chạy lại từ hop mới),
    False nếu nên dừng hẳn (session.status đã chuyển sang "failed").

    Bộ lập kế hoạch (_solve_trip) dùng mô hình tiêu hao chuẩn hoá cố định,
    không biết về điều kiện thực tế (trọng tải/thời tiết) — nên nếu gọi lại
    với đúng SOC hiện tại, nó sẽ ra lại y hệt kế hoạch cũ và lập tức "unsafe"
    trở lại. Để việc lập lại kế hoạch thực sự có tác dụng, ta báo cho nó một
    SOC hiệu dụng thấp hơn, theo đúng tỉ lệ tiêu hao vượt mức đã quan sát
    được (deviation_ratio) — khiến nó chọn trạm gần hơn / sạc lên mức cao hơn.
    """
    if session._consecutive_replans >= MAX_CONSECUTIVE_REPLANS:
        session.status = "failed"
        session.error = (
            "Không tìm được kế hoạch an toàn: tiêu hao thực tế vượt quá "
            "khả năng bù đắp bằng cách đổi trạm sạc."
        )
        return False
    effective_soc_frac = min(1.0, session.soc_frac / max(1.0, session.deviation_ratio))
    try:
        new_plan, _risk = _solve_trip(
            session.vehicle, origin_pt, session.destination,
            effective_soc_frac, session.intermediate_stations,
        )
    except Exception as e:
        session.status = "failed"
        session.error = f"Không tìm được kế hoạch an toàn sau khi tiêu hao lệch dự báo: {e}"
        return False

    session.load_plan(new_plan)
    session.replan_count += 1
    session._consecutive_replans += 1
    session.warnings.append(
        f"🔄 Đã lập lại kế hoạch (lần {session.replan_count}): SOC thực tế sắp "
        f"xuống dưới mức an toàn, đã tính lại chuỗi trạm sạc từ vị trí hiện tại."
    )
    return True


async def _drive_hop(session: SimSession, origin_pt: Coordinate, hop: dict,
                      distance_m: float, actual_kwh: float) -> bool:
    """Di chuyển một hop theo thời gian mô phỏng, nội suy vị trí + SOC tuyến
    tính. Trả về False nếu phiên bị huỷ giữa chừng."""
    usable_kwh = session.vehicle.battery.usable_capacity_kwh
    duration_sim_s = leg_duration_s(distance_m)
    ticks = max(1, int(duration_sim_s / SIM_TIME_SCALE / SIM_TICK_S))
    session.status = "driving"
    for tick in range(1, ticks + 1):
        if session.cancelled:
            return False
        frac = tick / ticks
        session.lat = origin_pt.lat + (hop["to"].lat - origin_pt.lat) * frac
        session.lon = origin_pt.lon + (hop["to"].lon - origin_pt.lon) * frac
        session.soc_frac -= actual_kwh / usable_kwh * (1 / ticks)
        session.elapsed_sim_s += duration_sim_s / ticks
        await asyncio.sleep(SIM_TICK_S)
    session.lat, session.lon = hop["to"].lat, hop["to"].lon
    return True


async def _charge_at_stop(session: SimSession, hop: dict, soc_before: float) -> bool:
    """Sạc tại trạm dừng — dùng thời gian sạc thật qua đường cong sạc của xe.
    Trả về False nếu phiên bị huỷ giữa chừng."""
    session.status = "charging"
    target = hop["target_soc_frac"]
    station = next(
        (s for s in session.intermediate_stations
         if s.location.lat == hop["to"].lat and s.location.lon == hop["to"].lon),
        None,
    )
    station_power_kw = (
        max((c.max_power_kw for c in station.connectors), default=50.0) if station else 50.0
    )
    charge_s = compute_charge_time_s(session.vehicle, station_power_kw, session.soc_frac, target)
    charge_ticks = max(1, int(charge_s / SIM_TIME_SCALE / SIM_TICK_S))
    for _tick in range(1, charge_ticks + 1):
        if session.cancelled:
            return False
        session.soc_frac += (target - soc_before) * (1 / charge_ticks)
        session.elapsed_sim_s += charge_s / charge_ticks
        await asyncio.sleep(SIM_TICK_S)
    session.soc_frac = target
    return True


async def _run_simulation(session_id: str):
    session = _sim_sessions[session_id]
    started_at = time.monotonic()
    try:
        while not session.cancelled and session._hop_index < len(session._hops):
            if time.monotonic() - started_at > MAX_SIM_WALLCLOCK_S:
                session.status = "failed"
                session.error = "Mô phỏng vượt quá thời gian cho phép — đã huỷ để bảo vệ hệ thống."
                return
            hop = session._hops[session._hop_index]
            origin_pt = Coordinate(session.lat, session.lon)
            distance_m = _haversine_m(origin_pt, hop["to"])

            planned_kwh = compute_leg_energy_kwh(session.vehicle, distance_m)
            actual_kwh = compute_leg_energy_kwh(
                session.vehicle, distance_m,
                temperature_c=session.conditions.temperature_c,
                wind_mps=session.conditions.wind_mps,
                extra_load_kg=session.conditions.extra_load_kg,
            )
            usable_kwh = session.vehicle.battery.usable_capacity_kwh
            soc_at_hop_end = session.soc_frac - actual_kwh / usable_kwh
            session.deviation_ratio = actual_kwh / planned_kwh if planned_kwh > 0 else 1.0

            _warn_deviation_once(session, planned_kwh, actual_kwh)

            # Chỉ lập lại kế hoạch khi thực sự nguy hiểm (SOC sắp chạm reserve) —
            # đây là điều bộ lập kế hoạch CÓ THỂ khắc phục (chọn trạm gần/khác đi).
            safety_floor = session.vehicle.battery.reserve_soc_frac + REPLAN_SAFETY_MARGIN_FRAC
            if soc_at_hop_end < safety_floor:
                if _try_replan(session, origin_pt):
                    continue  # chạy lại từ hop đầu tiên của kế hoạch mới
                return

            if not await _drive_hop(session, origin_pt, hop, distance_m, actual_kwh):
                return
            session.soc_frac = soc_at_hop_end
            session._consecutive_replans = 0  # đã di chuyển thành công, reset bộ đếm

            if hop["is_destination"]:
                session.status = "arrived"
                return

            if not await _charge_at_stop(session, hop, soc_at_hop_end):
                return

            session._hop_index += 1
    except Exception as e:
        session.status = "failed"
        session.error = str(e)


@app.post("/api/simulate/start")
async def start_simulation(req: SimulateStartRequest):
    vehicle_path = Path(f"data/vehicles/{req.vehicle_id}.yaml")
    if not vehicle_path.exists():
        raise HTTPException(status_code=404, detail=f"Xe '{req.vehicle_id}' không tồn tại.")
    vehicle = load_vehicle_from_yaml(vehicle_path)

    waypoints, intermediate_stations = _prepare_stations_and_waypoints(req.origin, req.destination)
    start_soc_frac = req.start_soc_pct / 100.0

    try:
        final_plan, _risk = _solve_trip(
            vehicle, req.origin, req.destination, start_soc_frac, intermediate_stations,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    conditions = generate_real_world_conditions(random.Random())
    session_id = str(uuid.uuid4())
    session = SimSession(vehicle, req.origin, req.destination, start_soc_frac,
                          intermediate_stations, conditions)
    session.load_plan(final_plan)
    _sim_sessions[session_id] = session

    asyncio.create_task(_run_simulation(session_id))

    return {
        "session_id": session_id,
        "conditions": dataclasses.asdict(conditions),
        "route_waypoints": [[lon, lat] for lat, lon in waypoints],
    }


@app.get("/api/simulate/{session_id}", response_model=SimulateStateResponse)
async def get_simulation_state(session_id: str):
    session = _sim_sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Phiên mô phỏng không tồn tại.")
    return SimulateStateResponse(
        status=session.status,
        lat=session.lat,
        lon=session.lon,
        soc_pct=session.soc_frac * 100,
        elapsed_minutes=session.elapsed_sim_s / 60,
        replan_count=session.replan_count,
        warnings=session.warnings,
        stops=session.stops_out,
        conditions=dataclasses.asdict(session.conditions),
        error=session.error,
    )


@app.post("/api/simulate/{session_id}/stop")
async def stop_simulation(session_id: str):
    session = _sim_sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Phiên mô phỏng không tồn tại.")
    session.cancelled = True
    del _sim_sessions[session_id]
    return {"stopped": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
