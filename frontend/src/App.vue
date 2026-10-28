<script setup lang="ts">
import { computed, watchEffect } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import LanguageSwitch from '@/components/LanguageSwitch.vue'
import { USE_MOCK } from '@/api/gameClient'

const route = useRoute()
const { t, locale } = useI18n()
/** Màn hình chính tự đặt nút ngôn ngữ ở góc để không tốn chiều cao. */
const showTopbar = computed(() => route.name !== 'screen')

watchEffect(() => {
  try {
    document.documentElement.lang = locale.value
    document.title = t('app.name')
  } catch {
    /* bỏ qua */
  }
})
</script>

<template>
  <header v-if="showTopbar" class="topbar">
    <RouterLink v-if="route.name !== 'home'" to="/" class="brand">{{ t('app.name') }}</RouterLink>
    <span v-if="USE_MOCK" class="badge mock" :title="t('app.mockHint')">{{ t('app.mock') }}</span>
    <span class="spacer" />
    <LanguageSwitch />
  </header>
  <RouterView />
</template>

<style scoped>
.brand { white-space: nowrap; font-weight: 900; font-size: 1.2rem; color: var(--c-primary-dark); text-decoration: none; min-height: var(--tap); display: inline-flex; align-items: center; }
.spacer { flex: 1; }
.mock { background: #ece5ff; color: #4b2ea3; }
@media (orientation: landscape) and (max-height: 520px) {
  .topbar { padding-top: calc(0.25rem + var(--safe-t)); padding-bottom: 0.25rem; }
}
</style>
