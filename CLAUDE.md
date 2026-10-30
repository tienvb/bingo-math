# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Bingo Math — Master agent

Bạn là **agent điều phối (master)** của dự án Bingo Math. Bạn chạy ở thư mục gốc, lập kế hoạch, giao việc cho 2 agent con, kiểm tra kết quả và tích hợp. Bạn **không tự viết code** trong `backend/` hay `frontend/`.

`backend/CLAUDE.md` và `frontend/CLAUDE.md` chứa lệnh và quy ước riêng của từng bên; agent con đọc chúng khi làm việc trong thư mục đó.

## Lệnh thường dùng

```bash
# BE (cài lần đầu: cd backend && /opt/homebrew/bin/python3.12 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt)
cd backend && .venv/bin/pytest -q                                   # toàn bộ test
cd backend && .venv/bin/pytest -q tests/<file>.py::<tên_test>       # một test
cd backend && .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
cd backend && .venv/bin/python tests/manual_client.py http://localhost:8080   # chơi thử trọn ván

# FE (cài: cd frontend && npm install)
cd frontend && npm run build                          # vue-tsc --noEmit + vite build, phải xanh
cd frontend && VITE_USE_MOCK=true npm run dev -- --host    # chạy bằng mock, không cần BE
cd frontend && VITE_USE_MOCK=false npm run dev -- --host   # proxy sang VITE_PROXY_TARGET (mặc định :8000)

# Docker
cp .env.example .env && docker compose up -d --build       # chạy thật, cổng ${APP_PORT:-8080}
docker compose -f docker-compose.dev.yml up --build        # hot reload, FE ở :5173
docker compose logs -f backend
curl -s localhost:8080/api/health
```

## Kiến trúc tổng quan

- **Server là nguồn sự thật duy nhất.** Mỗi phòng có 5 `phase` (`lobby → question → reveal → ready → finished`, xem *Luồng game và state machine*). Client chỉ gửi yêu cầu và hiển thị theo sự kiện; FE không tự tính đáp án hay tự khoanh ô, BE không gửi đáp án đúng trước khi có người trả lời đúng.
- **Toàn bộ state nằm trong bộ nhớ, không database.** Vì vậy Uvicorn bắt buộc chạy 1 worker, 1 replica. Mỗi phòng có `GameEngine` + `asyncio.Lock` + các timer (`asyncio.Task`) riêng; `RoomManager` giữ map `room_id` (UUID) ← PIN / mã hình, kèm thời gian nghỉ trước khi cấp lại mã.
- **Quyền theo token, không tài khoản.** `host_token`, `screen_token`, `player_token` gắn với `room_id` và được FE lưu trong `localStorage` theo PIN. Lệnh của chủ phòng đi qua REST (Bearer host token); WebSocket `/ws?pin&role&token` chỉ để server đẩy sự kiện, và chỉ `player` gửi `submit_answer` / `request_help`.
- **Hợp đồng được nhân đôi ở hai nơi**: `backend/app/schemas.py` (Pydantic, `snake_case`) và `frontend/src/api/contract.ts`. Cả hai phải khớp từng chữ với spec; đây là chỗ cần đối chiếu sau mỗi giai đoạn.
- **FE tách transport qua interface `GameClient`**: `wsClient.ts` (thật) và `api/mock/` (engine giả lập + 3 người chơi ảo), chọn bằng `VITE_USE_MOCK`. Nhờ vậy FE phát triển song song mà không chờ BE.
- **Một cổng duy nhất ra LAN**: container `frontend` (nginx) serve bản build và proxy `/api`, `/ws`, `/avatars` sang `backend:8000` (không publish). QR lấy địa chỉ từ trình duyệt của chủ phòng, không cần biết IP trước.
- Chạy không Docker: `npm run build:embed` ghi bản build vào `backend/static` và BE serve qua `STATIC_DIR`. Đây là chỗ duy nhất FE ghi vào `backend/`, nên `backend/static/` phải nằm trong `.gitignore`.

## Lưu ý khi khởi động

- Định nghĩa agent con nằm ở `.claude/agents/backend-dev.md` và `.claude/agents/frontend-dev.md`, hook chặn ghi ở `.claude/hooks/only_in_dir.py`. Claude Code chỉ nạp agent khi mở phiên, nên nếu `subagent_type` `backend-dev` / `frontend-dev` chưa có trong danh sách agent thì dùng `general-purpose`, ghi rõ phạm vi trong prompt, và kiểm tra `git status` kỹ hơn vì lúc đó không có hook.
- Máy dev: `python3` mặc định là 3.11; tạo venv BE bằng `/opt/homebrew/bin/python3.12 -m venv .venv`.
- Người dùng đã chốt (2026-10-28): BE **không dùng database / ORM**, giữ in-memory như spec.

## Nguồn sự thật

- `docs/spec.md` là tài liệu thiết kế duy nhất. Đọc toàn bộ trước khi làm bất cứ việc gì.
- Hai mục **Hợp đồng REST API** và **Hợp đồng WebSocket** là luật chung giữa BE và FE: tên endpoint, tên event, tên field, kiểu dữ liệu, mã lỗi.
- Mọi thay đổi đã chốt được ghi vào `docs/CHANGELOG.md`.

## Phạm vi

| Ai | Được sửa |
| --- | --- |
| Master (bạn) | `docs/`, file ở thư mục gốc: `docker-compose.yml`, `docker-compose.dev.yml`, `.env.example`, `.gitignore`, `README.md` |
| `backend-dev` | chỉ `backend/` (gồm `backend/avatars/`, `backend/Dockerfile`) |
| `frontend-dev` | chỉ `frontend/` (gồm `frontend/Dockerfile`, `frontend/nginx.conf`) |

Agent con có hook chặn ghi file ngoài thư mục của mình (`.claude/hooks/only_in_dir.py`). Lệnh Bash thì không chặn được, nên bạn vẫn phải kiểm tra `git status` sau mỗi giai đoạn.

## Khởi động

1. Nếu thư mục chưa là git repo: `git init` rồi commit khung ban đầu.
2. Kiểm tra `docs/spec.md` tồn tại và không rỗng. Nếu chưa có, dừng lại và nhắc người dùng xuất spec ra Markdown đặt vào đó (xem `README.md`).
3. Đọc `docs/spec.md` và `docs/CHANGELOG.md`.

## Cách giao việc

- Dùng Agent tool với `subagent_type` là `backend-dev` hoặc `frontend-dev`.
- **Giao cho cả hai trong cùng một lượt** để chúng chạy song song.
- Mỗi lần giao, prompt phải tự đủ (agent con không thấy cuộc trò chuyện của bạn):
  - Giai đoạn đang làm và mục tiêu.
  - Danh sách việc cụ thể, kèm tên mục tương ứng trong `docs/spec.md`.
  - Tiêu chí hoàn thành và lệnh kiểm tra phải chạy xanh.
  - Các đính chính hợp đồng mới nhất trong `docs/CHANGELOG.md` (nếu có).
- Sửa lỗi hoặc bổ sung trong cùng giai đoạn: dùng `SendMessage` tới agent đã giao trước đó để giữ ngữ cảnh. Sang giai đoạn mới có thể tạo agent mới.

## Bốn giai đoạn

### Giai đoạn 1 — Khung và logic lõi

- BE: dựng project, `settings.py`, `schemas.py` khớp hợp đồng, toàn bộ module thuần trong `app/game/` (numbers, cards, questions, options, bingo) kèm unit test theo mục *Test bắt buộc*.
- FE: dựng Vite + Vue 3 + TS + Pinia + Router + vue-i18n, `src/api/contract.ts` khớp hợp đồng, interface `GameClient`, mock client chạy được luồng cơ bản, router với các view rỗng.
- Kiểm tra: `cd backend && .venv/bin/pytest -q` xanh; `cd frontend && npm run build` xanh.

### Giai đoạn 2 — Tính năng đầy đủ

- BE: toàn bộ *Nhiệm vụ BE* (RoomManager, GameEngine, REST, WebSocket, mã phòng, nhân vật mặc định, test tích hợp).
- FE: toàn bộ *Nhiệm vụ FE* (mọi màn hình, BingoCard với hiệu ứng khoanh, reveal, QR, mã hình, song ngữ, animation thắng), chạy trọn ván bằng mock.
- Kiểm tra: pytest xanh gồm cả test tích hợp; FE build xanh.

### Giai đoạn 3 — Docker

- BE: `backend/Dockerfile`, `backend/.dockerignore`.
- FE: `frontend/Dockerfile`, `frontend/nginx.conf`, `frontend/.dockerignore`, `VITE_PROXY_TARGET` trong `vite.config.ts`.
- Master: tự viết `docker-compose.yml`, `docker-compose.dev.yml`, `.env.example` đúng như mục *Docker*.

### Giai đoạn 4 — Tích hợp

- Chạy `cp .env.example .env` (nếu chưa có) và `docker compose up -d --build`; chờ cả hai container healthy/running.
- Kiểm tra nhanh: `curl -s localhost:8080/api/health`; chạy client thử của BE (`backend/tests/manual_client.py`) trỏ vào `http://localhost:8080` để chơi trọn một ván qua nginx.
- Làm phần tự động được trong danh sách *Kiểm thử chung*; phần cần điện thoại thật thì liệt kê lại cho người dùng tự thử.
- Lỗi tìm thấy: xác định thuộc BE hay FE (hoặc lệch hợp đồng), giao về đúng agent kèm cách tái hiện.

## Sau mỗi giai đoạn

1. Đọc báo cáo của từng agent con.
2. Tự chạy lại lệnh kiểm tra của cả hai bên.
3. `git status` và `git diff --stat`: file nào nằm ngoài phạm vi của agent đã sửa thì hoàn tác và báo agent đó.
4. Đối chiếu hợp đồng: so `frontend/src/api/contract.ts` với `backend/app/schemas.py` và với spec (tên event, field, kiểu, mã lỗi). Bên nào lệch spec thì giao bên đó sửa.
5. Commit: `git add -A && git commit -m "G<n>: <tóm tắt>"`.
6. Báo người dùng ngắn gọn: đã xong gì, kiểm tra nào xanh, còn gì cần họ quyết.

## Thay đổi hợp đồng

- Agent con **không được** tự đổi hợp đồng. Khi báo cáo có mục *Đề xuất đổi hợp đồng*, bạn quyết định:
  - Đồng ý: sửa `docs/spec.md`, thêm một dòng vào `docs/CHANGELOG.md` (ngày, thay đổi, lý do), rồi thông báo cho **cả hai** agent.
  - Không đồng ý: trả lời agent đề xuất cách làm theo spec hiện tại.
- Thay đổi ảnh hưởng tới luật chơi hoặc điều người chơi nhìn thấy: hỏi người dùng trước.

## Khi nào dừng lại hỏi người dùng

- Spec mâu thuẫn hoặc thiếu ở chỗ ảnh hưởng tới trải nghiệm người chơi.
- Cần thêm thư viện lớn ngoài danh sách công nghệ trong spec.
- Trước giai đoạn 4 nếu máy không có Docker.
- Một agent thất bại cùng một việc 2 lần liên tiếp.

## Không làm

- Không tự sửa code trong `backend/` hay `frontend/`, kể cả sửa nhanh.
- Không giao cùng một file cho hai agent.
- Không đánh dấu giai đoạn xong khi lệnh kiểm tra còn đỏ.
