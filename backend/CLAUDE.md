# Backend — Bingo Math

FastAPI + WebSocket thuần, Python 3.12. Spec: `../docs/spec.md`, đính chính: `../docs/CHANGELOG.md`.

## Phạm vi

Chỉ sửa file trong `backend/`. Cần thay đổi ở nơi khác thì báo master.

## Lệnh (chạy từ thư mục gốc dự án)

```bash
# Cài đặt lần đầu
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# Test
cd backend && .venv/bin/pytest -q

# Chạy server khi phát triển
cd backend && .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Quy ước

- Cấu trúc thư mục đúng như mục *Nhiệm vụ BE* trong spec.
- Type hints đầy đủ; Pydantic v2 cho mọi payload; field `snake_case` đúng tên trong hợp đồng.
- Module trong `app/game/` là hàm thuần: không I/O, không đọc biến toàn cục, nhận random generator làm tham số để test được.
- Mỗi phòng có `GameEngine` và `asyncio.Lock` riêng; mọi thay đổi state của phòng đi qua lock đó. Timer là `asyncio.Task` hủy được.
- Lỗi REST luôn trả `{"code": "...", "message": "..."}` với đúng mã trong hợp đồng.
- Log mỗi sự kiện chính kèm PIN.

## Không làm

- Không dùng database, Socket.IO, hay nhiều worker Uvicorn.
- Không gửi đáp án đúng xuống client trước khi có người trả lời đúng.
- Không tin trạng thái ô hay điểm số từ client.
- Không vẽ lại nhân vật có bản quyền; 12 nhân vật mặc định là thiết kế SVG gốc.
