<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { AnswererMode, GameConfig, PlayerInfo } from '@/api/contract'
import { api } from '@/api/rest'
import { useGameStore } from '@/stores/game'
import { useSessionStore } from '@/stores/session'
import { useErrorText } from '@/composables/useErrorText'
import { useAvatars } from '@/composables/useAvatars'
import { useAnswerFeedback } from '@/composables/useAnswerFeedback'
import AnswerButtons from '@/components/AnswerButtons.vue'
import AvatarBadge from '@/components/AvatarBadge.vue'
import BaseDialog from '@/components/BaseDialog.vue'
import ConfigForm from '@/components/ConfigForm.vue'
import ConnectionBanner from '@/components/ConnectionBanner.vue'
import DrawnNumbers from '@/components/DrawnNumbers.vue'
import JoinLinkPanel from '@/components/JoinLinkPanel.vue'
import PlayerList from '@/components/PlayerList.vue'
import QuestionPanel from '@/components/QuestionPanel.vue'
import RoomCodeDisplay from '@/components/RoomCodeDisplay.vue'
import StatusScreen from '@/components/StatusScreen.vue'

const props = defineProps<{ pin: string }>()
const { t } = useI18n()
const game = useGameStore()
const session = useSessionStore()
const errText = useErrorText()
useAvatars()
const { shown, reason, feedback } = useAnswerFeedback()

const tokens = ref(session.get(props.pin))
const hasToken = computed(() => !!tokens.value.host_token)
const screenHref = computed(() =>
  tokens.value.screen_token ? `/screen/${props.pin}?token=${encodeURIComponent(tokens.value.screen_token)}` : null,
)

function connect() {
  tokens.value = session.get(props.pin)
  if (tokens.value.host_token) game.connect(props.pin, 'host', tokens.value.host_token)
}
watch(() => props.pin, connect, { immediate: true })
onBeforeUnmount(() => game.disconnect())

// ---- lệnh ----
const busy = ref<string | null>(null)
const error = ref<string | null>(null)
async function run(name: string, fn: () => Promise<unknown>): Promise<boolean> {
  error.value = null
  busy.value = name
  try {
    await fn()
    return true
  } catch (e) {
    error.value = errText(e)
    return false
  } finally {
    busy.value = null
  }
}
const phase = computed(() => game.phase)
const canNext = computed(() => phase.value === 'ready')
const canSkipHelp = computed(() => phase.value === 'question')
const canEnd = computed(() => ['question', 'reveal', 'ready'].includes(phase.value))
const canNewRound = computed(() => phase.value === 'finished')
const canEditConfig = computed(() => phase.value === 'lobby' || phase.value === 'finished')

const next = () => run('next', () => api.next(props.pin))
const skip = () => run('skip', () => api.skip(props.pin))
const help = () => run('help', () => api.help(props.pin))
const end = () => run('end', () => api.end(props.pin))
const newRound = () => run('newRound', () => api.newRound(props.pin, { join_base_url: session.resolveJoinBaseUrl() }))

// ---- bắt đầu ----
const startOpen = ref(false)
const mode = ref<AnswererMode>('random')
const fixedId = ref<string>('')
function openStart() {
  error.value = null
  mode.value = 'random'
  fixedId.value = game.players.find((p) => p.connected)?.id ?? game.players[0]?.id ?? ''
  startOpen.value = true
}
async function start() {
  const ok = await run('start', () =>
    api.start(props.pin, { answerer_mode: mode.value, fixed_player_id: mode.value === 'fixed' ? fixedId.value || null : null }),
  )
  if (ok) startOpen.value = false
}

// ---- kick ----
const kickTarget = ref<PlayerInfo | null>(null)
async function kick() {
  const p = kickTarget.value
  if (!p) return
  const ok = await run(`kick-${p.id}`, () => api.kickPlayer(props.pin, p.id))
  if (ok) kickTarget.value = null
}

// ---- cấu hình ----
const draft = ref<GameConfig | null>(null)
const dirty = ref(false)
const configSaved = ref(false)
watch(
  () => game.config,
  (c) => {
    if (c && !dirty.value) draft.value = JSON.parse(JSON.stringify(c)) as GameConfig
  },
  { immediate: true },
)
function onDraft(c: GameConfig) {
  draft.value = c
  dirty.value = true
  configSaved.value = false
}
async function saveConfig() {
  if (!draft.value) return
  const cfg = draft.value
  const ok = await run('config', () => api.updateConfig(props.pin, cfg))
  if (ok) {
    dirty.value = false
    configSaved.value = true
    session.saveLastConfig(cfg)
  }
}
function resetConfig() {
  dirty.value = false
  if (game.config) draft.value = JSON.parse(JSON.stringify(game.config)) as GameConfig
}

// ---- đóng phòng ----
const closeOpen = ref(false)
const closedByMe = ref(false)
async function closeRoom() {
  const ok = await run('close', () => api.closeRoom(props.pin))
  if (ok) {
    closeOpen.value = false
    closedByMe.value = true
    session.clear(props.pin)
    game.disconnect()
  }
}

const notHost = computed(() => !hasToken.value || game.ended === 'bad_token')
const closed = computed(() => closedByMe.value || game.ended === 'closed' || game.ended === 'not_found')
watch(closed, (c) => c && session.clear(props.pin, ['host_token', 'screen_token']))

const answererLabel = computed(() =>
  game.answererMode === 'fixed'
    ? t('host.modeFixedWith', { name: game.players.find((p) => p.id === game.fixedPlayerId)?.nickname ?? '?' })
    : game.answererMode === 'random'
      ? t('host.modeRandom')
      : '',
)
const lastAnswerText = computed(() => {
  const a = game.lastAnswer
  if (!a || phase.value !== 'question') return ''
  const name = game.players.find((p) => p.id === a.player_id)?.nickname ?? '?'
  return t(a.correct ? 'host.lastAnswerRight' : 'host.lastAnswerWrong', { name, key: a.key, value: a.value })
})
</script>

<template>
  <main class="page host">
    <StatusScreen v-if="notHost" :title="t('host.notHost')" :message="t('host.notHostHint')" tone="warn" />
    <StatusScreen v-else-if="closed" :title="t('play.roomClosed')" :message="t('host.closedHint')" tone="info">
      <RouterLink class="btn" to="/create">{{ t('home.createRoom') }}</RouterLink>
      <RouterLink class="btn ghost" to="/">{{ t('app.backHome') }}</RouterLink>
    </StatusScreen>
    <p v-else-if="!game.ready" class="center muted loading">{{ t('app.connection.connecting') }}</p>

    <template v-else>
      <ConnectionBanner :status="game.status" :ready="game.ready" @retry="connect" />

      <header class="host-head">
        <div class="titles">
          <h1>{{ t('host.title') }}</h1>
          <div class="row">
            <span class="badge phase" :class="phase">{{ t(`phase.${phase}`) }}</span>
            <span v-if="answererLabel" class="badge">{{ answererLabel }}</span>
            <span class="badge">{{ t('host.playerCount', { n: game.players.length }) }}</span>
          </div>
        </div>
        <RoomCodeDisplay :pin="pin" :pictures="game.pictureCode" size="sm" />
        <a v-if="screenHref" class="btn alt" :href="screenHref" target="_blank" rel="noopener">{{ t('host.openScreen') }}</a>
      </header>

      <div class="host-grid">
        <div class="col-main">
          <!-- bảng điều khiển theo phase -->
          <section class="card control" :aria-label="t('host.controls')">
            <template v-if="phase === 'lobby'">
              <h2>{{ t('host.lobbyTitle') }}</h2>
              <p class="muted">{{ t('host.lobbyHint') }}</p>
            </template>

            <template v-else-if="phase === 'question' && shown">
              <QuestionPanel :question="shown" :reason="reason" :timer-total="game.config?.timer_seconds ?? 0" size="sm" />
              <AnswerButtons :options="shown.options" :feedback="feedback" />
              <p v-if="lastAnswerText" class="muted">{{ lastAnswerText }}</p>
            </template>

            <template v-else-if="phase === 'reveal' && game.reveal">
              <h2>{{ t('reveal.newNumber') }} <span class="num">{{ game.reveal.number }}</span></h2>
              <p>{{ game.reveal.items.length ? t('host.revealOn', { n: game.reveal.items.length }) : t('reveal.nobody', { n: game.reveal.number }) }}</p>
              <ul v-if="game.reveal.items.length" class="who-has">
                <li v-for="it in game.reveal.items" :key="it.player_id">
                  <AvatarBadge :avatar-id="it.avatar_id" :nickname="it.nickname" size="xs" />
                </li>
              </ul>
            </template>

            <template v-else-if="phase === 'ready'">
              <h2>{{ t('host.readyTitle') }}</h2>
              <p v-if="game.lastSkipped" class="muted">{{ t('host.skipped', { n: game.lastSkipped.number }) }}</p>
              <p v-else class="muted">{{ t('host.readyHint') }}</p>
            </template>

            <template v-else-if="phase === 'finished'">
              <h2>{{ t('phase.finished') }}</h2>
              <template v-if="game.winners.length">
                <p>{{ t('host.winners') }}</p>
                <ul class="who-has">
                  <li v-for="w in game.winners" :key="w.player_id">
                    <AvatarBadge :avatar-id="w.avatar_id" :nickname="w.nickname" size="sm" />
                  </li>
                </ul>
              </template>
              <p v-else class="muted">{{ t('winner.endedByHost') }}</p>
            </template>

            <p v-if="error && !startOpen && !closeOpen && !kickTarget" class="error-text" role="alert">{{ error }}</p>
          </section>

          <!-- nút điều khiển chính: trên điện thoại cố định ở đáy màn hình -->
          <div class="action-bar" role="toolbar" :aria-label="t('host.controls')">
            <button v-if="phase === 'lobby'" type="button" class="btn success main" :disabled="!game.players.length || !!busy" @click="openStart">
              {{ t('host.start') }}
            </button>
            <button v-if="phase !== 'lobby' && phase !== 'finished'" type="button" class="btn success main" :disabled="!canNext || !!busy" @click="next">
              {{ t('host.next') }}
            </button>
            <button v-if="phase === 'finished'" type="button" class="btn success main" :disabled="!canNewRound || !!busy" @click="newRound">
              {{ t('host.newRound') }}
            </button>
            <template v-if="phase !== 'lobby' && phase !== 'finished'">
              <button type="button" class="btn alt" :disabled="!canSkipHelp || !!busy" @click="help">{{ t('host.help') }}</button>
              <button type="button" class="btn warn" :disabled="!canSkipHelp || !!busy" @click="skip">{{ t('host.skip') }}</button>
              <button type="button" class="btn danger" :disabled="!canEnd || !!busy" @click="end">{{ t('host.end') }}</button>
            </template>
          </div>

          <section class="card">
            <DrawnNumbers :drawn="game.drawn" size="sm" />
          </section>

          <section class="card">
            <h2>{{ t('players.title') }} <span class="muted">({{ game.players.length }})</span></h2>
            <PlayerList
              :players="game.players" :kickable="phase === 'lobby'" :highlight-id="shown?.answerer.id ?? null"
              :busy-id="busy?.startsWith('kick-') ? busy.slice(5) : null" @kick="kickTarget = $event"
            />
          </section>

          <section v-if="canEditConfig && draft" class="card stack">
            <h2>{{ t('host.config') }}</h2>
            <p class="muted">{{ phase === 'lobby' ? t('host.configLobbyHint') : t('host.configFinishedHint') }}</p>
            <ConfigForm :model-value="draft" :disabled="busy === 'config'" @update:model-value="onDraft" />
            <div class="row">
              <button type="button" class="btn" :disabled="!dirty || busy === 'config'" @click="saveConfig">{{ t('host.saveConfig') }}</button>
              <button type="button" class="btn ghost" :disabled="!dirty" @click="resetConfig">{{ t('host.resetConfig') }}</button>
              <span v-if="configSaved" class="badge ok">{{ t('host.configSaved') }}</span>
            </div>
          </section>
        </div>

        <div class="col-side">
          <JoinLinkPanel :pin="pin" :join-url="game.joinUrl" :pictures="game.pictureCode" />
          <section class="card stack danger-zone">
            <button type="button" class="btn danger" @click="closeOpen = true">{{ t('host.closeRoom') }}</button>
          </section>
        </div>
      </div>

      <BaseDialog :open="startOpen" :title="t('host.startTitle')" @close="startOpen = false">
        <fieldset class="modes">
          <legend class="field-label">{{ t('host.answererMode') }}</legend>
          <label class="mode" :class="{ on: mode === 'random' }">
            <input v-model="mode" type="radio" value="random" />
            <span><strong>{{ t('host.modeRandom') }}</strong><span class="muted block">{{ t('host.modeRandomHint') }}</span></span>
          </label>
          <label class="mode" :class="{ on: mode === 'fixed' }">
            <input v-model="mode" type="radio" value="fixed" />
            <span><strong>{{ t('host.modeFixed') }}</strong><span class="muted block">{{ t('host.modeFixedHint') }}</span></span>
          </label>
        </fieldset>
        <div v-if="mode === 'fixed'" class="field">
          <label for="fixed-player">{{ t('host.fixedPlayer') }}</label>
          <select id="fixed-player" v-model="fixedId" class="input">
            <option v-for="p in game.players" :key="p.id" :value="p.id">
              {{ p.nickname }}{{ p.connected ? '' : ` (${t('players.offline')})` }}
            </option>
          </select>
        </div>
        <p v-if="error" class="error-text" role="alert">{{ error }}</p>
        <template #actions>
          <button type="button" class="btn ghost" @click="startOpen = false">{{ t('app.cancel') }}</button>
          <button type="button" class="btn success" :disabled="busy === 'start' || (mode === 'fixed' && !fixedId)" @click="start">
            {{ t('host.start') }}
          </button>
        </template>
      </BaseDialog>

      <BaseDialog :open="!!kickTarget" :title="t('players.kickTitle')" @close="kickTarget = null">
        <p v-if="kickTarget">{{ t('players.kickConfirm', { name: kickTarget.nickname }) }}</p>
        <p v-if="error" class="error-text" role="alert">{{ error }}</p>
        <template #actions>
          <button type="button" class="btn ghost" @click="kickTarget = null">{{ t('app.cancel') }}</button>
          <button type="button" class="btn danger" :disabled="!!busy" @click="kick">{{ t('players.kick') }}</button>
        </template>
      </BaseDialog>

      <BaseDialog :open="closeOpen" :title="t('host.closeRoom')" @close="closeOpen = false">
        <p>{{ t('host.closeConfirm') }}</p>
        <p v-if="error" class="error-text" role="alert">{{ error }}</p>
        <template #actions>
          <button type="button" class="btn ghost" @click="closeOpen = false">{{ t('app.cancel') }}</button>
          <button type="button" class="btn danger" :disabled="busy === 'close'" @click="closeRoom">{{ t('host.closeRoom') }}</button>
        </template>
      </BaseDialog>
    </template>
  </main>
</template>

<style scoped>
.host { max-width: 1400px; }
.loading { margin-top: 3rem; font-size: 1.2rem; }
.host-head { display: flex; flex-wrap: wrap; align-items: center; gap: 0.8rem 1.2rem; margin-bottom: 1rem; }
.titles { flex: 1 1 260px; min-width: 0; }
.titles h1 { margin: 0 0 0.3rem; }
.phase { background: #dff2ff; color: #145a8a; }
.phase.question { background: #ffe8d6; color: #8a3b12; }
.phase.reveal { background: #fff3b0; color: #6b5300; }
.phase.finished { background: #e6f8ee; color: #136b3f; }
.host-grid { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr); gap: 1rem; align-items: start; }
.col-main, .col-side { display: flex; flex-direction: column; gap: 1rem; min-width: 0; }
.control { display: flex; flex-direction: column; gap: 0.8rem; }
.control h2 { margin: 0; }
.num { color: var(--c-mark); }
.who-has { list-style: none; display: flex; flex-wrap: wrap; gap: 0.5rem 1rem; padding: 0; margin: 0; }
.action-bar { display: flex; flex-wrap: wrap; gap: 0.6rem; }
.action-bar .btn { flex: 1 1 auto; min-height: 52px; font-size: 1.1rem; }
.action-bar .main { flex: 2 1 200px; font-size: 1.25rem; }
.danger-zone { align-items: flex-start; }
.ok { background: #e6f8ee; color: #136b3f; }
.modes { border: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 0.6rem; }
.mode { display: flex; gap: 0.7rem; align-items: flex-start; padding: 0.7rem; border-radius: 1rem; border: 3px solid var(--c-border); cursor: pointer; min-height: var(--tap); }
.mode.on { border-color: var(--c-success); background: #e6f8ee; }
.mode input { width: 24px; height: 24px; margin: 0.15rem 0 0; accent-color: var(--c-success); flex: none; }
.block { display: block; font-size: 0.92rem; }

/* điện thoại / tablet dọc: một cột, nút điều khiển chính cố định ở đáy */
@media (max-width: 900px) {
  .host-grid { grid-template-columns: minmax(0, 1fr); }
  .host { padding-bottom: calc(150px + var(--safe-b)); }
  .action-bar {
    position: fixed; z-index: 20; left: 0; right: 0; bottom: 0;
    padding: 0.6rem calc(0.75rem + var(--safe-r)) calc(0.6rem + var(--safe-b)) calc(0.75rem + var(--safe-l));
    background: rgba(255, 255, 255, 0.96); box-shadow: 0 -6px 18px rgba(43, 45, 66, 0.12);
    backdrop-filter: blur(6px);
  }
  .action-bar .btn { min-height: 48px; font-size: 1rem; padding: 0.5rem 0.7rem; }
  .action-bar .main { flex-basis: 100%; }
}
@media (max-width: 900px) and (orientation: landscape) and (max-height: 500px) {
  .host { padding-bottom: calc(90px + var(--safe-b)); }
  .action-bar .main { flex-basis: auto; }
}
</style>
