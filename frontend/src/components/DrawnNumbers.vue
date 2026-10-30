<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = withDefaults(defineProps<{ drawn: number[]; size?: 'sm' | 'md'; scroll?: boolean }>(), {
  size: 'md',
  scroll: false,
})
const { t } = useI18n()
/** Mới nhất ở đầu để luôn thấy được. */
const items = computed(() => [...props.drawn].reverse())
</script>

<template>
  <section class="drawn" :class="[size, { scroll }]" :aria-label="t('drawn.title')">
    <span class="label">{{ t('drawn.title') }} <span class="count">({{ drawn.length }})</span></span>
    <p v-if="!drawn.length" class="muted none">{{ t('drawn.none') }}</p>
    <ol v-else class="list" reversed>
      <li v-for="(n, i) in items" :key="n" class="ball" :class="{ latest: i === 0 }">{{ n }}</li>
    </ol>
  </section>
</template>

<style scoped>
.drawn { display: flex; align-items: center; gap: 0.6rem; min-width: 0; flex-wrap: wrap; }
.label { font-weight: 900; white-space: nowrap; }
.count { color: var(--c-muted); font-weight: 700; }
.none { margin: 0; }
.list { list-style: none; display: flex; flex-wrap: wrap; gap: 0.35rem; padding: 0; margin: 0; min-width: 0; flex: 1; }
.scroll .list { flex-wrap: nowrap; overflow-x: auto; overscroll-behavior-x: contain; scrollbar-width: thin; padding-bottom: 0.2rem; }
.ball { box-sizing: border-box; white-space: nowrap; max-width: 100%;
  flex: none; min-width: 2.2em; height: 2.2em; padding: 0 0.45em; border-radius: 999px; display: grid; place-items: center;
  background: #fff; border: 2px solid var(--c-border); font-weight: 900; font-variant-numeric: tabular-nums; font-size: 0.95rem;
}
.ball.latest { background: var(--c-mark); color: #fff; border-color: var(--c-mark); transform: scale(1.15); animation: pop-in 0.4s ease-out; }
.md .ball { font-size: clamp(0.95rem, 1.4vw, 1.35rem); }
</style>
