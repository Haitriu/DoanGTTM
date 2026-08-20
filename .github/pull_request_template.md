## Thay đổi gì?

(Mô tả ngắn gọn về những thay đổi trong PR này)

## Tại sao?

(Lý do của sự thay đổi, link đến issue nếu có)

## Đã test thế nào?

- [ ] Unit tests cho core logic mới
- [ ] Property tests nếu thay đổi thuật toán
- [ ] Chạy `make test` thành công

## Ảnh hưởng đến Golden Trips?

- [ ] Không làm thay đổi kết quả (hoặc thay đổi < tolerance)
- [ ] Có làm thay đổi (Vui lòng giải thích lý do bên dưới)

## Checklist (Định nghĩa Xong)

- [ ] Code có type hint đầy đủ, `make lint` sạch
- [ ] Có test, `make test` xanh
- [ ] Golden trips không lệch quá ngưỡng (hoặc có giải thích hợp lý)
- [ ] Đơn vị trong tên biến đúng chuẩn (VD: `_kw`, `_kwh`, `_m`, `_s`)
- [ ] Không vi phạm bất biến của mô hình (VD: SOC không dưới reserve)
- [ ] Cập nhật tài liệu (`PRD.md` / `ARCHITECTURE.md` / ADR) nếu có kiến trúc thay đổi
- [ ] Không thêm secret hoặc dữ liệu bulk vào git
