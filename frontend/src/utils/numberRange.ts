// Tập R (spec *Thuật toán chi tiết* mục 1) biểu diễn bằng các đoạn số rời nhau, không dựng mảng đầy đủ,
// vì max_number (M) không có giới hạn trên. Form cấu hình dùng để báo lỗi |R| < 25 ngay khi nhập;
// mock dùng để sinh vé / bốc số. Đây chỉ là kiểm tra cấu hình, không phải tính đáp án.

import type { GameConfig } from '@/api/contract'

/** Đoạn [lo, hi], cả hai đầu đều thuộc tập. */
export type Interval = [number, number]

export const DEFAULT_MAX_NUMBER = 100
/** max_number phải > 30. */
export const MIN_MAX_NUMBER = 31
/** Vé 5 × 5 có 24 ô số → cần |R| ≥ 25 (spec mục 1). */
export const MIN_R_SIZE = 25

type Ops = GameConfig['operations']

/** Sắp và gộp các đoạn chồng hoặc liền nhau. */
export function mergeIntervals(list: Interval[]): Interval[] {
  const sorted = list.filter(([lo, hi]) => lo <= hi).sort((a, b) => a[0] - b[0])
  const out: Interval[] = []
  for (const [lo, hi] of sorted) {
    const last = out[out.length - 1]
    if (last && lo <= last[1] + 1) last[1] = Math.max(last[1], hi)
    else out.push([lo, hi])
  }
  return out
}

/** R theo phép được bật và M. */
export function resultIntervals(ops: Ops, maxNumber: number): Interval[] {
  const M = maxNumber
  const list: Interval[] = []
  if (ops.add) list.push([2, M]) // a, b ≥ 1, a + b ≤ M
  if (ops.sub) list.push([1, M - 1]) // a ≤ M, b ≥ 1
  if (ops.mul) for (let a = 1; a <= 10; a++) for (let b = 1; b <= 10; b++) if (a * b <= M) list.push([a * b, a * b])
  if (ops.div)
    for (let n = 1; n <= 10; n++) {
      // b trong 2–10 (n = 1 thì cho phép b = 1) và a = n × b ≤ M
      const minB = n === 1 ? 1 : 2
      if (n * minB <= M) list.push([n, n])
    }
  return mergeIntervals(list)
}

export function intervalsSize(iv: Interval[]): number {
  return iv.reduce((s, [lo, hi]) => s + (hi - lo + 1), 0)
}

/** Phần tử thứ k (0-based) của tập theo thứ tự tăng dần. */
export function nthInIntervals(iv: Interval[], k: number): number {
  let rest = k
  for (const [lo, hi] of iv) {
    const len = hi - lo + 1
    if (rest < len) return lo + rest
    rest -= len
  }
  throw new RangeError(`index ${k} out of range`)
}

export function inIntervals(iv: Interval[], n: number): boolean {
  return iv.some(([lo, hi]) => n >= lo && n <= hi)
}

export type MaxNumberProblem = 'not_integer' | 'too_small' | 'too_large' | null

/** max_number hợp lệ: số nguyên > 30. JS chỉ biểu diễn chính xác tới Number.MAX_SAFE_INTEGER. */
export function maxNumberProblem(m: unknown): MaxNumberProblem {
  if (typeof m !== 'number' || !Number.isFinite(m) || !Number.isInteger(m)) return 'not_integer'
  if (m < MIN_MAX_NUMBER) return 'too_small'
  if (m > Number.MAX_SAFE_INTEGER) return 'too_large'
  return null
}

/** Số phần tử của R, hoặc null nếu M không hợp lệ. */
export function availableCount(ops: Ops, maxNumber: number): number | null {
  if (maxNumberProblem(maxNumber)) return null
  return intervalsSize(resultIntervals(ops, maxNumber))
}
