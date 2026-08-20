# PRD — Voltrail

**Tối ưu tuyến đường và trạm sạc cho ô tô điện đi đường dài**

| | |
|---|---|
| Phiên bản | 0.1 (draft) |
| Trạng thái | Đề xuất |
| Giấy phép | Apache-2.0 (code) |
| Phạm vi tài liệu | Phase 1 — bản chạy được đầu tiên |

---

## 1. Vấn đề

Đi ô tô điện quãng ngắn trong thành phố đã là bài toán đã giải: sạc ở nhà, quãng đường
dư dả. **Đi đường dài thì không.** Người lái phải tự trả lời một chuỗi câu hỏi mà họ
không có đủ dữ liệu để trả lời:

* Với pin hiện tại, thời tiết này, tải này, tôi đi được bao xa **thật sự**?
* Trạm nào trên đường là trạm nên dừng — không phải trạm gần nhất, mà trạm làm **tổng
  thời gian chuyến đi ngắn nhất**?
* Sạc bao lâu là đủ? Sạc đầy có phải lúc nào cũng tốt?
* Nếu trạm đó hỏng hoặc kín chỗ thì sao?

Kết quả là hai loại hành vi đều tệ:

```
Lo lắng quá mức           →  sạc quá nhiều lần, sạc đến 100%, chuyến đi dài thêm 1–2 giờ
Tự tin quá mức            →  chết máy giữa đường, hoặc phải bò 40 km/h để về tới trạm
```

Các công cụ hiện có hoặc là closed-source, hoặc gắn chặt với một hãng xe, hoặc chỉ
hoạt động tốt ở Bắc Mỹ / Tây Âu. Không có nền tảng mở nào cho phép cộng đồng đóng góp
thông số xe, dữ liệu trạm địa phương, hoặc cải tiến thuật toán.

### Điều làm bài toán này khó (và thú vị)

Đây không phải bài toán tìm đường ngắn nhất. Nó là bài toán tìm đường **có ràng buộc
tài nguyên và điểm nạp lại tài nguyên phi tuyến**:

* Chi phí đi một cạnh phụ thuộc tốc độ, độ dốc, nhiệt độ, tải — không phải hằng số.
* Trạng thái không chỉ là "đang ở đâu" mà là "đang ở đâu **với bao nhiêu pin**".
* Thời gian sạc là hàm phi tuyến của SOC vào và SOC ra. Sạc 10→80% nhanh hơn 80→100%.
* Sạc thêm ở trạm này có thể cho phép bỏ qua trạm sau — đánh đổi không hiển nhiên.

---

## 2. Người dùng

### P1 — Người lái xe cá nhân đi đường dài (chính)

Có xe điện, sắp đi 300–800 km. Muốn biết trước: đi mấy tiếng, dừng mấy lần, dừng ở đâu.
Không quan tâm kỹ thuật, quan tâm **con số cuối cùng và mức độ đáng tin của nó**.

> "Hà Nội → Đà Nẵng, xe VF8, khởi hành 6h sáng. Mấy giờ tới, dừng ở đâu?"

### P2 — Lập trình viên / nhà nghiên cứu (chính, vì đây là OSS)

Muốn một engine tính năng lượng và routing dùng được như thư viện. Muốn chạy mô phỏng,
so sánh thuật toán, tích hợp vào hệ thống riêng.

> "Cho tôi một hàm nhận (xe, tuyến, thời tiết) trả về kWh, có test đàng hoàng."

### P3 — Người vận hành đội xe nhỏ (phụ, Phase 3)

5–50 xe. Muốn biết xe nào đủ pin cho chuyến nào. **Ngoài phạm vi Phase 1.**

### P4 — Cộng đồng đóng góp dữ liệu (bổ trợ)

Đóng góp thông số xe, đường cong sạc, xác minh trạm địa phương — đặc biệt ở những thị
trường mà dữ liệu quốc tế còn mỏng.

---

## 3. Mục tiêu và không phải mục tiêu

### Mục tiêu Phase 1

1. Lập được kế hoạch hành trình đầy đủ cho một chuyến đi bất kỳ trong vùng có dữ liệu
   trạm sạc, **chỉ cần: điểm đi, điểm đến, mẫu xe, SOC hiện tại**.
2. Mô hình năng lượng dựa trên vật lý, chính xác đủ để dùng thật, và **giải thích được**
   (nói rõ vì sao ra con số đó).
3. Kế hoạch tối ưu theo **tổng thời gian đến nơi**, không phải theo quãng đường.
4. Mọi kế hoạch đều đảm bảo SOC không xuống dưới ngưỡng dự trữ, có tính đến sai số.
5. Lồng ghép **thời điểm nghỉ của người lái** vào chính kế hoạch sạc — đây là điểm khác
   biệt: sạc và nghỉ nên là cùng một lần dừng bất cứ khi nào có thể.
6. Chạy được offline / bằng dữ liệu mẫu, để bất kỳ ai cũng thử được.

### KHÔNG phải mục tiêu Phase 1

```
- Điều phối đội xe, gán xe cho chuyến
- Đặt chỗ trạm sạc / thanh toán
- Xe máy điện, xe tải điện
- Ứng dụng di động native
- Dẫn đường turn-by-turn thời gian thực (chúng ta tạo kế hoạch, không thay Google Maps)
- Tự lái
- LLM assistant
- Deep learning cho mô hình năng lượng
- Kubernetes / multi-region
```

Những thứ này không bị loại vĩnh viễn — chúng bị loại **khỏi bản đầu tiên**, để bản đầu
tiên thực sự ra đời.

### Điều chỉnh quan trọng so với kế hoạch gốc

Kế hoạch ban đầu đặt **telemetry xe thật** làm Sprint 0 và coi routing là Phase 2.
Với một dự án open-source, thứ tự này phải đảo lại:

| | Kế hoạch gốc | PRD này |
|---|---|---|
| Điểm khởi đầu | Kết nối xe thật, lấy SOC | Engine năng lượng + routing thuần |
| Rào cản cho contributor | Cần xe điện + OEM API | Không cần gì, `make demo` |
| Nếu Sprint 0 thất bại | Cả dự án dừng | Không có rủi ro này |
| Telemetry | Nền tảng bắt buộc | Adapter tùy chọn (Mốc D) |
| Giá trị sau 4 tuần | Có một luồng dữ liệu | Có một sản phẩm chạy được |

Telemetry vẫn rất giá trị — nó là thứ biến ước lượng thành **hiệu chỉnh theo xe thật**.
Nhưng nó là *tầng cải thiện độ chính xác*, không phải *điều kiện tiên quyết*.

---

## 4. Trải nghiệm mục tiêu

### Đầu vào tối thiểu

```
Từ:        Hà Nội
Đến:       Đà Nẵng
Xe:        VinFast VF8 Eco (từ catalog cộng đồng)
SOC:       92%
Khởi hành: 06:00
```

### Đầu ra

```
┌─────────────────────────────────────────────────────────────┐
│  Hà Nội → Đà Nẵng          764 km                           │
│  Đến nơi 17:42  •  11h 42m  •  2 lần dừng  •  1.9 triệu đ  │
│                                                             │
│  06:00  Hà Nội                            SOC  92%          │
│         ↓  248 km  •  3h 05m  •  17.9 kWh/100km            │
│  09:05  Trạm Nghi Sơn (150 kW)            đến   34%         │
│         ⚡ sạc 26 phút → 80%   •  ☕ trùng giờ nghỉ          │
│         ↓  276 km  •  3h 28m  •  18.4 kWh/100km            │
│  12:59  Trạm Phong Nha (120 kW)           đến   21%         │
│         ⚡ sạc 34 phút → 85%   •  🍽 nghỉ trưa 30 phút       │
│         ↓  240 km  •  3h 09m  •  19.1 kWh/100km            │
│  17:42  Đà Nẵng                           đến   19%         │
│                                                             │
│  Độ tin cậy: CAO                                            │
│  SOC khi đến (khoảng 80%): 14% – 24%                        │
│  Phương án dự phòng nếu Phong Nha kín: Trạm Đồng Hới, +18′   │
└─────────────────────────────────────────────────────────────┘
```

### Vì sao lại thế này — hệ thống phải giải thích được

Bấm vào bất kỳ quyết định nào phải ra được lý do:

```
Vì sao dừng ở Nghi Sơn chứ không phải Ninh Bình (gần hơn 90 km)?

  Ninh Bình có công suất 60 kW → mất thêm 19 phút cho cùng lượng điện.
  Dừng Nghi Sơn khiến SOC khi đến trạm là 34%, nằm trong vùng
  đường cong sạc nhanh nhất của xe này.
  Nghi Sơn cũng rơi đúng mốc lái liên tục 3h05 → gộp được với giờ nghỉ.

Vì sao chỉ sạc đến 80%?

  Sạc 80→90% ở trạm này mất thêm 11 phút nhưng chỉ tiết kiệm 4 phút
  ở chặng sau. Không đáng.
```

---

## 5. Yêu cầu chức năng

Ký hiệu: **P0** = bắt buộc cho bản phát hành đầu, **P1** = nên có, **P2** = sau.

### F1 — Catalog xe (P0)

Thông số xe dưới dạng file YAML, cộng đồng đóng góp qua PR.

```yaml
id: vinfast-vf8-eco-2023
name: VinFast VF8 Eco (2023)
battery:
  nominal_capacity_kwh: 87.7
  usable_capacity_kwh: 82.0
  reserve_soc_frac: 0.10
physics:
  curb_mass_kg: 2350
  drag_coefficient: 0.31          # ước lượng, cần xác minh
  frontal_area_m2: 2.75
  rolling_resistance_coeff: 0.010
  drivetrain_efficiency: 0.90
  regen_efficiency: 0.70
auxiliary:
  base_power_kw: 0.5
  hvac_max_power_kw: 5.0
charging:
  max_dc_power_kw: 150
  max_ac_power_kw: 11
  connectors: [ccs2, type2]
  curve:                          # [soc_frac, power_kw]
    - [0.05, 120]
    - [0.30, 150]
    - [0.55, 110]
    - [0.80, 60]
    - [0.95, 25]
metadata:
  source: "Thông số nhà sản xuất + đo đạc cộng đồng"
  confidence: medium
  contributors: ["@username"]
```

**Chấp nhận:** ≥ 10 mẫu xe phổ biến khi phát hành. Schema có validation. Thiếu trường
optional thì dùng mặc định theo phân khúc xe, và **đánh dấu rõ là giá trị mặc định**.

### F2 — Mô hình tiêu hao năng lượng (P0)

Tính năng lượng cho từng đoạn đường từ vật lý, không từ hằng số "kWh/100km".

**Đầu vào:** hình học tuyến (khoảng cách, độ cao), tốc độ dự kiến, nhiệt độ ngoài, gió,
thông số xe, số người/tải.

**Đầu ra:** `kWh` cho đoạn, kèm phân rã: lăn / khí động / độ dốc / phụ tải / regen.

**Chấp nhận:**
* Trên bộ golden trips, MAE < **2.0 kWh/100km**; sau khi có dữ liệu thật, mục tiêu < 1.0.
* Phân rã năng lượng luôn cộng lại đúng bằng tổng (bất biến, có property test).
* Nhiệt độ −10°C phải cho tiêu hao cao hơn 20°C ít nhất 20% ở cùng điều kiện khác.
* Chạy < 1 ms cho một đoạn 10 km.

### F3 — Mô hình thời gian sạc (P0)

Tính thời gian sạc từ SOC_a → SOC_b tại một trạm cụ thể.

Công suất thực = `min(công suất trạm, công suất tối đa của xe, đường cong theo SOC)`,
có hệ số suy giảm theo nhiệt độ pin.

**Chấp nhận:**
* Không bao giờ tính tuyến tính.
* Sạc 10→80% phải nhanh hơn 30→100% cùng lượng kWh (property test).
* Có tính thời gian cắm/rút cố định (mặc định 3 phút mỗi lần dừng).

### F4 — Dữ liệu trạm sạc (P0)

Nạp trạm từ nguồn mở, chuẩn hoá về một schema, lưu vào PostGIS, cache 24h.

Mỗi trạm cần: vị trí, loại đầu nối, công suất mỗi cổng, số cổng, nhà vận hành, tình
trạng, lần xác minh gần nhất, tiện ích xung quanh (WC, đồ ăn — quan trọng cho chỗ nghỉ).

**Chấp nhận:**
* Lọc bỏ trạm có trạng thái đã đóng/không hoạt động.
* Mỗi trạm có `data_confidence` ∈ {high, medium, low}.
* Truy vấn theo bán kính < 50 ms (p95).
* Có attribution nguồn dữ liệu hiển thị trong UI.

### F5 — Engine lập kế hoạch sạc (P0) — **trái tim của dự án**

Nhận điểm đi/đến/SOC, trả về chuỗi trạm dừng tối ưu.

**Hàm mục tiêu (mặc định):** tối thiểu tổng thời gian đến nơi
= thời gian lái + thời gian sạc + thời gian chờ + thời gian nghỉ bắt buộc.

**Ràng buộc:**
* SOC ≥ reserve tại mọi điểm trên tuyến, tính theo **p10** (kịch bản xấu), không theo p50.
* Đầu nối tương thích.
* Công suất tối thiểu (người dùng chọn được).
* Số lần dừng tối đa (tùy chọn).

**Chấp nhận:**
* Chuyến 500 km, ~40 trạm ứng viên → p95 < 2s.
* Kết quả tối ưu trong tập ứng viên (verify bằng brute-force trên bài toán nhỏ).
* Không tìm được phương án khả thi → trả lỗi rõ ràng kèm **lý do** ("khoảng cách giữa
  trạm X và Y là 210 km, xe chỉ đi được 180 km ở điều kiện này"), không im lặng trả rỗng.
* Trả kèm **1–2 phương án thay thế** (ít dừng hơn / rẻ hơn / an toàn hơn).

### F6 — Nghỉ ngơi & mệt mỏi người lái (P0)

Lồng quy tắc nghỉ vào kế hoạch, không tách rời.

```
Mặc định (chỉnh được):
  lái liên tục tối đa      2h 30m  →  nghỉ ≥ 15 phút
  lái tích luỹ trong ngày  8h      →  cảnh báo mạnh
  nghỉ trưa                        →  nếu chuyến qua 11:30–13:30
```

**Chấp nhận:** engine **ưu tiên gộp** điểm nghỉ với điểm sạc. Khi không thể gộp, phải nói
rõ vì sao. Nếu nghỉ đủ dài, thời gian sạc "miễn phí" trong lúc nghỉ không được tính vào
tổng thời gian tăng thêm.

### F7 — Ước lượng có khoảng tin cậy & risk engine (P0)

Không trả một con số. Trả `p10 / p50 / p90` cho SOC tại mỗi điểm.

Trạng thái rủi ro:

```
SAFE                  SOC p10 khi đến trạm kế ≥ reserve + 10 điểm %
AWARE                 SOC p10 ≥ reserve, nhưng biên hẹp
REST_RECOMMENDED      chạm ngưỡng thời gian lái, hoặc tiêu hao đang tăng bất thường
CHARGING_RECOMMENDED  SOC p10 sẽ chạm reserve trước trạm kế
CRITICAL              không có trạm nào tới được với SOC hiện tại
```

**Chấp nhận:** risk engine là một **module riêng, đầu vào là các tín hiệu độc lập**, để
sau này thay bằng ML mà không phải viết lại phần còn lại. Ngưỡng nằm trong config, không
hard-code.

### F8 — HTTP API (P0)

```http
POST /v1/plan                       # lập kế hoạch
POST /v1/replan                     # cập nhật khi đang đi
POST /v1/energy/estimate            # chỉ tính năng lượng cho một tuyến
GET  /v1/vehicles                   # catalog xe
GET  /v1/vehicles/{id}
GET  /v1/stations?bbox=&connector=&min_power_kw=
GET  /healthz  /metrics
```

**Chấp nhận:** OpenAPI schema tự sinh. Mọi lỗi có mã lỗi ổn định và thông điệp đọc được.

### F9 — Giao diện web (P0)

Một trang: form nhập → bản đồ + timeline hành trình → panel giải thích.

**Chấp nhận:** dùng được trên mobile. Không cần đăng nhập. Có attribution dữ liệu.

### F10 — CLI (P1)

```bash
voltrail plan --from "Hà Nội" --to "Đà Nẵng" --vehicle vf8-eco --soc 92
voltrail simulate --trips 100 --seed 42 --out trips.parquet
```

### F11 — Simulator (P0 — điều kiện để `make demo` chạy được)

Sinh chuyến đi tổng hợp: telemetry theo tuyến thật, có nhiễu, có bias theo tài xế,
có sự kiện (kẹt xe, mưa, sạc). Dùng để dev, test, và tạo dataset huấn luyện ban đầu.

**Chấp nhận:** có seed → tái lập được. Dữ liệu sinh ra **luôn được đánh dấu synthetic**.

### F12 — Telemetry adapter (P1, tùy chọn)

Nhận dữ liệu xe thật để hiệu chỉnh mô hình theo từng xe.

```
Base prediction  18.5 kWh/100km
Quan sát thực    20.1
Hệ số hiệu chỉnh +8.6%   (EMA, có giới hạn ±25%)
```

**Chấp nhận:** hệ thống **chạy đầy đủ khi không có adapter nào**. Có adapter thì độ chính
xác tăng. Không bao giờ là điều kiện bắt buộc.

### F13 — Hồ sơ xe & tài xế (P2)

Học dần từ lịch sử: xe này thường tốn hơn chuẩn bao nhiêu %, tài xế này chạy nhanh hay chậm.

### F14 — ML thay thế mô hình vật lý (P2)

Chỉ khi đã có ≥ 500 chuyến thật. Gradient boosting trên phần **dư** (residual) của mô
hình vật lý, không thay thế toàn bộ mô hình vật lý. Lý do: mô hình vật lý ngoại suy an
toàn ở điều kiện chưa gặp; ML thì không.

---

## 6. Yêu cầu phi chức năng

| | Yêu cầu |
|---|---|
| Hiệu năng | `/v1/plan` p95 < 2s; energy model < 1ms/leg |
| Khả dụng | Một nguồn dữ liệu ngoài chết → degrade, không sập |
| Chính xác | Energy MAE < 2 kWh/100km; sai số SOC khi đến < 5 điểm % |
| Riêng tư | Không lưu lịch sử hành trình khi chưa được đồng ý; không log GPS thô |
| Vận hành | `docker compose up` là đủ để chạy full stack |
| Quốc tế hoá | Đơn vị metric/imperial; UI i18n-ready; không hard-code tiếng Anh |
| Khả năng đóng góp | Setup < 15 phút, test suite < 60 giây |

---

## 7. Lộ trình — 4 mốc

Mỗi mốc phải **tự nó đã có giá trị**. Không mốc nào là "nền móng chưa dùng được".

### Mốc A — Energy Engine *(≈ 3 tuần)*

```
[ ] Schema xe + 10 xe trong catalog
[ ] Mô hình năng lượng vật lý
[ ] Adapter routing (OSRM) + elevation
[ ] Adapter thời tiết
[ ] Bộ golden trips + khung validation
[ ] CLI: voltrail energy --from --to --vehicle
```

**Xong khi:** trả lời được *"Chuyến này tốn bao nhiêu kWh?"* với sai số đo được.
**Đã dùng được:** như một thư viện Python độc lập. Đây là thứ có thể phát hành lên PyPI ngay.

### Mốc B — Charging Planner *(≈ 4 tuần)*

```
[ ] Nạp + chuẩn hoá dữ liệu trạm, PostGIS
[ ] Mô hình đường cong sạc
[ ] Chọn tập trạm ứng viên theo hành lang tuyến
[ ] Thuật toán labeling với charging function
[ ] Ràng buộc nghỉ ngơi
[ ] HTTP API
```

**Xong khi:** trả lời được *"Dừng ở đâu, sạc bao lâu?"* cho một chuyến bất kỳ.
**Đây là mốc quan trọng nhất của dự án.**

### Mốc C — Sản phẩm *(≈ 3 tuần)*

```
[ ] Web UI + bản đồ + timeline
[ ] Panel giải thích quyết định
[ ] Khoảng tin cậy + risk engine
[ ] Phương án dự phòng khi trạm hỏng
[ ] Endpoint re-plan
[ ] Docs, README, deploy demo công khai
```

**Xong khi:** người không biết code cũng dùng được. → **Phát hành v0.1.0**

### Mốc D — Học từ thực tế *(liên tục)*

```
[ ] Telemetry adapter (OBD / MQTT / OEM tùy chọn)
[ ] Hiệu chỉnh online theo từng xe
[ ] Hồ sơ xe & tài xế
[ ] Cơ chế cộng đồng báo cáo chuyến thật để cải thiện mô hình
[ ] ML trên phần dư
```

Đây là nơi ý tưởng telemetry của kế hoạch gốc quay lại — nhưng ở đúng vị trí của nó:
**tầng cải thiện, không phải tầng nền.**

---

## 8. Đo lường thành công

### Chất lượng kỹ thuật

```
Energy MAE                    < 2.0 kWh/100km  →  < 1.0
Sai số SOC khi đến            < 5 điểm %
Kế hoạch không khả thi lọt ra  0        ← chỉ số quan trọng nhất
Thời gian kế hoạch vs tối ưu   trong 5%
p95 latency /v1/plan           < 2s
```

**"Kế hoạch không khả thi lọt ra" là chỉ số quan trọng nhất.** Một kế hoạch chậm hơn 10%
là phiền. Một kế hoạch làm người ta chết máy giữa đèo là mất niềm tin vĩnh viễn.

### Sức khoẻ dự án OSS

```
Số mẫu xe được cộng đồng đóng góp
Số contributor ngoài maintainer
Thời gian setup của người mới      < 15 phút
Test suite                          < 60 giây
```

---

## 9. Rủi ro

| Rủi ro | Mức | Xử lý |
|---|---|---|
| Dữ liệu trạm sai/lỗi thời | Cao | Luôn có phương án dự phòng; hiển thị `data_confidence`; cho phép cộng đồng báo lỗi |
| Đường cong sạc không công bố | Cao | Bắt đầu bằng đường cong mẫu theo phân khúc; thu thập dữ liệu cộng đồng |
| Thông số khí động (Cd, A) không chính xác | Trung bình | Đánh dấu mức tin cậy; hiệu chỉnh ngược từ chuyến thật |
| Giấy phép dữ liệu bị hiểu sai | Trung bình | Ghi rõ từng nguồn trong `docs/DATA_SOURCES.md`, rà lại trước mỗi release |
| Phạm vi phình to | Cao | Danh sách "không phải mục tiêu" ở mục 3 là ràng buộc, không phải gợi ý |
| Kỳ vọng độ chính xác | Trung bình | Luôn hiển thị khoảng, không bao giờ hiển thị con số trần |
| Chi phí hosting bản demo | Thấp | Rate limit; hướng dẫn self-host là con đường chính |

---

## 10. Câu hỏi còn mở

1. Vùng địa lý nào là ưu tiên đầu tiên? Việt Nam có dữ liệu trạm thưa hơn nhưng nhu cầu
   rõ ràng hơn; châu Âu có dữ liệu tốt nhất để kiểm chứng thuật toán. Đề xuất: **phát
   triển và validate trên châu Âu, ra mắt kèm hỗ trợ Việt Nam đầy đủ.**
2. Có mô hình hoá thời gian xếp hàng ở trạm không? Cần dữ liệu occupancy — có thể để Phase 2.
3. Chọn Valhalla thay OSRM? Valhalla có elevation và costing model tích hợp sẵn.
   → Cần một ADR, xem `docs/adr/`.
4. Cơ chế nào để cộng đồng đóng góp chuyến thật mà vẫn bảo vệ riêng tư?
