import type { Reveal } from '@/api/contract'

/** Vị trí hiện tại của reveal: vé thứ `index` (0-based), đã hiện được `elapsedInCard` ms. */
export type RevealPosition = {
  index: number
  elapsedInCard: number
  /** true khi đã hết thời gian của vé cuối (chờ server chuyển phase). */
  done: boolean
}

/**
 * Đồng bộ reveal theo spec: vé đang hiện = floor((now − started_at) / seconds_per_card).
 * Kẹp vào [0, items.length − 1] để mở tab giữa chừng (hoặc lệch đồng hồ) vẫn hiện được một vé.
 */
export function revealPosition(reveal: Reveal, nowMs: number): RevealPosition {
  const start = Date.parse(reveal.started_at)
  const per = Math.max(1, reveal.seconds_per_card) * 1000
  const count = reveal.items.length
  const elapsed = Number.isFinite(start) ? Math.max(0, nowMs - start) : 0
  const raw = Math.floor(elapsed / per)
  if (count === 0) return { index: 0, elapsedInCard: elapsed, done: elapsed >= per }
  const index = Math.min(raw, count - 1)
  return { index, elapsedInCard: elapsed - index * per, done: raw >= count }
}

/** Số giây còn lại (làm tròn lên, không âm) tới `deadline` ISO. */
export function secondsLeft(deadline: string | null, nowMs: number): number | null {
  if (!deadline) return null
  const end = Date.parse(deadline)
  if (!Number.isFinite(end)) return null
  return Math.max(0, Math.ceil((end - nowMs) / 1000))
}

/**
 * Ước lượng độ lệch đồng hồ server − client (ms) từ một mốc thời gian server vừa sinh ra.
 * Chỉ dùng cho sự kiện mới (không dùng cho snapshot): `serverStampMs` ≈ thời điểm server gửi.
 * Bỏ qua lệch nhỏ (< 1,5 s) để không nhảy số vì độ trễ mạng.
 */
export function estimateOffset(serverStampMs: number, receivedAtMs: number): number {
  const off = serverStampMs - receivedAtMs
  return Math.abs(off) < 1500 ? 0 : off
}
