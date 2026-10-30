<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Card, Cell, Line } from '@/api/contract'
import { useAvatars } from '@/composables/useAvatars'
import AvatarBadge from './AvatarBadge.vue'

const props = withDefaults(
  defineProps<{
    card: Card
    marked: Cell[]
    newCell?: Cell | null
    animateNew?: boolean
    winningLines?: Line[]
    player?: { nickname: string; avatar_id: string } | null
    size?: 'sm' | 'md' | 'lg'
  }>(),
  { newCell: null, animateNew: false, winningLines: () => [], player: null, size: 'md' },
)

const { t } = useI18n()
const { byId } = useAvatars()
const color = computed(() => (props.player ? byId(props.player.avatar_id)?.color : undefined) ?? 'var(--c-secondary)')

const key = (r: number, c: number) => r * 5 + c
const FREE = key(2, 2)

// Chỉ hiển thị theo dữ liệu server: marked (không gồm FREE) + FREE luôn coi là đã khoanh.
const markedSet = computed(() => {
  const s = new Set<number>([FREE])
  for (const [r, c] of props.marked) s.add(key(r, c))
  return s
})
const newKey = computed(() => (props.newCell ? key(props.newCell[0], props.newCell[1]) : -1))

function lineCells(l: Line): number[] {
  const idx = [0, 1, 2, 3, 4]
  if (l.type === 'row') return idx.map((c) => key(l.index, c))
  if (l.type === 'col') return idx.map((r) => key(r, l.index))
  return l.index === 0 ? idx.map((k) => key(k, k)) : idx.map((k) => key(k, 4 - k))
}
/** Ô thuộc đường thắng → thứ tự sáng lần lượt. */
const winOrder = computed(() => {
  const m = new Map<number, number>()
  props.winningLines.forEach((l, li) =>
    lineCells(l).forEach((k, i) => {
      if (!m.has(k)) m.set(k, li * 5 + i)
    }),
  )
  return m
})

const cells = computed(() =>
  props.card.flatMap((row, r) =>
    row.map((n, c) => {
      const k = key(r, c)
      const isNew = k === newKey.value
      return {
        k,
        n,
        free: k === FREE,
        d: k === FREE ? 2 : String(n).length,
        isNew,
        marked: markedSet.value.has(k) || isNew,
        win: winOrder.value.has(k),
        winDelay: `${(winOrder.value.get(k) ?? 0) * 0.18}s`,
      }
    }),
  ),
)

const ariaLabel = computed(() =>
  props.player ? t('card.ariaOf', { name: props.player.nickname }) : t('card.aria'),
)
</script>

<template>
  <figure class="bingo-card" :class="[size, { winning: winningLines.length }]" :style="{ '--card-color': color }" :aria-label="ariaLabel">
    <figcaption v-if="player" class="head">
      <AvatarBadge :avatar-id="player.avatar_id" :nickname="player.nickname" :size="size === 'lg' ? 'md' : 'sm'" />
    </figcaption>
    <div class="grid" role="grid">
      <div
        v-for="cell in cells" :key="cell.k" role="gridcell" class="cell"
        :class="{ free: cell.free, marked: cell.marked, 'is-new': cell.isNew, animate: cell.isNew && animateNew, win: cell.win }"
        :style="{ '--d': cell.d, ...(cell.win ? { '--win-delay': cell.winDelay } : {}) }"
        :aria-label="cell.free ? t('card.free') : String(cell.n)"
        :aria-selected="cell.marked"
      >
        <span class="num">{{ cell.free ? t('card.free') : cell.n }}</span>
        <svg v-if="cell.marked && !cell.free" class="ring" viewBox="0 0 100 100" aria-hidden="true">
          <circle cx="50" cy="50" r="41" pathLength="100" />
        </svg>
      </div>
    </div>
  </figure>
</template>

<style scoped>
.bingo-card {
  margin: 0; width: 100%; max-width: var(--max); min-width: 0;
  background: #fff; border-radius: 1.2rem; padding: clamp(0.4rem, 1.6cqi, 0.9rem);
  border: clamp(4px, 1vw, 8px) solid var(--card-color); box-shadow: var(--shadow);
  display: flex; flex-direction: column; gap: 0.5rem;
}
.sm { --max: 300px; }
.md { --max: 460px; }
.lg { --max: 720px; }
.head { display: flex; justify-content: center; min-width: 0; }
.grid {
  container-type: inline-size;
  display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: clamp(3px, 1.2cqi, 8px);
}
.cell {
  position: relative; aspect-ratio: 1; border-radius: 14%;
  display: grid; place-items: center; background: #fdf6ea;
  font-weight: 900; font-variant-numeric: tabular-nums; color: var(--c-text);
  font-size: 1.1rem; font-size: 8.5cqi; line-height: 1; user-select: none;
  /* số nhiều chữ số (max_number lớn): thu chữ cho vừa ô, không tràn */
  font-size: min(8.5cqi, calc(16cqi / (var(--d, 2) * 0.6)));
  min-width: 0; overflow: hidden;
}
.cell.free { background: color-mix(in srgb, var(--card-color) 22%, #fff); color: var(--c-text); font-size: 0.7rem; font-size: 4.6cqi; letter-spacing: 0.02em; }
.num { position: relative; z-index: 1; white-space: nowrap; letter-spacing: -0.02em; }
.ring { position: absolute; inset: 4%; width: 92%; height: 92%; overflow: visible; pointer-events: none; z-index: 2; }
.ring circle {
  fill: none; stroke: var(--c-mark); stroke-linecap: round;
  stroke-width: 6; opacity: 0.6; transform: rotate(-90deg); transform-origin: 50% 50%;
}

/* ô mới: vẽ trực tiếp bằng stroke-dashoffset, nét đậm, nền sáng nhấp nháy */
.cell.is-new { background: #fff3b0; }
.cell.is-new .ring circle { stroke-width: 10; opacity: 1; }
.cell.animate { animation: new-glow 1.1s ease-in-out 0.5s infinite alternate; }
.cell.animate .ring circle {
  stroke-dasharray: 100; stroke-dashoffset: 100;
  animation: draw-ring 1.2s cubic-bezier(0.6, 0.05, 0.3, 1) 0.5s forwards;
}
@keyframes draw-ring { to { stroke-dashoffset: 0; } }
@keyframes new-glow {
  from { background: #fff3b0; box-shadow: 0 0 0 0 rgba(255, 196, 0, 0); }
  to { background: #ffe066; box-shadow: 0 0 0 4px rgba(255, 196, 0, 0.55); }
}

/* đường thắng: sáng lần lượt */
.cell.win { animation: win-light 0.5s ease-out var(--win-delay, 0s) both; }
.cell.win .num { color: #5a3d00; }
@keyframes win-light {
  from { background: #fdf6ea; transform: scale(1); }
  60% { transform: scale(1.12); }
  to { background: var(--c-win); transform: scale(1); box-shadow: 0 0 0 3px #f59f00 inset; }
}
</style>
