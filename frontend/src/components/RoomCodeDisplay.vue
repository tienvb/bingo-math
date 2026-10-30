<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { RoomIcon as RoomIconId } from '@/api/contract'
import RoomIcon from './RoomIcon.vue'

withDefaults(defineProps<{ pin: string; pictures: RoomIconId[]; size?: 'sm' | 'md' | 'lg'; showLabels?: boolean }>(), {
  size: 'md',
  showLabels: true,
})
const { t } = useI18n()
</script>

<template>
  <div class="room-code" :class="size" role="group" :aria-label="t('room.codeLabel')">
    <div class="pin-block">
      <span v-if="showLabels && size !== 'sm'" class="label">{{ t('room.pin') }}</span>
      <span class="pin" :aria-label="t('room.pinAria', { pin: pin.split('').join(' ') })">
        <span v-for="(d, i) in pin.split('')" :key="i" class="digit">{{ d }}</span>
      </span>
    </div>
    <div v-if="pictures.length" class="pics-block">
      <span v-if="showLabels && size !== 'sm'" class="label">{{ t('room.pictures') }}</span>
      <ol class="pics">
        <li v-for="(p, i) in pictures" :key="p + i" class="pic">
          <span class="img"><span class="num">{{ i + 1 }}</span><RoomIcon :icon="p" /></span>
          <span v-if="size === 'lg'" class="name">{{ t(`roomIcons.${p}`) }}</span>
        </li>
      </ol>
    </div>
  </div>
</template>

<style scoped>
.room-code { display: flex; flex-direction: column; align-items: center; gap: 0.6rem; min-width: 0; }
.label { display: block; text-align: center; font-weight: 800; color: var(--c-muted); font-size: 0.95rem; }
.pin { display: flex; gap: 0.35em; justify-content: center; }
.digit {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 1.15em; padding: 0.05em 0.15em; border-radius: 0.25em;
  background: #fff; box-shadow: var(--shadow); font-weight: 900; color: var(--c-primary-dark);
  font-variant-numeric: tabular-nums; line-height: 1.1;
}
.pics-block { display: flex; flex-direction: column; align-items: center; gap: 0.5em; }
.lg .pics-block { gap: 0.25em; }
.pics { list-style: none; display: flex; gap: 0.6em; padding: 0; margin: 0; justify-content: center; }
.pic { position: relative; display: flex; flex-direction: column; align-items: center; gap: 0.2em; }
.img { position: relative; display: block; background: #fff; border-radius: 0.6em; box-shadow: var(--shadow); padding: 0.15em; }
.num {
  position: absolute; top: -0.45em; left: -0.45em; z-index: 1;
  width: 1.5em; height: 1.5em; border-radius: 50%; display: grid; place-items: center;
  background: var(--c-secondary); color: #fff; font-weight: 900; font-size: 0.8em;
}
.name { font-weight: 800; font-size: 0.3em; text-align: center; }

.sm { flex-direction: row; gap: 0.6rem; font-size: 1.1rem; }
.sm .digit { box-shadow: none; background: transparent; min-width: 0.7em; }
.sm .pin { gap: 0.1em; }
.sm .img { width: 1.9rem; height: 1.9rem; box-shadow: none; }
.sm .pics { gap: 0.3rem; }
.sm .num { font-size: 0.55rem; }

.md { font-size: clamp(1.6rem, 6vw, 2.4rem); }
.md .img { width: clamp(2.6rem, 10vw, 3.6rem); height: clamp(2.6rem, 10vw, 3.6rem); }
.md .num { font-size: 0.4em; }

.lg { font-size: clamp(2.6rem, min(9vw, 11vh), 7rem); gap: 1rem; }
.lg .img { width: clamp(3.5rem, min(13vw, 15vh), 9rem); height: clamp(3.5rem, min(13vw, 15vh), 9rem); padding: 0.1em; }
.lg .num { font-size: 0.3em; }
.lg .label { font-size: clamp(1rem, 2vw, 1.5rem); }
</style>
