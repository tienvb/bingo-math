<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { LANGS, setLang, type Lang } from '@/i18n'

const { t, locale } = useI18n()
const choose = (l: Lang) => setLang(l)
</script>

<template>
  <div class="lang-switch" role="group" :aria-label="t('app.language')">
    <button
      v-for="l in LANGS"
      :key="l"
      type="button"
      :class="{ active: locale === l }"
      :aria-pressed="locale === l"
      @click="choose(l)"
    >
      {{ t(`app.languages.${l}`) }}
    </button>
  </div>
</template>

<style scoped>
.lang-switch { display: inline-flex; gap: 0.5rem; }
button {
  font: inherit; font-size: 1rem; padding: 0.5rem 1rem; border-radius: 999px;
  border: 2px solid var(--c-primary); background: #fff; color: var(--c-primary); cursor: pointer;
}
button.active { background: var(--c-primary); color: #fff; }
</style>
