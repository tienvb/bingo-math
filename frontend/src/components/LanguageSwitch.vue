<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { LANGS, setLang, type Lang } from '@/i18n'

withDefaults(defineProps<{ compact?: boolean }>(), { compact: false })
const { t, locale } = useI18n()
const choose = (l: Lang) => setLang(l)
</script>

<template>
  <div class="lang-switch" :class="{ compact }" role="group" :aria-label="t('app.language')">
    <button
      v-for="l in LANGS" :key="l" type="button" :class="{ active: locale === l }" :aria-pressed="locale === l"
      :title="t(`app.languages.${l}`)" @click="choose(l)"
    >
      <span v-if="!compact" class="full">{{ t(`app.languages.${l}`) }}</span>
      <span :class="compact ? '' : 'short'">{{ l.toUpperCase() }}</span>
    </button>
  </div>
</template>

<style scoped>
.lang-switch { display: inline-flex; gap: 0.25rem; padding: 0.2rem; border-radius: 999px; background: #fff; box-shadow: var(--shadow); }
button {
  font: inherit; font-size: 0.95rem; font-weight: 800; min-height: 44px; min-width: 44px; padding: 0.35rem 0.85rem;
  border-radius: 999px; border: none; background: transparent; color: var(--c-primary-dark); cursor: pointer;
}
.lang-switch { min-height: var(--tap); align-items: center; }
button.active { background: var(--c-primary); color: #fff; }
.compact button { padding: 0.35rem 0.6rem; }
.short { display: none; }
@media (max-width: 520px) {
  .full { display: none; }
  .short { display: inline; }
  button { padding: 0.35rem 0.6rem; }
}
</style>
