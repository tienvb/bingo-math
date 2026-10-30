// Mock server: giả lập BE trong bộ nhớ của tab trình duyệt, theo đúng hợp đồng.
// Gồm REST giả (ném ApiError như server thật) và kết nối WS giả (MockConnection).

import type {
  AnswererMode,
  Card,
  ClientMessage,
  CreateRoomRequest,
  CreateRoomResponse,
  ErrorCode,
  GameConfig,
  JoinRequest,
  JoinResponse,
  OptionKey,
  Phase,
  PlayerInfo,
  Question,
  QuestionReason,
  Reveal,
  RevealItem,
  RoomInfoResponse,
  Role,
  RoomIcon,
  ServerMessageMap,
  ServerMessageType,
  Snapshot,
  StartRequest,
  Winner,
} from '../contract'
import { ROOM_ICONS, WS_CLOSE } from '../contract'
import { ApiError } from '../errors'
import {
  OPTION_KEYS,
  availableRanges,
  drawFromRanges,
  findCell,
  generateCard,
  generateOptions,
  generateProblem,
  isValidConfig,
  markedCells,
  normalizeConfig,
  pick,
  randomId,
  shuffle,
  winningLines,
  type Interval,
  type MathProblem,
  type Rng,
} from './algorithms'
import { MOCK_AVATARS } from './avatars'

const MAX_PLAYERS = 30
const MAX_ROOMS = 20
const BOT_ANSWER_MS = 2000
const DISCONNECT_GRACE_MS = 10_000

export const BOT_NAMES = ['Bin', 'Na', 'Tí']

type Timer = ReturnType<typeof setTimeout>

export interface MockConnection {
  role: Role
  playerId?: string
  deliver<T extends ServerMessageType>(type: T, data: ServerMessageMap[T]): void
  /** Server đóng kết nối với mã đóng. */
  terminate(code: number): void
}

type MockPlayer = {
  info: PlayerInfo
  token: string
  card: Card
  bot: boolean
}

/** Dạng tuần tự hóa được (JSON) của một phòng, để tab khác lên làm leader thì khôi phục. */
export type RoomState = {
  room_id: string
  host_token: string
  screen_token: string
  pin: string
  picture_code: RoomIcon[]
  config: GameConfig
  joinBase: string
  phase: Phase
  players: MockPlayer[]
  answerer_mode: AnswererMode | null
  fixed_player_id: string | null
  drawn: number[]
  q: (Omit<QuestionState, 'tried' | 'usedWrong'> & { tried: string[]; usedWrong: number[] }) | null
  reveal: Reveal | null
  winners: Winner[]
  lastSkipped: number | null
}

export type ServerState = { rooms: RoomState[]; closedPins: string[]; closedPictures: string[] }

type QuestionState = {
  question_id: string
  attempt: number
  number: number
  problem: MathProblem
  values: number[]
  correctIndex: number
  answererId: string
  tried: Set<string>
  wrongCount: number
  usedWrong: Set<number>
  deadline: string | null
}

const fail = (status: number, code: ErrorCode, message = code): never => {
  throw new ApiError(status, code, message)
}

export function normalizeJoinBase(raw: unknown): string | null {
  if (typeof raw !== 'string') return null
  try {
    const u = new URL(raw.trim())
    if (u.protocol !== 'http:' && u.protocol !== 'https:') return null
    if (!u.host) return null
    if ((u.pathname && u.pathname !== '/') || u.search || u.hash) return null
    return `${u.protocol}//${u.host}`
  } catch {
    return null
  }
}

function isEasyPin(pin: string): boolean {
  const d = pin.split('').map(Number)
  if (d.every((x) => x === d[0])) return true
  const inc = d.every((x, i) => i === 0 || x === d[i - 1] + 1)
  const dec = d.every((x, i) => i === 0 || x === d[i - 1] - 1)
  return inc || dec
}

class MockRoom {
  room_id = randomId()
  host_token = randomId(43)
  screen_token = randomId(43)
  phase: Phase = 'lobby'
  players: MockPlayer[] = []
  answerer_mode: AnswererMode | null = null
  fixed_player_id: string | null = null
  drawn: number[] = []
  q: QuestionState | null = null
  reveal: Reveal | null = null
  winners: Winner[] = []
  lastSkipped: number | null = null
  conns = new Set<MockConnection>()
  private timers = new Map<string, Timer>()

  constructor(
    readonly server: MockServer,
    readonly pin: string,
    readonly picture_code: RoomIcon[],
    public config: GameConfig,
    public joinBase: string,
  ) {}

  get rng(): Rng {
    return this.server.rng
  }
  get join_url(): string {
    return `${this.joinBase}/play/${this.pin}`
  }
  /** Tập R dạng đoạn số (M có thể rất lớn). */
  get R(): Interval[] {
    return availableRanges(this.config.operations, this.config.max_number)
  }
  /** Thời lượng reveal = max(số vé, 1) × reveal_seconds. */
  revealMs(r: Reveal): number {
    return Math.max(r.items.length, 1) * r.seconds_per_card * 1000
  }

  // ---- timer ----
  setTimer(name: string, ms: number, fn: () => void): void {
    this.clearTimer(name)
    this.timers.set(
      name,
      setTimeout(() => {
        this.timers.delete(name)
        fn()
      }, ms),
    )
  }
  clearTimer(name: string): void {
    const t = this.timers.get(name)
    if (t) clearTimeout(t)
    this.timers.delete(name)
  }
  clearAllTimers(): void {
    this.timers.forEach((t) => clearTimeout(t))
    this.timers.clear()
  }

  // ---- gửi ----
  broadcast<T extends ServerMessageType>(type: T, data: ServerMessageMap[T]): void {
    this.conns.forEach((c) => c.deliver(type, data))
  }
  sendToPlayer<T extends ServerMessageType>(playerId: string, type: T, data: ServerMessageMap[T]): void {
    this.conns.forEach((c) => {
      if (c.role === 'player' && c.playerId === playerId) c.deliver(type, data)
    })
  }
  playerInfos(): PlayerInfo[] {
    return this.players.map((p) => ({ ...p.info }))
  }
  broadcastPlayers(): void {
    this.broadcast('players_updated', { players: this.playerInfos() })
  }
  setPhase(phase: Phase): void {
    this.phase = phase
    this.broadcast('phase_changed', { phase })
  }

  player(id: string): MockPlayer | undefined {
    return this.players.find((p) => p.info.id === id)
  }
  drawnSet(): Set<number> {
    return new Set(this.drawn)
  }
  connectedIds(): string[] {
    return this.players.filter((p) => p.info.connected).map((p) => p.info.id)
  }

  snapshotFor(conn: MockConnection): Snapshot {
    const snap: Snapshot = {
      pin: this.pin,
      picture_code: [...this.picture_code],
      phase: this.phase,
      join_url: this.join_url,
      config: structuredClone(this.config),
      players: this.playerInfos(),
      answerer_mode: this.answerer_mode,
      fixed_player_id: this.fixed_player_id,
      drawn: [...this.drawn],
      question: this.q ? this.questionPayload() : null,
      reveal: this.reveal ? structuredClone(this.reveal) : null,
      winners: structuredClone(this.winners),
    }
    if (conn.role === 'player' && conn.playerId) {
      const p = this.player(conn.playerId)
      if (p) {
        snap.me = { ...p.info }
        snap.card = structuredClone(p.card)
        snap.marked = markedCells(p.card, this.drawnSet())
      }
    }
    return snap
  }

  // ---- người chơi ----
  addPlayer(nickname: string, avatar_id: string, bot: boolean): MockPlayer {
    const p: MockPlayer = {
      info: { id: randomId(12), nickname, avatar_id, connected: bot },
      token: randomId(43),
      card: generateCard(this.R, this.rng),
      bot,
    }
    this.players.push(p)
    return p
  }

  setConnected(playerId: string, connected: boolean): void {
    const p = this.player(playerId)
    if (!p || p.bot || p.info.connected === connected) return
    p.info.connected = connected
    this.broadcastPlayers()
    if (!connected && this.phase === 'question' && this.q?.answererId === playerId) {
      this.setTimer('disconnect', DISCONNECT_GRACE_MS, () => {
        if (this.phase === 'question' && this.q?.answererId === playerId && !this.player(playerId)?.info.connected) {
          this.changeAnswerer('disconnect')
        }
      })
    }
    if (connected && this.q?.answererId === playerId) this.clearTimer('disconnect')
  }

  // ---- câu hỏi ----
  questionPayload(): Question {
    const q = this.q!
    const ans = this.player(q.answererId)!
    return {
      question_id: q.question_id,
      attempt: q.attempt,
      text: q.problem.text,
      operator: q.problem.operator,
      a: q.problem.a,
      b: q.problem.b,
      options: OPTION_KEYS.map((key, i) => ({ key, value: q.values[i] })),
      answerer: { ...ans.info },
      deadline: q.deadline,
    }
  }

  /** Bốc một số chưa ra (tránh số vừa bỏ qua nếu còn số khác). null nếu kho hết. */
  drawNumber(): number | null {
    const drawn = this.drawnSet()
    const skipped = this.lastSkipped
    if (this.config.draw_only_card_numbers) {
      const onCards = new Set<number>()
      this.players.forEach((p) => p.card.flat().forEach((n) => n && !drawn.has(n) && onCards.add(n)))
      let pool = [...onCards]
      if (skipped != null && pool.length > 1) pool = pool.filter((n) => n !== skipped)
      return pool.length ? pick(this.rng, pool) : null
    }
    const R = this.R
    const n = drawFromRanges(R, (x) => drawn.has(x) || x === skipped, drawn.size + (skipped != null && !drawn.has(skipped) ? 1 : 0), this.rng)
    if (n != null) return n
    return skipped != null && !drawn.has(skipped) ? skipped : null
  }

  /**
   * Bốc số + tạo câu hỏi mới. Trả false nếu hết số.
   * `announcePhase = false` khi phase đã là question (auto: Bỏ qua → question_skipped → question{new}).
   */
  newQuestion(announcePhase = true): boolean {
    const n = this.drawNumber()
    if (n == null) return false
    this.lastSkipped = null
    const connected = this.connectedIds()
    let answererId: string
    if (this.answerer_mode === 'fixed' && this.fixed_player_id && connected.includes(this.fixed_player_id)) {
      answererId = this.fixed_player_id
    } else {
      answererId = pick(this.rng, connected.length ? connected : this.players.map((p) => p.info.id))
    }
    const usedWrong = new Set<number>()
    const M = this.config.max_number
    const problem = generateProblem(n, this.config.operations, this.rng, M)
    const opts = generateOptions(n, usedWrong, null, this.rng, M, problem)
    this.q = {
      question_id: randomId(12),
      attempt: 1,
      number: n,
      problem,
      values: opts.values,
      correctIndex: opts.correctIndex,
      answererId,
      tried: new Set([answererId]),
      wrongCount: 0,
      usedWrong,
      deadline: null,
    }
    this.reveal = null
    if (announcePhase || this.phase !== 'question') this.setPhase('question')
    this.emitQuestion('new')
    return true
  }

  regenerateOptions(): void {
    const q = this.q!
    q.values.forEach((v, i) => i !== q.correctIndex && q.usedWrong.add(v))
    const opts = generateOptions(q.number, q.usedWrong, q.correctIndex, this.rng, this.config.max_number, q.problem)
    q.values = opts.values
    q.correctIndex = opts.correctIndex
    q.attempt += 1
  }

  emitQuestion(reason: QuestionReason): void {
    const q = this.q!
    this.clearTimer('countdown')
    this.clearTimer('bot')
    this.clearTimer('disconnect')
    q.deadline = this.config.timer_seconds > 0 ? new Date(Date.now() + this.config.timer_seconds * 1000).toISOString() : null
    this.broadcast('question', { question: this.questionPayload(), reason })
    if (this.config.timer_seconds > 0) {
      const qid = q.question_id
      const attempt = q.attempt
      this.setTimer('countdown', this.config.timer_seconds * 1000, () => {
        if (this.phase === 'question' && this.q?.question_id === qid && this.q.attempt === attempt) this.changeAnswerer('timeout')
      })
    }
    const ans = this.player(q.answererId)
    if (ans?.bot) {
      const qid = q.question_id
      const attempt = q.attempt
      const answererId = q.answererId
      this.setTimer('bot', BOT_ANSWER_MS, () => {
        this.submitAnswer(answererId, { question_id: qid, attempt, key: pick(this.rng, OPTION_KEYS) })
      })
    } else if (ans && !ans.info.connected) {
      // Người trả lời đang mất kết nối: chờ 10 giây rồi đổi người.
      this.setTimer('disconnect', DISCONNECT_GRACE_MS, () => {
        if (this.phase === 'question' && this.q?.answererId === ans.info.id && !ans.info.connected) this.changeAnswerer('disconnect')
      })
    }
  }

  /** Đổi người trả lời (Help, sai max_wrong, hết giờ, mất kết nối). */
  changeAnswerer(reason: QuestionReason): void {
    const q = this.q!
    const connected = this.connectedIds()
    let cands = connected.filter((id) => !q.tried.has(id))
    if (!cands.length) {
      q.tried = new Set([q.answererId])
      cands = connected.filter((id) => id !== q.answererId)
    }
    if (cands.length) q.answererId = pick(this.rng, cands)
    q.tried.add(q.answererId)
    q.wrongCount = 0
    this.regenerateOptions()
    this.emitQuestion(reason)
  }

  submitAnswer(playerId: string, data: { question_id: string; attempt: number; key: OptionKey }): ErrorCode | null {
    if (this.phase !== 'question' || !this.q) return 'invalid_phase'
    const q = this.q
    if (data.question_id !== q.question_id) return 'stale_question'
    if (q.answererId !== playerId) return 'not_your_turn'
    if (data.attempt !== q.attempt) return 'stale_question'
    const idx = OPTION_KEYS.indexOf(data.key)
    if (idx < 0) return 'invalid_message'
    const value = q.values[idx]
    const correct = idx === q.correctIndex
    this.broadcast('answer_result', { question_id: q.question_id, attempt: q.attempt, player_id: playerId, key: data.key, value, correct })
    if (correct) {
      this.onCorrect()
    } else {
      q.wrongCount += 1
      if (q.wrongCount < this.config.max_wrong) {
        this.regenerateOptions()
        this.emitQuestion('wrong')
      } else {
        this.changeAnswerer('max_wrong')
      }
    }
    return null
  }

  requestHelp(playerId: string | null, question_id?: string): ErrorCode | null {
    if (this.phase !== 'question' || !this.q) return 'invalid_phase'
    if (question_id !== undefined && question_id !== this.q.question_id) return 'stale_question'
    if (playerId !== null && this.q.answererId !== playerId) return 'not_your_turn'
    this.changeAnswerer('help')
    return null
  }

  onCorrect(): void {
    const q = this.q!
    const n = q.number
    const before = this.drawnSet()
    this.drawn.push(n)
    this.clearTimer('countdown')
    this.clearTimer('bot')
    this.clearTimer('disconnect')
    this.broadcast('number_drawn', { number: n, drawn: [...this.drawn] })
    const items: RevealItem[] = []
    for (const p of this.players) {
      const cell = findCell(p.card, n)
      if (!cell) continue
      items.push({
        player_id: p.info.id,
        nickname: p.info.nickname,
        avatar_id: p.info.avatar_id,
        card: structuredClone(p.card),
        marked_before: markedCells(p.card, before),
        new_cell: cell,
      })
      this.sendToPlayer(p.info.id, 'cell_marked', { number: n, cell })
    }
    this.q = null
    this.reveal = {
      number: n,
      seconds_per_card: this.config.reveal_seconds,
      started_at: new Date().toISOString(),
      items,
    }
    this.setPhase('reveal')
    this.broadcast('reveal', structuredClone(this.reveal))
    this.setTimer('reveal', this.revealMs(this.reveal), () => this.afterReveal())
  }

  afterReveal(): void {
    const drawn = this.drawnSet()
    const winners: Winner[] = []
    for (const p of this.players) {
      const lines = winningLines(p.card, drawn)
      if (lines.length) {
        winners.push({
          player_id: p.info.id,
          nickname: p.info.nickname,
          avatar_id: p.info.avatar_id,
          card: structuredClone(p.card),
          marked: markedCells(p.card, drawn),
          lines,
        })
      }
    }
    if (winners.length) this.finish('bingo', winners)
    else this.advance()
  }

  /** Sau reveal không bingo / sau Bỏ qua: auto thì ra câu mới ngay (kho hết thì ready), manual thì ready. */
  advance(): void {
    if (this.config.next_mode === 'auto') {
      // reveal → question: phase_changed{question} → question{new}; Bỏ qua (đang question): chỉ question{new}
      if (this.newQuestion(this.phase !== 'question')) return
    }
    this.setPhase('ready')
  }

  finish(reason: 'bingo' | 'ended_by_host', winners: Winner[]): void {
    this.clearAllTimers()
    this.q = null
    this.winners = winners
    this.setPhase('finished')
    this.broadcast('game_over', { reason, winners: structuredClone(winners) })
  }

  exportState(): RoomState {
    const q = this.q
    return structuredClone({
      room_id: this.room_id,
      host_token: this.host_token,
      screen_token: this.screen_token,
      pin: this.pin,
      picture_code: this.picture_code,
      config: this.config,
      joinBase: this.joinBase,
      phase: this.phase,
      players: this.players,
      answerer_mode: this.answerer_mode,
      fixed_player_id: this.fixed_player_id,
      drawn: this.drawn,
      q: q ? { ...q, tried: [...q.tried], usedWrong: [...q.usedWrong] } : null,
      reveal: this.reveal,
      winners: this.winners,
      lastSkipped: this.lastSkipped,
    })
  }

  importState(st: RoomState): void {
    this.room_id = st.room_id
    this.host_token = st.host_token
    this.screen_token = st.screen_token
    this.phase = st.phase
    // Sau khi đổi leader mọi kết nối đã mất; người chơi thật sẽ tự kết nối lại.
    this.players = st.players.map((p) => ({ ...p, info: { ...p.info, connected: p.bot } }))
    this.answerer_mode = st.answerer_mode
    this.fixed_player_id = st.fixed_player_id
    this.drawn = st.drawn
    this.q = st.q ? { ...st.q, tried: new Set(st.q.tried), usedWrong: new Set(st.q.usedWrong) } : null
    this.reveal = st.reveal
    this.winners = st.winners
    this.lastSkipped = st.lastSkipped
    this.resumeTimers()
  }

  /** Đặt lại các timer theo state hiện tại (dùng sau khi khôi phục). */
  private resumeTimers(): void {
    const q = this.q
    if (this.phase === 'question' && q) {
      const ans = this.player(q.answererId)
      const qid = q.question_id
      const attempt = q.attempt
      if (q.deadline) {
        const left = Math.max(0, Date.parse(q.deadline) - Date.now())
        this.setTimer('countdown', left, () => {
          if (this.phase === 'question' && this.q?.question_id === qid && this.q.attempt === attempt) this.changeAnswerer('timeout')
        })
      }
      if (ans?.bot) {
        this.setTimer('bot', BOT_ANSWER_MS, () =>
          this.submitAnswer(ans.info.id, { question_id: qid, attempt, key: pick(this.rng, OPTION_KEYS) }),
        )
      } else if (ans) {
        this.setTimer('disconnect', DISCONNECT_GRACE_MS, () => {
          if (this.phase === 'question' && this.q?.answererId === ans.info.id && !ans.info.connected) this.changeAnswerer('disconnect')
        })
      }
    } else if (this.phase === 'reveal' && this.reveal) {
      const r = this.reveal
      const left = Math.max(0, Date.parse(r.started_at) + this.revealMs(r) - Date.now())
      this.setTimer('reveal', left, () => this.afterReveal())
    }
  }

  close(reason: 'closed_by_host' | 'expired'): void {
    this.clearAllTimers()
    this.broadcast('room_closed', { reason })
    this.conns.forEach((c) => c.terminate(WS_CLOSE.ROOM_CLOSED))
    this.conns.clear()
  }
}

export class MockServer {
  rng: Rng = Math.random
  private rooms = new Map<string, MockRoom>()
  /** PIN / mã hình của phòng đã đóng (thời gian nghỉ). */
  private closedPins = new Set<string>()
  private closedPictures = new Set<string>()
  /** Số người chơi ảo tự vào mỗi phòng mới. */
  botCount = 3

  private room(pin: string): MockRoom {
    return this.rooms.get(pin) ?? fail(404, 'room_not_found')
  }
  private hostRoom(pin: string, token: string | undefined): MockRoom {
    const r = this.room(pin)
    if (!token || token !== r.host_token) fail(401, 'bad_token')
    return r
  }

  private genPin(): string {
    for (;;) {
      const pin = String(1000 + Math.floor(this.rng() * 9000))
      if (!isEasyPin(pin) && !this.rooms.has(pin) && !this.closedPins.has(pin)) return pin
    }
  }
  private genPictures(): RoomIcon[] {
    const used = new Set([...this.rooms.values()].map((r) => r.picture_code.join(',')))
    for (;;) {
      const code = shuffle(this.rng, [...ROOM_ICONS]).slice(0, 3)
      const k = code.join(',')
      if (!used.has(k) && !this.closedPictures.has(k)) return code
    }
  }

  // ---------------- REST ----------------

  createRoom(body: CreateRoomRequest): CreateRoomResponse {
    const config = normalizeConfig(body?.config)
    if (!config || !isValidConfig(config)) fail(422, 'invalid_config')
    const base = normalizeJoinBase(body.join_base_url) ?? fail(422, 'invalid_join_url')
    if (this.rooms.size >= MAX_ROOMS) fail(503, 'too_many_rooms')
    const room = new MockRoom(this, this.genPin(), this.genPictures(), structuredClone(config!), base)
    this.rooms.set(room.pin, room)
    for (let i = 0; i < this.botCount; i++) {
      room.addPlayer(BOT_NAMES[i % BOT_NAMES.length], MOCK_AVATARS[(i * 4 + 1) % MOCK_AVATARS.length].id, true)
    }
    return {
      pin: room.pin,
      picture_code: [...room.picture_code],
      host_token: room.host_token,
      screen_token: room.screen_token,
      join_url: room.join_url,
    }
  }

  getRoom(pin: string): RoomInfoResponse {
    const r = this.room(pin)
    const avatar_counts: Record<string, number> = {}
    for (const p of r.players) avatar_counts[p.info.avatar_id] = (avatar_counts[p.info.avatar_id] ?? 0) + 1
    return { phase: r.phase, player_count: r.players.length, avatar_counts }
  }

  lookup(pictures: string[]) {
    const k = pictures.join(',')
    for (const r of this.rooms.values()) if (r.picture_code.join(',') === k) return { pin: r.pin }
    return fail(404, 'room_not_found')
  }

  closeRoom(pin: string, token?: string) {
    const r = this.hostRoom(pin, token)
    r.close('closed_by_host')
    this.rooms.delete(pin)
    this.closedPins.add(pin)
    this.closedPictures.add(r.picture_code.join(','))
    return { ok: true as const }
  }

  updateConfig(pin: string, token: string | undefined, raw: GameConfig): GameConfig {
    const r = this.hostRoom(pin, token)
    if (r.phase !== 'lobby' && r.phase !== 'finished') fail(409, 'invalid_phase')
    const config = normalizeConfig(raw)
    if (!config || !isValidConfig(config)) fail(422, 'invalid_config')
    r.config = structuredClone(config!)
    r.broadcast('config_updated', { config: structuredClone(r.config) })
    if (r.phase === 'lobby') {
      for (const p of r.players) {
        p.card = generateCard(r.R, r.rng)
        r.sendToPlayer(p.info.id, 'your_card', { card: structuredClone(p.card), marked: [] })
      }
    }
    return structuredClone(r.config)
  }

  updateJoinBaseUrl(pin: string, token: string | undefined, join_base_url: string) {
    const r = this.hostRoom(pin, token)
    r.joinBase = normalizeJoinBase(join_base_url) ?? fail(422, 'invalid_join_url')
    r.broadcast('join_url_updated', { join_url: r.join_url })
    return { join_url: r.join_url }
  }

  kickPlayer(pin: string, token: string | undefined, playerId: string) {
    const r = this.hostRoom(pin, token)
    if (r.phase !== 'lobby') fail(409, 'invalid_phase')
    const idx = r.players.findIndex((p) => p.info.id === playerId)
    if (idx < 0) fail(404, 'player_not_found')
    r.players.splice(idx, 1)
    r.conns.forEach((c) => {
      if (c.role === 'player' && c.playerId === playerId) {
        c.deliver('kicked', {})
        c.terminate(WS_CLOSE.KICKED)
        r.conns.delete(c)
      }
    })
    r.broadcastPlayers()
    return { ok: true as const }
  }

  start(pin: string, token: string | undefined, body: StartRequest) {
    const r = this.hostRoom(pin, token)
    if (r.phase !== 'lobby') fail(409, 'invalid_phase')
    if (!r.players.length) fail(422, 'no_players')
    if (body.answerer_mode === 'fixed' && (!body.fixed_player_id || !r.player(body.fixed_player_id))) fail(422, 'fixed_player_required')
    r.answerer_mode = body.answerer_mode
    r.fixed_player_id = body.answerer_mode === 'fixed' ? body.fixed_player_id : null
    r.broadcast('game_started', { answerer_mode: r.answerer_mode, fixed_player_id: r.fixed_player_id })
    if (!r.newQuestion()) fail(409, 'no_numbers_left')
    return { ok: true as const }
  }

  next(pin: string, token: string | undefined) {
    const r = this.hostRoom(pin, token)
    if (r.phase !== 'ready') fail(409, 'invalid_phase')
    if (!r.newQuestion()) fail(409, 'no_numbers_left')
    return { ok: true as const }
  }

  skip(pin: string, token: string | undefined) {
    const r = this.hostRoom(pin, token)
    if (r.phase !== 'question' || !r.q) fail(409, 'invalid_phase')
    const q = r.q!
    r.clearAllTimers()
    r.lastSkipped = q.number
    r.q = null
    r.broadcast('question_skipped', { question_id: q.question_id, number: q.number })
    // manual: question_skipped → phase_changed{ready}; auto: question_skipped → question{new} (vẫn phase question)
    r.advance()
    return { ok: true as const }
  }

  help(pin: string, token: string | undefined) {
    const r = this.hostRoom(pin, token)
    const err = r.requestHelp(null)
    if (err) fail(409, err)
    return { ok: true as const }
  }

  end(pin: string, token: string | undefined) {
    const r = this.hostRoom(pin, token)
    if (r.phase !== 'question' && r.phase !== 'reveal' && r.phase !== 'ready') fail(409, 'invalid_phase')
    r.finish('ended_by_host', [])
    return { ok: true as const }
  }

  newRound(pin: string, token: string | undefined, join_base_url?: string) {
    const r = this.hostRoom(pin, token)
    if (r.phase !== 'finished') fail(409, 'invalid_phase')
    let baseChanged = false
    if (join_base_url !== undefined) {
      const base = normalizeJoinBase(join_base_url) ?? fail(422, 'invalid_join_url')
      baseChanged = base !== r.joinBase
      r.joinBase = base
    }
    r.clearAllTimers()
    r.phase = 'lobby'
    r.answerer_mode = null
    r.fixed_player_id = null
    r.drawn = []
    r.q = null
    r.reveal = null
    r.winners = []
    r.lastSkipped = null
    for (const p of r.players) p.card = generateCard(r.R, r.rng)
    if (baseChanged) r.broadcast('join_url_updated', { join_url: r.join_url })
    r.conns.forEach((c) => c.deliver('snapshot', r.snapshotFor(c)))
    return { ok: true as const }
  }

  join(pin: string, body: JoinRequest): JoinResponse {
    const r = this.room(pin)
    if (r.phase !== 'lobby') fail(409, 'game_in_progress')
    const nickname = typeof body.nickname === 'string' ? body.nickname.trim() : ''
    if (nickname.length < 1 || nickname.length > 20) fail(422, 'invalid_nickname')
    if (!MOCK_AVATARS.some((a) => a.id === body.avatar_id)) fail(422, 'invalid_avatar')
    if (r.players.some((p) => p.info.nickname.toLowerCase() === nickname.toLowerCase())) fail(409, 'nickname_taken')
    if (r.players.length >= MAX_PLAYERS) fail(409, 'room_full')
    const p = r.addPlayer(nickname, body.avatar_id, false)
    r.broadcastPlayers()
    return { player_id: p.info.id, player_token: p.token }
  }

  // ---------------- WS ----------------

  /** Trả về hàm xử lý message client → server, hoặc null nếu đã từ chối (conn bị terminate). */
  connect(pin: string, role: Role, token: string, conn: MockConnection): ((msg: ClientMessage) => void) | null {
    const r = this.rooms.get(pin)
    if (!r) {
      conn.terminate(this.closedPins.has(pin) ? WS_CLOSE.ROOM_CLOSED : WS_CLOSE.ROOM_NOT_FOUND)
      return null
    }
    let player: MockPlayer | undefined
    if (role === 'host') {
      if (token !== r.host_token) return conn.terminate(WS_CLOSE.BAD_TOKEN), null
    } else if (role === 'screen') {
      if (token !== r.screen_token) return conn.terminate(WS_CLOSE.BAD_TOKEN), null
    } else {
      player = r.players.find((p) => p.token === token)
      if (!player) return conn.terminate(WS_CLOSE.BAD_TOKEN), null
      conn.playerId = player.info.id
      // Người chơi kết nối lại thì thay socket cũ.
      r.conns.forEach((c) => {
        if (c.role === 'player' && c.playerId === player!.info.id) {
          r.conns.delete(c)
          c.terminate(WS_CLOSE.REPLACED)
        }
      })
    }
    r.conns.add(conn)
    conn.deliver('snapshot', r.snapshotFor(conn))
    if (player) r.setConnected(player.info.id, true)

    return (msg: ClientMessage) => {
      if (!r.conns.has(conn)) return
      if (msg.type === 'ping') {
        conn.deliver('pong', {})
        return
      }
      if (role !== 'player' || !conn.playerId) {
        conn.deliver('error', { code: 'invalid_message', message: 'only players may send this' })
        return
      }
      let err: ErrorCode | null
      if (msg.type === 'submit_answer') err = r.submitAnswer(conn.playerId, msg.data)
      else if (msg.type === 'request_help') err = r.requestHelp(conn.playerId, msg.data?.question_id)
      else err = 'invalid_message'
      if (err) conn.deliver('error', { code: err, message: err })
    }
  }

  disconnect(pin: string, conn: MockConnection): void {
    const r = this.rooms.get(pin)
    if (!r || !r.conns.delete(conn)) return
    if (conn.role === 'player' && conn.playerId) {
      const still = [...r.conns].some((c) => c.role === 'player' && c.playerId === conn.playerId)
      if (!still) r.setConnected(conn.playerId, false)
    }
  }

  // ---- tiện ích cho test / dev ----
  peekCorrectKey(pin: string): OptionKey | null {
    const q = this.rooms.get(pin)?.q
    return q ? OPTION_KEYS[q.correctIndex] : null
  }
  exportState(): ServerState {
    return {
      rooms: [...this.rooms.values()].map((r) => r.exportState()),
      closedPins: [...this.closedPins],
      closedPictures: [...this.closedPictures],
    }
  }

  importState(st: ServerState): void {
    this.reset()
    for (const rs of st.rooms) {
      const room = new MockRoom(this, rs.pin, rs.picture_code, rs.config, rs.joinBase)
      room.importState(rs)
      this.rooms.set(room.pin, room)
    }
    st.closedPins.forEach((p) => this.closedPins.add(p))
    st.closedPictures.forEach((p) => this.closedPictures.add(p))
  }

  reset(): void {
    this.rooms.forEach((r) => r.clearAllTimers())
    this.rooms.clear()
    this.closedPins.clear()
    this.closedPictures.clear()
  }
}

/** Một server giả dùng chung cho cả tab. */
export const mockServer = new MockServer()
