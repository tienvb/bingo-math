<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<template>
  <main class="page home">
    <h1>{{ t('home.title') }}</h1>
    <p class="subtitle">{{ t('home.subtitle') }}</p>
    <nav class="big-actions">
      <RouterLink class="big-btn" to="/create">{{ t('home.createRoom') }}</RouterLink>
      <RouterLink class="big-btn alt" to="/play">{{ t('home.joinRoom') }}</RouterLink>
    </nav>
  </main>
</template>

<style scoped>
.home { text-align: center; }
.subtitle { font-size: 1.4rem; }
.big-actions { display: flex; flex-direction: column; gap: 1rem; align-items: center; margin-top: 2rem; }
</style>
