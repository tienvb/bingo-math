<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { OptionKey, Question } from '@/api/contract'

withDefaults(
  defineProps<{
    options: Question['options']
    /** true: bấm được (người đang trả lời); false: chỉ hiển thị. */
    interactive?: boolean
    disabled?: boolean
    /** Đáp án vừa chọn để tô (sai thì rung đỏ). */
    feedback?: { key: OptionKey; correct: boolean } | null
    pendingKey?: OptionKey | null
    size?: 'md' | 'lg'
  }>(),
  { interactive: false, disabled: false, feedback: null, pendingKey: null, size: 'md' },
)
const emit = defineEmits<{ choose: [OptionKey] }>()
const { t } = useI18n()
</script>

<template>
  <div class="answers" :class="size" role="group" :aria-label="t('question.options')">
    <component
      :is="interactive ? 'button' : 'div'"
      v-for="o in options" :key="o.key"
      :type="interactive ? 'button' : undefined"
      class="opt" :class="[`k-${o.key}`, {
        wrong: feedback?.key === o.key && !feedback.correct,
        right: feedback?.key === o.key && feedback.correct,
        pending: pendingKey === o.key,
        dim: (feedback || pendingKey) && feedback?.key !== o.key && pendingKey !== o.key,
        static: !interactive,
      }]"
      :disabled="interactive ? disabled : undefined"
      :aria-label="t('question.optionAria', { key: o.key, value: o.value })"
      @click="interactive && !disabled && emit('choose', o.key)"
    >
      <span class="key">{{ o.key }}</span>
      <span class="val">{{ o.value }}</span>
    </component>
  </div>
</template>

<style scoped>
.answers { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: clamp(0.5rem, 2vw, 1.1rem); width: 100%; }
.opt {
  --c: var(--opt-a);
  position: relative; display: flex; align-items: center; justify-content: center; gap: 0.6rem;
  min-height: clamp(76px, 18vw, 120px); padding: 0.5rem; border-radius: 1.3rem; border: none;
  background: var(--c); color: #fff; font: inherit; font-weight: 900;
  box-shadow: 0 6px 0 color-mix(in srgb, var(--c) 70%, #000); cursor: pointer; touch-action: manipulation;
  transition: transform 0.08s, opacity 0.2s, box-shadow 0.08s;
}
.opt.static { cursor: default; }
.k-B { --c: var(--opt-b); }
.k-C { --c: var(--opt-c); }
.k-D { --c: var(--opt-d); }
button.opt:active:not(:disabled) { transform: translateY(4px); box-shadow: 0 2px 0 color-mix(in srgb, var(--c) 70%, #000); }
button.opt:disabled { cursor: not-allowed; }
.key {
  position: absolute; top: 0.45rem; left: 0.6rem; font-size: clamp(1rem, 3vw, 1.4rem);
  width: 1.8em; height: 1.8em; border-radius: 50%; display: grid; place-items: center; background: rgba(255, 255, 255, 0.28);
}
.val { font-size: clamp(2.2rem, 10vw, 3.6rem); font-variant-numeric: tabular-nums; text-shadow: 0 2px 0 rgba(0, 0, 0, 0.15); }
.lg .opt { min-height: clamp(56px, 16vh, 210px); border-radius: 1.8rem; }
.lg .val { font-size: clamp(2rem, min(7vw, 11vh), 6.5rem); }
.lg .key { font-size: clamp(1.1rem, 2.2vw, 2.2rem); }
.dim { opacity: 0.45; }
.pending { outline: 5px solid #fff; outline-offset: -9px; animation: pulse 0.9s ease-in-out infinite; }
.wrong { --c: var(--c-danger); animation: shake 0.5s ease-in-out 2; }
.right { --c: var(--c-success); animation: pop-in 0.3s ease-out; }
@keyframes pulse { 50% { transform: scale(0.97); } }

/* điện thoại nằm ngang: 4 đáp án trên một hàng để thấy hết không cần cuộn */
@media (orientation: landscape) and (max-height: 520px) {
  .answers { grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0.5rem; }
  .opt, .lg .opt { min-height: clamp(52px, 17vh, 76px); border-radius: 1rem; box-shadow: 0 4px 0 color-mix(in srgb, var(--c) 70%, #000); }
  .val, .lg .val { font-size: clamp(1.5rem, 10vh, 2.4rem); }
  .key, .lg .key { top: 0.25rem; left: 0.3rem; font-size: 0.8rem; }
}
</style>
