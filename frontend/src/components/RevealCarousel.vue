<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Reveal } from '@/api/contract'
import { useGameStore } from '@/stores/game'
import { revealPosition } from '@/utils/time'
import BingoCard from './BingoCard.vue'

/** sm: gọn cho trang điều khiển của chủ phòng; md: điện thoại; lg: màn hình chính 1920 × 1080. */
const props = withDefaults(defineProps<{ reveal: Reveal; size?: 'sm' | 'md' | 'lg' }>(), { size: 'lg' })
const { t } = useI18n()
const game = useGameStore()

// Đồng bộ theo started_at: mở lại tab giữa chừng vẫn đúng vé đang hiện.
const pos = computed(() => revealPosition(props.reveal, game.serverNow))
const item = computed(() => props.reveal.items[pos.value.index] ?? null)
const perMs = computed(() => Math.max(1, props.reveal.seconds_per_card) * 1000)
const progress = computed(() => Math.min(1, pos.value.elapsedInCard / perMs.value))
const cardSize = computed(() => (props.size === 'sm' ? 'md' : props.size))
const digits = computed(() => String(props.reveal.number).length)
</script>

<template>
  <section class="reveal" :class="size" :style="{ '--d': digits }" aria-live="polite">
    <header class="head">
      <span class="new-number">
        {{ t('reveal.newNumber') }} <strong class="num">{{ reveal.number }}</strong>
      </span>
      <span v-if="reveal.items.length" class="counter">
        {{ t('reveal.cardOf', { i: pos.index + 1, n: reveal.items.length }) }}
      </span>
    </header>

    <div v-if="item" class="stage">
      <Transition name="card" mode="out-in">
        <BingoCard
          :key="`${reveal.started_at}-${pos.index}`"
          class="the-card"
          :card="item.card"
          :marked="item.marked_before"
          :new-cell="item.new_cell"
          :animate-new="true"
          :player="{ nickname: item.nickname, avatar_id: item.avatar_id }"
          :size="cardSize"
        />
      </Transition>
      <div class="progress" aria-hidden="true"><span :style="{ transform: `scaleX(${progress})` }" /></div>
      <ol v-if="reveal.items.length > 1" class="dots" aria-hidden="true">
        <li v-for="(it, i) in reveal.items" :key="it.player_id" :class="{ on: i === pos.index, done: i < pos.index }" />
      </ol>
    </div>

    <div v-else class="nobody">
      <strong class="big">{{ reveal.number }}</strong>
      <p>{{ t('reveal.nobody', { n: reveal.number }) }}</p>
    </div>
  </section>
</template>

<style scoped>
.reveal { display: flex; flex-direction: column; align-items: center; gap: clamp(0.4rem, 1.5vh, 1rem); width: 100%; min-height: 0; }
.head { display: flex; flex-wrap: wrap; gap: 0.5rem 1.5rem; align-items: baseline; justify-content: center; text-align: center; }
.reveal { container-type: inline-size; }
.head { max-width: 100%; }
.new-number { font-weight: 900; font-size: clamp(1.4rem, 4vw, 3rem); max-width: 100%; overflow-wrap: anywhere; }
.num { color: var(--c-mark); font-size: 1.35em; }
.sm .new-number { font-size: clamp(1.25rem, 3vw, 1.8rem); }
.sm .counter { font-size: clamp(1rem, 2vw, 1.3rem); }
.counter { font-weight: 800; color: var(--c-muted); font-size: clamp(1.1rem, 2.5vw, 2rem); }
.stage { display: flex; flex-direction: column; align-items: center; gap: 0.6rem; width: 100%; min-height: 0; }
/* lg: vé vừa chiều cao màn hình 1080p (trừ tiêu đề và dải số đã ra) */
.lg .the-card { width: min(100%, calc(100dvh - 300px), 720px); min-width: min(100%, 300px); }
.md .the-card { width: min(100%, 460px); }
/* sm (trang host): vé co theo bề rộng và chiều cao còn lại, để nút điều khiển vẫn trong tầm với */
.sm .the-card { width: min(100%, 420px, max(240px, calc(100dvh - 380px))); }
.progress { width: min(100%, 420px); height: 8px; background: #efe3d1; border-radius: 99px; overflow: hidden; }
.progress span { display: block; height: 100%; background: var(--c-secondary); transform-origin: left; transition: transform 0.25s linear; }
.dots { list-style: none; display: flex; flex-wrap: wrap; justify-content: center; gap: 0.4rem; padding: 0; margin: 0; }
.dots li { width: 12px; height: 12px; border-radius: 50%; background: #e3d6c3; }
.dots li.done { background: #b8c7d6; }
.dots li.on { background: var(--c-secondary); transform: scale(1.3); }
.nobody { text-align: center; font-weight: 800; font-size: clamp(1.3rem, 3.5vw, 2.6rem); }
.nobody { max-width: 100%; }
.nobody p { overflow-wrap: anywhere; }
.nobody .big {
  display: block; color: var(--c-mark); line-height: 1; white-space: nowrap;
  font-size: min(clamp(4rem, 14vw, 10rem), calc(96cqi / (var(--d, 2) * 0.62)));
}
.sm .nobody { font-size: clamp(1.1rem, 2.6vw, 1.6rem); }
.sm .nobody .big { font-size: min(clamp(3rem, 10vw, 6rem), calc(96cqi / (var(--d, 2) * 0.62))); }
.card-enter-active { animation: pop-in 0.35s ease-out; }
.card-leave-active { transition: opacity 0.2s; }
.card-leave-to { opacity: 0; }
</style>
