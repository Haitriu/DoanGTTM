# Nguồn dữ liệu ngoài

Ghi lại theo yêu cầu ở CLAUDE.md mục 7 — mỗi nguồn dữ liệu ngoài phải có giấy phép
được kiểm tra và ghi chú tại đây trước khi dùng trong production.

## OpenStreetMap (qua OSRM self-hosted)

- **Dùng cho:** routing thật (tuyến đường lái xe) — `packages/adapters/voltrail_adapters/routing/osrm.py`.
- **Dữ liệu:** extract Việt Nam từ Geofabrik (`https://download.geofabrik.de/asia/vietnam-latest.osm.pbf`),
  build thành routing graph bằng `osrm-extract`/`osrm-partition`/`osrm-customize`
  (image `osrm/osrm-backend`), chạy qua `osrm-routed`.
- **Giấy phép:** [ODbL 1.0](https://opendatacommons.org/licenses/odbl/) — bắt buộc
  ghi nguồn ("© OpenStreetMap contributors") và áp dụng share-alike cho bất kỳ
  cơ sở dữ liệu phái sinh (derivative database) nào công khai dựa trên dữ liệu này.
- **Attribution:** hiển thị "© OpenStreetMap contributors" ở footer bản đồ trong
  `apps/web/index.html`.
- **Lưu trữ:** file `.osm.pbf` và routing graph build ra (`data/osm/`) KHÔNG commit
  vào git — tải lại bằng `make osrm-data`, xem `.gitignore`.
- **Giới hạn thương mại:** không có — ODbL cho phép dùng thương mại, chỉ ràng buộc
  attribution + share-alike với derivative database (không phải với sản phẩm dùng nó).

## Open Charge Map

- **Dùng cho:** dữ liệu trạm sạc thật (công suất kW, connector, operator) —
  `packages/adapters/voltrail_adapters/stations/open_charge_map.py`.
- **Giấy phép:** [CC BY 4.0](https://openchargemap.org/site/about#license) — bắt buộc
  ghi nguồn. Cần API key miễn phí tại https://openchargemap.org/site/develop/api.
- **Attribution:** cần bổ sung "Dữ liệu trạm sạc © Open Charge Map" ở footer khi
  `has_real_stations=true` — TODO, chưa có trong UI hiện tại.

## Mapbox (tiles)

- **Dùng cho:** nền bản đồ hiển thị trên web app.
- **Giấy phép:** theo Mapbox Terms of Service — free tier giới hạn số lượt tải tile
  mỗi tháng, vượt ngưỡng sẽ tính phí. Cần access token cá nhân.

## SerpApi (Google Maps)

- **Dùng cho:** gợi ý vị trí trạm sạc trên bản đồ (tham khảo, không dùng lập kế hoạch) —
  `packages/adapters/voltrail_adapters/stations/serpapi_maps.py`. Hiện KHÔNG được
  gọi trong `apps/api/main.py` (xem ghi chú trong file đó) vì gây nhiễu bản đồ và
  không có dữ liệu công suất sạc.
- **Giấy phép:** theo SerpApi Terms of Service — free tier giới hạn ~100 lượt tìm/tháng,
  dữ liệu lấy từ Google Maps nên còn chịu ràng buộc của Google Maps Platform ToS
  (không được cache/lưu trữ lâu dài kết quả để dùng lại ngoài mục đích hiển thị tức thời).
  Cần API key riêng tại https://serpapi.com/dashboard.
