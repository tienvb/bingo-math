<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { RoomIcon } from '@/api/contract'

// 12 SVG riêng cho mã hình (không dùng emoji).
const urls = import.meta.glob('@/assets/room-icons/*.svg', { eager: true, query: '?url', import: 'default' }) as Record<string, string>
const byId: Record<string, string> = {}
for (const [path, url] of Object.entries(urls)) {
  const id = path.split('/').pop()!.replace('.svg', '')
  byId[id] = url
}

const props = defineProps<{ icon: RoomIcon; decorative?: boolean }>()
const { t } = useI18n()
const src = computed(() => byId[props.icon] ?? '')
</script>

<template>
  <img class="room-icon" :src="src" :alt="decorative ? '' : t(`roomIcons.${icon}`)" draggable="false" />
</template>

<style scoped>
.room-icon { display: block; width: 100%; height: 100%; object-fit: contain; pointer-events: none; }
</style>
