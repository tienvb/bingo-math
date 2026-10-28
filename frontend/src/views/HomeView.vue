<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<template>
  <main class="page narrow home">
    <div class="logo" aria-hidden="true">
      <span v-for="(c, i) in t('home.logo').split('')" :key="i" class="ball" :class="`b${i % 5}`">{{ c }}</span>
    </div>
    <h1>{{ t('home.title') }}</h1>
    <p class="subtitle">{{ t('home.subtitle') }}</p>
    <nav class="big-actions">
      <RouterLink class="big-btn" to="/create">{{ t('home.createRoom') }}</RouterLink>
      <RouterLink class="big-btn alt" to="/play">{{ t('home.joinRoom') }}</RouterLink>
    </nav>
    <p class="muted tip">{{ t('home.tip') }}</p>
  </main>
</template>

<style scoped>
.home { text-align: center; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 0.4rem; }
.logo { display: flex; gap: clamp(0.3rem, 2vw, 0.6rem); margin-bottom: 0.5rem; }
.ball {
  width: clamp(46px, 14vw, 72px); aspect-ratio: 1; border-radius: 50%; display: grid; place-items: center;
  color: #fff; font-weight: 900; font-size: clamp(1.4rem, 6vw, 2.2rem); box-shadow: var(--shadow);
  animation: pop-in 0.4s ease-out both;
}
.b0 { background: var(--opt-a); }
.b1 { background: var(--opt-b); animation-delay: 0.08s; }
.b2 { background: var(--opt-c); animation-delay: 0.16s; }
.b3 { background: var(--opt-d); animation-delay: 0.24s; }
.b4 { background: var(--c-primary); animation-delay: 0.32s; }
.subtitle { font-size: clamp(1.15rem, 4vw, 1.5rem); font-weight: 700; }
.big-actions { display: flex; flex-direction: column; gap: 1.1rem; align-items: center; width: 100%; margin-top: 1.5rem; }
.tip { margin-top: 1.5rem; max-width: 420px; }
</style>
