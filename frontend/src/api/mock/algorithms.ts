// Thuật toán đơn giản cho mock server (chỉ chạy trong mock, đóng vai BE).
// UI không được import file này: FE không tự tính đáp án, không tự khoanh ô.

import type { Card, Cell, GameConfig, Line, OptionKey, Operator } from '../contract'
import {
  DEFAULT_MAX_NUMBER,
  MIN_R_SIZE,
  intervalsSize,
  maxNumberProblem,
  nthInIntervals,
  resultIntervals,
  type Interval,
} from '@/utils/numberRange'

export type { Interval }

export type Rng = () => number

export const randInt = (rng: Rng, min: number, max: number): number => min + Math.floor(rng() * (max - min + 1))
export const pick = <T>(rng: Rng, arr: readonly T[]): T => arr[Math.floor(rng() * arr.length)]
export function shuffle<T>(rng: Rng, arr: T[]): T[] {
  const a = arr.slice()
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1))
    ;[a[i], a[j]] = [a[j], a[i]]
  }
  return a
}

type Ops = GameConfig['operations']

/** Tập R theo phép được bật và M, dạng đoạn số (không dựng mảng đầy đủ khi M lớn). */
export function availableRanges(ops: Ops, maxNumber: number): Interval[] {
  return resultIntervals(ops, maxNumber)
}

/** Bù mặc định cho field thiếu (spec: request thiếu max_number / next_mode thì dùng mặc định). */
export function normalizeConfig(raw: unknown): GameConfig | null {
  if (!raw || typeof raw !== 'object') return null
  const r = raw as Partial<GameConfig>
  return {
    ...(r as GameConfig),
    max_number: r.max_number === undefined ? DEFAULT_MAX_NUMBER : (r.max_number as number),
    next_mode: r.next_mode === undefined ? 'auto' : (r.next_mode as GameConfig['next_mode']),
  }
}

export function isValidConfig(c: GameConfig): boolean {
  const o = c.operations
  if (!o || !(o.add || o.sub || o.mul || o.div)) return false
  if (maxNumberProblem(c.max_number)) return false
  if (intervalsSize(availableRanges(o, c.max_number)) < MIN_R_SIZE) return false
  if (c.next_mode !== 'auto' && c.next_mode !== 'manual') return false
  const int = Number.isInteger
  if (!int(c.timer_seconds) || !(c.timer_seconds === 0 || (c.timer_seconds >= 5 && c.timer_seconds <= 120))) return false
  if (!int(c.max_wrong) || c.max_wrong < 1 || c.max_wrong > 5) return false
  if (!int(c.reveal_seconds) || c.reveal_seconds < 2 || c.reveal_seconds > 15) return false
  return typeof c.draw_only_card_numbers === 'boolean'
}

/** k số chỉ số khác nhau ngẫu nhiên trong [lo, hi] (khoảng có thể rất lớn). */
function sampleIndices(rng: Rng, lo: number, hi: number, k: number): number[] {
  const size = hi - lo + 1
  if (size <= 64) return shuffle(rng, Array.from({ length: size }, (_, i) => lo + i)).slice(0, k)
  const out = new Set<number>()
  while (out.size < k) out.add(randInt(rng, lo, hi))
  return [...out]
}

/** Sinh vé 5x5: R chia 5 nhóm liên tiếp (nhóm lớn hơn bên trái), cột c lấy từ nhóm c, ô giữa = 0. */
export function generateCard(R: Interval[], rng: Rng): Card {
  const total = intervalsSize(R)
  const base = Math.floor(total / 5)
  const extra = total % 5
  const card: Card = Array.from({ length: 5 }, () => Array<number>(5).fill(0))
  let idx = 0
  for (let c = 0; c < 5; c++) {
    const size = base + (c < extra ? 1 : 0)
    const need = c === 2 ? 4 : 5
    const col = sampleIndices(rng, idx, idx + size - 1, need)
      .map((k) => nthInIntervals(R, k))
      .sort((x, y) => x - y)
    idx += size
    if (c === 2) col.splice(2, 0, 0)
    for (let r = 0; r < 5; r++) card[r][c] = col[r]
  }
  return card
}

/**
 * Bốc ngẫu nhiên một số trong R mà `excluded(n)` là false. `excludedCount` = số phần tử của R bị loại.
 * R lớn thì lấy mẫu loại bỏ; R nhỏ (hoặc gần cạn) thì duyệt.
 */
export function drawFromRanges(R: Interval[], excluded: (n: number) => boolean, excludedCount: number, rng: Rng): number | null {
  const total = intervalsSize(R)
  const left = total - excludedCount
  if (left <= 0) return null
  if (total > 5000 && left * 4 > total) {
    for (let i = 0; i < 200; i++) {
      const n = nthInIntervals(R, randInt(rng, 0, total - 1))
      if (!excluded(n)) return n
    }
  }
  if (total > 200_000) {
    // cực hiếm: duyệt từ vị trí ngẫu nhiên
    const startK = randInt(rng, 0, total - 1)
    for (let i = 0; i < total; i++) {
      const n = nthInIntervals(R, (startK + i) % total)
      if (!excluded(n)) return n
    }
    return null
  }
  const pool: number[] = []
  for (const [lo, hi] of R) for (let n = lo; n <= hi; n++) if (!excluded(n)) pool.push(n)
  return pool.length ? pick(rng, pool) : null
}

export type MathProblem = { operator: Operator; a: number; b: number; text: string }

const SYMBOL: Record<Operator, string> = { '+': '+', '-': '−', x: '×', ':': ':' }

/** Sinh phép tính có kết quả n, mọi số ≤ M. */
export function generateProblem(n: number, ops: Ops, rng: Rng, maxNumber = DEFAULT_MAX_NUMBER): MathProblem {
  const M = maxNumber
  const cands: Operator[] = []
  if (ops.add && n >= 2 && n <= M) cands.push('+')
  if (ops.sub && n >= 1 && n <= M - 1) cands.push('-')
  const mulPairs: [number, number][] = []
  for (let a = 1; a <= 10; a++) for (let b = 1; b <= 10; b++) if (a * b === n && n <= M) mulPairs.push([a, b])
  if (ops.mul && mulPairs.length) cands.push('x')
  const divBs: number[] = []
  if (n >= 1 && n <= 10) for (let b = n === 1 ? 1 : 2; b <= 10; b++) if (n * b <= M) divBs.push(b)
  if (ops.div && divBs.length) cands.push(':')
  const op = pick(rng, cands)
  let a: number
  let b: number
  if (op === '+') {
    a = randInt(rng, 1, n - 1)
    b = n - a
  } else if (op === '-') {
    b = randInt(rng, 1, M - n)
    a = n + b
  } else if (op === 'x') {
    const no1 = mulPairs.filter(([x, y]) => x !== 1 && y !== 1)
    ;[a, b] = pick(rng, no1.length ? no1 : mulPairs)
  } else {
    b = pick(rng, divBs)
    a = n * b
  }
  return { operator: op, a, b, text: `${a} ${SYMBOL[op]} ${b} = ?` }
}

export const OPTION_KEYS: OptionKey[] = ['A', 'B', 'C', 'D']

/** Sinh 4 đáp án trong 1–M; tránh các đáp án sai đã dùng và đổi vị trí đáp án đúng so với lần trước. */
export function generateOptions(
  n: number,
  usedWrong: Set<number>,
  prevCorrectIndex: number | null,
  rng: Rng,
  maxNumber = DEFAULT_MAX_NUMBER,
  problem?: Pick<MathProblem, 'operator' | 'a' | 'b'>,
): { values: number[]; correctIndex: number } {
  const M = maxNumber
  const ok = (v: number, chosen: Set<number>) => Number.isInteger(v) && v >= 1 && v <= M && v !== n && !usedWrong.has(v) && !chosen.has(v)
  const pool = new Set<number>()
  const cands = [n + 1, n - 1, n + 2, n - 2, n + 10, n - 10]
  if (n >= 10 && n <= 99 && n % 10 !== Math.floor(n / 10)) cands.push((n % 10) * 10 + Math.floor(n / 10))
  if (problem) {
    const { operator: op, a, b } = problem
    if (op === '+') cands.push(a - b)
    if (op === '-') cands.push(a + b)
    if (op === 'x') cands.push(a * (b + 1), a * (b - 1), (a + 1) * b, (a - 1) * b)
  }
  for (const v of cands) if (ok(v, pool)) pool.add(v)
  let wrong = shuffle(rng, [...pool]).slice(0, 3)
  const chosen = new Set(wrong)
  const fill = (lo: number, hi: number, tries: number) => {
    for (let i = 0; wrong.length < 3 && i < tries; i++) {
      const v = randInt(rng, lo, hi)
      if (ok(v, chosen)) {
        chosen.add(v)
        wrong.push(v)
      }
    }
  }
  fill(Math.max(1, n - 15), Math.min(M, n + 15), 500)
  fill(1, M, 500) // vẫn cạn thì mở rộng ra cả 1–M
  // Dự phòng cực hiếm: nới điều kiện usedWrong.
  for (let v = 1; wrong.length < 3 && v <= M; v++) if (v !== n && !chosen.has(v)) {
    chosen.add(v)
    wrong.push(v)
  }
  wrong = shuffle(rng, wrong)
  const positions = [0, 1, 2, 3].filter((i) => i !== prevCorrectIndex)
  const correctIndex = pick(rng, positions)
  const values = wrong.slice()
  values.splice(correctIndex, 0, n)
  return { values, correctIndex }
}

/** 12 đường thắng. */
export const LINES: { line: Line; cells: Cell[] }[] = (() => {
  const out: { line: Line; cells: Cell[] }[] = []
  for (let i = 0; i < 5; i++) out.push({ line: { type: 'row', index: i }, cells: [0, 1, 2, 3, 4].map((c) => [i, c] as Cell) })
  for (let i = 0; i < 5; i++) out.push({ line: { type: 'col', index: i }, cells: [0, 1, 2, 3, 4].map((r) => [r, i] as Cell) })
  out.push({ line: { type: 'diag', index: 0 }, cells: [0, 1, 2, 3, 4].map((k) => [k, k] as Cell) })
  out.push({ line: { type: 'diag', index: 1 }, cells: [0, 1, 2, 3, 4].map((k) => [k, 4 - k] as Cell) })
  return out
})()

/** Các ô đã khoanh (không gồm FREE). */
export function markedCells(card: Card, drawn: Set<number>): Cell[] {
  const out: Cell[] = []
  for (let r = 0; r < 5; r++) for (let c = 0; c < 5; c++) if (card[r][c] !== 0 && drawn.has(card[r][c])) out.push([r, c])
  return out
}

export function winningLines(card: Card, drawn: Set<number>): Line[] {
  const isMarked = ([r, c]: Cell) => card[r][c] === 0 || drawn.has(card[r][c])
  return LINES.filter((l) => l.cells.every(isMarked)).map((l) => l.line)
}

export function findCell(card: Card, n: number): Cell | null {
  for (let r = 0; r < 5; r++) for (let c = 0; c < 5; c++) if (card[r][c] === n) return [r, c]
  return null
}

const ALNUM = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
/** Id/token ngẫu nhiên (crypto.randomUUID không có trên http LAN). */
export function randomId(len = 22): string {
  let s = ''
  for (let i = 0; i < len; i++) s += ALNUM[Math.floor(Math.random() * ALNUM.length)]
  return s
}
