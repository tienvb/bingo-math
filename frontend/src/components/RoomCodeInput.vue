<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ROOM_ICONS, type RoomIcon as RoomIconId } from '@/api/contract'
import RoomIcon from './RoomIcon.vue'

const props = defineProps<{ busy?: boolean; error?: string | null }>()
const emit = defineEmits<{ pictures: [RoomIconId[]]; pin: [string] }>()
const { t } = useI18n()

const tab = ref<'pictures' | 'pin'>('pictures')

// ---- Chọn hình ----
const chosen = ref<RoomIconId[]>([])
function choose(icon: RoomIconId) {
  if (props.busy || chosen.value.length >= 3 || chosen.value.includes(icon)) return
  chosen.value = [...chosen.value, icon]
  if (chosen.value.length === 3) emit('pictures', [...chosen.value])
}
function removeLast() {
  chosen.value = chosen.value.slice(0, -1)
}
function clearPictures() {
  chosen.value = []
}

// ---- Nhập số ----
const digits = ref<string[]>(['', '', '', ''])
const inputs = ref<HTMLInputElement[]>([])
const pin = computed(() => digits.value.join(''))

function focusAt(i: number) {
  void nextTick(() => inputs.value[i]?.focus())
}
function onInput(i: number, ev: Event) {
  const el = ev.target as HTMLInputElement
  const only = el.value.replace(/\D/g, '')
  if (only.length > 1) {
    // dán hoặc bàn phím gợi ý nhiều số
    fill(only, i)
    return
  }
  digits.value[i] = only
  el.value = only
  if (only && i < 3) focusAt(i + 1)
  submitIfFull()
}
function fill(text: string, from = 0) {
  const ds = text.replace(/\D/g, '').slice(0, 4 - from).split('')
  ds.forEach((d, k) => (digits.value[from + k] = d))
  focusAt(Math.min(3, from + ds.length))
  submitIfFull()
}
function onKeydown(i: number, ev: KeyboardEvent) {
  if (ev.key === 'Backspace' && !digits.value[i] && i > 0) {
    digits.value[i - 1] = ''
    focusAt(i - 1)
    ev.preventDefault()
  } else if (ev.key === 'ArrowLeft' && i > 0) focusAt(i - 1)
  else if (ev.key === 'ArrowRight' && i < 3) focusAt(i + 1)
  else if (ev.key === 'Enter') submitIfFull()
}
function onPaste(i: number, ev: ClipboardEvent) {
  const text = ev.clipboardData?.getData('text') ?? ''
  if (text) {
    ev.preventDefault()
    fill(text, i)
  }
}
function submitIfFull() {
  if (/^\d{4}$/.test(pin.value) && !props.busy) emit('pin', pin.value)
}
function clearPin() {
  digits.value = ['', '', '', '']
  focusAt(0)
}

function switchTab(next: 'pictures' | 'pin') {
  tab.value = next
  if (next === 'pin') focusAt(digits.value.findIndex((d) => !d) === -1 ? 3 : digits.value.findIndex((d) => !d))
}

defineExpose({ clearPictures, clearPin })
</script>

<template>
  <div class="code-input">
    <div class="tabs" role="tablist">
      <button
        type="button" role="tab" class="tab" :class="{ active: tab === 'pictures' }"
        :aria-selected="tab === 'pictures'" @click="switchTab('pictures')"
      >
        {{ t('play.pickPictures') }}
      </button>
      <button
        type="button" role="tab" class="tab" :class="{ active: tab === 'pin' }"
        :aria-selected="tab === 'pin'" @click="switchTab('pin')"
      >
        {{ t('play.enterPin') }}
      </button>
    </div>

    <section v-if="tab === 'pictures'" class="pane" role="tabpanel">
      <p class="hint">{{ t('play.pickPicturesHint') }}</p>
      <div class="slots">
        <div v-for="i in 3" :key="i" class="slot" :class="{ filled: chosen[i - 1] }">
          <span class="slot-num">{{ i }}</span>
          <RoomIcon v-if="chosen[i - 1]" :icon="chosen[i - 1]" />
        </div>
        <button
          type="button" class="btn ghost erase" :disabled="!chosen.length || busy"
          :aria-label="t('play.removeLastPicture')" @click="removeLast"
        >
          <svg viewBox="0 0 24 24" width="26" height="26" aria-hidden="true">
            <path d="M9 5h11a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H9l-6-7z" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round" />
            <path d="M12 9l6 6M18 9l-6 6" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" />
          </svg>
        </button>
      </div>
      <div class="grid">
        <button
          v-for="icon in ROOM_ICONS" :key="icon" type="button" class="pic"
          :class="{ used: chosen.includes(icon) }"
          :disabled="busy || chosen.includes(icon) || chosen.length >= 3"
          :aria-label="t(`roomIcons.${icon}`)"
          @click="choose(icon)"
        >
          <RoomIcon :icon="icon" decorative />
          <span class="pic-name">{{ t(`roomIcons.${icon}`) }}</span>
        </button>
      </div>
    </section>

    <section v-else class="pane" role="tabpanel">
      <p class="hint">{{ t('play.enterPinHint') }}</p>
      <div class="digits" @click.self="focusAt(digits.findIndex((d) => !d) === -1 ? 3 : digits.findIndex((d) => !d))">
        <input
          v-for="(d, i) in digits" :key="i" ref="inputs"
          class="digit" type="text" inputmode="numeric" pattern="[0-9]*" autocomplete="one-time-code"
          maxlength="4" :value="d" :disabled="busy" :aria-label="t('play.digitAria', { n: i + 1 })"
          @input="onInput(i, $event)" @keydown="onKeydown(i, $event)" @paste="onPaste(i, $event)"
          @focus="($event.target as HTMLInputElement).select()"
        />
      </div>
      <div class="row center-row">
        <button type="button" class="btn ghost small" :disabled="busy || !pin" @click="clearPin">{{ t('play.clear') }}</button>
        <button type="button" class="btn" :disabled="busy || pin.length !== 4" @click="submitIfFull">{{ t('play.go') }}</button>
      </div>
    </section>

    <p v-if="error" class="error-text center" role="alert">{{ error }}</p>
  </div>
</template>

<style scoped>
.code-input { display: flex; flex-direction: column; gap: 1rem; }
.tabs { display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem; background: #fff; padding: 0.35rem; border-radius: 999px; box-shadow: var(--shadow); }
.tab {
  font: inherit; font-weight: 900; font-size: 1.1rem; min-height: 48px; border: none; border-radius: 999px;
  background: transparent; color: var(--c-muted); cursor: pointer;
}
.tab.active { background: var(--c-secondary); color: #fff; }
.pane { display: flex; flex-direction: column; gap: 0.9rem; }
.hint { text-align: center; font-size: 1.1rem; font-weight: 700; }
.slots { display: flex; gap: 0.6rem; justify-content: center; align-items: center; }
.slot {
  position: relative; width: clamp(64px, 20vw, 92px); aspect-ratio: 1; border-radius: 1rem;
  border: 3px dashed #d9c6ad; background: #fffdf9; padding: 0.4rem;
}
.slot.filled { border-style: solid; border-color: var(--c-secondary); background: #fff; animation: pop-in 0.2s ease-out; }
.slot-num {
  position: absolute; top: -0.6rem; left: -0.6rem; width: 1.6rem; height: 1.6rem; border-radius: 50%;
  display: grid; place-items: center; background: var(--c-secondary); color: #fff; font-weight: 900; font-size: 0.9rem;
}
.erase { width: 56px; height: 56px; padding: 0; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(96px, 28%), 1fr)); gap: 0.6rem; }
.pic {
  display: flex; flex-direction: column; align-items: center; gap: 0.2rem;
  min-height: 88px; padding: 0.5rem 0.25rem 0.4rem; border-radius: 1rem; border: 3px solid transparent;
  background: #fff; box-shadow: var(--shadow); cursor: pointer; font: inherit; touch-action: manipulation;
}
.pic :deep(.room-icon) { width: 100%; height: auto; aspect-ratio: 1; max-height: 64px; }
.pic:active:not(:disabled) { transform: scale(0.95); }
.pic.used { opacity: 0.3; }
.pic:disabled:not(.used) { opacity: 0.8; cursor: default; }
.pic-name { font-size: 0.85rem; font-weight: 800; line-height: 1.1; text-align: center; }
.digits { display: flex; gap: clamp(0.4rem, 3vw, 0.9rem); justify-content: center; }
.digit {
  width: clamp(56px, 18vw, 84px); height: clamp(68px, 22vw, 96px); text-align: center;
  font: inherit; font-size: clamp(2.2rem, 10vw, 3.2rem); font-weight: 900; color: var(--c-primary-dark);
  border-radius: 1rem; border: 3px solid var(--c-border); background: #fff; box-shadow: var(--shadow); padding: 0;
}
.digit:focus { border-color: var(--c-secondary); outline: none; }
.center-row { justify-content: center; }
</style>
