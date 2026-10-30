<script setup lang="ts">
import { useI18n } from 'vue-i18n'

withDefaults(defineProps<{ title: string; message?: string; tone?: 'info' | 'warn' | 'error' }>(), {
  message: '',
  tone: 'info',
})
const { t } = useI18n()
</script>

<template>
  <section class="status-screen card" :class="tone" role="alert">
    <svg class="icon" viewBox="0 0 64 64" aria-hidden="true">
      <circle cx="32" cy="32" r="28" />
      <path v-if="tone === 'info'" d="M32 28v16M32 20v1" />
      <path v-else d="M32 18v18M32 44v1" />
    </svg>
    <h1 class="title">{{ title }}</h1>
    <p v-if="message" class="message">{{ message }}</p>
    <div class="actions">
      <slot>
        <RouterLink class="btn" to="/">{{ t('app.backHome') }}</RouterLink>
      </slot>
    </div>
  </section>
</template>

<style scoped>
.status-screen { display: flex; flex-direction: column; align-items: center; text-align: center; gap: 0.6rem; margin: 1.5rem auto; max-width: 520px; }
.icon { width: 72px; height: 72px; }
.icon circle { fill: #dff2ff; stroke: var(--c-secondary); stroke-width: 4; }
.icon path { stroke: var(--c-secondary-dark); stroke-width: 6; stroke-linecap: round; fill: none; }
.warn .icon circle { fill: #fff1d6; stroke: var(--c-warn); }
.warn .icon path { stroke: #c98500; }
.error .icon circle { fill: #ffe1e3; stroke: var(--c-danger); }
.error .icon path { stroke: var(--c-danger); }
.title { font-size: clamp(1.5rem, 5vw, 2.2rem); }
.message { font-size: 1.15rem; }
.actions { display: flex; flex-wrap: wrap; gap: 0.6rem; justify-content: center; margin-top: 0.5rem; }
</style>
