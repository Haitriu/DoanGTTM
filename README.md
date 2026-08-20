# Voltrail

**Tối ưu tuyến đường và trạm sạc cho ô tô điện đi đường dài**

Voltrail là công cụ mã nguồn mở lập kế hoạch hành trình đường dài cho ô tô điện. 
Hệ thống giải quyết bài toán: tìm tuyến đường + chuỗi trạm sạc + thời điểm nghỉ sao cho **tổng thời gian đi ngắn nhất** mà **không bao giờ hết pin giữa đường**.

> **Mục tiêu:** Người dùng clone repo về phải chạy được kết quả thật trong 5 phút, không cần xe điện, không cần API key trả phí.

---

## 🚀 Cài đặt & Khởi chạy (Phát triển)

Dự án sử dụng `uv` để quản lý môi trường và package siêu tốc.

```bash
# 1. Cài đặt các dependencies và setup hooks
make setup

# 2. Khởi chạy các dịch vụ nền (PostGIS, Redis, OSRM) và API
make dev

# 3. Chạy toàn bộ tests (không cần internet)
make test
```

---

## 🗺️ Lộ trình triển khai & Tiến độ (Roadmap)

Dưới đây là tiến độ chi tiết của các mốc phát triển (Phases).

### 🏁 PHASE 0 — Khởi tạo dự án
- [x] 0.1 Cấu trúc repo & tooling
  - [x] Tạo `pyproject.toml`
  - [x] Tạo `Makefile`
  - [x] Tạo `.env.example`
  - [x] Tạo `.pre-commit-config.yaml`
  - [x] Tạo `docker-compose.yml`
  - [x] Tạo `tests/test_architecture.py`
- [x] 0.2 CI/CD
  - [x] Tạo `.github/workflows/ci.yml`
  - [x] Tạo `.github/pull_request_template.md`

### 🏁 PHASE 1 — Core Models & Energy Engine (Mốc A)
*Mục tiêu: Trả lời được câu hỏi "Chuyến này tốn bao nhiêu kWh?" với sai số được kiểm soát.*
- [x] 1.1 Domain Models
- [x] 1.2 Energy Model (Tính toán tiêu hao vật lý)
- [x] 1.3 Charging Model (Đường cong sạc & tính thời gian)
- [x] 1.4 Vehicle Catalog (Khai báo mẫu xe)
- [x] 1.5 Routing Adapter Interface
- [x] 1.6 OSRM Adapter
- [x] 1.7 CLI — Bản chạy thử Mốc A
- [x] 1.8 Golden Trips & Validation (Kiểm định)

### 🏁 PHASE 2 — Charging Planner (Mốc B)
*Mục tiêu: Trả lời được câu hỏi "Dừng ở đâu, sạc bao lâu?" bằng thuật toán tối ưu (Labeling algorithm).*
- [x] 2.1 Database Schema (PostGIS)
- [x] 2.2 Trạm sạc Adapter (Open Charge Map)
- [x] 2.3 Thời tiết Adapter (Open-Meteo)
- [x] 2.4 Thuật toán Planning & Xây dựng đồ thị
- [x] 2.5 Quy tắc nghỉ ngơi & Lái xe an toàn
- [x] 2.6 Risk Engine (Cảnh báo rủi ro)
- [x] 2.7 REST HTTP API (FastAPI)

### 🏁 PHASE 3 — Sản phẩm Web (Mốc C)
*Mục tiêu: Giao diện hoàn chỉnh cho người dùng cuối.*
- [x] 3.1 Web UI (Next.js/Vite + MapLibre)
- [x] 3.2 Simulator (Sinh dữ liệu giả lập cho test)
- [x] 3.3 CLI bản hoàn chỉnh
- [x] 3.4 Đóng gói Deployment (Docker full-stack)
- [x] 3.5 Tích hợp hệ thống Monitoring (Prometheus)

### 🏁 PHASE 4 — Học từ thực tế (Mốc D)
*Mục tiêu: Cải thiện mô hình dựa trên Telemetry xe thật (Tùy chọn).*
- [x] Telemetry Adapter (OBD/MQTT)
- [x] Hiệu chỉnh Online (Theo thói quen tài xế / xe thật)
- [x] Huấn luyện ML trên phần dư của vật lý

---

## 🏛️ Kiến trúc tổng quan

Kiến trúc 3 lớp nghiêm ngặt (Hexagonal Architecture):
1. **Core (`packages/core`)**: Chứa 100% logic nghiệp vụ. Không giao tiếp I/O, mạng hay Database.
2. **Adapters (`packages/adapters`)**: Gọi API ngoài, query database.
3. **Apps (`apps/`)**: Điểm vào của ứng dụng (API, Web UI, CLI).

Tham khảo chi tiết tại `ARCHITECTURE.md` và `PRD.md`.