# ARCHITECTURE — Voltrail

Thiết kế hệ thống. Đọc `PRD.md` trước để hiểu *làm gì*; file này giải thích *làm thế nào*.

---

## 1. Nguyên tắc kiến trúc

1. **Lõi thuần, biên bẩn.** Toàn bộ thuật toán nằm trong `core/` — không I/O, không
   network, không DB. Tính được, test được ở mili-giây.
2. **Nguồn dữ liệu là thứ thay thế được.** OSRM có thể đổi thành Valhalla; Open Charge Map
   có thể đổi thành OCPI. Mỗi loại nguồn có một `Protocol` do `core/` định nghĩa.
3. **Chạy được khi không có gì.** Không có internet, không có xe, không có API key → vẫn
   chạy được bằng fixture + simulator.
4. **Mọi ước lượng đều có phân phối.** Không có con số trần trong hệ thống.
5. **Quyết định phải giải thích được.** Mỗi bước trong kế hoạch mang theo lý do của nó.
6. **Đơn giản trước.** Không Kafka, không Kubernetes, không microservice ở bản đầu.
   Một FastAPI + PostGIS + Redis là đủ cho hàng nghìn request/ngày.

---

## 2. Tổng quan hệ thống

```
        Web UI (Next.js)          CLI              Thư viện Python
              │                    │                      │
              └────────────────────┼──────────────────────┘
                                   │
                          ┌────────▼────────┐
                          │   FastAPI       │
                          │   apps/api      │
                          └────────┬────────┘
                                   │
       ┌───────────────────────────┼───────────────────────────┐
       │                           │                           │
┌──────▼───────┐          ┌────────▼────────┐        ┌─────────▼────────┐
│  ADAPTERS    │          │      CORE       │        │   PERSISTENCE    │
│              │          │  (thuần, tested)│        │                  │
│ routing/     │          │                 │        │  PostgreSQL      │
│  └ OSRM      │─────────►│  energy/        │        │   + PostGIS      │
│ stations/    │  cung    │  charging/      │        │                  │
│  └ OCM       │  cấp     │  routing/       │        │  Redis (cache,   │
│ weather/     │  dữ liệu │  rest/          │        │   trạng thái)    │
│  └ Open-Meteo│          │  risk/          │        │                  │
│ elevation/   │          │                 │        │  MinIO / S3      │
│ telemetry/*  │          │  KHÔNG có I/O   │        │   (tùy chọn)     │
└──────┬───────┘          └─────────────────┘        └──────────────────┘
       │
       ▼
  Dịch vụ ngoài / fixture / simulator

  * telemetry là tùy chọn — hệ thống chạy đầy đủ khi không có nó
```

### Vì sao không có Kafka ở bản đầu

Kế hoạch gốc đặt Kafka làm xương sống. Kafka đúng khi bạn có **hàng nghìn xe phát
telemetry liên tục**. Ở đây, luồng chính là **request–response**: người dùng hỏi, hệ
thống tính, trả lời. Đưa Kafka vào ngay sẽ:

* làm việc setup của contributor mới nặng thêm rất nhiều,
* thêm một tầng debug không cần thiết,
* giải quyết một vấn đề chưa tồn tại.

Kafka sẽ vào ở **Mốc D**, khi telemetry thật xuất hiện — và khi đó nó vào sau một
interface, không phải thay thế toàn bộ kiến trúc. Xem §11.

---

## 3. Mô hình miền

```python
# packages/core/voltrail_core/models/

@dataclass(frozen=True)
class Coordinate:
    lat: float
    lon: float

@dataclass(frozen=True)
class Vehicle:
    id: str
    battery: BatterySpec          # usable_capacity_kwh, reserve_soc_frac
    physics: PhysicsSpec          # mass_kg, cd, frontal_area_m2, crr, eta
    auxiliary: AuxiliarySpec      # base_power_kw, hvac_max_power_kw
    charging: ChargingSpec        # max_dc_kw, connectors, curve

@dataclass(frozen=True)
class RouteSegment:
    """Một đoạn ~100–500 m của tuyến, đơn vị nguyên tử để tính năng lượng."""
    distance_m: float
    start: Coordinate
    end: Coordinate
    elevation_gain_m: float       # đã làm mượt
    grade: float                  # tỉ lệ, +0.06 = lên dốc 6%
    speed_limit_mps: float
    expected_speed_mps: float     # đã tính traffic
    road_class: RoadClass

@dataclass(frozen=True)
class EnergyEstimate:
    total_kwh: float
    rolling_kwh: float
    aero_kwh: float
    grade_kwh: float
    auxiliary_kwh: float
    regen_kwh: float              # âm
    p10_kwh: float
    p90_kwh: float

@dataclass(frozen=True)
class ChargingStation:
    id: str
    location: Coordinate
    connectors: list[Connector]   # type, max_power_kw, count
    operator: str | None
    amenities: frozenset[Amenity] # restroom, food, shelter → dùng cho điểm nghỉ
    data_confidence: Confidence
    last_verified_at: datetime | None

@dataclass(frozen=True)
class PlanStop:
    station: ChargingStation
    arrival_soc: SocEstimate      # p10 / p50 / p90
    departure_soc_frac: float
    charge_duration_s: int
    is_rest_stop: bool
    reason: StopReason            # lý do có thể hiển thị cho người dùng

@dataclass(frozen=True)
class TripPlan:
    legs: list[PlanLeg]
    stops: list[PlanStop]
    total_duration_s: int
    total_drive_s: int
    total_charge_s: int
    total_energy_kwh: float
    estimated_cost: Money | None
    risk: RiskLevel
    alternatives: list[TripPlan]
    warnings: list[Warning]
```

**Tất cả đều `frozen=True`.** Kế hoạch là giá trị bất biến, không phải đối tượng bị sửa
đổi dần. Điều này loại bỏ cả một lớp bug trong thuật toán tìm kiếm.

---

## 4. Mô hình năng lượng

### 4.1. Vật lý

Với mỗi `RouteSegment`, lực cản tại bánh xe:

```
F_lăn    = C_rr · m · g · cos(θ)
F_khí    = ½ · ρ(T, h) · C_d · A · v_eff²
F_dốc    = m · g · sin(θ)
F_quán   = m · a          (chỉ khi mô hình hoá tăng/giảm tốc)

F_tổng   = F_lăn + F_khí + F_dốc + F_quán
```

Trong đó `v_eff = v + v_gió_ngược` (thành phần gió chiếu lên hướng đi).

Năng lượng tại bánh xe:

```
E_bánh_J = F_tổng · d
```

Quy về năng lượng lấy từ pin:

```
nếu E_bánh_J > 0:   E_pin_J = E_bánh_J / η_drivetrain
nếu E_bánh_J < 0:   E_pin_J = E_bánh_J · η_regen        (thu hồi, giá trị âm)
```

Phụ tải:

```
P_aux_kW = P_base + P_hvac(T_ngoài)
E_aux_kWh = P_aux_kW · (d / v) / 3600
```

Tổng:

```
E_kWh = E_pin_J / 3.6e6 + E_aux_kWh
```

### 4.2. Hiệu ứng nhiệt độ

Ba tác động riêng biệt — dễ bị gộp nhầm thành một:

```
1. Dung lượng khả dụng giảm       usable · f_cap(T_pin)
2. Hiệu suất drivetrain giảm      η · f_eff(T_pin)
3. HVAC tiêu thụ                  P_hvac(T_ngoài)   ← thường là tác động lớn nhất
```

Đường cong mặc định (hiệu chỉnh sau bằng dữ liệu thật):

```
T (°C)   f_cap    f_eff    P_hvac (kW)
 -10     0.80     0.90       4.5
   0     0.88     0.94       3.0
  10     0.95     0.97       1.2
  20     1.00     1.00       0.3
  30     0.98     0.99       2.0
  40     0.94     0.96       3.5
```

### 4.3. Khoảng tin cậy

Không dùng Monte Carlo (quá chậm cho ngân sách 1ms). Dùng lan truyền sai số phân tích:

```
σ²_tổng = σ²_tốc_độ + σ²_thời_tiết + σ²_hồ_sơ_xe + σ²_tài_xế

p10 = p50 · (1 - 1.28·σ)
p90 = p50 · (1 + 1.28·σ)
```

σ mặc định theo mức tin cậy của thông số xe: `high 0.06 / medium 0.10 / low 0.15`.

**Quan trọng:** ràng buộc SOC ≥ reserve luôn kiểm tra trên **p10**, không trên p50.
Kế hoạch phải an toàn trong kịch bản xấu, không chỉ kịch bản trung bình.

### 4.4. Làm mượt độ dốc

Dữ liệu elevation (SRTM ~30m) rất nhiễu. Độ dốc thô đưa thẳng vào mô hình sẽ tạo ra dao
động năng lượng phi vật lý.

```
Elevation thô
     ↓  Savitzky–Golay, cửa sổ ≥ 100 m
Elevation mượt
     ↓  vi phân
Độ dốc
     ↓  clamp ±12%      (dốc thực tế trên đường công cộng hiếm khi vượt)
Độ dốc dùng cho mô hình
```

---

## 5. Mô hình sạc

### 5.1. Công suất thực tế

```python
def actual_power_kw(vehicle, station_connector, soc_frac, battery_temp_c) -> float:
    return min(
        station_connector.max_power_kw,
        vehicle.charging.max_dc_power_kw,
        vehicle.charging.curve.at(soc_frac),
    ) * temp_derate(battery_temp_c)
```

Đường cong là piecewise-linear giữa các điểm mốc trong catalog xe.

### 5.2. Thời gian sạc

```
t(soc_a → soc_b) = ∫  C_usable / P(s)  ds
                   soc_a→soc_b
```

Tích phân số bằng cách chia thành bước 1% SOC. Với 100 bước, mỗi bước là một phép chia —
đủ nhanh để gọi hàng nghìn lần trong vòng lặp tìm kiếm.

**Tối ưu:** tiền tính bảng `time_to_charge[station_power][soc_a][soc_b]` cho mỗi xe,
lưới 1% → tra bảng O(1) trong thuật toán.

### 5.3. Vì sao đây là điểm mấu chốt của toàn bộ bài toán

```
Sạc 10% → 80%    ở 150 kW    ≈ 28 phút     (2.05 kWh/phút)
Sạc 80% → 100%   ở 150 kW    ≈ 38 phút     (0.43 kWh/phút)
```

20 điểm % cuối mất **nhiều thời gian hơn** 70 điểm % đầu. Đây chính là lý do "sạc đầy rồi
đi tiếp" gần như luôn là chiến lược tệ, và là lý do bài toán cần thuật toán chứ không cần
heuristic.

---

## 6. Thuật toán lập kế hoạch

Đây là phần cốt lõi. Chia 5 giai đoạn.

```
       Điểm đi, điểm đến, xe, SOC, thời điểm
                      │
    ┌─────────────────▼─────────────────┐
    │  GĐ1  Trích xuất hành lang tuyến  │   OSRM: tuyến chính + 2 phương án
    └─────────────────┬─────────────────┘
                      │
    ┌─────────────────▼─────────────────┐
    │  GĐ2  Lọc trạm ứng viên           │   PostGIS trong buffer, lọc tương thích
    └─────────────────┬─────────────────┘   ~2000 trạm → ~40 trạm
                      │
    ┌─────────────────▼─────────────────┐
    │  GĐ3  Xây đồ thị + tính năng lượng│   Cạnh (i,j) nếu đi được
    └─────────────────┬─────────────────┘
                      │
    ┌─────────────────▼─────────────────┐
    │  GĐ4  Labeling với charging func  │   ← thuật toán chính
    └─────────────────┬─────────────────┘
                      │
    ┌─────────────────▼─────────────────┐
    │  GĐ5  Chèn ràng buộc nghỉ + PA dự phòng │
    └─────────────────┬─────────────────┘
                      ▼
                  TripPlan
```

### GĐ1 — Hành lang tuyến

Gọi routing engine lấy tuyến chính và các phương án. Không tự tính đường — đó là bài toán
đã được giải rất tốt bởi OSRM/Valhalla. Chúng ta giải bài toán **năng lượng trên tuyến**.

Chia polyline thành `RouteSegment` ~200 m, gắn elevation và tốc độ kỳ vọng.

### GĐ2 — Tập trạm ứng viên

Đây là bước làm bài toán từ không giải được thành giải được trong 2 giây.

```sql
SELECT * FROM charging_stations
WHERE ST_DWithin(location::geography, ST_GeogFromText(:route_wkt), 5000)
  AND status = 'operational'
  AND EXISTS (
    SELECT 1 FROM connectors c
    WHERE c.station_id = charging_stations.id
      AND c.connector_type = ANY(:vehicle_connectors)
      AND c.max_power_kw >= :min_power_kw
  )
ORDER BY route_progress_m;
```

Sau đó lọc thêm:

* Đường vòng để tới trạm ≤ `max(5 phút, 10% khoảng cách chặng)`.
* Trong một cụm bán kính 2 km, giữ tối đa 2 trạm tốt nhất (tránh nổ tổ hợp ở đô thị).
* Luôn giữ lại trạm công suất cao nhất trong mỗi đoạn 50 km.

Kết quả: **~30–60 nút** cho chuyến 500 km. Đây là kích thước mà thuật toán chính xác chạy
được, thay vì phải dùng heuristic.

### GĐ3 — Đồ thị

Nút = {điểm đi} ∪ {trạm ứng viên} ∪ {điểm đến}, sắp theo tiến độ trên tuyến.

Cạnh `i → j` (chỉ đi tới, `progress(j) > progress(i)`) tồn tại nếu:

```
E_p90(i→j)  ≤  C_usable · (1 - reserve_soc_frac)
```

Dùng **p90** ở đây (kịch bản tốn nhiều điện nhất) để cạnh không khả thi bị loại từ đầu.

Mỗi cạnh mang: `energy_p10/p50/p90`, `drive_time_s`, `distance_m`.

### GĐ4 — Labeling với charging function

Đây là phương pháp chuẩn cho bài toán này (họ thuật toán "shortest feasible path with
charging stops"). Ý tưởng: mỗi nhãn không phải một giá trị mà là **một hàm** — thời gian
tới nơi như hàm của SOC lúc rời đi.

```
Nhãn tại nút v:  (t_arrive, soc_arrive, parent, charge_decision)

Quan hệ trội (dominance):
   nhãn A trội nhãn B   ⟺   t_A ≤ t_B  ∧  soc_A ≥ soc_B
   → loại B
```

Vòng lặp:

```python
labels = {origin: [Label(t=depart_time, soc=initial_soc)]}
queue = PriorityQueue([(depart_time, origin_label)])

while queue:
    t, label = queue.pop()
    v = label.node
    if v is destination:
        return reconstruct(label)

    for u in successors(v):
        # cần bao nhiêu SOC để tới u an toàn
        need = edge_energy_p90(v, u) / usable_capacity + reserve
        if need > 1.0:
            continue                      # không tới nổi kể cả sạc đầy

        # chỉ xét các mức sạc rời đi có ý nghĩa
        for soc_depart in candidate_departure_socs(label.soc, need):
            t_charge = charge_time(v.station, label.soc, soc_depart)
            t_arrive = t + t_charge + edge_drive_time(v, u)
            soc_arrive = soc_depart - need + reserve
            new = Label(t_arrive, soc_arrive, parent=label)
            if not dominated(new, labels[u]):
                insert(labels[u], new)
                queue.push((t_arrive, new))
```

**`candidate_departure_socs`** là chỗ cần cẩn thận. Không rời rạc hoá đều 1% (quá chậm).
Chỉ xét các mức có ý nghĩa:

```
1. Vừa đủ tới u với biên an toàn      (soc_min)
2. Vừa đủ tới u rồi tới u' kế tiếp     (bỏ qua một trạm)
3. Các điểm gãy của đường cong sạc     (80%, 90% — nơi tốc độ sạc thay đổi)
4. Sạc đầy 100%                        (chỉ khi cần thiết)
```

Thường chỉ còn **3–6 lựa chọn mỗi nút**, thay vì 100. Đây là tối ưu quan trọng nhất về
hiệu năng.

**Độ phức tạp thực tế:** với 40 nút, 5 mức sạc, dominance pruning tích cực → vài chục
nghìn nhãn, chạy dưới 500 ms bằng Python thuần.

### GĐ5 — Ràng buộc nghỉ

Sau khi có tuyến tối ưu về thời gian, kiểm tra ràng buộc nghỉ:

```
Với mỗi chặng lái liên tục > max_continuous_drive_s:
    │
    ├─ Có điểm sạc trong khoảng thời gian đó?
    │     → kéo dài lần sạc đó lên tối thiểu 15 phút   (chi phí = 0 nếu đang sạc lâu hơn)
    │
    └─ Không có?
          → chèn một điểm nghỉ
              ưu tiên trạm có amenities, kể cả khi chưa cần sạc
              (sạc một ít trong lúc nghỉ là "miễn phí" về thời gian)
```

**Nguyên tắc:** một lần dừng phục vụ hai mục đích luôn tốt hơn hai lần dừng. Đây là điểm
mà việc gộp nghỉ ngơi vào ngay trong bài toán tối ưu (thay vì nhắc nhở riêng lẻ) tạo ra
khác biệt thật.

### Phương án dự phòng

Với mỗi điểm dừng, tìm trạm thay thế gần nhất vẫn giữ kế hoạch khả thi, tính chi phí thời
gian tăng thêm. Hiển thị cho người dùng:

```
Trạm Phong Nha kín chỗ?
  → Trạm Đồng Hới, cách 34 km, +18 phút, SOC khi tới 12%
```

**Nếu một điểm dừng không có phương án dự phòng nào** → cảnh báo rõ ràng. Đây là thông tin
người lái cần biết trước khi khởi hành, không phải lúc đứng trước trụ sạc hỏng.

### Re-plan khi đang đi

Chạy lại GĐ2–GĐ5 từ vị trí hiện tại. Kích hoạt khi:

```
|SOC thực tế - SOC dự đoán|  >  5 điểm %
tiêu hao thực tế lệch p50    >  15%
đã đi lệch khỏi tuyến        >  2 km
trạm kế tiếp báo không khả dụng
```

Có **hysteresis** để tránh kế hoạch nhảy liên tục: chỉ thay kế hoạch khi phương án mới tốt
hơn ≥ 5 phút hoặc kế hoạch cũ đã không còn khả thi.

---

## 7. Risk engine

Tách riêng khỏi planner, để sau này thay bằng ML mà không phải viết lại planner.

```
    SOC hiện tại ──┐
    SOC p10 kế   ──┤
    Thời gian lái──┤
    Xu hướng tiêu ─┤──►  Risk Engine  ──►  SAFE | AWARE | REST | CHARGE | CRITICAL
    Khoảng cách  ──┤        (rule)
    Nhiệt độ pin ──┤
    Tin cậy trạm ──┘
```

Interface cố định, cài đặt thay được:

```python
class RiskEngine(Protocol):
    def evaluate(self, signals: RiskSignals) -> RiskAssessment: ...
```

Phase 1: `RuleBasedRiskEngine`, ngưỡng trong `config/risk.yaml`.
Phase 3: `MLRiskEngine` học từ dữ liệu "cảnh báo → người dùng làm gì → kết quả thực tế".

### Chống spam thông báo

Bài toán này trong kế hoạch gốc được nêu rất đúng. Giải pháp:

```
Chỉ phát cảnh báo khi:
   trạng thái rủi ro THAY ĐỔI            (không phải mỗi lần SOC giảm 1%)
   AND đã qua cooldown                   (≥ 10 phút cho cùng loại)
   AND người dùng chưa bỏ qua lần trước  (tôn trọng quyết định của họ)

CRITICAL bỏ qua cooldown.
```

---

## 8. Dữ liệu

### 8.1. Schema (PostgreSQL + PostGIS)

```sql
-- Danh mục
vehicles                (id, name, spec JSONB, confidence, source, created_at)
charging_stations       (id, external_id, source, location GEOGRAPHY(POINT,4326),
                         name, operator, status, amenities TEXT[],
                         data_confidence, last_verified_at, raw JSONB)
connectors              (id, station_id, connector_type, max_power_kw, count, status)

-- Lập kế hoạch
trip_plans              (id, request JSONB, plan JSONB, engine_version,
                         created_at, compute_ms)

-- Học từ thực tế (Mốc D)
observed_trips          (id, vehicle_id, started_at, ended_at, distance_m,
                         energy_kwh, is_synthetic BOOLEAN NOT NULL)
trip_segments_observed  (id, trip_id, seq, distance_m, duration_s,
                         energy_kwh, avg_speed_mps, elevation_gain_m,
                         temperature_c)
vehicle_calibration     (vehicle_instance_id, correction_factor, sample_count,
                         updated_at)
prediction_log          (id, plan_id, predicted JSONB, actual JSONB,
                         error_kwh_per_100km, model_version)

-- Index
CREATE INDEX ON charging_stations USING GIST (location);
CREATE INDEX ON charging_stations (status) WHERE status = 'operational';
CREATE INDEX ON connectors (station_id, connector_type, max_power_kw);
```

`observed_trips.is_synthetic` là `NOT NULL` có chủ đích — để **không bao giờ** vô tình
huấn luyện mô hình trên dữ liệu simulator mà tưởng là dữ liệu thật.

### 8.2. Chiến lược cache (Redis)

```
station:bbox:{geohash}:{connector}:{power}     TTL 24h
weather:{lat_r}:{lon_r}:{hour}                 TTL  1h
elevation:{polyline_hash}                      TTL  ∞    ← địa hình không đổi
route:{origin}:{dest}:{profile}                TTL  1h
plan:{request_hash}                            TTL 15m
```

### 8.3. Nguồn dữ liệu

| Loại | Nguồn chính | Dự phòng |
|---|---|---|
| Định tuyến | OSRM (self-host) | Valhalla |
| Trạm sạc | Open Charge Map | NREL AFDC (US), OCPI, dữ liệu địa phương |
| Thời tiết | Open-Meteo | mặc định theo mùa |
| Độ cao | SRTM qua Open-Elevation | tile tự host |
| Địa danh | Nominatim | — |

**Mỗi nguồn phải được ghi vào `docs/DATA_SOURCES.md`** kèm giấy phép, yêu cầu attribution
và giới hạn rate. Kiểm tra lại điều khoản trước mỗi lần release — điều khoản có thay đổi.

---

## 9. API

### `POST /v1/plan`

```jsonc
// Request
{
  "origin": {"lat": 21.0285, "lon": 105.8542},
  "destination": {"lat": 16.0544, "lon": 108.2022},
  "vehicle_id": "vinfast-vf8-eco-2023",
  "initial_soc_frac": 0.92,
  "departure_time": "2026-08-21T06:00:00+07:00",
  "preferences": {
    "objective": "min_time",          // min_time | min_cost | min_stops
    "min_charger_power_kw": 50,
    "reserve_soc_frac": 0.10,
    "max_continuous_drive_s": 9000,
    "passengers": 2,
    "extra_load_kg": 60
  }
}
```

```jsonc
// Response 200
{
  "plan": {
    "total_duration_s": 42120,
    "total_drive_s": 38520,
    "total_charge_s": 3600,
    "total_energy_kwh": 141.2,
    "arrival_soc": {"p10": 0.14, "p50": 0.19, "p90": 0.24},
    "risk": "SAFE",
    "legs": [ /* ... */ ],
    "stops": [
      {
        "station": { "id": "ocm-123456", "name": "Trạm Nghi Sơn",
                     "location": {"lat": 19.35, "lon": 105.78},
                     "max_power_kw": 150, "data_confidence": "high" },
        "arrival_soc": {"p10": 0.29, "p50": 0.34, "p90": 0.39},
        "departure_soc_frac": 0.80,
        "charge_duration_s": 1560,
        "is_rest_stop": true,
        "reason": {
          "code": "OPTIMAL_POWER_AND_REST",
          "text": "Công suất 150 kW và trùng mốc nghỉ 3 giờ lái"
        },
        "fallback": { "station_id": "ocm-789", "extra_duration_s": 1080 }
      }
    ],
    "warnings": []
  },
  "alternatives": [ /* tối đa 2 */ ],
  "meta": { "engine_version": "0.1.0", "compute_ms": 1240,
            "data_sources": ["openchargemap", "openstreetmap", "open-meteo"] }
}
```

```jsonc
// Response 422 — không có phương án khả thi
{
  "error": "no_feasible_plan",
  "message": "Không tìm được lộ trình an toàn với SOC ban đầu 22%.",
  "detail": {
    "reason": "charging_gap_too_large",
    "gap_km": 210,
    "max_range_km": 178,
    "between": ["ocm-123456", "ocm-789012"]
  },
  "suggestions": [
    {"action": "increase_initial_soc", "min_soc_frac": 0.41},
    {"action": "lower_min_power", "current_kw": 100, "suggested_kw": 50}
  ]
}
```

Lỗi phải **hữu ích**. "Không tìm được đường" là câu trả lời tệ; "khoảng cách giữa hai trạm
là 210 km, xe chỉ đi được 178 km ở điều kiện này, hãy khởi hành với ít nhất 41% pin" là
câu trả lời dùng được.

---

## 10. Chất lượng & validation

### Golden trips

Bộ chuyến đi thật với năng lượng tiêu thụ đã biết, lưu trong `tests/golden/`:

```yaml
- id: hanoi-danang-vf8-summer
  vehicle: vinfast-vf8-eco-2023
  route_polyline: "..."
  conditions: {temperature_c: 32, wind_mps: 3, load_kg: 150}
  actual_energy_kwh: 141.8
  actual_duration_s: 41400
  tolerance_pct: 5
  source: "Báo cáo cộng đồng, 2026-03"
```

CI chạy toàn bộ golden trips. Lệch quá `tolerance_pct` → fail. Đây là lá chắn chống việc
"tinh chỉnh" mô hình làm hỏng độ chính xác ở nơi khác.

### Property tests

```python
# Đối xứng: đi và về trên đường phẳng
assert energy(A→B) + energy(B→A) ≈ 2 * flat_energy(distance) ± 5%

# Đơn điệu: nặng hơn → tốn hơn
assert energy(mass=m1) < energy(mass=m2)  for m1 < m2

# Thêm lựa chọn không bao giờ làm tệ đi
assert plan(stations=S).duration <= plan(stations=S-{s}).duration

# Bất biến an toàn
assert all(leg.soc_p10 >= reserve for leg in plan.legs)
```

### Đo trên tập kiểm định

```
MAE, RMSE, MAPE cho kWh/100km
Sai số SOC khi đến (điểm %)
Phân tách theo: cao tốc / đô thị / miền núi / nóng / lạnh / mưa
```

Phân tách theo điều kiện quan trọng hơn con số tổng. Một mô hình MAE 1.5 tổng thể nhưng
sai 5.0 ở vùng núi lạnh là mô hình nguy hiểm.

---

## 11. Đường tiến hoá

Kiến trúc phải chịu được những thay đổi sau **mà không phải viết lại**:

```
Hôm nay                          Sau này
─────────────────────────────────────────────────────────────
Mô hình vật lý          →   Vật lý + ML trên phần dư
Rule-based risk         →   ML risk engine
Không telemetry         →   Kafka + hiệu chỉnh theo xe
Một xe                  →   Đội xe, tối ưu chung
Trạm tĩnh               →   Occupancy thời gian thực, mô hình xếp hàng
Một máy chủ             →   Kubernetes
```

Ba điểm mở rộng đã được thiết kế sẵn:

1. `EnergyModel` là Protocol → thêm cài đặt ML, so sánh A/B, không đụng planner.
2. `RiskEngine` là Protocol → thay rule bằng ML.
3. Adapter telemetry ghi vào `observed_trips` → chèn Kafka vào giữa mà không component
   nào phía sau biết.

**Điều KHÔNG được thay đổi:** ranh giới `core/` không I/O. Đây là thứ giữ cho hệ thống
test được và hiểu được khi nó lớn lên.

---

## 12. Vận hành

### Phát triển

```bash
docker compose up          # postgres+postgis, redis, osrm, api, web
make demo                  # chạy chuyến mẫu bằng fixture, không cần mạng
```

### Triển khai

Một VPS là đủ cho bản đầu:

```
nginx  →  FastAPI (uvicorn, 4 worker)
          ├── PostgreSQL + PostGIS
          ├── Redis
          └── OSRM (dữ liệu OSM khu vực, ~4 GB RAM cho một quốc gia)

Prometheus + Grafana + Loki   (tùy chọn)
```

### Chỉ số theo dõi

```
Ứng dụng    plan_requests_total, plan_duration_seconds{quantile},
            plan_infeasible_total, plan_stops_count
Dữ liệu     external_api_errors_total{source}, cache_hit_ratio{cache},
            station_data_staleness_days
Chất lượng  energy_prediction_error_kwh_per_100km, golden_trip_deviation_pct
```

`plan_infeasible_total` tăng đột biến là tín hiệu dữ liệu trạm có vấn đề, không phải
thuật toán có vấn đề — đây là loại insight mà chỉ số được chọn đúng mang lại.

---

## 13. Architecture Decision Records

Quyết định lớn ghi trong `docs/adr/NNNN-tieu-de.md`, format:
*Bối cảnh → Quyết định → Hệ quả → Phương án đã cân nhắc.*

Đã có:

| # | Quyết định | Lý do ngắn gọn |
|---|---|---|
| 0001 | Core thuần, không I/O | Test được ở mili-giây; tái dùng cho API/CLI/notebook |
| 0002 | Routing + charging là core, telemetry là tùy chọn | Contributor phải chạy được mà không cần xe thật |
| 0003 | Vật lý trước, ML sau | Vật lý ngoại suy an toàn; ML cần dữ liệu chưa có |
| 0004 | Labeling algorithm thay vì heuristic | Tập ứng viên đã lọc còn ~40 nút → giải chính xác được |
| 0005 | Chưa dùng Kafka | Luồng chính là request–response; Kafka giải vấn đề chưa tồn tại |
| 0006 | Mọi ước lượng có khoảng tin cậy | Ràng buộc an toàn phải tính trên kịch bản xấu, không phải trung bình |

Cần ADR mới: chọn Valhalla thay OSRM? mô hình xếp hàng ở trạm?
