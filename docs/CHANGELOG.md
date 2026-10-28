# Đính chính hợp đồng

Master ghi lại mọi thay đổi đã chốt đối với `spec.md` tại đây, mới nhất ở trên cùng. Agent con đọc file này trước mỗi việc.

| Ngày | Mục trong spec | Thay đổi | Lý do |
| --- | --- | --- | --- |
| 2026-10-28 | Hợp đồng WebSocket — thứ tự sự kiện | Chốt thứ tự: **Bắt đầu** `game_started` → `phase_changed{question}` → `question{reason:new}`; **Câu tiếp theo** `phase_changed{question}` → `question{new}`; **Bỏ qua** `question_skipped` → `phase_changed{ready}`; **Kết thúc ván** (cả bingo lẫn chủ phòng) `phase_changed{finished}` → `game_over`; **Ván mới** `join_url_updated` (chỉ khi địa chỉ đổi) → `snapshot` cho tất cả, không gửi riêng `phase_changed` / `your_card`; **Sửa cấu hình ở lobby** `config_updated` → `your_card{marked:[]}` cho từng người | Spec chỉ chốt thứ tự cho câu trả lời đúng; FE đề xuất ở G1 để BE làm cùng cách |
| 2026-10-28 | Hợp đồng — kiểm lỗi | `submit_answer` kiểm theo thứ tự `invalid_phase` → `question_id` lệch (`stale_question`) → `not_your_turn` → `attempt` lệch (`stale_question`). `nickname_taken` so sánh sau trim, không phân biệt hoa/thường. `join_base_url` có `/` cuối được chấp nhận và bỏ `/`; path khác, query, hash thì `invalid_join_url`. WS tới PIN đang trong thời gian nghỉ đóng bằng 4410, PIN chưa từng tồn tại đóng bằng 4404 | Làm rõ chỗ spec chưa nói; 4410 để QR cũ hiện "Phòng đã đóng" đúng như *Mã phòng* |
| 2026-10-28 | Công nghệ FE | Cho phép `vitest` (devDependency, chỉ để test). Mock ở G2 đồng bộ nhiều tab qua `BroadcastChannel` (một tab giữ engine) | Kiểm thử mock tự động; chơi trọn ván bằng mock trên 3 màn hình khác tab |
| 2026-10-28 | Hợp đồng WebSocket — `Cell[]` | Làm rõ: `marked`, `marked_before` (trong `your_card`, `Snapshot`, `Winner`, `RevealItem`) **không chứa** ô FREE `[2,2]`; FE luôn tự coi FREE là đã khoanh | Tránh hai bên hiểu khác nhau |
| 2026-10-28 | Hợp đồng WebSocket — `error` | Thêm mã lỗi `invalid_message` cho message WS sai dạng (JSON hỏng, `type` lạ, `data` sai, role không được gửi `type` đó) | Spec nói gửi `error` nhưng không nêu mã; BE đề xuất ở G1 |
| 2026-10-26 | — | Phiên bản đầu tiên của spec | — |
