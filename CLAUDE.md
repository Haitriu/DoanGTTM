# CLAUDE.md

Hướng dẫn vận hành cho Claude Code (và mọi AI coding agent) khi làm việc trong repo này.
File này là **nguồn chân lý về quy tắc kỹ thuật**. Khi có mâu thuẫn giữa file này và
thói quen chung, **file này thắng**.

> Đọc kèm: `PRD.md` (làm cái gì, cho ai) và `ARCHITECTURE.md` (làm như thế nào).

---

## 1. Dự án là gì

**Voltrail** — công cụ mã nguồn mở lập kế hoạch hành trình đường dài cho ô tô điện:
tìm tuyến đường + chuỗi trạm sạc + thời điểm nghỉ sao cho **tổng thời gian đi ngắn nhất**
mà **không bao giờ hết pin giữa đường**.

Tên `voltrail` là placeholder — nếu đổi tên, đổi ở `pyproject.toml`, `README.md` và file này.

Ba câu trả lời hệ thống phải đưa ra:

```
1. Đi đường nào?
2. Sạc ở đâu, sạc bao lâu, sạc đến bao nhiêu %?
3. Khi nào phải nghỉ (mệt / pin / rủi ro)?
```

### Nguyên tắc số 1 của repo

> **Người mới clone repo về phải chạy được kết quả thật trong 5 phút, không cần xe điện,
> không cần API key trả phí.**

Mọi quyết định kỹ thuật phải bảo vệ nguyên tắc này. Nếu một feature bắt buộc phải có
xe thật hoặc tài khoản trả phí mới chạy được, nó phải nằm sau một adapter tùy chọn,
và phải có fallback bằng simulator/fixture.

---

## 2. Bố cục repo

```
voltrail/
├── CLAUDE.md              # file này
├── PRD.md
├── ARCHITECTURE.md
├── README.md
├── LICENSE                # Apache-2.0
├── pyproject.toml         # uv workspace root
├── Makefile
├── docker-compose.yml
│
├── packages/
│   ├── core/              # DOMAIN THUẦN — không I/O, không network, không DB
│   │   └── voltrail_core/
│   │       ├── models/        # dataclass/pydantic: Vehicle, Station, Leg, Plan...
│   │       ├── energy/        # mô hình tiêu hao năng lượng (vật lý)
│   │       ├── charging/      # charging curve, thời gian sạc
│   │       ├── routing/       # thuật toán chọn trạm + labeling
│   │       ├── rest/          # quy tắc nghỉ / mệt mỏi
│   │       └── risk/          # risk engine
│   │
│   ├── adapters/          # MỌI THỨ CHẠM RA NGOÀI
│   │   └── voltrail_adapters/
│   │       ├── routing/       # OSRM, Valhalla
│   │       ├── stations/      # OpenChargeMap, NREL AFDC, OCPI
│   │       ├── weather/       # Open-Meteo
│   │       ├── elevation/     # SRTM / Open-Elevation
│   │       └── telemetry/     # OPTIONAL: OBD, OEM API, MQTT
│   │
│   └── simulator/         # sinh chuyến đi giả để dev/test/demo
│
├── apps/
│   ├── api/               # FastAPI
│   ├── cli/               # `voltrail plan --from ... --to ...`
│   └── web/               # Next.js + MapLibre
│
├── data/
│   ├── vehicles/          # thông số xe dạng YAML (đóng góp cộng đồng)
│   └── fixtures/          # response API đã ghi lại, dùng cho test
│
├── tests/
├── notebooks/             # phân tích, KHÔNG được import từ code production
└── docs/adr/              # architecture decision records
```

### Quy tắc phụ thuộc — BẮT BUỘC

```
apps/  ──►  adapters/  ──►  core/
                 │              ▲
                 └──────────────┘   (chỉ qua interface do core định nghĩa)
```

* `core/` **không được** import `requests`, `httpx`, `sqlalchemy`, `redis`, `fastapi`.
* `core/` chỉ dùng stdlib + `numpy` + `pydantic`.
* Có một test CI thực thi luật này (`tests/test_architecture.py`). Đừng sửa test đó để
  code chạy được — hãy sửa code.

Lý do: thuật toán năng lượng và routing phải test được ở tốc độ mili-giây, không cần
network, và phải tái sử dụng được cho cả API lẫn CLI lẫn notebook.

---

## 3. Lệnh thường dùng

```bash
make setup          # uv sync + cài pre-commit hooks
make dev            # docker-compose up (postgres+postgis, redis, osrm) + api reload
make test           # pytest, không network
make test-int       # test tích hợp, CÓ network — không chạy trong CI mặc định
make lint           # ruff check + ruff format --check + mypy
make fmt            # ruff format + ruff check --fix
make demo           # chạy 1 chuyến demo Hà Nội → Đà Nẵng bằng dữ liệu fixture
```

Trước khi commit, luôn: `make fmt && make lint && make test`.

Nếu một lệnh trong Makefile không tồn tại → tạo nó, đừng hướng dẫn người dùng gõ lệnh dài.

---

## 4. Chuẩn code

### Ngôn ngữ & công cụ

| Hạng mục | Lựa chọn |
|---|---|
| Python | 3.12+ |
| Quản lý gói | `uv` (workspace) |
| Lint + format | `ruff` (line length 100) |
| Type check | `mypy --strict` cho `packages/core`, `--no-strict-optional` cho phần còn lại |
| Test | `pytest`, `pytest-cov`, `hypothesis` cho thuật toán |
| Validation | `pydantic` v2 |
| DB | `SQLAlchemy 2.0` (style mới), `alembic` |
| Frontend | TypeScript strict, Next.js App Router, MapLibre GL |

### Quy tắc viết code

* **Type hint đầy đủ** cho mọi hàm public. Không dùng `Any` trừ khi có comment giải thích.
* **Không dùng số ma thuật.** Mọi hằng số vật lý nằm trong `core/constants.py` với đơn vị
  trong tên: `AIR_DENSITY_KG_PER_M3 = 1.225`.
* **Hàm thuần trước, side effect sau.** Logic tính toán tách khỏi logic I/O.
* Không viết class khi một hàm là đủ.
* Docstring theo Google style, chỉ cho hàm public. Không viết docstring lặp lại tên hàm.
* Comment giải thích **tại sao**, không giải thích **cái gì**.

### Đặt tên — quy tắc đơn vị (QUAN TRỌNG NHẤT)

**Mọi biến số có đơn vị vật lý phải mang đơn vị trong tên.** Đây là nguồn bug số 1 trong
loại hệ thống này.

```python
# ĐÚNG
distance_m: float
distance_km: float
speed_mps: float
speed_kmh: float
energy_kwh: float
power_kw: float
duration_s: int
soc_frac: float          # 0.0 – 1.0
soc_pct: float           # 0 – 100
consumption_kwh_per_100km: float
temperature_c: float

# SAI
distance, speed, energy, soc, temp
```

### Đơn vị nội bộ chuẩn (SI)

Bên trong `core/`, **luôn dùng SI**. Chuyển đổi chỉ xảy ra ở biên (API request/response,
UI, parser dữ liệu ngoài).

```
Khoảng cách   → mét (m)
Tốc độ        → m/s
Thời gian     → giây (s)
Năng lượng    → kWh   (ngoại lệ có chủ đích: cả ngành EV dùng kWh)
Công suất     → kW    (ngoại lệ có chủ đích)
SOC           → phân số 0.0–1.0
Nhiệt độ      → °C
Khối lượng    → kg
Độ dốc        → tỉ lệ (0.06 = 6%), KHÔNG phải độ
```

### Toạ độ

* Bên trong hệ thống + PostGIS + GeoJSON: **`(lon, lat)`**
* API công khai và UI: **`{"lat": ..., "lon": ...}`** dạng object có tên, không dùng tuple.
* Không bao giờ truyền tuple toạ độ trần qua ranh giới module. Dùng `Coordinate` model.
* SRID mặc định: `4326`. Tính khoảng cách dùng `geography` hoặc chuyển sang lưới mét,
  không tính Euclid trên độ.

### Thời gian

* Mọi `datetime` là **UTC và tz-aware**. `datetime.now(UTC)`, không dùng `utcnow()`.
* Lưu DB dạng `TIMESTAMPTZ`.
* Chỉ chuyển sang giờ địa phương ở tầng hiển thị.

---

## 5. Bất biến của miền nghiệp vụ (domain invariants)

Đây là những điều **không bao giờ được vi phạm**. Nếu code có thể vi phạm, phải có
assertion hoặc validation chặn lại.

1. **SOC không bao giờ xuống dưới `reserve_soc_frac`** trong bất kỳ kế hoạch nào được
   trả về. Mặc định `0.10`. Kế hoạch vi phạm → không phải kế hoạch, phải trả lỗi
   `NoFeasiblePlanError`.

2. **Dùng `usable_capacity_kwh`, không dùng `nominal_capacity_kwh`.** Xe điện luôn có
   vùng đệm không dùng được. Nếu code nào đó tính năng lượng từ dung lượng danh nghĩa,
   đó là bug.

3. **Đường cong sạc không tuyến tính.** Không bao giờ tính thời gian sạc bằng
   `energy / max_power`. Luôn tích phân qua `ChargingCurve`. Sạc từ 80%→100% có thể lâu
   hơn 10%→80%.

4. **Sạc mặc định dừng ở 80%** trừ khi chặng tiếp theo bắt buộc phải cao hơn. Sạc lên
   100% gần như luôn là quyết định tệ về tổng thời gian.

5. **Năng lượng có thể âm** (khi xuống dốc, có regen), nhưng **SOC không bao giờ vượt
   `1.0`** dù regen nhiều đến đâu.

6. **Mọi ước lượng phải có khoảng tin cậy.** Trả `RangeEstimate(p10, p50, p90)`, không
   trả một con số trần. Risk engine phụ thuộc vào độ rộng khoảng này.

7. **Thời tiết lạnh làm giảm cả dung lượng khả dụng lẫn hiệu suất.** Không được bỏ qua
   `temperature_c` trong mô hình năng lượng.

8. **Một trạm sạc "có trên bản đồ" ≠ "dùng được".** Luôn mang theo
   `data_confidence` và `last_verified_at`. Không bao giờ lập kế hoạch mà chặng cuối
   phụ thuộc vào đúng một trạm chưa xác minh — phải có phương án dự phòng.

9. **Không bao giờ hiển thị cho người dùng một tuyến đường mà hệ thống không tự tin.**
   Thà nói "không tìm được phương án an toàn" còn hơn đưa ra kế hoạch làm người ta chết
   máy giữa đèo.

---

## 6. Testing

### Ba tầng

| Tầng | Vị trí | Đặc điểm |
|---|---|---|
| Unit | `tests/unit/` | Thuần, < 1ms/test, **không network, không DB** |
| Property | `tests/property/` | `hypothesis`, kiểm tra bất biến toán học |
| Integration | `tests/integration/` | `@pytest.mark.integration`, có network, không chạy CI mặc định |

### Quy tắc

* **Test không được gọi mạng.** Dùng fixture đã ghi trong `data/fixtures/`. Nếu cần
  fixture mới, thêm script `scripts/record_fixture.py` để ghi lại một cách tái lập được.
* Mỗi thuật toán trong `core/` phải có ít nhất một **property test**:
  * năng lượng đi A→B→A trên đường phẳng ≈ 2× năng lượng A→B (sai số < 5%)
  * thêm một trạm sạc vào tập ứng viên không bao giờ làm kế hoạch tối ưu **tệ đi**
  * tăng khối lượng xe không bao giờ làm giảm năng lượng tiêu thụ
  * SOC trong mọi kế hoạch trả về luôn ≥ reserve
* **Bug fix phải kèm regression test.** Test trước, fix sau.
* Có bộ **golden trips** trong `tests/golden/`: các chuyến đi thật đã biết kết quả.
  Thay đổi mô hình năng lượng làm lệch golden trip > 3% → CI fail, buộc phải giải thích.

Ngưỡng coverage: `packages/core` ≥ 85%. Phần còn lại không đặt ngưỡng cứng.

---

## 7. Xử lý dữ liệu ngoài

Mọi nguồn dữ liệu bên ngoài đều **không đáng tin**. Adapter phải:

1. Validate bằng pydantic ngay tại biên. Dữ liệu sai schema → bỏ, ghi log, **không crash**.
2. Có timeout (mặc định 5s) và retry với exponential backoff (tối đa 3 lần).
3. Có cache. Trạm sạc: TTL 24h. Thời tiết: TTL 1h. Elevation: cache vĩnh viễn (địa hình
   không đổi).
4. Có **circuit breaker**: nguồn hỏng thì degrade, không sập cả hệ thống.
5. Không bao giờ để API key trong code. Chỉ qua biến môi trường, khai báo trong
   `.env.example`.

### Về giấy phép dữ liệu — ĐỌC KỸ

Đây là dự án open-source, việc dùng sai dữ liệu là rủi ro pháp lý thật.

* Dữ liệu OpenStreetMap: **ODbL** — bắt buộc ghi nguồn, và có điều khoản share-alike với
  derivative database.
* Open Charge Map, NREL AFDC, Open-Meteo: mỗi nguồn có điều khoản riêng, có nguồn giới
  hạn mục đích thương mại.
* **Trước khi thêm bất kỳ nguồn dữ liệu mới nào**, phải: kiểm tra giấy phép hiện hành trên
  trang chính thức, ghi vào `docs/DATA_SOURCES.md`, và thêm attribution vào UI.
* **Không commit dữ liệu bulk từ nguồn ngoài vào git.** Chỉ commit fixture nhỏ dùng cho test.

---

## 8. Git & quy trình

### Branch

```
main            # luôn deploy được
feat/<slug>
fix/<slug>
docs/<slug>
```

### Commit — Conventional Commits, viết bằng tiếng Anh

```
feat(routing): add charging-function labeling algorithm
fix(energy): use usable capacity instead of nominal
perf(stations): cache OCM responses for 24h
docs(prd): clarify Milestone B acceptance criteria
```

* Commit nhỏ, một chủ đề một commit.
* **Không** thêm "Generated by AI" hay co-author trailer trừ khi maintainer yêu cầu.
* Không commit: `.env`, dump dữ liệu, file model `.pkl` (dùng MLflow/artifact store),
  `node_modules`, notebook đã chạy còn output nặng.

### PR

Mỗi PR phải trả lời được: *thay đổi gì, tại sao, đã test thế nào, có ảnh hưởng golden
trips không.* Template ở `.github/pull_request_template.md`.

---

## 9. Hành vi mong đợi của agent

### LÀM

* **Đọc `ARCHITECTURE.md` trước khi thêm component mới.** Nếu thay đổi mâu thuẫn với nó,
  viết một ADR mới trong `docs/adr/` chứ đừng lặng lẽ làm khác đi.
* Sửa **nguyên nhân gốc**, không vá triệu chứng.
* Khi không chắc về một con số vật lý (Cd, C_rr, hiệu suất drivetrain), **nói rõ là ước
  lượng** và ghi nguồn trong comment. Đừng bịa số rồi trình bày như sự thật.
* Khi một yêu cầu mơ hồ về mặt nghiệp vụ (ví dụ: "tối ưu" theo thời gian hay theo chi
  phí?), hỏi lại thay vì đoán.
* Ưu tiên thư viện đã có trong repo hơn là thêm dependency mới.

### KHÔNG LÀM

* **Không thêm dependency mới** vào `core/` mà không có lý do được ghi trong PR.
* **Không tự ý đổi cấu trúc thư mục.**
* **Không viết mock data trông như dữ liệu thật.** Nếu chưa có nguồn thật, dùng
  `simulator/` và đặt tên rõ ràng là synthetic.
* **Không sửa test cho pass.** Test fail nghĩa là code sai hoặc test sai — phải xác định
  cái nào trước khi sửa.
* **Không đưa ML vào khi rule-based còn chưa chạy.** Xem Mốc trong `PRD.md`.
* **Không tối ưu hoá sớm.** Đo trước bằng `make bench`, tối ưu sau.
* Không tạo file `.md` tổng kết công việc trừ khi được yêu cầu.

### Khi bắt đầu một task

1. Xác định thay đổi thuộc tầng nào: `core` / `adapters` / `apps`.
2. Nếu chạm `core`: viết test trước.
3. Nếu chạm thuật toán routing hoặc năng lượng: chạy `make test-golden` trước và sau.
4. Nếu thêm nguồn dữ liệu: cập nhật `docs/DATA_SOURCES.md`.

---

## 10. Bẫy đã biết

Ghi lại để không mắc lại. Thêm vào đây khi phát hiện bẫy mới.

* **Toạ độ đảo chiều.** OSRM nhận `lon,lat`. Leaflet nhận `lat,lon`. Đây là bug kinh điển,
  và nó âm thầm — kết quả vẫn ra route, chỉ là sai nước.
* **Độ dốc từ dữ liệu elevation rất nhiễu.** Phải làm mượt trên cửa sổ ≥ 100m trước khi
  đưa vào mô hình năng lượng, nếu không tiêu hao sẽ dao động phi vật lý.
* **SOC báo từ xe bị trễ và bị làm tròn.** Nhiều xe chỉ báo bước 1%. Đừng tính tiêu hao
  tức thời từ hiệu hai lần đọc SOC liên tiếp — dùng cửa sổ trượt ≥ 5 km.
* **Công suất sạc thực tế phụ thuộc cả trạm lẫn xe lẫn nhiệt độ pin.** Trạm 150kW không
  có nghĩa xe sẽ nhận 150kW. Luôn lấy `min(station_power, vehicle_max_ac_or_dc, curve(soc))`.
* **Trạm sạc chia sẻ công suất.** Một trụ 350kW có 2 cổng có thể chỉ cho 175kW mỗi cổng
  khi cả hai đang cắm.
* **Múi giờ khi trip qua biên giới.** Luôn tính bằng UTC, chỉ format ở cuối.
* **Open Charge Map trả về cả trạm đã đóng cửa.** Phải lọc theo `StatusType`.

---

## 11. Bảo mật

* Không log toàn bộ toạ độ GPS. Chỉ log ở mức grid ~1km khi debug, xoá sau 7 ngày.
* Không log VIN, không log thông tin định danh xe ra stdout.
* Không đưa `vehicle_id` nội bộ ra frontend — dùng ID công khai riêng.
* Mọi endpoint ghi dữ liệu đều phải kiểm tra quyền sở hữu xe.
* Dependency scan trong CI (`pip-audit`, `npm audit`).

---

## 12. Hiệu năng — ngân sách

Vi phạm ngân sách là bug, không phải "cần cải thiện sau".

```
POST /v1/plan  (chuyến 500 km, ~40 trạm ứng viên)   p95 < 2.0 s
Mô hình năng lượng, 1 leg 10 km                      < 1 ms
Truy vấn trạm trong bán kính 20 km (PostGIS)         p95 < 50 ms
Re-plan khi đang di chuyển                           p95 < 800 ms
```

---

## 13. Định nghĩa "Xong"

Một task chỉ xong khi:

- [ ] Code có type hint đầy đủ, `make lint` sạch
- [ ] Có test, `make test` xanh
- [ ] Golden trips không lệch quá ngưỡng, hoặc lệch có giải thích trong PR
- [ ] Đơn vị trong tên biến đúng chuẩn mục 4
- [ ] Không vi phạm bất biến ở mục 5
- [ ] Tài liệu liên quan (`PRD.md` / `ARCHITECTURE.md` / ADR) đã cập nhật nếu cần
- [ ] Không thêm secret, không thêm dữ liệu bulk vào git
