import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { GameConfig, Role, ServerMessageType } from '../contract'
import { ApiError } from '../errors'
import { MockServer } from './server'
import { MockGameClient } from './mockClient'
import { createMockRestApi } from './mockRest'
import { availableRanges, generateCard, generateOptions, generateProblem, isValidConfig, normalizeConfig } from './algorithms'
import { availableCount, intervalsSize } from '@/utils/numberRange'
import { configIssues } from '@/utils/config'

const CONFIG: GameConfig = {
  operations: { add: true, sub: true, mul: true, div: true },
  timer_seconds: 0,
  max_wrong: 2,
  reveal_seconds: 5,
  draw_only_card_numbers: true,
  max_number: 100,
  next_mode: 'manual',
}

const ALL_TYPES: ServerMessageType[] = [
  'snapshot', 'phase_changed', 'players_updated', 'config_updated', 'join_url_updated', 'your_card',
  'game_started', 'question', 'answer_result', 'number_drawn', 'cell_marked', 'reveal',
  'question_skipped', 'game_over', 'kicked', 'room_closed', 'error', 'pong',
]

function record(client: MockGameClient) {
  const log: { type: ServerMessageType; data: any }[] = []
  for (const t of ALL_TYPES) client.on(t, (data) => log.push({ type: t, data }))
  return log
}

const tick = (ms = 0) => vi.advanceTimersByTimeAsync(ms)

describe('mock server', () => {
  let server: MockServer
  let hostToken = ''
  beforeEach(() => {
    vi.useFakeTimers()
    server = new MockServer()
  })
  afterEach(() => {
    server.reset()
    vi.useRealTimers()
  })

  it('sinh vé đúng cột, không trùng, ô giữa là 0', () => {
    const R = availableRanges(CONFIG.operations, 100)
    for (let i = 0; i < 200; i++) {
      const card = generateCard(R, Math.random)
      expect(card[2][2]).toBe(0)
      const flat = card.flat().filter((n) => n)
      expect(new Set(flat).size).toBe(24)
      for (let c = 0; c < 5; c++)
        for (let r = 0; r < 5; r++) if (card[r][c]) expect(Math.ceil(card[r][c] / 20) - 1).toBe(c)
    }
  })

  it('chạy trọn luồng lobby → question → reveal → ready → finished', async () => {
    const api = createMockRestApi(server, () => hostToken)
    const created = api.createRoom({ config: CONFIG, join_base_url: 'http://192.168.1.15:8080' })
    await tick(100)
    const room = await created
    hostToken = room.host_token
    expect(room.pin).toMatch(/^\d{4}$/)
    expect(room.join_url).toBe(`http://192.168.1.15:8080/play/${room.pin}`)
    expect(new Set(room.picture_code).size).toBe(3)

    // lookup mã hình
    const lk = api.lookup(room.picture_code)
    await tick(100)
    expect((await lk).pin).toBe(room.pin)

    // người chơi thật vào phòng
    const joinP = api.join(room.pin, { nickname: '  Bé Na  ', avatar_id: 'cat' })
    await tick(100)
    const joined = await joinP
    const dupP = api.join(room.pin, { nickname: 'bé na', avatar_id: 'cat' }).catch((e) => e)
    await tick(100)
    expect(((await dupP) as ApiError).code).toBe('nickname_taken')

    // avatar_counts: chỉ gồm nhân vật có ≥ 1 người chọn (3 bot: cat, fox, unicorn + người chơi chọn cat)
    const infoP = api.getRoom(room.pin)
    await tick(100)
    const info = await infoP
    expect(info.player_count).toBe(4)
    expect(info.avatar_counts).toEqual({ cat: 2, fox: 1, unicorn: 1 })

    const connect = (role: Role, token: string) => {
      const c = new MockGameClient(server)
      const log = record(c)
      c.connect(room.pin, role, token)
      return { c, log }
    }
    const host = connect('host', room.host_token)
    const screen = connect('screen', room.screen_token)
    const player = connect('player', joined.player_token)
    await tick(0)

    const snap = player.log.find((m) => m.type === 'snapshot')!.data
    expect(snap.phase).toBe('lobby')
    expect(snap.players).toHaveLength(4) // 3 người chơi ảo + 1
    expect(snap.me.id).toBe(joined.player_id)
    expect(snap.card[2][2]).toBe(0)
    expect(screen.log[0].type).toBe('snapshot')

    // token sai bị đóng 4401
    const bad = new MockGameClient(server)
    let badCode: number | undefined
    bad.onStatus((s, code) => s === 'closed' && (badCode = code))
    bad.connect(room.pin, 'host', 'wrong')
    await tick(0)
    expect(badCode).toBe(4401)

    // bắt đầu
    const startP = api.start(room.pin, { answerer_mode: 'random', fixed_player_id: null })
    await tick(100)
    await startP
    expect(host.log.map((m) => m.type).slice(-3)).toEqual(['game_started', 'phase_changed', 'question'])

    const phases = new Set<string>()
    let correctCount = 0
    for (let guard = 0; guard < 2000; guard++) {
      const phase = [...host.log].reverse().find((m) => m.type === 'phase_changed')!.data.phase as string
      phases.add(phase)
      if (phase === 'finished') break
      if (phase === 'question') {
        const q = [...host.log].reverse().find((m) => m.type === 'question')!.data.question
        expect(q).not.toHaveProperty('correct')
        if (q.answerer.id === joined.player_id) {
          player.c.send('submit_answer', { question_id: q.question_id, attempt: q.attempt, key: server.peekCorrectKey(room.pin)! })
          await tick(0)
        } else {
          await tick(2000) // người chơi ảo trả lời sau 2 giây
        }
      } else if (phase === 'reveal') {
        correctCount++
        await tick(1000)
      } else if (phase === 'ready') {
        const p = api.next(room.pin)
        await tick(100)
        await p
      }
    }
    expect([...phases].sort()).toEqual(['finished', 'question', 'ready', 'reveal'].sort())
    expect(correctCount).toBeGreaterThan(0)

    // Thứ tự sự kiện khi trả lời đúng
    const types = host.log.map((m) => m.type)
    const iCorrect = host.log.findIndex((m) => m.type === 'answer_result' && m.data.correct)
    expect(types.slice(iCorrect, iCorrect + 4)).toEqual(['answer_result', 'number_drawn', 'phase_changed', 'reveal'])
    expect(host.log[iCorrect + 2].data.phase).toBe('reveal')

    // Người chơi: cell_marked nằm giữa number_drawn và phase_changed {reveal}
    const ptypes = player.log.map((m) => m.type)
    const iMark = ptypes.indexOf('cell_marked')
    if (iMark >= 0) {
      expect(ptypes[iMark - 1]).toBe('number_drawn')
      expect(ptypes[iMark + 1]).toBe('phase_changed')
      expect(ptypes[iMark + 2]).toBe('reveal')
    }

    // Kết thúc ván
    const over = host.log.find((m) => m.type === 'game_over')!.data
    expect(over.reason).toBe('bingo')
    expect(over.winners.length).toBeGreaterThan(0)
    for (const w of over.winners) {
      expect(w.lines.length).toBeGreaterThan(0)
      expect(w.marked.some(([r, c]: number[]) => r === 2 && c === 2)).toBe(false) // FREE không nằm trong marked
    }
    for (const m of host.log.filter((x) => x.type === 'reveal'))
      for (const it of m.data.items) expect(it.marked_before.some(([r, c]: number[]) => r === 2 && c === 2)).toBe(false)

    // Ván mới → snapshot lobby cho tất cả
    const nr = api.newRound(room.pin, {})
    await tick(100)
    await nr
    const last = player.log[player.log.length - 1]
    expect(last.type).toBe('snapshot')
    expect(last.data.phase).toBe('lobby')
    expect(last.data.drawn).toEqual([])

    // Cùng người chơi mở tab khác: kết nối cũ bị đóng 4409, không tự kết nối lại
    let replacedCode: number | undefined
    player.c.onStatus((s, code) => s === 'closed' && (replacedCode = code))
    const player2 = connect('player', joined.player_token)
    await tick(0)
    expect(replacedCode).toBe(4409)
    await tick(5000)
    expect(player2.log.filter((m) => m.type === 'snapshot')).toHaveLength(1)
    player.c = player2.c
    player.log = player2.log

    // Đóng phòng
    let closedCode: number | undefined
    player.c.onStatus((s, code) => s === 'closed' && (closedCode = code))
    const cl = api.closeRoom(room.pin)
    await tick(100)
    await cl
    expect(player.log[player.log.length - 1]).toEqual({ type: 'room_closed', data: { reason: 'closed_by_host' } })
    expect(closedCode).toBe(4410)
    const gone = api.getRoom(room.pin).catch((e) => e)
    await tick(100)
    expect(((await gone) as ApiError).code).toBe('room_not_found')
  })

  it('sai 2 lần thì đổi người, Help đổi người, Bỏ qua về ready', async () => {
    server.botCount = 0
    const api = createMockRestApi(server, () => hostToken)
    const cp = api.createRoom({ config: CONFIG, join_base_url: 'http://localhost:5173' })
    await tick(100)
    const room = await cp
    hostToken = room.host_token
    const players: { id: string; c: MockGameClient; log: ReturnType<typeof record> }[] = []
    for (const name of ['A', 'B', 'C']) {
      const jp = api.join(room.pin, { nickname: name, avatar_id: 'cat' })
      await tick(100)
      const j = await jp
      const c = new MockGameClient(server)
      const log = record(c)
      c.connect(room.pin, 'player', j.player_token)
      players.push({ id: j.player_id, c, log })
    }
    await tick(0)
    const sp = api.start(room.pin, { answerer_mode: 'fixed', fixed_player_id: players[0].id })
    await tick(100)
    await sp
    const lastQ = () => [...players[0].log].reverse().find((m) => m.type === 'question')!.data
    let q = lastQ()
    expect(q.reason).toBe('new')
    expect(q.question.answerer.id).toBe(players[0].id)

    const wrongKey = () => (['A', 'B', 'C', 'D'] as const).find((k) => k !== server.peekCorrectKey(room.pin))!
    players[0].c.send('submit_answer', { question_id: q.question.question_id, attempt: q.question.attempt, key: wrongKey() })
    await tick(0)
    q = lastQ()
    expect(q.reason).toBe('wrong')
    expect(q.question.answerer.id).toBe(players[0].id)
    players[0].c.send('submit_answer', { question_id: q.question.question_id, attempt: q.question.attempt, key: wrongKey() })
    await tick(0)
    q = lastQ()
    expect(q.reason).toBe('max_wrong')
    expect(q.question.answerer.id).not.toBe(players[0].id)

    // Người không đến lượt gửi → not_your_turn
    players[0].c.send('submit_answer', { question_id: q.question.question_id, attempt: q.question.attempt, key: 'A' })
    await tick(0)
    expect(players[0].log[players[0].log.length - 1]).toMatchObject({ type: 'error', data: { code: 'not_your_turn' } })

    const hp = api.help(room.pin)
    await tick(100)
    await hp
    expect(lastQ().reason).toBe('help')

    const skp = api.skip(room.pin)
    await tick(100)
    await skp
    const tail = players[0].log.slice(-2).map((m) => m.type)
    expect(tail).toEqual(['question_skipped', 'phase_changed'])
  })

  it('max_number: |R| theo spec mục 1, kiểm tra form, thiếu field thì dùng mặc định', () => {
    const only = (k: keyof GameConfig['operations']) => ({ add: false, sub: false, mul: false, div: false, [k]: true })
    expect(availableCount(only('mul'), 100)).toBe(42)
    expect(availableCount(only('mul'), 31)).toBe(22)
    expect(availableCount(CONFIG.operations, 100)).toBe(100)
    expect(availableCount(only('add'), 1_000_000)).toBe(999_999)
    expect(configIssues({ ...CONFIG, operations: only('mul'), max_number: 31 })).toEqual(['too_few_numbers'])
    expect(configIssues({ ...CONFIG, max_number: 30 })).toEqual(['max_number_too_small'])
    expect(configIssues({ ...CONFIG, max_number: Number.NaN })).toEqual(['max_number_invalid'])
    expect(configIssues({ ...CONFIG, max_number: 31 })).toEqual([])
    const { max_number: _m, next_mode: _n, ...old } = CONFIG
    const filled = normalizeConfig(old)!
    expect(filled.max_number).toBe(100)
    expect(filled.next_mode).toBe('auto')
    expect(isValidConfig(filled)).toBe(true)
    expect(isValidConfig({ ...CONFIG, max_number: 30 })).toBe(false)
    // giới hạn kỹ thuật 2^53 − 1 (CHANGELOG 2026-10-29)
    expect(configIssues({ ...CONFIG, max_number: Number.MAX_SAFE_INTEGER })).toEqual([])
    expect(configIssues({ ...CONFIG, max_number: Number('9007199254740993') })).toEqual(['max_number_too_large'])
    expect(configIssues({ ...CONFIG, max_number: 100.5 })).toEqual(['max_number_invalid'])
    expect(isValidConfig({ ...CONFIG, max_number: Number.MAX_SAFE_INTEGER + 2 })).toBe(false)
  })

  it('M rất lớn: vé, phép tính, đáp án đều ≤ M, không dựng mảng đầy đủ', () => {
    const M = 1_000_000_000
    const R = availableRanges(CONFIG.operations, M)
    expect(R.length).toBeLessThan(5) // vài đoạn, không phải 10^9 phần tử
    expect(intervalsSize(R)).toBe(M)
    for (let i = 0; i < 50; i++) {
      const card = generateCard(R, Math.random)
      const flat = card.flat().filter((n) => n)
      expect(new Set(flat).size).toBe(24)
      for (let c = 0; c < 5; c++)
        for (let r = 0; r < 5; r++) {
          const n = card[r][c]
          if (!n) continue
          expect(n).toBeLessThanOrEqual(M)
          expect(Math.ceil(n / (M / 5)) - 1).toBe(c)
          if (r > 0 && card[r - 1][c]) expect(n).toBeGreaterThan(card[r - 1][c])
        }
      const n = flat[i % 24]
      const p = generateProblem(n, CONFIG.operations, Math.random, M)
      for (const v of [p.a, p.b]) expect(v).toBeLessThanOrEqual(M)
      const o = generateOptions(n, new Set(), null, Math.random, M, p)
      expect(o.values).toContain(n)
      expect(new Set(o.values).size).toBe(4)
      for (const v of o.values) expect(v >= 1 && v <= M).toBe(true)
    }
    // M nhỏ: chia vẫn ≤ M
    for (let i = 0; i < 200; i++) {
      const p = generateProblem(7, { add: false, sub: false, mul: false, div: true }, Math.random, 31)
      expect(p.a).toBeLessThanOrEqual(31)
    }
  })

  it('next_mode auto: hết reveal → phase_changed{question} → question{new}; Bỏ qua → question_skipped → question{new}', async () => {
    server.botCount = 0
    const api = createMockRestApi(server, () => hostToken)
    const cp = api.createRoom({ config: { ...CONFIG, next_mode: 'auto', reveal_seconds: 3, draw_only_card_numbers: false, max_number: 1_000_000 }, join_base_url: 'http://localhost:5173' })
    await tick(100)
    const room = await cp
    hostToken = room.host_token
    const jp = api.join(room.pin, { nickname: 'A', avatar_id: 'cat' })
    await tick(100)
    const j = await jp
    const c = new MockGameClient(server)
    const log = record(c)
    c.connect(room.pin, 'player', j.player_token)
    await tick(0)
    const sp = api.start(room.pin, { answerer_mode: 'random', fixed_player_id: null })
    await tick(100)
    await sp

    // Bỏ qua ở auto: không có phase_changed
    let from = log.length
    const skp = api.skip(room.pin)
    await tick(100)
    await skp
    expect(log.slice(from).map((m) => m.type)).toEqual(['question_skipped', 'question'])
    expect(log[log.length - 1].data.reason).toBe('new')

    // Trả lời đúng → reveal → (3 giây × max(số vé, 1)) → phase_changed{question} → question{new}
    const q = log[log.length - 1].data.question
    for (const v of [q.a, q.b, ...q.options.map((o: { value: number }) => o.value)]) expect(v).toBeLessThanOrEqual(1_000_000)
    c.send('submit_answer', { question_id: q.question_id, attempt: q.attempt, key: server.peekCorrectKey(room.pin)! })
    await tick(0)
    const rv = [...log].reverse().find((m) => m.type === 'reveal')!.data
    expect(rv.seconds_per_card).toBe(3)
    from = log.length
    await tick(Math.max(rv.items.length, 1) * 3000 - 50)
    expect(log.length).toBe(from) // chưa hết reveal
    await tick(100)
    const after = log.slice(from).map((m) => (m.type === 'phase_changed' ? `phase:${m.data.phase}` : m.type))
    expect(after).toEqual(['phase:question', 'question'])
    expect(log[log.length - 1].data.reason).toBe('new')
    expect(log.some((m) => m.type === 'phase_changed' && m.data.phase === 'ready')).toBe(false)
  })

  it('next_mode auto: chơi tới bingo không bao giờ qua ready', async () => {
    server.botCount = 0
    const api = createMockRestApi(server, () => hostToken)
    const cp = api.createRoom({ config: { ...CONFIG, next_mode: 'auto', reveal_seconds: 2 }, join_base_url: 'http://localhost:5173' })
    await tick(100)
    const room = await cp
    hostToken = room.host_token
    const jp = api.join(room.pin, { nickname: 'A', avatar_id: 'cat' })
    await tick(100)
    const j = await jp
    const c = new MockGameClient(server)
    const log = record(c)
    c.connect(room.pin, 'player', j.player_token)
    await tick(0)
    const sp = api.start(room.pin, { answerer_mode: 'random', fixed_player_id: null })
    await tick(100)
    await sp
    for (let i = 0; i < 40; i++) {
      const last = [...log].reverse().find((m) => m.type === 'phase_changed')!.data.phase
      if (last === 'finished' || last === 'ready') break
      const q = [...log].reverse().find((m) => m.type === 'question')!.data.question
      if (last === 'question') c.send('submit_answer', { question_id: q.question_id, attempt: q.attempt, key: server.peekCorrectKey(room.pin)! })
      await tick(2100)
    }
    const phasesSeen = log.filter((m) => m.type === 'phase_changed').map((m) => m.data.phase)
    expect(phasesSeen).not.toContain('ready')
    expect(phasesSeen[phasesSeen.length - 1]).toBe('finished')
  })

  it('next_mode auto: kho bốc hết khi cần câu mới → phase_changed{ready}', async () => {
    server.botCount = 1
    const api = createMockRestApi(server, () => hostToken)
    const cp = api.createRoom({ config: { ...CONFIG, next_mode: 'auto' }, join_base_url: 'http://localhost:5173' })
    await tick(100)
    const room = await cp
    hostToken = room.host_token
    const c = new MockGameClient(server)
    const log = record(c)
    c.connect(room.pin, 'host', room.host_token)
    const sp = api.start(room.pin, { answerer_mode: 'random', fixed_player_id: null })
    await tick(100)
    await sp
    // Giả lập kho đã hết: mọi số trên vé đều đã ra (chỉ để kiểm nhánh, không qua luật bingo).
    const r = (server as unknown as { rooms: Map<string, { players: { card: number[][] }[]; drawn: number[]; advance(): void; clearAllTimers(): void }> }).rooms.get(room.pin)!
    r.clearAllTimers()
    r.drawn = r.players.flatMap((p) => p.card.flat().filter((n) => n))
    const from = log.length
    r.advance()
    await tick(0)
    expect(log.slice(from).map((m) => m.type)).toEqual(['phase_changed'])
    expect(log[log.length - 1].data.phase).toBe('ready')
  })

  it('next_mode auto: Bỏ qua khi kho chỉ còn số vừa bỏ → hỏi lại số đó (question_skipped → question{new})', async () => {
    server.botCount = 1
    const api = createMockRestApi(server, () => hostToken)
    const cp = api.createRoom({ config: { ...CONFIG, next_mode: 'auto' }, join_base_url: 'http://localhost:5173' })
    await tick(100)
    const room = await cp
    hostToken = room.host_token
    const c = new MockGameClient(server)
    const log = record(c)
    c.connect(room.pin, 'host', room.host_token)
    const sp = api.start(room.pin, { answerer_mode: 'random', fixed_player_id: null })
    await tick(100)
    await sp
    type R = { players: { card: number[][] }[]; drawn: number[]; q: { number: number } | null; clearAllTimers(): void }
    const r = (server as unknown as { rooms: Map<string, R> }).rooms.get(room.pin)!
    const n = r.q!.number
    r.clearAllTimers()
    r.drawn = r.players.flatMap((p) => p.card.flat().filter((x) => x && x !== n)) // chỉ còn n trong kho
    const from = log.length
    const skp = api.skip(room.pin)
    await tick(100)
    await skp
    expect(log.slice(from).map((m) => m.type)).toEqual(['question_skipped', 'question'])
    expect(log[log.length - 1].data.reason).toBe('new')
    expect(r.q!.number).toBe(n)
  })
})
