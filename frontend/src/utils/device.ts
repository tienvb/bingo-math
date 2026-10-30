import { readString, writeString } from './storage'

export function prefersReducedMotion(): boolean {
  try {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches
  } catch {
    return false
  }
}

/** Rung máy nếu trình duyệt hỗ trợ (iOS Safari không hỗ trợ: bỏ qua). */
export function vibrate(pattern: number | number[]): void {
  try {
    if (typeof navigator !== 'undefined' && 'vibrate' in navigator) navigator.vibrate(pattern)
  } catch {
    /* bỏ qua */
  }
}

/** Sao chép văn bản; có dự phòng cho http (không có navigator.clipboard ngoài secure context). */
export async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {
    /* thử cách dự phòng */
  }
  try {
    const ta = document.createElement('textarea')
    ta.value = text
    ta.setAttribute('readonly', '')
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(ta)
    return ok
  } catch {
    return false
  }
}

// ---- Âm thanh tùy chọn (chỉ màn hình chính, mặc định tắt) ----
const KEY_SOUND = 'bingo.screenSound'
let audioCtx: AudioContext | null = null

export function loadSoundEnabled(): boolean {
  return readString(KEY_SOUND) === '1'
}
export function saveSoundEnabled(on: boolean): void {
  writeString(KEY_SOUND, on ? '1' : '0')
}

/** Chuỗi nốt ngắn bằng WebAudio, không cần file âm thanh. */
export function playTones(freqs: number[], stepMs = 140): void {
  try {
    const Ctx = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
    if (!Ctx) return
    audioCtx ??= new Ctx()
    const ctx = audioCtx
    if (ctx.state === 'suspended') void ctx.resume()
    freqs.forEach((f, i) => {
      const t = ctx.currentTime + (i * stepMs) / 1000
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.type = 'triangle'
      osc.frequency.value = f
      gain.gain.setValueAtTime(0.0001, t)
      gain.gain.exponentialRampToValueAtTime(0.25, t + 0.02)
      gain.gain.exponentialRampToValueAtTime(0.0001, t + stepMs / 1000 + 0.15)
      osc.connect(gain).connect(ctx.destination)
      osc.start(t)
      osc.stop(t + stepMs / 1000 + 0.2)
    })
  } catch {
    /* bỏ qua */
  }
}
