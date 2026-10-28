<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAvatars } from '@/composables/useAvatars'

const props = withDefaults(
  defineProps<{
    avatarId: string
    nickname?: string
    size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl'
    /** Hiện tên bên cạnh (row) hoặc bên dưới (column). */
    layout?: 'row' | 'column' | 'none'
    connected?: boolean | null
  }>(),
  { size: 'md', layout: 'row', connected: null, nickname: '' },
)
const { t } = useI18n()
const { byId, nameOf } = useAvatars()
const avatar = computed(() => byId(props.avatarId))
const color = computed(() => avatar.value?.color ?? '#9aa0b5')
const initial = computed(() => (props.nickname || '?').trim().charAt(0).toUpperCase())
</script>

<template>
  <span class="avatar-badge" :class="[size, layout]" :style="{ '--av': color }">
    <span class="pic">
      <img v-if="avatar" :src="avatar.image_url" :alt="nameOf(avatar)" draggable="false" />
      <span v-else class="fallback" aria-hidden="true">{{ initial }}</span>
      <span
        v-if="connected !== null" class="dot" :class="{ off: !connected }"
        :title="connected ? t('players.online') : t('players.offline')"
      />
    </span>
    <span v-if="layout !== 'none' && nickname" class="name">{{ nickname }}</span>
  </span>
</template>

<style scoped>
.avatar-badge { display: inline-flex; align-items: center; gap: 0.5rem; min-width: 0; max-width: 100%; }
.column { flex-direction: column; gap: 0.3rem; text-align: center; }
.pic {
  position: relative; flex: none; border-radius: 50%; background: #fff;
  box-shadow: 0 0 0 3px var(--av), 0 3px 8px rgba(0, 0, 0, 0.12);
  width: var(--s); height: var(--s); display: grid; place-items: center;
}
.pic img { width: 100%; height: 100%; object-fit: contain; border-radius: 50%; }
.fallback { font-weight: 900; color: var(--av); font-size: calc(var(--s) * 0.45); }
.name { font-weight: 800; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 100%; }
.dot {
  position: absolute; right: 2%; bottom: 2%; width: 26%; height: 26%; min-width: 10px; min-height: 10px;
  border-radius: 50%; background: var(--c-success); border: 2px solid #fff;
}
.dot.off { background: #b0b4c4; }
.xs { --s: 28px; font-size: 0.9rem; }
.sm { --s: 40px; font-size: 1rem; }
.md { --s: 56px; font-size: 1.1rem; }
.lg { --s: clamp(80px, 18vw, 120px); font-size: clamp(1.2rem, 3vw, 1.6rem); }
.xl { --s: clamp(140px, 32vw, 300px); font-size: clamp(1.6rem, 4vw, 2.6rem); }
.lg .pic, .xl .pic { box-shadow: 0 0 0 5px var(--av), 0 6px 16px rgba(0, 0, 0, 0.15); }
</style>
