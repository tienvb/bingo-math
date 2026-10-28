<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import type { GameConfig } from '@/api/contract'
import { api } from '@/api/rest'
import { useSessionStore } from '@/stores/session'
import { useErrorText } from '@/composables/useErrorText'
import ConfigForm from '@/components/ConfigForm.vue'

const DEFAULT_CONFIG: GameConfig = {
  operations: { add: true, sub: true, mul: true, div: true },
  timer_seconds: 0,
  max_wrong: 2,
  reveal_seconds: 5,
  draw_only_card_numbers: true,
}

const { t } = useI18n()
const router = useRouter()
const session = useSessionStore()
const errText = useErrorText()

function initialConfig(): GameConfig {
  const last = session.loadLastConfig()
  if (!last || typeof last !== 'object' || !last.operations) return JSON.parse(JSON.stringify(DEFAULT_CONFIG)) as GameConfig
  return {
    ...DEFAULT_CONFIG,
    ...last,
    operations: { ...DEFAULT_CONFIG.operations, ...last.operations },
  }
}

const config = ref<GameConfig>(initialConfig())
const busy = ref(false)
const error = ref<string | null>(null)
const valid = computed(() => Object.values(config.value.operations).some(Boolean))
const joinBase = computed(() => session.resolveJoinBaseUrl())

async function submit() {
  error.value = null
  if (!valid.value) {
    error.value = t('errors.invalid_config')
    return
  }
  busy.value = true
  try {
    const res = await api.createRoom({ config: config.value, join_base_url: session.resolveJoinBaseUrl() })
    session.set(res.pin, { host_token: res.host_token, screen_token: res.screen_token })
    session.saveLastConfig(config.value)
    await router.push({ name: 'host', params: { pin: res.pin } })
  } catch (e) {
    error.value = errText(e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <main class="page narrow">
    <h1>{{ t('create.title') }}</h1>
    <form class="card stack" @submit.prevent="submit">
      <ConfigForm v-model="config" :disabled="busy" />
      <p class="muted small">{{ t('create.joinBaseInfo', { url: joinBase }) }}</p>
      <p v-if="error" class="error-text" role="alert">{{ error }}</p>
      <div class="actions">
        <RouterLink class="btn ghost" to="/">{{ t('app.back') }}</RouterLink>
        <button type="submit" class="btn success big" :disabled="busy || !valid">
          {{ busy ? t('app.loading') : t('create.submit') }}
        </button>
      </div>
    </form>
  </main>
</template>

<style scoped>
.small { font-size: 0.92rem; overflow-wrap: anywhere; }
.actions {
  position: sticky; bottom: 0; display: flex; gap: 0.6rem; justify-content: space-between; flex-wrap: wrap;
  padding: 0.6rem 0 calc(0.2rem + var(--safe-b)); background: linear-gradient(to top, #fff 75%, rgba(255, 255, 255, 0));
}
.big { font-size: 1.3rem; min-height: 56px; padding: 0.7rem 2rem; flex: 1 1 180px; }
</style>
