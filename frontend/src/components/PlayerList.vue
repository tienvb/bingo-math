<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { PlayerInfo } from '@/api/contract'
import AvatarBadge from './AvatarBadge.vue'

withDefaults(
  defineProps<{
    players: PlayerInfo[]
    kickable?: boolean
    highlightId?: string | null
    meId?: string | null
    layout?: 'list' | 'tiles'
    busyId?: string | null
  }>(),
  { kickable: false, highlightId: null, meId: null, layout: 'list', busyId: null },
)
const emit = defineEmits<{ kick: [PlayerInfo] }>()
const { t } = useI18n()
</script>

<template>
  <div class="player-list" :class="layout">
    <p v-if="!players.length" class="empty muted">{{ t('players.empty') }}</p>
    <TransitionGroup v-else tag="ul" name="pl" class="items">
      <li v-for="p in players" :key="p.id" class="item" :class="{ hl: p.id === highlightId, off: !p.connected }">
        <AvatarBadge
          :avatar-id="p.avatar_id" :nickname="p.nickname" :connected="p.connected"
          :size="layout === 'tiles' ? 'lg' : 'sm'" :layout="layout === 'tiles' ? 'column' : 'row'"
        />
        <span v-if="p.id === meId" class="badge me">{{ t('players.you') }}</span>
        <button
          v-if="kickable" type="button" class="btn ghost small kick" :disabled="busyId === p.id"
          :aria-label="t('players.kickAria', { name: p.nickname })" @click="emit('kick', p)"
        >
          {{ t('players.kick') }}
        </button>
      </li>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.items { list-style: none; padding: 0; margin: 0; }
.list .items { display: flex; flex-direction: column; gap: 0.4rem; }
.list .item {
  display: flex; align-items: center; gap: 0.5rem; padding: 0.35rem 0.5rem; border-radius: 0.9rem;
  background: #fffaf3; min-width: 0;
}
.list .item :deep(.avatar-badge) { flex: 1; }
.tiles .items { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(150px, 45%), 1fr)); gap: 1rem; }
.tiles .item { display: flex; flex-direction: column; align-items: center; gap: 0.3rem; padding: 0.5rem; min-width: 0; }
.item.hl { background: #fff3b0; box-shadow: 0 0 0 3px var(--c-warn); }
.item.off { opacity: 0.6; }
.me { background: #dff2ff; color: #145a8a; }
.kick { flex: none; }
.pl-enter-active { animation: pop-in 0.35s ease-out; }
.pl-leave-active { transition: opacity 0.2s; }
.pl-leave-to { opacity: 0; }
</style>
