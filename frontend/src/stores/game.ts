import { defineStore } from 'pinia'
import { computed, ref, shallowRef } from 'vue'
import type {
  AnswererMode,
  Card,
  Cell,
  ErrorBody,
  GameConfig,
  GameOverReason,
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
import { createGameClient, type ConnectionStatus, type GameClient } from '@/api/gameClient'

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

  // ---- sự kiện một lần ----
  const lastAnswer = ref<ServerMessageMap['answer_result'] | null>(null)
  const lastSkipped = ref<ServerMessageMap['question_skipped'] | null>(null)
  const gameOverReason = ref<GameOverReason | null>(null)
  const kicked = ref(false)
  const roomClosed = ref<RoomClosedReason | null>(null)
  const lastError = ref<ErrorBody | null>(null)

  const isMyTurn = computed(() => !!me.value && question.value?.answerer.id === me.value.id)

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
    gameOverReason.value = null
    ready.value = true
  }

  function bind(c: GameClient): void {
    unsubs.push(
      c.onStatus((s, code) => {
        status.value = s
        if (code !== undefined) closeCode.value = code
      }),
      c.on('snapshot', applySnapshot),
      c.on('phase_changed', (d) => {
        phase.value = d.phase
        if (d.phase !== 'question') question.value = null
        if (d.phase !== 'reveal') reveal.value = null
        if (d.phase === 'lobby') winners.value = []
      }),
      c.on('players_updated', (d) => {
        players.value = d.players
        if (me.value) me.value = d.players.find((p) => p.id === me.value!.id) ?? me.value
      }),
      c.on('config_updated', (d) => (config.value = d.config)),
      c.on('join_url_updated', (d) => (joinUrl.value = d.join_url)),
      c.on('your_card', (d) => {
        card.value = d.card
        marked.value = d.marked
        lastMarkedCell.value = null
      }),
      c.on('game_started', (d) => {
        answererMode.value = d.answerer_mode
        fixedPlayerId.value = d.fixed_player_id
        winners.value = []
        gameOverReason.value = null
      }),
      c.on('question', (d) => {
        question.value = d.question
        questionReason.value = d.reason
      }),
      c.on('answer_result', (d) => (lastAnswer.value = d)),
      c.on('number_drawn', (d) => (drawn.value = d.drawn)),
      c.on('cell_marked', (d) => {
        marked.value = [...marked.value, d.cell]
        lastMarkedCell.value = d.cell
      }),
      c.on('reveal', (d) => (reveal.value = d)),
      c.on('question_skipped', (d) => {
        lastSkipped.value = d
        question.value = null
      }),
      c.on('game_over', (d) => {
        gameOverReason.value = d.reason
        winners.value = d.winners
      }),
      c.on('kicked', () => (kicked.value = true)),
      c.on('room_closed', (d) => (roomClosed.value = d.reason)),
      c.on('error', (d) => (lastError.value = d)),
    )
  }

  function connect(p: string, r: Role, token: string): GameClient {
    disconnect()
    kicked.value = false
    roomClosed.value = null
    closeCode.value = null
    lastError.value = null
    ready.value = false
    role.value = r
    const c = createGameClient()
    client.value = c
    bind(c)
    c.connect(p, r, token)
    return c
  }

  function disconnect(): void {
    client.value?.close()
    unsubs.forEach((u) => u())
    unsubs = []
    client.value = null
    status.value = 'idle'
  }

  function submitAnswer(key: ServerMessageMap['answer_result']['key']): void {
    const q = question.value
    if (!q) return
    client.value?.send('submit_answer', { question_id: q.question_id, attempt: q.attempt, key })
  }

  function requestHelp(): void {
    const q = question.value
    if (!q) return
    client.value?.send('request_help', { question_id: q.question_id })
  }

  return {
    // kết nối
    role, status, closeCode, client,
    // phòng
    ready, pin, pictureCode, phase, joinUrl, config, players, answererMode, fixedPlayerId,
    drawn, question, questionReason, reveal, winners,
    // người chơi
    me, card, marked, lastMarkedCell, isMyTurn,
    // sự kiện
    lastAnswer, lastSkipped, gameOverReason, kicked, roomClosed, lastError,
    // hành động
    applySnapshot, connect, disconnect, submitAnswer, requestHelp,
  }
})
