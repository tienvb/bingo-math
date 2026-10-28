<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { Avatar } from '@/api/contract'
import { useAvatars } from '@/composables/useAvatars'

defineProps<{
  avatars: Avatar[]
  modelValue: string | null
  /** Số người đã chọn mỗi nhân vật (nếu biết). */
  counts?: Record<string, number>
  disabled?: boolean
}>()
const emit = defineEmits<{ 'update:modelValue': [string] }>()
const { t } = useI18n()
const { nameOf } = useAvatars()
</script>

<template>
  <div class="avatar-picker" role="radiogroup" :aria-label="t('play.pickAvatar')">
    <button
      v-for="a in avatars" :key="a.id" type="button" class="opt" role="radio"
      :class="{ selected: modelValue === a.id }" :aria-checked="modelValue === a.id" :disabled="disabled"
      :style="{ '--av': a.color }" @click="emit('update:modelValue', a.id)"
    >
      <span class="img-wrap">
        <img :src="a.image_url" :alt="''" draggable="false" />
        <span v-if="counts && counts[a.id]" class="count" :aria-label="t('play.avatarTaken', { n: counts[a.id] })">
          {{ counts[a.id] }}
        </span>
      </span>
      <span class="name">{{ nameOf(a) }}</span>
    </button>
    <p v-if="!avatars.length" class="muted">{{ t('app.loading') }}</p>
  </div>
</template>

<style scoped>
.avatar-picker { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(120px, 30%), 1fr)); gap: 0.7rem; }
.opt {
  display: flex; flex-direction: column; align-items: center; gap: 0.35rem; min-width: 0;
  padding: 0.6rem 0.3rem; border-radius: 1.2rem; border: 4px solid transparent; background: #fff;
  box-shadow: var(--shadow); cursor: pointer; font: inherit; touch-action: manipulation;
  transition: transform 0.1s;
}
.opt:active:not(:disabled) { transform: scale(0.96); }
.opt.selected { border-color: var(--av); background: color-mix(in srgb, var(--av) 14%, #fff); transform: scale(1.03); }
.img-wrap { position: relative; width: 100%; max-width: 110px; aspect-ratio: 1; }
.img-wrap img { width: 100%; height: 100%; object-fit: contain; }
.count {
  position: absolute; top: 0; right: 0; min-width: 1.6rem; height: 1.6rem; padding: 0 0.35rem;
  border-radius: 999px; background: var(--c-text); color: #fff; font-weight: 900; font-size: 0.9rem;
  display: grid; place-items: center;
}
.name { font-weight: 800; font-size: clamp(0.85rem, 3.2vw, 1.05rem); text-align: center; line-height: 1.15; overflow-wrap: anywhere; }
</style>
