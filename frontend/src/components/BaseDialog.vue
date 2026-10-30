<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps<{ open: boolean; title: string }>()
const emit = defineEmits<{ close: [] }>()
const panel = ref<HTMLElement | null>(null)

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('close')
}
watch(
  () => props.open,
  (o) => {
    if (o) {
      window.addEventListener('keydown', onKey)
      void nextTick(() => panel.value?.focus())
    } else window.removeEventListener('keydown', onKey)
  },
  { immediate: true },
)
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="backdrop" @click.self="emit('close')">
      <div ref="panel" class="dialog card" role="dialog" aria-modal="true" :aria-label="title" tabindex="-1">
        <h2 class="title">{{ title }}</h2>
        <div class="body"><slot /></div>
        <div class="actions"><slot name="actions" /></div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.backdrop {
  position: fixed; inset: 0; z-index: 50; background: rgba(43, 45, 66, 0.45);
  display: flex; align-items: center; justify-content: center;
  padding: calc(1rem + var(--safe-t)) calc(1rem + var(--safe-r)) calc(1rem + var(--safe-b)) calc(1rem + var(--safe-l));
}
.dialog {
  width: min(100%, 520px); max-height: 100%; overflow-y: auto; display: flex; flex-direction: column; gap: 0.8rem;
  animation: pop-in 0.2s ease-out; outline: none;
}
.title { margin: 0; }
.body { display: flex; flex-direction: column; gap: 0.8rem; }
.actions { display: flex; flex-wrap: wrap; gap: 0.6rem; justify-content: flex-end; }
@media (max-width: 480px) {
  .backdrop { align-items: flex-end; }
  .actions :slotted(.btn) { flex: 1 1 auto; }
}
</style>
