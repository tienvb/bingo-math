import { describe, expect, it } from 'vitest'
import type { Reveal, RevealItem } from '@/api/contract'
import { estimateOffset, revealPosition, secondsLeft } from './time'

const item = (id: string): RevealItem => ({
  player_id: id, nickname: id, avatar_id: 'cat', card: [[0]], marked_before: [], new_cell: [0, 0],
})
const T0 = Date.parse('2026-10-28T10:00:00.000Z')
const reveal = (n: number, secs = 5): Reveal => ({
  number: 56, seconds_per_card: secs, started_at: new Date(T0).toISOString(), items: Array.from({ length: n }, (_, i) => item(`p${i}`)),
})

describe('revealPosition: floor((now − started_at) / seconds_per_card)', () => {
  it('vé đầu tiên ngay khi bắt đầu', () => {
    expect(revealPosition(reveal(3), T0)).toEqual({ index: 0, elapsedInCard: 0, done: false })
  })
  it('mỗi vé đúng 5 giây', () => {
    expect(revealPosition(reveal(3), T0 + 4999).index).toBe(0)
    expect(revealPosition(reveal(3), T0 + 5000).index).toBe(1)
    expect(revealPosition(reveal(3), T0 + 12_500)).toEqual({ index: 2, elapsedInCard: 2500, done: false })
  })
  it('mở lại tab giữa chừng vẫn đúng vé', () => {
    expect(revealPosition(reveal(5, 4), T0 + 9000).index).toBe(2)
  })
  it('hết thời gian: kẹp ở vé cuối, done = true (server quyết định lúc chuyển phase)', () => {
    expect(revealPosition(reveal(3), T0 + 60_000)).toMatchObject({ index: 2, done: true })
  })
  it('đồng hồ client chậm hơn started_at: không âm', () => {
    expect(revealPosition(reveal(3), T0 - 3000)).toMatchObject({ index: 0, elapsedInCard: 0 })
  })
  it('không ai có số', () => {
    expect(revealPosition(reveal(0), T0 + 1000)).toMatchObject({ index: 0, done: false })
    expect(revealPosition(reveal(0), T0 + 6000).done).toBe(true)
  })
})

describe('secondsLeft / estimateOffset', () => {
  it('làm tròn lên, không âm, null khi tắt', () => {
    const d = new Date(T0 + 10_000).toISOString()
    expect(secondsLeft(d, T0)).toBe(10)
    expect(secondsLeft(d, T0 + 9_001)).toBe(1)
    expect(secondsLeft(d, T0 + 20_000)).toBe(0)
    expect(secondsLeft(null, T0)).toBeNull()
  })
  it('bỏ qua lệch nhỏ do mạng, giữ lệch lớn do đồng hồ máy', () => {
    expect(estimateOffset(T0 + 300, T0)).toBe(0)
    expect(estimateOffset(T0 + 30_000, T0)).toBe(30_000)
    expect(estimateOffset(T0 - 30_000, T0)).toBe(-30_000)
  })
})
