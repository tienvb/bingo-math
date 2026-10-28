<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import type { OptionKey, RoomIcon as RoomIconId } from '@/api/contract'
import { api } from '@/api/rest'
import { useGameStore } from '@/stores/game'
import { loadLastPlayer, saveLastPlayer, useSessionStore } from '@/stores/session'
import { errorCode, useErrorText } from '@/composables/useErrorText'
import { useAvatars } from '@/composables/useAvatars'
import { useAnswerFeedback } from '@/composables/useAnswerFeedback'
import { vibrate } from '@/utils/device'
import AnswerButtons from '@/components/AnswerButtons.vue'
import AvatarBadge from '@/components/AvatarBadge.vue'
import AvatarPicker from '@/components/AvatarPicker.vue'
import BingoCard from '@/components/BingoCard.vue'
import ConnectionBanner from '@/components/ConnectionBanner.vue'
import DrawnNumbers from '@/components/DrawnNumbers.vue'
import QuestionPanel from '@/components/QuestionPanel.vue'
import RoomCodeInput from '@/components/RoomCodeInput.vue'
import StatusScreen from '@/components/StatusScreen.vue'
import WinnerCelebration from '@/components/WinnerCelebration.vue'

const props = defineProps<{ pin?: string }>()
const router = useRouter()
const { t } = useI18n()
const game = useGameStore()
const session = useSessionStore()
const errText = useErrorText()
const { avatars } = useAvatars()
const { shown, reason, feedback, holding } = useAnswerFeedback()

type Step = 'enter' | 'checking' | 'name' | 'avatar' | 'joining' | 'game' | 'blocked'
const step = ref<Step>('enter')
const blocked = ref<{ title: string; message?: string; canEnterCode: boolean; canRetry: boolean; playHere: boolean } | null>(null)

// ---------------- Nhập mã ----------------
const codeBusy = ref(false)
const codeError = ref<string | null>(null)
async function onPictures(pics: RoomIconId[]) {
  codeBusy.value = true
  codeError.value = null
  try {
    const { pin } = await api.lookup(pics)
    await router.push({ name: 'play', params: { pin } })
  } catch (e) {
    codeError.value = errText(e)
    codeInput.value?.clearPictures()
  } finally {
    codeBusy.value = false
  }
}
async function onPin(pin: string) {
  codeBusy.value = true
  codeError.value = null
  try {
    await api.getRoom(pin)
    await router.push({ name: 'play', params: { pin } })
  } catch (e) {
    codeError.value = errText(e)
  } finally {
    codeBusy.value = false
  }
}
const codeInput = ref<InstanceType<typeof RoomCodeInput> | null>(null)

// ---------------- Vào phòng ----------------
const last = loadLastPlayer()
const nickname = ref(last?.nickname ?? '')
const avatarId = ref<string | null>(last?.avatar_id ?? null)
const joinError = ref<string | null>(null)
const trimmed = computed(() => nickname.value.trim())
const nameValid = computed(() => trimmed.value.length >= 1 && trimmed.value.length <= 20)

function block(title: string, opts: { message?: string; canEnterCode?: boolean; canRetry?: boolean; playHere?: boolean } = {}) {
  blocked.value = { title, message: opts.message, canEnterCode: !!opts.canEnterCode, canRetry: !!opts.canRetry, playHere: !!opts.playHere }
  step.value = 'blocked'
}

const avatarCounts = ref<Record<string, number>>({})
/** Làm mới số người đã chọn mỗi nhân vật (GET /api/rooms/{pin} → avatar_counts). */
async function refreshCounts() {
  if (!props.pin) return
  try {
    avatarCounts.value = (await api.getRoom(props.pin)).avatar_counts ?? {}
  } catch {
    /* giữ số cũ */
  }
}

async function checkRoom(pin: string) {
  step.value = 'checking'
  try {
    const info = await api.getRoom(pin)
    avatarCounts.value = info.avatar_counts ?? {}
    if (info.phase !== 'lobby') {
      block(t('errors.game_in_progress'), { message: t('play.gameInProgressHint'), canRetry: true, canEnterCode: true })
      return
    }
    step.value = 'name'
  } catch (e) {
    if (errorCode(e) === 'room_not_found') block(t('play.roomClosed'), { message: t('play.roomNotFoundHint'), canEnterCode: true })
    else block(errText(e), { canRetry: true, canEnterCode: true })
  }
}

function start(pin: string | undefined) {
  game.disconnect()
  joinError.value = null
  blocked.value = null
  if (!pin) {
    step.value = 'enter'
    return
  }
  const s = session.get(pin)
  if (s.player_token) {
    step.value = 'game'
    game.connect(pin, 'player', s.player_token)
  } else void checkRoom(pin)
}
watch(() => props.pin, start, { immediate: true })
onBeforeUnmount(() => game.disconnect())

function toAvatar() {
  joinError.value = null
  if (!nameValid.value) {
    joinError.value = t('errors.invalid_nickname')
    return
  }
  step.value = 'avatar'
  void refreshCounts()
}

async function join() {
  const pin = props.pin
  if (!pin || !avatarId.value) return
  step.value = 'joining'
  joinError.value = null
  try {
    const res = await api.join(pin, { nickname: trimmed.value, avatar_id: avatarId.value })
    session.set(pin, { player_token: res.player_token, player_id: res.player_id })
    saveLastPlayer({ nickname: trimmed.value, avatar_id: avatarId.value })
    step.value = 'game'
    game.connect(pin, 'player', res.player_token)
  } catch (e) {
    const code = errorCode(e)
    joinError.value = errText(e)
    if (code === 'nickname_taken' || code === 'invalid_nickname') step.value = 'name'
    else if (code === 'invalid_avatar') step.value = 'avatar'
    else if (code === 'room_not_found') block(t('play.roomClosed'), { canEnterCode: true })
    else if (code === 'game_in_progress' || code === 'room_full')
      block(joinError.value, { canRetry: code === 'game_in_progress', canEnterCode: true })
    else step.value = 'avatar'
  }
}

// ---------------- Trong ván ----------------
const tab = ref<'card' | 'question'>('card')
const phase = computed(() => game.phase)
const myTurn = computed(() => !!shown.value && !!game.me && shown.value.answerer.id === game.me.id)
const pendingKey = ref<OptionKey | null>(null)

watch(
  () => [shown.value?.question_id, shown.value?.attempt, myTurn.value] as const,
  ([qid, , mine], prev) => {
    pendingKey.value = null
    if (mine && qid) {
      tab.value = 'question'
      // rung khi vừa đến lượt (không rung lại cho mỗi lần sinh lại đáp án của chính mình)
      if (!prev || !prev[2] || prev[0] !== qid) vibrate([120, 60, 120])
    }
  },
)
watch(phase, (p) => {
  if (p === 'question') tab.value = 'question'
  if (p === 'reveal' || p === 'finished' || p === 'lobby') tab.value = 'card'
})
watch(
  () => game.answerLocked,
  (l) => !l && (pendingKey.value = null),
)

function choose(key: OptionKey) {
  if (!myTurn.value || game.answerLocked || holding.value) return
  pendingKey.value = key
  game.submitAnswer(key)
}
function askHelp() {
  if (!myTurn.value || game.answerLocked || holding.value) return
  game.requestHelp()
}

const hasNewNumber = computed(() => !!game.reveal && !!game.me && game.reveal.items.some((i) => i.player_id === game.me!.id))
const myWinner = computed(() => game.winners.find((w) => w.player_id === game.me?.id) ?? null)

// Kết nối bị đóng hẳn
watch(
  () => game.ended,
  (e) => {
    const pin = props.pin
    if (!e || !pin || step.value !== 'game') return
    if (e === 'replaced') {
      // 4409: đang chơi ở tab/thiết bị khác; giữ token, cho bấm "Chơi ở đây" để lấy lại kết nối.
      block(t('play.replaced'), { message: t('play.replacedHint'), playHere: true })
      return
    }
    session.clear(pin, ['player_token', 'player_id'])
    if (e === 'kicked') block(t('play.kicked'), { message: t('play.kickedHint') })
    else if (e === 'closed' || e === 'not_found') block(t('play.roomClosed'), { canEnterCode: true })
    else if (e === 'bad_token') void checkRoom(pin) // token cũ (phòng khác trùng PIN): vào lại từ đầu
  },
)
function reconnect() {
  start(props.pin)
}
function retry() {
  start(props.pin)
}
</script>

<template>
  <main class="page narrow play" :class="`step-${step}`">
    <!-- Nhập mã phòng -->
    <section v-if="step === 'enter'" class="stack">
      <h1 class="center">{{ t('play.title') }}</h1>
      <RoomCodeInput ref="codeInput" :busy="codeBusy" :error="codeError" @pictures="onPictures" @pin="onPin" />
    </section>

    <p v-else-if="step === 'checking'" class="center muted loading">{{ t('app.loading') }}</p>

    <StatusScreen v-else-if="step === 'blocked' && blocked" :title="blocked.title" :message="blocked.message" :tone="blocked.playHere ? 'info' : 'warn'">
      <button v-if="blocked.playHere" type="button" class="btn success" @click="retry">{{ t('play.playHere') }}</button>
      <button v-if="blocked.canRetry" type="button" class="btn" @click="retry">{{ t('app.retry') }}</button>
      <RouterLink v-if="blocked.canEnterCode" class="btn alt" to="/play">{{ t('play.enterCodeManually') }}</RouterLink>
      <RouterLink class="btn ghost" to="/">{{ t('app.backHome') }}</RouterLink>
    </StatusScreen>

    <!-- Nhập tên -->
    <form v-else-if="step === 'name'" class="card stack" @submit.prevent="toAvatar">
      <p class="room-tag">{{ t('play.roomTag', { pin: pin?.split('').join(' ') }) }}</p>
      <label class="big-label" for="nickname">{{ t('play.nickname') }}</label>
      <input
        id="nickname" v-model="nickname" class="input big-input" maxlength="20" autocomplete="nickname"
        enterkeyhint="next" :placeholder="t('play.nicknamePlaceholder')" autofocus
      />
      <p class="muted counter">{{ trimmed.length }}/20</p>
      <p v-if="joinError" class="error-text" role="alert">{{ joinError }}</p>
      <button type="submit" class="btn big block" :disabled="!nameValid">{{ t('play.next') }}</button>
    </form>

    <!-- Chọn nhân vật -->
    <section v-else-if="step === 'avatar' || step === 'joining'" class="stack">
      <h1 class="center">{{ t('play.pickAvatar') }}</h1>
      <AvatarPicker v-model="avatarId" :avatars="avatars" :counts="avatarCounts" :disabled="step === 'joining'" />
      <p v-if="joinError" class="error-text center" role="alert">{{ joinError }}</p>
      <div class="sticky-actions">
        <button type="button" class="btn ghost" :disabled="step === 'joining'" @click="step = 'name'">{{ t('app.back') }}</button>
        <button type="button" class="btn success big" :disabled="!avatarId || step === 'joining'" @click="join">
          {{ step === 'joining' ? t('app.loading') : t('play.join') }}
        </button>
      </div>
    </section>

    <!-- Trong phòng -->
    <template v-else-if="step === 'game'">
      <p v-if="!game.ready" class="center muted loading">{{ t('app.connection.connecting') }}</p>
      <template v-else>
        <ConnectionBanner :status="game.status" :ready="game.ready" @retry="reconnect" />
        <div class="game-top">
          <header class="me-head">
            <AvatarBadge v-if="game.me" :avatar-id="game.me.avatar_id" :nickname="game.me.nickname" size="md" />
            <span class="badge">{{ t(`phase.${phase}`) }}</span>
          </header>
          <div v-if="phase !== 'finished'" class="tabs" role="tablist">
            <button type="button" role="tab" class="tab" :class="{ active: tab === 'card' }" :aria-selected="tab === 'card'" @click="tab = 'card'">
              {{ t('play.tabCard') }}
            </button>
            <button type="button" role="tab" class="tab" :class="{ active: tab === 'question', attention: myTurn && tab !== 'question' }" :aria-selected="tab === 'question'" @click="tab = 'question'">
              {{ t('play.tabQuestion') }}
            </button>
          </div>
        </div>

        <!-- Kết thúc -->
        <section v-if="phase === 'finished'" class="result">
          <WinnerCelebration v-if="myWinner" :winners="game.winners" mode="me" :me-id="game.me?.id ?? null" />
          <template v-else>
            <WinnerCelebration v-if="game.winners.length" :winners="game.winners" mode="other" :me-id="game.me?.id ?? null" />
            <div v-else class="card center"><h2>{{ t('winner.endedByHost') }}</h2></div>
            <BingoCard v-if="game.card" class="my-card" :card="game.card" :marked="game.marked" size="md" />
          </template>
          <p class="muted center">{{ t('play.waitNewRound') }}</p>
        </section>

        <template v-else>
          <!-- Vé của tôi -->
          <section v-if="tab === 'card'" class="tab-pane" role="tabpanel">
            <p v-if="phase === 'reveal' && game.reveal" class="notice" :class="{ good: hasNewNumber }">
              {{ hasNewNumber ? t('play.youHaveIt', { n: game.reveal.number }) : t('play.youDontHaveIt', { n: game.reveal.number }) }}
            </p>
            <p v-else-if="phase === 'lobby'" class="notice">{{ t('play.waitStart') }}</p>
            <BingoCard
              v-if="game.card"
              :key="game.markSeq"
              class="my-card"
              :card="game.card"
              :marked="game.marked"
              :new-cell="game.lastMarkedCell"
              :animate-new="!!game.lastMarkedCell"
              size="md"
            />
            <DrawnNumbers :drawn="game.drawn" size="sm" />
          </section>

          <!-- Câu hỏi -->
          <section v-else class="tab-pane" role="tabpanel">
            <template v-if="phase === 'question' && shown">
              <div class="card stack q-card">
                <QuestionPanel :question="shown" :reason="reason" :is-me="myTurn" :timer-total="game.config?.timer_seconds ?? 0" size="md" />
                <div class="q-actions">
                <AnswerButtons
                  :options="shown.options" :interactive="myTurn" :disabled="game.answerLocked || holding"
                  :feedback="feedback" :pending-key="pendingKey" @choose="choose"
                />
                <button v-if="myTurn" type="button" class="btn alt block help" :disabled="game.answerLocked || holding" @click="askHelp">
                  {{ t('question.help') }}
                </button>
                <p v-else class="muted center">{{ t('play.watchHint') }}</p>
                </div>
              </div>
            </template>
            <p v-else-if="phase === 'lobby'" class="notice">{{ t('play.waitStart') }}</p>
            <p v-else-if="phase === 'reveal' && game.reveal" class="notice">{{ t('reveal.newNumber') }} {{ game.reveal.number }}</p>
            <p v-else-if="phase === 'ready'" class="notice">{{ game.lastSkipped ? t('screen.skipped') : t('screen.waitingNext') }}</p>
          </section>
        </template>
      </template>
    </template>
  </main>
</template>

<style scoped>
.play { max-width: 600px; display: flex; flex-direction: column; gap: 0.9rem; }
.loading { margin-top: 3rem; font-size: 1.2rem; }
.room-tag { font-weight: 800; color: var(--c-muted); margin: 0; }
.big-label { font-size: clamp(1.4rem, 5vw, 1.8rem); font-weight: 900; }
.big-input { font-size: 1.6rem; min-height: 60px; font-weight: 800; }
.counter { margin: 0; text-align: right; font-size: 0.9rem; }
.big { min-height: 60px; font-size: 1.35rem; }
.sticky-actions {
  position: sticky; bottom: 0; z-index: 5; display: flex; gap: 0.6rem;
  padding: 0.6rem 0 calc(0.6rem + var(--safe-b)); background: linear-gradient(to top, var(--c-bg) 75%, rgba(255, 248, 239, 0));
}
.sticky-actions .big { flex: 1; }
.me-head { display: flex; align-items: center; justify-content: space-between; gap: 0.6rem; min-width: 0; }
.tabs {
  display: grid; grid-template-columns: 1fr 1fr; gap: 0.4rem;
  background: #fff; padding: 0.3rem; border-radius: 999px; box-shadow: var(--shadow);
}
.tab { font: inherit; font-weight: 900; font-size: 1.1rem; min-height: 50px; border: none; border-radius: 999px; background: transparent; color: var(--c-muted); cursor: pointer; }
.tab.active { background: var(--c-primary); color: #fff; }
.tab.attention { background: #fff3b0; color: #6b5300; animation: blink 1s ease-in-out infinite; }
@keyframes blink { 50% { opacity: 0.6; } }
.tab-pane { display: flex; flex-direction: column; gap: 0.9rem; align-items: center; }
.tab-pane > * { width: 100%; }
.my-card { margin: 0 auto; }
.notice { text-align: center; font-weight: 900; font-size: clamp(1.2rem, 4.5vw, 1.6rem); margin: 0; }
.notice.good { color: var(--c-success); }
.help { min-height: 56px; font-size: 1.2rem; }
.game-top { display: flex; flex-direction: column; gap: 0.9rem; min-width: 0; }
.q-actions { display: flex; flex-direction: column; gap: 0.75rem; min-width: 0; }

/* điện thoại nằm ngang: tên + tab trên một hàng, câu hỏi bên trái, 4 đáp án bên phải */
@media (orientation: landscape) and (max-height: 520px) {
  .play { max-width: 900px; gap: 0.5rem; padding-bottom: calc(0.5rem + var(--safe-b)); }
  .game-top { flex-direction: row; align-items: center; gap: 0.6rem; }
  .game-top .me-head { flex: 0 1 auto; }
  .game-top .me-head :deep(.avatar-badge) { --s: 40px; }
  .game-top .tabs { position: static; flex: 1; }
  .tab { min-height: 44px; font-size: 1rem; }
  .q-card { display: grid; grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.4fr); gap: 0.6rem; align-items: center; padding: 0.6rem 0.8rem; }
  .q-actions { gap: 0.45rem; }
  .help { min-height: 44px; font-size: 1rem; }
  .q-actions .muted { margin: 0; }
  .my-card { width: min(100%, calc(100dvh - 110px)); min-width: 220px; }
}
.result { display: flex; flex-direction: column; gap: 1rem; align-items: center; }
.result > * { width: 100%; }
</style>
