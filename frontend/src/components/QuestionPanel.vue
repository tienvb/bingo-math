<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Question, QuestionReason } from '@/api/contract'
import { expression } from '@/utils/format'
import AvatarBadge from './AvatarBadge.vue'
import Countdown from './Countdown.vue'

const props = withDefaults(
  defineProps<{
    question: Question
    reason?: QuestionReason | null
    /** Người xem chính là người trả lời. */
    isMe?: boolean
    timerTotal?: number
    size?: 'sm' | 'md' | 'lg'
  }>(),
  { reason: null, isMe: false, timerTotal: 0, size: 'md' },
)
const { t, locale } = useI18n()
const text = computed(() => expression(props.question, locale.value))
const reasonText = computed(() =>
  props.reason && props.reason !== 'new' ? t(`question.reason.${props.reason}`) : '',
)
</script>

<template>
  <section class="question-panel" :class="size" aria-live="polite">
    <div class="who">
      <AvatarBadge
        :avatar-id="question.answerer.avatar_id" :nickname="question.answerer.nickname"
        :size="size === 'lg' ? 'lg' : size === 'md' ? 'md' : 'sm'" layout="none"
      />
      <div class="who-text">
        <strong v-if="isMe" class="me">{{ t('question.yourTurn') }}</strong>
        <span v-else class="answering">{{ t('question.answering', { name: question.answerer.nickname }) }}</span>
        <span v-if="reasonText" class="reason">{{ reasonText }}</span>
      </div>
      <Countdown
        v-if="question.deadline" class="timer" :deadline="question.deadline" :total="timerTotal"
        :size="size === 'lg' ? 'lg' : size === 'md' ? 'md' : 'sm'"
      />
    </div>
    <p class="expr" :aria-label="text" :style="{ '--len': text.length }">{{ text }}</p>
  </section>
</template>

<style scoped>
.question-panel { display: flex; flex-direction: column; gap: 0.6rem; width: 100%; min-width: 0; container-type: inline-size; }
.who { display: flex; align-items: center; gap: 0.8rem; min-width: 0; }
.who-text { display: flex; flex-direction: column; flex: 1; min-width: 0; }
.answering, .me { font-weight: 900; font-size: 1.15rem; overflow-wrap: anywhere; }
.me { color: var(--c-primary-dark); font-size: 1.35rem; }
.reason { font-weight: 700; color: var(--c-muted); font-size: 0.95rem; }
.timer { margin-left: auto; }
.expr {
  margin: 0; text-align: center; font-weight: 900; font-variant-numeric: tabular-nums;
  font-size: clamp(2.4rem, 12vw, 4rem); line-height: 1.1; color: var(--c-text); white-space: nowrap;
  /* phép tính dài (max_number lớn): thu chữ theo bề rộng khung, không tràn */
  font-size: min(clamp(2.4rem, 12vw, 4rem), calc(100cqi / (var(--len, 8) * 0.56)));
}
.sm .expr { font-size: min(clamp(1.8rem, 8vw, 2.4rem), calc(100cqi / (var(--len, 8) * 0.56))); }
.lg .answering, .lg .me { font-size: clamp(1.4rem, 3vw, 2.6rem); }
.lg .reason { font-size: clamp(1rem, 1.8vw, 1.5rem); }
.lg .expr { font-size: min(clamp(2.2rem, min(10vw, 16vh), 9rem), calc(100cqi / (var(--len, 8) * 0.56))); }
.lg .who :deep(.avatar-badge.lg) { --s: clamp(56px, min(18vw, 16vh), 140px); }

/* điện thoại nằm ngang: thu gọn để còn chỗ cho 4 đáp án */
@media (orientation: landscape) and (max-height: 520px) {
  .question-panel { gap: 0.2rem; }
  .who :deep(.avatar-badge) { --s: 40px !important; }
  .answering, .me, .lg .answering, .lg .me { font-size: 1.05rem; }
  .reason, .lg .reason { font-size: 0.85rem; }
  .expr, .sm .expr, .lg .expr { font-size: min(clamp(1.6rem, 13vh, 3rem), calc(100cqi / (var(--len, 8) * 0.56))); }
}
</style>
