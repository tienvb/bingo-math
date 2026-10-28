# Frontend — Bingo Math

Vue 3 + Vite + TypeScript + Pinia + Vue Router + vue-i18n. Spec: `../docs/spec.md`, đính chính: `../docs/CHANGELOG.md`.

## Phạm vi

Chỉ sửa file trong `frontend/`. Cần thay đổi ở nơi khác thì báo master.

## Lệnh (chạy từ thư mục gốc dự án)

```bash
# Cài đặt
cd frontend && npm install

# Phát triển với mock (không cần backend)
cd frontend && VITE_USE_MOCK=true npm run dev -- --host

# Phát triển với backend thật (backend chạy ở :8000)
cd frontend && VITE_USE_MOCK=false npm run dev -- --host

# Kiểm tra kiểu + build (phải xanh trước khi báo xong)
cd frontend && npm run build
```

`npm run build` phải chạy `vue-tsc --noEmit` trước `vite build`.

## Quy ước

- Cấu trúc thư mục đúng như mục *Nhiệm vụ FE* trong spec.
- `src/api/contract.ts` là bản sao từng chữ của hợp đồng; mọi chỗ khác import type từ đây.
- Component dùng `<script setup lang="ts">`.
- Không có chuỗi hiển thị hard-code: mọi chữ nằm trong `src/i18n/locales/vi.json` và `en.json`; lỗi từ server dịch theo `code`.
- Thiết kế cho trẻ em: nút to, chữ to, màu tươi, dễ bấm; màn hình người chơi mobile-first; màn hình chính 1920 × 1080.
- Tôn trọng `prefers-reduced-motion`.
- Bọc mọi truy cập `localStorage` trong try/catch.

## Không làm

- Không tự tính đáp án, không tự đánh dấu ô: chỉ hiển thị theo sự kiện từ server hoặc mock.
- Không dùng emoji cho mã hình; dùng 12 SVG riêng trong `src/assets/room-icons/`.
- Không vẽ lại nhân vật có bản quyền.
