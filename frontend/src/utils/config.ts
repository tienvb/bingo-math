import type { GameConfig } from '@/api/contract'
import { DEFAULT_MAX_NUMBER, MIN_R_SIZE, availableCount, maxNumberProblem } from './numberRange'

/** Cấu hình mặc định theo spec *Cấu hình phòng (`GameConfig`)*. */
export const DEFAULT_CONFIG: Readonly<GameConfig> = Object.freeze({
  operations: Object.freeze({ add: true, sub: true, mul: true, div: true }) as GameConfig['operations'],
  timer_seconds: 0,
  max_wrong: 2,
  reveal_seconds: 3,
  draw_only_card_numbers: true,
  max_number: DEFAULT_MAX_NUMBER,
  next_mode: 'auto',
})

export function defaultConfig(): GameConfig {
  return { ...DEFAULT_CONFIG, operations: { ...DEFAULT_CONFIG.operations } }
}

/**
 * Bù mặc định cho cấu hình thiếu field (vd. "cấu hình lần trước" lưu từ bản cũ chưa có
 * max_number / next_mode). Field sai kiểu cũng thay bằng mặc định.
 */
export function withConfigDefaults(raw: unknown): GameConfig {
  const d = defaultConfig()
  if (!raw || typeof raw !== 'object') return d
  const r = raw as Partial<Record<keyof GameConfig, unknown>>
  const num = (v: unknown, fb: number) => (typeof v === 'number' && Number.isFinite(v) ? v : fb)
  const ops = (r.operations && typeof r.operations === 'object' ? r.operations : {}) as Partial<Record<keyof GameConfig['operations'], unknown>>
  const bool = (v: unknown, fb: boolean) => (typeof v === 'boolean' ? v : fb)
  return {
    operations: {
      add: bool(ops.add, d.operations.add),
      sub: bool(ops.sub, d.operations.sub),
      mul: bool(ops.mul, d.operations.mul),
      div: bool(ops.div, d.operations.div),
    },
    timer_seconds: num(r.timer_seconds, d.timer_seconds),
    max_wrong: num(r.max_wrong, d.max_wrong),
    reveal_seconds: num(r.reveal_seconds, d.reveal_seconds),
    draw_only_card_numbers: bool(r.draw_only_card_numbers, d.draw_only_card_numbers),
    max_number: num(r.max_number, d.max_number),
    next_mode: r.next_mode === 'manual' || r.next_mode === 'auto' ? r.next_mode : d.next_mode,
  }
}

export type ConfigIssue = 'no_operation' | 'max_number_invalid' | 'max_number_too_small' | 'max_number_too_large' | 'too_few_numbers'

/** Kiểm tra form (spec mục 1): ≥ 1 phép, M nguyên > 30, |R| ≥ 25. Không phải tính đáp án. */
export function configIssues(c: GameConfig): ConfigIssue[] {
  const out: ConfigIssue[] = []
  const anyOp = Object.values(c.operations).some(Boolean)
  if (!anyOp) out.push('no_operation')
  const p = maxNumberProblem(c.max_number)
  if (p === 'not_integer') out.push('max_number_invalid')
  else if (p === 'too_small') out.push('max_number_too_small')
  else if (p === 'too_large') out.push('max_number_too_large')
  else if (anyOp && (availableCount(c.operations, c.max_number) ?? 0) < MIN_R_SIZE) out.push('too_few_numbers')
  return out
}
