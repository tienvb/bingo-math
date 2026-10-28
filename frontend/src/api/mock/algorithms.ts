// Thuật toán đơn giản cho mock server (chỉ chạy trong mock, đóng vai BE).
// UI không được import file này: FE không tự tính đáp án, không tự khoanh ô.

import type { Card, Cell, GameConfig, Line, OptionKey, Operator } from '../contract'

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

/** Tập R: các kết quả có thể theo phép được bật. */
export function availableNumbers(ops: Ops): number[] {
  const s = new Set<number>()
  if (ops.add) for (let n = 2; n <= 100; n++) s.add(n)
  if (ops.sub) for (let n = 1; n <= 99; n++) s.add(n)
  if (ops.mul) for (let a = 1; a <= 10; a++) for (let b = 1; b <= 10; b++) s.add(a * b)
  if (ops.div) for (let n = 1; n <= 10; n++) s.add(n)
  return [...s].sort((x, y) => x - y)
}

export function isValidConfig(c: GameConfig): boolean {
  const o = c.operations
  if (!o || !(o.add || o.sub || o.mul || o.div)) return false
  if (availableNumbers(o).length < 25) return false
  const int = Number.isInteger
  if (!int(c.timer_seconds) || !(c.timer_seconds === 0 || (c.timer_seconds >= 5 && c.timer_seconds <= 120))) return false
  if (!int(c.max_wrong) || c.max_wrong < 1 || c.max_wrong > 5) return false
  if (!int(c.reveal_seconds) || c.reveal_seconds < 2 || c.reveal_seconds > 15) return false
  return typeof c.draw_only_card_numbers === 'boolean'
}

/** Sinh vé 5x5: R chia 5 nhóm liên tiếp, cột c lấy từ nhóm c, ô giữa = 0. */
export function generateCard(R: number[], rng: Rng): Card {
  const groups: number[][] = []
  const base = Math.floor(R.length / 5)
  const extra = R.length % 5
  let idx = 0
  for (let g = 0; g < 5; g++) {
    const size = base + (g < extra ? 1 : 0)
    groups.push(R.slice(idx, idx + size))
    idx += size
  }
  const card: Card = Array.from({ length: 5 }, () => Array<number>(5).fill(0))
  for (let c = 0; c < 5; c++) {
    const need = c === 2 ? 4 : 5
    const col = shuffle(rng, groups[c]).slice(0, need).sort((x, y) => x - y)
    if (c === 2) col.splice(2, 0, 0)
    for (let r = 0; r < 5; r++) card[r][c] = col[r]
  }
  return card
}

export type MathProblem = { operator: Operator; a: number; b: number; text: string }

const SYMBOL: Record<Operator, string> = { '+': '+', '-': '−', x: '×', ':': ':' }

/** Sinh phép tính có kết quả n. */
export function generateProblem(n: number, ops: Ops, rng: Rng): MathProblem {
  const cands: Operator[] = []
  if (ops.add && n >= 2 && n <= 100) cands.push('+')
  if (ops.sub && n >= 1 && n <= 99) cands.push('-')
  const mulPairs: [number, number][] = []
  for (let a = 1; a <= 10; a++) for (let b = 1; b <= 10; b++) if (a * b === n) mulPairs.push([a, b])
  if (ops.mul && mulPairs.length) cands.push('x')
  if (ops.div && n >= 1 && n <= 10) cands.push(':')
  const op = pick(rng, cands)
  let a: number
  let b: number
  if (op === '+') {
    a = randInt(rng, 1, n - 1)
    b = n - a
  } else if (op === '-') {
    b = randInt(rng, 1, 100 - n)
    a = n + b
  } else if (op === 'x') {
    const no1 = mulPairs.filter(([x, y]) => x !== 1 && y !== 1)
    ;[a, b] = pick(rng, no1.length ? no1 : mulPairs)
  } else {
    b = n === 1 ? randInt(rng, 1, 10) : randInt(rng, 2, 10)
    a = n * b
  }
  return { operator: op, a, b, text: `${a} ${SYMBOL[op]} ${b} = ?` }
}

export const OPTION_KEYS: OptionKey[] = ['A', 'B', 'C', 'D']

/** Sinh 4 đáp án; tránh các đáp án sai đã dùng và đổi vị trí đáp án đúng so với lần trước. */
export function generateOptions(
  n: number,
  usedWrong: Set<number>,
  prevCorrectIndex: number | null,
  rng: Rng,
): { values: number[]; correctIndex: number } {
  const ok = (v: number, chosen: Set<number>) => v >= 1 && v <= 100 && v !== n && !usedWrong.has(v) && !chosen.has(v)
  const pool = new Set<number>()
  for (const d of [1, -1, 2, -2, 10, -10]) if (ok(n + d, pool)) pool.add(n + d)
  let wrong = shuffle(rng, [...pool]).slice(0, 3)
  const chosen = new Set(wrong)
  let guard = 0
  while (wrong.length < 3 && guard++ < 1000) {
    const v = randInt(rng, Math.max(1, n - 15), Math.min(100, n + 15))
    if (ok(v, chosen)) {
      chosen.add(v)
      wrong.push(v)
    }
  }
  // Dự phòng cực hiếm: nới điều kiện usedWrong.
  for (let v = 1; wrong.length < 3 && v <= 100; v++) if (v !== n && !chosen.has(v)) {
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
