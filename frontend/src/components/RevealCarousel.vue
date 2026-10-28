<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Reveal } from '@/api/contract'
import { useGameStore } from '@/stores/game'
import { revealPosition } from '@/utils/time'
import BingoCard from './BingoCard.vue'

const props = withDefaults(defineProps<{ reveal: Reveal; size?: 'md' | 'lg' }>(), { size: 'lg' })
const { t } = useI18n()
const game = useGameStore()

// Đồng bộ theo started_at: mở lại tab giữa chừng vẫn đúng vé đang hiện.
const pos = computed(() => revealPosition(props.reveal, game.serverNow))
const item = computed(() => props.reveal.items[pos.value.index] ?? null)
const perMs = computed(() => Math.max(1, props.reveal.seconds_per_card) * 1000)
const progress = computed(() => Math.min(1, pos.value.elapsedInCard / perMs.value))
</script>

<template>
  <section class="reveal" :class="size" aria-live="polite">
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
          :size="size"
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
.new-number { font-weight: 900; font-size: clamp(1.4rem, 4vw, 3rem); }
.num { color: var(--c-mark); font-size: 1.35em; }
.counter { font-weight: 800; color: var(--c-muted); font-size: clamp(1.1rem, 2.5vw, 2rem); }
.stage { display: flex; flex-direction: column; align-items: center; gap: 0.6rem; width: 100%; min-height: 0; }
/* lg: vé vừa chiều cao màn hình 1080p (trừ tiêu đề và dải số đã ra) */
.lg .the-card { width: min(100%, calc(100dvh - 300px), 720px); min-width: min(100%, 300px); }
.md .the-card { width: min(100%, 460px); }
.progress { width: min(100%, 420px); height: 8px; background: #efe3d1; border-radius: 99px; overflow: hidden; }
.progress span { display: block; height: 100%; background: var(--c-secondary); transform-origin: left; transition: transform 0.25s linear; }
.dots { list-style: none; display: flex; flex-wrap: wrap; justify-content: center; gap: 0.4rem; padding: 0; margin: 0; }
.dots li { width: 12px; height: 12px; border-radius: 50%; background: #e3d6c3; }
.dots li.done { background: #b8c7d6; }
.dots li.on { background: var(--c-secondary); transform: scale(1.3); }
.nobody { text-align: center; font-weight: 800; font-size: clamp(1.3rem, 3.5vw, 2.6rem); }
.nobody .big { display: block; font-size: clamp(4rem, 14vw, 10rem); color: var(--c-mark); line-height: 1; }
.card-enter-active { animation: pop-in 0.35s ease-out; }
.card-leave-active { transition: opacity 0.2s; }
.card-leave-to { opacity: 0; }
</style>
