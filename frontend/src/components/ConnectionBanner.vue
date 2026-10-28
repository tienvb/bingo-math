<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ConnectionStatus } from '@/api/gameClient'

const props = defineProps<{ status: ConnectionStatus; ready: boolean }>()
const emit = defineEmits<{ retry: [] }>()
const { t } = useI18n()

const show = computed(() => props.status === 'reconnecting' || props.status === 'closed' || (props.status === 'connecting' && props.ready))
</script>

<template>
  <div v-if="show" class="conn-banner" :class="status" role="status">
    <span class="dot" aria-hidden="true" />
    <span class="text">{{ t(`app.connection.${status}`) }}</span>
    <button v-if="status === 'closed'" type="button" class="btn small alt" @click="emit('retry')">{{ t('app.reconnect') }}</button>
  </div>
</template>

<style scoped>
.conn-banner {
  position: sticky; top: 0; z-index: 30; display: flex; align-items: center; justify-content: center; gap: 0.6rem; flex-wrap: wrap;
  padding: 0.5rem 1rem; background: #fff1d6; color: #6b4500; font-weight: 800; text-align: center;
  border-bottom: 2px solid var(--c-warn);
}
.conn-banner.closed { background: #ffe1e3; color: #8a1520; border-color: var(--c-danger); }
.dot { width: 12px; height: 12px; border-radius: 50%; background: var(--c-warn); animation: blink 1s ease-in-out infinite; }
.closed .dot { background: var(--c-danger); animation: none; }
@keyframes blink { 50% { opacity: 0.25; } }
</style>
