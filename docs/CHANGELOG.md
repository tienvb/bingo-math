# Đính chính hợp đồng

Master ghi lại mọi thay đổi đã chốt đối với `spec.md` tại đây, mới nhất ở trên cùng. Agent con đọc file này trước mỗi việc.

| Ngày | Mục trong spec | Thay đổi | Lý do |
| --- | --- | --- | --- |
| 2026-10-28 | Docker | Image build FE và FE dev đổi `node:20-alpine` → `node:22-alpine`; README yêu cầu Node.js 22+ | `vue-i18n` 11 / `@intlify/*` yêu cầu Node ≥ 22 (`EBADENGINE`) |
| 2026-10-28 | Docker — nginx | `/assets/` dùng một header `Cache-Control: public, max-age=31536000, immutable` thay cho `expires 1y` + `add_header`; nginx dùng `resolver 127.0.0.11` để không chết khi backend chưa lên | `expires` sinh hai dòng Cache-Control; FE đề xuất ở G3 |
| 2026-10-28 | Nhiệm vụ FE — Công nghệ | Thêm `lottie-web`, chỉ lazy-load (dynamic import) khi người thắng có `win_animation` dạng `.json` | Người dùng chọn hỗ trợ Lottie đầy đủ như spec |
| 2026-10-28 | Hợp đồng REST API — `GET /api/rooms/{pin}` | Response thêm `avatar_counts: Record<avatar_id, number>` (chỉ nhân vật có ≥ 1 người chọn) | *Nhân vật* yêu cầu hiện số nhỏ ở góc nhân vật đã có người chọn nhưng hợp đồng chưa có dữ liệu; FE đề xuất ở G2 |
| 2026-10-28 | Hợp đồng REST API — Quy ước chung | Thêm 422 `invalid_request` (body sai dạng chung), 404 `not_found` (route không tồn tại), 405 `method_not_allowed`. FE gặp mã lạ thì hiện lỗi chung | BE đề xuất ở G2; trước đó dùng tạm `invalid_message` |
| 2026-10-28 | Hợp đồng WebSocket — mã đóng | Thêm 4409: kết nối bị thay bằng kết nối mới của cùng người chơi. Client không tự kết nối lại khi nhận 4401, 4403, 4404, 4409, 4410 | Tránh hai tab giành nhau kết nối; BE đề xuất ở G2 |
| 2026-10-28 | Nhiệm vụ BE — nhân vật | Manifest có mục sai: bỏ qua mục đó, log cảnh báo rõ, server vẫn chạy. Chỉ dừng khi manifest không đọc được hoặc không còn nhân vật hợp lệ | Một lỗi gõ khi thêm nhân vật không được làm sập cả game |
| 2026-10-28 | Vai trò và màn hình | Mọi màn hình chạy được cả trên laptop lẫn mobile web (360px → 1920px, cảm ứng và chuột, không cuộn ngang, vùng bấm ≥ 44px). Xem đoạn **Responsive** | Người dùng yêu cầu |
| 2026-10-28 | Hợp đồng WebSocket — thứ tự sự kiện | Chốt thứ tự: **Bắt đầu** `game_started` → `phase_changed{question}` → `question{reason:new}`; **Câu tiếp theo** `phase_changed{question}` → `question{new}`; **Bỏ qua** `question_skipped` → `phase_changed{ready}`; **Kết thúc ván** (cả bingo lẫn chủ phòng) `phase_changed{finished}` → `game_over`; **Ván mới** `join_url_updated` (chỉ khi địa chỉ đổi) → `snapshot` cho tất cả, không gửi riêng `phase_changed` / `your_card`; **Sửa cấu hình ở lobby** `config_updated` → `your_card{marked:[]}` cho từng người | Spec chỉ chốt thứ tự cho câu trả lời đúng; FE đề xuất ở G1 để BE làm cùng cách |
| 2026-10-28 | Hợp đồng — kiểm lỗi | `submit_answer` kiểm theo thứ tự `invalid_phase` → `question_id` lệch (`stale_question`) → `not_your_turn` → `attempt` lệch (`stale_question`). `nickname_taken` so sánh sau trim, không phân biệt hoa/thường. `join_base_url` có `/` cuối được chấp nhận và bỏ `/`; path khác, query, hash thì `invalid_join_url`. WS tới PIN đang trong thời gian nghỉ đóng bằng 4410, PIN chưa từng tồn tại đóng bằng 4404 | Làm rõ chỗ spec chưa nói; 4410 để QR cũ hiện "Phòng đã đóng" đúng như *Mã phòng* |
| 2026-10-28 | Công nghệ FE | Cho phép `vitest` (devDependency, chỉ để test). Mock ở G2 đồng bộ nhiều tab qua `BroadcastChannel` (một tab giữ engine) | Kiểm thử mock tự động; chơi trọn ván bằng mock trên 3 màn hình khác tab |
| 2026-10-28 | Hợp đồng WebSocket — `Cell[]` | Làm rõ: `marked`, `marked_before` (trong `your_card`, `Snapshot`, `Winner`, `RevealItem`) **không chứa** ô FREE `[2,2]`; FE luôn tự coi FREE là đã khoanh | Tránh hai bên hiểu khác nhau |
| 2026-10-28 | Hợp đồng WebSocket — `error` | Thêm mã lỗi `invalid_message` cho message WS sai dạng (JSON hỏng, `type` lạ, `data` sai, role không được gửi `type` đó) | Spec nói gửi `error` nhưng không nêu mã; BE đề xuất ở G1 |
| 2026-10-26 | — | Phiên bản đầu tiên của spec | — |
