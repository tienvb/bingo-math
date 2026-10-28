<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import confetti from 'canvas-confetti'
import type { Winner } from '@/api/contract'
import { useAvatars } from '@/composables/useAvatars'
import { prefersReducedMotion, vibrate } from '@/utils/device'
import AvatarBadge from './AvatarBadge.vue'
import BingoCard from './BingoCard.vue'
import LottiePlayer from './LottiePlayer.vue'

const props = withDefaults(
  defineProps<{
    winners: Winner[]
    /** screen: màn hình chính · me: điện thoại người thắng · other: điện thoại người khác */
    mode?: 'screen' | 'me' | 'other'
    meId?: string | null
  }>(),
  { mode: 'screen', meId: null },
)
const { t } = useI18n()
const { byId } = useAvatars()

const PER_WINNER_MS = 6000
const index = ref(0)
let cycle: ReturnType<typeof setInterval> | null = null
let burstTimer: ReturnType<typeof setInterval> | null = null

const list = computed(() => {
  if (props.mode === 'me' && props.meId) {
    const mine = props.winners.filter((w) => w.player_id === props.meId)
    return mine.length ? mine : props.winners
  }
  return props.winners
})
const current = computed(() => list.value[index.value % Math.max(1, list.value.length)] ?? null)
const currentAvatar = computed(() => byId(current.value?.avatar_id))
const color = computed(() => currentAvatar.value?.color ?? '#ff7a59')
/** Lottie lỗi tải thì đánh dấu để quay về hiệu ứng nhún nhảy. */
const lottieFailed = ref(new Set<string>())
const winAnim = computed<{ kind: 'img' | 'lottie'; url: string } | null>(() => {
  const url = currentAvatar.value?.win_animation_url
  if (!url) return null
  // GIF/WebP dùng <img>; Lottie JSON dùng lottie-web (tải động, chunk riêng)
  if (/\.json(\?|#|$)/i.test(url)) return lottieFailed.value.has(url) ? null : { kind: 'lottie', url }
  // reduced motion: ảnh động có thể tự chạy, nên dùng ảnh nhân vật tĩnh
  return prefersReducedMotion() ? null : { kind: 'img', url }
})
function onLottieError(url: string) {
  lottieFailed.value = new Set([...lottieFailed.value, url])
}
const others = computed(() => props.winners.filter((w) => w.player_id !== props.meId))

function burst(c: string) {
  if (props.mode === 'other') return
  const reduced = prefersReducedMotion()
  const colors = [c, '#ffd43b', '#ffffff', '#ff7a59']
  try {
    void confetti({
      particleCount: reduced ? 30 : props.mode === 'screen' ? 160 : 110,
      spread: 80, startVelocity: reduced ? 20 : 48, origin: { y: 0.65 }, colors,
      disableForReducedMotion: false, ticks: reduced ? 80 : 220, scalar: props.mode === 'screen' ? 1.3 : 1,
    })
    if (!reduced) {
      void confetti({ particleCount: 60, angle: 60, spread: 60, origin: { x: 0, y: 0.75 }, colors })
      void confetti({ particleCount: 60, angle: 120, spread: 60, origin: { x: 1, y: 0.75 }, colors })
    }
  } catch {
    /* bỏ qua */
  }
}

watch(current, (w, prev) => {
  if (w && w.player_id !== prev?.player_id) burst(color.value)
})

onMounted(() => {
  burst(color.value)
  if (props.mode === 'me') vibrate([200, 100, 200, 100, 400])
  if (list.value.length > 1) cycle = setInterval(() => (index.value = (index.value + 1) % list.value.length), PER_WINNER_MS)
  else if (props.mode !== 'other' && !prefersReducedMotion()) burstTimer = setInterval(() => burst(color.value), 4500)
})
onBeforeUnmount(() => {
  if (cycle) clearInterval(cycle)
  if (burstTimer) clearInterval(burstTimer)
  try {
    confetti.reset()
  } catch {
    /* bỏ qua */
  }
})
</script>

<template>
  <section class="celebration" :class="mode" :style="{ '--win-color': color }" aria-live="polite">
    <template v-if="mode === 'other'">
      <h2 class="title">{{ t('winner.congratsOthers') }}</h2>
      <ul class="small-list">
        <li v-for="w in winners" :key="w.player_id">
          <AvatarBadge :avatar-id="w.avatar_id" :nickname="w.nickname" size="lg" layout="column" />
        </li>
      </ul>
      <p class="muted">{{ t('winner.betterLuck') }}</p>
    </template>

    <template v-else-if="current">
      <h2 class="title bingo">{{ t('winner.bingo') }}</h2>
      <Transition name="swap" mode="out-in">
        <div :key="current.player_id" class="stage">
          <div class="hero">
            <div class="sparkles" aria-hidden="true">
              <span v-for="i in 8" :key="i" :style="{ '--i': i }" />
            </div>
            <img v-if="winAnim?.kind === 'img'" class="win-anim" :src="winAnim.url" :alt="current.nickname" />
            <LottiePlayer
              v-else-if="winAnim?.kind === 'lottie'" :key="winAnim.url" :src="winAnim.url" :label="current.nickname"
              @error="onLottieError(winAnim.url)"
            />
            <div v-else class="bouncer">
              <AvatarBadge :avatar-id="current.avatar_id" :nickname="current.nickname" size="xl" layout="none" />
            </div>
            <p class="name">{{ mode === 'me' ? t('winner.youWon') : t('winner.wins', { name: current.nickname }) }}</p>
          </div>
          <BingoCard
            class="win-card" :card="current.card" :marked="current.marked" :winning-lines="current.lines"
            :player="{ nickname: current.nickname, avatar_id: current.avatar_id }" :size="mode === 'screen' ? 'lg' : 'md'"
          />
        </div>
      </Transition>
      <p v-if="mode === 'me' && others.length" class="also muted">
        {{ t('winner.alsoWon', { names: others.map((w) => w.nickname).join(', ') }) }}
      </p>
      <ol v-if="list.length > 1" class="dots" aria-hidden="true">
        <li v-for="(w, i) in list" :key="w.player_id" :class="{ on: i === index % list.length }" />
      </ol>
    </template>
  </section>
</template>

<style scoped>
.celebration { display: flex; flex-direction: column; align-items: center; gap: 0.8rem; width: 100%; text-align: center; }
.title { margin: 0; font-size: clamp(1.6rem, 5vw, 3rem); }
.bingo {
  font-size: clamp(2.6rem, 10vw, 6rem); font-weight: 900; letter-spacing: 0.05em; color: var(--win-color);
  text-shadow: 0 4px 0 rgba(0, 0, 0, 0.12); animation: pop-in 0.5s ease-out;
}
.stage { display: grid; grid-template-columns: minmax(0, 1fr); gap: 1rem; align-items: center; justify-items: center; width: 100%; }
@media (min-width: 900px) and (orientation: landscape) {
  .screen .stage { grid-template-columns: minmax(0, 1fr) minmax(0, 1.1fr); }
}
@media (min-width: 640px) and (orientation: landscape) {
  .me .stage { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }
}
.hero { position: relative; display: flex; flex-direction: column; align-items: center; gap: 0.8rem; min-width: 0; }
.bouncer { animation: bounce 1.2s ease-in-out infinite; transform-origin: 50% 100%; }
.win-anim { width: clamp(140px, 32vw, 320px); aspect-ratio: 1; object-fit: contain; }
.name { font-weight: 900; font-size: clamp(1.5rem, 4.5vw, 3.2rem); margin: 0; overflow-wrap: anywhere; }
.screen .win-card { width: min(100%, calc(100dvh - 330px), 640px); min-width: min(100%, 280px); }
.sparkles { position: absolute; inset: -10%; pointer-events: none; }
.sparkles span {
  position: absolute; left: 50%; top: 40%; width: 18px; height: 18px; margin: -9px;
  background: radial-gradient(circle, #fff 0 20%, var(--c-win) 40%, transparent 70%);
  transform: rotate(calc(var(--i) * 45deg)) translateY(calc(-1 * clamp(90px, 20vw, 190px)));
  animation: twinkle 1.6s ease-in-out calc(var(--i) * 0.2s) infinite;
}
@keyframes bounce {
  0%, 100% { transform: translateY(0) rotate(-4deg) scale(1); }
  30% { transform: translateY(-14%) rotate(4deg) scale(1.04, 0.98); }
  55% { transform: translateY(0) rotate(-2deg) scale(1.05, 0.94); }
  75% { transform: translateY(-5%) rotate(2deg); }
}
@keyframes twinkle {
  0%, 100% { opacity: 0.2; scale: 0.6; }
  50% { opacity: 1; scale: 1.3; }
}
.small-list { list-style: none; display: flex; flex-wrap: wrap; justify-content: center; gap: 1rem; padding: 0; margin: 0; }
.dots { list-style: none; display: flex; gap: 0.4rem; padding: 0; margin: 0; }
.dots li { width: 12px; height: 12px; border-radius: 50%; background: #e3d6c3; }
.dots li.on { background: var(--win-color); }
.swap-enter-active { animation: pop-in 0.4s ease-out; }
.swap-leave-active { transition: opacity 0.25s; }
.swap-leave-to { opacity: 0; }
@media (prefers-reduced-motion: reduce) {
  .bouncer { animation: none; }
  .sparkles span { animation: none; opacity: 0.8; }
}
</style>
