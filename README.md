# Bingo Math

Web game toán + bingo cho các bé, chơi trong mạng LAN. Thiết kế đầy đủ ở `docs/spec.md`.

## Cấu trúc

```text
bingo-math/
  CLAUDE.md                  # hướng dẫn cho master agent (chạy ở thư mục gốc)
  .claude/agents/            # 2 agent con: backend-dev, frontend-dev
  .claude/hooks/             # hook chặn agent con ghi file ngoài thư mục của mình
  docs/                      # spec.md, CHANGELOG.md
  backend/                   # FastAPI (agent backend-dev)
  frontend/                  # Vue 3 (agent frontend-dev)
```

## Cần cài

- Claude Code (extension VS Code hoặc CLI)
- Python 3.12 và lệnh `python3` có trong PATH (hook của agent con dùng lệnh này; trên Windows nên chạy trong WSL, hoặc sửa `python3` thành `python` trong `.claude/agents/*.md`)
- Node.js 22 (hoặc mới hơn)
- Docker Desktop / Docker Engine (cho giai đoạn 3–4)
- Git

## Bắt đầu với Claude Code trên VS Code

1. Giải nén, mở thư mục `bingo-math` bằng VS Code.
2. Mở Claude Code. Khi được hỏi có tin cậy thư mục này không, chọn **Trust** (cần để hook của agent con chạy được).
3. Gửi cho Claude Code:

   > Đọc CLAUDE.md và docs/spec.md, rồi bắt đầu giai đoạn 1.

4. Sau mỗi giai đoạn, master sẽ báo lại. Gửi tiếp:

   > Tiếp tục giai đoạn 2.

   Hoặc để chạy liền mạch:

   > Chạy lần lượt giai đoạn 1 đến 3, dừng lại hỏi tôi trước giai đoạn 4.

## Điều chỉnh spec

Muốn đổi luật chơi hay hợp đồng: nói với master. Master sẽ sửa `docs/spec.md`, ghi vào `docs/CHANGELOG.md` và báo cho cả hai agent con. Không sửa tay trong `backend/` hay `frontend/` khi các agent đang chạy.

## Chạy game (sau khi xong)

```bash
cp .env.example .env
docker compose up -d --build
```

Mở `http://<IP LAN của máy>:8080` trên máy chủ phòng, bấm **Tạo phòng**, rồi cho các bé quét QR.
