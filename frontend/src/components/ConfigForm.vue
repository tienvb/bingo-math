<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { GameConfig, NextMode } from '@/api/contract'
import { configIssues } from '@/utils/config'
import { MIN_R_SIZE, availableCount } from '@/utils/numberRange'

const props = defineProps<{ modelValue: GameConfig; disabled?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [GameConfig] }>()
const { t } = useI18n()

type OpKey = keyof GameConfig['operations']
const OPS: { key: OpKey; sym: string }[] = [
  { key: 'add', sym: '+' },
  { key: 'sub', sym: '−' },
  { key: 'mul', sym: '×' },
  { key: 'div', sym: ':' },
]
const LIMITS = { timer: [5, 120], maxWrong: [1, 5], reveal: [2, 15] } as const
const DEFAULT_TIMER = 20

const cfg = computed(() => props.modelValue)
function patch(p: Partial<GameConfig>) {
  emit('update:modelValue', { ...cfg.value, ...p, operations: { ...cfg.value.operations, ...(p.operations ?? {}) } })
}
function toggleOp(k: OpKey) {
  patch({ operations: { ...cfg.value.operations, [k]: !cfg.value.operations[k] } })
}
const timerOn = computed(() => cfg.value.timer_seconds > 0)
function toggleTimer() {
  patch({ timer_seconds: timerOn.value ? 0 : DEFAULT_TIMER })
}
const clamp = (v: number, [lo, hi]: readonly [number, number]) => Math.min(hi, Math.max(lo, Math.round(v)))
function step(field: 'timer_seconds' | 'max_wrong' | 'reveal_seconds', delta: number) {
  const lim = field === 'timer_seconds' ? LIMITS.timer : field === 'max_wrong' ? LIMITS.maxWrong : LIMITS.reveal
  patch({ [field]: clamp((cfg.value[field] || lim[0]) + delta, lim) } as Partial<GameConfig>)
}
function setNum(field: 'timer_seconds' | 'max_wrong' | 'reveal_seconds', raw: string) {
  const lim = field === 'timer_seconds' ? LIMITS.timer : field === 'max_wrong' ? LIMITS.maxWrong : LIMITS.reveal
  const n = Number(raw)
  if (Number.isFinite(n)) patch({ [field]: clamp(n, lim) } as Partial<GameConfig>)
}
const issues = computed(() => configIssues(cfg.value))
const noOps = computed(() => issues.value.includes('no_operation'))

// ---- Số lớn nhất (max_number): giữ chuỗi đang gõ để báo lỗi ngay, kể cả khi chưa hợp lệ ----
const maxText = ref(String(cfg.value.max_number))
watch(
  () => cfg.value.max_number,
  (m) => {
    if (Number(maxText.value.trim()) !== m) maxText.value = Number.isFinite(m) ? String(m) : ''
  },
)
function onMaxInput(raw: string) {
  maxText.value = raw
  const v = raw.trim()
  // Chỉ nhận chữ số; rỗng hoặc ký tự lạ → NaN để form báo "hãy nhập số nguyên".
  patch({ max_number: /^\d+$/.test(v) ? Number(v) : Number.NaN })
}
const maxError = computed(() => {
  const i = issues.value
  if (i.includes('max_number_invalid')) return t('create.maxNumberInvalid')
  if (i.includes('max_number_too_small')) return t('create.maxNumberTooSmall')
  if (i.includes('max_number_too_large')) return t('create.maxNumberTooLarge')
  if (i.includes('too_few_numbers'))
    return t('create.tooFewNumbers', { n: availableCount(cfg.value.operations, cfg.value.max_number) ?? 0, min: MIN_R_SIZE })
  return null
})

const NEXT_MODES: NextMode[] = ['auto', 'manual']
</script>

<template>
  <div class="config-form" :class="{ disabled }">
    <fieldset class="group">
      <legend class="field-label">{{ t('create.operations') }}</legend>
      <div class="ops">
        <button
          v-for="o in OPS" :key="o.key" type="button" class="op" :class="{ on: cfg.operations[o.key] }"
          role="switch" :aria-checked="cfg.operations[o.key]" :disabled="disabled" @click="toggleOp(o.key)"
        >
          <span class="sym" aria-hidden="true">{{ o.key === 'div' ? t('create.divSymbol') : o.sym }}</span>
          <span class="op-name">{{ t(`operations.${o.key}`) }}</span>
        </button>
      </div>
      <p v-if="noOps" class="error-text">{{ t('create.needOperation') }}</p>
    </fieldset>

    <div class="group">
      <label class="field-label" for="cfg-max-number">{{ t('create.maxNumber') }}</label>
      <input
        id="cfg-max-number" class="input max-num" type="text" inputmode="numeric" autocomplete="off" spellcheck="false"
        :value="maxText" :disabled="disabled" :aria-invalid="!!maxError" aria-describedby="cfg-max-number-hint"
        @input="onMaxInput(($event.target as HTMLInputElement).value)"
      />
      <p v-if="maxError" class="error-text" role="alert">{{ maxError }}</p>
      <p id="cfg-max-number-hint" class="muted hint">{{ t('create.maxNumberHint') }}</p>
    </div>

    <fieldset class="group">
      <legend class="field-label">{{ t('create.nextMode') }}</legend>
      <div class="modes" role="radiogroup" :aria-label="t('create.nextMode')">
        <button
          v-for="m in NEXT_MODES" :key="m" type="button" class="mode" :class="{ on: cfg.next_mode === m }"
          role="radio" :aria-checked="cfg.next_mode === m" :disabled="disabled" @click="patch({ next_mode: m })"
        >
          <strong>{{ t(`create.nextModes.${m}`) }}</strong>
          <span class="mode-hint">{{ t(`create.nextModes.${m}Hint`) }}</span>
        </button>
      </div>
    </fieldset>

    <div class="group">
      <div class="line">
        <span class="field-label">{{ t('create.timer') }}</span>
        <button type="button" class="switch" role="switch" :aria-checked="timerOn" :disabled="disabled" @click="toggleTimer">
          <span class="knob" />
          <span class="visually-hidden">{{ t('create.timer') }}</span>
        </button>
      </div>
      <div v-if="timerOn" class="stepper" role="group" :aria-label="t('create.timerSeconds')">
        <button type="button" class="btn ghost" :disabled="disabled" :aria-label="t('create.less')" @click="step('timer_seconds', -5)">−</button>
        <input
          class="input num" type="number" inputmode="numeric" :min="LIMITS.timer[0]" :max="LIMITS.timer[1]"
          :value="cfg.timer_seconds" :disabled="disabled" :aria-label="t('create.timerSeconds')"
          @change="setNum('timer_seconds', ($event.target as HTMLInputElement).value)"
        />
        <button type="button" class="btn ghost" :disabled="disabled" :aria-label="t('create.more')" @click="step('timer_seconds', 5)">+</button>
        <span class="unit">{{ t('create.seconds') }}</span>
      </div>
      <p class="muted hint">{{ t('create.timerHint') }}</p>
    </div>

    <div class="group">
      <span class="field-label">{{ t('create.maxWrong') }}</span>
      <div class="stepper" role="group" :aria-label="t('create.maxWrong')">
        <button type="button" class="btn ghost" :disabled="disabled || cfg.max_wrong <= LIMITS.maxWrong[0]" :aria-label="t('create.less')" @click="step('max_wrong', -1)">−</button>
        <output class="value">{{ cfg.max_wrong }}</output>
        <button type="button" class="btn ghost" :disabled="disabled || cfg.max_wrong >= LIMITS.maxWrong[1]" :aria-label="t('create.more')" @click="step('max_wrong', 1)">+</button>
      </div>
    </div>

    <div class="group">
      <span class="field-label">{{ t('create.revealSeconds') }}</span>
      <div class="stepper" role="group" :aria-label="t('create.revealSeconds')">
        <button type="button" class="btn ghost" :disabled="disabled || cfg.reveal_seconds <= LIMITS.reveal[0]" :aria-label="t('create.less')" @click="step('reveal_seconds', -1)">−</button>
        <output class="value">{{ cfg.reveal_seconds }}</output>
        <button type="button" class="btn ghost" :disabled="disabled || cfg.reveal_seconds >= LIMITS.reveal[1]" :aria-label="t('create.more')" @click="step('reveal_seconds', 1)">+</button>
        <span class="unit">{{ t('create.seconds') }}</span>
      </div>
    </div>

    <label class="group check">
      <input
        type="checkbox" :checked="cfg.draw_only_card_numbers" :disabled="disabled"
        @change="patch({ draw_only_card_numbers: ($event.target as HTMLInputElement).checked })"
      />
      <span>
        <span class="field-label">{{ t('create.drawOnlyCardNumbers') }}</span>
        <span class="muted hint block">{{ t('create.drawOnlyHint') }}</span>
      </span>
    </label>
  </div>
</template>

<style scoped>
.config-form { display: flex; flex-direction: column; gap: 1.1rem; }
.group { border: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 0.5rem; min-width: 0; }
legend { padding: 0; margin-bottom: 0.5rem; }
.ops { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0.5rem; }
@media (max-width: 400px) { .ops { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
.op {
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 0.1rem;
  min-height: 76px; border-radius: 1rem; border: 3px solid var(--c-border); background: #fff; cursor: pointer;
  font: inherit; color: var(--c-muted); touch-action: manipulation;
}
.op.on { border-color: var(--c-success); background: #e6f8ee; color: #136b3f; }
.sym { font-size: 2rem; font-weight: 900; line-height: 1; }
.op-name { font-weight: 800; font-size: 0.9rem; }
.line { display: flex; align-items: center; justify-content: space-between; gap: 0.8rem; }
.switch {
  position: relative; flex: none; width: 64px; height: 44px; border-radius: 999px; border: none; cursor: pointer;
  background: #d9d3c7; transition: background 0.15s;
}
.switch .knob { position: absolute; top: 6px; left: 6px; width: 32px; height: 32px; border-radius: 50%; background: #fff; box-shadow: 0 2px 4px rgba(0,0,0,.2); transition: transform 0.15s; }
.switch[aria-checked='true'] { background: var(--c-success); }
.switch[aria-checked='true'] .knob { transform: translateX(20px); }
.stepper { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
.stepper .btn { width: 48px; height: 48px; padding: 0; font-size: 1.5rem; }
.value { min-width: 2.5rem; text-align: center; font-size: 1.6rem; font-weight: 900; }
.num { width: 5.5rem; text-align: center; font-weight: 900; font-size: 1.3rem; }
.unit { font-weight: 700; color: var(--c-muted); }
.hint { font-size: 0.92rem; margin: 0; }
.block { display: block; }
.check { flex-direction: row; align-items: flex-start; gap: 0.7rem; cursor: pointer; }
.check input { width: 28px; height: 28px; margin: 0.1rem 0 0; flex: none; accent-color: var(--c-success); }
.disabled { opacity: 0.7; }
.max-num { width: 100%; max-width: 18rem; font-weight: 900; font-size: 1.3rem; font-variant-numeric: tabular-nums; }
.max-num[aria-invalid='true'] { border-color: var(--c-danger); }
.modes { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.5rem; }
.mode {
  display: flex; flex-direction: column; align-items: flex-start; gap: 0.15rem; text-align: left;
  min-height: 64px; padding: 0.6rem 0.8rem; border-radius: 1rem; border: 3px solid var(--c-border); background: #fff;
  font: inherit; color: var(--c-text); cursor: pointer; touch-action: manipulation; min-width: 0;
}
.mode strong { font-size: 1.1rem; }
.mode-hint { font-size: 0.88rem; color: var(--c-muted); font-weight: 700; }
.mode.on { border-color: var(--c-success); background: #e6f8ee; }
@media (max-width: 400px) { .modes { grid-template-columns: minmax(0, 1fr); } }
</style>
