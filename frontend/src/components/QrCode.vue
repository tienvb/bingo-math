<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import QRCode from 'qrcode'

const props = defineProps<{ value: string }>()
const { t } = useI18n()
const src = ref('')

watch(
  () => props.value,
  async (v) => {
    if (!v) {
      src.value = ''
      return
    }
    try {
      src.value = await QRCode.toDataURL(v, { errorCorrectionLevel: 'M', margin: 1, width: 512, color: { dark: '#2b2d42', light: '#ffffff' } })
    } catch (e) {
      console.warn('[qr] failed', e)
      src.value = ''
    }
  },
  { immediate: true },
)
</script>

<template>
  <div class="qr">
    <img v-if="src" :src="src" :alt="t('join.qrAlt', { url: value })" draggable="false" />
  </div>
</template>

<style scoped>
.qr { width: 100%; aspect-ratio: 1; background: #fff; border-radius: 1rem; padding: 4%; box-shadow: var(--shadow); }
.qr img { width: 100%; height: 100%; display: block; image-rendering: pixelated; }
</style>
