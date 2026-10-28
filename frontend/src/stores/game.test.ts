import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type {
  Card, ClientMessageMap, ClientMessageType, PlayerInfo, Question, Role, ServerMessageMap, ServerMessageType, Snapshot,
} from '@/api/contract'
import type { ConnectionStatus, GameClient, ServerHandler } from '@/api/gameClient'
import { ServerEmitter } from '@/api/emitter'
import { useGameStore } from './game'

/** Client giả để đẩy từng sự kiện vào store. */
class FakeClient implements GameClient {
  emitter = new ServerEmitter()
  sent: { type: ClientMessageType; data: unknown }[] = []
  connected: { pin: string; role: Role; token: string } | null = null
  connect(pin: string, role: Role, token: string) {
    this.connected = { pin, role, token }
  }
  on<T extends ServerMessageType>(type: T, fn: ServerHandler<T>) {
    return this.emitter.on(type, fn)
  }
  onStatus(fn: (s: ConnectionStatus, code?: number) => void) {
    return this.emitter.onStatus(fn)
  }
  send<T extends ClientMessageType>(type: T, data: ClientMessageMap[T]) {
    this.sent.push({ type, data })
  }
  close() {}
  push<T extends ServerMessageType>(type: T, data: ServerMessageMap[T]) {
    this.emitter.emit(type, data)
  }
}

const me: PlayerInfo = { id: 'p1', nickname: 'Na', avatar_id: 'cat', connected: true }
const bin: PlayerInfo = { id: 'p2', nickname: 'Bin', avatar_id: 'fox', connected: true }
const card: Card = [
  [1, 21, 41, 61, 81],
  [2, 22, 42, 62, 82],
  [3, 23, 0, 63, 83],
  [4, 24, 44, 64, 84],
  [5, 25, 45, 65, 85],
]
const config = { operations: { add: true, sub: true, mul: true, div: true }, timer_seconds: 0, max_wrong: 2, reveal_seconds: 5, draw_only_card_numbers: true }
const snapshot = (over: Partial<Snapshot> = {}): Snapshot => ({
  pin: '4729', picture_code: ['apple', 'car', 'fish'], phase: 'lobby', join_url: 'http://192.168.1.15:8080/play/4729',
  config, players: [me, bin], answerer_mode: null, fixed_player_id: null, drawn: [], question: null, reveal: null, winners: [],
  me, card, marked: [], ...over,
})
const question = (over: Partial<Question> = {}): Question => ({
  question_id: 'q1', attempt: 1, text: '7 × 8 = ?', operator: 'x', a: 7, b: 8,
  options: [{ key: 'A', value: 54 }, { key: 'B', value: 56 }, { key: 'C', value: 57 }, { key: 'D', value: 66 }],
  answerer: me, deadline: null, ...over,
})

describe('game store áp dụng chuỗi sự kiện', () => {
  let c: FakeClient
  let game: ReturnType<typeof useGameStore>
  beforeEach(() => {
    setActivePinia(createPinia())
    game = useGameStore()
    c = new FakeClient()
    game.connect('4729', 'player', 'tok', c)
  })

  it('snapshot rồi trọn một ván: start → sai → đúng → reveal → ready → bingo → ván mới', () => {
    expect(c.connected).toEqual({ pin: '4729', role: 'player', token: 'tok' })
    c.push('snapshot', snapshot())
    expect(game.ready).toBe(true)
    expect(game.phase).toBe('lobby')
    expect(game.card).toEqual(card)

    // Bắt đầu: game_started → phase_changed{question} → question{new}
    c.push('game_started', { answerer_mode: 'random', fixed_player_id: null })
    c.push('phase_changed', { phase: 'question' })
    c.push('question', { question: question(), reason: 'new' })
    expect(game.answererMode).toBe('random')
    expect(game.isMyTurn).toBe(true)

    // Trả lời: khóa nút đến khi có answer_result
    game.submitAnswer('A')
    expect(c.sent).toEqual([{ type: 'submit_answer', data: { question_id: 'q1', attempt: 1, key: 'A' } }])
    expect(game.answerLocked).toBe(true)
    game.submitAnswer('B') // bị khóa, không gửi thêm
    expect(c.sent).toHaveLength(1)

    c.push('answer_result', { question_id: 'q1', attempt: 1, player_id: 'p1', key: 'A', value: 54, correct: false })
    expect(game.answerLocked).toBe(false)
    c.push('question', { question: question({ attempt: 2 }), reason: 'wrong' })
    expect(game.question?.attempt).toBe(2)
    expect(game.questionReason).toBe('wrong')

    // Đúng: answer_result → number_drawn → cell_marked → phase_changed{reveal} → reveal
    game.submitAnswer('B')
    c.push('answer_result', { question_id: 'q1', attempt: 2, player_id: 'p1', key: 'B', value: 56, correct: true })
    c.push('number_drawn', { number: 44, drawn: [44] })
    c.push('cell_marked', { number: 44, cell: [3, 2] })
    c.push('phase_changed', { phase: 'reveal' })
    const rv = { number: 44, seconds_per_card: 5, started_at: new Date().toISOString(), items: [{ player_id: 'p1', nickname: 'Na', avatar_id: 'cat', card, marked_before: [], new_cell: [3, 2] as [number, number] }] }
    c.push('reveal', rv)
    expect(game.drawn).toEqual([44])
    expect(game.marked).toEqual([[3, 2]])
    expect(game.lastMarkedCell).toEqual([3, 2])
    expect(game.markSeq).toBe(1)
    expect(game.question).toBeNull()
    expect(game.reveal).toEqual(rv)
    expect(game.answerLocked).toBe(false)

    // Hết reveal, chưa bingo
    c.push('phase_changed', { phase: 'ready' })
    expect(game.reveal).toBeNull()

    // Bỏ qua: question_skipped → phase_changed{ready}
    c.push('phase_changed', { phase: 'question' })
    c.push('question', { question: question({ question_id: 'q2', answerer: bin }), reason: 'new' })
    expect(game.isMyTurn).toBe(false)
    game.submitAnswer('A') // không phải lượt mình: không gửi
    expect(c.sent).toHaveLength(2)
    c.push('question_skipped', { question_id: 'q2', number: 23 })
    c.push('phase_changed', { phase: 'ready' })
    expect(game.lastSkipped?.number).toBe(23)
    expect(game.question).toBeNull()

    // Bingo: phase_changed{finished} → game_over
    c.push('phase_changed', { phase: 'finished' })
    const winner = { player_id: 'p1', nickname: 'Na', avatar_id: 'cat', card, marked: [[3, 2]] as [number, number][], lines: [{ type: 'col' as const, index: 2 }] }
    c.push('game_over', { reason: 'bingo', winners: [winner] })
    expect(game.gameOverReason).toBe('bingo')
    expect(game.isWinner).toBe(true)

    // Ván mới: snapshot cho tất cả
    c.push('snapshot', snapshot({ card: card.map((r) => r.slice().reverse()) }))
    expect(game.phase).toBe('lobby')
    expect(game.drawn).toEqual([])
    expect(game.winners).toEqual([])
    expect(game.marked).toEqual([])
    expect(game.lastMarkedCell).toBeNull()
  })

  it('cell_marked trùng không nhân đôi ô; your_card thay vé và bỏ khoanh', () => {
    c.push('snapshot', snapshot({ phase: 'reveal', drawn: [44], marked: [[3, 2]] }))
    c.push('cell_marked', { number: 44, cell: [3, 2] })
    expect(game.marked).toEqual([[3, 2]])
    c.push('config_updated', { config: { ...config, max_wrong: 3 } })
    c.push('your_card', { card, marked: [] })
    expect(game.config?.max_wrong).toBe(3)
    expect(game.marked).toEqual([])
  })

  it('players_updated cập nhật me; join_url_updated; kicked / room_closed / mã đóng', () => {
    c.push('snapshot', snapshot())
    c.push('players_updated', { players: [{ ...me, nickname: 'Na' , connected: false }, bin] })
    expect(game.me?.connected).toBe(false)
    c.push('join_url_updated', { join_url: 'http://10.0.0.2:8080/play/4729' })
    expect(game.joinUrl).toBe('http://10.0.0.2:8080/play/4729')
    expect(game.ended).toBeNull()
    c.push('kicked', {})
    expect(game.ended).toBe('kicked')

    const c2 = new FakeClient()
    game.connect('4729', 'player', 'tok', c2)
    expect(game.ended).toBeNull()
    expect(game.ready).toBe(false)
    c2.push('room_closed', { reason: 'closed_by_host' })
    expect(game.ended).toBe('closed')

    const c3 = new FakeClient()
    game.connect('4729', 'host', 'bad', c3)
    c3.emitter.emitStatus('closed', 4401)
    expect(game.ended).toBe('bad_token')

    const c4 = new FakeClient()
    game.connect('4729', 'player', 'tok', c4)
    c4.emitter.emitStatus('closed', 4409)
    expect(game.ended).toBe('replaced')
  })

  it('error mở khóa nút; Help gửi request_help một lần', () => {
    c.push('snapshot', snapshot({ phase: 'question', question: question() }))
    game.requestHelp()
    game.requestHelp()
    expect(c.sent).toEqual([{ type: 'request_help', data: { question_id: 'q1' } }])
    c.push('error', { code: 'stale_question', message: '' })
    expect(game.answerLocked).toBe(false)
    expect(game.lastError?.code).toBe('stale_question')
  })

  it('ước lượng lệch đồng hồ từ reveal mới (không dùng snapshot)', () => {
    const skewed = new Date(Date.now() + 60_000).toISOString()
    c.push('snapshot', snapshot({ phase: 'reveal', reveal: { number: 1, seconds_per_card: 5, started_at: skewed, items: [] } }))
    expect(game.clockOffset).toBe(0)
    c.push('reveal', { number: 2, seconds_per_card: 5, started_at: skewed, items: [] })
    expect(Math.abs(game.clockOffset - 60_000)).toBeLessThan(1000)
  })
})
