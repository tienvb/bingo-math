<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useGameStore } from '@/stores/game'
import { useSessionStore } from '@/stores/session'
import { useAvatars } from '@/composables/useAvatars'
import { useAnswerFeedback } from '@/composables/useAnswerFeedback'
import { loadSoundEnabled, playTones, saveSoundEnabled } from '@/utils/device'
import { withLang } from '@/utils/format'
import AnswerButtons from '@/components/AnswerButtons.vue'
import ConnectionBanner from '@/components/ConnectionBanner.vue'
import DrawnNumbers from '@/components/DrawnNumbers.vue'
import LanguageSwitch from '@/components/LanguageSwitch.vue'
import PlayerList from '@/components/PlayerList.vue'
import QrCode from '@/components/QrCode.vue'
import QuestionPanel from '@/components/QuestionPanel.vue'
import RevealCarousel from '@/components/RevealCarousel.vue'
import RoomCodeDisplay from '@/components/RoomCodeDisplay.vue'
import StatusScreen from '@/components/StatusScreen.vue'
import WinnerCelebration from '@/components/WinnerCelebration.vue'

const props = defineProps<{ pin: string }>()
const route = useRoute()
const { t, locale } = useI18n()
const game = useGameStore()
const session = useSessionStore()
useAvatars()
const { shown, reason, feedback } = useAnswerFeedback()

const token = ref<string | null>(null)
function connect() {
  const q = route.query.token
  const fromUrl = typeof q === 'string' && q ? q : null
  if (fromUrl) session.set(props.pin, { screen_token: fromUrl })
  token.value = fromUrl ?? session.get(props.pin).screen_token ?? null
  if (token.value) game.connect(props.pin, 'screen', token.value)
}
watch(() => props.pin, connect, { immediate: true })
onBeforeUnmount(() => game.disconnect())

const phase = computed(() => game.phase)
const qrValue = computed(() => withLang(game.joinUrl, locale.value))
const lastNumber = computed(() => game.drawn[game.drawn.length - 1] ?? null)

// ---- âm thanh tùy chọn, mặc định tắt ----
const sound = ref(loadSoundEnabled())
function toggleSound() {
  sound.value = !sound.value
  saveSoundEnabled(sound.value)
  if (sound.value) playTones([660])
}
watch(
  () => game.lastAnswer,
  (a) => {
    if (!sound.value || !a) return
    playTones(a.correct ? [523, 659, 784] : [300, 220], a.correct ? 120 : 180)
  },
)
watch(phase, (p) => {
  if (sound.value && p === 'finished' && game.winners.length) playTones([523, 659, 784, 1046, 784, 1046], 150)
})
</script>

<template>
  <main class="screen" :class="`phase-${phase}`">
    <StatusScreen v-if="!token || game.ended === 'bad_token'" :title="t('screen.noToken')" :message="t('screen.noTokenHint')" tone="warn" />
    <StatusScreen v-else-if="game.ended === 'closed' || game.ended === 'not_found'" :title="t('play.roomClosed')" tone="info" />
    <p v-else-if="!game.ready" class="center muted loading">{{ t('app.connection.connecting') }}</p>

    <template v-else>
      <ConnectionBanner :status="game.status" :ready="game.ready" @retry="connect" />

      <header class="bar">
        <RoomCodeDisplay v-if="phase !== 'lobby'" class="corner-code" :pin="pin" :pictures="game.pictureCode" size="sm" />
        <span class="badge phase">{{ t(`phase.${phase}`) }}</span>
        <span class="spacer" />
        <button
          type="button" class="btn ghost small sound" :aria-pressed="sound"
          :aria-label="sound ? t('screen.soundOff') : t('screen.soundOn')" @click="toggleSound"
        >
          <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
            <path d="M4 9h4l5-4v14l-5-4H4z" fill="currentColor" />
            <path v-if="sound" d="M16 8.5a5 5 0 0 1 0 7M18.5 6a8.5 8.5 0 0 1 0 12" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" />
            <path v-else d="M16 9l5 6M21 9l-5 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
          </svg>
        </button>
        <LanguageSwitch compact />
      </header>

      <section class="stage">
        <!-- Sảnh -->
        <div v-if="phase === 'lobby'" class="lobby">
          <div class="lobby-code">
            <h1 class="join-title">{{ t('screen.joinTitle') }}</h1>
            <RoomCodeDisplay :pin="pin" :pictures="game.pictureCode" size="lg" />
            <div class="qr-wrap">
              <QrCode :value="qrValue" />
              <p class="url">{{ game.joinUrl }}</p>
            </div>
          </div>
          <div class="lobby-players card">
            <h2>{{ t('players.title') }} <span class="muted">({{ game.players.length }})</span></h2>
            <PlayerList :players="game.players" layout="tiles" />
            <p class="muted waiting">{{ t('screen.waitingStart') }}</p>
          </div>
        </div>

        <!-- Câu hỏi -->
        <div v-else-if="phase === 'question' && shown" class="question">
          <QuestionPanel :question="shown" :reason="reason" :timer-total="game.config?.timer_seconds ?? 0" size="lg" />
          <AnswerButtons :options="shown.options" :feedback="feedback" size="lg" />
        </div>

        <!-- Khoanh số -->
        <RevealCarousel v-else-if="phase === 'reveal' && game.reveal" :reveal="game.reveal" size="lg" />

        <!-- Chờ câu tiếp theo -->
        <div v-else-if="phase === 'ready'" class="ready">
          <template v-if="game.lastSkipped">
            <p class="ready-title">{{ t('screen.skipped') }}</p>
          </template>
          <template v-else-if="lastNumber !== null">
            <p class="muted">{{ t('screen.lastNumber') }}</p>
            <strong class="last" :style="{ '--d': String(lastNumber).length }">{{ lastNumber }}</strong>
          </template>
          <p class="ready-title">{{ t('screen.waitingNext') }}</p>
        </div>

        <!-- Kết thúc -->
        <div v-else-if="phase === 'finished'" class="finished">
          <WinnerCelebration v-if="game.winners.length" :winners="game.winners" mode="screen" />
          <div v-else class="ended">
            <h1>{{ t('winner.endedByHost') }}</h1>
            <p class="muted">{{ t('screen.waitingNewRound') }}</p>
          </div>
        </div>
      </section>

      <footer v-if="phase !== 'lobby'" class="strip">
        <DrawnNumbers :drawn="game.drawn" scroll />
      </footer>
    </template>
  </main>
</template>

<style scoped>
.screen {
  min-height: 100vh; min-height: 100dvh; display: flex; flex-direction: column; width: 100%;
  padding: calc(0.5rem + var(--safe-t)) calc(var(--gutter) + var(--safe-r)) calc(0.5rem + var(--safe-b)) calc(var(--gutter) + var(--safe-l));
  background: radial-gradient(circle at 20% 0%, #fff 0, var(--c-bg) 60%);
}
.loading { margin-top: 3rem; font-size: 1.4rem; }
.bar { display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap; min-height: 52px; }
.spacer { flex: 1; }
.corner-code { background: #fff; border-radius: 999px; padding: 0.2rem 0.8rem; box-shadow: var(--shadow); }
.phase { font-size: clamp(0.9rem, 1.4vw, 1.2rem); }
.sound { width: 44px; height: 44px; padding: 0; }
.stage { flex: 1; display: flex; align-items: center; justify-content: center; min-height: 0; padding: clamp(0.5rem, 2vh, 1.5rem) 0; }
.stage > * { width: 100%; }

.lobby { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr); gap: clamp(1rem, 3vw, 3rem); align-items: center; }
.lobby-code { display: flex; flex-direction: column; align-items: center; gap: clamp(0.8rem, 2vh, 1.6rem); min-width: 0; }
.join-title { text-align: center; font-size: clamp(1.6rem, 3.4vw, 3.4rem); }
.qr-wrap { width: min(100%, 34vh, 360px); min-width: min(100%, 200px); display: flex; flex-direction: column; gap: 0.4rem; align-items: center; }
.url { font-weight: 700; color: var(--c-muted); text-align: center; overflow-wrap: anywhere; font-size: clamp(0.9rem, 1.3vw, 1.3rem); }
.lobby-players { align-self: stretch; display: flex; flex-direction: column; gap: 0.6rem; max-height: calc(100dvh - 120px); overflow-y: auto; }
.waiting { text-align: center; font-size: clamp(1rem, 1.6vw, 1.5rem); margin-top: auto; }

.question { display: flex; flex-direction: column; gap: clamp(1rem, 3vh, 2.5rem); max-width: 1500px; margin: 0 auto; }

.ready { text-align: center; display: flex; flex-direction: column; align-items: center; gap: 0.5rem; }
.ready .muted { font-size: clamp(1.2rem, 2.5vw, 2rem); margin: 0; }
.last { font-size: min(clamp(5rem, 22vh, 14rem), calc(92vw / (var(--d, 2) * 0.62))); line-height: 1; color: var(--c-mark); font-weight: 900; white-space: nowrap; }
.ready-title { font-size: clamp(1.4rem, 3.2vw, 3rem); font-weight: 900; margin: 0; }
.ended { text-align: center; }
.ended h1 { font-size: clamp(2rem, 5vw, 4.5rem); }

.strip { background: #fff; border-radius: 1rem; padding: 0.5rem 0.9rem; box-shadow: var(--shadow); min-width: 0; }

@media (orientation: landscape) and (max-height: 520px) {
  .bar { min-height: 44px; gap: 0.5rem; }
  .stage { padding: 0.25rem 0; }
  .question { gap: 0.5rem; }
  .strip { padding: 0.25rem 0.6rem; }
}

/* màn hình hẹp (laptop nhỏ dọc, điện thoại): xếp dọc */
@media (max-width: 900px), (orientation: portrait) {
  .lobby { grid-template-columns: minmax(0, 1fr); }
  .lobby-players { max-height: none; }
}
</style>
