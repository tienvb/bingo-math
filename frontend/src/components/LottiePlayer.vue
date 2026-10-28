<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { AnimationItem } from 'lottie-web'
import { prefersReducedMotion } from '@/utils/device'

/**
 * Phát file Lottie JSON (`win_animation_url` kết thúc bằng .json).
 * `lottie-web` chỉ được tải bằng dynamic import khi cần, nên nằm ở chunk riêng.
 * Dùng bản `lottie_light` (chỉ SVG, không chạy expressions/eval).
 * prefers-reduced-motion: không tự phát, dừng ở frame đầu.
 * Lỗi tải thư viện hoặc file: emit `error` để bên ngoài quay về hiệu ứng nhún nhảy.
 */
const props = defineProps<{ src: string; label?: string }>()
const emit = defineEmits<{ error: [] }>()

const el = ref<HTMLElement | null>(null)
let anim: AnimationItem | null = null
let disposed = false

function destroy() {
  try {
    anim?.destroy()
  } catch {
    /* bỏ qua */
  }
  anim = null
}

async function fetchLottie(src: string): Promise<unknown> {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), 8000)
  try {
    const res = await fetch(src, { signal: ctrl.signal })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = (await res.json()) as { layers?: unknown }
    if (!data || !Array.isArray(data.layers)) throw new Error('not a Lottie file')
    return data
  } finally {
    clearTimeout(timer)
  }
}

async function load(src: string) {
  destroy()
  if (!el.value) return
  try {
    // Tự tải và kiểm tra JSON (404, hoặc server trả index.html thay cho file → lỗi rõ ràng)
    const [mod, data] = await Promise.all([import('lottie-web/build/player/lottie_light'), fetchLottie(src)])
    if (disposed || !el.value) return
    const reduced = prefersReducedMotion()
    const a = mod.default.loadAnimation({
      container: el.value,
      renderer: 'svg',
      loop: !reduced,
      autoplay: !reduced,
      animationData: data,
      // ảnh trong file Lottie (nếu có) lấy tương đối theo thư mục của file
      assetsPath: src.replace(/[^/]*$/, ''),
      rendererSettings: { preserveAspectRatio: 'xMidYMid meet' },
    })
    anim = a
    a.addEventListener('data_failed', () => emit('error'))
    a.addEventListener('error', () => emit('error'))
    if (reduced) a.addEventListener('DOMLoaded', () => a.goToAndStop(0, true))
  } catch (e) {
    console.warn('[lottie] load failed', e)
    emit('error')
  }
}

onMounted(() => void load(props.src))
watch(
  () => props.src,
  (s) => void load(s),
)
onBeforeUnmount(() => {
  disposed = true
  destroy()
})
</script>

<template>
  <div ref="el" class="lottie" role="img" :aria-label="label ?? ''" />
</template>

<style scoped>
.lottie { width: clamp(140px, 32vw, 320px); aspect-ratio: 1; }
</style>
