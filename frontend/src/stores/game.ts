import { defineStore } from 'pinia'
import { computed, ref, shallowRef } from 'vue'
import type {
  AnswererMode,
  Avatar,
  Card,
  Cell,
  ErrorBody,
  GameConfig,
  GameOverReason,
  OptionKey,
  Phase,
  PlayerInfo,
  Question,
  QuestionReason,
  Reveal,
  Role,
  RoomClosedReason,
  RoomIcon,
  ServerMessageMap,
  Snapshot,
  Winner,
} from '@/api/contract'
import { WS_CLOSE } from '@/api/contract'
import { createGameClient, type ConnectionStatus, type GameClient } from '@/api/gameClient'
import { estimateOffset } from '@/utils/time'

const sameCell = (a: Cell, b: Cell) => a[0] === b[0] && a[1] === b[1]

/**
 * Trạng thái phòng phía client: nhận snapshot rồi áp dụng từng sự kiện.
 * Không tự tính đáp án hay tự khoanh ô; chỉ phản ánh dữ liệu server gửi.
 */
export const useGameStore = defineStore('game', () => {
  // ---- kết nối ----
  const role = ref<Role | null>(null)
  const status = ref<ConnectionStatus>('idle')
  const closeCode = ref<number | null>(null)
  const client = shallowRef<GameClient | null>(null)
  let unsubs: (() => void)[] = []

  // ---- đồng hồ (để đếm ngược / reveal không phụ thuộc lệch giờ máy) ----
  const now = ref(Date.now())
  const clockOffset = ref(0)
  const serverNow = computed(() => now.value + clockOffset.value)
  let ticker: ReturnType<typeof setInterval> | null = null

  // ---- dữ liệu phòng (theo Snapshot) ----
  const ready = ref(false)
  const pin = ref<string | null>(null)
  const pictureCode = ref<RoomIcon[]>([])
  const phase = ref<Phase>('lobby')
  const joinUrl = ref('')
  const config = ref<GameConfig | null>(null)
  const players = ref<PlayerInfo[]>([])
  const answererMode = ref<AnswererMode | null>(null)
  const fixedPlayerId = ref<string | null>(null)
  const drawn = ref<number[]>([])
  const question = ref<Question | null>(null)
  const questionReason = ref<QuestionReason | null>(null)
  const reveal = ref<Reveal | null>(null)
  const winners = ref<Winner[]>([])

  // ---- riêng người chơi ----
  const me = ref<PlayerInfo | null>(null)
  const card = ref<Card | null>(null)
  const marked = ref<Cell[]>([])
  const lastMarkedCell = ref<Cell | null>(null)
  /** Tăng mỗi lần nhận cell_marked, dùng làm key để chạy lại animation. */
  const markSeq = ref(0)
  /** Đã bấm đáp án/Help, chờ answer_result hoặc question mới. */
  const answerLocked = ref(false)

  // ---- sự kiện một lần ----
  const lastAnswer = ref<ServerMessageMap['answer_result'] | null>(null)
  const lastSkipped = ref<ServerMessageMap['question_skipped'] | null>(null)
  const gameOverReason = ref<GameOverReason | null>(null)
  const kicked = ref(false)
  const roomClosed = ref<RoomClosedReason | null>(null)
  const lastError = ref<ErrorBody | null>(null)

  // ---- nhân vật (GET /api/avatars) ----
  const avatars = ref<Avatar[]>([])
  const avatarMap = computed(() => new Map(avatars.value.map((a) => [a.id, a])))

  const isMyTurn = computed(() => !!me.value && question.value?.answerer.id === me.value.id)
  const isWinner = computed(() => !!me.value && winners.value.some((w) => w.player_id === me.value!.id))
  /** Kết nối đã bị đóng hẳn: không tự kết nối lại. */
  const ended = computed<'kicked' | 'closed' | 'bad_token' | 'not_found' | 'replaced' | null>(() => {
    if (kicked.value || closeCode.value === WS_CLOSE.KICKED) return 'kicked'
    if (roomClosed.value || closeCode.value === WS_CLOSE.ROOM_CLOSED) return 'closed'
    if (closeCode.value === WS_CLOSE.BAD_TOKEN) return 'bad_token'
    if (closeCode.value === WS_CLOSE.ROOM_NOT_FOUND) return 'not_found'
    if (closeCode.value === WS_CLOSE.REPLACED) return 'replaced'
    return null
  })

  function applySnapshot(s: Snapshot): void {
    pin.value = s.pin
    pictureCode.value = s.picture_code
    phase.value = s.phase
    joinUrl.value = s.join_url
    config.value = s.config
    players.value = s.players
    answererMode.value = s.answerer_mode
    fixedPlayerId.value = s.fixed_player_id
    drawn.value = s.drawn
    question.value = s.question
    questionReason.value = null
    reveal.value = s.reveal
    winners.value = s.winners
    me.value = s.me ?? null
    card.value = s.card ?? null
    marked.value = s.marked ?? []
    lastMarkedCell.value = null
    lastAnswer.value = null
    lastSkipped.value = null
    gameOverReason.value = s.phase === 'finished' ? (s.winners.length ? 'bingo' : 'ended_by_host') : null
    answerLocked.value = false
    ready.value = true
  }

  const handlers: { [K in keyof ServerMessageMap]?: (d: ServerMessageMap[K]) => void } = {
    snapshot: applySnapshot,
    phase_changed: (d) => {
      phase.value = d.phase
      if (d.phase !== 'question') {
        question.value = null
        answerLocked.value = false
      }
      if (d.phase !== 'reveal') reveal.value = null
      if (d.phase === 'lobby') {
        winners.value = []
        gameOverReason.value = null
      }
    },
    players_updated: (d) => {
      players.value = d.players
      if (me.value) me.value = d.players.find((p) => p.id === me.value!.id) ?? me.value
    },
    config_updated: (d) => (config.value = d.config),
    join_url_updated: (d) => (joinUrl.value = d.join_url),
    your_card: (d) => {
      card.value = d.card
      marked.value = d.marked
      lastMarkedCell.value = null
    },
    game_started: (d) => {
      answererMode.value = d.answerer_mode
      fixedPlayerId.value = d.fixed_player_id
      winners.value = []
      gameOverReason.value = null
      drawn.value = []
      lastAnswer.value = null
      lastSkipped.value = null
    },
    question: (d) => {
      question.value = d.question
      questionReason.value = d.reason
      answerLocked.value = false
      lastSkipped.value = null
      if (d.question.deadline && config.value && config.value.timer_seconds > 0) {
        const stamp = Date.parse(d.question.deadline) - config.value.timer_seconds * 1000
        if (Number.isFinite(stamp)) clockOffset.value = estimateOffset(stamp, Date.now())
      }
    },
    answer_result: (d) => {
      lastAnswer.value = d
      if (me.value && d.player_id === me.value.id) answerLocked.value = false
    },
    number_drawn: (d) => (drawn.value = d.drawn),
    cell_marked: (d) => {
      if (!marked.value.some((c) => sameCell(c, d.cell))) marked.value = [...marked.value, d.cell]
      lastMarkedCell.value = d.cell
      markSeq.value++
    },
    reveal: (d) => {
      reveal.value = d
      const stamp = Date.parse(d.started_at)
      if (Number.isFinite(stamp)) clockOffset.value = estimateOffset(stamp, Date.now())
    },
    question_skipped: (d) => {
      lastSkipped.value = d
      question.value = null
      answerLocked.value = false
    },
    game_over: (d) => {
      gameOverReason.value = d.reason
      winners.value = d.winners
    },
    kicked: () => (kicked.value = true),
    room_closed: (d) => (roomClosed.value = d.reason),
    error: (d) => {
      lastError.value = d
      answerLocked.value = false
    },
  }

  /** Áp dụng một message server (dùng chung cho client thật, mock và test). */
  function apply<K extends keyof ServerMessageMap>(type: K, data: ServerMessageMap[K]): void {
    const h = handlers[type] as ((d: ServerMessageMap[K]) => void) | undefined
    h?.(data)
  }

  function bind(c: GameClient): void {
    unsubs.push(
      c.onStatus((s, code) => {
        status.value = s
        if (code !== undefined) closeCode.value = code
        if (s === 'reconnecting') answerLocked.value = false
      }),
    )
    for (const type of Object.keys(handlers) as (keyof ServerMessageMap)[]) {
      unsubs.push(c.on(type, (d) => apply(type, d as never)))
    }
  }

  function reset(): void {
    ready.value = false
    pin.value = null
    pictureCode.value = []
    phase.value = 'lobby'
    joinUrl.value = ''
    config.value = null
    players.value = []
    answererMode.value = null
    fixedPlayerId.value = null
    drawn.value = []
    question.value = null
    questionReason.value = null
    reveal.value = null
    winners.value = []
    me.value = null
    card.value = null
    marked.value = []
    lastMarkedCell.value = null
    answerLocked.value = false
    lastAnswer.value = null
    lastSkipped.value = null
    gameOverReason.value = null
    kicked.value = false
    roomClosed.value = null
    closeCode.value = null
    lastError.value = null
  }

  /** Kết nối tới phòng. `c` cho phép test truyền client giả. */
  function connect(p: string, r: Role, token: string, c: GameClient = createGameClient()): GameClient {
    disconnect()
    reset()
    role.value = r
    client.value = c
    bind(c)
    if (!ticker && typeof window !== 'undefined') ticker = setInterval(() => (now.value = Date.now()), 250)
    c.connect(p, r, token)
    return c
  }

  function disconnect(): void {
    const c = client.value
    unsubs.forEach((u) => u())
    unsubs = []
    client.value = null
    c?.close()
    status.value = 'idle'
    if (ticker) clearInterval(ticker)
    ticker = null
  }

  function submitAnswer(key: OptionKey): void {
    const q = question.value
    if (!q || !isMyTurn.value || answerLocked.value) return
    answerLocked.value = true
    client.value?.send('submit_answer', { question_id: q.question_id, attempt: q.attempt, key })
  }

  function requestHelp(): void {
    const q = question.value
    if (!q || !isMyTurn.value || answerLocked.value) return
    answerLocked.value = true
    client.value?.send('request_help', { question_id: q.question_id })
  }

  function setAvatars(list: Avatar[]): void {
    avatars.value = list
  }

  return {
    // kết nối
    role, status, closeCode, client, ended,
    // đồng hồ
    now, clockOffset, serverNow,
    // phòng
    ready, pin, pictureCode, phase, joinUrl, config, players, answererMode, fixedPlayerId,
    drawn, question, questionReason, reveal, winners,
    // người chơi
    me, card, marked, lastMarkedCell, markSeq, isMyTurn, isWinner, answerLocked,
    // sự kiện
    lastAnswer, lastSkipped, gameOverReason, kicked, roomClosed, lastError,
    // nhân vật
    avatars, avatarMap, setAvatars,
    // hành động
    applySnapshot, apply, connect, disconnect, reset, submitAnswer, requestHelp,
  }
})
