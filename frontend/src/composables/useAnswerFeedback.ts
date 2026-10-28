import { onBeforeUnmount, ref, watch } from 'vue'
import type { OptionKey, Question, QuestionReason } from '@/api/contract'
import { useGameStore } from '@/stores/game'

/** Thời gian giữ bộ đáp án cũ để ô sai rung đỏ trước khi hiện bộ mới. */
export const WRONG_HOLD_MS = 1100

/**
 * Câu hỏi đang hiển thị + phản hồi đáp án vừa chọn.
 * Khi `answer_result` sai, giữ bộ đáp án cũ ~1 giây (ô đó rung đỏ) rồi mới hiện câu mới từ server.
 */
export function useAnswerFeedback() {
  const game = useGameStore()
  const shown = ref<Question | null>(game.question)
  const reason = ref<QuestionReason | null>(game.questionReason)
  const feedback = ref<{ key: OptionKey; correct: boolean; player_id: string } | null>(null)
  const holding = ref(false)
  let timer: ReturnType<typeof setTimeout> | null = null

  function flush() {
    timer = null
    holding.value = false
    shown.value = game.question
    reason.value = game.questionReason
    feedback.value = null
  }

  watch(
    () => game.lastAnswer,
    (a) => {
      const q = shown.value
      if (!a || !q || a.question_id !== q.question_id || a.attempt !== q.attempt) return
      feedback.value = { key: a.key, correct: a.correct, player_id: a.player_id }
      if (!a.correct) {
        holding.value = true
        if (timer) clearTimeout(timer)
        timer = setTimeout(flush, WRONG_HOLD_MS)
      }
    },
    { flush: 'sync' },
  )

  watch(
    () => [game.question, game.questionReason] as const,
    () => {
      if (holding.value) return // flush() sẽ lấy câu mới nhất
      if (!game.question) {
        // hết câu (đúng → reveal, bỏ qua, kết thúc): giữ phản hồi "đúng" tới khi view đổi
        shown.value = null
        return
      }
      flush()
    },
    { flush: 'sync' },
  )

  onBeforeUnmount(() => timer && clearTimeout(timer))

  return { shown, reason, feedback, holding }
}
