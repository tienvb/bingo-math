<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { RoomIcon as RoomIconId } from '@/api/contract'
import { api } from '@/api/rest'
import { useSessionStore } from '@/stores/session'
import { useErrorText } from '@/composables/useErrorText'
import { copyText } from '@/utils/device'
import { isLocalHost, withLang } from '@/utils/format'
import QrCode from './QrCode.vue'
import RoomCodeDisplay from './RoomCodeDisplay.vue'

const props = defineProps<{ pin: string; joinUrl: string; pictures: RoomIconId[] }>()
const { t, locale } = useI18n()
const session = useSessionStore()
const errText = useErrorText()

const qrValue = computed(() => withLang(props.joinUrl, locale.value))
const host = computed(() => {
  try {
    return new URL(props.joinUrl).hostname
  } catch {
    return ''
  }
})
const isLocal = computed(() => !!host.value && isLocalHost(host.value))

const editing = ref(false)
const draft = ref('')
const busy = ref(false)
const error = ref<string | null>(null)
const copied = ref(false)
const ips = ref<string[]>([])
const port = ref<number | null>(null)

function currentBase(): string {
  try {
    const u = new URL(props.joinUrl)
    return `${u.protocol}//${u.host}`
  } catch {
    return ''
  }
}
watch(
  () => props.joinUrl,
  () => {
    if (!editing.value) draft.value = currentBase()
  },
  { immediate: true },
)

async function loadNetwork() {
  try {
    const n = await api.network()
    ips.value = n.ips
    port.value = n.port
  } catch {
    ips.value = []
  }
}
onMounted(() => {
  if (isLocal.value) void loadNetwork()
})
watch(isLocal, (v) => v && !ips.value.length && loadNetwork())

function suggestion(ip: string): string {
  const proto = (() => {
    try {
      return new URL(props.joinUrl).protocol
    } catch {
      return 'http:'
    }
  })()
  const p = port.value ?? (Number(window.location.port) || null)
  return `${proto}//${ip}${p && p !== 80 && p !== 443 ? `:${p}` : ''}`
}

async function save(base: string, remember: boolean) {
  error.value = null
  busy.value = true
  try {
    await api.updateJoinBaseUrl(props.pin, base.trim())
    session.setJoinBaseOverride(remember ? base.trim().replace(/\/$/, '') : null)
    editing.value = false
  } catch (e) {
    error.value = errText(e)
  } finally {
    busy.value = false
  }
}

function useCurrent() {
  void save(window.location.origin, false)
}
function pickIp(ip: string) {
  draft.value = suggestion(ip)
  editing.value = true
}
async function copy() {
  copied.value = await copyText(qrValue.value)
  if (copied.value) setTimeout(() => (copied.value = false), 1800)
}
</script>

<template>
  <section class="join-panel card">
    <h2 class="title">{{ t('join.title') }}</h2>
    <div class="layout">
      <div class="qr-col">
        <QrCode :value="qrValue" />
      </div>
      <div class="info-col">
        <RoomCodeDisplay :pin="pin" :pictures="pictures" size="md" />
        <div class="url-row">
          <code class="url">{{ qrValue }}</code>
          <button type="button" class="btn alt small" @click="copy">{{ copied ? t('join.copied') : t('join.copy') }}</button>
        </div>
      </div>
    </div>

    <div v-if="isLocal" class="warn" role="alert">
      <strong>{{ t('join.localhostWarning') }}</strong>
      <template v-if="ips.length">
        <p>{{ t('join.suggested') }}</p>
        <div class="row">
          <button v-for="ip in ips" :key="ip" type="button" class="btn ghost small" @click="pickIp(ip)">{{ suggestion(ip) }}</button>
        </div>
      </template>
      <p v-else>{{ t('join.howToFindIp') }}</p>
    </div>

    <form class="edit" @submit.prevent="save(draft, true)">
      <label class="field-label" :for="`join-base-${pin}`">{{ t('join.editLabel') }}</label>
      <div class="edit-row">
        <input
          :id="`join-base-${pin}`" v-model="draft" class="input" type="url" inputmode="url" autocomplete="off"
          autocapitalize="off" spellcheck="false" placeholder="http://192.168.1.15:8080" @focus="editing = true"
        />
        <button type="submit" class="btn small" :disabled="busy || !draft.trim()">{{ t('join.save') }}</button>
      </div>
      <button type="button" class="btn ghost small" :disabled="busy" @click="useCurrent">{{ t('join.useCurrent') }}</button>
      <p v-if="error" class="error-text" role="alert">{{ error }}</p>
    </form>
  </section>
</template>

<style scoped>
.join-panel { display: flex; flex-direction: column; gap: 0.9rem; }
.title { margin: 0; }
.layout { display: grid; grid-template-columns: minmax(0, 220px) minmax(0, 1fr); gap: 1rem; align-items: center; }
@media (max-width: 560px) {
  .layout { grid-template-columns: minmax(0, 1fr); justify-items: center; }
  .qr-col { width: min(100%, 260px); }
}
.info-col { display: flex; flex-direction: column; gap: 0.8rem; min-width: 0; width: 100%; }
.url-row { display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: center; min-width: 0; }
.url {
  flex: 1 1 200px; min-width: 0; overflow-wrap: anywhere; word-break: break-all; font-size: 0.95rem;
  background: #fffaf3; padding: 0.5rem 0.7rem; border-radius: 0.6rem; border: 1px solid var(--c-border);
}
.warn { background: #fff1d6; border: 2px solid var(--c-warn); border-radius: 1rem; padding: 0.8rem 1rem; display: flex; flex-direction: column; gap: 0.4rem; }
.warn .btn { word-break: break-all; }
.edit { display: flex; flex-direction: column; gap: 0.5rem; align-items: flex-start; }
.edit-row { display: flex; gap: 0.5rem; width: 100%; flex-wrap: wrap; }
.edit-row .input { flex: 1 1 200px; }
</style>
