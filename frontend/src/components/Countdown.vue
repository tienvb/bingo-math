<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useGameStore } from '@/stores/game'
import { secondsLeft } from '@/utils/time'

const props = withDefaults(defineProps<{ deadline: string | null; total?: number; size?: 'sm' | 'md' | 'lg' }>(), {
  total: 0,
  size: 'md',
})
const { t } = useI18n()
const game = useGameStore()

const left = computed(() => secondsLeft(props.deadline, game.serverNow))
const frac = computed(() => {
  if (left.value === null || !props.total) return 1
  return Math.max(0, Math.min(1, left.value / props.total))
})
const urgent = computed(() => left.value !== null && left.value <= 5)
</script>

<template>
  <div
    v-if="left !== null" class="countdown" :class="[size, { urgent }]" role="timer"
    :aria-label="t('question.secondsLeft', { n: left })"
  >
    <svg viewBox="0 0 100 100" aria-hidden="true">
      <circle class="track" cx="50" cy="50" r="44" />
      <circle class="bar" cx="50" cy="50" r="44" pathLength="100" :style="{ strokeDashoffset: 100 - frac * 100 }" />
    </svg>
    <span class="num">{{ left }}</span>
  </div>
</template>

<style scoped>
.countdown { position: relative; display: inline-grid; place-items: center; width: var(--s); height: var(--s); flex: none; }
.sm { --s: 52px; font-size: 1.2rem; }
.md { --s: 76px; font-size: 1.8rem; }
.lg { --s: clamp(90px, 10vw, 150px); font-size: clamp(2rem, 4vw, 3.4rem); }
svg { position: absolute; inset: 0; width: 100%; height: 100%; transform: rotate(-90deg); }
.track { fill: #fff; stroke: #eee3d3; stroke-width: 9; }
.bar { fill: none; stroke: var(--c-secondary); stroke-width: 9; stroke-linecap: round; stroke-dasharray: 100; transition: stroke-dashoffset 0.25s linear; }
.urgent .bar { stroke: var(--c-danger); }
.num { position: relative; font-weight: 900; font-variant-numeric: tabular-nums; }
.urgent .num { color: var(--c-danger); animation: tick 1s ease-in-out infinite; }
@keyframes tick { 50% { transform: scale(1.15); } }
</style>
